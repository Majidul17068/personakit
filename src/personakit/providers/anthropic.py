"""Anthropic provider adapter.

Requires `personakit[anthropic]` extra (installs the official `anthropic` SDK).

Anthropic's tool-calling protocol differs from OpenAI's: tool requests appear
as `tool_use` blocks inside an assistant message's `content` list, and tool
results are sent back as `tool_result` blocks inside a user message. This
module translates personakit's OpenAI-shaped `Message.tool_calls` and
`role="tool"` messages to and from Anthropic's content-block format.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from ..errors import MissingDependencyError, ProviderError
from .base import LLMResponse, Message, StreamChunk


class AnthropicProvider:
    """Adapter around the official `anthropic` Python SDK."""

    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        default_model: str = "claude-sonnet-4-6",
        client: Any | None = None,
    ) -> None:
        self.default_model = default_model
        if client is not None:
            self._client = client
            return
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise MissingDependencyError(
                "AnthropicProvider requires the 'anthropic' package. "
                "Install with: pip install 'personakit[anthropic]'"
            ) from exc
        self._client = AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        response_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        system_parts: list[str] = []
        conv: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            else:
                conv.append(_to_anthropic_message(m))

        if response_schema is not None:
            system_parts.append(
                "Return a single JSON object matching this schema. "
                "Respond with ONLY the JSON object — no Markdown fences, no prose.\n"
                f"{response_schema}"
            )

        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "system": "\n\n".join(system_parts) if system_parts else "",
            "messages": conv,
            "max_tokens": max_tokens or 2048,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if tools:
            payload["tools"] = _to_anthropic_tools(tools)
        payload.update(kwargs)

        try:
            raw = await self._client.messages.create(**payload)
        except Exception as exc:
            raise ProviderError(f"Anthropic request failed: {exc}") from exc

        text = ""
        tool_calls: list[dict[str, Any]] = []
        for block in raw.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text += getattr(block, "text", "")
            elif btype == "tool_use":
                # Normalise Anthropic's dict `input` into an OpenAI-style JSON
                # string so downstream consumers (Agent.analyze) can treat all
                # providers identically.
                input_obj = getattr(block, "input", None) or {}
                try:
                    args_str = json.dumps(input_obj)
                except (TypeError, ValueError):
                    args_str = "{}"
                tool_calls.append(
                    {
                        "id": getattr(block, "id", None),
                        "name": getattr(block, "name", None),
                        "arguments": args_str,
                    }
                )

        usage = {}
        if getattr(raw, "usage", None) is not None:
            usage = {
                "input_tokens": getattr(raw.usage, "input_tokens", 0),
                "output_tokens": getattr(raw.usage, "output_tokens", 0),
            }
        return LLMResponse(
            text=text,
            model=raw.model,
            finish_reason=getattr(raw, "stop_reason", None),
            usage=usage,
            tool_calls=tool_calls,
            raw=raw.model_dump() if hasattr(raw, "model_dump") else {},
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        response_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Stream the model's response chunk-by-chunk via Anthropic's
        `messages.stream`.

        Anthropic's stream emits typed events: `content_block_start`,
        `content_block_delta` (with `text_delta` or `input_json_delta`),
        `message_delta` (with stop_reason), and `message_stop`. We translate
        to personakit's StreamChunk format on the fly.
        """
        system_parts: list[str] = []
        conv: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            else:
                conv.append(_to_anthropic_message(m))

        if response_schema is not None:
            system_parts.append(
                "Return a single JSON object matching this schema. "
                "Respond with ONLY the JSON object — no Markdown fences, no prose.\n"
                f"{response_schema}"
            )

        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "system": "\n\n".join(system_parts) if system_parts else "",
            "messages": conv,
            "max_tokens": max_tokens or 2048,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if tools:
            payload["tools"] = _to_anthropic_tools(tools)
        payload.update(kwargs)

        # Track the in-flight content blocks so we can re-assemble tool_use
        # input JSON across multiple input_json_delta events.
        tool_blocks: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage: dict[str, Any] = {}
        model_seen = payload["model"]

        try:
            async with self._client.messages.stream(**payload) as stream_ctx:
                async for event in stream_ctx:
                    etype = getattr(event, "type", None)

                    if etype == "content_block_start":
                        index = getattr(event, "index", 0)
                        block = getattr(event, "content_block", None)
                        if block is not None and getattr(block, "type", "") == "tool_use":
                            tool_blocks[index] = {
                                "id": getattr(block, "id", None),
                                "name": getattr(block, "name", None),
                                "arguments": "",
                            }

                    elif etype == "content_block_delta":
                        index = getattr(event, "index", 0)
                        delta = getattr(event, "delta", None)
                        if delta is None:
                            continue
                        dtype = getattr(delta, "type", None)
                        if dtype == "text_delta":
                            text_delta = getattr(delta, "text", "") or ""
                            if text_delta:
                                yield StreamChunk(text_delta=text_delta, model=model_seen)
                        elif dtype == "input_json_delta":
                            partial = getattr(delta, "partial_json", "") or ""
                            buf = tool_blocks.setdefault(
                                index, {"id": None, "name": None, "arguments": ""}
                            )
                            buf["arguments"] += partial

                    elif etype == "message_delta":
                        delta = getattr(event, "delta", None)
                        if delta is not None:
                            stop = getattr(delta, "stop_reason", None)
                            if stop:
                                finish_reason = stop
                        ev_usage = getattr(event, "usage", None)
                        if ev_usage is not None:
                            usage = {
                                "input_tokens": getattr(ev_usage, "input_tokens", 0),
                                "output_tokens": getattr(ev_usage, "output_tokens", 0),
                            }
        except Exception as exc:
            raise ProviderError(f"Anthropic stream request failed: {exc}") from exc

        # Anthropic's tool_use input arrives as a JSON string already; the OpenAI
        # contract is the same shape, so we keep arguments as a string.
        final_tool_calls = [
            {
                "id": tool_blocks[idx]["id"],
                "name": tool_blocks[idx]["name"],
                "arguments": tool_blocks[idx]["arguments"] or "{}",
            }
            for idx in sorted(tool_blocks)
            if tool_blocks[idx]["id"] is not None
        ]
        yield StreamChunk(
            text_delta="",
            is_final=True,
            finish_reason=finish_reason,
            tool_calls=final_tool_calls,
            usage=usage,
            model=model_seen,
        )


def _to_anthropic_message(message: Message) -> dict[str, Any]:
    """Translate a personakit Message into Anthropic's wire format.

    Three cases:
    - `role="tool"` → user message with a `tool_result` content block
    - `role="assistant"` with tool_calls → assistant message with `tool_use` blocks
    - Everything else → plain `{"role": ..., "content": ...}`
    """
    if message.role == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id or "",
                    "content": message.content,
                }
            ],
        }

    if message.role == "assistant" and message.tool_calls:
        blocks: list[dict[str, Any]] = []
        if message.content:
            blocks.append({"type": "text", "text": message.content})
        for call in message.tool_calls:
            args_raw = call.get("arguments")
            if isinstance(args_raw, str):
                try:
                    args = json.loads(args_raw) if args_raw else {}
                except json.JSONDecodeError:
                    args = {}
            else:
                args = args_raw or {}
            blocks.append(
                {
                    "type": "tool_use",
                    "id": call.get("id"),
                    "name": call.get("name"),
                    "input": args,
                }
            )
        return {"role": "assistant", "content": blocks}

    return {"role": message.role, "content": message.content}


def _to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate OpenAI-style tool schemas into Anthropic's format.

    Input shape (OpenAI / what personakit's @tool emits):
        {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}

    Output shape (Anthropic):
        {"name": ..., "description": ..., "input_schema": {...}}
    """
    out: list[dict[str, Any]] = []
    for t in tools:
        if "function" in t:
            fn = t["function"]
            out.append(
                {
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object"}),
                }
            )
        else:
            out.append(t)
    return out

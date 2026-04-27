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
from typing import Any

from ..errors import MissingDependencyError, ProviderError
from .base import LLMResponse, Message


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

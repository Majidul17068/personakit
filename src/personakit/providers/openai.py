"""OpenAI provider adapter.

Requires `personakit[openai]` extra (installs the official `openai` SDK).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..errors import MissingDependencyError, ProviderError
from .base import LLMResponse, Message, StreamChunk


class OpenAIProvider:
    """Adapter around the official `openai` Python SDK."""

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
        default_model: str = "gpt-4o-mini",
        client: Any | None = None,
    ) -> None:
        self.default_model = default_model
        if client is not None:
            self._client = client
            return
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise MissingDependencyError(
                "OpenAIProvider requires the 'openai' package. "
                "Install with: pip install 'personakit[openai]'"
            ) from exc
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            organization=organization,
        )

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
        model_name = model or self.default_model
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": [self._serialise(m) for m in messages],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "personakit_output",
                    "schema": response_schema,
                    "strict": False,
                },
            }
        if tools:
            payload["tools"] = tools
        payload.update(kwargs)

        try:
            raw = await self._client.chat.completions.create(**payload)
        except Exception as exc:
            raise ProviderError(f"OpenAI request failed: {exc}") from exc

        choice = raw.choices[0]
        content = choice.message.content or ""
        tool_calls = _extract_tool_calls(choice.message)
        return LLMResponse(
            text=content,
            model=raw.model,
            finish_reason=choice.finish_reason,
            usage=raw.usage.model_dump() if getattr(raw, "usage", None) else {},
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
        """Stream the model's response chunk-by-chunk.

        Yields a series of `StreamChunk` events. Most chunks carry only a
        `text_delta`. The terminal chunk has `is_final=True` and includes the
        accumulated `tool_calls`, `finish_reason`, and `usage` fields.
        """
        model_name = model or self.default_model
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": [self._serialise(m) for m in messages],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "personakit_output",
                    "schema": response_schema,
                    "strict": False,
                },
            }
        if tools:
            payload["tools"] = tools
        payload.update(kwargs)

        try:
            stream_iter = await self._client.chat.completions.create(**payload)
        except Exception as exc:
            raise ProviderError(f"OpenAI stream request failed: {exc}") from exc

        # Tool calls in OpenAI streaming are assembled across multiple deltas:
        # each delta carries a partial fragment keyed by call index.
        tool_call_buffers: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage: dict[str, Any] = {}
        model_seen = model_name

        async for raw_chunk in stream_iter:
            model_seen = getattr(raw_chunk, "model", model_seen) or model_seen
            chunk_usage = getattr(raw_chunk, "usage", None)
            if chunk_usage is not None:
                if hasattr(chunk_usage, "model_dump"):
                    usage = chunk_usage.model_dump()
                else:
                    usage = dict(chunk_usage)

            choices = getattr(raw_chunk, "choices", None) or []
            if not choices:
                continue
            choice = choices[0]
            delta = getattr(choice, "delta", None)
            finish_reason = getattr(choice, "finish_reason", None) or finish_reason

            # Emit text deltas as they arrive
            if delta is not None:
                text_delta = getattr(delta, "content", None) or ""
                # Accumulate any tool-call fragments for the final chunk
                delta_tool_calls = getattr(delta, "tool_calls", None) or []
                for tc in delta_tool_calls:
                    idx = getattr(tc, "index", 0)
                    buf = tool_call_buffers.setdefault(
                        idx, {"id": None, "name": None, "arguments": ""}
                    )
                    if getattr(tc, "id", None):
                        buf["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            buf["name"] = fn.name
                        if getattr(fn, "arguments", None):
                            buf["arguments"] += fn.arguments

                if text_delta:
                    yield StreamChunk(text_delta=text_delta, model=model_seen)

        # Final chunk — emit accumulated tool_calls + usage + finish_reason
        final_tool_calls = [
            tool_call_buffers[idx]
            for idx in sorted(tool_call_buffers)
            if tool_call_buffers[idx]["id"] is not None
        ]
        yield StreamChunk(
            text_delta="",
            is_final=True,
            finish_reason=finish_reason,
            tool_calls=final_tool_calls,
            usage=usage,
            model=model_seen,
        )

    @staticmethod
    def _serialise(message: Message) -> dict[str, Any]:
        data: dict[str, Any] = {"role": message.role}
        # Assistant messages with tool_calls may have empty content. OpenAI
        # accepts content=null in that case but pydantic gives us "". Normalise.
        if message.role == "assistant" and message.tool_calls:
            data["content"] = message.content or None
            data["tool_calls"] = [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": call.get("arguments") or "{}",
                    },
                }
                for call in message.tool_calls
            ]
        else:
            data["content"] = message.content
        if message.name:
            data["name"] = message.name
        if message.tool_call_id:
            data["tool_call_id"] = message.tool_call_id
        return data


def _extract_tool_calls(message: Any) -> list[dict[str, Any]]:
    calls = getattr(message, "tool_calls", None)
    if not calls:
        return []
    out: list[dict[str, Any]] = []
    for call in calls:
        out.append(
            {
                "id": getattr(call, "id", None),
                "name": getattr(getattr(call, "function", None), "name", None),
                "arguments": getattr(getattr(call, "function", None), "arguments", None),
            }
        )
    return out

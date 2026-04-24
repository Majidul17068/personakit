"""OpenAI provider adapter.

Requires `personakit[openai]` extra (installs the official `openai` SDK).
"""

from __future__ import annotations

from typing import Any

from ..errors import MissingDependencyError, ProviderError
from .base import LLMResponse, Message


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

    @staticmethod
    def _serialise(message: Message) -> dict[str, Any]:
        data: dict[str, Any] = {"role": message.role, "content": message.content}
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

"""Anthropic provider adapter.

Requires `personakit[anthropic]` extra (installs the official `anthropic` SDK).
"""

from __future__ import annotations

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
            from anthropic import AsyncAnthropic  # type: ignore[import-not-found]
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
                conv.append({"role": m.role, "content": m.content})

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
            payload["tools"] = tools
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
                tool_calls.append(
                    {
                        "id": getattr(block, "id", None),
                        "name": getattr(block, "name", None),
                        "arguments": getattr(block, "input", None),
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

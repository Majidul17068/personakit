"""LiteLLM provider adapter — one interface, 100+ LLM providers.

LiteLLM (https://github.com/BerriAI/litellm) normalises the APIs of OpenAI,
Anthropic, Azure OpenAI, AWS Bedrock, Google Vertex AI, Cohere, Mistral,
Hugging Face, Ollama, DeepSeek, Together AI, Groq, Fireworks, Anyscale, and
any OpenAI-compatible endpoint to a single `completion` / `acompletion`
function.

Wrapping LiteLLM gives personakit access to every provider LiteLLM supports
without shipping provider-specific code in personakit itself. The model string
is the routing key:

    LiteLLMProvider(default_model="bedrock/anthropic.claude-v2")
    LiteLLMProvider(default_model="azure/gpt-4-deployment")
    LiteLLMProvider(default_model="vertex_ai/gemini-pro")
    LiteLLMProvider(default_model="ollama/llama3")
    LiteLLMProvider(default_model="groq/mixtral-8x7b-32768")

Requires the `personakit[litellm]` extra.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..errors import MissingDependencyError, ProviderError
from .base import LLMResponse, Message, StreamChunk


class LiteLLMProvider:
    """Adapter around `litellm.acompletion`.

    Parameters
    ----------
    default_model:
        LiteLLM-style model string used when the caller doesn't pass one.
        Examples: `"gpt-4o-mini"`, `"claude-sonnet-4-6"`,
        `"bedrock/anthropic.claude-v2"`, `"azure/my-deployment"`.
    api_key:
        Optional. Most providers read from environment variables; pass here to
        override at the call level.
    api_base:
        Optional. Base URL for self-hosted / OpenAI-compatible endpoints
        (vLLM, LM Studio, Ollama, LiteLLM proxy, etc.).
    client:
        Optional injected client (any object exposing `acompletion(**kwargs)`
        as an awaitable). Primarily for testing; leave `None` in production.
    **defaults:
        Extra keyword arguments forwarded to every `acompletion` call — e.g.
        `api_version`, `azure_deployment`, `aws_region_name`,
        `vertex_project`, `vertex_location`, custom headers.
    """

    name = "litellm"

    def __init__(
        self,
        *,
        default_model: str = "gpt-4o-mini",
        api_key: str | None = None,
        api_base: str | None = None,
        client: Any | None = None,
        **defaults: Any,
    ) -> None:
        self.default_model = default_model
        self.api_key = api_key
        self.api_base = api_base
        self.defaults = defaults
        if client is not None:
            self._client = client
            return
        try:
            import litellm
        except ImportError as exc:
            raise MissingDependencyError(
                "LiteLLMProvider requires the 'litellm' package. "
                "Install with: pip install 'personakit[litellm]'"
            ) from exc
        self._client = litellm

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
            **self.defaults,
        }
        if self.api_key is not None:
            payload["api_key"] = self.api_key
        if self.api_base is not None:
            payload["api_base"] = self.api_base
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
            raw = await self._client.acompletion(**payload)
        except Exception as exc:
            raise ProviderError(f"LiteLLM request failed: {exc}") from exc

        # LiteLLM returns OpenAI-shaped objects regardless of the underlying
        # provider, so the same extraction code works for every backend.
        choice = raw.choices[0]
        content = choice.message.content or ""
        tool_calls = _extract_tool_calls(choice.message)

        usage: dict[str, Any] = {}
        raw_usage = getattr(raw, "usage", None)
        if raw_usage is not None:
            if hasattr(raw_usage, "model_dump"):
                usage = raw_usage.model_dump()
            elif hasattr(raw_usage, "__dict__"):
                usage = dict(raw_usage.__dict__)
            elif isinstance(raw_usage, dict):
                usage = dict(raw_usage)

        return LLMResponse(
            text=content,
            model=getattr(raw, "model", model_name),
            finish_reason=getattr(choice, "finish_reason", None),
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
        """Stream the model's response chunk-by-chunk via litellm.acompletion.

        LiteLLM normalises chunks to OpenAI shape regardless of the underlying
        provider, so the same delta-handling logic as OpenAIProvider works for
        every supported model.
        """
        model_name = model or self.default_model
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": [self._serialise(m) for m in messages],
            "stream": True,
            **self.defaults,
        }
        if self.api_key is not None:
            payload["api_key"] = self.api_key
        if self.api_base is not None:
            payload["api_base"] = self.api_base
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
            stream_iter = await self._client.acompletion(**payload)
        except Exception as exc:
            raise ProviderError(f"LiteLLM stream request failed: {exc}") from exc

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
                elif hasattr(chunk_usage, "__dict__"):
                    usage = dict(chunk_usage.__dict__)

            choices = getattr(raw_chunk, "choices", None) or []
            if not choices:
                continue
            choice = choices[0]
            delta = getattr(choice, "delta", None)
            finish_reason = getattr(choice, "finish_reason", None) or finish_reason

            if delta is not None:
                text_delta = getattr(delta, "content", None) or ""
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
        # LiteLLM normalises to OpenAI shape, so we use the same tool-call
        # serialisation as OpenAIProvider.
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
        fn = getattr(call, "function", None)
        out.append(
            {
                "id": getattr(call, "id", None),
                "name": getattr(fn, "name", None),
                "arguments": getattr(fn, "arguments", None),
            }
        )
    return out

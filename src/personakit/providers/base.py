"""Provider protocol and shared message/response types.

Every provider adapter implements the `LLMProvider` protocol — a single async
`complete()` method that takes a list of messages plus optional JSON schema for
structured output. Streaming is exposed via the optional `stream()` method;
providers that don't override it inherit a default that calls `complete()` and
emits the entire response as one chunk.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


class Message(BaseModel):
    """A single chat message in the provider-agnostic format.

    Most messages have just `role` + `content`. Two extras support the
    tool-calling loop:

    - `tool_calls` — set on `role="assistant"` messages when the model has
      requested one or more tool invocations. Each entry is an OpenAI-shaped
      dict with `id`, `name`, `arguments` (str). Providers translate to their
      native format on the wire.
    - `tool_call_id` — set on `role="tool"` messages to associate a tool's
      execution result with the originating call.
    """

    role: Role
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class LLMResponse(BaseModel):
    """Provider-agnostic LLM response."""

    text: str
    model: str
    finish_reason: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class StreamChunk(BaseModel):
    """A single chunk emitted by `LLMProvider.stream()`.

    The first chunks may carry only text deltas. The final chunk includes the
    complete response (text, tool_calls, usage). Consumers should accumulate
    `text_delta` until they see `is_final=True` and then read the assembled
    fields. See `Agent.analyze_stream` for typical usage.
    """

    text_delta: str = ""
    is_final: bool = False
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
    model: str = ""


@runtime_checkable
class LLMProvider(Protocol):
    """Uniform interface every provider implements."""

    name: str

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
    ) -> LLMResponse: ...

    def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        response_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]: ...

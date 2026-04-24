"""Provider protocol and shared message/response types.

Every provider adapter implements the `LLMProvider` protocol — a single async
`complete()` method that takes a list of messages plus optional JSON schema for
structured output. Authors never touch providers directly; the Agent selects
the right one via `Agent(specialist=..., model=...)` and falls back to the
explicitly supplied provider if given.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


class Message(BaseModel):
    """A single chat message in the provider-agnostic format."""

    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class LLMResponse(BaseModel):
    """Provider-agnostic LLM response."""

    text: str
    model: str
    finish_reason: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Uniform interface every provider implements."""

    name: str

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        response_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse: ...

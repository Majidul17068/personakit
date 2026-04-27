"""In-memory mock provider — for tests, demos, and offline development."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

from .base import LLMResponse, Message

# A canned response can be:
# - str:                     plain text content
# - dict (no "tool_calls"):  treated as JSON content (serialised on the wire)
# - dict with "tool_calls":  an LLMResponse-shaped dict — produces a tool-call turn
# - LLMResponse:             used as-is (most flexible)
CannedResponse = str | dict[str, Any] | LLMResponse


class MockProvider:
    """Returns canned responses without calling any external API.

    Modes:

    - `responses=str`             — single text response
    - `responses=dict`            — single JSON response (or LLMResponse-shaped
      dict if it includes a `tool_calls` key)
    - `responses=LLMResponse`     — a pre-built response, used as-is
    - `responses=[...]`           — cycles through the list, one per call.
      Last entry repeats once exhausted (useful for tool-call loops).
    - `handler=callable`          — called with (messages, kwargs) and returns
      a CannedResponse. Use this for stateful test scenarios.

    For multi-turn tool-call tests, queue an LLMResponse with `tool_calls`
    first, then a final text/dict response. The Agent's tool loop will run
    the tool, feed the result back, then receive your final response.
    """

    name = "mock"

    def __init__(
        self,
        responses: Iterable[CannedResponse] | CannedResponse | None = None,
        *,
        handler: Callable[[list[Message], dict[str, Any]], CannedResponse] | None = None,
        model: str = "mock-1",
    ) -> None:
        self.model = model
        self.calls: list[list[Message]] = []
        self._handler = handler
        if responses is None:
            self._queue: list[CannedResponse] = []
        elif isinstance(responses, (str, dict, LLMResponse)):
            self._queue = [responses]
        else:
            self._queue = list(responses)

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
        self.calls.append(list(messages))
        if self._handler is not None:
            result: CannedResponse = self._handler(messages, kwargs)
        elif self._queue:
            result = self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]
        else:
            result = ""
        return self._to_response(result, model=model)

    def _to_response(self, result: CannedResponse, *, model: str | None) -> LLMResponse:
        if isinstance(result, LLMResponse):
            return result
        if isinstance(result, str):
            return LLMResponse(
                text=result,
                model=model or self.model,
                finish_reason="stop",
                usage={"input_tokens": 0, "output_tokens": 0},
            )
        # dict: either an LLMResponse-shaped dict (with tool_calls) or a JSON content body
        if "tool_calls" in result:
            return LLMResponse(
                text=result.get("text", "") or "",
                model=result.get("model", model or self.model),
                finish_reason=result.get("finish_reason", "tool_calls"),
                usage=result.get("usage", {"input_tokens": 0, "output_tokens": 0}),
                tool_calls=result.get("tool_calls", []),
                raw=result.get("raw", {}),
            )
        return LLMResponse(
            text=json.dumps(result),
            model=model or self.model,
            finish_reason="stop",
            usage={"input_tokens": 0, "output_tokens": 0},
        )

"""In-memory mock provider — for tests, demos, and offline development."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

from .base import LLMResponse, Message


class MockProvider:
    """Returns canned responses without calling any external API.

    Three modes:

    - `responses=[...]` — cycles through the list, one per `complete()` call.
    - `responses=dict` — treated as a JSON response. Serialised and returned.
    - `handler=callable` — called with (messages, kwargs) and returns either a
      string or a dict; dicts are JSON-serialised.
    """

    name = "mock"

    def __init__(
        self,
        responses: Iterable[str | dict[str, Any]] | str | dict[str, Any] | None = None,
        *,
        handler: Callable[[list[Message], dict[str, Any]], str | dict[str, Any]] | None = None,
        model: str = "mock-1",
    ) -> None:
        self.model = model
        self.calls: list[list[Message]] = []
        self._handler = handler
        if responses is None:
            self._queue: list[str | dict[str, Any]] = []
        elif isinstance(responses, (str, dict)):
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
            result = self._handler(messages, kwargs)
        elif self._queue:
            result = self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]
        else:
            result = ""
        text = result if isinstance(result, str) else json.dumps(result)
        return LLMResponse(
            text=text,
            model=model or self.model,
            finish_reason="stop",
            usage={"input_tokens": 0, "output_tokens": 0},
        )

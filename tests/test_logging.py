"""Tests for the v0.3 built-in logging.

The contract:
- ``logging.getLogger("personakit")`` always exists and is silent by default
  (only a NullHandler attached).
- ``enable_verbose_logging()`` attaches a StreamHandler exactly once, idempotent
  on repeat calls.
- ``Agent(..., verbose=True)`` configures the same logger.
- Submodule loggers (``personakit.agent`` etc.) inherit propagation through
  the ``personakit`` parent.
- An ``Agent`` construction emits one INFO log line via ``personakit.agent``.
"""

from __future__ import annotations

import io
import logging
from typing import Any

import pytest

from personakit import (
    Agent,
    Specialist,
    enable_verbose_logging,
    get_logger,
)
from personakit._logging import _ROOT_NAME
from personakit.providers.base import LLMResponse, Message


class _DummyProvider:
    """Minimal LLMProvider implementation for tests that never calls a real LLM."""

    name = "dummy"

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        response_schema: Any = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        return LLMResponse(text="", model=model or "dummy/none", usage={}, tool_calls=[])

    def stream(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - unused in tests
        raise NotImplementedError


def _make_specialist() -> Specialist:
    return Specialist(
        name="test-specialist",
        persona="A test specialist used for verifying logging behavior.",
        frameworks=[],
        probes=[],
        red_flags=[],
        themes=[],
    )


def _reset_logger() -> None:
    """Strip everything except a NullHandler so tests don't bleed into each other."""
    logger = logging.getLogger(_ROOT_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.NOTSET)
    logger.propagate = True


@pytest.fixture(autouse=True)
def _isolate_logger() -> Any:
    _reset_logger()
    yield
    _reset_logger()


def test_root_logger_has_null_handler_by_default() -> None:
    logger = logging.getLogger(_ROOT_NAME)
    assert any(isinstance(h, logging.NullHandler) for h in logger.handlers), (
        "personakit root logger must have a NullHandler attached so library "
        "users never see 'no handler' warnings."
    )


def test_get_logger_returns_root_when_no_name() -> None:
    assert get_logger().name == _ROOT_NAME
    assert get_logger("agent").name == f"{_ROOT_NAME}.agent"


def test_enable_verbose_logging_attaches_stream_handler() -> None:
    buf = io.StringIO()
    logger = enable_verbose_logging("INFO", stream=buf)
    logger.info("hello world")

    output = buf.getvalue()
    assert "[personakit]" in output
    assert "INFO" in output
    assert "hello world" in output


def test_enable_verbose_logging_is_idempotent() -> None:
    buf1 = io.StringIO()
    enable_verbose_logging("INFO", stream=buf1)
    enable_verbose_logging("INFO", stream=buf1)  # second call should not duplicate

    logger = logging.getLogger(_ROOT_NAME)
    stream_handlers = [
        h
        for h in logger.handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.NullHandler)
    ]
    assert len(stream_handlers) == 1, (
        f"Expected exactly one StreamHandler after two enable calls, got {len(stream_handlers)}."
    )

    logger.info("after second enable")
    assert buf1.getvalue().count("after second enable") == 1


def test_enable_verbose_logging_accepts_int_level() -> None:
    buf = io.StringIO()
    enable_verbose_logging(logging.DEBUG, stream=buf)
    logger = logging.getLogger(_ROOT_NAME)
    logger.debug("debug visible")
    assert "debug visible" in buf.getvalue()


def test_enable_verbose_logging_rejects_invalid_level() -> None:
    with pytest.raises(ValueError, match="Unknown logging level"):
        enable_verbose_logging("NOPE")


def test_agent_construction_emits_info_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=f"{_ROOT_NAME}.agent"):
        Agent(
            specialist=_make_specialist(),
            provider=_DummyProvider(),  # type: ignore[arg-type]
            model="dummy/none",
        )

    info_records = [r for r in caplog.records if r.levelno >= logging.INFO]
    assert any("Agent ready" in r.getMessage() for r in info_records), (
        "Expected Agent.__init__ to emit an INFO log with 'Agent ready'."
    )


def test_agent_verbose_flag_attaches_handler() -> None:
    Agent(
        specialist=_make_specialist(),
        provider=_DummyProvider(),  # type: ignore[arg-type]
        model="dummy/none",
        verbose=True,
    )
    logger = logging.getLogger(_ROOT_NAME)
    stream_handlers = [
        h
        for h in logger.handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.NullHandler)
    ]
    assert len(stream_handlers) == 1, (
        "Agent(verbose=True) must attach a StreamHandler to the personakit logger."
    )


@pytest.mark.asyncio
async def test_analyze_emits_lifecycle_logs(caplog: pytest.LogCaptureFixture) -> None:
    """analyze() should emit at least: started, provider call, done."""

    class _NoOpProvider(_DummyProvider):
        async def complete(  # type: ignore[override]
            self,
            messages: list[Message],
            **kwargs: Any,
        ) -> LLMResponse:
            return LLMResponse(
                text='{"summary":"ok","red_flags_detected":[],"probes_answered":{},'
                '"recommendations":[],"priorities_status":[],"citations_used":[]}',
                model="dummy/none",
                usage={"total_tokens": 10},
                tool_calls=[],
            )

    agent = Agent(
        specialist=_make_specialist(),
        provider=_NoOpProvider(),  # type: ignore[arg-type]
        model="dummy/none",
    )

    with caplog.at_level(logging.DEBUG, logger=_ROOT_NAME):
        await agent.analyze("Test input")

    messages = [r.getMessage() for r in caplog.records]
    assert any("analyze started" in m for m in messages), "missing 'analyze started' log"
    assert any("analyze done" in m for m in messages), "missing 'analyze done' log"
    assert any("provider call" in m for m in messages), "missing 'provider call' log"

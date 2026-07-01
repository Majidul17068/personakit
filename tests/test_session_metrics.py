"""Tests for ``personakit.metrics.SessionMetrics``.

The ledger is a plain in-memory dataclass. These tests exercise the aggregate
properties, the specialist/model grouping, and the ``summary()`` renderer.
"""

from __future__ import annotations

from personakit.metrics import CallRecord, SessionMetrics


def test_session_metrics_records_calls_and_aggregates():
    m = SessionMetrics()
    m.record(
        specialist="router",
        model="gpt-4o-mini",
        duration_ms=340,
        usage={"prompt_tokens": 128, "completion_tokens": 12},
    )
    m.record(
        specialist="code_reviewer",
        model="gpt-4o",
        duration_ms=1420,
        usage={"prompt_tokens": 542, "completion_tokens": 318},
        tool_calls=1,
    )

    assert m.total_calls == 2
    assert m.total_input_tokens == 128 + 542
    assert m.total_output_tokens == 12 + 318
    assert m.total_tokens == 128 + 12 + 542 + 318
    assert m.total_duration_ms == 340 + 1420
    assert m.total_tool_calls == 1
    assert m.total_cost_usd > 0


def test_session_metrics_handles_missing_usage_gracefully():
    m = SessionMetrics()
    record = m.record(
        specialist="s",
        model="unknown-model",
        duration_ms=10,
        usage=None,
    )
    assert isinstance(record, CallRecord)
    assert record.input_tokens == 0
    assert record.output_tokens == 0
    assert record.cost_usd is None
    assert m.total_cost_usd == 0.0


def test_session_metrics_accepts_anthropic_shaped_usage():
    m = SessionMetrics()
    m.record(
        specialist="s",
        model="claude-3-5-sonnet",
        duration_ms=200,
        usage={"input_tokens": 200, "output_tokens": 50},
    )
    assert m.total_input_tokens == 200
    assert m.total_output_tokens == 50


def test_session_metrics_by_specialist_grouping():
    m = SessionMetrics()
    m.record(specialist="a", model="gpt-4o", duration_ms=100, usage={"prompt_tokens": 10, "completion_tokens": 5})
    m.record(specialist="a", model="gpt-4o", duration_ms=200, usage={"prompt_tokens": 20, "completion_tokens": 5})
    m.record(specialist="b", model="gpt-4o", duration_ms=50, usage={"prompt_tokens": 5, "completion_tokens": 5})
    grouped = m.by_specialist()
    assert grouped["a"]["calls"] == 2
    assert grouped["a"]["tokens"] == 40
    assert grouped["b"]["calls"] == 1


def test_session_metrics_by_model_grouping():
    m = SessionMetrics()
    m.record(specialist="s", model="gpt-4o", duration_ms=100, usage={"prompt_tokens": 10, "completion_tokens": 5})
    m.record(specialist="s", model="gpt-4o-mini", duration_ms=50, usage={"prompt_tokens": 5, "completion_tokens": 5})
    grouped = m.by_model()
    assert set(grouped.keys()) == {"gpt-4o", "gpt-4o-mini"}


def test_session_metrics_reset_clears_all():
    m = SessionMetrics()
    m.record(specialist="s", model="gpt-4o", duration_ms=100, usage={"prompt_tokens": 10, "completion_tokens": 5})
    assert m.total_calls == 1
    m.reset()
    assert m.total_calls == 0
    assert m.calls == []


def test_session_metrics_summary_reports_empty_state():
    assert "no calls" in SessionMetrics().summary().lower()


def test_session_metrics_summary_includes_totals_and_breakdowns():
    m = SessionMetrics()
    m.record(specialist="router", model="gpt-4o-mini", duration_ms=340, usage={"prompt_tokens": 128, "completion_tokens": 12})
    m.record(specialist="reviewer", model="gpt-4o", duration_ms=1420, usage={"prompt_tokens": 542, "completion_tokens": 318})
    summary = m.summary()
    assert "SessionMetrics" in summary
    assert "calls" in summary
    assert "tokens" in summary
    assert "cost" in summary.lower()
    assert "router" in summary
    assert "reviewer" in summary
    assert "gpt-4o" in summary


def test_agent_metrics_are_initialised_and_empty():
    from personakit import Specialist
    from personakit.agent import Agent
    from personakit.providers.base import LLMProvider, LLMResponse

    class _StubProvider:
        name = "stub"
        default_model = "stub-1"

        async def complete(self, *a, **kw):
            return LLMResponse(text="{}", usage={}, tool_calls=[])

    spec = Specialist(name="s", persona="Test persona")
    agent = Agent(specialist=spec, provider=_StubProvider(), model="stub-1")
    assert agent.metrics.total_calls == 0
    assert isinstance(agent.metrics, SessionMetrics)

"""Session-level metrics — cumulative ledger for personakit ``Agent`` runs.

``SessionMetrics`` accumulates per-call statistics (calls, tokens, cost,
duration) across every ``Agent.analyze`` invocation. It is a plain in-memory
object; no threads, no I/O, no external dependencies. Read the aggregates via
``.total_calls``, ``.total_tokens``, ``.total_cost_usd``, or call
``.summary()`` for a printable table.

The metrics fold in cost estimates from :mod:`personakit.cost`, so if the
model has known pricing you get a per-model USD figure; otherwise the cost
field is ``None`` and the aggregate still reports what it can.

Usage — the ``Agent`` wires this up automatically; you just read from it::

    from personakit import Agent
    agent = Agent(specialist=spec, model="gpt-4o")
    await agent.analyze("...")
    print(agent.metrics.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .cost import estimate_cost_from_usage


@dataclass
class CallRecord:
    """One recorded ``Agent.analyze`` invocation."""

    specialist: str
    model: str
    duration_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    tool_calls: int
    error: str | None = None


@dataclass
class SessionMetrics:
    """Cumulative ledger across one or more ``Agent.analyze`` calls."""

    calls: list[CallRecord] = field(default_factory=list)

    def record(
        self,
        *,
        specialist: str,
        model: str,
        duration_ms: float,
        usage: dict[str, Any] | None,
        tool_calls: int = 0,
        error: str | None = None,
    ) -> CallRecord:
        """Record one call and return the appended ``CallRecord``.

        ``usage`` accepts either OpenAI-shape (``prompt_tokens`` /
        ``completion_tokens``) or Anthropic-shape (``input_tokens`` /
        ``output_tokens``) dicts. Missing / unknown → 0.
        """
        usage = usage or {}
        input_tokens = int(
            usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or 0
        )
        output_tokens = int(
            usage.get("output_tokens")
            or usage.get("completion_tokens")
            or 0
        )
        cost = estimate_cost_from_usage(model, usage) if model else None
        record = CallRecord(
            specialist=specialist,
            model=model,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            tool_calls=tool_calls,
            error=error,
        )
        self.calls.append(record)
        return record

    @property
    def total_calls(self) -> int:
        return len(self.calls)

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost_usd(self) -> float:
        return sum((c.cost_usd or 0.0) for c in self.calls)

    @property
    def total_duration_ms(self) -> float:
        return sum(c.duration_ms for c in self.calls)

    @property
    def total_tool_calls(self) -> int:
        return sum(c.tool_calls for c in self.calls)

    def by_specialist(self) -> dict[str, dict[str, Any]]:
        """Aggregate ``calls / tokens / cost`` grouped by specialist name."""
        buckets: dict[str, dict[str, Any]] = {}
        for c in self.calls:
            b = buckets.setdefault(
                c.specialist,
                {"calls": 0, "tokens": 0, "cost_usd": 0.0, "duration_ms": 0.0},
            )
            b["calls"] += 1
            b["tokens"] += c.input_tokens + c.output_tokens
            b["cost_usd"] += c.cost_usd or 0.0
            b["duration_ms"] += c.duration_ms
        return buckets

    def by_model(self) -> dict[str, dict[str, Any]]:
        """Aggregate ``calls / tokens / cost`` grouped by model id."""
        buckets: dict[str, dict[str, Any]] = {}
        for c in self.calls:
            b = buckets.setdefault(
                c.model or "(unknown)",
                {"calls": 0, "tokens": 0, "cost_usd": 0.0, "duration_ms": 0.0},
            )
            b["calls"] += 1
            b["tokens"] += c.input_tokens + c.output_tokens
            b["cost_usd"] += c.cost_usd or 0.0
            b["duration_ms"] += c.duration_ms
        return buckets

    def reset(self) -> None:
        """Drop every recorded call. Aggregates go back to zero."""
        self.calls.clear()

    def summary(self) -> str:
        """Return a human-readable multi-line summary of the session."""
        if not self.calls:
            return "SessionMetrics: no calls recorded yet."
        lines = [
            "SessionMetrics",
            f"  calls        {self.total_calls}",
            f"  tokens       {self.total_input_tokens:,} in / {self.total_output_tokens:,} out"
            f" ({self.total_tokens:,} total)",
            f"  cost (USD)   ${self.total_cost_usd:.5f}",
            f"  duration     {self.total_duration_ms:.0f}ms",
            f"  tool calls   {self.total_tool_calls}",
        ]
        by_spec = self.by_specialist()
        if len(by_spec) > 1:
            lines.append("  by specialist:")
            for name, agg in sorted(by_spec.items()):
                lines.append(
                    f"    {name:<20} {agg['calls']:>3}x  "
                    f"{agg['tokens']:>7,} tok  ${agg['cost_usd']:.5f}"
                )
        by_mod = self.by_model()
        if len(by_mod) > 1:
            lines.append("  by model:")
            for name, agg in sorted(by_mod.items()):
                lines.append(
                    f"    {name:<20} {agg['calls']:>3}x  "
                    f"{agg['tokens']:>7,} tok  ${agg['cost_usd']:.5f}"
                )
        return "\n".join(lines)


__all__ = ["CallRecord", "SessionMetrics"]

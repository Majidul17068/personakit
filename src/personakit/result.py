"""Structured result objects returned by `Agent.analyze()` and
`Agent.analyze_stream()`."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .specialist import Probe, RedFlag, Severity

StreamEventType = Literal[
    "text_delta",
    "red_flag_pre_match",
    "tool_call",
    "tool_result",
    "iteration_complete",
    "complete",
    "error",
]


class TriggeredRedFlag(BaseModel):
    """A red flag that fired, with evidence and the detection source."""

    model_config = ConfigDict(frozen=True)

    red_flag: RedFlag
    evidence: str = Field(description="Quote or reasoning that triggered the flag.")
    source: str = Field(description="'regex', 'keyword', or 'semantic'.")

    @property
    def severity(self) -> Severity:
        return self.red_flag.severity

    @property
    def trigger(self) -> str:
        return self.red_flag.trigger

    @property
    def action(self) -> str:
        return self.red_flag.action

    @property
    def citation(self) -> str | None:
        return self.red_flag.citation


class Recommendation(BaseModel):
    """A single recommendation produced by the specialist."""

    model_config = ConfigDict(frozen=True)

    theme: str
    text: str
    citations: list[str] = Field(default_factory=list)
    priority: str | None = None


class AnalyzeResult(BaseModel):
    """Structured output of a Specialist analysis.

    Attributes:
        specialist_name: The Specialist that produced the result.
        summary: Narrative summary aligned to the specialist's summary focus.
        probes_answered: Map of probe key → answered value.
        probes_unanswered: Probes the LLM could not answer from the input.
        red_flags_triggered: Red flags that fired (regex + keyword + semantic).
        recommendations: Theme-organised recommendations.
        priorities_status: Status of each declared immediate priority.
        citations_used: Framework citation keys referenced in the output.
        raw_output: The raw string returned by the LLM (for debugging).
        usage: Token usage metadata from the provider, if available.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    specialist_name: str
    summary: str = ""
    probes_answered: dict[str, Any] = Field(default_factory=dict)
    probes_unanswered: list[Probe] = Field(default_factory=list)
    red_flags_triggered: list[TriggeredRedFlag] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    priorities_status: list[dict[str, Any]] = Field(default_factory=list)
    citations_used: list[str] = Field(default_factory=list)
    raw_output: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)
    model: str = Field(
        default="",
        description="The model identifier reported by the provider — used for cost estimation.",
    )

    @property
    def estimated_cost_usd(self) -> float | None:
        """Estimated USD cost based on `usage` + `model`.

        Returns `None` when the model isn't in the pricing table (so callers
        can distinguish "unknown" from "zero"). For local models (Ollama,
        vLLM, etc.) the table returns `0.0`.
        """
        from .cost import estimate_cost_from_usage

        if not self.model or not self.usage:
            return None
        return estimate_cost_from_usage(self.model, self.usage)

    @property
    def has_urgent(self) -> bool:
        return any(
            rf.severity in {Severity.URGENT, Severity.CRITICAL}
            for rf in self.red_flags_triggered
        )

    @property
    def by_severity(self) -> dict[Severity, list[TriggeredRedFlag]]:
        buckets: dict[Severity, list[TriggeredRedFlag]] = {s: [] for s in Severity}
        for rf in self.red_flags_triggered:
            buckets[rf.severity].append(rf)
        return buckets

    def pretty(self) -> str:
        """Human-friendly textual summary — handy for CLIs and demos."""
        lines: list[str] = []
        lines.append(f"=== {self.specialist_name} ===")
        if self.summary:
            lines.append(self.summary)
            lines.append("")
        if self.red_flags_triggered:
            lines.append("RED FLAGS")
            for rf in self.red_flags_triggered:
                cite = f" [{rf.citation}]" if rf.citation else ""
                lines.append(f"  [{rf.severity.value.upper()}] {rf.trigger}{cite}")
                lines.append(f"    → {rf.action}")
            lines.append("")
        if self.probes_unanswered:
            lines.append("UNANSWERED PROBES")
            for p in self.probes_unanswered:
                lines.append(f"  - {p.question}")
            lines.append("")
        if self.recommendations:
            lines.append("RECOMMENDATIONS")
            for r in self.recommendations:
                cite = f" [{', '.join(r.citations)}]" if r.citations else ""
                lines.append(f"  - ({r.theme}) {r.text}{cite}")
        return "\n".join(lines).strip()


class StreamEvent(BaseModel):
    """A discrete event emitted by `Agent.analyze_stream()`.

    Event types:

    - `text_delta` — a fragment of the LLM's response text. Concatenate these
      to display progressive output in a UI.
    - `red_flag_pre_match` — the deterministic regex/keyword matcher fired on
      the input. Available before the LLM has even started.
    - `tool_call` — the LLM has requested a tool invocation (about to run).
    - `tool_result` — a tool finished. Carries the duration and result.
    - `iteration_complete` — one tool-loop iteration finished. Useful for
      progress UIs that want a "step counter".
    - `complete` — the analysis finished. Carries the full `AnalyzeResult`.
    - `error` — something failed during streaming.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    type: StreamEventType
    text: str = ""
    red_flag: TriggeredRedFlag | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    tool_result: Any = None
    duration_ms: float | None = None
    iteration: int | None = None
    result: AnalyzeResult | None = None
    error: str | None = None

"""Tests for v0.3.0a2 — versioned specialists (core).

The contract:
* ``Specialist.checksum()`` is stable: identical declarative content → same hash.
* Any meaningful change to declarative fields → different checksum.
* ``Specialist.diff(other)`` returns a structured ``SpecialistDiff`` that
  identifies added / removed / changed items in every collection and every
  scalar field.
* ``AnalyzeResult.specialist_checksum`` is populated by ``Agent.analyze()``
  with the source Specialist's checksum.

CLI tests live in ``tests/test_cli.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from personakit import (
    Agent,
    CollectionItemChange,
    Probe,
    RedFlag,
    Severity,
    Specialist,
    SpecialistDiff,
    Theme,
    diff_specialists,
)
from personakit.providers.base import LLMResponse, Message

# -- helpers ----------------------------------------------------------------


def _spec(**overrides: Any) -> Specialist:
    """Build a baseline Specialist for tests — caller overrides fields as needed."""
    defaults: dict[str, Any] = {
        "name": "test-spec",
        "persona": "A baseline specialist used in versioning tests.",
        "probes": [Probe(question="Is the patient stable?", key="stable")],
        "red_flags": [
            RedFlag(
                trigger="chest pain",
                severity=Severity.HIGH,
                action="escalate",
                id="rf_chest_pain",
            )
        ],
        "themes": [Theme(name="triage", description="Initial assessment")],
    }
    defaults.update(overrides)
    return Specialist(**defaults)


class _NoOpProvider:
    name = "noop"

    async def complete(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> LLMResponse:
        del messages, kwargs
        return LLMResponse(
            text='{"summary":"ok","red_flags_detected":[],"probes_answered":{},'
            '"recommendations":[],"priorities_status":[],"citations_used":[]}',
            model="noop/none",
            usage={"total_tokens": 0},
            tool_calls=[],
        )

    def stream(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - unused
        raise NotImplementedError


# -- checksum stability -----------------------------------------------------


def test_checksum_is_a_sha256_hex() -> None:
    cs = _spec().checksum()
    assert isinstance(cs, str)
    assert len(cs) == 64  # SHA-256 hex digest length
    int(cs, 16)  # raises ValueError if not hex


def test_identical_specs_have_identical_checksum() -> None:
    a = _spec()
    b = _spec()
    assert a.checksum() == b.checksum()


def test_changing_persona_changes_checksum() -> None:
    a = _spec()
    b = _spec(persona="Different persona text entirely.")
    assert a.checksum() != b.checksum()


def test_adding_a_red_flag_changes_checksum() -> None:
    a = _spec()
    b = _spec(
        red_flags=[
            RedFlag(
                trigger="chest pain",
                severity=Severity.HIGH,
                action="escalate",
                id="rf_chest_pain",
            ),
            RedFlag(
                trigger="stroke symptoms",
                severity=Severity.CRITICAL,
                action="call EMS",
                id="rf_stroke",
            ),
        ]
    )
    assert a.checksum() != b.checksum()


def test_reordering_lists_does_not_change_checksum() -> None:
    """Pydantic preserves list order, so reordering DOES change the dump.
    This test documents the current behaviour — if we want order-insensitive
    checksums later, this test is the canary."""
    a = _spec(
        probes=[
            Probe(question="A?", key="a"),
            Probe(question="B?", key="b"),
        ]
    )
    b = _spec(
        probes=[
            Probe(question="B?", key="b"),
            Probe(question="A?", key="a"),
        ]
    )
    # Different order → different checksum. Document the choice.
    assert a.checksum() != b.checksum()


# -- diff structure ---------------------------------------------------------


def test_diff_identical_specs_returns_same_true() -> None:
    diff = diff_specialists(_spec(), _spec())
    assert diff.same is True
    assert diff.field_changes == []
    assert diff.added == {}
    assert diff.removed == {}
    assert diff.changed == {}


def test_diff_detects_persona_change() -> None:
    a = _spec()
    b = _spec(persona="changed persona")
    diff = a.diff(b)
    assert diff.same is False
    assert any(fc.field == "persona" for fc in diff.field_changes)


def test_diff_detects_added_probe() -> None:
    a = _spec()
    b = _spec(
        probes=[
            Probe(question="Is the patient stable?", key="stable"),
            Probe(question="Any allergies?", key="allergies"),
        ]
    )
    diff = a.diff(b)
    assert diff.same is False
    assert "probes" in diff.added
    assert len(diff.added["probes"]) == 1
    assert diff.added["probes"][0]["key"] == "allergies"


def test_diff_detects_removed_red_flag() -> None:
    a = _spec()
    b = _spec(red_flags=[])
    diff = a.diff(b)
    assert diff.same is False
    assert "red_flags" in diff.removed
    assert len(diff.removed["red_flags"]) == 1


def test_diff_detects_changed_red_flag_severity() -> None:
    a = _spec()
    b = _spec(
        red_flags=[
            RedFlag(
                trigger="chest pain",
                severity=Severity.CRITICAL,
                action="escalate",
                id="rf_chest_pain",
            )
        ]
    )
    diff = a.diff(b)
    assert diff.same is False
    assert "red_flags" in diff.changed
    change = diff.changed["red_flags"][0]
    assert isinstance(change, CollectionItemChange)
    assert change.before["severity"] == "high"
    assert change.after["severity"] == "critical"


def test_diff_to_markdown_renders_changes() -> None:
    a = _spec()
    b = _spec(persona="changed", red_flags=[])
    md = a.diff(b).to_markdown()
    assert "# Specialist diff" in md
    assert "persona" in md
    assert "red_flags" in md.lower() or "Red Flags" in md


def test_diff_to_markdown_no_changes_message() -> None:
    md = _spec().diff(_spec()).to_markdown()
    assert "No changes" in md


# -- AnalyzeResult.specialist_checksum --------------------------------------


@pytest.mark.asyncio
async def test_analyze_populates_specialist_checksum() -> None:
    spec = _spec()
    agent = Agent(specialist=spec, provider=_NoOpProvider(), model="noop/none")  # type: ignore[arg-type]
    result = await agent.analyze("Test input")
    assert result.specialist_checksum == spec.checksum()
    assert len(result.specialist_checksum) == 64


def test_analyze_result_checksum_defaults_to_empty_string_when_unset() -> None:
    """Backward-compat: results constructed manually default to empty checksum."""
    from personakit import AnalyzeResult

    result = AnalyzeResult(specialist_name="manual")
    assert result.specialist_checksum == ""


def test_spec_diff_type_is_specialist_diff() -> None:
    """diff_specialists and Specialist.diff both return SpecialistDiff."""
    result = diff_specialists(_spec(), _spec(persona="x"))
    assert isinstance(result, SpecialistDiff)
    assert isinstance(_spec().diff(_spec()), SpecialistDiff)

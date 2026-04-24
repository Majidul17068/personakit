from __future__ import annotations

import pytest

from personakit import Agent, Severity, Specialist
from personakit.examples import FALLS_PREVENTION_NURSE
from personakit.testing import MockProvider, assert_cited, assert_triggered

CANNED = {
    "summary": "Unwitnessed post-fall incident in an anticoagulated resident with new confusion.",
    "probes_answered": {
        "witnessed": "unwitnessed",
        "head_strike": None,
        "anticoagulated": True,
        "weight_bearing": True,
        "new_neuro_symptoms": True,
        "pre_fall_activity": "toileting",
        "time_and_lighting": "03:15, dim",
        "recent_med_changes": None,
        "recurrent": None,
    },
    "red_flags_detected": [
        {
            "id": "head_contact_in_an_anticoagulated_resident",
            "evidence": "on apixaban; head strike cannot be excluded",
        }
    ],
    "priorities_status": [
        {"priority": "Rule out head injury — assess GCS, pupils, neuro baseline", "status": "unmet"}
    ],
    "recommendations": [
        {
            "theme": "Neurological observation",
            "text": "Commence neuro obs every 15 min then hourly.",
            "citations": ["NICE CG176"],
        },
        {
            "theme": "GP / 111 contact",
            "text": "Contact GP / 111 within 2 hours.",
            "citations": ["NICE CG176 §1.4.11"],
        },
    ],
    "citations_used": ["NICE CG176", "NICE CG176 §1.4.11"],
}


@pytest.mark.asyncio
async def test_analyze_parses_canned_response():
    provider = MockProvider(responses=CANNED)
    agent = Agent(specialist=FALLS_PREVENTION_NURSE, provider=provider)
    result = await agent.analyze(
        "Resident on apixaban, unconscious for 10s, now confused."
    )
    assert result.summary.startswith("Unwitnessed")
    assert result.has_urgent
    assert_cited(result, "NICE CG176")


@pytest.mark.asyncio
async def test_pre_match_and_semantic_merge():
    provider = MockProvider(responses=CANNED)
    agent = Agent(specialist=FALLS_PREVENTION_NURSE, provider=provider)
    result = await agent.analyze("unconscious for several seconds; on apixaban")
    ids = {r.red_flag.id for r in result.red_flags_triggered}
    assert "loss_of_consciousness_before_during_or_after_the_fall" in ids
    assert "head_contact_in_an_anticoagulated_resident" in ids


@pytest.mark.asyncio
async def test_unanswered_probes_reported():
    provider = MockProvider(responses=CANNED)
    agent = Agent(specialist=FALLS_PREVENTION_NURSE, provider=provider)
    result = await agent.analyze("Short note, little info.")
    keys = {p.key for p in result.probes_unanswered}
    assert "head_strike" in keys
    assert "recent_med_changes" in keys


@pytest.mark.asyncio
async def test_chat_returns_raw_text():
    provider = MockProvider(responses="Photosynthesis is how plants make food.")
    tutor = Specialist(name="tutor", persona="You are a kind teacher.")
    agent = Agent(specialist=tutor, provider=provider)
    reply = await agent.chat("What is photosynthesis?")
    assert "Photosynthesis" in reply


@pytest.mark.asyncio
async def test_citations_required_enforced():
    nocite = {**CANNED, "citations_used": [], "recommendations": []}
    provider = MockProvider(responses=nocite)
    agent = Agent(specialist=FALLS_PREVENTION_NURSE, provider=provider)
    with pytest.raises(Exception) as exc_info:
        await agent.analyze("case with no cites")
    assert "citation" in str(exc_info.value).lower()


def test_severity_ordering():
    assert Severity.URGENT.value == "urgent"
    assert Severity.CRITICAL.value == "critical"


@pytest.mark.asyncio
async def test_triggered_assertion_helper():
    provider = MockProvider(responses=CANNED)
    agent = Agent(specialist=FALLS_PREVENTION_NURSE, provider=provider)
    result = await agent.analyze("unconscious; on apixaban")
    assert_triggered(result, "loss_of_consciousness_before_during_or_after_the_fall")

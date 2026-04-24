from __future__ import annotations

from personakit.examples import FALLS_PREVENTION_NURSE
from personakit.matching import merge_post, pre_match


def test_pre_match_triggers_on_keyword():
    text = "Resident found unconscious on the floor."
    hits = pre_match(FALLS_PREVENTION_NURSE, text)
    ids = {h.red_flag.id for h in hits}
    assert "loss_of_consciousness_before_during_or_after_the_fall" in ids


def test_pre_match_handles_case_insensitivity():
    text = "Severe HEADACHE reported an hour after the event."
    hits = pre_match(FALLS_PREVENTION_NURSE, text)
    assert any("new_confusion" in (h.red_flag.id or "") for h in hits)


def test_pre_match_empty_text():
    assert pre_match(FALLS_PREVENTION_NURSE, "") == []


def test_merge_prefers_deterministic_over_semantic():
    text = "Patient was unconscious for 30 seconds."
    pre = pre_match(FALLS_PREVENTION_NURSE, text)
    llm_hits = [
        {
            "id": "loss_of_consciousness_before_during_or_after_the_fall",
            "evidence": "LLM paraphrase of LOC",
        }
    ]
    merged = merge_post(FALLS_PREVENTION_NURSE, pre, llm_hits)
    assert len(merged) == 1
    assert merged[0].source in {"regex", "keyword"}


def test_merge_includes_semantic_only_flags():
    llm_hits = [
        {
            "id": "head_contact_in_an_anticoagulated_resident",
            "evidence": "Patient on apixaban with head strike suspected",
        }
    ]
    merged = merge_post(FALLS_PREVENTION_NURSE, [], llm_hits)
    assert len(merged) == 1
    assert merged[0].source == "semantic"

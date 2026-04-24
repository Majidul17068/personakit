from __future__ import annotations

from personakit import PromptBuilder
from personakit.examples import FALLS_PREVENTION_NURSE, MATH_TUTOR


def test_prompt_contains_role_and_frameworks():
    builder = PromptBuilder()
    prompt = builder.build_system_prompt(FALLS_PREVENTION_NURSE)
    assert "<role>" in prompt
    assert "Falls Prevention Specialist Nurse" in prompt
    assert "NICE NG161" in prompt
    assert "<red_flags>" in prompt


def test_minimal_specialist_prompt():
    builder = PromptBuilder()
    prompt = builder.build_system_prompt(MATH_TUTOR)
    assert "<role>" in prompt
    assert "<red_flags>" not in prompt
    assert "<probes>" not in prompt


def test_schema_has_probe_keys():
    builder = PromptBuilder()
    schema = builder.build_output_schema(FALLS_PREVENTION_NURSE)
    probe_props = schema["properties"]["probes_answered"]["properties"]
    assert "witnessed" in probe_props
    assert "anticoagulated" in probe_props


def test_schema_red_flag_ids_are_enumed():
    builder = PromptBuilder()
    schema = builder.build_output_schema(FALLS_PREVENTION_NURSE)
    rf_item = schema["properties"]["red_flags_detected"]["items"]
    assert "enum" in rf_item["properties"]["id"]
    assert len(rf_item["properties"]["id"]["enum"]) > 0


def test_selected_themes_narrows_output():
    builder = PromptBuilder()
    schema = builder.build_output_schema(
        FALLS_PREVENTION_NURSE, selected_themes=["Medication review"]
    )
    theme_enum = schema["properties"]["recommendations"]["items"]["properties"]["theme"]["enum"]
    assert theme_enum == ["Medication review"]

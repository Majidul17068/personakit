from __future__ import annotations

import pytest

from personakit import Framework, Probe, RedFlag, Severity, Specialist, Theme
from personakit.errors import SpecialistValidationError


def test_minimal_specialist():
    s = Specialist(name="bare", persona="I am minimal.")
    assert s.name == "bare"
    assert s.effective_display_name == "Bare"
    assert s.frameworks == []
    assert s.red_flags == []


def test_string_coercion():
    s = Specialist(
        name="spec",
        persona="x",
        frameworks=["NICE NG161", {"name": "Morse Fall Scale"}],
        probes=["Was it witnessed?"],
        themes=["Med review", {"name": "Physio"}],
    )
    assert isinstance(s.frameworks[0], Framework)
    assert s.frameworks[0].name == "NICE NG161"
    assert isinstance(s.probes[0], Probe)
    assert s.probes[0].key == "was_it_witnessed"
    assert s.themes[1].name == "Physio"


def test_probe_enum_requires_values():
    with pytest.raises(SpecialistValidationError):
        Probe(question="Q?", value_type="enum")


def test_red_flag_auto_id():
    rf = RedFlag(
        trigger="Loss of consciousness",
        severity=Severity.URGENT,
        action="Call 999",
    )
    assert rf.id == "loss_of_consciousness"


def test_duplicate_probe_keys_rejected():
    with pytest.raises(SpecialistValidationError):
        Specialist(
            name="dup",
            persona="x",
            probes=[
                Probe(question="A?", key="k"),
                Probe(question="B?", key="k"),
            ],
        )


def test_extend_appends_list_fields():
    base = Specialist(
        name="base",
        persona="x",
        frameworks=["NICE NG161"],
        constraints=["No prescribing"],
    )
    child = base.extend(
        name="child",
        frameworks=["Morse"],
        constraints=["Cite UK guidance"],
    )
    assert [f.name for f in child.frameworks] == ["NICE NG161", "Morse"]
    assert child.constraints == ["No prescribing", "Cite UK guidance"]
    assert child.name == "child"


def test_framework_citation_key_defaults_to_name():
    f = Framework(name="NICE NG161")
    assert f.citation_key == "NICE NG161"


def test_theme_default_selected():
    t = Theme(name="Physio")
    assert t.default_selected is True

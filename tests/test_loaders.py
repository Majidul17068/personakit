from __future__ import annotations

import json
from pathlib import Path

import pytest

from personakit import Specialist
from personakit.registry import SpecialistRegistry

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "examples" / "personas" / "falls_nurse.yaml"


def test_specialist_from_dict():
    s = Specialist.from_dict({"name": "x", "persona": "y"})  # type: ignore[attr-defined]
    assert s.name == "x"


def test_specialist_from_json(tmp_path):
    data = {
        "name": "dummy",
        "persona": "I'm a test.",
        "frameworks": ["F1"],
        "probes": ["Q1?"],
    }
    p = tmp_path / "dummy.json"
    p.write_text(json.dumps(data))
    s = Specialist.from_json(p)  # type: ignore[attr-defined]
    assert s.name == "dummy"
    assert s.frameworks[0].name == "F1"


@pytest.mark.skipif(not YAML_PATH.exists(), reason="YAML example not present")
def test_specialist_from_yaml():
    pytest.importorskip("yaml")
    s = Specialist.from_yaml(YAML_PATH)  # type: ignore[attr-defined]
    assert s.name == "falls_prevention_nurse"
    assert any(f.name == "NICE NG161" for f in s.frameworks)


def test_registry_from_directory(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"name": "a", "persona": "A"}))
    (tmp_path / "b.json").write_text(json.dumps({"name": "b", "persona": "B", "domain": "x.y"}))
    reg = SpecialistRegistry.from_directory(tmp_path)
    assert reg.names() == ["a", "b"]
    assert reg.get("a").persona == "A"
    assert reg.by_domain("x")[0].name == "b"

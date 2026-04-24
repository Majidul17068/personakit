"""File and dict loaders for Specialist definitions.

Enables the non-coder authoring path:

    specialist = Specialist.from_yaml("path/to/spec.yaml")
    specialist = Specialist.from_json("path/to/spec.json")
    specialist = Specialist.from_dict({...})

Keeping the loaders in a separate module lets us attach classmethods to
Specialist without forcing pyyaml as a core dependency.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import MissingDependencyError
from .specialist import Specialist


def specialist_from_dict(data: dict[str, Any]) -> Specialist:
    return Specialist(**data)


def specialist_from_json(path: str | Path) -> Specialist:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return specialist_from_dict(data)


def specialist_from_yaml(path: str | Path) -> Specialist:
    try:
        import yaml
    except ImportError as exc:
        raise MissingDependencyError(
            "YAML loading requires the 'pyyaml' package. "
            "Install with: pip install 'personakit[yaml]'"
        ) from exc
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML at {path} must be a mapping; got {type(data).__name__}.")
    return specialist_from_dict(data)


def _from_dict(cls: type[Specialist], data: dict[str, Any]) -> Specialist:
    return specialist_from_dict(data)


def _from_json(cls: type[Specialist], path: str | Path) -> Specialist:
    return specialist_from_json(path)


def _from_yaml(cls: type[Specialist], path: str | Path) -> Specialist:
    return specialist_from_yaml(path)


Specialist.from_dict = classmethod(_from_dict)  # type: ignore[attr-defined]
Specialist.from_json = classmethod(_from_json)  # type: ignore[attr-defined]
Specialist.from_yaml = classmethod(_from_yaml)  # type: ignore[attr-defined]

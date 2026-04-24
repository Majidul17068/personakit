"""Declarative specialist model — the heart of personakit.

A `Specialist` is a pure data object. It describes a role, the frameworks it
applies, the probes it asks, the red flags it watches for, the recommendation
themes it organises its output under, and the priorities it always enforces.

The runtime (`Agent`) consumes a `Specialist` — the Specialist itself has no
behaviour. This separation lets authors (nurses, lawyers, analysts, PMs) hand
over a YAML file to engineers and get a working agent without writing any
orchestration code.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .errors import SpecialistValidationError


class Severity(str, Enum):
    """Urgency classification applied to a red flag."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class MatchMode(str, Enum):
    """How a red flag is detected."""

    REGEX = "regex"
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    BOTH = "both"


ProbeType = Literal["string", "boolean", "number", "enum", "list"]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    slug = slug.strip("_")
    return slug or "field"


class Framework(BaseModel):
    """A body of knowledge or guideline the specialist applies.

    Examples: "NICE NG161", "UCC §9", "IFRS 15", "GCSE AQA Maths".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    authority: str | None = None
    url: str | None = None
    citation_key: str | None = Field(
        default=None,
        description="Short reference used in output citations; defaults to `name`.",
    )

    @model_validator(mode="after")
    def _fill_citation_key(self) -> Framework:
        if self.citation_key is None:
            object.__setattr__(self, "citation_key", self.name)
        return self


class Probe(BaseModel):
    """A diagnostic question the specialist asks of the input.

    Probes define the shape of the structured output: each probe becomes a field
    in the response schema, and the LLM is required to either fill it in or mark
    it as unknown.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    question: str
    key: str | None = Field(default=None, description="JSON key; derived from question if omitted.")
    category: str | None = None
    weight: Literal["low", "normal", "high"] = "normal"
    value_type: ProbeType = "string"
    enum_values: list[str] | None = None

    @model_validator(mode="after")
    def _fill_key(self) -> Probe:
        if self.key is None:
            object.__setattr__(self, "key", _slugify(self.question))
        if self.value_type == "enum" and not self.enum_values:
            raise SpecialistValidationError(
                f"Probe {self.question!r} has value_type='enum' but no enum_values."
            )
        return self


class RedFlag(BaseModel):
    """A trigger → action rule enforced by the specialist.

    This is the single most distinctive feature of personakit. A RedFlag
    declares: "if you see this condition in the input or in your own analysis,
    raise an urgent alert with this action and cite this authority."

    Matching happens in two phases:

    - `regex` / `keyword`: deterministic pre-match on raw input (fast, offline)
    - `semantic`: post-match by the LLM, which evaluates whether the trigger
      applies to the case (handles paraphrase, synonyms, context)
    - `both` (default): merge both phases

    Regex / keyword patterns are optional — without them, matching falls back to
    semantic only.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    trigger: str
    severity: Severity
    action: str
    citation: str | None = None
    match: MatchMode = MatchMode.BOTH
    patterns: list[str] = Field(
        default_factory=list,
        description="Regex / keyword patterns for deterministic pre-match.",
    )
    id: str | None = None

    @model_validator(mode="after")
    def _fill_id(self) -> RedFlag:
        if self.id is None:
            object.__setattr__(self, "id", _slugify(self.trigger))
        return self


class Theme(BaseModel):
    """A recommendation theme the specialist organises output under.

    Users can select which themes to surface at call time, enabling dynamic
    response shaping without changing the specialist definition.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str | None = None
    default_selected: bool = True


class FocusAreas(BaseModel):
    """Two free-text fields that shape summary vs prevention narratives."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str | None = None
    prevention: str | None = None


def _coerce_framework(value: Any) -> Framework:
    if isinstance(value, Framework):
        return value
    if isinstance(value, str):
        return Framework(name=value)
    if isinstance(value, dict):
        return Framework(**value)
    raise SpecialistValidationError(f"Cannot coerce {value!r} into Framework.")


def _coerce_probe(value: Any) -> Probe:
    if isinstance(value, Probe):
        return value
    if isinstance(value, str):
        return Probe(question=value)
    if isinstance(value, dict):
        return Probe(**value)
    raise SpecialistValidationError(f"Cannot coerce {value!r} into Probe.")


def _coerce_red_flag(value: Any) -> RedFlag:
    if isinstance(value, RedFlag):
        return value
    if isinstance(value, dict):
        return RedFlag(**value)
    raise SpecialistValidationError(f"Cannot coerce {value!r} into RedFlag.")


def _coerce_theme(value: Any) -> Theme:
    if isinstance(value, Theme):
        return value
    if isinstance(value, str):
        return Theme(name=value)
    if isinstance(value, dict):
        return Theme(**value)
    raise SpecialistValidationError(f"Cannot coerce {value!r} into Theme.")


class Specialist(BaseModel):
    """A declarative specialist agent definition.

    The required fields are `name` and `persona`. Everything else is optional —
    a minimal Specialist with just those two fields behaves as a plain
    persona-prompted chat agent. Adding frameworks, probes, red flags, and
    themes progressively upgrades the agent into a structured analyst that
    produces machine-readable output with citations and safety triggers.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)

    name: str = Field(
        ...,
        description="Machine identifier (snake_case recommended). Unique within a registry.",
    )
    display_name: str | None = Field(default=None, description="Human-readable name.")
    domain: str | None = Field(
        default=None,
        description="Taxonomy tag — e.g. 'healthcare.clinical', 'legal.contracts'.",
    )
    persona: str = Field(
        ...,
        description="Role description and voice. Becomes part of the system prompt.",
    )
    tone: str | None = None
    style: str | None = None

    frameworks: list[Framework] = Field(default_factory=list)
    probes: list[Probe] = Field(default_factory=list)
    red_flags: list[RedFlag] = Field(default_factory=list)
    themes: list[Theme] = Field(default_factory=list)

    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    priorities: list[str] = Field(
        default_factory=list,
        description="Always-on checks, enforced regardless of input.",
    )

    taxonomies: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Domain taxonomies — e.g. {'primary': [...], 'secondary': [...]} "
        "or {'jurisdictions': [...]}. Free-form to stay domain-neutral.",
    )
    focus: FocusAreas = Field(default_factory=FocusAreas)

    citations_required: bool = Field(
        default=False,
        description=(
            "If True, the Agent raises CitationMissingError when output "
            "lacks framework citations."
        ),
    )
    response_length: Literal["brief", "standard", "detailed"] = "standard"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("frameworks", mode="before")
    @classmethod
    def _coerce_frameworks(cls, value: Any) -> list[Framework]:
        if value is None:
            return []
        return [_coerce_framework(v) for v in value]

    @field_validator("probes", mode="before")
    @classmethod
    def _coerce_probes(cls, value: Any) -> list[Probe]:
        if value is None:
            return []
        return [_coerce_probe(v) for v in value]

    @field_validator("red_flags", mode="before")
    @classmethod
    def _coerce_red_flags(cls, value: Any) -> list[RedFlag]:
        if value is None:
            return []
        return [_coerce_red_flag(v) for v in value]

    @field_validator("themes", mode="before")
    @classmethod
    def _coerce_themes(cls, value: Any) -> list[Theme]:
        if value is None:
            return []
        return [_coerce_theme(v) for v in value]

    @model_validator(mode="after")
    def _check_unique_keys(self) -> Specialist:
        probe_keys = [p.key for p in self.probes]
        if len(probe_keys) != len(set(probe_keys)):
            dupes = {k for k in probe_keys if probe_keys.count(k) > 1}
            raise SpecialistValidationError(f"Duplicate probe keys: {sorted(dupes)}")
        flag_ids = [f.id for f in self.red_flags]
        if len(flag_ids) != len(set(flag_ids)):
            dupes = {fid for fid in flag_ids if flag_ids.count(fid) > 1}
            raise SpecialistValidationError(f"Duplicate red flag ids: {sorted(dupes)}")
        theme_names = [t.name for t in self.themes]
        if len(theme_names) != len(set(theme_names)):
            dupes = {n for n in theme_names if theme_names.count(n) > 1}
            raise SpecialistValidationError(f"Duplicate theme names: {sorted(dupes)}")
        return self

    @property
    def effective_display_name(self) -> str:
        return self.display_name or self.name.replace("_", " ").title()

    def extend(self, **overrides: Any) -> Specialist:
        """Return a new Specialist with the given fields overridden.

        List fields in `overrides` are appended (not replaced) to avoid losing
        inherited frameworks / probes / red_flags by accident. Pass an explicit
        empty list to clear.
        """
        list_fields = {
            "frameworks",
            "probes",
            "red_flags",
            "themes",
            "goals",
            "constraints",
            "priorities",
        }
        base = self.model_dump()
        for key, value in overrides.items():
            if key in list_fields and isinstance(value, list):
                base[key] = base.get(key, []) + value
                continue
            base[key] = value
        return Specialist(**base)

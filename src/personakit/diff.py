"""Structured diff between two Specialists.

``Specialist.diff(other)`` returns a ``SpecialistDiff`` — a serialisable model
containing every change between two specs, categorised by collection
(frameworks / probes / red_flags / themes) and by scalar field. Use the
markdown renderer for human-readable output (CLI, code review comments) or
``model_dump_json()`` for machine-readable diffs (CI gating).

This module deliberately keeps the diff structure flat and explicit. The
schema is part of the public API and is meant to be consumed by external
tools (audit pipelines, compliance dashboards, the planned
``personakit verify`` CLI in v0.3 Phase 5).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from .specialist import Specialist


# Scalar fields that go through the field-by-field comparison. Anything not
# in this list is either a list collection (handled separately) or a property
# (excluded from the dump).
_SCALAR_FIELDS: Final[tuple[str, ...]] = (
    "name",
    "display_name",
    "domain",
    "persona",
    "tone",
    "style",
    "goals",
    "constraints",
    "priorities",
    "taxonomies",
    "focus",
    "citations_required",
    "response_length",
    "metadata",
)

# Collection fields keyed by their "identity" field — the value the diff uses
# to align items between A and B (otherwise we'd treat a reorder as a
# full add/remove cycle, which is noisy).
_COLLECTION_IDENTITY: Final[dict[str, tuple[str, ...]]] = {
    "frameworks": ("name",),
    "probes": ("key", "question"),
    "red_flags": ("id", "trigger"),
    "themes": ("name",),
}


class FieldDiff(BaseModel):
    """One scalar field whose value changed between two Specialists."""

    model_config = ConfigDict(frozen=True)

    field: str
    before: Any
    after: Any


class CollectionItemChange(BaseModel):
    """One item that exists in both specs but with different content."""

    model_config = ConfigDict(frozen=True)

    identity: str
    before: dict[str, Any]
    after: dict[str, Any]


class SpecialistDiff(BaseModel):
    """Structured diff between two Specialists.

    ``same`` is the quick-check field — True iff the checksums match.
    Everything else is detail to render in CLIs / dashboards / replay logs.
    """

    model_config = ConfigDict(frozen=True)

    same: bool
    a_checksum: str
    b_checksum: str
    field_changes: list[FieldDiff] = Field(default_factory=list)
    added: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    removed: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    changed: dict[str, list[CollectionItemChange]] = Field(default_factory=dict)

    def to_markdown(self) -> str:
        """Render a reviewer-friendly markdown summary of the diff."""
        lines: list[str] = []
        if self.same:
            lines.append(f"**No changes.** Checksums match: `{self.a_checksum[:12]}...`")
            return "\n".join(lines)

        lines.append("# Specialist diff")
        lines.append("")
        lines.append(f"- **A:** `{self.a_checksum[:16]}...`")
        lines.append(f"- **B:** `{self.b_checksum[:16]}...`")
        lines.append("")

        if self.field_changes:
            lines.append("## Field changes")
            for fc in self.field_changes:
                before = _short_repr(fc.before)
                after = _short_repr(fc.after)
                lines.append(f"- **{fc.field}**: `{before}` → `{after}`")
            lines.append("")

        for collection in ("frameworks", "probes", "red_flags", "themes"):
            added = self.added.get(collection, [])
            removed = self.removed.get(collection, [])
            changed = self.changed.get(collection, [])
            if not (added or removed or changed):
                continue
            lines.append(f"## {collection.replace('_', ' ').title()}")
            if added:
                lines.append(f"**Added** ({len(added)}):")
                for item in added:
                    lines.append(f"- `+` {_short_item(item)}")
            if removed:
                lines.append(f"**Removed** ({len(removed)}):")
                for item in removed:
                    lines.append(f"- `-` {_short_item(item)}")
            if changed:
                lines.append(f"**Changed** ({len(changed)}):")
                for change in changed:
                    lines.append(f"- `~` `{change.identity}`")
            lines.append("")
        return "\n".join(lines).rstrip()


def _short_repr(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _short_item(item: dict[str, Any]) -> str:
    for key in ("name", "key", "id", "trigger", "question"):
        if item.get(key):
            return f"{key}={item[key]!r}"
    return _short_repr(item)


def _identity_for(item: dict[str, Any], identity_fields: tuple[str, ...]) -> str:
    """Pick the first non-empty identity field; fall back to JSON repr."""
    for field in identity_fields:
        value = item.get(field)
        if value:
            return str(value)
    return _short_repr(item)


def diff_specialists(a: Specialist, b: Specialist) -> SpecialistDiff:
    """Compute a structured diff between two Specialists.

    Pure function (no I/O). Both inputs must already be validated
    ``Specialist`` instances. The result is a frozen ``SpecialistDiff``;
    callers serialise or render as needed.
    """
    a_dump = a.model_dump(mode="json")
    b_dump = b.model_dump(mode="json")

    a_checksum = a.checksum()
    b_checksum = b.checksum()
    same = a_checksum == b_checksum

    field_changes: list[FieldDiff] = []
    for field in _SCALAR_FIELDS:
        a_val = a_dump.get(field)
        b_val = b_dump.get(field)
        if a_val != b_val:
            field_changes.append(FieldDiff(field=field, before=a_val, after=b_val))

    added: dict[str, list[dict[str, Any]]] = {}
    removed: dict[str, list[dict[str, Any]]] = {}
    changed: dict[str, list[CollectionItemChange]] = {}

    for collection, identity_fields in _COLLECTION_IDENTITY.items():
        a_items: list[dict[str, Any]] = a_dump.get(collection, []) or []
        b_items: list[dict[str, Any]] = b_dump.get(collection, []) or []

        # Build identity → item maps. Position-based fallback when no
        # identity field is set (preserves ordering-as-identity for unnamed items).
        a_map = {
            _identity_for(item, identity_fields) or f"__pos_{i}": item
            for i, item in enumerate(a_items)
        }
        b_map = {
            _identity_for(item, identity_fields) or f"__pos_{i}": item
            for i, item in enumerate(b_items)
        }

        a_keys = set(a_map)
        b_keys = set(b_map)

        added_items = [b_map[k] for k in sorted(b_keys - a_keys)]
        removed_items = [a_map[k] for k in sorted(a_keys - b_keys)]
        changed_items: list[CollectionItemChange] = []
        for k in sorted(a_keys & b_keys):
            if a_map[k] != b_map[k]:
                changed_items.append(
                    CollectionItemChange(identity=k, before=a_map[k], after=b_map[k])
                )

        if added_items:
            added[collection] = added_items
        if removed_items:
            removed[collection] = removed_items
        if changed_items:
            changed[collection] = changed_items

    return SpecialistDiff(
        same=same,
        a_checksum=a_checksum,
        b_checksum=b_checksum,
        field_changes=field_changes,
        added=added,
        removed=removed,
        changed=changed,
    )


__all__ = [
    "CollectionItemChange",
    "FieldDiff",
    "SpecialistDiff",
    "diff_specialists",
]

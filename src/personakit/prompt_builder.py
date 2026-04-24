"""Translates a `Specialist` into an LLM system prompt plus a JSON output schema.

Two outputs:

1. A human-readable, XML-tagged system prompt. XML tags are used because they
   improve adherence on Claude and work at least as well as Markdown on GPT.
2. A machine-readable JSON Schema describing the expected structured output.
   The schema is auto-derived from the Specialist's probes, red_flags, themes,
   and priorities — authors never write schemas by hand.
"""

from __future__ import annotations

from typing import Any

from .specialist import Specialist, Theme


class PromptBuilder:
    """Default deterministic prompt builder.

    Swap with a custom subclass if you need a different prompt style (Markdown,
    bare-text, domain-specific headers, etc.).
    """

    def build_system_prompt(
        self,
        specialist: Specialist,
        selected_themes: list[str] | None = None,
    ) -> str:
        themes = _filter_themes(specialist.themes, selected_themes)
        parts: list[str] = []

        parts.append("<role>")
        parts.append(
            f"You are {specialist.effective_display_name}. {specialist.persona}".strip()
        )
        if specialist.tone:
            parts.append(f"Tone: {specialist.tone}.")
        if specialist.style:
            parts.append(f"Style: {specialist.style}.")
        parts.append("</role>")

        if specialist.goals:
            parts.append("<goals>")
            parts.extend(f"- {g}" for g in specialist.goals)
            parts.append("</goals>")

        if specialist.constraints:
            parts.append("<constraints>")
            parts.extend(f"- {c}" for c in specialist.constraints)
            parts.append("</constraints>")

        if specialist.frameworks:
            parts.append("<frameworks>")
            parts.append("Apply and cite these frameworks where relevant:")
            for f in specialist.frameworks:
                line = f"- {f.name}"
                if f.authority:
                    line += f" ({f.authority})"
                parts.append(line)
            parts.append("</frameworks>")

        if specialist.probes:
            parts.append("<probes>")
            parts.append(
                "Evaluate the case against these diagnostic questions. For each, "
                "record your answer (or null if the input is silent) in "
                "`probes_answered` using the given key."
            )
            for p in specialist.probes:
                meta = f"[key={p.key}, type={p.value_type}"
                if p.category:
                    meta += f", category={p.category}"
                if p.weight != "normal":
                    meta += f", weight={p.weight}"
                if p.enum_values:
                    meta += f", enum={p.enum_values}"
                meta += "]"
                parts.append(f"- {p.question} {meta}")
            parts.append("</probes>")

        if specialist.red_flags:
            parts.append("<red_flags>")
            parts.append(
                "If any of the following conditions apply to the case, include the "
                "matching entry in `red_flags_detected`. Quote the evidence from "
                "the input that triggered it."
            )
            for rf in specialist.red_flags:
                cite = f" — cite: {rf.citation}" if rf.citation else ""
                parts.append(
                    f"- [{rf.severity.value}] id={rf.id}: {rf.trigger} "
                    f"→ {rf.action}{cite}"
                )
            parts.append("</red_flags>")

        if specialist.priorities:
            parts.append("<immediate_priorities>")
            parts.append(
                "Always report the status of each priority in `priorities_status`:"
            )
            for p_str in specialist.priorities:
                parts.append(f"- {p_str}")
            parts.append("</immediate_priorities>")

        if themes:
            parts.append("<recommendation_themes>")
            parts.append(
                "Organise recommendations under the following themes. Produce one "
                "or more recommendations per theme only when the input supports it "
                "— do not invent recommendations."
            )
            for t in themes:
                desc = f": {t.description}" if t.description else ""
                parts.append(f"- {t.name}{desc}")
            parts.append("</recommendation_themes>")

        if specialist.taxonomies:
            parts.append("<taxonomies>")
            for taxonomy, values in specialist.taxonomies.items():
                parts.append(f"{taxonomy}:")
                for v in values:
                    parts.append(f"  - {v}")
            parts.append("</taxonomies>")

        if specialist.focus.summary or specialist.focus.prevention:
            parts.append("<focus>")
            if specialist.focus.summary:
                parts.append(f"Summary should emphasise: {specialist.focus.summary}")
            if specialist.focus.prevention:
                parts.append(f"Prevention should emphasise: {specialist.focus.prevention}")
            parts.append("</focus>")

        parts.append("<output_format>")
        parts.append(
            "Respond with a single JSON object matching the provided schema. "
            "Do not wrap it in Markdown code fences. Do not add prose outside the "
            "JSON object. If you cannot answer a probe from the input, set its "
            "value to null — do not invent facts."
        )
        if specialist.citations_required:
            parts.append(
                "Every recommendation MUST include at least one framework citation "
                "from the frameworks list. Output without citations will be rejected."
            )
        length_hint = {
            "brief": "Keep the summary to 1-2 sentences.",
            "standard": "Keep the summary to 3-5 sentences.",
            "detailed": "The summary may be up to 10 sentences.",
        }[specialist.response_length]
        parts.append(length_hint)
        parts.append("</output_format>")

        return "\n".join(parts)

    def build_output_schema(
        self,
        specialist: Specialist,
        selected_themes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Produce a JSON Schema describing the expected LLM response."""
        themes = _filter_themes(specialist.themes, selected_themes)
        probe_props: dict[str, Any] = {}
        for p in specialist.probes:
            probe_props[p.key] = _probe_json_schema(p)

        red_flag_ids = [rf.id for rf in specialist.red_flags]
        theme_names = [t.name for t in themes]

        schema: dict[str, Any] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string"},
                "probes_answered": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": probe_props,
                    "required": list(probe_props.keys()),
                }
                if probe_props
                else {"type": "object"},
                "red_flags_detected": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "evidence"],
                        "properties": {
                            "id": (
                                {"type": "string", "enum": red_flag_ids}
                                if red_flag_ids
                                else {"type": "string"}
                            ),
                            "evidence": {"type": "string"},
                        },
                    },
                },
                "priorities_status": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["priority", "status"],
                        "properties": {
                            "priority": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["met", "unmet", "unknown"],
                            },
                            "notes": {"type": "string"},
                        },
                    },
                },
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["theme", "text"],
                        "properties": {
                            "theme": (
                                {"type": "string", "enum": theme_names}
                                if theme_names
                                else {"type": "string"}
                            ),
                            "text": {"type": "string"},
                            "citations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "priority": {"type": "string"},
                        },
                    },
                },
                "citations_used": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["summary", "recommendations"],
        }
        return schema


def _probe_json_schema(probe: Any) -> dict[str, Any]:
    base: dict[str, Any]
    if probe.value_type == "boolean":
        base = {"type": ["boolean", "null"]}
    elif probe.value_type == "number":
        base = {"type": ["number", "null"]}
    elif probe.value_type == "enum":
        base = {"type": ["string", "null"], "enum": [*probe.enum_values, None]}
    elif probe.value_type == "list":
        base = {"type": ["array", "null"], "items": {"type": "string"}}
    else:
        base = {"type": ["string", "null"]}
    base["description"] = probe.question
    return base


def _filter_themes(all_themes: list[Theme], selected: list[str] | None) -> list[Theme]:
    if selected is None:
        return [t for t in all_themes if t.default_selected]
    wanted = set(selected)
    return [t for t in all_themes if t.name in wanted]

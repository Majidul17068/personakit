"""Red-flag matching engine.

Two phases:

- `pre_match` — runs on raw input text. Uses regex and keyword patterns declared
  on the RedFlag. Deterministic, offline, cheap.
- `merge_post` — merges pre-match results with LLM-reported triggers. Handles
  de-duplication by red-flag id and prefers deterministic evidence when both
  sources agree.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from .result import TriggeredRedFlag
from .specialist import MatchMode, RedFlag, Specialist


def pre_match(specialist: Specialist, text: str) -> list[TriggeredRedFlag]:
    """Run deterministic red-flag matching on the raw input."""
    if not text:
        return []
    triggered: list[TriggeredRedFlag] = []
    for rf in specialist.red_flags:
        if rf.match not in {MatchMode.REGEX, MatchMode.KEYWORD, MatchMode.BOTH}:
            continue
        for pattern in rf.patterns:
            source, evidence = _match_one(pattern, text, rf.match)
            if evidence is not None:
                triggered.append(
                    TriggeredRedFlag(red_flag=rf, evidence=evidence, source=source)
                )
                break  # one pattern match per flag is enough
    return triggered


def merge_post(
    specialist: Specialist,
    pre: Iterable[TriggeredRedFlag],
    llm_hits: Iterable[dict[str, str]],
) -> list[TriggeredRedFlag]:
    """Merge pre-match results with LLM-reported red flags."""
    by_id: dict[str, RedFlag] = {rf.id: rf for rf in specialist.red_flags if rf.id}
    merged: dict[str, TriggeredRedFlag] = {
        t.red_flag.id: t for t in pre if t.red_flag.id is not None
    }
    for hit in llm_hits:
        rf_id = hit.get("id")
        if rf_id is None or rf_id not in by_id:
            continue
        rf = by_id[rf_id]
        if rf.match not in {MatchMode.SEMANTIC, MatchMode.BOTH}:
            continue
        evidence = hit.get("evidence", "").strip() or "(no evidence quoted)"
        if rf_id in merged:
            continue  # deterministic evidence wins
        merged[rf_id] = TriggeredRedFlag(red_flag=rf, evidence=evidence, source="semantic")
    ordered: list[TriggeredRedFlag] = []
    for rf in specialist.red_flags:
        if rf.id in merged:
            ordered.append(merged[rf.id])
    return ordered


def _match_one(pattern: str, text: str, mode: MatchMode) -> tuple[str, str | None]:
    if mode in {MatchMode.REGEX, MatchMode.BOTH}:
        try:
            m = re.search(pattern, text, re.IGNORECASE)
        except re.error:
            m = None
        if m is not None:
            return "regex", _context(text, m.start(), m.end())
    if mode in {MatchMode.KEYWORD, MatchMode.BOTH}:
        lowered = text.lower()
        needle = pattern.lower()
        idx = lowered.find(needle)
        if idx >= 0:
            return "keyword", _context(text, idx, idx + len(needle))
    return "", None


def _context(text: str, start: int, end: int, window: int = 40) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    snippet = text[left:right].replace("\n", " ").strip()
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(text) else ""
    return f"{prefix}{snippet}{suffix}"

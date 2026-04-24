"""Testing helpers — re-exports and assertion utilities.

Usage:

    from personakit.testing import MockProvider, assert_triggered
"""

from __future__ import annotations

from .providers.mock import MockProvider
from .result import AnalyzeResult

__all__ = ["MockProvider", "assert_cited", "assert_not_triggered", "assert_triggered"]


def assert_triggered(result: AnalyzeResult, red_flag_id: str) -> None:
    ids = {t.red_flag.id for t in result.red_flags_triggered}
    if red_flag_id not in ids:
        raise AssertionError(
            f"Expected red flag {red_flag_id!r} to trigger. "
            f"Triggered: {sorted(i for i in ids if i)}"
        )


def assert_not_triggered(result: AnalyzeResult, red_flag_id: str) -> None:
    ids = {t.red_flag.id for t in result.red_flags_triggered}
    if red_flag_id in ids:
        raise AssertionError(f"Red flag {red_flag_id!r} should NOT have triggered.")


def assert_cited(result: AnalyzeResult, citation_key: str) -> None:
    if citation_key not in result.citations_used:
        raise AssertionError(
            f"Expected citation {citation_key!r}. Got: {result.citations_used}"
        )

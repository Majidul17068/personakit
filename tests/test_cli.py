"""Tests for the `personakit` CLI (v0.3.0a2 Phase 2).

These verify the `personakit diff <a> <b>` command, including exit codes,
markdown vs JSON output, and error handling.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def yaml_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Write two YAML specs that differ on one probe."""
    a_path = tmp_path / "a.yaml"
    a_path.write_text(
        """
name: test-spec
persona: Original
probes:
  - question: Original probe?
    key: orig
""".strip()
    )
    b_path = tmp_path / "b.yaml"
    b_path.write_text(
        """
name: test-spec
persona: Original
probes:
  - question: Updated probe?
    key: updated
""".strip()
    )
    return a_path, b_path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke `python -m personakit ...` in a subprocess.

    Sets PYTHONPATH so the subprocess finds the editable source tree even when
    macOS has re-flagged the editable .pth file as hidden (see ROADMAP tech debt).
    """
    repo_src = Path(__file__).resolve().parent.parent / "src"
    env = {**os.environ, "PYTHONPATH": str(repo_src)}
    return subprocess.run(
        [sys.executable, "-m", "personakit", *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_diff_exit_zero_for_identical(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(
        """
name: test-spec
persona: Same
""".strip()
    )
    proc = _run_cli("diff", str(spec_path), str(spec_path))
    assert proc.returncode == 0, proc.stderr
    assert "No changes" in proc.stdout


def test_cli_diff_exit_one_when_specs_differ(yaml_pair: tuple[Path, Path]) -> None:
    a, b = yaml_pair
    proc = _run_cli("diff", str(a), str(b))
    assert proc.returncode == 1
    assert "Specialist diff" in proc.stdout


def test_cli_diff_json_output(yaml_pair: tuple[Path, Path]) -> None:
    a, b = yaml_pair
    proc = _run_cli("diff", str(a), str(b), "--json")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["same"] is False
    assert "a_checksum" in payload
    assert "b_checksum" in payload


def test_cli_diff_quiet_suppresses_output(yaml_pair: tuple[Path, Path]) -> None:
    a, b = yaml_pair
    proc = _run_cli("diff", str(a), str(b), "--quiet")
    assert proc.returncode == 1
    assert proc.stdout == ""


def test_cli_diff_missing_file_exits_two(tmp_path: Path) -> None:
    proc = _run_cli(
        "diff", str(tmp_path / "nonexistent.yaml"), str(tmp_path / "also-missing.yaml")
    )
    assert proc.returncode == 2
    assert "error" in proc.stderr.lower()


def test_cli_no_command_prints_help() -> None:
    proc = _run_cli()
    assert proc.returncode == 2
    assert "usage" in proc.stdout.lower() or "usage" in proc.stderr.lower()

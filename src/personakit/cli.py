"""personakit command-line interface.

Currently exposes a single command:

    personakit diff <a.yaml> <b.yaml> [--json] [--quiet]

Compares two Specialist YAML files. Exit code:
    0  — specs are identical (checksums match)
    1  — specs differ
    2  — invocation error (file not found, YAML parse error, etc.)

This module is intentionally light. The diff engine lives in
``personakit.diff``; this file just glues argparse + file loading +
output formatting on top.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .diff import diff_specialists
from .errors import PersonakitError
from .specialist import Specialist


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="personakit",
        description=(
            "personakit — declarative LLM specialist agents. "
            "See https://pypi.org/project/personakit/ for full docs."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    diff_p = subparsers.add_parser(
        "diff",
        help="Compare two Specialist YAML files and report what changed.",
    )
    diff_p.add_argument("a", type=Path, help="Path to the first Specialist YAML file.")
    diff_p.add_argument("b", type=Path, help="Path to the second Specialist YAML file.")
    diff_p.add_argument(
        "--json",
        action="store_true",
        help="Output the diff as JSON instead of markdown.",
    )
    diff_p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output; rely on the exit code (0=same, 1=differ).",
    )
    return parser


def _load_specialist(path: Path) -> Specialist:
    if not path.exists():
        raise FileNotFoundError(f"Specialist file not found: {path}")
    # `from_yaml` is attached dynamically by personakit.loaders. mypy can't see
    # it, but it's always present once the package is imported (loaders runs
    # at import time via __init__.py).
    return Specialist.from_yaml(path)  # type: ignore[attr-defined,no-any-return]


def _cmd_diff(args: argparse.Namespace) -> int:
    try:
        a = _load_specialist(args.a)
        b = _load_specialist(args.b)
    except (FileNotFoundError, PersonakitError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    diff = diff_specialists(a, b)

    if not args.quiet:
        if args.json:
            print(diff.model_dump_json(indent=2))
        else:
            print(diff.to_markdown())

    return 0 if diff.same else 1


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``personakit`` console script."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "diff":
        return _cmd_diff(args)

    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover — exercised via console_scripts
    sys.exit(main())

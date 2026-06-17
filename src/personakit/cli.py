"""personakit command-line interface.

Exposed commands:

    personakit diff <a.yaml> <b.yaml> [--json] [--quiet]
        Compare two Specialist YAML files. Exit 0=same, 1=differ, 2=error.

    personakit show <spec.yaml> [--json]
        Print a summary of a Specialist (name, checksum, counts,
        persona preview). Exit 0=ok, 2=error.

This module is intentionally light. The diff engine lives in
``personakit.diff``; this file just glues argparse + file loading +
output formatting on top.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path
from typing import Any

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

    show_p = subparsers.add_parser(
        "show",
        help="Print a summary of a Specialist YAML file (name, checksum, counts).",
    )
    show_p.add_argument(
        "spec", type=Path, help="Path to the Specialist YAML file."
    )
    show_p.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of human-readable text.",
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


def _cmd_show(args: argparse.Namespace) -> int:
    try:
        spec = _load_specialist(args.spec)
    except (FileNotFoundError, PersonakitError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    counts: dict[str, int] = {
        "frameworks": len(spec.frameworks),
        "probes": len(spec.probes),
        "red_flags": len(spec.red_flags),
        "themes": len(spec.themes),
        "goals": len(spec.goals),
        "constraints": len(spec.constraints),
        "priorities": len(spec.priorities),
    }
    summary: dict[str, Any] = {
        "name": spec.name,
        "display_name": spec.effective_display_name,
        "domain": spec.domain,
        "checksum": spec.checksum(),
        "persona_preview": textwrap.shorten(spec.persona, width=160, placeholder="…"),
        "counts": counts,
        "citations_required": spec.citations_required,
        "response_length": spec.response_length,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"# {summary['display_name']}")
        print(f"  name        : {summary['name']}")
        if summary["domain"]:
            print(f"  domain      : {summary['domain']}")
        print(f"  checksum    : {summary['checksum'][:16]}…")
        print(f"  citations   : {'required' if summary['citations_required'] else 'optional'}")
        print(f"  response    : {summary['response_length']}")
        print()
        print(f"  persona     : {summary['persona_preview']}")
        print()
        print("  counts:")
        for key, count in counts.items():
            print(f"    {key:14s}: {count}")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``personakit`` console script."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "diff":
        return _cmd_diff(args)
    if args.command == "show":
        return _cmd_show(args)

    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover — exercised via console_scripts
    sys.exit(main())

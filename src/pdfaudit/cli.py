"""Command-line interface.

    pdfaudit scan FILE [--json] [--only VEC,VEC] [--fail-on LEVEL] [--no-color]

Exit code is the worst severity mapped against ``--fail-on`` so it drops cleanly
into CI: 0 = clean (or below threshold), 2 = at/above threshold, 1 = usage/IO
error. ``--list-vectors`` prints the available detector names.
"""

from __future__ import annotations

import argparse
import sys

from .engine import Engine
from .model import Severity
from .reporters import to_json, format_cli

_EXIT_OK = 0
_EXIT_ERROR = 1
_EXIT_FINDINGS = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdfaudit",
        description="Audit a PDF for recoverable/leaked content behind redactions.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Scan a PDF file for redaction leaks.")
    scan.add_argument("file", help="Path to the PDF to scan.")
    scan.add_argument("--json", action="store_true", help="Emit JSON instead of a report.")
    scan.add_argument("--only", default=None,
                      help="Comma-separated detector names to run (see --list-vectors).")
    scan.add_argument("--fail-on", default="high",
                      choices=[s.label for s in Severity],
                      help="Minimum severity that causes a non-zero exit (default: high).")
    scan.add_argument("--no-color", action="store_true", help="Disable ANSI colour.")

    sub.add_parser("list-vectors", help="List available detector names.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    engine = Engine()

    if args.command == "list-vectors":
        for name in engine.available_vectors():
            print(name)
        return _EXIT_OK

    # scan
    only = [v.strip() for v in args.only.split(",")] if args.only else None
    if only:
        unknown = set(only) - set(engine.available_vectors())
        if unknown:
            print(f"Unknown vector(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return _EXIT_ERROR

    try:
        report = engine.scan(args.file, only=only)
    except FileNotFoundError:
        print(f"File not found: {args.file}", file=sys.stderr)
        return _EXIT_ERROR
    except Exception as exc:
        print(f"Could not open PDF: {type(exc).__name__}: {exc}", file=sys.stderr)
        return _EXIT_ERROR

    try:
        if args.json:
            print(to_json(report))
        else:
            print(format_cli(report, color=not args.no_color))
    except BrokenPipeError:
        # Output was piped into something that closed early (head/less). Exit
        # quietly rather than dumping a traceback.
        try:
            sys.stdout.close()
        except Exception:
            pass
        return _EXIT_OK

    threshold = Severity.from_label(args.fail_on)
    worst = report.worst_severity
    if worst is not None and worst >= threshold:
        return _EXIT_FINDINGS
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

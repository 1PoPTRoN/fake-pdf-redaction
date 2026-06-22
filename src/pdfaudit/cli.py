"""Command-line interface.

    pdfaudit scan FILE [--json] [--only VEC,VEC] [--fail-on LEVEL] [--no-color]

Exit code drops cleanly into CI:
  0 = clean / below threshold AND every detector ran
  2 = a finding at or above ``--fail-on`` (default high)
  3 = scan incomplete — a detector errored, so "clean" cannot be certified
      (suppress with ``--no-fail-on-error``)
  1 = usage / I/O error
``list-vectors`` prints the available detector names.
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
_EXIT_INCOMPLETE = 3


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
    scan.add_argument("--no-fail-on-error", action="store_true",
                      help="Do not exit 3 when a detector errors (default: a detector "
                           "error fails the gate, since 'clean' cannot be certified).")
    scan.add_argument("--max-memory", type=int, default=None, metavar="MB",
                      help="Cap address space (MiB) so a decompression bomb fails safely "
                           "instead of exhausting memory. Unix only; best-effort.")

    sub.add_parser("list-vectors", help="List available detector names.")
    return parser


def _apply_memory_limit(mb: int) -> None:
    try:
        import resource

        limit = mb * 1024 * 1024
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        new_hard = hard if hard != resource.RLIM_INFINITY and hard < limit else limit
        resource.setrlimit(resource.RLIMIT_AS, (limit, new_hard))
    except Exception:
        pass  # not supported on this platform; --max-memory is best-effort


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    engine = Engine()

    if args.command == "list-vectors":
        for name in engine.available_vectors():
            print(name)
        return _EXIT_OK

    # scan
    if args.max_memory:
        _apply_memory_limit(args.max_memory)

    only = [v.strip() for v in args.only.split(",") if v.strip()] if args.only else None
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
    # A detector that errored did not get to verify the document, so a sub-threshold
    # result is "incomplete", not "clean" — fail the gate unless explicitly told not to.
    if report.detector_errors and not args.no_fail_on_error:
        return _EXIT_INCOMPLETE
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

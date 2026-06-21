"""Output formatting, kept separate from detection.

``to_json`` is the stable contract that the future MCP server / web frontend will
consume. ``format_cli`` is the human view. Neither contains detection logic.
"""

from __future__ import annotations

import json

from .model import Report, Severity

_COLORS = {
    Severity.CRITICAL: "\033[1;37;41m",  # white on red
    Severity.HIGH: "\033[1;31m",          # bright red
    Severity.MEDIUM: "\033[1;33m",        # yellow
    Severity.LOW: "\033[36m",             # cyan
    Severity.INFO: "\033[90m",            # grey
}
_RESET = "\033[0m"
_BOLD = "\033[1m"


def to_json(report: Report, indent: int = 2) -> str:
    return json.dumps(report.to_dict(), indent=indent, ensure_ascii=False)


def _c(text: str, code: str, color: bool) -> str:
    return f"{code}{text}{_RESET}" if color else text


def format_cli(report: Report, color: bool = True) -> str:
    lines: list[str] = []
    lines.append(_c(f"PDF redaction audit: {report.path}", _BOLD, color))

    worst = report.worst_severity
    if worst is None:
        lines.append(_c("  No findings. Nothing recoverable was detected.", _COLORS[Severity.INFO], color))
    else:
        lines.append(
            f"  {len(report.findings)} finding(s); worst severity: "
            + _c(worst.label.upper(), _COLORS[worst], color)
        )

    lines.append("")
    for f in report.by_severity():
        tag = _c(f" {f.severity.label.upper():^8} ", _COLORS[f.severity], color)
        loc = f" p{f.page}" if f.page else ""
        lines.append(f"{tag} [{f.vector}{loc}] {f.description}")
        if f.evidence:
            ev = f.evidence.replace("\n", " ")
            if len(ev) > 240:
                ev = ev[:240] + " ..."
            lines.append(_c(f"           recovered: {ev}", _BOLD, color))
        if f.recommendation:
            lines.append(_c(f"           fix: {f.recommendation}", _COLORS[Severity.INFO], color))
        lines.append("")

    if report.detector_errors:
        lines.append(_c("Detector errors (scan continued):", _COLORS[Severity.LOW], color))
        for name, err in report.detector_errors.items():
            lines.append(f"  - {name}: {err}")

    return "\n".join(lines)

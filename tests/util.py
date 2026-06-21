"""Small helpers for asserting against Report objects."""

from pdfaudit.model import Report, Severity

# Vectors that represent an actual content leak (as opposed to informational
# metadata). Clean controls must never produce any of these.
LEAK_VECTORS = {
    "covered_text",
    "hidden_text",
    "revision_history",
    "embedded_files",
    "redact_annotations",
}


def findings_for(report: Report, vector: str):
    return [f for f in report.findings if f.vector == vector]


def vectors(report: Report) -> set[str]:
    return {f.vector for f in report.findings}


def evidence_blob(report: Report, vector: str) -> str:
    return " ".join((f.evidence or "") for f in findings_for(report, vector))


def max_severity_for(report: Report, vector: str) -> Severity | None:
    fs = findings_for(report, vector)
    return max((f.severity for f in fs), default=None)

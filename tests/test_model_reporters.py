"""Model + reporter unit tests."""

import json

from pdfaudit.model import Finding, Report, Severity
from pdfaudit.reporters import to_json, format_cli


def _sample_report() -> Report:
    r = Report(path="x.pdf")
    r.add(Finding(vector="metadata", severity=Severity.INFO, description="info"))
    r.add(Finding(vector="covered_text", severity=Severity.CRITICAL,
                  description="leak", page=1, evidence="SSN 123-45-6789"))
    r.add(Finding(vector="embedded_files", severity=Severity.HIGH, description="attach"))
    return r


def test_severity_ordering_and_labels():
    assert Severity.CRITICAL > Severity.HIGH > Severity.MEDIUM > Severity.LOW > Severity.INFO
    assert Severity.from_label("high") is Severity.HIGH
    assert Severity.HIGH.label == "high"


def test_worst_severity_and_sorting():
    r = _sample_report()
    assert r.worst_severity is Severity.CRITICAL
    ordered = r.by_severity()
    assert ordered[0].severity is Severity.CRITICAL
    assert ordered[-1].severity is Severity.INFO


def test_empty_report_has_no_worst_severity():
    assert Report(path="x.pdf").worst_severity is None


def test_count_with_threshold():
    r = _sample_report()
    assert r.count(Severity.HIGH) == 2  # critical + high
    assert r.count(Severity.INFO) == 3


def test_to_json_is_valid_and_complete():
    r = _sample_report()
    data = json.loads(to_json(r))
    assert data["worst_severity"] == "critical"
    assert data["finding_count"] == 3
    assert data["findings"][0]["severity"] == "critical"
    # findings are ordered worst-first in the serialized form too
    assert [f["severity"] for f in data["findings"]] == ["critical", "high", "info"]


def test_cli_report_includes_recovered_evidence():
    r = _sample_report()
    text = format_cli(r, color=False)
    assert "SSN 123-45-6789" in text
    assert "covered_text" in text
    assert "CRITICAL" in text


def test_cli_report_handles_empty_report():
    text = format_cli(Report(path="x.pdf"), color=False)
    assert "No findings" in text

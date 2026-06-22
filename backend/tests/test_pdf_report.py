"""The summary-PDF renderer must not stamp 'CLEAN' on a partial (errored) scan."""
from __future__ import annotations

import io

from pdfminer.high_level import extract_text

from pdfaudit import Report, Severity
from pdfaudit.model import Finding

from app.services.pdf_report import render_report_pdf


def _text(report: Report) -> str:
    return extract_text(io.BytesIO(render_report_pdf(report)))


def test_pdf_stamps_partial_when_a_detector_errored():
    r = Report(path="x.pdf")
    r.detector_errors["covered_text"] = "PDFSyntaxError: boom"
    text = _text(r)
    assert "PARTIAL" in text
    assert "CLEAN" not in text  # an errored scan is not clean


def test_pdf_stamps_clean_when_no_findings_and_no_errors():
    r = Report(path="x.pdf")
    text = _text(r)
    assert "CLEAN" in text


def test_pdf_stamps_worst_severity_when_findings_present():
    r = Report(path="x.pdf")
    r.add(Finding(vector="covered_text", severity=Severity.CRITICAL, description="d"))
    text = _text(r)
    assert "CRITICAL" in text

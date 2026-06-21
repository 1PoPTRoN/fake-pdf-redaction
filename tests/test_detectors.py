"""Per-detector behaviour against the fixture corpus.

Each leaky fixture must (1) fire the expected detector, (2) at the expected
severity, and (3) surface the planted secret as evidence. Clean controls must
never fire a leak vector.
"""

import pytest

from pdfaudit.model import Severity
import util

# fixture name -> (vector, minimum severity, [tokens that must appear in evidence])
LEAK_EXPECTATIONS = {
    "box_over_text": ("covered_text", Severity.CRITICAL, ["123-45-6789"]),
    "invisible_text": ("hidden_text", Severity.CRITICAL, ["Robert", "4242"]),
    "incremental_redaction": ("revision_history", Severity.CRITICAL, ["4200000", "Acme"]),
    "embedded_file": ("embedded_files", Severity.HIGH, ["payroll.csv"]),
    "metadata_leak": ("metadata", Severity.MEDIUM, ["Jane Insider", "SEALED-2026-00042"]),
    "unapplied_redact": ("redact_annotations", Severity.CRITICAL, ["REDACTED"]),
}


@pytest.mark.parametrize("fixture_name", sorted(LEAK_EXPECTATIONS))
def test_leak_is_detected(engine, corpus, fixture_name):
    vector, min_sev, tokens = LEAK_EXPECTATIONS[fixture_name]
    report = engine.scan(corpus[fixture_name])

    fs = util.findings_for(report, vector)
    assert fs, f"{fixture_name}: expected a {vector} finding, got vectors {util.vectors(report)}"

    assert util.max_severity_for(report, vector) >= min_sev, (
        f"{fixture_name}: {vector} severity below {min_sev.label}"
    )

    blob = util.evidence_blob(report, vector)
    for tok in tokens:
        assert tok in blob, f"{fixture_name}: evidence missing '{tok}'. Got: {blob!r}"


@pytest.mark.parametrize("fixture_name", sorted(LEAK_EXPECTATIONS))
def test_no_detector_errors_on_leaky_fixtures(engine, corpus, fixture_name):
    report = engine.scan(corpus[fixture_name])
    assert report.detector_errors == {}, f"detector errors: {report.detector_errors}"


def test_clean_stripped_has_zero_findings(engine, corpus):
    report = engine.scan(corpus["clean_stripped"])
    assert report.findings == [], f"expected zero findings, got {util.vectors(report)}"
    assert report.worst_severity is None


def test_clean_simple_has_no_meaningful_findings(engine, corpus):
    """An ordinary doc may carry INFO software metadata but nothing higher,
    and must not trip any leak vector (false-positive protection)."""
    report = engine.scan(corpus["clean_simple"])
    assert not (util.vectors(report) & util.LEAK_VECTORS), (
        f"clean control tripped leak vectors: {util.vectors(report) & util.LEAK_VECTORS}"
    )
    worst = report.worst_severity
    assert worst is None or worst <= Severity.INFO, (
        f"clean control produced {worst.label if worst else None}-level finding"
    )


@pytest.mark.parametrize("clean_name", ["clean_simple", "clean_stripped"])
def test_clean_controls_never_fire_leak_vectors(engine, corpus, clean_name):
    report = engine.scan(corpus[clean_name])
    assert not (util.vectors(report) & util.LEAK_VECTORS)


def test_box_over_text_does_not_falsely_report_revisions(engine, corpus):
    """Cross-contamination guard: a single-revision file with a box must not
    produce revision_history findings."""
    report = engine.scan(corpus["box_over_text"])
    assert util.findings_for(report, "revision_history") == []

"""Engine-level behaviour: isolation, filtering, registry."""

from pdfaudit import Engine, default_detectors
from pdfaudit.detectors.base import Detector
import util


class _BoomDetector(Detector):
    name = "boom"

    def analyze(self, doc):
        raise RuntimeError("kaboom")


def test_broken_detector_does_not_sink_the_scan(corpus):
    """Stability: a detector that raises is isolated; the rest still run and the
    error is recorded rather than propagated."""
    engine = Engine(default_detectors() + [_BoomDetector()])
    report = engine.scan(corpus["box_over_text"])

    assert "boom" in report.detector_errors
    assert "kaboom" in report.detector_errors["boom"]
    # Other detectors still produced their findings.
    assert util.findings_for(report, "covered_text")


def test_only_filter_restricts_detectors(engine, corpus):
    report = engine.scan(corpus["box_over_text"], only=["covered_text"])
    assert util.vectors(report) == {"covered_text"}


def test_available_vectors_lists_all_defaults(engine):
    vectors = set(engine.available_vectors())
    assert {
        "covered_text",
        "hidden_text",
        "revision_history",
        "embedded_files",
        "metadata",
        "redact_annotations",
    } <= vectors


def test_scan_is_repeatable(engine, corpus):
    a = engine.scan(corpus["incremental_redaction"])
    b = engine.scan(corpus["incremental_redaction"])
    assert a.to_dict() == b.to_dict()

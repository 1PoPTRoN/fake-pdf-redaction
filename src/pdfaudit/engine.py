"""The scan engine: run every detector against one document, aggregate findings.

Stability is a first-class goal here. Each detector runs inside its own
try/except so a single malformed-PDF edge case in one detector degrades to a
recorded ``detector_errors`` entry instead of crashing the whole scan. A partial
report is far more useful than a stack trace.
"""

from __future__ import annotations

from .document import PDFDocument
from .detectors.base import Detector
from .detectors.covered_text import CoveredTextDetector
from .detectors.hidden_text import HiddenTextDetector
from .detectors.revision_history import RevisionHistoryDetector
from .detectors.embedded_files import EmbeddedFileDetector
from .detectors.metadata import MetadataDetector
from .detectors.redact_annotations import RedactAnnotationDetector
from .model import Report


def default_detectors() -> list[Detector]:
    """The v1 detector set: Tier A (covered/hidden/revision) + Tier B."""
    return [
        CoveredTextDetector(),
        HiddenTextDetector(),
        RevisionHistoryDetector(),
        EmbeddedFileDetector(),
        MetadataDetector(),
        RedactAnnotationDetector(),
    ]


class Engine:
    def __init__(self, detectors: list[Detector] | None = None):
        self.detectors = detectors if detectors is not None else default_detectors()

    def available_vectors(self) -> list[str]:
        return [d.name for d in self.detectors]

    def scan(self, path: str, only: list[str] | None = None) -> Report:
        report = Report(path=path)
        with PDFDocument(path) as doc:
            for detector in self.detectors:
                if only and detector.name not in only:
                    continue
                try:
                    for finding in detector.analyze(doc):
                        report.add(finding)
                except Exception as exc:  # isolation: one detector can't sink the scan
                    report.detector_errors[detector.name] = f"{type(exc).__name__}: {exc}"
        return report

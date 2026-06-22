"""The scan engine: run every detector against one document, aggregate findings.

Stability is a first-class goal here. Each detector runs inside its own
try/except so a single malformed-PDF edge case in one detector degrades to a
recorded ``detector_errors`` entry instead of crashing the whole scan. A partial
report is far more useful than a stack trace.
"""

from __future__ import annotations

import contextlib
import os
import signal
import threading

from .document import PDFDocument
from .detectors.base import Detector
from .detectors.covered_text import CoveredTextDetector
from .detectors.hidden_text import HiddenTextDetector
from .detectors.revision_history import RevisionHistoryDetector
from .detectors.embedded_files import EmbeddedFileDetector
from .detectors.metadata import MetadataDetector
from .detectors.redact_annotations import RedactAnnotationDetector
from .model import Report

#: Default wall-clock budget per detector. Hostile PDFs can drive a detector into a
#: pathological (or non-terminating) state; the engine's try/except cannot catch a
#: hang, only an exception, so we convert "too slow" into a catchable TimeoutError.
DEFAULT_DETECTOR_TIMEOUT = float(os.environ.get("PDFAUDIT_DETECTOR_TIMEOUT", "60"))


@contextlib.contextmanager
def _time_limit(seconds: float):
    """Best-effort wall-clock limit using SIGALRM.

    Only active on the main thread of a platform with SIGALRM (the CLI path). It
    interrupts at the next Python bytecode boundary, so a pure C-level hang (e.g.
    inside a decompressor) may still run over — full containment needs an OS-level
    rlimit/sandbox, which the CLI exposes via ``--max-memory``. A no-op elsewhere
    (e.g. worker threads, Windows) so tests and library use are unaffected.
    """
    if (
        not seconds
        or seconds <= 0
        or not hasattr(signal, "SIGALRM")
        or threading.current_thread() is not threading.main_thread()
    ):
        yield
        return

    def _handler(signum, frame):
        raise TimeoutError(f"detector exceeded {seconds:g}s time limit")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _sanitize_error(exc: Exception) -> str:
    """Record exception type + a short, single-line message.

    The full message can embed object/byte fragments from the document (the very
    content we handle carefully) and is rarely useful in a report. Set
    ``PDFAUDIT_DEBUG`` to keep the untruncated message for debugging.
    """
    msg = str(exc)
    if not os.environ.get("PDFAUDIT_DEBUG"):
        msg = " ".join(msg.split())[:200]
    return f"{type(exc).__name__}: {msg}"


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
    def __init__(
        self,
        detectors: list[Detector] | None = None,
        detector_timeout: float = DEFAULT_DETECTOR_TIMEOUT,
    ):
        self.detectors = detectors if detectors is not None else default_detectors()
        self.detector_timeout = detector_timeout

    def available_vectors(self) -> list[str]:
        return [d.name for d in self.detectors]

    def scan(self, path: str, only: list[str] | None = None) -> Report:
        report = Report(path=path)
        with PDFDocument(path) as doc:
            for detector in self.detectors:
                if only and detector.name not in only:
                    continue
                try:
                    with _time_limit(self.detector_timeout):
                        for finding in detector.analyze(doc):
                            report.add(finding)
                # isolation: one detector (exception, timeout, or even a recoverable
                # MemoryError from --max-memory) can't sink the scan. The CLI treats a
                # non-empty detector_errors as a failed gate so this never reads "clean".
                except Exception as exc:
                    report.detector_errors[detector.name] = _sanitize_error(exc)
        return report

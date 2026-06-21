"""Base class for all leak detectors.

A detector is a small, isolated unit with one job and a uniform interface:
``analyze(doc) -> list[Finding]``. This is what makes the system testable and
extensible — Tier C vectors are added by writing one more subclass, and the
engine treats every detector identically.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..document import PDFDocument
from ..model import Finding


class Detector(ABC):
    #: Stable machine name used in JSON output and the ``--only`` CLI flag.
    name: str = "detector"

    @abstractmethod
    def analyze(self, doc: PDFDocument) -> list[Finding]:
        """Inspect the document and return zero or more findings."""
        raise NotImplementedError

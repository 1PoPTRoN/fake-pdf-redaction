"""Detect unapplied redaction annotations and text-bearing annotations.

In Acrobat-style workflows you first *mark* content with ``/Redact`` annotations
and then *apply* them, which is the step that actually removes the content. A
``/Redact`` annotation still present in the file means the redaction was marked
but (most likely) never applied — the underlying content is still there, and the
annotation may even store the intended overlay text. We flag those CRITICAL.

We also surface ordinary annotations that carry text in ``/Contents`` (sticky
notes, comments), which can leak commentary, as INFO.
"""

from __future__ import annotations

from .base import Detector
from ..document import PDFDocument
from ..model import Finding, Severity


def _annot_text(annot) -> str | None:
    for key in ("/OverlayText", "/Contents", "/RC"):
        try:
            val = annot.get(key)
        except Exception:
            val = None
        if val is not None:
            s = str(val).strip()
            if s:
                return s
    return None


class RedactAnnotationDetector(Detector):
    name = "redact_annotations"

    def analyze(self, doc: PDFDocument) -> list[Finding]:
        findings: list[Finding] = []
        for page_index, page in enumerate(doc.pdf.pages, start=1):
            try:
                annots = page.get("/Annots")
            except Exception:
                annots = None
            if annots is None:
                continue
            for annot in annots:
                try:
                    subtype = str(annot.get("/Subtype"))
                except Exception:
                    continue
                text = _annot_text(annot)
                if subtype == "/Redact":
                    findings.append(
                        Finding(
                            vector=self.name,
                            severity=Severity.CRITICAL,
                            page=page_index,
                            evidence=text or "(no overlay text)",
                            description=(
                                "An unapplied /Redact annotation is present. Redaction was "
                                "marked but not applied, so the content under the mark is "
                                "still in the document."
                            ),
                            recommendation=(
                                "Apply (commit) the redaction so the underlying content is "
                                "removed, then re-verify. Marking is not removing."
                            ),
                        )
                    )
                elif text:
                    findings.append(
                        Finding(
                            vector=self.name,
                            severity=Severity.INFO,
                            page=page_index,
                            evidence=f"{subtype}: {text[:200]}",
                            description=(
                                f"A {subtype} annotation carries text content, which is "
                                f"retained independently of the page body."
                            ),
                            recommendation="Remove annotation text if it is sensitive.",
                        )
                    )
        return findings

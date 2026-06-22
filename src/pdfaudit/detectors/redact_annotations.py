"""Detect unapplied redaction annotations and text-bearing annotations.

In Acrobat-style workflows you first *mark* content with ``/Redact`` annotations
and then *apply* them, which is the step that actually removes the content. A
``/Redact`` annotation still present means the redaction was marked but (most
likely) never applied — the underlying content is still there.

For each such annotation we recover the *real* leaked content, in priority order:
the page text geometrically under the annotation's ``/Rect`` (what the redaction
was meant to remove), then the annotation's own stored ``/Contents``/``/RC`` (which
often restates the secret), and only last the ``/OverlayText`` placeholder. The
earlier version emitted just the placeholder, which is proof a redaction is
unapplied but is not the recovered secret.

We also surface ordinary annotations that carry text in ``/Contents`` (sticky
notes, comments) as INFO.
"""

from __future__ import annotations

from .base import Detector
from ..document import PDFDocument, iter_chars, overlap_ratio
from ..model import Finding, Severity

_MIN_OVERLAP = 0.30


def _annot_texts(annot) -> list[tuple[str, str]]:
    """Stored annotation text, content-first (placeholder last)."""
    out: list[tuple[str, str]] = []
    for key in ("/Contents", "/RC", "/OverlayText"):
        try:
            val = annot.get(key)
        except Exception:
            val = None
        if val is not None:
            s = str(val).strip()
            if s:
                out.append((key.lstrip("/"), s))
    return out


def _normalised_rect(annot):
    try:
        r = annot.get("/Rect")
        if r is not None and len(r) == 4:
            x0, y0, x1, y1 = (float(r[i]) for i in range(4))
            return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    except Exception:
        pass
    return None


def _text_under_rect(doc: PDFDocument, page_index: int, rect) -> str:
    if rect is None:
        return ""
    try:
        pages = doc.layout_pages()
    except Exception:
        return ""
    if not (1 <= page_index <= len(pages)):
        return ""
    chars = [
        c for c in iter_chars(pages[page_index - 1])
        if c.get_text().strip() and overlap_ratio(c.bbox, rect) >= _MIN_OVERLAP
    ]
    chars.sort(key=lambda c: (-c.bbox[1], c.bbox[0]))
    return "".join(c.get_text() for c in chars).strip()


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
                stored = _annot_texts(annot)
                if subtype == "/Redact":
                    under = _text_under_rect(doc, page_index, _normalised_rect(annot))
                    parts = []
                    if under:
                        parts.append(f"under redaction: {under}")
                    parts.extend(f"{field}: {text}" for field, text in stored)
                    evidence = " | ".join(parts) if parts else "(no recoverable text)"
                    findings.append(
                        Finding(
                            vector=self.name,
                            severity=Severity.CRITICAL,
                            page=page_index,
                            evidence=evidence,
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
                elif stored:
                    field, text = stored[0]
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

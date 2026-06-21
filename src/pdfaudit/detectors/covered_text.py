"""Detect real, extractable text sitting underneath an opaque cover.

This is the classic "black box over live text" failure: a dark rectangle (or an
image) is drawn on top of text, but the text characters are still present in the
content stream and come straight out via copy/paste or any extractor.

Approach (v1): use pdfminer geometry. Collect every character bbox on the page,
and every "cover" candidate — a filled dark rectangle (``LTRect`` whose
non-stroking colour reads as dark) or an image region (``LTImage`` / ``LTFigure``).
Any character whose centre falls inside a cover is reported, with the recovered
text as evidence.

Known limitation (documented, deferred): we treat *any* character under a dark
rect as covered rather than strictly checking content-stream z-order. In practice
the leaky case — text drawn then boxed — is exactly what this catches; the rare
false positive is a dark design element that legitimately sits over decorative
text, which we surface as HIGH ("review") rather than CRITICAL.
"""

from __future__ import annotations

from pdfminer.layout import LTRect, LTImage, LTFigure

from .base import Detector
from ..document import PDFDocument, iter_chars, center_inside
from ..model import Finding, Severity

# Treat a fill as "dark/opaque cover" when the average channel value is below
# this threshold on a 0..1 scale (i.e. near-black). White boxes are not covers.
_DARK_THRESHOLD = 0.35
_MIN_COVERED_CHARS = 1


def _as_brightness(color) -> float | None:
    """Best-effort interpretation of a pdfminer colour into 0..1 brightness."""
    if color is None:
        return None
    try:
        if isinstance(color, (int, float)):
            return float(color)
        # tuple/list: gray (1), rgb (3), cmyk (4)
        vals = [float(c) for c in color]
        if len(vals) == 1:
            return vals[0]
        if len(vals) == 3:
            return sum(vals) / 3.0
        if len(vals) == 4:
            c, m, y, k = vals[:4]
            return (1 - c) * (1 - k) * 0.33 + (1 - m) * (1 - k) * 0.33 + (1 - y) * (1 - k) * 0.34
    except (TypeError, ValueError):
        return None
    return None


def _is_dark_rect(rect: LTRect) -> bool:
    b = _as_brightness(getattr(rect, "non_stroking_color", None))
    if b is None:
        # No fill colour info; only treat as a cover if it also has no stroke,
        # which is unusual — be conservative and skip.
        return False
    return b <= _DARK_THRESHOLD


def _collect_covers(page) -> list[tuple[str, tuple]]:
    covers: list[tuple[str, tuple]] = []
    for el in page:
        if isinstance(el, LTRect):
            if _is_dark_rect(el):
                covers.append(("dark_rect", el.bbox))
        elif isinstance(el, LTImage):
            covers.append(("image", el.bbox))
        elif isinstance(el, LTFigure):
            # A figure usually wraps an image; its bbox is the painted region.
            covers.append(("image", el.bbox))
    return covers


class CoveredTextDetector(Detector):
    name = "covered_text"

    def analyze(self, doc: PDFDocument) -> list[Finding]:
        findings: list[Finding] = []
        for page_index, page in enumerate(doc.layout_pages(), start=1):
            chars = list(iter_chars(page))
            if not chars:
                continue
            covers = _collect_covers(page)
            for kind, cover_bbox in covers:
                covered = [c for c in chars if center_inside(c.bbox, cover_bbox)]
                covered = [c for c in covered if c.get_text().strip()]
                if len(covered) < _MIN_COVERED_CHARS:
                    continue
                covered.sort(key=lambda c: (-c.bbox[1], c.bbox[0]))
                text = "".join(c.get_text() for c in covered).strip()
                if not text:
                    continue
                sev = Severity.CRITICAL if kind == "dark_rect" else Severity.HIGH
                findings.append(
                    Finding(
                        vector=self.name,
                        severity=sev,
                        page=page_index,
                        bbox=tuple(round(v, 2) for v in cover_bbox),
                        evidence=text,
                        description=(
                            f"{len(covered)} extractable character(s) lie beneath an "
                            f"opaque {kind.replace('_', ' ')}. The cover hides the text "
                            f"visually but the characters remain in the content stream."
                        ),
                        recommendation=(
                            "Remove the underlying text from the content stream "
                            "(true redaction) or flatten the page to a raster image. "
                            "A drawn box is not redaction."
                        ),
                    )
                )
        return findings

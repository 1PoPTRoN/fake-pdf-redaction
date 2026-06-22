"""Detect real, extractable text sitting underneath an opaque cover.

This is the classic "black box over live text" failure: a rectangle (or an image)
is drawn on top of text, but the text characters are still present in the content
stream and come straight out via copy/paste or any extractor.

Approach (v1): use pdfminer geometry. Collect every character bbox on the page and
every "cover" candidate, then report any character whose box meaningfully overlaps
a cover, with the recovered text as evidence.

A cover is any *filled* rectangle (``LTRect`` with ``fill=True``) or image region
(``LTImage`` / ``LTFigure``) at any depth in the layout tree. Crucially the test is
*opacity, not darkness*: a white, grey, yellow, or Separation/pattern-filled box
hides text just as well as a black one, so all of them are covers. Darkness only
chooses the severity — a dark box is the unambiguous "redaction black box"
(CRITICAL); any other opaque cover is flagged for review (HIGH).

Known limitation (documented, deferred): we treat geometric coverage rather than
strictly checking content-stream z-order, and pdfminer does not expose per-element
constant alpha (``ca``/``CA``), so a fully transparent overlay would be flagged.
Both are the safe direction for an auditor (a false positive beats a missed leak)
and are resolved by the roadmap render-and-sample pass (spec v1.3).
"""

from __future__ import annotations

from pdfminer.layout import LTRect, LTImage, LTFigure, LTContainer

from .base import Detector
from ..document import PDFDocument, iter_chars, overlap_ratio, bbox_area, color_brightness
from ..model import Finding, Severity

# A fill counts as a "dark / classic redaction" cover (CRITICAL rather than HIGH)
# when its average channel value is at/below this threshold on a 0..1 scale.
_DARK_THRESHOLD = 0.35
# Minimum fraction of a glyph's area that must lie under a cover to count it. Using
# overlap (not centre-containment) so partially-covered glyphs are not missed.
_MIN_OVERLAP = 0.30
_MIN_COVERED_CHARS = 1
# A *non-dark* cover larger than this fraction of the page is almost certainly a
# background fill or watermark, not a localised redaction, so we skip it to avoid
# flagging every glyph on the page. Dark covers are never skipped (a full-page
# blackout that still leaks text is a genuine critical leak).
_MAX_COVER_PAGE_FRACTION = 0.80


def _iter_covers(obj):
    """Yield ``(kind, bbox, brightness)`` cover candidates at any depth.

    ``kind`` is ``"rect"`` or ``"image"``; ``brightness`` is 0..1 or ``None`` when
    the fill colour space can't be reduced to a brightness (e.g. Pattern, Separation
    or an ICC space) — such a fill is still an opaque cover, just not provably dark.
    """
    if isinstance(obj, LTRect):
        # Only *filled* rectangles cover anything; a stroked-only outline does not.
        if getattr(obj, "fill", False):
            yield ("rect", obj.bbox, color_brightness(getattr(obj, "non_stroking_color", None)))
        return
    if isinstance(obj, LTImage):
        yield ("image", obj.bbox, None)
        return
    if isinstance(obj, LTFigure):
        # A figure wraps a form/image XObject. Recurse to find rects/images painted
        # inside it (e.g. a dark rect drawn within a Form XObject); if it surfaces
        # nothing, treat the whole figure region as an opaque image cover.
        found = False
        for child in obj:
            for cov in _iter_covers(child):
                found = True
                yield cov
        if not found:
            yield ("image", obj.bbox, None)
        return
    if isinstance(obj, LTContainer):
        for child in obj:
            yield from _iter_covers(child)


def _cover_severity(kind: str, brightness: float | None) -> tuple[Severity, str]:
    if kind == "rect" and brightness is not None and brightness <= _DARK_THRESHOLD:
        return Severity.CRITICAL, "dark rectangle"
    if kind == "rect":
        return Severity.HIGH, "rectangle"
    return Severity.HIGH, "image"


class CoveredTextDetector(Detector):
    name = "covered_text"

    def analyze(self, doc: PDFDocument) -> list[Finding]:
        findings: list[Finding] = []
        for page_index, page in enumerate(doc.layout_pages(), start=1):
            chars = list(iter_chars(page))
            if not chars:
                continue
            page_area = bbox_area(page.bbox)
            covers = list(_iter_covers(page))
            for kind, cover_bbox, brightness in covers:
                sev, label = _cover_severity(kind, brightness)
                # A large non-dark cover is a background/watermark, not a redaction.
                if sev is not Severity.CRITICAL and page_area > 0:
                    if bbox_area(cover_bbox) / page_area > _MAX_COVER_PAGE_FRACTION:
                        continue
                covered = [
                    c for c in chars
                    if c.get_text().strip()
                    and overlap_ratio(c.bbox, cover_bbox) >= _MIN_OVERLAP
                ]
                if len(covered) < _MIN_COVERED_CHARS:
                    continue
                covered.sort(key=lambda c: (-c.bbox[1], c.bbox[0]))
                text = "".join(c.get_text() for c in covered).strip()
                if not text:
                    continue
                findings.append(
                    Finding(
                        vector=self.name,
                        severity=sev,
                        page=page_index,
                        bbox=tuple(round(v, 2) for v in cover_bbox),
                        evidence=text,
                        description=(
                            f"{len(covered)} extractable character(s) lie beneath an "
                            f"opaque {label}. The cover hides the text visually but the "
                            f"characters remain in the content stream."
                        ),
                        recommendation=(
                            "Remove the underlying text from the content stream "
                            "(true redaction) or flatten the page to a raster image. "
                            "A drawn box is not redaction."
                        ),
                    )
                )
        return findings

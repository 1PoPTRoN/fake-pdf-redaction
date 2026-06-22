"""Detect text that renders to nothing yet remains fully extractable.

Two independent channels of invisibility:

1. **Invisible render mode** (``Tr 3`` = neither fill nor stroke, ``Tr 7`` = add to
   clip only). We walk the page content stream with pikepdf, maintaining a proper
   ``q``/``Q`` graphics-state stack for the render mode and recursing into Form
   XObjects invoked by ``Do`` (with a cycle guard). The actual strings shown while
   invisible are captured as *scoped* evidence — only the hidden text, not the whole
   page.

2. **Visually invisible glyphs** (from pdfminer geometry): text whose fill colour
   matches the background (e.g. white-on-white), text at a near-zero font size, and
   text positioned outside the page boundary. All are extractable but render to
   nothing, and none involve an invisible render mode, so channel 1 would miss them.
"""

from __future__ import annotations

import pikepdf

from .base import Detector
from ..document import PDFDocument, iter_chars, overlap_ratio, color_brightness
from ..model import Finding, Severity

_INVISIBLE_MODES = {3, 7}
_SHOW_OPS = {"Tj", "TJ", "'", '"'}
_MAX_XOBJECT_DEPTH = 12

# A glyph fill at/above this brightness is treated as "white" (assumed white page).
_WHITE_THRESHOLD = 0.95
# A dark fill underneath white text means it is actually visible (white-on-dark).
_DARK_THRESHOLD = 0.35
# Font sizes at/below this (points) render to effectively nothing.
_MIN_VISIBLE_SIZE = 0.5
_EVIDENCE_CAP = 400


def _decode_pdf_string(b: bytes) -> str:
    if b[:2] == b"\xfe\xff":
        try:
            return b[2:].decode("utf-16-be", "replace")
        except Exception:
            pass
    return b.decode("latin-1", "replace")


def _shown_bytes(operands) -> bytes:
    """Concatenate the literal string bytes from a text-show operator's operands.

    Handles ``Tj``/``'``/``"`` (a single string, possibly preceded by spacing
    numbers) and ``TJ`` (an array of strings and kerning numbers).
    """
    out: list[bytes] = []
    for o in operands:
        if isinstance(o, pikepdf.String):
            out.append(bytes(o))
        elif isinstance(o, pikepdf.Array):
            for e in o:
                if isinstance(e, pikepdf.String):
                    out.append(bytes(e))
    return b"".join(out)


def _resolve_form_xobject(resources, name):
    if resources is None:
        return None
    try:
        xobjs = resources.get("/XObject")
        if xobjs is None:
            return None
        xo = xobjs.get(str(name))
    except Exception:
        return None
    if xo is None:
        return None
    try:
        if str(xo.get("/Subtype")) == "/Form":
            return xo
    except Exception:
        return None
    return None


def _scan_stream(stream_obj, resources, render_mode, depth, visited, acc) -> None:
    """Accumulate invisible-mode show ops and their text from one content stream."""
    try:
        instructions = pikepdf.parse_content_stream(stream_obj)
    except Exception:
        return

    stack: list[int] = []
    mode = render_mode
    for instr in instructions:
        operator = str(instr.operator)
        operands = instr.operands
        if operator == "q":
            stack.append(mode)
        elif operator == "Q":
            if stack:
                mode = stack.pop()
        elif operator == "Tr" and operands:
            try:
                mode = int(operands[0])
            except (TypeError, ValueError):
                pass
        elif operator in _SHOW_OPS:
            if mode in _INVISIBLE_MODES:
                acc["count"] += 1
                shown = _shown_bytes(operands)
                if shown:
                    acc["text"].append(shown)
        elif operator == "Do" and operands and depth < _MAX_XOBJECT_DEPTH:
            xo = _resolve_form_xobject(resources, operands[0])
            if xo is not None:
                key = getattr(xo, "objgen", id(xo))
                if key not in visited:
                    visited.add(key)
                    sub_res = None
                    try:
                        sub_res = xo.get("/Resources")
                    except Exception:
                        sub_res = None
                    _scan_stream(xo, sub_res or resources, mode, depth + 1, visited, acc)


def _dark_region_bboxes(page) -> list[tuple]:
    """Filled near-dark rectangles in the pdfminer layout (a backdrop for text)."""
    from pdfminer.layout import LTRect

    regions = []
    for el in page:
        if isinstance(el, LTRect) and getattr(el, "fill", False):
            b = color_brightness(getattr(el, "non_stroking_color", None))
            if b is not None and b <= _DARK_THRESHOLD:
                regions.append(el.bbox)
    return regions


def _geometry_invisible(page) -> dict[str, list]:
    """Group visually-invisible glyphs by reason (white / tiny / off-page)."""
    reasons: dict[str, list] = {"white": [], "tiny": [], "offpage": []}
    px0, py0, px1, py1 = page.bbox
    dark = _dark_region_bboxes(page)
    for ch in iter_chars(page):
        if not ch.get_text().strip():
            continue
        cx0, cy0, cx1, cy1 = ch.bbox
        if cx1 < px0 or cx0 > px1 or cy1 < py0 or cy0 > py1:
            reasons["offpage"].append(ch)
            continue
        if getattr(ch, "size", 1.0) <= _MIN_VISIBLE_SIZE:
            reasons["tiny"].append(ch)
            continue
        gs = getattr(ch, "graphicstate", None)
        b = color_brightness(getattr(gs, "ncolor", None)) if gs is not None else None
        if b is not None and b >= _WHITE_THRESHOLD:
            # White text sitting on a dark backdrop is actually visible — skip it.
            if not any(overlap_ratio(ch.bbox, r) >= 0.3 for r in dark):
                reasons["white"].append(ch)
    return reasons


_REASON_TEXT = {
    "white": "the same colour as the background (e.g. white-on-white)",
    "tiny": "a near-zero font size",
    "offpage": "a position outside the page boundary",
}


def _join_chars(chars) -> str:
    chars = sorted(chars, key=lambda c: (-c.bbox[1], c.bbox[0]))
    return "".join(c.get_text() for c in chars).strip()


class HiddenTextDetector(Detector):
    name = "hidden_text"

    def analyze(self, doc: PDFDocument) -> list[Finding]:
        findings: list[Finding] = []
        layout_pages = doc.layout_pages()
        for page_index, page in enumerate(doc.pdf.pages, start=1):
            # Channel 1: invisible render mode (Tr 3/7), with scoped evidence.
            acc = {"count": 0, "text": []}
            try:
                resources = page.get("/Resources")
            except Exception:
                resources = None
            _scan_stream(page, resources, 0, 0, set(), acc)
            if acc["count"] > 0:
                shown = _decode_pdf_string(b"".join(acc["text"])).strip()
                evidence = shown[:_EVIDENCE_CAP] if shown else None
                findings.append(
                    Finding(
                        vector=self.name,
                        severity=Severity.CRITICAL,
                        page=page_index,
                        evidence=evidence,
                        description=(
                            f"{acc['count']} text-show operation(s) on this page render in "
                            f"an invisible mode (Tr 3/7). The text is not visible but is "
                            f"fully extractable."
                        ),
                        recommendation=(
                            "If this is an OCR layer over a scan, ensure it contains no "
                            "content meant to be redacted; otherwise remove the invisible "
                            "text from the content stream."
                        ),
                    )
                )

            # Channel 2: visually-invisible glyphs (colour / size / position).
            if page_index - 1 < len(layout_pages):
                hits = {k: v for k, v in _geometry_invisible(layout_pages[page_index - 1]).items() if v}
                if hits:
                    sample = [c for chars in hits.values() for c in chars]
                    evidence = _join_chars(sample)[:_EVIDENCE_CAP] or None
                    parts = [f"{len(v)} character(s) drawn in {_REASON_TEXT[k]}" for k, v in hits.items()]
                    findings.append(
                        Finding(
                            vector=self.name,
                            severity=Severity.CRITICAL,
                            page=page_index,
                            evidence=evidence,
                            description=(
                                "Visually-invisible but extractable text: "
                                + "; ".join(parts)
                                + "."
                            ),
                            recommendation=(
                                "Remove text that is hidden by colour, size, or off-page "
                                "positioning; hiding is not redaction."
                            ),
                        )
                    )
        return findings

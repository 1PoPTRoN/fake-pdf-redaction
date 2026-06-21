"""Detect text painted in an invisible text-rendering mode.

PDF text-rendering mode is set by the ``Tr`` operator. Mode 3 = "neither fill nor
stroke" (invisible), mode 7 = "add to clip, no paint" (also invisible). Scanners
and some redaction tools leave an invisible OCR/text layer that is fully
extractable yet renders to nothing — a leak that the covered-text detector won't
catch because there is no visible cover, just invisible glyphs.

We tokenise the page content stream with pikepdf, track the current text-render
mode across the graphics state, and flag any text-show operator executed while the
mode is invisible. pdfminer text for the page is attached as best-effort evidence.
"""

from __future__ import annotations

import pikepdf

from .base import Detector
from ..document import PDFDocument, iter_chars
from ..model import Finding, Severity

_INVISIBLE_MODES = {3, 7}
_SHOW_OPS = {"Tj", "TJ", "'", '"'}


def _page_invisible_show_count(page) -> int:
    """Number of text-show operations executed under an invisible render mode."""
    try:
        instructions = pikepdf.parse_content_stream(page)
    except Exception:
        return 0

    render_mode = 0
    invisible_shows = 0
    for instr in instructions:
        # pikepdf returns ContentStreamInstruction(.operands, .operator) on
        # current versions; fall back to tuple unpacking just in case.
        try:
            operands = instr.operands
            operator = str(instr.operator)
        except AttributeError:  # pragma: no cover - legacy shape
            operands, op = instr
            operator = str(op)

        if operator == "Tr" and operands:
            try:
                render_mode = int(operands[0])
            except (TypeError, ValueError):
                pass
        elif operator in _SHOW_OPS:
            if render_mode in _INVISIBLE_MODES:
                invisible_shows += 1
    return invisible_shows


class HiddenTextDetector(Detector):
    name = "hidden_text"

    def analyze(self, doc: PDFDocument) -> list[Finding]:
        findings: list[Finding] = []
        layout_pages = doc.layout_pages()
        for page_index, page in enumerate(doc.pdf.pages, start=1):
            count = _page_invisible_show_count(page)
            if count <= 0:
                continue
            # Best-effort recovered text from the matching pdfminer page.
            evidence = None
            if page_index - 1 < len(layout_pages):
                chars = list(iter_chars(layout_pages[page_index - 1]))
                text = "".join(c.get_text() for c in chars).strip()
                if text:
                    evidence = text[:400]
            findings.append(
                Finding(
                    vector=self.name,
                    severity=Severity.CRITICAL,
                    page=page_index,
                    evidence=evidence,
                    description=(
                        f"{count} text-show operation(s) on this page render in an "
                        f"invisible mode (Tr 3/7). The text is not visible but is fully "
                        f"extractable."
                    ),
                    recommendation=(
                        "If this is an OCR layer over a scan, ensure it does not contain "
                        "content meant to be redacted; otherwise remove the invisible "
                        "text from the content stream."
                    ),
                )
            )
        return findings

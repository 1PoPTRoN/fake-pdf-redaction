"""Shared, parse-once document context handed to every detector.

Design note: we keep the *original file bytes* around deliberately. qpdf/pikepdf
normalise a PDF on load, which can collapse the incremental-update structure that
the revision-history detector depends on. So detectors that need structure read
``raw_bytes``; detectors that need the object model use ``pdf`` (pikepdf); and
detectors that need glyph geometry use ``layout_pages()`` (pdfminer.six), which is
parsed lazily and cached.
"""

from __future__ import annotations

import io
import os
import stat
from functools import cached_property
from typing import Iterator, Optional

import pikepdf
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams

#: Hard cap on the input size we will read into memory. PDFs being audited are
#: assumed hostile; without a cap a device/FIFO (``/dev/zero``) or a multi-GB file
#: would hang or exhaust memory before any detector runs. Override via the
#: ``PDFAUDIT_MAX_BYTES`` environment variable.
MAX_PDF_BYTES = int(os.environ.get("PDFAUDIT_MAX_BYTES", str(512 * 1024 * 1024)))


class PDFDocument:
    def __init__(self, path: str):
        self.path = path
        # Refuse anything that is not a *regular* file before opening it. A symlink
        # to a device or a FIFO would otherwise block forever inside read().
        st = os.stat(path)  # raises FileNotFoundError for a missing path
        if not stat.S_ISREG(st.st_mode):
            raise ValueError(f"not a regular file: {path}")
        if st.st_size > MAX_PDF_BYTES:
            raise ValueError(
                f"file too large: {st.st_size} bytes exceeds limit {MAX_PDF_BYTES}"
            )
        with open(path, "rb") as fh:
            # Read one byte past the cap so a file that grows between stat() and
            # read() (or a lying st_size) is still caught rather than truncated.
            self.raw_bytes: bytes = fh.read(MAX_PDF_BYTES + 1)
        if len(self.raw_bytes) > MAX_PDF_BYTES:
            raise ValueError(f"file too large: exceeds limit {MAX_PDF_BYTES} bytes")
        # pikepdf object model. Opened from the bytes we already read so the two
        # views are guaranteed consistent.
        self.pdf: pikepdf.Pdf = pikepdf.open(io.BytesIO(self.raw_bytes))
        self._layout_cache: Optional[list] = None
        self._layout_text: Optional[str] = None

    # -- pikepdf-side convenience ------------------------------------------
    @cached_property
    def page_count(self) -> int:
        return len(self.pdf.pages)

    # -- pdfminer-side convenience -----------------------------------------
    def layout_pages(self) -> list:
        """Return cached pdfminer LTPage objects (one per page)."""
        if self._layout_cache is None:
            self._layout_cache = list(
                extract_pages(io.BytesIO(self.raw_bytes), laparams=LAParams())
            )
        return self._layout_cache

    def layout_text(self) -> str:
        """Current-document text, derived from the cached layout (parsed once).

        Built from :meth:`layout_pages` so detectors needing the current text (e.g.
        revision-history diffing) reuse the single pdfminer pass instead of running
        a second, independent ``extract_text`` over the same bytes.
        """
        if self._layout_text is None:
            parts = []
            for page in self.layout_pages():
                for ch in iter_chars(page):
                    parts.append(ch.get_text())
            self._layout_text = "".join(parts)
        return self._layout_text

    def close(self) -> None:
        try:
            self.pdf.close()
        except Exception:
            pass

    def __enter__(self) -> "PDFDocument":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def iter_chars(lt_obj) -> Iterator:
    """Recursively yield every ``LTChar`` under a pdfminer layout object."""
    from pdfminer.layout import LTChar, LTContainer

    if isinstance(lt_obj, LTChar):
        yield lt_obj
    elif isinstance(lt_obj, LTContainer):
        for child in lt_obj:
            yield from iter_chars(child)


def bbox_center(bbox) -> tuple[float, float]:
    x0, y0, x1, y1 = bbox
    return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def center_inside(inner_bbox, outer_bbox, pad: float = 0.0) -> bool:
    cx, cy = bbox_center(inner_bbox)
    ox0, oy0, ox1, oy1 = outer_bbox
    return (ox0 - pad) <= cx <= (ox1 + pad) and (oy0 - pad) <= cy <= (oy1 + pad)


def bbox_area(b) -> float:
    x0, y0, x1, y1 = b
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def color_brightness(color) -> Optional[float]:
    """Reduce a pdfminer colour (gray / RGB / CMYK) to 0..1 brightness, or ``None``.

    ``None`` means the colour could not be interpreted (e.g. a Pattern/Separation/
    ICC space that pdfminer reports as a name or empty) — callers decide what an
    uninterpretable colour means for their check.
    """
    if color is None:
        return None
    try:
        if isinstance(color, (int, float)):
            return float(color)
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


def overlap_ratio(inner_bbox, outer_bbox) -> float:
    """Fraction of ``inner_bbox``'s area that lies inside ``outer_bbox`` (0..1).

    Used instead of pure centre-containment so a glyph that is only *partially*
    under a cover (e.g. a box drawn slightly small, or covering the top of a line)
    is still recognised — missing such a glyph is a false negative, the worst kind
    of bug for this tool.
    """
    ix0, iy0, ix1, iy1 = inner_bbox
    ox0, oy0, ox1, oy1 = outer_bbox
    inter = (
        max(0.0, min(ix1, ox1) - max(ix0, ox0))
        * max(0.0, min(iy1, oy1) - max(iy0, oy0))
    )
    area = bbox_area(inner_bbox)
    if area <= 0:
        # Degenerate glyph box: fall back to centre-containment.
        return 1.0 if center_inside(inner_bbox, outer_bbox) else 0.0
    return inter / area

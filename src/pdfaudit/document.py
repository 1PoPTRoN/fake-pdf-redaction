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
from functools import cached_property
from typing import Iterator, Optional

import pikepdf
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams


class PDFDocument:
    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as fh:
            self.raw_bytes: bytes = fh.read()
        # pikepdf object model. Opened from the bytes we already read so the two
        # views are guaranteed consistent.
        self.pdf: pikepdf.Pdf = pikepdf.open(io.BytesIO(self.raw_bytes))
        self._layout_cache: Optional[list] = None

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

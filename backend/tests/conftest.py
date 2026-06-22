"""Pytest fixtures: in-memory sample PDFs + shared TestClient."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Make `app` importable when running `pytest` from backend/.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(create_app())


def make_pdf_bytes(title: str = "T", num_pages: int = 2) -> bytes:
    """In-memory valid PDF (no leaks)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(title)
    c.setAuthor("test-fixture")
    for i in range(num_pages):
        c.drawString(72, 720, f"{title} p{i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def make_boxed_pdf_bytes(title: str = "Boxed", secret: str = "SSN123-45-6789") -> bytes:
    """A PDF that draws visible text and then paints a black rectangle
    over it. The covered-text detector should recover the `secret`."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(title)
    c.setFont("Helvetica", 14)
    c.drawString(72, 720, secret)              # visible (extractable) text
    c.setFillColorRGB(0, 0, 0)                 # solid black box
    c.rect(70, 715, 200, 18, fill=1, stroke=0) # covers the secret
    c.showPage()
    c.save()
    return buf.getvalue()


def make_corrupt_pdf_bytes() -> bytes:
    """Bytes that look like a PDF (header present) but are definitively unparseable.

    Deterministic — does not rely on pikepdf failing to *recover* a truncation,
    which can be flaky. No valid xref/trailer, so pikepdf cannot open it."""
    return b"%PDF-1.7\n" + b"not a real pdf body, no xref, no trailer.\n" * 8


def make_encrypted_readable_pdf_bytes(secret: str = "SSN123-45-6789") -> bytes:
    """A PDF encrypted with an OWNER password but an EMPTY user password.

    pikepdf opens this without any password (it is fully readable/auditable) even
    though ``is_encrypted`` is True — the common 'permission-restricted' PDF. It
    must be scanned, not rejected as encrypted."""
    import pikepdf

    pdf = pikepdf.open(io.BytesIO(make_boxed_pdf_bytes("Enc", secret)))
    out = io.BytesIO()
    pdf.save(out, encryption=pikepdf.Encryption(owner="ownerpw", user=""))
    return out.getvalue()


def make_password_protected_pdf_bytes() -> bytes:
    """A PDF that genuinely requires a (user) password to open."""
    import pikepdf

    pdf = pikepdf.open(io.BytesIO(make_pdf_bytes("Locked", 1)))
    out = io.BytesIO()
    pdf.save(out, encryption=pikepdf.Encryption(owner="ownerpw", user="secret"))
    return out.getvalue()


def upload(name: str, data: bytes, content_type: str = "application/pdf") -> list:
    """Build a list with one multipart file part for httpx.

    The /scan endpoints take a single `file` field, so this always returns
    a single-element list — same shape as the merger's helper, just
    hard-coded to field="file".
    """
    return [("file", (name, io.BytesIO(data), content_type))]
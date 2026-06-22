"""Deterministic generators for the test-fixture corpus.

Each function produces a PDF exhibiting exactly ONE leak vector, plus clean
controls that must produce no meaningful findings. Generating fixtures (rather
than committing opaque binaries) keeps tests reproducible and doubles as a demo:
"here is a PDF I planted a leak in; watch the tool recover it."

Run as a script to write the whole corpus to ``tests/fixtures/corpus/``.
"""

from __future__ import annotations

import io
import os
import tempfile

import pikepdf
from reportlab.pdfgen.canvas import Canvas


# --------------------------------------------------------------------------
# Hand-crafted minimal PDF helpers (for the incremental-update fixture, where
# real libraries would normalise away the revision structure we need).
# --------------------------------------------------------------------------
def _stream_obj(num: int, data: bytes) -> bytes:
    return b"%d 0 obj\n<< /Length %d >>\nstream\n" % (num, len(data)) + data + b"\nendstream\nendobj\n"


def _dict_obj(num: int, body: bytes) -> bytes:
    return b"%d 0 obj\n" % num + body + b"\nendobj\n"


SECRET_LINE = b"Settlement amount is 4200000 dollars paid to Acme Holdings"
REDACTED_LINE = b"Settlement amount is [REDACTED] dollars paid to [REDACTED]"


def incremental_redaction() -> bytes:
    """Two revisions: revision 1 holds the secret, revision 2 hides it.

    The secret remains recoverable from the file's revision history.
    """
    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    secret_stream = b"BT\n/F1 14 Tf\n72 700 Td\n(" + SECRET_LINE + b") Tj\nET"
    objs = [
        _dict_obj(1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        _dict_obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        _dict_obj(3, b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                     b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"),
        _stream_obj(4, secret_stream),
        _dict_obj(5, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    ]
    body = header
    offsets: dict[int, int] = {}
    for i, o in enumerate(objs, start=1):
        offsets[i] = len(body)
        body += o
    xref_off = len(body)
    xref = b"xref\n0 6\n0000000000 65535 f \n"
    for i in range(1, 6):
        xref += b"%010d 00000 n \n" % offsets[i]
    trailer = b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref_off
    base = body + xref + trailer

    redacted_stream = b"BT\n/F1 14 Tf\n72 700 Td\n(" + REDACTED_LINE + b") Tj\nET"
    new4_off = len(base)
    upd_obj = _stream_obj(4, redacted_stream)
    new_xref_off = len(base) + len(upd_obj)
    upd_xref = b"xref\n4 1\n%010d 00000 n \n" % new4_off
    upd_trailer = (b"trailer\n<< /Size 6 /Root 1 0 R /Prev %d >>\nstartxref\n%d\n%%%%EOF\n"
                   % (xref_off, new_xref_off))
    return base + upd_obj + upd_xref + upd_trailer


# --------------------------------------------------------------------------
# reportlab-based fixtures
# --------------------------------------------------------------------------
def _blank_identity_meta(c: Canvas) -> None:
    """Clear reportlab's placeholder Author/Title/Subject so a 'clean' control
    is genuinely clean (only benign software/date metadata remains, at INFO)."""
    c.setAuthor("")
    c.setTitle("")
    c.setSubject("")
    c.setKeywords("")


def box_over_text() -> bytes:
    """Visible text with an opaque black rectangle drawn on top of it."""
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(612, 792))
    _blank_identity_meta(c)
    c.setFont("Helvetica", 14)
    c.drawString(72, 700, "Patient SSN 123-45-6789 diagnosis HIV positive")
    # Opaque black rectangle over the same region (text stays in the stream).
    c.setFillColorRGB(0, 0, 0)
    c.rect(70, 694, 360, 22, stroke=0, fill=1)
    c.showPage()
    c.save()
    return buf.getvalue()


def invisible_text() -> bytes:
    """Text drawn in render mode 3 (invisible) — extractable but not visible."""
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(612, 792))
    _blank_identity_meta(c)
    c.setFont("Helvetica", 14)
    c.drawString(72, 740, "Public notice: meeting minutes attached.")
    t = c.beginText(72, 700)
    t.setFont("Helvetica", 14)
    t.setTextRenderMode(3)  # invisible
    t.textLine("Confidential informant name is Robert Paulson badge 4242")
    c.drawText(t)
    c.showPage()
    c.save()
    return buf.getvalue()


def white_box_over_text() -> bytes:
    """An *opaque white* rectangle over live text (the classic 'white-out')."""
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(612, 792))
    _blank_identity_meta(c)
    c.setFont("Helvetica", 14)
    c.drawString(72, 700, "Account 4455-6677 PIN 8899 internal only")
    c.setFillColorRGB(1, 1, 1)  # white, fully opaque — hides the text visually
    c.rect(70, 694, 360, 22, stroke=0, fill=1)
    c.showPage()
    c.save()
    return buf.getvalue()


def white_on_white_text() -> bytes:
    """White text on the (white) page: invisible by colour, fully extractable."""
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(612, 792))
    _blank_identity_meta(c)
    c.setFont("Helvetica", 14)
    c.drawString(72, 740, "Public notice.")  # visible (black)
    c.setFillColorRGB(1, 1, 1)
    c.drawString(72, 700, "Hidden source Maria Vargas code 7788")
    c.showPage()
    c.save()
    return buf.getvalue()


def _base_text_pdf(line: str = "Quarterly public report. Nothing to see here.") -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(612, 792))
    _blank_identity_meta(c)
    c.setFont("Helvetica", 14)
    c.drawString(72, 700, line)
    c.showPage()
    c.save()
    return buf.getvalue()


# --------------------------------------------------------------------------
# pikepdf-based fixtures
# --------------------------------------------------------------------------
def embedded_file() -> bytes:
    """Clean-looking page that secretly embeds a file containing raw data."""
    pdf = pikepdf.open(io.BytesIO(_base_text_pdf()))
    payload = b"name,ssn,salary\nJane Doe,123-45-6789,200000\n"
    tmp = tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False)
    try:
        tmp.write(payload)
        tmp.close()
        fs = pikepdf.AttachedFileSpec.from_filepath(pdf, tmp.name)
        pdf.attachments["payroll.csv"] = fs
    finally:
        os.unlink(tmp.name)
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


def metadata_leak() -> bytes:
    """Clean-looking page whose Info dictionary leaks author/custom fields."""
    pdf = pikepdf.open(io.BytesIO(_base_text_pdf()))
    with pdf.open_metadata() as meta:
        # ensure an XMP packet exists too
        meta["dc:creator"] = ["Jane Insider"]
    pdf.docinfo["/Author"] = "Jane Insider"
    pdf.docinfo["/Title"] = "INTERNAL DRAFT - do not circulate"
    pdf.docinfo[pikepdf.Name("/CaseNumber")] = "SEALED-2026-00042"
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


def unapplied_redact() -> bytes:
    """Page with a /Redact annotation that was marked but never applied."""
    pdf = pikepdf.open(io.BytesIO(_base_text_pdf("Witness statement on file.")))
    page = pdf.pages[0]
    annot = pikepdf.Dictionary(
        Type=pikepdf.Name.Annot,
        Subtype=pikepdf.Name.Redact,
        Rect=pikepdf.Array([100, 690, 300, 712]),
        OverlayText=pikepdf.String("REDACTED"),
        Contents=pikepdf.String("witness identity: Sarah Connor"),
    )
    page.Annots = pikepdf.Array([pdf.make_indirect(annot)])
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


# --------------------------------------------------------------------------
# Clean controls — must NOT produce meaningful findings
# --------------------------------------------------------------------------
def clean_simple() -> bytes:
    """Ordinary single-revision text PDF (may carry only INFO-level metadata)."""
    return _base_text_pdf("This is a perfectly ordinary public document.")


def clean_stripped() -> bytes:
    """As clean_simple but with all metadata removed — expect zero findings."""
    pdf = pikepdf.open(io.BytesIO(clean_simple()))
    for key in list(pdf.docinfo.keys()):
        del pdf.docinfo[key]
    try:
        del pdf.Root.Metadata
    except Exception:
        pass
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


# --------------------------------------------------------------------------
# Registry + corpus writer
# --------------------------------------------------------------------------
LEAKY: dict[str, callable] = {
    "box_over_text": box_over_text,
    "white_box_over_text": white_box_over_text,
    "invisible_text": invisible_text,
    "white_on_white_text": white_on_white_text,
    "incremental_redaction": incremental_redaction,
    "embedded_file": embedded_file,
    "metadata_leak": metadata_leak,
    "unapplied_redact": unapplied_redact,
}
CLEAN: dict[str, callable] = {
    "clean_simple": clean_simple,
    "clean_stripped": clean_stripped,
}
ALL = {**LEAKY, **CLEAN}


def write_corpus(target_dir: str) -> dict[str, str]:
    os.makedirs(target_dir, exist_ok=True)
    paths: dict[str, str] = {}
    for name, fn in ALL.items():
        path = os.path.join(target_dir, f"{name}.pdf")
        with open(path, "wb") as fh:
            fh.write(fn())
        paths[name] = path
    return paths


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "corpus")
    written = write_corpus(out_dir)
    for name, path in written.items():
        print(f"{name:24s} -> {path} ({os.path.getsize(path)} bytes)")

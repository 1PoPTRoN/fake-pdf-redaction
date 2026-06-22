"""Regression tests for the audit fixes.

Each test pins a specific previously-confirmed false negative, false positive, or
unsafe behaviour. Names reference the audit issue numbers.
"""

import io
import os
import signal
import threading
import time

import pikepdf
import pytest
from reportlab.pdfgen.canvas import Canvas

from pdfaudit import Engine
from pdfaudit.model import Finding, Report, Severity
import gen_fixtures as g
import util


def _scan_bytes(data: bytes, **kw):
    import tempfile
    f = tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False)
    f.write(data)
    f.close()
    try:
        return Engine(**kw).scan(f.name)
    finally:
        os.unlink(f.name)


def _blank_meta(c):
    for k in ("Author", "Title", "Subject", "Keywords"):
        getattr(c, "set" + k)("")


# --- #2/#4 covered_text: opacity, not darkness -----------------------------

@pytest.mark.parametrize("gray,expect_sev", [(1.0, Severity.HIGH), (0.6, Severity.HIGH), (0.0, Severity.CRITICAL)])
def test_opaque_cover_of_any_shade_is_detected(gray, expect_sev):
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(612, 792))
    _blank_meta(c)
    c.setFont("Helvetica", 14)
    c.drawString(72, 700, "SSN 555-66-7777 secret")
    c.setFillColorRGB(gray, gray, gray)
    c.rect(70, 694, 360, 22, stroke=0, fill=1)
    c.showPage()
    c.save()
    rep = _scan_bytes(buf.getvalue())
    ct = util.findings_for(rep, "covered_text")
    assert ct, f"opaque gray={gray} cover was missed (false negative)"
    assert max(f.severity for f in ct) == expect_sev
    assert "555-66-7777" in util.evidence_blob(rep, "covered_text")


def test_dark_rect_inside_form_xobject_is_detected():
    """#16: a cover painted inside a Form XObject must be found, not just top-level."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica))
    form = pdf.make_stream(b"0 0 0 rg 0 0 300 20 re f")  # black filled rect
    form.Type = pikepdf.Name.XObject
    form.Subtype = pikepdf.Name.Form
    form.BBox = pikepdf.Array([0, 0, 300, 20])
    page = pdf.add_blank_page(page_size=(612, 792))
    page.Contents = pdf.make_stream(
        b"BT /F1 14 Tf 72 700 Td (NESTED 271828) Tj ET\nq 1 0 0 1 70 694 cm /Fm0 Do Q")
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font),
                                        XObject=pikepdf.Dictionary(Fm0=form))
    out = io.BytesIO()
    pdf.save(out)
    rep = _scan_bytes(out.getvalue())
    ct = util.findings_for(rep, "covered_text")
    assert ct, "cover inside a Form XObject was missed (#16)"
    assert "271828" in util.evidence_blob(rep, "covered_text")


def test_covered_text_on_rotated_page():
    """#28: coverage math must hold on a /Rotate page."""
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(612, 792))
    _blank_meta(c)
    c.setFont("Helvetica", 14)
    c.drawString(72, 700, "ROT SECRET 314159")
    c.setFillColorRGB(0, 0, 0)
    c.rect(70, 694, 320, 22, stroke=0, fill=1)
    c.showPage()
    c.save()
    pdf = pikepdf.open(io.BytesIO(buf.getvalue()))
    pdf.pages[0].Rotate = 90
    out = io.BytesIO()
    pdf.save(out)
    rep = _scan_bytes(out.getvalue())
    assert util.findings_for(rep, "covered_text"), "covered text missed on a rotated page (#28)"
    assert "314159" in util.evidence_blob(rep, "covered_text")


def test_fullpage_background_is_not_a_false_positive():
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(612, 792))
    _blank_meta(c)
    c.setFillColorRGB(0.95, 0.95, 0.9)
    c.rect(0, 0, 612, 792, stroke=0, fill=1)  # page background fill
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 14)
    c.drawString(72, 700, "ordinary visible text")
    c.showPage()
    c.save()
    rep = _scan_bytes(buf.getvalue())
    assert util.findings_for(rep, "covered_text") == []


# --- #3 hidden_text: colour / size / off-page ------------------------------

def test_white_on_white_is_detected():
    rep = _scan_bytes(g.white_on_white_text())
    assert util.findings_for(rep, "hidden_text"), "white-on-white text missed"
    assert "Maria" in util.evidence_blob(rep, "hidden_text")


def test_tiny_font_text_is_detected():
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(612, 792))
    _blank_meta(c)
    c.setFont("Helvetica", 0.2)  # effectively invisible
    c.drawString(72, 700, "microprint salary 999000")
    c.showPage()
    c.save()
    rep = _scan_bytes(buf.getvalue())
    assert util.findings_for(rep, "hidden_text"), "near-zero font size missed"


# --- #5 / #19 / #20 hidden_text interpreter --------------------------------

def test_invisible_text_in_form_xobject_is_detected_with_scoped_evidence():
    pdf = pikepdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica))
    form = pdf.make_stream(b"BT /F1 14 Tf 3 Tr 10 10 Td (HIDDEN-XOBJECT-9900) Tj ET")
    form.Type = pikepdf.Name.XObject
    form.Subtype = pikepdf.Name.Form
    form.BBox = pikepdf.Array([0, 0, 300, 20])
    form.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
    page = pdf.add_blank_page(page_size=(612, 792))
    page.Contents = pdf.make_stream(b"BT /F1 14 Tf 0 Tr 72 700 Td (visible) Tj ET\n/Fm0 Do")
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font),
                                        XObject=pikepdf.Dictionary(Fm0=form))
    out = io.BytesIO()
    pdf.save(out)
    rep = _scan_bytes(out.getvalue())
    hits = util.findings_for(rep, "hidden_text")
    assert hits, "invisible text in a Form XObject was missed (#5)"
    blob = util.evidence_blob(rep, "hidden_text")
    assert "HIDDEN-XOBJECT-9900" in blob          # recovered
    assert "visible" not in blob                   # evidence is scoped (#20)


def test_qQ_stack_restores_render_mode():
    """`q 3 Tr (a) Tj Q (b) Tj` => only one invisible show (b is visible after Q)."""
    from pdfaudit.detectors.hidden_text import _scan_stream
    pdf = pikepdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica))
    page = pdf.add_blank_page(page_size=(612, 792))
    page.Contents = pdf.make_stream(
        b"BT /F1 14 Tf q 3 Tr (hidden) Tj Q 72 700 Td (shown) Tj ET")
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
    acc = {"count": 0, "text": []}
    _scan_stream(page, page.Resources, 0, 0, set(), acc)
    assert acc["count"] == 1, "q/Q did not restore the render mode (#19)"


# --- #6 / #13 revision_history boundary handling ---------------------------

def test_literal_eof_in_stream_is_not_a_revision():
    rep = _scan_bytes(_false_eof_pdf())
    assert util.findings_for(rep, "revision_history") == [], "literal %%EOF flagged (#13)"


def test_real_incremental_update_still_recovered():
    rep = _scan_bytes(g.incremental_redaction())
    blob = util.evidence_blob(rep, "revision_history")
    assert "4200000" in blob and "Acme" in blob


def test_recurring_token_still_recovered_via_multiset_diff():
    """A token redacted in one spot but still present elsewhere is recovered (#14)."""
    from collections import Counter
    from pdfaudit.detectors.revision_history import _tokens
    earlier = "the secret code is ZEBRA and ZEBRA appears twice"
    current = "the code is [X] and ZEBRA appears twice"  # one ZEBRA removed
    diff = Counter(_tokens(earlier)) - Counter(_tokens(current))
    assert diff.get("ZEBRA", 0) == 1


def test_short_numeric_token_is_recoverable():
    from pdfaudit.detectors.revision_history import _tokens
    assert "42" in _tokens("pin 42 only")  # #15: <3-char tokens kept


def _false_eof_pdf() -> bytes:
    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"

    def dobj(n, b):
        return b"%d 0 obj\n" % n + b + b"\nendobj\n"

    def sobj(n, d):
        return b"%d 0 obj\n<< /Length %d >>\nstream\n" % (n, len(d)) + d + b"\nendstream\nendobj\n"

    objs = [
        dobj(1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        dobj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        dobj(3, b"<< /Type /Page /Parent 2 0 R /Contents 4 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 5 0 R >> >> >>"),
        sobj(4, b"BT /F1 14 Tf 72 700 Td (A report mentioning %%EOF in prose) Tj ET"),
        dobj(5, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    ]
    body = header
    off = {}
    for i, o in enumerate(objs, 1):
        off[i] = len(body)
        body += o
    xoff = len(body)
    xref = b"xref\n0 6\n0000000000 65535 f \n" + b"".join(
        b"%010d 00000 n \n" % off[i] for i in range(1, 6))
    return body + xref + b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xoff


# --- #10 embedded_files: FileAttachment annotations ------------------------

def test_file_attachment_annotation_is_detected():
    pdf = pikepdf.open(io.BytesIO(g.clean_simple()))
    ef = pdf.make_stream(b"name,ssn\nJ Doe,111-22-3333\n")
    fs = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Filespec, F=pikepdf.String("evidence.csv"),
        UF=pikepdf.String("evidence.csv"), EF=pikepdf.Dictionary(F=ef)))
    annot = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.FileAttachment,
                               Rect=pikepdf.Array([100, 100, 120, 120]), FS=fs)
    pdf.pages[0].Annots = pikepdf.Array([pdf.make_indirect(annot)])
    out = io.BytesIO()
    pdf.save(out)
    rep = _scan_bytes(out.getvalue())
    assert "evidence.csv" in util.evidence_blob(rep, "embedded_files"), "FileAttachment missed (#10)"


# --- #11 redact_annotations: surface the real secret -----------------------

def test_redact_surfaces_contents_secret(corpus):
    rep = Engine().scan(corpus["unapplied_redact"])
    blob = util.evidence_blob(rep, "redact_annotations")
    assert "Sarah Connor" in blob, "real /Contents secret not surfaced (#11)"


# --- #18 / #25 metadata: XMP-only identity + XXE safety --------------------

def test_xmp_only_identity_is_recovered():
    pdf = pikepdf.open(io.BytesIO(g.clean_simple()))
    for k in list(pdf.docinfo.keys()):
        del pdf.docinfo[k]
    with pdf.open_metadata() as m:
        m["dc:creator"] = ["Deep Throat XMP"]
    out = io.BytesIO()
    pdf.save(out)
    rep = _scan_bytes(out.getvalue())
    assert "Deep Throat XMP" in util.evidence_blob(rep, "metadata"), "XMP-only identity missed (#18)"


def test_xmp_parser_blocks_xxe():
    from pdfaudit.detectors.metadata import _parse_xmp
    payload = (b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
               b'<dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">&xxe;</dc:creator>')
    out = _parse_xmp(payload)  # must not raise, must not read the file
    assert all("root:" not in v for _, v, _ in out)


# --- #7 adversarial input safety -------------------------------------------

def test_non_regular_file_is_rejected():
    from pdfaudit.cli import main
    assert main(["scan", "/dev/null"]) == 1  # char device, not a regular file


def test_oversize_file_is_rejected(corpus, monkeypatch):
    import pdfaudit.document as d
    monkeypatch.setattr(d, "MAX_PDF_BYTES", 16)
    with pytest.raises(Exception):
        Engine().scan(corpus["clean_simple"])


# --- #9 / #24 engine timeout + sanitised errors ----------------------------

def test_slow_detector_times_out(corpus):
    if not hasattr(signal, "SIGALRM") or threading.current_thread() is not threading.main_thread():
        pytest.skip("SIGALRM timeout not active in this context")
    from pdfaudit.detectors.base import Detector

    class _Slow(Detector):
        name = "slow"

        def analyze(self, doc):
            time.sleep(3)
            return []

    rep = Engine([_Slow()], detector_timeout=0.2).scan(corpus["clean_simple"])
    assert "slow" in rep.detector_errors
    assert "time limit" in rep.detector_errors["slow"]


def test_detector_error_message_is_sanitised(corpus):
    from pdfaudit.detectors.base import Detector

    class _Boom(Detector):
        name = "boom"

        def analyze(self, doc):
            raise RuntimeError("x" * 5000 + "\nsecret-looking line")

    rep = Engine([_Boom()]).scan(corpus["clean_simple"])
    msg = rep.detector_errors["boom"]
    assert msg.startswith("RuntimeError: ")
    assert "\n" not in msg and len(msg) < 250


# --- #21 Severity is truthy ------------------------------------------------

def test_info_severity_is_truthy():
    assert Severity.INFO  # was 0 (falsy) before the fix
    assert bool(Severity.INFO) is True


# --- #1 / #27 CLI exit semantics -------------------------------------------

def test_detector_error_fails_the_gate(monkeypatch, corpus):
    from pdfaudit import cli

    def fake_scan(self, path, only=None):
        r = Report(path=path)
        r.detector_errors["covered_text"] = "PDFSyntaxError: boom"
        return r

    monkeypatch.setattr(cli.Engine, "scan", fake_scan)
    assert cli.main(["scan", corpus["clean_simple"], "--json"]) == 3
    assert cli.main(["scan", corpus["clean_simple"], "--json", "--no-fail-on-error"]) == 0


def test_finding_takes_precedence_over_error_exit(monkeypatch, corpus):
    from pdfaudit import cli

    def fake_scan(self, path, only=None):
        r = Report(path=path)
        r.add(Finding(vector="covered_text", severity=Severity.CRITICAL, description="x"))
        r.detector_errors["hidden_text"] = "Boom: e"
        return r

    monkeypatch.setattr(cli.Engine, "scan", fake_scan)
    assert cli.main(["scan", corpus["clean_simple"], "--json"]) == 2


def test_only_with_trailing_comma_is_accepted(corpus):
    from pdfaudit.cli import main
    # Trailing comma => empty token dropped, covered_text still runs.
    assert main(["scan", corpus["box_over_text"], "--only", "covered_text,", "--json"]) == 2

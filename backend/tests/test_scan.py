"""POST /api/v1/scan — JSON report endpoint."""
from __future__ import annotations

from tests.conftest import (
    make_boxed_pdf_bytes,
    make_corrupt_pdf_bytes,
    make_encrypted_readable_pdf_bytes,
    make_password_protected_pdf_bytes,
    make_pdf_bytes,
    upload,
)

# Sentinel markers we hide under a black box to verify the covered-text
# detector recovers them.
LEAKY_SECRET = "SSN123-45-6789"


# ── happy path: clean PDF ────────────────────────────────────────────


def test_scan_clean_pdf_returns_low_or_info_only(client):
    parts = upload("clean.pdf", make_pdf_bytes("Clean", 2))
    r = client.post("/api/v1/scan", files=parts)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["finding_count"] == len(body["findings"])
    # The covered/hidden/revision detectors should NOT fire on a clean PDF.
    # metadata may or may not produce info-level findings depending on
    # whether reportlab sets anything; we only assert no HIGH+ severities.
    severe = [f for f in body["findings"] if f["severity"] in ("high", "critical")]
    assert severe == [], f"clean PDF triggered high/critical findings: {severe}"


# ── happy path: leaky PDF ─────────────────────────────────────────────


def test_scan_boxed_pdf_recovers_secret_as_critical(client):
    parts = upload("boxed.pdf", make_boxed_pdf_bytes("Boxed", LEAKY_SECRET))
    r = client.post("/api/v1/scan", files=parts)
    assert r.status_code == 200, r.text
    body = r.json()

    # The covered-text detector MUST flag this as critical.
    critical = [f for f in body["findings"] if f["severity"] == "critical"]
    assert critical, f"expected at least one critical finding, got: {body['findings']}"

    # And the recovered evidence must include our secret string.
    evidence_blob = " ".join(
        (f.get("evidence") or "") for f in critical
    )
    assert LEAKY_SECRET in evidence_blob, (
        f"expected secret in evidence, got: {evidence_blob!r}"
    )

    # Worst severity at top level should match.
    assert body["worst_severity"] == "critical"
    assert body["path"] == "boxed.pdf"


# ── filter ────────────────────────────────────────────────────────────


def test_scan_only_filter_respected(client):
    parts = upload("boxed.pdf", make_boxed_pdf_bytes("Boxed", LEAKY_SECRET))
    r = client.post(
        "/api/v1/scan",
        files=parts,
        data={"only": "covered_text"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Every finding should come from the covered_text vector.
    vectors = {f["vector"] for f in body["findings"]}
    assert vectors <= {"covered_text"}, f"unexpected vectors leaked through filter: {vectors}"


def test_scan_only_with_unknown_vector_returns_400(client):
    """Unknown detector names must be REJECTED, not silently dropped.

    Silently dropping them runs zero detectors and returns a falsely-clean
    report — a dangerous false negative. This matches the CLI, which exits 1
    on an unknown --only vector."""
    parts = upload("boxed.pdf", make_boxed_pdf_bytes("Boxed", LEAKY_SECRET))
    r = client.post(
        "/api/v1/scan",
        files=parts,
        data={"only": "does_not_exist"},
    )
    assert r.status_code == 400, r.text
    body = r.json()
    assert "error" in body
    assert "does_not_exist" in body["error"]


def test_scan_only_mixed_known_and_unknown_returns_400(client):
    """If any name in the list is unknown, reject the whole request."""
    parts = upload("boxed.pdf", make_boxed_pdf_bytes("Boxed", LEAKY_SECRET))
    r = client.post(
        "/api/v1/scan",
        files=parts,
        data={"only": "covered_text,nope"},
    )
    assert r.status_code == 400, r.text


# ── error surface ─────────────────────────────────────────────────────


def test_scan_missing_file_returns_422(client):
    """FastAPI's validation: required file field → 422."""
    r = client.post("/api/v1/scan")
    assert r.status_code == 422


def test_validation_error_uses_error_envelope(client):
    """422 validation errors must use the documented {"error": ...} shape, not
    FastAPI's default {"detail": [...]}, so the contract (and the frontend's
    error parsing) is consistent across all error responses."""
    r = client.post("/api/v1/scan")  # missing required `file`
    assert r.status_code == 422
    body = r.json()
    assert "error" in body
    assert isinstance(body["error"], str) and body["error"]


def test_scan_empty_file_returns_400(client):
    parts = upload("empty.pdf", b"")
    r = client.post("/api/v1/scan", files=parts)
    assert r.status_code == 400


def test_scan_corrupt_pdf_returns_422(client):
    parts = upload("bad.pdf", make_corrupt_pdf_bytes())
    r = client.post("/api/v1/scan", files=parts)
    assert r.status_code == 422
    assert "error" in r.json()


def test_scan_encrypted_but_readable_pdf_is_scanned(client):
    """An owner-password / empty-user-password PDF opens without a password, so
    it must be SCANNED (200), not falsely rejected as encrypted (415)."""
    parts = upload("permissions.pdf", make_encrypted_readable_pdf_bytes())
    r = client.post("/api/v1/scan", files=parts)
    assert r.status_code == 200, r.text


def test_scan_password_protected_pdf_returns_415(client):
    """A PDF that genuinely needs a user password to open is still rejected 415."""
    parts = upload("locked.pdf", make_password_protected_pdf_bytes())
    r = client.post("/api/v1/scan", files=parts)
    assert r.status_code == 415


def test_scan_oversized_returns_413(client, monkeypatch):
    """Shrink the cap so we don't have to upload a 100 MB blob in tests."""
    from app.config import Limits, get_limits

    def tiny_limits() -> Limits:
        return Limits(max_file_bytes=1024, detector_timeout=Limits.detector_timeout)

    monkeypatch.setattr("app.routes.scan.get_limits", tiny_limits)
    parts = upload("big.pdf", make_pdf_bytes("Big", 2))
    r = client.post("/api/v1/scan", files=parts)
    assert r.status_code == 413


def test_scan_wrong_content_type_returns_415(client):
    parts = upload("image.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
    r = client.post("/api/v1/scan", files=parts)
    assert r.status_code == 415


def test_oversize_request_body_rejected_by_middleware(client, monkeypatch):
    """A request whose Content-Length exceeds the cap is rejected 413 up front,
    before the body is spooled/parsed — not only after reading it all."""
    from app.config import Limits

    monkeypatch.setattr("app.main.get_limits", lambda: Limits(max_file_bytes=1024))
    r = client.post(
        "/api/v1/scan",
        content=b"x" * 200_000,
        headers={"content-type": "application/pdf"},
    )
    assert r.status_code == 413, r.text
    assert "error" in r.json()


def test_scan_flags_incomplete_when_a_detector_errors(client, monkeypatch):
    """If any detector errored, the report must be flagged `incomplete: true`
    so a consumer can't read a partial scan as 'clean' (the CLI exits 3 here)."""
    from pdfaudit import Report

    def fake_scan(payload, *, filename, limits, only=None):
        r = Report(path=filename)
        r.detector_errors["covered_text"] = "PDFSyntaxError: boom"
        return r

    monkeypatch.setattr("app.routes.scan.scan_bytes", fake_scan)
    parts = upload("x.pdf", make_pdf_bytes("X", 1))
    r = client.post("/api/v1/scan", files=parts)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["incomplete"] is True
    assert body["detector_errors"]


def test_scan_not_incomplete_on_full_coverage(client):
    parts = upload("x.pdf", make_pdf_bytes("X", 1))
    body = client.post("/api/v1/scan", files=parts).json()
    assert body["incomplete"] is False


def test_concurrent_scans_all_succeed(client):
    """The scan route is sync (`def`), so FastAPI runs it in a worker thread and
    the event loop is not blocked. Concurrent requests must all complete cleanly."""
    import concurrent.futures

    def one(i: int) -> int:
        parts = upload(f"f{i}.pdf", make_boxed_pdf_bytes("Boxed", LEAKY_SECRET))
        return client.post("/api/v1/scan", files=parts).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        codes = list(ex.map(one, range(8)))
    assert all(c == 200 for c in codes), codes
"""POST /api/v1/scan and POST /api/v1/scan/pdf."""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response

from pdfaudit import Engine, Report

from ..config import get_limits
from ..schemas import ErrorResponse, ReportResponse
from ..services.pdf_report import render_report_pdf
from ..services.scanner import scan_bytes

logger = logging.getLogger("pdf-auditor")
router = APIRouter()

# The detector set is stable, so resolve the valid vector names once at import.
_AVAILABLE_VECTORS = frozenset(Engine().available_vectors())

# Error responses shared by both scan endpoints (OpenAPI docs).
_ERROR_RESPONSES = {code: {"model": ErrorResponse} for code in (400, 413, 415, 422)}


def _read_upload(file: UploadFile, limits) -> bytes:
    """Read + validate a single uploaded file. Raises HTTPException for size/type issues."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing filename")
    if file.content_type and file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"{file.filename}: unsupported content type {file.content_type}",
        )
    data = file.file.read()
    if len(data) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{file.filename} is empty")
    if len(data) > limits.max_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{file.filename} exceeds limit of {limits.max_file_bytes} bytes",
        )
    return data


def _parse_only(raw: str | None) -> list[str] | None:
    """Parse + validate the `only` form field (comma-separated detector names).

    Unknown names are REJECTED with 400. Silently dropping them would run zero
    detectors and return a falsely-clean report — the worst failure mode for an
    auditor. (The CLI exits 1 on the same input.)
    """
    if raw is None or raw.strip() == "":
        return None
    names = [name.strip() for name in raw.split(",") if name.strip()]
    if not names:
        return None
    unknown = sorted(set(names) - _AVAILABLE_VECTORS)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown vector(s): {', '.join(unknown)}",
        )
    return names


def _scan_upload(file: UploadFile, only: str | None) -> Report:
    """Read + validate the upload and run the scan (shared by both endpoints).

    Domain errors raised by ``scan_bytes`` (``PDFEncryptedError`` / ``PDFCorruptError``)
    propagate to the app-level exception handlers, which map them to 415 / 422.
    """
    limits = get_limits()
    payload = _read_upload(file, limits)
    return scan_bytes(payload, filename=file.filename, limits=limits, only=_parse_only(only))


# Both routes are ``def`` (not ``async def``) so FastAPI runs the blocking scan in a
# worker thread and the event loop stays free. (pdfaudit's SIGALRM detector timeout
# only fires on the main thread, so it is inactive in-server; a hard per-request
# timeout would need a process pool — front this with a proxy timeout for now.)


@router.post("/scan", response_model=ReportResponse, responses=_ERROR_RESPONSES, tags=["scan"])
def scan(
    file: UploadFile = File(..., description="A single PDF to audit"),
    only: str | None = Form(default=None, description="Comma-separated detector names"),
) -> ReportResponse:
    """Scan an uploaded PDF and return the JSON report."""
    report = _scan_upload(file, only)
    data = report.to_dict()
    # Flag partial coverage so a consumer never reads an errored scan as fully clean.
    data["incomplete"] = bool(report.detector_errors)
    return ReportResponse.model_validate(data)


@router.post(
    "/scan/pdf",
    responses={200: {"content": {"application/pdf": {}}}, **_ERROR_RESPONSES},
    tags=["scan"],
)
def scan_pdf(
    file: UploadFile = File(..., description="A single PDF to audit"),
    only: str | None = Form(default=None, description="Comma-separated detector names"),
):
    """Scan an uploaded PDF and return a one-page summary PDF for download."""
    report = _scan_upload(file, only)
    base = (file.filename or "report").rsplit(".", 1)[0]
    return Response(
        content=render_report_pdf(report),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{base}-audit.pdf"'},
    )
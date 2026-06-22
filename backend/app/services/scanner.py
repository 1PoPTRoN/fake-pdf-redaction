"""Thin wrapper around `pdfaudit.Engine`.

The job of this module is to:
  1. Materialize the upload as a temp file (the engine reads by path).
  2. Detect encrypted / unparseable PDFs BEFORE handing off to the engine,
     so we can return precise HTTP status codes (415 / 422).
  3. Run the scan and return the report.

Detector timeouts and per-detector errors are handled inside the engine
itself — we do not need to re-implement them here.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import pikepdf

from pdfaudit import Engine, Report

from ..config import Limits

logger = logging.getLogger("pdf-auditor")


class PDFEncryptedError(Exception):
    """Raised when the uploaded PDF is encrypted."""


class PDFCorruptError(Exception):
    """Raised when the uploaded PDF cannot be parsed at all."""


def _validate_openable(path: Path) -> None:
    """Raise PDFEncryptedError / PDFCorruptError as appropriate.

    We deliberately use pikepdf here (rather than relying on the engine to
    blow up) so we can return the right HTTP status code instead of letting
    a generic 500 escape. The engine's per-detector error handling is
    separate and covers detectors that fail on otherwise-valid PDFs.

    Encryption note: we reject ONLY when the file truly cannot be opened without
    a password (``PasswordError``). A PDF encrypted with an owner password but an
    empty user password — the common 'permission-restricted' PDF — opens fine and
    is fully auditable, so ``is_encrypted`` alone must NOT cause a rejection.
    """
    try:
        with pikepdf.open(path):
            pass  # opened successfully (empty-user-password files included)
    except pikepdf.PasswordError as e:
        # The file genuinely needs a password we don't have.
        raise PDFEncryptedError(str(e) or "PDF requires a password to open") from e
    except Exception as e:  # pragma: no cover — depends on file shape
        # pikepdf can raise a variety of low-level errors for truncated /
        # garbage PDFs (e.g. "Could not find xref table", "not a PDF").
        # Normalize them to PDFCorruptError.
        raise PDFCorruptError(f"PDF is corrupt or unparseable: {type(e).__name__}: {e}") from e


def scan_bytes(
    payload: bytes,
    *,
    filename: str,
    limits: Limits,
    only: list[str] | None = None,
) -> Report:
    """Scan `payload` as a PDF and return a `pdfaudit.Report`.

    The payload is written to a temp file (via ``mkstemp``) because pdfaudit's
    engine opens files by path. The file is removed in the ``finally`` block, so
    it is always cleaned up — including on exceptions.
    """
    if not payload:
        raise PDFCorruptError("uploaded file is empty")

    # mkstemp gives a path (mode 0600, owner-only) with an explicit .pdf suffix;
    # we close the fd immediately and write via the Path. Removed in `finally`.
    fd, raw_path = tempfile.mkstemp(prefix="pdfaudit-", suffix=".pdf")
    os.close(fd)
    path = Path(raw_path)
    try:
        path.write_bytes(payload)
        _validate_openable(path)
        engine = Engine(detector_timeout=limits.detector_timeout)
        report = engine.scan(str(path), only=only)
        # Replace the engine's internal temp path with the user's filename
        # so the report reads naturally in the JSON response.
        report.path = filename
        return report
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:  # pragma: no cover
            logger.warning("failed to remove temp file %s", path)
"""Runtime limits and tunables for the PDF auditor service."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    # Max size of a single uploaded PDF.
    max_file_bytes: int = 100 * 1024 * 1024  # 100 MB
    # Per-detector timeout, in seconds. pdfaudit's Engine wraps each detector
    # in a SIGALRM-based time limit; we expose the same knob here.
    detector_timeout: float = 60.0


def get_limits() -> Limits:
    """Override from environment if needed."""
    return Limits(
        max_file_bytes=int(os.getenv("PDFAUDIT_MAX_FILE_BYTES", Limits.max_file_bytes)),
        detector_timeout=float(os.getenv("PDFAUDIT_DETECTOR_TIMEOUT", Limits.detector_timeout)),
    )


# Default to local dev origins — never a wildcard. The API is unauthenticated and
# returns recovered (potentially sensitive) content, so the allow-list must be
# explicit. Set PDFAUDIT_CORS_ORIGINS (comma-separated) in prod; "*" to opt into
# fully-open CORS deliberately.
_DEFAULT_CORS_ORIGINS = ["http://localhost:5174", "http://127.0.0.1:5174"]


def get_cors_origins() -> list[str]:
    raw = os.getenv("PDFAUDIT_CORS_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return list(_DEFAULT_CORS_ORIGINS)

"""Pydantic schemas for the auditor API.

We mirror `pdfaudit.Report.to_dict()` exactly so the wire format is the same
as what the CLI emits via `pdfaudit.reporters.to_json()`. This keeps the
contract simple: anything the library knows how to serialize, the API can
emit unchanged.
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


Severity = Literal["info", "low", "medium", "high", "critical"]


class HealthResponse(BaseModel):
    """Readiness signal for the home-page status pill.

    `status` distinguishes three real states:
      - "warming": detector imports / Engine() init have not finished yet. The
        process is up but a scan would block on import. The frontend shows a
        "LAUNCHING" pill so the user knows to wait.
      - "ok": everything is warm. The pill shows "BACKEND LIVE".
      - "degraded": warmup failed (e.g. an optional dep was missing). The
        process is up but the engine may not scan. Surfaces a real error.

    A free-tier cold start returns "warming" with HTTP 503 until warmup
    completes, then "ok" with HTTP 200. The frontend must read the body, not
    just the status code.
    """
    status: Literal["ok", "warming", "degraded"] = "warming"
    detail: str = ""
    vectors_ready: int = 0


class ErrorResponse(BaseModel):
    error: str


class VectorInfo(BaseModel):
    """One detector entry in the /vectors response."""
    name: str = Field(..., description="Detector identifier used in the `only` filter")
    description: str = Field(..., description="One-line summary of what this detector looks for")


class VectorsResponse(BaseModel):
    vectors: List[VectorInfo]


class Finding(BaseModel):
    """One audit finding — mirrors pdfaudit.Finding.to_dict()."""
    vector: str
    severity: Severity
    description: str
    page: Optional[int] = None
    bbox: Optional[Tuple[float, float, float, float]] = None
    evidence: Optional[str] = None
    recommendation: Optional[str] = None


class ReportResponse(BaseModel):
    """Mirrors pdfaudit.Report.to_dict(), plus an `incomplete` coverage flag."""
    path: str
    worst_severity: Optional[Severity] = None
    finding_count: int
    findings: List[Finding]
    detector_errors: Dict[str, str] = Field(default_factory=dict)
    # True when one or more detectors errored, so a clean-looking result cannot be
    # trusted as fully clean. Mirrors the CLI's non-zero "incomplete" exit code.
    incomplete: bool = False
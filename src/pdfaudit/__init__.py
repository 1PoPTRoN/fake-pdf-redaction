"""pdfaudit — a read-only auditor that detects recoverable content behind PDF redactions."""

from .engine import Engine, default_detectors
from .model import Finding, Report, Severity

__version__ = "0.1.0"
__all__ = ["Engine", "default_detectors", "Finding", "Report", "Severity"]

"""Surface document metadata that can leak identity or internal information.

The Info dictionary and the XMP packet routinely carry author names, the
software/version used, original file paths, and custom application fields. These
survive page-level redaction. We report populated fields; fields likely to carry
personal/organisational identity (Author, Title, custom keys) are MEDIUM, generic
software fields (Producer, Creator) are INFO.
"""

from __future__ import annotations

from .base import Detector
from ..document import PDFDocument
from ..model import Finding, Severity

# Standard Info keys we recognise; anything else is treated as a custom field.
_STANDARD_KEYS = {
    "/Title", "/Author", "/Subject", "/Keywords",
    "/Creator", "/Producer", "/CreationDate", "/ModDate", "/Trapped",
}
_IDENTITY_KEYS = {"/Author", "/Title", "/Subject", "/Keywords"}


class MetadataDetector(Detector):
    name = "metadata"

    def analyze(self, doc: PDFDocument) -> list[Finding]:
        findings: list[Finding] = []
        populated: list[tuple[str, str, bool]] = []  # (key, value, is_identity)

        try:
            docinfo = doc.pdf.docinfo
        except Exception:
            docinfo = None

        if docinfo is not None:
            for key, value in docinfo.items():
                key_s = str(key)
                val_s = str(value).strip()
                if not val_s:
                    continue
                is_identity = key_s in _IDENTITY_KEYS or key_s not in _STANDARD_KEYS
                populated.append((key_s, val_s, is_identity))

        for key_s, val_s, is_identity in populated:
            sev = Severity.MEDIUM if is_identity else Severity.INFO
            kind = "identity/custom" if is_identity else "software"
            findings.append(
                Finding(
                    vector=self.name,
                    severity=sev,
                    evidence=f"{key_s} = {val_s[:200]}",
                    description=(
                        f"Document metadata field {key_s} ({kind}) is populated and is "
                        f"retained independently of page content."
                    ),
                    recommendation=(
                        "Strip or sanitise document metadata (Info dictionary and XMP) "
                        "before distribution."
                    ),
                )
            )

        # XMP packet presence (we report it; deep XMP parsing is a fast-follow).
        try:
            xmp = doc.pdf.Root.get("/Metadata")
        except Exception:
            xmp = None
        if xmp is not None:
            try:
                raw = bytes(xmp.read_bytes())
                size = len(raw)
            except Exception:
                size = -1
            findings.append(
                Finding(
                    vector=self.name,
                    severity=Severity.INFO,
                    evidence=f"XMP packet present ({size} bytes)"
                    if size >= 0 else "XMP packet present",
                    description=(
                        "An XMP metadata stream is present. XMP commonly duplicates Info "
                        "fields and may add application-specific history."
                    ),
                    recommendation="Sanitise or remove the XMP packet before distribution.",
                )
            )
        return findings

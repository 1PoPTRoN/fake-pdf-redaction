"""Surface document metadata that can leak identity or internal information.

The Info dictionary and the XMP packet routinely carry author names, the
software/version used, original file paths, and custom application fields. These
survive page-level redaction. We report populated Info fields, parse the XMP packet
to recover identity fields it carries (even when they are not duplicated in the Info
dictionary), and note object-level metadata streams.

XMP is attacker-controlled XML, so it is parsed with ``defusedxml`` (external
entities / DTDs disabled) to avoid XXE and entity-expansion attacks.
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

# XMP local element names worth recovering, split by how sensitive they are.
_XMP_IDENTITY = {"creator", "author", "title", "subject", "rights", "DocumentID", "InstanceID"}
_XMP_SOFTWARE = {"CreatorTool", "ProducerTool", "History", "ManagedFrom"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _all_text(el) -> str:
    return " ".join(t.strip() for t in el.itertext() if t and t.strip())


def _parse_xmp(data: bytes) -> list[tuple[str, str, bool]]:
    """Return ``(field, value, is_identity)`` recovered from an XMP packet."""
    try:
        import defusedxml.ElementTree as ET
    except Exception:
        return []
    try:
        root = ET.fromstring(data)
    except Exception:
        return []
    out: list[tuple[str, str, bool]] = []
    seen: set[tuple[str, str]] = set()
    for el in root.iter():
        name = _local(el.tag)
        identity = name in _XMP_IDENTITY
        if not identity and name not in _XMP_SOFTWARE:
            continue
        val = _all_text(el)
        if not val or (name, val) in seen:
            continue
        seen.add((name, val))
        out.append((name, val[:200], identity))
    return out


class MetadataDetector(Detector):
    name = "metadata"

    def analyze(self, doc: PDFDocument) -> list[Finding]:
        findings: list[Finding] = []
        seen_values: set[str] = set()

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
                seen_values.add(val_s)
                is_identity = key_s in _IDENTITY_KEYS or key_s not in _STANDARD_KEYS
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

        # XMP packet: parse it and recover identity fields, not just presence.
        try:
            xmp = doc.pdf.Root.get("/Metadata")
        except Exception:
            xmp = None
        if xmp is not None:
            raw = b""
            try:
                raw = bytes(xmp.read_bytes())
            except Exception:
                raw = b""
            for field, val, is_identity in _parse_xmp(raw):
                if val in seen_values:
                    continue  # already reported via the Info dictionary
                seen_values.add(val)
                findings.append(
                    Finding(
                        vector=self.name,
                        severity=Severity.MEDIUM if is_identity else Severity.INFO,
                        evidence=f"xmp:{field} = {val}",
                        description=(
                            f"XMP metadata field '{field}' is populated and survives "
                            f"page-level redaction."
                        ),
                        recommendation="Sanitise or remove the XMP packet before distribution.",
                    )
                )
            findings.append(
                Finding(
                    vector=self.name,
                    severity=Severity.INFO,
                    evidence=f"XMP packet present ({len(raw)} bytes)" if raw else "XMP packet present",
                    description=(
                        "An XMP metadata stream is present. XMP commonly duplicates Info "
                        "fields and may add application-specific history."
                    ),
                    recommendation="Sanitise or remove the XMP packet before distribution.",
                )
            )

        # Object-level metadata streams (e.g. per-page XMP) survive too.
        try:
            for page_index, page in enumerate(doc.pdf.pages, start=1):
                if page.get("/Metadata") is not None:
                    findings.append(
                        Finding(
                            vector=self.name,
                            severity=Severity.INFO,
                            page=page_index,
                            evidence="page-level XMP metadata stream present",
                            description=(
                                "This page carries its own metadata stream, retained "
                                "independently of the document catalog."
                            ),
                            recommendation="Remove per-object metadata if it is sensitive.",
                        )
                    )
        except Exception:
            pass

        return findings

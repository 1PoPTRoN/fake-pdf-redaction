"""Detect embedded file attachments.

If a PDF embeds a file (a spreadsheet, the source document, an image), redacting
the visible page is pointless when the attachment still contains the raw data.
We enumerate attachments via pikepdf's attachment API and, as a backstop, the
``/Names /EmbeddedFiles`` name tree directly.
"""

from __future__ import annotations

import pikepdf

from .base import Detector
from ..document import PDFDocument
from ..model import Finding, Severity


def _attachment_names_and_sizes(pdf: pikepdf.Pdf) -> list[tuple[str, int]]:
    results: dict[str, int] = {}

    # Primary: pikepdf high-level attachment list.
    try:
        for name in pdf.attachments.keys():
            size = -1
            try:
                data = pdf.attachments[name].get_file().read_bytes()
                size = len(data)
            except Exception:
                size = -1
            results[str(name)] = size
    except Exception:
        pass

    # Backstop: walk the EmbeddedFiles name tree for anything missed.
    try:
        names = pdf.Root.get("/Names")
        if names is not None:
            ef = names.get("/EmbeddedFiles")
            if ef is not None:
                arr = ef.get("/Names")
                if arr is not None:
                    for i in range(0, len(arr) - 1, 2):
                        key = str(arr[i])
                        results.setdefault(key, -1)
    except Exception:
        pass

    return sorted(results.items())


class EmbeddedFileDetector(Detector):
    name = "embedded_files"

    def analyze(self, doc: PDFDocument) -> list[Finding]:
        findings: list[Finding] = []
        for fname, size in _attachment_names_and_sizes(doc.pdf):
            size_str = f"{size} bytes" if size >= 0 else "unknown size"
            findings.append(
                Finding(
                    vector=self.name,
                    severity=Severity.HIGH,
                    evidence=f"{fname} ({size_str})",
                    description=(
                        f"The document embeds the file '{fname}'. Embedded files retain "
                        f"their raw contents regardless of what is redacted on the page."
                    ),
                    recommendation=(
                        "Remove the embedded file unless it is intended for release, and "
                        "confirm it does not contain the data you redacted from the page."
                    ),
                )
            )
        return findings

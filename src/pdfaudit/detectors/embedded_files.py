"""Detect embedded file attachments through every path the format allows.

If a PDF carries a file (a spreadsheet, the source document, an image), redacting
the visible page is pointless when the attachment still holds the raw data. Files
can be attached in several distinct ways, and missing any of them is a leak the
tool reports as clean:

* the document ``/Names /EmbeddedFiles`` name tree (possibly split across ``/Kids``);
* ``/FileAttachment`` annotations on a page (a paper-clip icon);
* ``/AF`` associated-files arrays on the catalog or individual pages.

We enumerate all of them, deduplicating by name, on top of pikepdf's high-level
attachment API.
"""

from __future__ import annotations

import pikepdf

from .base import Detector
from ..document import PDFDocument
from ..model import Finding, Severity

_MAX_TREE_DEPTH = 50


def _filespec_name(fs) -> str:
    for key in ("/UF", "/F"):
        try:
            val = fs.get(key)
        except Exception:
            val = None
        if val is not None:
            return str(val)
    return "(unnamed)"


def _filespec_size(fs) -> int:
    try:
        ef = fs.get("/EF")
        if ef is not None:
            stream = ef.get("/F") or ef.get("/UF")
            if stream is not None:
                return len(stream.read_bytes())
    except Exception:
        pass
    return -1


def _record(results: dict, name: str, size: int) -> None:
    # Prefer a known size over an unknown one if we see the same name twice.
    if name not in results or (results[name] < 0 <= size):
        results[name] = size


def _walk_name_tree(node, results: dict, depth: int = 0) -> None:
    if node is None or depth > _MAX_TREE_DEPTH:
        return
    try:
        names = node.get("/Names")
        if names is not None:
            for i in range(0, len(names) - 1, 2):
                _record(results, str(names[i]), _filespec_size(names[i + 1]))
        kids = node.get("/Kids")
        if kids is not None:
            for kid in kids:
                _walk_name_tree(kid, results, depth + 1)
    except Exception:
        pass


def _collect(pdf: pikepdf.Pdf) -> list[tuple[str, int]]:
    results: dict[str, int] = {}

    # 1. pikepdf high-level API (walks the EmbeddedFiles name tree, incl. /Kids).
    try:
        for name in pdf.attachments.keys():
            size = -1
            try:
                size = len(pdf.attachments[name].get_file().read_bytes())
            except Exception:
                size = -1
            _record(results, str(name), size)
    except Exception:
        pass

    # 2. The EmbeddedFiles name tree directly, as a backstop (handles /Kids).
    try:
        names = pdf.Root.get("/Names")
        if names is not None:
            _walk_name_tree(names.get("/EmbeddedFiles"), results)
    except Exception:
        pass

    # 3. /FileAttachment annotations on each page.
    try:
        for page in pdf.pages:
            annots = page.get("/Annots")
            if annots is None:
                continue
            for annot in annots:
                try:
                    if str(annot.get("/Subtype")) != "/FileAttachment":
                        continue
                    fs = annot.get("/FS")
                    if fs is not None:
                        _record(results, _filespec_name(fs), _filespec_size(fs))
                except Exception:
                    continue
    except Exception:
        pass

    # 4. /AF associated files on the catalog and on pages.
    def _collect_af(holder):
        try:
            af = holder.get("/AF")
        except Exception:
            af = None
        if af is None:
            return
        try:
            for fs in af:
                _record(results, _filespec_name(fs), _filespec_size(fs))
        except Exception:
            pass

    try:
        _collect_af(pdf.Root)
        for page in pdf.pages:
            _collect_af(page)
    except Exception:
        pass

    return sorted(results.items())


class EmbeddedFileDetector(Detector):
    name = "embedded_files"

    def analyze(self, doc: PDFDocument) -> list[Finding]:
        findings: list[Finding] = []
        for fname, size in _collect(doc.pdf):
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

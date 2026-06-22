"""Recover content from earlier revisions of an incrementally-updated PDF.

THE DIFFERENTIATOR. A PDF grows by appending incremental updates; the bytes are
never rewritten, only added to, and each appended revision ends with ``%%EOF``.
The byte slice up to an *earlier* ``%%EOF`` is itself a loadable earlier version of
the document — the version before someone "redacted" or edited it.

Algorithm:

1. Find *genuine* revision termini. A real appended revision ends ``startxref
   <offset> %%EOF`` where ``offset`` points **backward**, into the prefix, at that
   revision's own cross-reference (a classic ``xref`` table or an xref-stream
   object). This single structural test rejects two whole classes of false
   boundary that fooled a naive ``%%EOF`` scan: a literal ``%%EOF`` inside a content
   stream/string, and a linearised file's internal ``%%EOF`` (whose ``startxref``
   points *forward* to the main xref). N termini ⇒ N document states.
2. For each earlier state, load ``raw_bytes[:eof_end]`` and extract its text.
3. Diff each earlier revision's tokens against the current text as a *multiset*, so
   a token whose count dropped (redacted on one page, still present elsewhere) is
   still recovered.

If an earlier revision is a valid terminus but its text cannot be extracted
(linearised/xref-stream prefixes pdfminer can't lay out), we do **not** report
"clean" — we surface it as a HIGH "could not verify" finding, because an
unreadable prior revision is unknown, not safe.
"""

from __future__ import annotations

import io
import re
from collections import Counter

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams

from .base import Detector
from ..document import PDFDocument, iter_chars
from ..model import Finding, Severity

_EOF = b"%%EOF"
# ``startxref <n>`` immediately before a ``%%EOF`` (allowing trailing EOL).
_STARTXREF_RE = re.compile(rb"startxref\s+(\d+)\s*\Z")
# An xref-stream cross-reference object header: ``<num> <gen> obj``.
_XREF_OBJ_RE = re.compile(rb"\s*\d+\s+\d+\s+obj")
# Keep tokens containing at least one alphanumeric (drops pure punctuation noise),
# regardless of length, so short secrets ("4242", initials) are still recovered.
_TOKEN_RE = re.compile(r"\S+")
_ALNUM_RE = re.compile(r"[A-Za-z0-9]")
# Cap the number of earlier states we fully parse, to bound work on a file crafted
# with many revision termini (defence in depth alongside the structural check).
_MAX_REVISIONS = 64


def _looks_like_xref_at(raw: bytes, off: int) -> bool:
    seg = raw[off:off + 64]
    return seg.lstrip()[:4] == b"xref" or _XREF_OBJ_RE.match(seg) is not None


def _revision_boundaries(raw: bytes) -> list[int]:
    """Offsets just past each *genuine* revision-terminating ``%%EOF``."""
    boundaries: list[int] = []
    start = 0
    while True:
        idx = raw.find(_EOF, start)
        if idx == -1:
            break
        eof_end = idx + len(_EOF)
        window = raw[max(0, idx - 128):idx]
        m = _STARTXREF_RE.search(window)
        if m:
            off = int(m.group(1))
            # Genuine appended revision: startxref points backward, into the prefix,
            # at a real cross-reference. (Forward-pointing => linearised internal EOF.)
            if 0 <= off < idx and _looks_like_xref_at(raw, off):
                boundaries.append(eof_end)
        start = eof_end
    return boundaries


def _text_from_bytes(data: bytes) -> str:
    """Extract text from a standalone PDF byte string, matching the layout-based
    tokenisation used for the current document (so the diff is apples-to-apples)."""
    try:
        parts: list[str] = []
        for page in extract_pages(io.BytesIO(data), laparams=LAParams()):
            for ch in iter_chars(page):
                parts.append(ch.get_text())
        return "".join(parts)
    except Exception:
        return ""


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text) if _ALNUM_RE.search(t)]


class RevisionHistoryDetector(Detector):
    name = "revision_history"

    def analyze(self, doc: PDFDocument) -> list[Finding]:
        raw = doc.raw_bytes
        boundaries = _revision_boundaries(raw)
        if len(boundaries) <= 1:
            return []  # single revision: nothing to recover

        total_revisions = len(boundaries)
        earlier = boundaries[:-1][:_MAX_REVISIONS]

        # Current text reuses the document's single cached pdfminer pass.
        current_counter = Counter(_tokens(doc.layout_text()))

        findings: list[Finding] = []
        recovered_any = False
        unverifiable = 0

        for rev_index, eof_end in enumerate(earlier, start=1):
            earlier_text = _text_from_bytes(raw[:eof_end])
            if not earlier_text.strip():
                unverifiable += 1
                continue
            earlier_counter = Counter(_tokens(earlier_text))
            diff = earlier_counter - current_counter  # multiset: counts that dropped
            if not diff:
                continue
            # Preserve readable order from the earlier revision, deduped.
            recovered: list[str] = []
            seen: set[str] = set()
            for tok in _tokens(earlier_text):
                if diff.get(tok, 0) > 0 and tok not in seen:
                    seen.add(tok)
                    recovered.append(tok)
            if recovered:
                recovered_any = True
                findings.append(
                    Finding(
                        vector=self.name,
                        severity=Severity.CRITICAL,
                        evidence=" ".join(recovered[:60]),
                        description=(
                            f"Revision {rev_index} of {total_revisions} contains text that "
                            f"is absent from (or reduced in) the current version. The "
                            f"document was edited via an incremental update, leaving the "
                            f"prior content recoverable from the file's revision history."
                        ),
                        recommendation=(
                            "Re-save the document as a single linearised revision so earlier "
                            "object states are discarded, then re-verify."
                        ),
                    )
                )

        if unverifiable:
            findings.append(
                Finding(
                    vector=self.name,
                    severity=Severity.HIGH,
                    evidence=f"{unverifiable} earlier revision(s) present but not parseable",
                    description=(
                        f"{unverifiable} earlier revision(s) could not be parsed for text "
                        f"comparison (e.g. a linearised or xref-stream prefix). Their content "
                        f"could not be verified and may still be recoverable — this is not a "
                        f"clean result."
                    ),
                    recommendation=(
                        "Flatten the file to a single revision and re-audit; if a finding "
                        "persists, recover the prior revision with a full xref-chain tool."
                    ),
                )
            )

        if not recovered_any and not unverifiable:
            # Genuine updates, all parsed, nothing diverged; still worth surfacing
            # because incremental updates can carry removed objects/attachments.
            findings.append(
                Finding(
                    vector=self.name,
                    severity=Severity.LOW,
                    evidence=f"{len(earlier)} incremental update(s) detected",
                    description=(
                        f"The file has {len(earlier)} incremental update(s) "
                        f"({total_revisions} revisions). No divergent text was recovered, "
                        f"but prior object states are retained in the file."
                    ),
                    recommendation=(
                        "Flatten to a single revision before distribution if the edit "
                        "history is sensitive."
                    ),
                )
            )
        return findings

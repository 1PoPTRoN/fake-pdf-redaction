"""Recover content from earlier revisions of an incrementally-updated PDF.

THE DIFFERENTIATOR. A PDF grows by appending incremental updates; the bytes are
never rewritten, only added to, and each appended revision ends with ``%%EOF``.
That means the byte slice up to an *earlier* ``%%EOF`` is itself a complete,
loadable earlier version of the document — the version before someone "redacted"
or edited it.

So the algorithm is pleasingly direct:

1. Find every ``%%EOF`` marker in the raw bytes. N markers => N document states.
2. For each earlier state, take ``raw_bytes[:eof_end]`` and load it as a
   standalone PDF, then extract its text.
3. Diff each earlier revision's text against the *current* (final) text. Any
   word/line present earlier but absent now is recovered content that the latest
   revision was trying to hide.

We do not hand-write an xref parser for v1 — the truncation trick exercises the
real recovery path on standard appended-update files. Limitation (documented):
linearised PDFs and some malformed updates won't truncate to a valid prefix; we
catch that per-revision and skip it rather than failing the whole scan.
"""

from __future__ import annotations

import io
import re

from pdfminer.high_level import extract_text

from .base import Detector
from ..document import PDFDocument
from ..model import Finding, Severity

_EOF = b"%%EOF"
_WORD_RE = re.compile(r"[^\s]+")
# Ignore very short tokens when diffing so punctuation/layout noise doesn't
# masquerade as "recovered" content.
_MIN_TOKEN_LEN = 3


def _eof_offsets(raw: bytes) -> list[int]:
    offsets = []
    start = 0
    while True:
        idx = raw.find(_EOF, start)
        if idx == -1:
            break
        offsets.append(idx + len(_EOF))
        start = idx + len(_EOF)
    return offsets


def _safe_extract_text(data: bytes) -> str:
    try:
        return extract_text(io.BytesIO(data)) or ""
    except Exception:
        return ""


def _tokens(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall(text) if len(t) >= _MIN_TOKEN_LEN]


class RevisionHistoryDetector(Detector):
    name = "revision_history"

    def analyze(self, doc: PDFDocument) -> list[Finding]:
        raw = doc.raw_bytes
        offsets = _eof_offsets(raw)
        if len(offsets) <= 1:
            return []  # single revision: nothing to recover

        findings: list[Finding] = []
        num_updates = len(offsets) - 1

        current_text = _safe_extract_text(raw)
        current_tokens = set(_tokens(current_text))

        recovered_any = False
        for rev_index, eof_end in enumerate(offsets[:-1], start=1):
            prefix = raw[:eof_end]
            earlier_text = _safe_extract_text(prefix)
            if not earlier_text.strip():
                continue
            earlier_tokens = _tokens(earlier_text)
            # Preserve order + dedupe for readable evidence.
            seen = set()
            recovered = []
            for tok in earlier_tokens:
                if tok not in current_tokens and tok not in seen:
                    seen.add(tok)
                    recovered.append(tok)
            if recovered:
                recovered_any = True
                snippet = " ".join(recovered[:60])
                findings.append(
                    Finding(
                        vector=self.name,
                        severity=Severity.CRITICAL,
                        page=None,
                        evidence=snippet,
                        description=(
                            f"Revision {rev_index} of {num_updates + 1} contains text "
                            f"that is absent from the current version. The document was "
                            f"edited via an incremental update, leaving the prior content "
                            f"recoverable from the file's revision history."
                        ),
                        recommendation=(
                            "Re-save the document as a single linearised revision so "
                            "earlier object states are discarded, then re-verify."
                        ),
                    )
                )

        if not recovered_any:
            # Updates exist but no text diverged; still worth surfacing because
            # incremental updates can carry removed objects, attachments, etc.
            findings.append(
                Finding(
                    vector=self.name,
                    severity=Severity.LOW,
                    evidence=f"{num_updates} incremental update(s) detected",
                    description=(
                        f"The file has {num_updates} incremental update(s) "
                        f"({num_updates + 1} revisions). No divergent text was recovered, "
                        f"but prior object states are retained in the file."
                    ),
                    recommendation=(
                        "Flatten to a single revision before distribution if the "
                        "edit history is sensitive."
                    ),
                )
            )
        return findings

# pdfaudit

A read-only auditor that detects **recoverable content behind PDF "redactions."**
It does not redact or modify anything — it finds the data your black boxes, blurs,
and deletions left behind, and shows it to you as evidence.

The premise: most redaction operates on the *presentation layer* (a rectangle is
drawn over text) while the *data layer* (the actual characters) is untouched.
`pdfaudit` works at the data layer and proves whether the protection holds.

## Install

```bash
pip install -e .            # from a clone
# or, for development (fixtures + tests):
pip install -e ".[dev]"
```

Requires Python ≥ 3.10. Core dependencies: `pikepdf`, `pdfminer.six`.

## Usage

```bash
# Human-readable report
pdfaudit scan document.pdf

# Machine-readable JSON (stable contract)
pdfaudit scan document.pdf --json

# Run only specific detectors
pdfaudit scan document.pdf --only covered_text,revision_history

# Use as a CI release gate (exit 2 if anything HIGH or worse is found)
pdfaudit scan document.pdf --fail-on high

# List available detectors
pdfaudit list-vectors
```

**Exit codes:** `0` clean / below threshold · `2` finding at or above `--fail-on`
(default `high`) · `1` usage or I/O error.

### As a library

```python
from pdfaudit import Engine

report = Engine().scan("document.pdf")
print(report.worst_severity)
for f in report.by_severity():
    print(f.severity.label, f.vector, "->", f.evidence)
```

## What it detects

| Vector | What it catches | Severity |
|---|---|---|
| `covered_text` | Extractable text under an opaque black box / image | CRITICAL / HIGH |
| `hidden_text` | Text drawn in an invisible render mode (`Tr 3`/`7`) | CRITICAL |
| `revision_history` | Content recoverable from an earlier incremental revision | CRITICAL |
| `embedded_files` | Embedded attachments carrying raw data | HIGH |
| `metadata` | Info-dict / XMP fields (author, software, custom keys) | MEDIUM / INFO |
| `redact_annotations` | `/Redact` annotations marked but never applied | CRITICAL |

Each finding carries the **recovered content** as evidence, the page/location
where applicable, and a recommendation.

## How it works

A single read-only `PDFDocument` is parsed once and shared across independent
detectors (`analyze(doc) -> [Finding]`). The engine runs each detector in
isolation — one malformed-PDF edge case becomes a recorded error, not a crashed
scan. Reporting (JSON / CLI) is kept separate from detection.

The two non-obvious detectors:

- **Revision history:** PDFs grow by appending updates that each end in `%%EOF`,
  so the bytes up to an earlier `%%EOF` are a loadable earlier version of the
  document. Diffing earlier revisions against the current text recovers what a
  later "redaction" tried to hide.
- **Covered text:** pdfminer glyph geometry locates characters whose centre falls
  inside an opaque dark rectangle or image — the text is invisible but still in
  the content stream.

See `docs/specs/2026-06-21-pdf-redaction-auditor.md` for the full design, known
limitations, and roadmap, and `MANUAL_TESTING.md` for a hands-on walkthrough.

## Tests

```bash
python -m pytest -q
```

## Scope

v1 is **detection only** — read-only, no PDF writing. It does not redact, repair,
or triage malware. A future verified redactor would use this auditor as its
fail-closed acceptance test.

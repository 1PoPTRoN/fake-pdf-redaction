# pdfaudit — PDF Redaction Leak Auditor

**Status:** v1 implemented and tested (35/35 passing)
**Date:** 2026-06-21
**Author:** Arpit (1PoPTRoN)

## 1. Problem & thesis

Most "redaction" in the wild operates on the *presentation layer*, not the *data
layer*. A black rectangle is drawn over text, a blur is applied, a strength bar
turns green — and the underlying data the protection is supposed to remove is
still sitting in the file. This is **sanitization theater**: the appearance of
protection without the substance. PDF redaction failures are a live, recurring,
high-stakes problem (court filings, government disclosures, corporate documents),
and the failure mode is almost always the same — the visible page was changed but
the *bytes* were not.

`pdfaudit` is a **read-only auditor** that works at the data layer and *proves*
whether claimed redaction holds. It does not redact, repair, or rewrite anything.
It recovers the leaked content and shows it to you as evidence. The deliverable of
a scan is not "this might be risky" — it is "here are the exact characters your
black box is sitting on top of."

### Why an auditor, not a redactor (v1 scope decision)

Redacting safely means rewriting content streams and re-emitting the file, which
is where most tools introduce *new* leaks. Auditing is a strictly read-only
problem with a crisp success criterion (did we recover content that was meant to
be gone?), it is independently valuable in a CI/release-gate workflow, and it is
the natural foundation a future redactor would have to be verified against. v1 is
therefore **detection only**.

## 2. Scope

**In scope (v1):** open a PDF, run a set of independent leak detectors, emit
findings with severity + location + recovered-evidence, in two formats (a stable
JSON contract and a human CLI report). Read-only static analysis. No PDF writing.

**Out of scope (v1, by design):** remediation/redaction, malware triage, OCR of
rasterized text, GUI, and any network/MCP/web frontend. These are designed
*around* (the architecture leaves room for them) but not built.

## 3. Leak vectors

Vectors are tiered by implementation difficulty and signal value.

### Tier A — the hard / novel core
- **`covered_text`** — real, extractable glyphs underneath an opaque cover (the
  classic black-box-over-live-text failure). *CRITICAL* under a dark rectangle,
  *HIGH* under an image.
- **`hidden_text`** — text painted in an invisible text-rendering mode (`Tr 3`/`7`):
  invisible on screen, fully extractable. *CRITICAL*.
- **`revision_history`** — content recoverable from an earlier incremental-update
  revision of the file. **The differentiator.** *CRITICAL* when earlier text
  diverges from current; *LOW* when updates exist but nothing diverged.

### Tier B — cheap, high-signal wins
- **`embedded_files`** — embedded attachments that hand over raw data wholesale.
  *HIGH*.
- **`metadata`** — Info-dictionary and XMP fields (author, software, custom keys)
  retained independently of page content. *MEDIUM* for identity/custom fields,
  *INFO* for software/date fields.
- **`redact_annotations`** — `/Redact` annotations that were *marked but never
  applied* (the content is still present, sometimes with the intended overlay
  text stored in the annotation). *CRITICAL*. Other text-bearing annotations are
  *INFO*.

### Tier C — deferred to fast-follow (architecture supports; v1 omits)
Outline/bookmark, hyperlink, and page-label strings; EXIF/XMP inside *embedded
images*; full XMP history parsing. Each is "add one more `Detector` subclass."

## 4. Architecture

```
            ┌──────────────────────────────────────────────┐
            │                 PDFDocument                   │
            │  raw_bytes  +  pikepdf model  +  pdfminer      │
            │  (parsed once, shared, read-only)             │
            └──────────────────────────────────────────────┘
                       ▲ analyze(doc) -> [Finding]
   ┌───────────────────┼───────────────────────────────────┐
   │ Detector subclasses (one isolated unit per vector)     │
   │ covered_text · hidden_text · revision_history ·        │
   │ embedded_files · metadata · redact_annotations         │
   └───────────────────┬───────────────────────────────────┘
                       │  (each wrapped in try/except)
                   ┌───▼────┐      ┌──────────────┐
                   │ Engine │ ───> │    Report    │
                   └────────┘      │ findings +   │
                                   │ detector_errors
                                   └──────┬───────┘
                          ┌──────────────┴──────────────┐
                      to_json (contract)          format_cli (human)
```

Key decisions:

- **Parse once, share.** A single `PDFDocument` holds three consistent views: the
  **original raw bytes** (kept deliberately — see §5.1), the **pikepdf** object
  model (xref, attachments, metadata, content-stream tokens), and lazily-parsed
  **pdfminer.six** glyph geometry.
- **Detectors are isolated and uniform.** Every detector implements
  `analyze(doc) -> list[Finding]`. They never print or format. This makes them
  individually unit-testable and makes Tier C a one-file change.
- **The Engine isolates failure.** Each detector runs inside its own try/except;
  an exception becomes a recorded `detector_errors` entry, not a crashed scan. A
  partial report beats a stack trace — this is the core stability property.
- **Reporting is separate from detection.** `to_json` is the stable contract a
  future MCP/web frontend consumes unchanged; `format_cli` is the human view.

**Stack:** pikepdf 10.x (object model / xref / attachments / metadata / content
tokens), pdfminer.six (glyph geometry), reportlab (fixtures only), pytest.

## 5. The two algorithmic centerpieces

### 5.1 Revision-history recovery (the differentiator)

A PDF grows by *appending* incremental updates; the original bytes are never
rewritten, only added to, and **each appended revision ends with `%%EOF`**. That
single fact gives a clean recovery algorithm without hand-writing an xref parser:

1. Find every `%%EOF` offset in the raw bytes. *N* markers ⇒ *N* document states.
2. For each earlier state, take `raw_bytes[:eof_end]` — this byte prefix is itself
   a complete, loadable earlier version of the document — and extract its text.
3. Diff each earlier revision's tokens against the **current** (final) text. Any
   token present earlier but absent now is recovered content the latest revision
   was trying to hide.

This is why the document context keeps the *original* bytes: qpdf/pikepdf
normalise on load and collapse exactly the incremental structure this depends on.

**Known limitation (documented):** linearised PDFs and some malformed updates do
not truncate to a valid prefix. This is caught per-revision and skipped rather
than failing the scan. A future hardening is a proper `startxref`→`/Prev` chain
walk reconstructing the object table as-of each revision (handles linearised and
object-stream xref cases); the truncation method covers the common appended-update
case that actually burns people, and degrades gracefully otherwise.

### 5.2 Glyph-coverage detection

From pdfminer geometry, collect every character bounding box on a page and every
"cover" candidate — a filled dark rectangle (`LTRect` whose non-stroking colour
reads as near-black) or an image region. Any character whose centre falls inside a
cover is reported, with the recovered string as evidence. Dark-rect covers are
*CRITICAL*; image covers are *HIGH*.

**Known limitation (documented):** v1 treats any character under a dark rect as
covered rather than strictly checking content-stream z-order, and this overlaps a
known patent on text-rectangle intersection (USPTO 11550934). The leaky case —
text drawn then boxed — is exactly what this catches; the rare false positive is a
dark design element legitimately over decorative text. Novelty for the project
comes from combining this with the revision and hidden-text vectors and the
fail-closed reporting posture, not from coverage detection alone. A future
precision booster is render-the-page-and-sample-dark-pixels.

## 6. Findings & report model

`Finding(vector, severity, description, page?, bbox?, evidence?, recommendation?)`.
`Severity` is an ordered `IntEnum` (`INFO=0 … CRITICAL=4`) so the numeric value
drives both sorting and CI exit codes. `evidence` is the *recovered content* — the
proof, not a restatement that risk exists. `Report` aggregates findings, computes
`worst_severity`, sorts worst-first, and serialises to the JSON contract.

## 7. CLI

```
pdfaudit scan FILE [--json] [--only VEC,VEC] [--fail-on LEVEL] [--no-color]
pdfaudit list-vectors
```

Exit codes are CI-oriented: **0** = clean / below threshold, **2** = a finding at
or above `--fail-on` (default `high`), **1** = usage / I/O error. So
`pdfaudit scan report.pdf` is a drop-in release gate.

## 8. Testing

A generated fixture corpus (no committed binaries) with one PDF per vector plus
**clean controls** that must produce no leak-vector findings — false-positive
protection is treated as equal in importance to detection. The incremental-update
fixture is hand-assembled at the byte level (real libraries would normalise away
the multi-revision structure under test), so it authentically exercises the
revision-recovery path with a correct `/Prev` chain.

Coverage (35 tests): per-detector recovery (each fixture must surface its planted
secret at the expected severity), clean-control quietness, cross-contamination
guards, engine isolation (a deliberately-throwing detector must not sink the
scan), model/severity/serialisation, reporter output, and CLI exit-code logic.

## 9. Roadmap

- **v1.1 (Tier C):** outline/link/page-label string detectors; embedded-image EXIF.
- **v1.2:** proper xref-chain revision reconstruction (linearised / xref-stream).
- **v1.3:** optional render-and-sample pass to cut covered-text false positives;
  optional OCR pass to compare a scanned image against its text layer.
- **v2 (separate effort):** a *verified* redactor that uses this auditor as its
  fail-closed acceptance test — redact, then re-audit, and refuse to emit a file
  that still leaks.
- **Frontends:** MCP server and/or web UI consuming the unchanged JSON contract.

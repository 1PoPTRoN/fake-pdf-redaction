# pdfaudit

A read-only auditor that detects **recoverable content behind PDF "redactions."**
It never redacts or modifies anything — it finds the data your black boxes, blurs,
and "deletions" left behind, and shows it to you as evidence.

The premise: most redaction operates on the *presentation layer* (a rectangle is
drawn over text) while the *data layer* (the actual characters) is untouched.
`pdfaudit` works at the data layer and proves whether the protection actually holds.

## What's in this repo

| Path | What it is |
|---|---|
| [`src/pdfaudit/`](src/pdfaudit/) | The auditor **library + `pdfaudit` CLI** (Python, read-only). The core. |
| [`backend/`](backend/) | A **FastAPI service** wrapping the library: upload a PDF → JSON report or a one-page PDF summary. See [`backend/README.md`](backend/README.md). |
| [`frontend/`](frontend/) | A **React + Vite UI** — drop a PDF in the browser and see what your redactions left behind. See [`frontend/README.md`](frontend/README.md). |
| [`tests/`](tests/) | The library test suite. The generated fixture corpus *is* the executable spec. |

You can use just the CLI, embed the library, or run the full web app — they all
sit on the same detection engine.

## Install (CLI / library)

```bash
pip install -e .            # from a clone
pip install -e ".[dev]"     # + fixtures & tests
```

Requires Python ≥ 3.10. Core dependencies: `pikepdf`, `pdfminer.six`, `defusedxml`.

## Usage

```bash
pdfaudit scan document.pdf                              # human-readable report
pdfaudit scan document.pdf --json                       # machine-readable (stable contract)
pdfaudit scan document.pdf --only covered_text,metadata # run specific detectors
pdfaudit scan document.pdf --fail-on high               # CI release gate
pdfaudit list-vectors                                   # list detectors
```

**Exit codes** (drop-in CI gate): `0` clean / below threshold **and** every detector
ran · `2` a finding at or above `--fail-on` (default `high`) · `3` scan incomplete —
a detector errored, so "clean" can't be certified (suppress with `--no-fail-on-error`)
· `1` usage / I/O error.

### As a library

```python
from pdfaudit import Engine

report = Engine().scan("document.pdf")
print(report.worst_severity)
for f in report.by_severity():
    print(f.severity.label, f.vector, "->", f.evidence)
```

### Web UI

A browser front end lives in [`backend/`](backend/) (FastAPI) and
[`frontend/`](frontend/) (React). In two terminals:

```bash
# 1) backend  → http://127.0.0.1:8001     (see backend/README.md)
cd backend && uv run uvicorn app.main:app --port 8001

# 2) frontend → http://localhost:5174      (see frontend/README.md)
cd frontend && npm install && npm run dev
```

## What it detects

| Vector | What it catches | Severity |
|---|---|---|
| `covered_text` | Extractable text under any **opaque cover** — a filled box of any colour (incl. white-out / Separation / pattern fills) or an image | CRITICAL / HIGH |
| `hidden_text` | Text rendered to nothing: invisible render mode (`Tr 3`/`7`, incl. inside Form XObjects), or hidden by **colour** (white-on-white), **near-zero size**, or **off-page** position | CRITICAL |
| `revision_history` | Content recoverable from an **earlier incremental revision**; flags valid-but-unparseable prior revisions instead of passing them as clean | CRITICAL / HIGH / LOW |
| `embedded_files` | Embedded attachments carrying raw data — name tree (incl. `/Kids`), `/FileAttachment` annotations, and `/AF` associated files | HIGH |
| `metadata` | Info-dictionary and parsed **XMP** fields (author, software, custom keys), incl. XMP-only identity and per-page metadata | MEDIUM / INFO |
| `redact_annotations` | `/Redact` annotations marked but **never applied** — recovers the text under the mark, not just the placeholder | CRITICAL |

Each finding carries the **recovered content** as evidence, the page/location where
applicable, and a fix recommendation.

## Try it yourself

Generate the demo corpus (8 PDFs with planted leaks + clean controls) and scan the
headline one:

```bash
python tests/fixtures/gen_fixtures.py
pdfaudit scan tests/fixtures/corpus/incremental_redaction.pdf
```

The page reads `Settlement amount is [REDACTED] …`, yet pdfaudit reaches into the
file's revision history and recovers **`4200000 Acme Holdings`** — the figure that
was edited out. Nothing on the rendered page shows it.

Plant your own leak — the classic "black box over live text":

```bash
python - <<'EOF'
from reportlab.pdfgen.canvas import Canvas
c = Canvas("/tmp/leaky.pdf", pagesize=(612, 792))
c.setFont("Helvetica", 14)
c.drawString(72, 700, "Account 9988-7766 PIN 4242 — internal only")
c.setFillColorRGB(0, 0, 0)
c.rect(70, 694, 360, 22, fill=1, stroke=0)   # opaque box over the text
c.showPage(); c.save()
EOF
pdfaudit scan /tmp/leaky.pdf      # recovers 9988-7766 and 4242
```

A document that is *actually* clean (text removed, not just covered) returns no
findings and exit `0` — that round trip (redact → re-audit) is how a future
verified redactor would gate itself.

## How it works

A single read-only `PDFDocument` is parsed once and shared across independent
detectors (`analyze(doc) -> [Finding]`). The engine runs each detector in its own
`try/except`, so one malformed-PDF edge case becomes a recorded error, not a crashed
scan. Reporting (JSON / CLI) is kept separate from detection. The two non-obvious
detectors:

- **Revision history** — PDFs grow by *appending* updates that each end in `%%EOF`,
  so the bytes up to an earlier `%%EOF` are a loadable earlier version of the file.
  pdfaudit validates each revision boundary (via the `startxref`→xref back-pointer),
  then diffs earlier revisions against the current text to recover what a later
  "redaction" tried to hide.
- **Covered text** — pdfminer glyph geometry flags characters whose box *overlaps*
  an opaque cover: a filled rectangle of any colour (black, white-out, or a
  Separation/pattern fill) or an image. The text is invisible but still present in
  the content stream.

## Tests

```bash
python -m pytest -q                 # library suite
cd backend && uv run pytest -q      # API suite
cd frontend && npm run build        # type-check + build the UI
```

The library's fixture corpus is generated, not committed — read
[`tests/fixtures/gen_fixtures.py`](tests/fixtures/gen_fixtures.py) to see exactly
what secret is planted in each PDF, then confirm the tool recovers *that* string.

## Scope

Detection only — read-only, no PDF writing. It does not redact, repair, or triage
malware. A future verified redactor would use this auditor as its fail-closed
acceptance test.
```

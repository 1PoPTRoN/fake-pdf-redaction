# Manual testing runbook

A hands-on walkthrough to convince yourself `pdfaudit` actually works — including
planting your own leak and watching the tool recover it. Every command is
copy-pasteable from the repo root.

## 0. Setup

```bash
pip install -e ".[dev]"      # installs pdfaudit + reportlab (for fixtures)
pdfaudit list-vectors        # sanity check the CLI is on PATH
```

You should see six vectors: `covered_text`, `hidden_text`, `revision_history`,
`embedded_files`, `metadata`, `redact_annotations`.

## 1. Generate the fixture corpus

```bash
python tests/fixtures/gen_fixtures.py
ls tests/fixtures/corpus/
```

Eight files: six leaky (one per vector) and two clean controls. These are
generated, not shipped, so you can read exactly what secret was planted in
`tests/fixtures/gen_fixtures.py` and then confirm the tool recovers *that exact
string*.

## 2. Scan each leaky fixture and confirm the recovered evidence

Run each scan and check the `recovered:` line against the "Expect to recover"
column. The point of an auditor is that it shows you the leaked bytes — so verify
the bytes, not just that a finding appeared.

```bash
pdfaudit scan tests/fixtures/corpus/box_over_text.pdf --no-color
pdfaudit scan tests/fixtures/corpus/invisible_text.pdf --no-color
pdfaudit scan tests/fixtures/corpus/incremental_redaction.pdf --no-color
pdfaudit scan tests/fixtures/corpus/embedded_file.pdf --no-color
pdfaudit scan tests/fixtures/corpus/metadata_leak.pdf --no-color
pdfaudit scan tests/fixtures/corpus/unapplied_redact.pdf --no-color
```

| Fixture | Vector fired | Expect to recover |
|---|---|---|
| `box_over_text` | `covered_text` (CRITICAL) | `...SSN123-45-6789...HIVpositive` |
| `invisible_text` | `hidden_text` (CRITICAL) | `...Robert Paulson badge 4242` |
| `incremental_redaction` | `revision_history` (CRITICAL) | `4200000 Acme Holdings` |
| `embedded_file` | `embedded_files` (HIGH) | `payroll.csv (44 bytes)` |
| `metadata_leak` | `metadata` (MEDIUM) | `Jane Insider`, `SEALED-2026-00042` |
| `unapplied_redact` | `redact_annotations` (CRITICAL) | `REDACTED` overlay text |

The headline demo is `incremental_redaction`: the page visibly reads
`Settlement amount is [REDACTED] ...`, yet the tool reaches into the file's
revision history and recovers `4200000 Acme Holdings` from the version before the
edit. Nothing on the rendered page shows that number.

## 3. Confirm the clean controls stay quiet (false-positive check)

A detector that screams on clean files is useless. Verify the controls:

```bash
pdfaudit scan tests/fixtures/corpus/clean_stripped.pdf --no-color   # zero findings
pdfaudit scan tests/fixtures/corpus/clean_simple.pdf  --no-color    # only INFO metadata
```

`clean_stripped` should report *no findings at all*. `clean_simple` should report
only INFO-level metadata (software/date fields) and must **not** fire any of the
six leak vectors.

## 4. Verify CI exit codes

The exit code is what makes this a release gate. Check it directly:

```bash
pdfaudit scan tests/fixtures/corpus/clean_stripped.pdf      >/dev/null; echo "exit=$?"  # -> 0
pdfaudit scan tests/fixtures/corpus/box_over_text.pdf       >/dev/null; echo "exit=$?"  # -> 2
pdfaudit scan tests/fixtures/corpus/clean_simple.pdf        >/dev/null; echo "exit=$?"  # -> 0 (INFO < high)
pdfaudit scan tests/fixtures/corpus/clean_simple.pdf --fail-on info >/dev/null; echo "exit=$?"  # -> 2
```

`0` = clean or below threshold, `2` = something at/above `--fail-on` (default
`high`), `1` = usage/IO error.

## 5. Plant your own leak (the convincing test)

This is the test that proves it on *your* tooling, not mine.

### Option A — any PDF editor / word processor (the realistic failure)

1. Open LibreOffice Draw, Word, Google Docs, or any PDF editor.
2. Type a line with a fake secret, e.g. `Account 9988-7766 PIN 4242`.
3. Draw a **filled black rectangle** on top of the text (the way most people
   "redact"). Do **not** delete the text — just cover it.
4. Export / print to PDF as `~/my_leaky.pdf`.
5. Scan it:

```bash
pdfaudit scan ~/my_leaky.pdf --no-color
```

You should get a `covered_text` CRITICAL finding that recovers `9988-7766` and
`4242`. The box hid it from your eyes; the characters were never removed.

### Option B — reproducible one-liner

```bash
python - << 'EOF'
from reportlab.pdfgen.canvas import Canvas
c = Canvas("/tmp/my_leaky.pdf", pagesize=(612, 792))
c.setFont("Helvetica", 14)
c.drawString(72, 700, "Account 9988-7766 PIN 4242 — internal only")
c.setFillColorRGB(0, 0, 0)
c.rect(70, 694, 360, 22, stroke=0, fill=1)   # black box over the text
c.showPage(); c.save()
EOF
pdfaudit scan /tmp/my_leaky.pdf --no-color
```

## 6. Confirm a *properly* handled PDF comes back clean

Now do it right and confirm the tool agrees:

```bash
python - << 'EOF'
from reportlab.pdfgen.canvas import Canvas
c = Canvas("/tmp/properly_clean.pdf", pagesize=(612, 792))
c.setAuthor(""); c.setTitle(""); c.setSubject("")   # don't leak via metadata
c.setFont("Helvetica", 14)
c.drawString(72, 700, "Account [REMOVED] PIN [REMOVED] — internal only")  # text actually removed
c.showPage(); c.save()
EOF
pdfaudit scan /tmp/properly_clean.pdf --no-color; echo "exit=$?"   # -> no covered_text finding
```

If you run a *real* redaction tool (e.g. Acrobat's "Apply Redactions", or
flattening the page to an image), re-scanning the output should likewise show no
`covered_text` / `hidden_text` finding. That round-trip — redact, then re-audit —
is exactly how a future verified redactor would gate itself.

## 7. Try a "known-bad" style document

The realistic known-bad is a document "redacted" by a non-expert with drawn boxes
— which is precisely Option A above. If you have any real PDF where someone
covered text with a black rectangle (a marked-up contract, a shared form), scan it
and confirm the tool recovers the text. Use your own files here; avoid testing on
documents containing other people's sensitive personal data.

## 8. Graceful degradation (the stability check)

The tool should never dump a traceback on bad input. There are two distinct
behaviours, both worth seeing.

**(a) A file that can't be parsed as a PDF at all** — clean one-line error, exit
`1`, no traceback:

```bash
printf 'this is not a pdf' > /tmp/bad.pdf
pdfaudit scan /tmp/bad.pdf; echo "exit=$?"     # -> "Could not open PDF: ...", exit 1
```

**(b) A file that opens but is damaged enough to defeat some detectors** — the
failing detectors are recorded under `detector_errors` while the rest still run
and the scan completes. This is the isolation property: one detector choking never
sinks the whole scan.

```bash
# Lop ~20 bytes off the tail of a good fixture so its content stream is damaged
# but pikepdf can still recover the document structure:
src=tests/fixtures/corpus/metadata_leak.pdf
head -c $(( $(wc -c < "$src") - 20 )) "$src" > /tmp/damaged.pdf
pdfaudit scan /tmp/damaged.pdf --json | python -m json.tool | grep -A4 detector_errors
```

You should see the geometry-based detectors (`covered_text`, `hidden_text`) listed
in `detector_errors`, yet the metadata findings still come through and no
traceback is printed. The detector-isolation guarantee is also asserted directly
in `tests/test_engine.py::test_broken_detector_does_not_sink_the_scan`.

## 9. Per-detector isolation while debugging

`--only` runs a single detector, which is handy when you want to see exactly what
one vector reports:

```bash
pdfaudit scan tests/fixtures/corpus/box_over_text.pdf --only covered_text --json
pdfaudit scan tests/fixtures/corpus/incremental_redaction.pdf --only revision_history --no-color
```

## 10. Run the automated suite

Everything above is also asserted in the test suite:

```bash
python -m pytest -q
```

Expected: **35 passed**. The suite generates its own corpus in a temp directory,
so it is independent of the files you created here.

---

### Quick interpretation guide

- **CRITICAL** — content that was meant to be gone was recovered (covered text,
  invisible text, prior-revision text, unapplied redaction). Treat as a real leak.
- **HIGH** — raw data exposure that bypasses page redaction (embedded files,
  image-covered text).
- **MEDIUM** — identity/custom metadata that survives page redaction.
- **INFO** — benign software/date metadata; surfaced for completeness, not a leak.
- **`detector_errors` populated** — one or more detectors hit a problem on this
  file; the rest still ran. Re-run with `--only <vector>` to investigate.

# fake-pdf-redaction

You blacked something out in a PDF. Is it actually gone? Probably not.

This is a read-only auditor that checks PDFs for recoverable content behind redactions. Six detectors run against a document and tell you exactly what leaked, with the recovered bytes in the `evidence` field. It does not modify files. It does not phone home.

## What it catches

- `covered_text` — text under a black box that's still extractable
- `hidden_text` — white-on-white, zero-size fonts, text behind images
- `revision_history` — content from earlier PDF revisions that an incremental update was supposed to remove
- `embedded_files` — attachments the redaction didn't touch
- `metadata` — author, title, XMP fields that shouldn't be there
- `redact_annotations` — redaction annotations that don't actually redact anything

Pick a subset with `--only`.

## The three layers

The repo is a monorepo. Each layer is independent and you can use any of them on its own.

### 1. Python library and CLI (`src/pdfaudit/`)

```bash
uv sync
uv run pdfaudit scan some.pdf
```

Exit codes drop into CI as-is:

- `0` — clean, or below your threshold
- `2` — a finding at or above `--fail-on` (default: `high`)
- `3` — a detector errored, so "clean" can't be certified. Suppress with `--no-fail-on-error` if you trust partial scans
- `1` — usage or I/O error

JSON is one flag away: `pdfaudit scan some.pdf --json`. Need a stricter gate? `--fail-on medium`. Want a memory cap so a decompression bomb doesn't kill the runner? `--max-memory 1024`.

### 2. FastAPI backend (`backend/`)

The same engine, served over HTTP. Four endpoints:

- `GET  /api/v1/health` — liveness
- `GET  /api/v1/vectors` — detector names with one-line descriptions
- `POST /api/v1/scan` — multipart upload, JSON report back
- `POST /api/v1/scan/pdf` — same, but renders a one-page summary PDF for download

```bash
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --port 8001
```

### 3. React frontend (`frontend/`)

Vite + TypeScript + Tailwind, neubrutalism styling. Three states: boot loader, home with dropzone, report. Confetti fires only on a clean scan — leaking feels wrong to celebrate.

```bash
cd frontend
npm install
npm run dev   # http://localhost:5174
```

The Vite dev server proxies `/api/*` to the backend on `:8001`.

## Quick demo

If you don't have a real PDF to test, this is the smallest path to a finding:

```python
# make_boxed.py
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("boxed.pdf", pagesize=letter)
c.setFont("Helvetica", 14)
c.drawString(72, 720, "SSN123-45-6789")
c.setFillColorRGB(0, 0, 0)
c.rect(70, 715, 200, 18, fill=1, stroke=0)
c.showPage()
c.save()
```

Then:

```bash
uv run pdfaudit scan boxed.pdf
```

You should see a `critical` finding from `covered_text` with the SSN in `evidence`. That black rectangle didn't redact anything; the text is still sitting in the content stream, fully selectable.

## Privacy

Read-only. No file storage. No telemetry. No auth. The backend writes uploads to a temp file and deletes it after scanning. The browser never talks to anything except your local backend through the Vite proxy.

## Layout

```
fake-pdf-redaction/
├── src/pdfaudit/      # Python library and CLI
├── backend/           # FastAPI service
├── frontend/          # React UI
├── tests/             # pytest suite (covers all six detectors)
├── pyproject.toml     # workspace
└── uv.lock
```

## Tests

```bash
uv run pytest -v
```

The fixture corpus covers the canonical redaction mistakes: black box over text, white text on white, tiny fonts, leftover incremental updates, hidden attachments, and metadata leaks.

## License

MIT.

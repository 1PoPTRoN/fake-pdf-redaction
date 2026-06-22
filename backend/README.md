# PDF Redaction Auditor — Backend

FastAPI wrapper around [`pdfaudit`](../) (the sibling Python CLI). Upload a
PDF, get back a JSON report of recoverable content behind redactions.

Privacy-first: read-only auditor, no file storage, no auth.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/api/v1/health` | liveness |
| `GET`  | `/api/v1/vectors` | list detector names + one-line descriptions |
| `POST` | `/api/v1/scan` | multipart `file` + optional `only` (csv) → JSON `Report` |
| `POST` | `/api/v1/scan/pdf` | same but renders a one-page summary PDF for download |

## Run

```bash
# from this directory (backend/)
uv sync --extra dev
uv run uvicorn app.main:app --port 8001
```

The frontend (Vite dev server on `:5174`) proxies `/api/*` to this service.

## Test

```bash
uv run pytest -v
```

## Manual smoke test

Start the server in one terminal:

```bash
uv run uvicorn app.main:app --port 8001
```

In another terminal:

```bash
# 1. health
curl http://127.0.0.1:8001/api/v1/health

# 2. list detectors
curl http://127.0.0.1:8001/api/v1/vectors

# 3. scan a PDF (any PDF)
curl -X POST http://127.0.0.1:8001/api/v1/scan \
  -F "file=@/path/to/some.pdf" | jq

# 4. scan and download a one-page PDF summary
curl -X POST http://127.0.0.1:8001/api/v1/scan/pdf \
  -F "file=@/path/to/some.pdf" -o audit.pdf
```

To verify the engine actually finds leaks, generate a quick fixture with
reportlab (the same one the test suite uses):

```python
# make_boxed.py
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("boxed.pdf", pagesize=letter)
c.setFont("Helvetica", 14)
c.drawString(72, 720, "SSN123-45-6789")  # visible (extractable) text
c.setFillColorRGB(0, 0, 0)
c.rect(70, 715, 200, 18, fill=1, stroke=0)  # black cover over the secret
c.showPage(); c.save()
```

Then scan `boxed.pdf` — the response should include a `critical` finding
from the `covered_text` vector with the SSN in `evidence`.

## Error responses

| Code | When |
|---|---|
| `400` | Empty file, missing filename, bad JSON in form fields |
| `413` | Uploaded file exceeds `PDFAUDIT_MAX_FILE_BYTES` (default 100 MB) |
| `415` | Wrong content type, or PDF is encrypted |
| `422` | PDF is corrupt / unparseable, or FastAPI couldn't validate the form |

## Configuration

Environment variables (all optional):

| Var | Default | Effect |
|---|---|---|
| `PDFAUDIT_MAX_FILE_BYTES` | `104857600` (100 MB) | Per-file upload cap |
| `PDFAUDIT_DETECTOR_TIMEOUT` | `60.0` (seconds) | Per-detector time limit (SIGALRM-based) |

## Layout

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, error handlers, CORS
│   ├── config.py            # runtime limits (env-overridable)
│   ├── schemas.py           # Pydantic mirrors of pdfaudit.Report / Finding
│   ├── routes/
│   │   ├── vectors.py       # GET /api/v1/vectors
│   │   └── scan.py          # POST /api/v1/scan and /scan/pdf
│   └── services/
│       ├── scanner.py       # write upload → temp file → Engine().scan()
│       └── pdf_report.py    # render the one-page summary PDF
├── tests/
│   ├── conftest.py          # client fixture + in-memory PDF helpers
│   ├── test_health.py
│   ├── test_vectors.py
│   ├── test_scan.py
│   └── test_scan_pdf.py
├── pyproject.toml           # [tool.uv.sources] pdfaudit = { path = ".." }
└── README.md
```

# PDF Redaction Auditor — Frontend

Neubrutalism React UI for the [`pdfaudit`](../) FastAPI backend. Upload a
PDF, see exactly what your redactions left behind. Privacy-first (read-only
auditor, no file storage).

## Run

In one terminal, start the backend on `:8001`:

```bash
cd ../backend
uv sync --extra dev
uv run uvicorn app.main:app --port 8001
```

In another, start this frontend on `:5174`:

```bash
npm install
npm run dev
```

Open <http://localhost:5174>. The Vite dev server proxies `/api/*` to
`http://127.0.0.1:8001` (see `vite.config.ts`).

## Build

```bash
npm run build      # tsc -b && vite build  →  dist/
npm run preview    # serve the built dist on :4174
```

## Stack

- Vite 6 + React 18 + TypeScript 5
- Tailwind 3 (Neubrutalism tokens — see `tailwind.config.js`)
- `react-dropzone` for the file upload

No backend calls happen in the browser; everything goes through the FastAPI
service via the Vite proxy.

## Page flow

1. **BootLoader** (`pages/BootLoader.tsx`) — full-screen intro with a
   spinning floppy, glitchy headline that flips through
   "BOOTING → LOADING DETECTORS → SHARPENING X-RAY → READY", chunky
   stepped progress bar, and a flickering LIVE dot. Auto-dismisses after
   the staged animation.
2. **Home** (`pages/Home.tsx`) — landing page with marquee tape
   (`AUDIT YOUR REDACTIONS * 100% LOCAL * SEE WHAT YOUR BLACK BOXES LEFT
   BEHIND`), the **AUDIT / PDFs** hero with three rotated badges
   (READ-ONLY, EVIDENCE-FIRST, OPEN SOURCE), three feature boxes
   (SEES THROUGH BLACK BOXES, SHOWS THE BYTES, PROVES THE LEAK), a
   single-file dropzone, the file card, and a yellow **AUDIT NOW**
   button with a counter chip.
3. **Report** (`pages/Report.tsx`) — findings page: a giant worst-severity
   stamp at the top (CLEAN on a clean scan, pink CRITICAL when leaks are
   found), per-severity counts, detector-errors banner if any, a
   `FindingCard` per finding with the recovered evidence in a monospace
   box, and three action buttons (Download report PDF, Save, Audit
   another). Confetti only fires on a clean scan — leaking feels wrong to
   celebrate.

## Keyboard

- `A` — run the audit (when a file is loaded)

## Layout

```
src/
├── App.tsx                  # 3-state machine: booting → home → report
├── main.tsx                 # React entry
├── index.css                # Tailwind + hand-rolled keyframes
├── lib/
│   ├── api.ts               # fetch wrappers + APIError
│   └── types.ts             # AuditReport / Finding / Severity mirrors
├── pages/
│   ├── BootLoader.tsx
│   ├── Home.tsx
│   └── Report.tsx
└── components/
    ├── GridOverlay.tsx      # full-page grid + corner halftones
    ├── CornerAccents.tsx    # 100% FREE + SAVE badges
    ├── Marquee.tsx          # scrolling privacy tape
    ├── Badge.tsx            # rotated tag chip
    ├── FeatureBox.tsx       # one of the 3 hero feature cards
    ├── Dropzone.tsx         # single-PDF drop zone
    ├── AuditButton.tsx      # the big yellow AUDIT NOW button
    ├── Toast.tsx            # error / success toast
    ├── ScanningLoader.tsx   # in-progress overlay
    ├── Confetti.tsx         # confetti burst (used only on CLEAN)
    ├── SeverityBadge.tsx    # severity chip (critical/high/medium/low/info)
    ├── FindingCard.tsx      # one finding with evidence + fix
    ├── ReportSummary.tsx    # worst-severity stamp + counts
    └── icons.tsx            # SVG icon set
```

## Ports

| Service      | Port |
|---|---|
| FastAPI backend | `8001` |
| Vite dev server | `5174` |
| Vite preview    | `4174` |

The merger project (sibling `pdf-merger/`) uses `8000` / `5173` / `4173`,
so you can run both projects side-by-side without conflicts.

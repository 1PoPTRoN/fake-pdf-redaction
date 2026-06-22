/** Tiny fetch wrappers for the auditor backend. */
import type { AuditReport, VectorInfo } from "./types";

// In dev the Vite proxy on /api forwards to the local backend (see vite.config.ts).
// In production set VITE_API_BASE to the deployed backend origin, e.g.
//   https://pdfaudit-api.onrender.com/api/v1
// The fallback keeps `npm run dev` working with zero config.
const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

export class APIError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Throw a rich APIError for a non-2xx response (using the {error} body if any),
 *  otherwise return the response. */
async function ensureOk(r: Response): Promise<Response> {
  if (r.ok) return r;
  let detail = `${r.status} ${r.statusText}`;
  try {
    const j = await r.json();
    if (j?.error) detail = j.error;
  } catch {
    // non-JSON error body; keep the status-line detail
  }
  throw new APIError(r.status, detail);
}

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const r = await ensureOk(
    await fetch(`${API_BASE}${path}`, { method: "POST", body: form }),
  );
  return r.json() as Promise<T>;
}

async function postFormBlob(path: string, form: FormData): Promise<Blob> {
  const r = await ensureOk(
    await fetch(`${API_BASE}${path}`, { method: "POST", body: form }),
  );
  return r.blob();
}

export async function fetchVectors(): Promise<VectorInfo[]> {
  const r = await ensureOk(await fetch(`${API_BASE}/vectors`));
  const j = (await r.json()) as { vectors: VectorInfo[] };
  return j.vectors;
}

/** Backend health snapshot returned by GET /api/v1/health.
 *  Mirrors backend/app/schemas.py:HealthResponse. */
export type BackendStatus = "ok" | "warming" | "degraded";

export type HealthSnapshot = {
  status: BackendStatus;
  detail: string;
  vectors_ready: number;
};

/** Reachability + readiness check for the home-page status pill.
 *
 *  Returns one of four outcomes so the pill can distinguish a backend that is
 *  simply slow to respond from one that is genuinely offline:
 *    - {kind: "ok",       ...}     — backend is up and warm
 *    - {kind: "warming",  ...}     — backend is up but the detector engine is
 *                                    still importing (cold start). The user
 *                                    should wait, not retry.
 *    - {kind: "degraded", ...}     — backend responded but warmup failed
 *    - {kind: "down"}              — network error or non-2xx with no body
 *
 *  Never throws. */
export async function fetchHealth(): Promise<
  | { kind: "ok"; snapshot: HealthSnapshot; latency: number }
  | { kind: "warming"; snapshot: HealthSnapshot; latency: number }
  | { kind: "degraded"; snapshot: HealthSnapshot; latency: number }
  | { kind: "down" }
> {
  const start = performance.now();
  try {
    const r = await fetch(`${API_BASE}/health`, { method: "GET", cache: "no-store" });
    const latency = Math.round(performance.now() - start);
    // Read the body regardless of status — the backend uses 503 + status:warming
    // to mean "alive but not ready yet", which is a perfectly valid state to
    // show on the pill (as LAUNCHING, not DOWN).
    let body: HealthSnapshot = { status: "warming", detail: "", vectors_ready: 0 };
    try {
      body = (await r.json()) as HealthSnapshot;
    } catch {
      // Body wasn't JSON; fall through with the default warming state.
    }
    if (body.status === "ok") return { kind: "ok", snapshot: body, latency };
    if (body.status === "warming") return { kind: "warming", snapshot: body, latency };
    if (body.status === "degraded") return { kind: "degraded", snapshot: body, latency };
    // Unknown body shape — treat as down so the user gets the wake link.
    return { kind: "down" };
  } catch {
    return { kind: "down" };
  }
}

/** Backend origin (no path) — used to render the "wake it up" link when the
 *  service is asleep on a free-tier host. Falls back to the current origin in
 *  dev so the link still goes somewhere sensible. */
export function backendOrigin(): string {
  try {
    return new URL(API_BASE).origin;
  } catch {
    return window.location.origin;
  }
}

export async function scanPdf(
  file: File,
  only?: string[],
): Promise<AuditReport> {
  const form = new FormData();
  form.append("file", file, file.name);
  if (only && only.length) {
    form.append("only", only.join(","));
  }
  return postForm<AuditReport>("/scan", form);
}

export async function scanPdfToFile(
  file: File,
  only?: string[],
): Promise<{ blob: Blob; filename: string }> {
  const form = new FormData();
  form.append("file", file, file.name);
  if (only && only.length) {
    form.append("only", only.join(","));
  }
  const blob = await postFormBlob("/scan/pdf", form);
  const base = file.name.replace(/\.pdf$/i, "");
  return { blob, filename: `${base}-audit.pdf` };
}
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
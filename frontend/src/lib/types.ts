/** Wire types for the auditor API. Mirrors `pdfaudit.Report.to_dict()`. */

export type Severity = "info" | "low" | "medium" | "high" | "critical";

export type Finding = {
  vector: string;
  severity: Severity;
  description: string;
  page: number | null;
  bbox: [number, number, number, number] | null;
  evidence: string | null;
  recommendation: string | null;
};

export type AuditReport = {
  path: string;
  worst_severity: Severity | null;
  finding_count: number;
  findings: Finding[];
  detector_errors: Record<string, string>;
  /** True when one or more detectors errored — a clean-looking result is then
   *  only "partial", not trustworthy-clean. */
  incomplete?: boolean;
};

/** A scan is only truly clean when nothing was found AND every detector ran. */
export function isReportClean(report: AuditReport): boolean {
  return (
    report.worst_severity === null &&
    !report.incomplete &&
    Object.keys(report.detector_errors).length === 0
  );
}

export function isReportIncomplete(report: AuditReport): boolean {
  return (
    Boolean(report.incomplete) ||
    Object.keys(report.detector_errors).length > 0
  );
}

/** Human-readable byte size, e.g. 2048 -> "2.0 KB". */
export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export type VectorInfo = {
  name: string;
  description: string;
};

export type AuditResponse = {
  /** The JSON report from /scan. */
  report: AuditReport;
  /** PDF blob returned from /scan/pdf (the same scan, second pass). */
  pdfBlob: Blob;
  pdfFilename: string;
};

export type LocalFile = {
  id: string;
  file: File;
  name: string;
  size: number;
  error: string | null;
};
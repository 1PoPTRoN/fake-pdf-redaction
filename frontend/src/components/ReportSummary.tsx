import type { AuditReport, Severity } from "../lib/types";
import { isReportIncomplete } from "../lib/types";
import { SeverityBadge } from "./SeverityBadge";

type Props = {
  report: AuditReport;
};

const SEVERITY_RANK: Severity[] = ["critical", "high", "medium", "low", "info"];

function severityStampColor(sev: Severity) {
  switch (sev) {
    case "critical":
      return "bg-pink text-paper";
    case "high":
      return "bg-sun text-ink";
    case "medium":
      return "bg-sky text-paper";
    case "low":
      return "bg-leaf text-ink";
    case "info":
      return "bg-paper text-ink";
  }
}

/** Stamp label/color. A no-findings scan is only "CLEAN" when every detector ran;
 *  if a detector errored it is "PARTIAL" (a warning), never a clean green stamp. */
function stamp(report: AuditReport): { label: string; color: string } {
  if (report.worst_severity !== null) {
    return {
      label: report.worst_severity.toUpperCase(),
      color: severityStampColor(report.worst_severity),
    };
  }
  if (isReportIncomplete(report)) {
    return { label: "PARTIAL", color: "bg-sun text-ink" };
  }
  return { label: "CLEAN", color: "bg-leaf text-ink" };
}

export function ReportSummary({ report }: Props) {
  const counts: Record<Severity, number> = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    info: 0,
  };
  for (const f of report.findings) counts[f.severity]++;

  const { label: stampText, color: stampClass } = stamp(report);

  return (
    <div className="flex flex-col items-center gap-6">
      <h1
        className={[
          "brutal-stamp",
          "font-display uppercase leading-[0.85]",
          "tracking-tight",
          "border-5 border-ink shadow-brutalXl",
          "px-6 sm:px-10 py-3 sm:py-5",
          stampClass,
        ].join(" ")}
        style={{ fontSize: "clamp(2rem, 18vw, 8rem)" }}
      >
        {stampText}
      </h1>

      <div className="text-center">
        <p className="font-mono text-sm sm:text-base uppercase tracking-widest">
          audited
        </p>
        <p className="font-display text-2xl sm:text-3xl mt-1 break-all">
          {report.path}
        </p>
      </div>

      {/* Severity breakdown pills */}
      <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3">
        {SEVERITY_RANK.map((sev) => (
          <div
            key={sev}
            className={[
              "flex items-center gap-2",
              "border-3 border-ink shadow-brutalSm",
              "bg-paper text-ink",
              "px-3 py-1.5",
            ].join(" ")}
            style={{ opacity: counts[sev] === 0 ? 0.45 : 1 }}
          >
            <SeverityBadge severity={sev} size="sm" />
            <span className="font-display text-lg sm:text-xl">
              {counts[sev]}
            </span>
          </div>
        ))}
      </div>

      {/* Detector errors banner — only if any */}
      {Object.keys(report.detector_errors).length > 0 && (
        <div className="w-full max-w-2xl border-5 border-ink bg-pink text-paper p-4 sm:p-5 shadow-brutal brutal-shake">
          <p className="font-display uppercase text-base sm:text-lg tracking-wider">
            Detector errors (scan continued with partial coverage)
          </p>
          <ul className="mt-2 font-mono text-sm space-y-1">
            {Object.entries(report.detector_errors).map(([name, msg]) => (
              <li key={name}>
                <b>{name}</b>: {msg}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
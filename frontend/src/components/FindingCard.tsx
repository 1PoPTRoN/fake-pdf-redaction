import type { Finding } from "../lib/types";
import { SeverityBadge } from "./SeverityBadge";

type Props = {
  finding: Finding;
  index: number;
};

const VECTOR_LABEL: Record<string, string> = {
  covered_text: "COVERED TEXT",
  hidden_text: "HIDDEN TEXT",
  revision_history: "REVISION HISTORY",
  embedded_files: "EMBEDDED FILES",
  metadata: "METADATA",
  redact_annotations: "REDACT ANNOTATIONS",
};

function labelFor(vector: string) {
  return VECTOR_LABEL[vector] ?? vector.toUpperCase().replace(/_/g, " ");
}

export function FindingCard({ finding, index }: Props) {
  return (
    <article
      className="brutal-card relative border-3 border-ink shadow-brutal bg-paper"
      style={{
        // Stagger the stamp-in entrance by index.
        animation: `brutal-stamp 360ms cubic-bezier(.2,1.4,.3,1) ${Math.min(
          index * 80,
          1200,
        )}ms both`,
      }}
    >
      {/* Header strip */}
      <header className="flex flex-wrap items-center gap-3 p-4 sm:p-5 border-b-3 border-ink bg-paper">
        <span className="font-mono text-sm sm:text-base font-bold text-ink/60">
          #{String(index + 1).padStart(2, "0")}
        </span>
        <SeverityBadge severity={finding.severity} />
        <h3 className="font-display uppercase text-lg sm:text-xl tracking-wide">
          {labelFor(finding.vector)}
        </h3>
        {finding.page !== null && (
          <span className="ml-auto font-mono text-sm border-2 border-ink bg-sun text-ink px-2 py-0.5">
            p.{finding.page}
          </span>
        )}
      </header>

      {/* Body */}
      <div className="p-4 sm:p-5 flex flex-col gap-4">
        <p className="font-body text-base sm:text-lg leading-snug">
          {finding.description}
        </p>

        {/* Evidence — the whole point of the auditor. */}
        {finding.evidence && (
          <div>
            <p className="font-display text-xs uppercase tracking-widest mb-1.5">
              Recovered evidence
            </p>
            <pre
              className={[
                "font-mono text-sm sm:text-base whitespace-pre-wrap break-words",
                "border-3 border-ink bg-ink text-paper",
                "p-3 sm:p-4",
                "max-h-60 overflow-auto",
              ].join(" ")}
            >
              {finding.evidence}
            </pre>
          </div>
        )}

        {/* Recommendation */}
        {finding.recommendation && (
          <div className="border-l-5 border-sun pl-3">
            <p className="font-display text-xs uppercase tracking-widest mb-0.5">
              Fix
            </p>
            <p className="font-body text-sm sm:text-base">
              {finding.recommendation}
            </p>
          </div>
        )}
      </div>
    </article>
  );
}
import { useEffect, useState } from "react";
import { GridOverlay } from "../components/GridOverlay";
import { FloppyIcon } from "../components/icons";
import { Confetti } from "../components/Confetti";
import { FindingCard } from "../components/FindingCard";
import { ReportSummary } from "../components/ReportSummary";
import { Toast } from "../components/Toast";
import { scanPdfToFile } from "../lib/api";
import type { AuditReport } from "../lib/types";
import { isReportClean, formatBytes } from "../lib/types";

type Props = {
  report: AuditReport;
  file: File;
  onAnother: () => void;
};

export function Report({ report, file, onAnother }: Props) {
  const [confettiPlay, setConfettiPlay] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [downloadName, setDownloadName] = useState<string>("report-audit.pdf");
  const [toast, setToast] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  // Truly clean = nothing found AND every detector ran. A scan where a detector
  // errored is "partial", not clean — don't celebrate it as safe.
  const isClean = isReportClean(report);

  useEffect(() => {
    // Confetti only on a genuinely clean scan — celebrating leaked data (or a
    // partial scan we can't trust) feels wrong.
    if (!isClean) return;
    const t1 = setTimeout(() => setConfettiPlay(true), 60);
    const t2 = setTimeout(() => setConfettiPlay(false), 2200);
    const t3 = setTimeout(() => setConfettiPlay(true), 2700);
    const t4 = setTimeout(() => setConfettiPlay(false), 4800);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
    };
  }, [isClean]);

  const handleDownloadPdf = async () => {
    setDownloading(true);
    try {
      const { blob, filename } = await scanPdfToFile(file);
      const url = URL.createObjectURL(blob);
      setDownloadUrl(url);
      setDownloadName(filename);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "download failed";
      setToast(msg);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="relative">
      <GridOverlay />
      <Confetti play={confettiPlay} />

      <div className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 py-10 sm:py-16">
        <ReportSummary report={report} />

        {/* FILE CARD */}
        <div className="mt-10 sm:mt-14 border-5 border-ink shadow-brutalXl bg-paper p-6 sm:p-8 brutal-pulse">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-12 h-12 sm:w-16 sm:h-16 border-3 border-ink bg-ink text-paper flex items-center justify-center">
              <FloppyIcon className="w-7 h-7 sm:w-10 sm:h-10" />
            </div>
            <div className="min-w-0">
              <p className="font-display text-xl sm:text-2xl uppercase truncate" title={report.path}>
                {report.path}
              </p>
              <p className="font-mono text-sm">
                {formatBytes(file.size)} · {report.finding_count} finding{report.finding_count === 1 ? "" : "s"}
              </p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-4">
            <button
              type="button"
              onClick={handleDownloadPdf}
              disabled={downloading}
              className={[
                "brutal-press flex-1 text-center px-6 py-4",
                "border-5 border-ink shadow-brutalLg",
                "bg-sun text-ink",
                "font-display uppercase text-xl sm:text-2xl",
                downloading ? "opacity-60 cursor-wait" : "",
              ].join(" ")}
            >
              {downloading ? "Rendering…" : "Download report PDF"}
            </button>
            {downloadUrl && !downloading && (
              <a
                href={downloadUrl}
                download={downloadName}
                className="brutal-press text-center px-6 py-4 border-5 border-ink shadow-brutalLg bg-leaf text-ink font-display uppercase text-xl sm:text-2xl"
              >
                Save · {downloadName}
              </a>
            )}
            <button
              type="button"
              onClick={onAnother}
              className="brutal-press px-6 py-4 border-5 border-ink shadow-brutalLg bg-paper text-ink font-display uppercase text-xl sm:text-2xl"
            >
              Audit another
            </button>
          </div>
        </div>

        {/* FINDINGS */}
        {report.findings.length > 0 && (
          <section className="mt-12 sm:mt-16">
            <h2 className="font-display uppercase text-3xl sm:text-4xl mb-6 sm:mb-8 text-center">
              {report.finding_count} finding{report.finding_count === 1 ? "" : "s"}
            </h2>
            <div className="flex flex-col gap-5 sm:gap-6">
              {report.findings.map((f, idx) => (
                <FindingCard key={`${f.vector}-${idx}`} finding={f} index={idx} />
              ))}
            </div>
          </section>
        )}

        {/* CLEAN stamp */}
        {isClean && (
          <div className="mt-12 sm:mt-16 text-center">
            <p
              className="font-display uppercase bg-leaf border-5 border-ink shadow-brutalLg inline-block px-6 py-3 brutal-stamp"
              style={{ fontSize: "clamp(1.5rem, 7vw, 3rem)" }}
            >
              nothing to see here
            </p>
          </div>
        )}
      </div>

      <Toast message={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}
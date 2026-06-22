import { useEffect, useState } from "react";
import { Dropzone } from "../components/Dropzone";
import { AuditButton } from "../components/AuditButton";
import { Toast } from "../components/Toast";
import { Marquee } from "../components/Marquee";
import { FeatureBox } from "../components/FeatureBox";
import { Badge } from "../components/Badge";
import { GridOverlay } from "../components/GridOverlay";
import { CornerAccents } from "../components/CornerAccents";
import { BackendStatus } from "../components/BackendStatus";
import { ScanningLoader } from "../components/ScanningLoader";
import {
  FileIcon,
  SearchIcon,
  CheckIcon,
  FloppyIcon,
} from "../components/icons";
import { APIError, scanPdf } from "../lib/api";
import type { AuditReport, LocalFile } from "../lib/types";
import { formatBytes } from "../lib/types";

type Props = {
  onReport: (report: AuditReport, file: File) => void;
};

let _id = 0;
const nextId = () => `f${++_id}`;

export function Home({ onReport }: Props) {
  const [item, setItem] = useState<LocalFile | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const addFile = (file: File) => {
    // Replace any prior file — the auditor takes one PDF at a time.
    setItem({
      id: nextId(),
      file,
      name: file.name,
      size: file.size,
      error: null,
    });
  };

  const removeFile = () => setItem(null);

  const handleAudit = async () => {
    if (!item) {
      setToast("DROP A PDF FIRST");
      return;
    }
    setBusy(true);
    try {
      const report = await scanPdf(item.file);
      onReport(report, item.file);
    } catch (e) {
      const msg =
        e instanceof APIError
          ? e.message
          : e instanceof Error
            ? e.message
            : "AUDIT FAILED";
      setToast(msg);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "a" && item && !busy) {
        const target = e.target as HTMLElement | null;
        if (target && ["INPUT", "TEXTAREA"].includes(target.tagName)) return;
        handleAudit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // Re-bind only when the inputs the handler reads change, not on every render.
  }, [item, busy]);

  return (
    <div className="relative">
      <GridOverlay />
      <CornerAccents />

      <div className="relative z-10">
        <Marquee text="AUDIT YOUR REDACTIONS * READ-ONLY * NOTHING STORED * SEE WHAT YOUR BLACK BOXES LEFT BEHIND" />

        {/* HERO */}
        <section className="max-w-5xl mx-auto px-4 sm:px-6 pt-8 sm:pt-12 pb-6 text-center">
          <div className="flex flex-wrap justify-center gap-2 sm:gap-3 mb-6">
            <div className="landing-badge"><Badge color="leaf" rotate={-3}>READ-ONLY</Badge></div>
            <div className="landing-badge"><Badge color="sun" rotate={2}>EVIDENCE-FIRST</Badge></div>
            <div className="landing-badge"><Badge color="pink" rotate={-1}>OPEN SOURCE</Badge></div>
          </div>

          <h1 className="font-display uppercase leading-[0.85] tracking-tight text-[18vw] sm:text-[10rem]">
            <span className="inline-block landing-reveal-1">AUDIT</span>
            <br />
            <span className="inline-block bg-ink text-paper px-3 sm:px-5 mt-1 landing-reveal-2">
              PDFs
            </span>
          </h1>

          <p className="mt-6 max-w-2xl mx-auto font-body text-lg sm:text-2xl font-bold landing-reveal-3">
            Drop a PDF. We look under the boxes. You see exactly what your
            redactions <span className="inline-block bg-pink text-paper border-2 border-ink px-1.5">left behind</span>.
          </p>
        </section>

        {/* FEATURE ROW */}
        <section className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-8 grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-5">
          <div className="landing-feature">
            <FeatureBox
              color="sky"
              icon={<SearchIcon className="w-5 h-5 sm:w-6 sm:h-6" />}
              title="SEES THROUGH BLACK BOXES"
              subtitle="Six detectors. Covered text, hidden text, revision history, embedded files, metadata leaks, unapplied redact annotations."
            />
          </div>
          <div className="landing-feature">
            <FeatureBox
              color="pink"
              icon={<FileIcon className="w-5 h-5 sm:w-6 sm:h-6" />}
              title="SHOWS THE BYTES"
              subtitle="Every finding includes the recovered text in a monospace box — the proof, not the promise."
            />
          </div>
          <div className="landing-feature">
            <FeatureBox
              color="grape"
              icon={<CheckIcon className="w-5 h-5 sm:w-6 sm:h-6" />}
              title="PROVES THE LEAK"
              subtitle="Severity stamps. Per-finding fix advice. A downloadable one-page summary you can hand to legal."
            />
          </div>
        </section>

        {/* WORKSPACE */}
        <section className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
          <div className="landing-thud">
            <Dropzone onFile={addFile} disabled={busy} />
          </div>

          {item && (
            <div className="mt-8 sm:mt-10">
              <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4 px-1">
                <h2 className="font-display text-2xl sm:text-3xl uppercase">
                  1 FILE LOADED
                </h2>
                <p className="font-mono text-sm sm:text-base">
                  {formatBytes(item.size)}
                </p>
              </div>
              <div className="brutal-card relative flex items-stretch border-3 border-ink bg-paper shadow-brutal">
                {/* Drag-free single-file preview card */}
                <div className="flex-shrink-0 w-12 sm:w-14 self-stretch border-r-3 border-ink bg-sky text-paper flex items-center justify-center">
                  <FileIcon className="w-6 h-6" />
                </div>
                <div className="flex-1 min-w-0 py-2 sm:py-3 px-3 sm:px-4 flex flex-col justify-center">
                  <p className="font-display text-base sm:text-lg truncate" title={item.name}>
                    {item.name}
                  </p>
                  <p className="font-mono text-xs sm:text-sm">
                    PDF · {formatBytes(item.size)}
                  </p>
                  {item.error && (
                    <p className="font-body text-sm text-pink font-bold mt-1">
                      ! {item.error}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  aria-label="Remove file"
                  onClick={removeFile}
                  className="flex-shrink-0 w-12 sm:w-14 self-stretch border-l-3 border-ink bg-paper flex items-center justify-center hover:bg-pink hover:text-paper transition-colors"
                >
                  <span className="font-display text-2xl leading-none">×</span>
                </button>
              </div>
            </div>
          )}
        </section>

        {/* ACTION BAR */}
        <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-6">
            <p className="font-body text-base sm:text-lg font-bold max-w-md">
              {!item ? (
                <>
                  DROP A PDF TO BEGIN.{" "}
                  <span className="text-pink">READ-ONLY</span>. YOUR FILE IS SCANNED IN MEMORY AND DELETED RIGHT AFTER. NOTHING IS STORED.
                </>
              ) : (
                <>
                  <span className="text-leaf">READY!</span> HIT THE BIG YELLOW BUTTON TO RUN ALL SIX DETECTORS.
                </>
              )}
            </p>
            <AuditButton
              onClick={handleAudit}
              disabled={!item}
              busy={busy}
              loaded={!!item}
            />
          </div>
        </section>

        {/* BACKEND STATUS — sits just above the footer, centered */}
        <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-6 sm:pb-8 flex justify-center">
          <BackendStatus />
        </section>

        {/* FOOTER STRIP */}
        <footer className="border-t-3 border-ink bg-ink text-paper">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-3 font-mono text-xs sm:text-sm uppercase tracking-wider">
            <span className="flex items-center gap-2">
              <FloppyIcon className="w-4 h-4" /> AUDIT.PDF · v0.1
            </span>
            <span>BUILT WITH BRUTAL HONESTY</span>
          </div>
          {/* ATTRIBUTION ROW — kept below the main footer line so it doesn't
              compete with the primary CTA. Sits on the same dark band, right-
              aligned. Internship/contact context: who built it, who's it for,
              how to reach the author. */}
          <div className="border-t-2 border-paper/20">
            <div className="max-w-5xl mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-3 font-mono text-xs sm:text-sm">
              <a
                href="https://digitalheroesco.com"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 border-2 border-paper bg-paper text-ink font-display uppercase tracking-wider shadow-brutalSm hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all"
              >
                Built for Digital Heroes
                <span aria-hidden>↗</span>
              </a>
              <span className="text-paper/90">
                <a
                  href="https://www.linkedin.com/in/arp1traj/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:underline"
                >
                  Arpit Raj
                </a>
                <span className="text-paper/50"> · </span>
                <a
                  href="https://github.com/1PoPTRoN"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-paper/70 hover:underline"
                >
                  1PoPTRoN
                </a>
                <span className="text-paper/50"> · </span>
                <a
                  href="mailto:vrxn.arp1traj@gmail.com"
                  className="hover:underline"
                >
                  vrxn.arp1traj@gmail.com
                </a>
              </span>
            </div>
          </div>
        </footer>

        <Toast message={toast} onDismiss={() => setToast(null)} />
      </div>

      {busy && <ScanningLoader />}
    </div>
  );
}
/**
 * In-progress scan overlay. Shown over Home while /scan is uploading +
 * processing. Mirrors MergingLoader but with audit-flavored copy.
 */
import { useEffect, useState } from "react";
import { GridOverlay } from "./GridOverlay";
import { CornerAccents } from "./CornerAccents";
import { FloppyIcon } from "./icons";

const MESSAGES = [
  "UPLOADING…",
  "READING CONTENT STREAMS…",
  "CROSS-REFERENCING…",
  "PROBING COVERS…",
  "ALMOST DONE…",
];

export function ScanningLoader() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(
      () => setI((n) => (n + 1) % MESSAGES.length),
      700,
    );
    return () => clearInterval(t);
  }, []);

  return (
    <div className="fixed inset-0 z-50 bg-paper/85 backdrop-blur-sm flex items-center justify-center p-6">
      <GridOverlay />
      <CornerAccents />

      <div
        className={[
          "relative z-10 w-full max-w-xl",
          "border-5 border-ink shadow-brutalXl bg-paper",
          "p-8 sm:p-10",
          "brutal-slide-up",
        ].join(" ")}
      >
        <div className="flex items-center gap-5 sm:gap-7">
          {/* Spinning floppy */}
          <div
            className={[
              "flex-shrink-0",
              "w-20 h-20 sm:w-28 sm:h-28",
              "border-5 border-ink shadow-brutalLg",
              "bg-sun text-ink",
              "flex items-center justify-center",
              "brutal-spin",
            ].join(" ")}
          >
            <FloppyIcon className="w-12 h-12 sm:w-16 sm:h-16" />
          </div>

          <div className="flex-1 min-w-0">
            <h2
              key={i}
              className="font-display uppercase text-2xl sm:text-4xl leading-none tracking-tight brutal-hue"
            >
              {MESSAGES[i]}
            </h2>
            <p className="mt-2 font-mono text-xs sm:text-sm uppercase tracking-wider text-ink/70">
              hold tight · we{"'"}re looking under the boxes
            </p>
          </div>
        </div>

        {/* Chunky progress bar */}
        <div className="mt-6 sm:mt-8 h-6 border-3 border-ink shadow-brutal bg-paper overflow-hidden">
          <div
            className="h-full bg-ink brutal-bar"
            style={{ width: "45%" }}
          />
        </div>

        {/* Three blinking status squares */}
        <div className="mt-5 flex items-center gap-3 font-mono text-xs uppercase tracking-widest">
          <span className="w-4 h-4 bg-leaf border-2 border-ink brutal-blink" />
          <span className="w-4 h-4 bg-sun border-2 border-ink brutal-blink [animation-delay:200ms]" />
          <span className="w-4 h-4 bg-pink border-2 border-ink brutal-blink [animation-delay:400ms]" />
          <span>SCANNING</span>
        </div>
      </div>
    </div>
  );
}
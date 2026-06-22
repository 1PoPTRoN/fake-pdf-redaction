import { useEffect, useState } from "react";
import { GridOverlay } from "../components/GridOverlay";
import { CornerAccents } from "../components/CornerAccents";
import { FloppyIcon } from "../components/icons";

/**
 * Initial full-page loader. The wait itself is the message: three privacy
 * promises the visitor registers before they ever see the dropzone. Each
 * phrase mirrors something already promised elsewhere in the UI so this
 * screen is a focused briefing, not a loading decoration.
 *
 * Total wait: 3300ms (below the 3.5s ceiling where bounce rate starts to
 * matter on a static landing page). The progress bar fills in lockstep so
 * the bar completes exactly as the home page takes over.
 */
const TOTAL_MS = 3300;
const STEP_MS: ReadonlyArray<number> = [0, 1100, 2200];

export function BootLoader() {
  const [step, setStep] = useState(0);
  // Progress bar drives from 0 → 100 across the full wait. Re-rendered every
  // animation frame so the bar visibly climbs (the prior fixed 40% read as
  // "stuck" once the wait exceeded ~2s).
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    // Reveal each privacy promise at the right beat. The final step is shown
    // for the remainder of TOTAL_MS so the home page swap feels like the
    // promise landing, not the next one being withheld.
    for (let i = 1; i < STEP_MS.length; i++) {
      timers.push(setTimeout(() => setStep(i), STEP_MS[i]));
    }

    const startedAt = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const pct = Math.min(100, ((now - startedAt) / TOTAL_MS) * 100);
      setProgress(pct);
      if (pct < 100) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      timers.forEach(clearTimeout);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden">
      <GridOverlay />
      <CornerAccents />

      <div className="relative z-10 flex flex-col items-center gap-8 sm:gap-10 px-6">
        {/* Big spinning floppy sticker */}
        <div
          className={[
            "w-28 h-28 sm:w-40 sm:h-40",
            "border-5 border-ink shadow-brutalXl",
            "bg-sun text-ink",
            "flex items-center justify-center",
            "brutal-spin",
          ].join(" ")}
        >
          <FloppyIcon className="w-16 h-16 sm:w-24 sm:h-24" />
        </div>

        {/* Glitchy headline that flips through three privacy promises. Each
            phrase is a promise already made elsewhere in the UI (badges,
            marquee, action-bar copy) so the boot screen is a focused
            reminder, not a new claim. */}
        <h1
          key={step}
          className="font-display uppercase text-5xl sm:text-7xl tracking-tight text-center brutal-stamp"
        >
          {step === 0 && "READ-ONLY"}
          {step === 1 && "NOTHING STORED"}
          {step === 2 && "EVIDENCE-FIRST"}
        </h1>

        {/* Chunky stepped progress bar. Width grows 0 → 100% over TOTAL_MS so
            the bar completes exactly as the home page takes over. The
            existing bar-slide shimmer keeps animating inside the growing
            fill so it still reads as a "live" loader, not a static gauge. */}
        <div className="w-[80vw] max-w-xl h-6 border-3 border-ink shadow-brutal bg-paper overflow-hidden">
          <div
            className="h-full bg-ink brutal-bar"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Flickering LIVE dot */}
        <div className="flex items-center gap-3 font-mono text-sm uppercase tracking-widest">
          <span className="w-3 h-3 bg-pink border-2 border-ink brutal-flicker" />
          <span>SYSTEM ONLINE</span>
        </div>
      </div>
    </div>
  );
}
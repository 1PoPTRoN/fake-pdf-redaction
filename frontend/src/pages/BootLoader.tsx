import { useEffect, useState } from "react";
import { GridOverlay } from "../components/GridOverlay";
import { CornerAccents } from "../components/CornerAccents";
import { FloppyIcon } from "../components/icons";

/**
 * Initial full-page loader. Shown while the JS bundle warms up + reads any
 * initial state. Auto-dismisses after a short scripted sequence so the user
 * sees the animation even on a fast machine.
 */
export function BootLoader() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t1 = setTimeout(() => setStep(1), 350);
    const t2 = setTimeout(() => setStep(2), 900);
    const t3 = setTimeout(() => setStep(3), 1500);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
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

        {/* Glitchy headline that flips copy per step */}
        <h1
          key={step}
          className="font-display uppercase text-5xl sm:text-7xl tracking-tight text-center brutal-stamp"
        >
          {step === 0 && "BOOTING…"}
          {step === 1 && "LOADING DETECTORS…"}
          {step === 2 && "SHARPENING X-RAY…"}
          {step === 3 && "READY."}
        </h1>

        {/* Chunky stepped progress bar */}
        <div className="w-[80vw] max-w-xl h-6 border-3 border-ink shadow-brutal bg-paper overflow-hidden">
          <div className="h-full bg-ink brutal-bar" style={{ width: "40%" }} />
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
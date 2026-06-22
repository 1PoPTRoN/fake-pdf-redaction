import { useEffect, useState } from "react";
import { backendOrigin, fetchHealth } from "../lib/api";

type PillKind = "checking" | "warming" | "live" | "down" | "degraded";

type Snapshot = {
  kind: PillKind;
  detail?: string;
  vectorsReady?: number;
  latency?: number;
};

export function BackendStatus() {
  const [snap, setSnap] = useState<Snapshot>({ kind: "checking" });

  // Poll the health endpoint on mount, then every 15s. The backend reports
  // status:warming during cold start, so the pill tracks that in real time
  // and flips to LIVE the moment the detector engine finishes warming.
  useEffect(() => {
    let cancelled = false;

    const tick = async () => {
      const result = await fetchHealth();
      if (cancelled) return;
      if (result.kind === "ok") {
        setSnap({
          kind: "live",
          vectorsReady: result.snapshot.vectors_ready,
          latency: result.latency,
        });
      } else if (result.kind === "warming") {
        setSnap({
          kind: "warming",
          detail: result.snapshot.detail || "loading detectors",
          vectorsReady: result.snapshot.vectors_ready,
          latency: result.latency,
        });
      } else if (result.kind === "degraded") {
        setSnap({
          kind: "degraded",
          detail: result.snapshot.detail || "warmup failed",
          latency: result.latency,
        });
      } else {
        setSnap({ kind: "down" });
      }
    };

    tick();
    const id = window.setInterval(tick, 15_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  // Color: warming → sun (yellow) is the existing palette's "in progress" tone.
  const colorMap: Record<PillKind, { bg: string; dot: string }> = {
    checking: { bg: "bg-sun", dot: "bg-sun" },
    warming: { bg: "bg-sun", dot: "bg-sun" },
    live: { bg: "bg-leaf", dot: "bg-leaf" },
    down: { bg: "bg-pink", dot: "bg-pink" },
    degraded: { bg: "bg-pink", dot: "bg-pink" },
  };
  const colors = colorMap[snap.kind];

  const labelMap: Record<PillKind, string> = {
    checking: "PINGING BACKEND…",
    warming: "BACKEND LAUNCHING…",
    live: "BACKEND LIVE",
    down: "BACKEND ASLEEP — CLICK TO WAKE",
    degraded: "BACKEND ERROR",
  };

  const base =
    "inline-flex items-center gap-2 px-3 py-1.5 border-3 border-ink shadow-brutalSm font-display text-xs sm:text-sm uppercase tracking-wider";
  const inner = (
    <>
      <span
        aria-hidden
        className={[
          colors.dot,
          "inline-block w-2.5 h-2.5 border-2 border-ink",
          snap.kind === "live" || snap.kind === "warming" ? "animate-pulse" : "",
        ].join(" ")}
      />
      <span>{labelMap[snap.kind]}</span>
      {snap.kind === "live" && snap.latency !== undefined && (
        <span className="font-mono text-[10px] sm:text-xs opacity-70">
          {snap.latency}MS
        </span>
      )}
      {snap.kind === "warming" && snap.vectorsReady !== undefined && (
        <span className="font-mono text-[10px] sm:text-xs opacity-70">
          {snap.vectorsReady}/6 VECTORS
        </span>
      )}
      {snap.kind === "degraded" && snap.detail && (
        <span
          className="font-mono text-[10px] sm:text-xs opacity-70 normal-case"
          title={snap.detail}
        >
          {snap.detail.slice(0, 40)}
        </span>
      )}
    </>
  );

  // DOWN: link to backend origin so a single click opens the health page and
  // wakes the free-tier Render service from sleep. The warming state is a
  // normal non-interactive state — clicking it can't make the warmup faster.
  if (snap.kind === "down") {
    return (
      <a
        href={backendOrigin()}
        target="_blank"
        rel="noopener noreferrer"
        className={`${base} ${colors.bg} hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all`}
        title="Open backend in a new tab to wake it from free-tier sleep"
      >
        {inner}
      </a>
    );
  }

  return (
    <span className={`${base} ${colors.bg}`} aria-live="polite">
      {inner}
    </span>
  );
}
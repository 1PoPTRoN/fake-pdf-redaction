import { useEffect, useState } from "react";
import { backendOrigin, fetchHealth } from "../lib/api";

type Status = "checking" | "live" | "down";

export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");
  const [latency, setLatency] = useState<number | null>(null);

  // Ping once on mount, then every 30s. Cheap (one GET), and gives a useful
  // "is this thing actually awake" signal for the free-tier Render cold start.
  useEffect(() => {
    let cancelled = false;

    const tick = async () => {
      const start = performance.now();
      const ok = await fetchHealth();
      if (cancelled) return;
      setLatency(Math.round(performance.now() - start));
      setStatus(ok ? "live" : "down");
    };

    tick();
    const id = window.setInterval(tick, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const color =
    status === "live" ? "leaf" : status === "down" ? "pink" : "sun";
  const dot =
    status === "live"
      ? "bg-leaf"
      : status === "down"
        ? "bg-pink"
        : "bg-sun";
  const label =
    status === "live"
      ? "BACKEND LIVE"
      : status === "down"
        ? "BACKEND ASLEEP — CLICK TO WAKE"
        : "PINGING BACKEND…";

  // Live: a non-clickable status chip. Down: a same-shape chip that links to
  // the backend origin so a single click opens the health page (and warms it).
  const base =
    "inline-flex items-center gap-2 px-3 py-1.5 border-3 border-ink shadow-brutalSm font-display text-xs sm:text-sm uppercase tracking-wider";
  const bg = { leaf: "bg-leaf", sun: "bg-sun", pink: "bg-pink" }[color];

  const inner = (
    <>
      {/* Status dot — small inline square matching the brutalist palette */}
      <span
        aria-hidden
        className={[
          dot,
          "inline-block w-2.5 h-2.5 border-2 border-ink",
          status === "live" ? "animate-pulse" : "",
        ].join(" ")}
      />
      <span>{label}</span>
      {status === "live" && latency !== null && (
        <span className="font-mono text-[10px] sm:text-xs opacity-70">
          {latency}MS
        </span>
      )}
    </>
  );

  if (status === "down") {
    return (
      <a
        href={backendOrigin()}
        target="_blank"
        rel="noopener noreferrer"
        className={`${base} ${bg} hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all`}
        title="Open backend in a new tab to wake it from free-tier sleep"
      >
        {inner}
      </a>
    );
  }

  return (
    <span className={`${base} ${bg}`} aria-live="polite">
      {inner}
    </span>
  );
}
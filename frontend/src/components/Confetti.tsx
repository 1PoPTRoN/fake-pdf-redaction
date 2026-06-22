/**
 * Confetti burst — a flat ring of colored, rotated chunks that pop in
 * then fly off in random directions. Pure CSS, no library.
 */
import { useEffect, useState } from "react";

const COLORS = [
  "bg-sun",
  "bg-pink",
  "bg-sky",
  "bg-leaf",
  "bg-grape",
];

type Piece = {
  id: number;
  left: number; // % of container width
  delay: number; // ms
  dx: number;    // px end-x (random between -300..300)
  dy: number;    // px end-y (random between -400..-100)
  rot: number;   // end rotation
  color: string;
  size: number;  // px
};

function randomPieces(count: number): Piece[] {
  // Deterministic-ish — only on first render, no re-runs.
  const seed = 1337;
  let s = seed;
  const rnd = () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
  return Array.from({ length: count }, (_, i) => ({
    id: i,
    left: 10 + rnd() * 80,
    delay: rnd() * 200,
    dx: (rnd() - 0.5) * 700,
    dy: -200 - rnd() * 400,
    rot: (rnd() - 0.5) * 720,
    color: COLORS[Math.floor(rnd() * COLORS.length)],
    size: 14 + Math.floor(rnd() * 14),
  }));
}

type Props = {
  /** Run the burst. Set to true to play. */
  play: boolean;
};

export function Confetti({ play }: Props) {
  const [pieces] = useState(() => randomPieces(48));
  const [active, setActive] = useState(false);

  useEffect(() => {
    if (!play) return;
    setActive(true);
    const t = setTimeout(() => setActive(false), 2000);
    return () => clearTimeout(t);
  }, [play]);

  if (!active) return null;

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-40 overflow-hidden"
    >
      {pieces.map((p) => (
        <span
          key={p.id}
          className={[
            "absolute",
            p.color,
            "border-2 border-ink",
            "block",
          ].join(" ")}
          style={
            {
              left: `${p.left}%`,
              top: "30%",
              width: `${p.size}px`,
              height: `${p.size}px`,
              animation: `pop-in 240ms ${p.delay}ms cubic-bezier(.2,1.4,.3,1) both, confetti-fly 1.4s ${300 + p.delay}ms cubic-bezier(.2,.6,.4,1) both`,
              ["--dx" as never]: `${p.dx}px`,
              ["--dy" as never]: `${p.dy}px`,
              ["--end-rot" as never]: `${p.rot}deg`,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}
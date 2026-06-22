import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  color?: "leaf" | "sun" | "pink" | "sky" | "grape";
  rotate?: number;
};

const bg = {
  leaf: "bg-leaf",
  sun: "bg-sun",
  pink: "bg-pink",
  sky: "bg-sky",
  grape: "bg-grape",
};

export function Badge({ children, color = "leaf", rotate = -3 }: Props) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5",
        "px-3 py-1.5",
        "border-3 border-ink shadow-brutalSm",
        "font-display text-xs sm:text-sm uppercase tracking-wider",
        bg[color],
      ].join(" ")}
      style={{ transform: `rotate(${rotate}deg)` }}
    >
      {children}
    </span>
  );
}
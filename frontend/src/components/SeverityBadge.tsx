import type { Severity } from "../lib/types";

type Props = {
  severity: Severity;
  size?: "sm" | "md";
};

const fill: Record<Severity, string> = {
  critical: "bg-pink text-paper",
  high: "bg-sun text-ink",
  medium: "bg-sky text-paper",
  low: "bg-leaf text-ink",
  info: "bg-paper text-ink",
};

export function SeverityBadge({ severity, size = "md" }: Props) {
  const sz =
    size === "sm"
      ? "px-2 py-0.5 text-xs"
      : "px-3 py-1.5 text-sm sm:text-base";
  return (
    <span
      className={[
        "inline-flex items-center gap-1",
        "border-3 border-ink shadow-brutalSm",
        "font-display uppercase tracking-wider",
        sz,
        fill[severity],
      ].join(" ")}
    >
      {severity}
    </span>
  );
}
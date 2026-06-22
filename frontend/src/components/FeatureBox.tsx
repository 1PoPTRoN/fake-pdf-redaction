import type { ReactNode } from "react";

type Color = "sun" | "pink" | "sky" | "leaf" | "grape";

const bg: Record<Color, string> = {
  sun: "bg-sun",
  pink: "bg-pink",
  sky: "bg-sky",
  leaf: "bg-leaf",
  grape: "bg-grape",
};

const text: Record<Color, string> = {
  sun: "text-ink",
  pink: "text-paper",
  sky: "text-paper",
  leaf: "text-ink",
  grape: "text-paper",
};

type Props = {
  icon: ReactNode;
  title: string;
  subtitle?: string;
  color?: Color;
};

export function FeatureBox({
  icon,
  title,
  subtitle,
  color = "sky",
}: Props) {
  return (
    <div
      className={[
        "border-3 border-ink shadow-brutal",
        bg[color],
        text[color],
        "p-5 sm:p-6",
        "flex flex-col gap-3",
      ].join(" ")}
    >
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 sm:w-12 sm:h-12 border-3 border-ink bg-paper text-ink flex items-center justify-center">
          {icon}
        </div>
        <h3 className="font-display text-xl sm:text-2xl uppercase tracking-wide">
          {title}
        </h3>
      </div>
      {subtitle && (
        <p className="font-body text-sm sm:text-base font-medium leading-snug">
          {subtitle}
        </p>
      )}
    </div>
  );
}
/**
 * Corner accents — fixed, non-interactive.
 * - bottom-left: green "100% FREE" badge
 * - bottom-right: pixel-art floppy with "SAVE" label
 */
import { FloppyIcon } from "./icons";

export function CornerAccents() {
  return (
    <>
      {/* Bottom-left: green 100% FREE badge */}
      <div
        className={[
          "hidden sm:flex",
          "fixed left-4 sm:left-6 bottom-12 z-30",
          "items-center gap-2",
          "px-4 py-2",
          "border-3 border-ink shadow-brutalLg",
          "bg-leaf text-ink",
          "font-display text-base sm:text-lg uppercase tracking-wider",
          "transform -rotate-6",
        ].join(" ")}
      >
        <span aria-hidden>★</span>
        <span>100% FREE</span>
      </div>

      {/* Bottom-right: pixel-art SAVE icon */}
      <div
        className={[
          "hidden sm:flex",
          "fixed right-4 sm:right-6 bottom-12 z-30",
          "flex-col items-center gap-1",
        ].join(" ")}
      >
        <div
          className={[
            "w-14 h-14 sm:w-16 sm:h-16",
            "border-3 border-ink shadow-brutalLg",
            "bg-paper text-ink",
            "flex items-center justify-center",
            "transform rotate-6",
          ].join(" ")}
        >
          <FloppyIcon className="w-9 h-9 sm:w-10 sm:h-10" />
        </div>
        <span
          className={[
            "px-2 py-0.5",
            "border-2 border-ink",
            "bg-sun text-ink",
            "font-display text-xs uppercase tracking-wider",
            "transform rotate-6",
          ].join(" ")}
        >
          SAVE
        </span>
      </div>
    </>
  );
}
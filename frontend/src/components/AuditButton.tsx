type Props = {
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  loaded: boolean;
};

export function AuditButton({ onClick, disabled, busy, loaded }: Props) {
  const isOff = disabled || busy;
  return (
    <div className="flex flex-col items-center sm:items-end gap-2">
      <button
        type="button"
        onClick={onClick}
        disabled={isOff}
        className={[
          "brutal-press",
          "w-full sm:w-auto",
          "px-10 sm:px-16 py-6 sm:py-8",
          "border-5 border-ink",
          "font-display text-3xl sm:text-5xl uppercase tracking-tight",
          "bg-sun text-ink",
          "shadow-brutalXl",
          "inline-flex items-center gap-4",
          isOff ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
        ].join(" ")}
      >
        <span>{busy ? "SCANNING…" : "AUDIT NOW"}</span>
        <span
          className={[
            "inline-flex items-center justify-center",
            "min-w-[2.5rem] h-12 sm:h-14",
            "px-3",
            "border-3 border-ink bg-ink text-sun",
            "font-mono text-2xl sm:text-3xl",
          ].join(" ")}
        >
          {loaded ? "1" : "0"}
        </span>
      </button>
      <p className="font-mono text-xs sm:text-sm uppercase tracking-wider">
        Press <kbd className="border-2 border-ink bg-paper px-1.5 py-0.5">A</kbd> to audit
      </p>
    </div>
  );
}
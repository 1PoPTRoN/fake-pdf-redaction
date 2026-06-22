import { useEffect } from "react";

type Props = {
  message: string | null;
  onDismiss: () => void;
  tone?: "error" | "success";
};

export function Toast({ message, onDismiss, tone = "error" }: Props) {
  useEffect(() => {
    if (!message) return;
    const t = setTimeout(onDismiss, 5000);
    return () => clearTimeout(t);
  }, [message, onDismiss]);

  if (!message) return null;

  const bg = tone === "error" ? "bg-pink" : "bg-leaf";

  return (
    <div
      role="status"
      className={[
        "fixed left-1/2 -translate-x-1/2 bottom-6 z-50",
        "max-w-[90vw] sm:max-w-md",
        "border-[3px] border-ink shadow-brutal",
        "px-5 py-3",
        "font-display uppercase text-base sm:text-lg text-ink",
        bg,
        "brutal-pulse",
      ].join(" ")}
    >
      {message}
    </div>
  );
}
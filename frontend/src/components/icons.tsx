type IconProps = { className?: string };

/** Pure SVG icons rendered as solid shapes. No external dep. */
export function PadlockIcon({ className = "" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M6 10V7a6 6 0 1112 0v3h1a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2v-9a2 2 0 012-2h1zm2 0h8V7a4 4 0 10-8 0v3z" />
    </svg>
  );
}

export function BoltIcon({ className = "" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z" />
    </svg>
  );
}

export function InfinityIcon({ className = "" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="3" aria-hidden>
      <path d="M18.178 8c-2.09 0-3.5 1.55-4.685 3.07-1.155 1.48-2.31 2.93-4.493 2.93-2.485 0-4.5-1.79-4.5-4s2.015-4 4.5-4c2.183 0 3.338 1.45 4.493 2.93C14.678 9.45 16.09 11 18.178 11c2.485 0 4.5-1.79 4.5-4s-2.015-4-4.5-4z" />
    </svg>
  );
}

export function FileIcon({ className = "" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M6 2h8l6 6v12a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2zm7 1.5V9h5.5L13 3.5z" />
    </svg>
  );
}

export function FloppyIcon({ className = "" }: IconProps) {
  // Pixelated floppy disk.
  return (
    <svg viewBox="0 0 24 24" className={className} shapeRendering="crispEdges" fill="currentColor" aria-hidden>
      <path d="M3 3h14l4 4v14H3V3zm2 2v4h10V5H5zm2 6v3h6v-3H7zm-2 5v6h14v-6H5zm9 1h3v3h-3v-3z" />
    </svg>
  );
}

export function DragIcon({ className = "" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <circle cx="9" cy="6" r="1.6" />
      <circle cx="15" cy="6" r="1.6" />
      <circle cx="9" cy="12" r="1.6" />
      <circle cx="15" cy="12" r="1.6" />
      <circle cx="9" cy="18" r="1.6" />
      <circle cx="15" cy="18" r="1.6" />
    </svg>
  );
}

export function CloseIcon({ className = "" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M5 6.4L6.4 5 12 10.6 17.6 5 19 6.4 13.4 12 19 17.6 17.6 19 12 13.4 6.4 19 5 17.6 10.6 12 5 6.4z" />
    </svg>
  );
}

/* ── Audit-specific icons ─────────────────────────────────────────── */

/** Magnifying glass — "sees through black boxes". */
export function SearchIcon({ className = "" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="3" aria-hidden>
      <circle cx="10.5" cy="10.5" r="6.5" fill="currentColor" stroke="none" />
      <line x1="15.2" y1="15.2" x2="21" y2="21" strokeLinecap="square" />
    </svg>
  );
}

/** Bold check mark — "proves the leak". */
export function CheckIcon({ className = "" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="square" strokeLinejoin="miter" aria-hidden>
      <path d="M4 12l5 5 11-12" />
    </svg>
  );
}

/** Exclamation — used by the worst-severity stamp on findings. */
export function AlertIcon({ className = "" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M12 2l11 19H1L12 2zm-1 8v6h2v-6h-2zm0 7v2h2v-2h-2z" />
    </svg>
  );
}
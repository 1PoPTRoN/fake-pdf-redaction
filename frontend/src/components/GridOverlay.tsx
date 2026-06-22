/**
 * Background layer: full-page grid (per the Neubrutalism spec) PLUS halftone
 * dot wash restricted to the bottom-left and bottom-right corners. Heavy ink
 * rules anchor the page top and bottom.
 */
export function GridOverlay() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0"
    >
      {/* heavy black grid lines, full page */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(0,0,0,0.18) 1px, transparent 1px), linear-gradient(to bottom, rgba(0,0,0,0.18) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
        }}
      />
      {/* halftone dot wash — bottom-left corner */}
      <div
        className="halftone-bg opacity-50"
        style={{
          position: "absolute",
          left: 0,
          bottom: 0,
          width: "40vw",
          height: "40vh",
          WebkitMaskImage:
            "linear-gradient(to top right, #000 0%, #000 50%, transparent 100%)",
          maskImage:
            "linear-gradient(to top right, #000 0%, #000 50%, transparent 100%)",
        }}
      />
      {/* halftone dot wash — bottom-right corner */}
      <div
        className="halftone-bg opacity-50"
        style={{
          position: "absolute",
          right: 0,
          bottom: 0,
          width: "40vw",
          height: "40vh",
          WebkitMaskImage:
            "linear-gradient(to top left, #000 0%, #000 50%, transparent 100%)",
          maskImage:
            "linear-gradient(to top left, #000 0%, #000 50%, transparent 100%)",
        }}
      />
      {/* heavy top + bottom rules to anchor the page */}
      <div className="absolute top-0 left-0 right-0 h-2 bg-ink" />
      <div className="absolute bottom-0 left-0 right-0 h-2 bg-ink" />
    </div>
  );
}
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#000000",
        paper: "#FFFFFF",
        sun: "#FFEB3B",
        pink: "#FF4FB4",
        sky: "#3D9CFF",
        leaf: "#7CFF6B",
        grape: "#9B5CFF",
        cream: "#FFF6E0",
      },
      fontFamily: {
        display: ['"Archivo Black"', "system-ui", "sans-serif"],
        body: ['"Space Grotesk"', "system-ui", "sans-serif"],
        mono: ['"Space Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        brutal: "6px 6px 0 0 #000",
        brutalSm: "4px 4px 0 0 #000",
        brutalLg: "8px 8px 0 0 #000",
        brutalXl: "10px 10px 0 0 #000",
      },
      borderWidth: {
        3: "3px",
        5: "5px",
      },
      backgroundImage: {
        halftone:
          "radial-gradient(#000 1.5px, transparent 1.5px)",
      },
      backgroundSize: {
        halftone: "14px 14px",
      },
      // Add an xs breakpoint (480px) so the small-phone range has its own
      // scale. Tailwind ships with sm (640px), md (768px), lg (1024px), xl,
      // 2xl — but no breakpoint between 0 and 640px. With the brutalist
      // display font (Archivo Black) being unusually wide, headings need
      // their own size step *below* sm, not just a mobile default.
      screens: {
        xs: "480px",
      },
    },
  },
  plugins: [],
};
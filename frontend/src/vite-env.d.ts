/// <reference types="vite/client" />

// Vite injects a typed `import.meta.env` at build time. Any custom env vars
// declared on ImportMetaEnv (e.g. VITE_API_BASE) are read here. Keep this file
// at the repo root of frontend/src — Vite auto-includes it via the reference
// triple-slash directive, no tsconfig change required.
interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
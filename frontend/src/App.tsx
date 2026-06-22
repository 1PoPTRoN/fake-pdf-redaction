import { useEffect, useState } from "react";
import { BootLoader } from "./pages/BootLoader";
import { Home } from "./pages/Home";
import { Report } from "./pages/Report";
import type { AuditReport } from "./lib/types";

type Result = {
  report: AuditReport;
  file: File;
};

export default function App() {
  // Three app states: booting, home, report.
  const [booted, setBooted] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    // Boot screen total wait is 3.3s (matches BootLoader.tsx TOTAL_MS). The
    // boot screen's three privacy promises are the message, not a side effect
    // of bundle loading — they need time to land, so we hold the home page
    // until they've all flashed once.
    const t = setTimeout(() => setBooted(true), 3300);
    return () => clearTimeout(t);
  }, []);

  return (
    <main className="min-h-full">
      {!booted ? (
        <BootLoader />
      ) : result ? (
        <Report
          report={result.report}
          file={result.file}
          onAnother={() => setResult(null)}
        />
      ) : (
        <Home onReport={(report, file) => setResult({ report, file })} />
      )}
    </main>
  );
}
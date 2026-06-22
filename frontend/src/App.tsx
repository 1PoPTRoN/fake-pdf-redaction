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
    // Auto-dismiss the boot loader after the staged animation finishes.
    const t = setTimeout(() => setBooted(true), 2200);
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
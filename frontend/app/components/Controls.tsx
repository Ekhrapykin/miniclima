import { useState, useEffect } from "react";
import type { Sernum, Vals } from "../types";

interface ImportState {
  loading: boolean;
  ok?: boolean;
  msg?: string;
  startedAt?: number;
}

interface ExportData {
  sernum: Sernum;
  vals: Vals;
  ophours: number | null;
  timestamp: Date;
}

interface ControlsProps {
  busy: boolean;
  isRunning: boolean;
  isStandby: boolean;
  onPost: (path: string, body?: object) => void;
  onOpenSettings: () => void;
  importState: ImportState | null;
  onImport: () => void;
  exportData: ExportData;
}

function ElapsedTimer({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 500);
    return () => clearInterval(id);
  }, [startedAt]);
  return <span>{elapsed}s</span>;
}

export default function Controls({
  busy, isRunning, isStandby,
  onPost, onOpenSettings,
  importState, onImport,
  exportData,
}: ControlsProps) {
  const [exporting, setExporting] = useState<"excel" | "pdf" | null>(null);
  const toggleLabel = isRunning ? "■ Stop" : "▶ Start";
  const toggleAction = isRunning ? "/stop" : "/start";
  const unknownState = !isRunning && !isStandby;

  const handleExport = async (type: "excel" | "pdf") => {
    setExporting(type);
    try {
      const { exportExcel, exportPDF } = await import("../lib/export");
      if (type === "excel") await exportExcel(exportData);
      else await exportPDF(exportData);
    } catch (e) {
      console.error("Export failed:", e);
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="controls-bar">
      <button
        className={`btn${isRunning ? " btn-running" : " btn-primary"}`}
        disabled={busy || unknownState}
        onClick={() => onPost(toggleAction)}
      >
        {toggleLabel}
      </button>

      <button className="btn" onClick={onOpenSettings}>
        ⚙ Settings
      </button>

      <div className="controls-spacer" />

      <button
        className="btn btn-ghost"
        disabled={exporting === "excel"}
        onClick={() => handleExport("excel")}
      >
        {exporting === "excel" ? "Generating…" : "Export Excel"}
      </button>

      <button
        className="btn btn-ghost"
        disabled={exporting === "pdf"}
        onClick={() => handleExport("pdf")}
      >
        {exporting === "pdf" ? "Generating…" : "Export PDF"}
      </button>

      <div className="controls-divider" />

      {importState?.loading ? (
        <div className="import-progress">
          <div className="import-progress-bar">
            <div className="import-progress-fill" />
          </div>
          <span className="import-progress-label">
            Importing… <ElapsedTimer startedAt={importState.startedAt ?? Date.now()} />
          </span>
        </div>
      ) : (
          <button
            className="btn"
            onClick={onImport}
          >
            Import to Prometheus
          </button>
      )}
    </div>
  );
}

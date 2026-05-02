import { useState, useEffect } from "react";

interface ImportState {
  loading: boolean;
  ok?: boolean;
  msg?: string;
  startedAt?: number;
}

interface ControlsProps {
  busy: boolean;
  isRunning: boolean;
  isStandby: boolean;
  onPost: (path: string, body?: object) => void;
  onOpenSettings: () => void;
  onOpenExport: () => void;
  importState: ImportState | null;
  onImport: () => void;
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
  onPost, onOpenSettings, onOpenExport,
  importState, onImport,
}: ControlsProps) {
  const toggleLabel = isRunning ? "■ Stop" : "▶ Start";
  const toggleAction = isRunning ? "/stop" : "/start";
  const unknownState = !isRunning && !isStandby;

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

      <button className="btn" onClick={onOpenExport}>
        Export
      </button>

      <div className="controls-spacer" />

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

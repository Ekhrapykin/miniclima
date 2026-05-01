interface ImportState {
  loading: boolean;
  ok?: boolean;
  msg?: string;
}

interface ControlsProps {
  busy: boolean;
  isRunning: boolean;
  isStandby: boolean;
  onPost: (path: string, body?: object) => void;
  onOpenSettings: () => void;
  importState: ImportState | null;
  onImport: () => void;
}

export default function Controls({
  busy, isRunning, isStandby,
  onPost, onOpenSettings,
  importState, onImport,
}: ControlsProps) {
  const toggleLabel = isRunning ? "■ Stop" : "▶ Start";
  const toggleAction = isRunning ? "/stop" : "/start";
  const unknownState = !isRunning && !isStandby;

  return (
    <div className="controls-bar">
      <button
        className={`btn${isRunning ? " btn-running" : ""}`}
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
        className="btn"
        disabled={importState?.loading ?? false}
        onClick={onImport}
      >
        {importState?.loading ? "Importing…" : "Import to Prometheus"}
      </button>
      {importState && !importState.loading && (
        <span
          className="ctrl-label"
          style={{ color: importState.ok ? "var(--green, #00e8a2)" : "var(--err)" }}
        >
          {importState.msg}
        </span>
      )}
    </div>
  );
}

interface ImportState {
  loading: boolean;
  ok?: boolean;
  msg?: string;
}

interface SettingsPanelProps {
  open: boolean;
  busy: boolean;
  logDraft: string;
  setLogDraft: (v: string) => void;
  onPost: (path: string, body?: object) => void;
  importState: ImportState | null;
  onImport: () => void;
}

export default function SettingsPanel({
  open, busy, logDraft, setLogDraft, onPost, importState, onImport,
}: SettingsPanelProps) {
  if (!open) return null;

  return (
    <div className="settings-panel">
      <div className="settings-row">
        <span className="ctrl-label">LOG INTERVAL</span>
        <input
          type="number"
          min={1}
          max={99}
          value={logDraft}
          onChange={(e) => setLogDraft(e.target.value)}
          className="sp-input"
          onKeyDown={(e) => {
            if (e.key === "Enter" && logDraft)
              onPost("/set-log-time", { minutes: parseInt(logDraft) });
          }}
        />
        <span className="ctrl-unit">min</span>
        <button
          className="btn amber"
          disabled={busy || !logDraft}
          onClick={() => onPost("/set-log-time", { minutes: parseInt(logDraft) })}
        >
          Apply
        </button>
      </div>

      <div className="settings-row">
        <span className="ctrl-label">HISTORY</span>
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
            style={{ color: importState.ok ? "var(--green)" : "var(--red)" }}
          >
            {importState.msg}
          </span>
        )}
      </div>
    </div>
  );
}

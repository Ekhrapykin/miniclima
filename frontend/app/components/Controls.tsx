interface ControlsProps {
  busy: boolean;
  isRunning: boolean;
  isStandby: boolean;
  spDraft: string;
  setSpDraft: (v: string) => void;
  settingsOpen: boolean;
  setSettingsOpen: (fn: (v: boolean) => boolean) => void;
  onPost: (path: string, body?: object) => void;
  stepSp: (delta: number) => void;
}

export default function Controls({
  busy, isRunning, isStandby,
  spDraft, setSpDraft,
  settingsOpen, setSettingsOpen,
  onPost, stepSp,
}: ControlsProps) {
  return (
    <div className="controls-bar">
      <button
        className={`btn${isRunning ? " btn-running" : ""}`}
        disabled={busy || isRunning}
        onClick={() => onPost("/start")}
      >
        ▶ Start
      </button>
      <button
        className="btn"
        disabled={busy || isStandby}
        onClick={() => onPost("/stop")}
      >
        ■ Stop
      </button>

      <div className="controls-divider" />

      <span className="ctrl-label">SET SP</span>
      <button
        className="btn amber btn-narrow"
        disabled={busy}
        onClick={() => stepSp(-1)}
      >
        −
      </button>
      <input
        type="number"
        min={0}
        max={99}
        value={spDraft}
        onChange={(e) => setSpDraft(e.target.value)}
        className="sp-input"
        onKeyDown={(e) => {
          if (e.key === "Enter" && spDraft)
            onPost("/setpoint", { rh_percent: parseInt(spDraft) });
        }}
      />
      <button
        className="btn amber btn-narrow"
        disabled={busy}
        onClick={() => stepSp(1)}
      >
        +
      </button>
      <span className="ctrl-unit">%</span>
      <button
        className="btn amber"
        disabled={busy || !spDraft}
        onClick={() => onPost("/setpoint", { rh_percent: parseInt(spDraft) })}
      >
        Apply
      </button>

      <div className="controls-spacer" />

      <button className="btn" onClick={() => setSettingsOpen((v) => !v)}>
        ⚙ Settings {settingsOpen ? "▴" : "▾"}
      </button>
    </div>
  );
}

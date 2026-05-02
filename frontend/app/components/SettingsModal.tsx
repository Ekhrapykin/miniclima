import { useState, useEffect, useRef } from "react";
import type { Sernum } from "../types";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  busy: boolean;
  sernum: Sernum;
  onPost: (path: string, body?: object) => void;
}

interface SettingField {
  label: string;
  key: keyof Sernum;
  min: number;
  max: number;
  unit: string;
  endpoint: string;
  bodyKey: string;
  group: string;
}

const FIELDS: SettingField[] = [
  { label: "Setpoint (SP)",   key: "sp",  min: 0,  max: 99, unit: "%",   endpoint: "/setpoint",    bodyKey: "val", group: "Control" },
  { label: "Alarm Min",       key: "lo",  min: 0,  max: 99, unit: "%",   endpoint: "/alarm-min",   bodyKey: "val", group: "Alarms" },
  { label: "Alarm Max",       key: "hi",  min: 0,  max: 99, unit: "%",   endpoint: "/alarm-max",   bodyKey: "val", group: "Alarms" },
  { label: "Hysteresis",      key: "hy",  min: 1,  max: 10, unit: "%",   endpoint: "/hysteresis",  bodyKey: "val", group: "Alarms" },
  { label: "Log Interval",    key: "lt",  min: 1,  max: 99, unit: "min", endpoint: "/log-time",    bodyKey: "val", group: "Logging" },
];

const GROUPS = ["Control", "Alarms", "Logging"];

export default function SettingsModal({ open, onClose, busy, sernum, onPost }: SettingsModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      const initial: Record<string, string> = {};
      for (const f of FIELDS) {
        initial[f.key] = sernum[f.key] != null ? String(sernum[f.key]) : "";
      }
      setDrafts(initial);
      setErrors({});
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open, sernum]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const handleClose = () => onClose();
    dialog.addEventListener("close", handleClose);
    return () => dialog.removeEventListener("close", handleClose);
  }, [onClose]);

  const setDraft = (key: string, val: string) => {
    setDrafts((prev) => ({ ...prev, [key]: val }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const stepDraft = (f: SettingField, delta: number) => {
    const current = parseInt(drafts[f.key]) || 0;
    const next = Math.max(f.min, Math.min(f.max, current + delta));
    setDraft(f.key, String(next));
  };

  const isChanged = (f: SettingField): boolean => {
    const draft = parseInt(drafts[f.key]);
    return !isNaN(draft) && draft !== sernum[f.key];
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    for (const f of FIELDS) {
      const val = parseInt(drafts[f.key]);
      if (drafts[f.key] !== "" && !isNaN(val)) {
        if (val < f.min || val > f.max) {
          newErrors[f.key] = `${f.min}–${f.max}`;
        }
      }
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const changedCount = FIELDS.filter((f) => isChanged(f)).length;

  const handleApply = () => {
    if (!validate()) return;
    for (const f of FIELDS) {
      const draft = parseInt(drafts[f.key]);
      const current = sernum[f.key];
      if (!isNaN(draft) && draft !== current) {
        onPost(f.endpoint, { [f.bodyKey]: draft });
      }
    }
    onClose();
  };

  return (
    <dialog ref={dialogRef} className="settings-modal" onClick={(e) => {
      if (e.target === dialogRef.current) onClose();
    }}>
      <div className="settings-modal-inner">
        <div className="settings-modal-header">Device Settings</div>
        <div className="settings-modal-body">
          {GROUPS.map((group) => {
            const fields = FIELDS.filter((f) => f.group === group);
            if (fields.length === 0) return null;
            return (
              <div key={group} className="settings-group">
                <div className="settings-group-label">{group}</div>
                {fields.map((f) => (
                  <div key={f.key} className="settings-field">
                    <label className="settings-field-label">
                      {isChanged(f) && <span className="settings-changed-dot" />}
                      {f.label}
                    </label>
                    <div className="settings-field-input">
                      <div className="sp-stepper">
                        <button type="button" className="sp-step-btn" onClick={() => stepDraft(f, -1)} aria-label="Decrease">−</button>
                        <input
                          type="text"
                          inputMode="numeric"
                          pattern="[0-9\-]*"
                          value={drafts[f.key] ?? ""}
                          onChange={(e) => setDraft(f.key, e.target.value)}
                          className={`sp-input${errors[f.key] ? " sp-input-error" : ""}`}
                        />
                        <button type="button" className="sp-step-btn" onClick={() => stepDraft(f, 1)} aria-label="Increase">+</button>
                      </div>
                      <span className="ctrl-unit">{f.unit}</span>
                    </div>
                    {errors[f.key] && (
                      <span className="settings-error">Range: {errors[f.key]}</span>
                    )}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
        <div className="settings-modal-footer">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn amber" disabled={busy || changedCount === 0} onClick={handleApply}>
            {changedCount > 0 ? `Apply ${changedCount} change${changedCount > 1 ? "s" : ""}` : "Apply"}
          </button>
        </div>
      </div>
    </dialog>
  );
}

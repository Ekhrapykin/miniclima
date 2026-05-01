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
}

const FIELDS: SettingField[] = [
  { label: "Setpoint (SP)",   key: "sp", min: 0,  max: 99, unit: "%",   endpoint: "/setpoint",        bodyKey: "rh_percent" },
  { label: "Log Interval",    key: "lt", min: 1,  max: 99, unit: "min", endpoint: "/log-time",    bodyKey: "minutes" },
  { label: "Alarm Min",       key: "lo", min: 0,  max: 99, unit: "%",   endpoint: "/alarm-min",    bodyKey: "lo" },
  { label: "Alarm Max",       key: "hi", min: 0,  max: 99, unit: "%",   endpoint: "/alarm-max",    bodyKey: "hi" },
  { label: "Hysteresis",      key: "hy", min: 1,  max: 10, unit: "%",   endpoint: "/hysteresis",  bodyKey: "hy" },
  { label: "RH Correction",   key: "rhc", min: -5, max: 5,  unit: "%",   endpoint: "/rhcorr", bodyKey: "rhc" },
];

export default function SettingsModal({ open, onClose, busy, sernum, onPost }: SettingsModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      const initial: Record<string, string> = {};
      for (const f of FIELDS) {
        initial[f.key] = sernum[f.key] != null ? String(sernum[f.key]) : "";
      }
      setDrafts(initial);
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
  };

  const handleApply = () => {
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
          {FIELDS.map((f) => (
            <div key={f.key} className="settings-field">
              <label className="settings-field-label">{f.label}</label>
              <div className="settings-field-input">
                <input
                  type="number"
                  min={f.min}
                  max={f.max}
                  value={drafts[f.key] ?? ""}
                  onChange={(e) => setDraft(f.key, e.target.value)}
                  className="sp-input"
                />
                <span className="ctrl-unit">{f.unit}</span>
              </div>
            </div>
          ))}
        </div>
        <div className="settings-modal-footer">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn amber" disabled={busy} onClick={handleApply}>Apply</button>
        </div>
      </div>
    </dialog>
  );
}

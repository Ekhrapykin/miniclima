"use client";

import { useState, useEffect, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const PERIODS = [
  { value: "1w", label: "1 Week" },
  { value: "1m", label: "1 Month" },
  { value: "3m", label: "3 Months" },
  { value: "1y", label: "1 Year" },
];

const FORMATS = [
  { value: "xlsx", label: "Excel (.xlsx)" },
  { value: "pdf", label: "PDF" },
];

const METRIC_LABELS: Record<string, string> = {
  humidity: "Humidity (%)",
  setpoint: "Setpoint (%)",
  alarm_min: "Alarm Min (%)",
  alarm_max: "Alarm Max (%)",
  t_ambient: "T Ambient (°C)",
};

interface ExportModalProps {
  open: boolean;
  onClose: () => void;
}

export default function ExportModal({ open, onClose }: ExportModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [period, setPeriod] = useState("1m");
  const [format, setFormat] = useState("xlsx");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setError(null);
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const handleClose = () => onClose();
    dialog.addEventListener("close", handleClose);
    return () => dialog.removeEventListener("close", handleClose);
  }, [onClose]);

  const handleExport = async () => {
    setBusy(true);
    setError(null);
    try {
      const resp = await fetch(`${API}/export-data?period=${period}`);
      if (!resp.ok) throw new Error(`API error ${resp.status}`);
      const data = await resp.json();

      if (format === "xlsx") {
        await generateExcel(data, period);
      } else {
        await generatePDF(data, period);
      }
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <dialog ref={dialogRef} className="settings-modal" onClick={(e) => {
      if (e.target === dialogRef.current) onClose();
    }}>
      <div className="settings-modal-inner">
        <div className="settings-modal-header">Export Historical Data</div>
        <div className="settings-modal-body">
          <div className="settings-group">
            <div className="settings-group-label">Period</div>
            <div className="export-options">
              {PERIODS.map((p) => (
                <button
                  key={p.value}
                  className={`btn export-option-btn${period === p.value ? " export-option-active" : ""}`}
                  onClick={() => setPeriod(p.value)}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="settings-group">
            <div className="settings-group-label">Format</div>
            <div className="export-options">
              {FORMATS.map((f) => (
                <button
                  key={f.value}
                  className={`btn export-option-btn${format === f.value ? " export-option-active" : ""}`}
                  onClick={() => setFormat(f.value)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          <div className="export-summary">
            <span className="ctrl-label">
              Metrics: Humidity, Setpoint, Alarm Min/Max, T Ambient
            </span>
          </div>

          {error && <span className="settings-error" style={{ marginLeft: 0 }}>{error}</span>}
        </div>
        <div className="settings-modal-footer">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn amber" disabled={busy} onClick={handleExport}>
            {busy ? "Exporting…" : "Export"}
          </button>
        </div>
      </div>
    </dialog>
  );
}

async function generateExcel(data: { period: string; step: string; metrics: Record<string, [number, number][]> }, period: string) {
  const XLSX = await import("xlsx");

  const allTimestamps = new Set<number>();
  for (const values of Object.values(data.metrics)) {
    for (const [ts] of values) allTimestamps.add(ts);
  }
  const sorted = [...allTimestamps].sort((a, b) => a - b);

  const lookup: Record<string, Map<number, number>> = {};
  for (const [name, values] of Object.entries(data.metrics)) {
    const m = new Map<number, number>();
    for (const [ts, val] of values) m.set(ts, val);
    lookup[name] = m;
  }

  const metricKeys = Object.keys(METRIC_LABELS);
  const header = ["Timestamp", ...metricKeys.map((k) => METRIC_LABELS[k])];
  const rows = sorted.map((ts) => {
    const row: (string | number | null)[] = [new Date(ts * 1000).toLocaleString()];
    for (const key of metricKeys) {
      const val = lookup[key]?.get(ts);
      row.push(val !== undefined ? Math.round(val * 10) / 10 : null);
    }
    return row;
  });

  const ws = XLSX.utils.aoa_to_sheet([header, ...rows]);
  ws["!cols"] = [{ wch: 20 }, ...metricKeys.map(() => ({ wch: 14 }))];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, `EBC10 ${period}`);
  XLSX.writeFile(wb, `ebc10-history-${period}-${new Date().toISOString().slice(0, 10)}.xlsx`);
}

async function generatePDF(data: { period: string; step: string; metrics: Record<string, [number, number][]> }, period: string) {
  const { default: jsPDF } = await import("jspdf");

  const allTimestamps = new Set<number>();
  for (const values of Object.values(data.metrics)) {
    for (const [ts] of values) allTimestamps.add(ts);
  }
  const sorted = [...allTimestamps].sort((a, b) => a - b);

  const lookup: Record<string, Map<number, number>> = {};
  for (const [name, values] of Object.entries(data.metrics)) {
    const m = new Map<number, number>();
    for (const [ts, val] of values) m.set(ts, val);
    lookup[name] = m;
  }

  const metricKeys = Object.keys(METRIC_LABELS);
  const pdf = new jsPDF("l", "mm", "a4");
  const pageW = 297;
  const margin = 10;
  const colW = (pageW - margin * 2) / (metricKeys.length + 1);
  const rowH = 6;
  let y = margin;

  pdf.setFontSize(14);
  pdf.text(`EBC10 Historical Data — ${PERIODS.find((p) => p.value === period)?.label ?? period}`, margin, y);
  y += 8;

  pdf.setFontSize(8);
  pdf.text(`Generated: ${new Date().toLocaleString()} | Step: ${data.step}`, margin, y);
  y += 8;

  pdf.setFontSize(7);
  pdf.setFont("helvetica", "bold");
  pdf.text("Timestamp", margin, y);
  metricKeys.forEach((key, i) => {
    pdf.text(METRIC_LABELS[key], margin + colW * (i + 1), y);
  });
  y += rowH;
  pdf.setFont("helvetica", "normal");

  for (const ts of sorted) {
    if (y > 200) {
      pdf.addPage();
      y = margin;
      pdf.setFont("helvetica", "bold");
      pdf.text("Timestamp", margin, y);
      metricKeys.forEach((key, i) => {
        pdf.text(METRIC_LABELS[key], margin + colW * (i + 1), y);
      });
      y += rowH;
      pdf.setFont("helvetica", "normal");
    }

    pdf.text(new Date(ts * 1000).toLocaleString(), margin, y);
    metricKeys.forEach((key, i) => {
      const val = lookup[key]?.get(ts);
      pdf.text(val !== undefined ? String(Math.round(val * 10) / 10) : "—", margin + colW * (i + 1), y);
    });
    y += rowH;
  }

  pdf.save(`ebc10-history-${period}-${new Date().toISOString().slice(0, 10)}.pdf`);
}


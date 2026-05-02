import type { Sernum, Vals } from "../types";

interface ExportData {
  sernum: Sernum;
  vals: Vals;
  ophours: number | null;
  timestamp: Date;
}

function buildRows(data: ExportData): string[][] {
  const { sernum, vals, ophours, timestamp } = data;
  return [
    ["EBC10 Climate Control — Status Report"],
    ["Generated", timestamp.toLocaleString()],
    [],
    ["READINGS"],
    ["Relative Humidity", vals.rh != null ? `${vals.rh}%` : "--"],
    ["Ambient Temperature", vals.t != null ? `${vals.t}°C` : "--"],
    ["T1 Cold Side", vals.t1 != null ? `${vals.t1}°C` : "--"],
    ["T2 Hot Side", vals.t2 != null ? `${vals.t2}°C` : "--"],
    ["State", vals.state ?? "--"],
    [],
    ["SETTINGS"],
    ["Setpoint", sernum.sp != null ? `${sernum.sp}%` : "--"],
    ["Alarm Min", sernum.lo != null ? `${sernum.lo}%` : "--"],
    ["Alarm Max", sernum.hi != null ? `${sernum.hi}%` : "--"],
    ["Hysteresis", sernum.hy != null ? `${sernum.hy}%` : "--"],
    ["Log Interval", sernum.lt != null ? `${sernum.lt} min` : "--"],
    ["RH Correction", sernum.rhc != null ? `${sernum.rhc}%` : "--"],
    [],
    ["DEVICE"],
    ["Serial", sernum.serial ?? "--"],
    ["Firmware", sernum.firmware ?? "--"],
    ["Operating Hours", ophours != null ? String(ophours) : "--"],
  ];
}

export async function exportExcel(data: ExportData): Promise<void> {
  const XLSX = await import("xlsx");
  const rows = buildRows(data);
  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 22 }, { wch: 20 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Status");
  const ts = data.timestamp.toISOString().replace(/[:.]/g, "-").slice(0, 19);
  XLSX.writeFile(wb, `ebc10-status-${ts}.xlsx`);
}

export async function exportPDF(data: ExportData): Promise<void> {
  const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
    import("jspdf"),
    import("html2canvas"),
  ]);

  const dashboard = document.querySelector(".dashboard") as HTMLElement;
  if (!dashboard) return;

  const canvas = await html2canvas(dashboard, {
    backgroundColor: getComputedStyle(document.documentElement).getPropertyValue("--bg").trim(),
    scale: 1.5,
    useCORS: true,
    allowTaint: true,
    ignoreElements: (el) => el.tagName === "IFRAME",
  });

  const imgWidth = 210;
  const imgHeight = (canvas.height * imgWidth) / canvas.width;
  const pdf = new jsPDF("p", "mm", "a4");
  pdf.addImage(canvas.toDataURL("image/png"), "PNG", 0, 0, imgWidth, Math.min(imgHeight, 297));

  const ts = data.timestamp.toISOString().replace(/[:.]/g, "-").slice(0, 19);
  pdf.save(`ebc10-status-${ts}.pdf`);
}

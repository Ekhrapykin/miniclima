"use client";

import { useState, useEffect } from "react";
import { getTheme } from "./ThemeToggle";

const GRAFANA_URL = process.env.NEXT_PUBLIC_GRAFANA_URL ?? "http://localhost:3001";

const RANGES = [
  { value: "now-1h",  label: "1H" },
  { value: "now-4h",  label: "4H" },
  { value: "now-12h", label: "12H" },
  { value: "now-24h", label: "1D" },
  { value: "now-7d",  label: "7D" },
  { value: "now-30d", label: "30D" },
  { value: "now-90d", label: "90D" },
  { value: "now-1y",  label: "1Y" },
];

export default function GrafanaPanel() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [range, setRange] = useState("now-4h");

  useEffect(() => {
    setTheme(getTheme());
    const handler = (e: Event) => setTheme((e as CustomEvent).detail);
    window.addEventListener("theme-change", handler);
    return () => window.removeEventListener("theme-change", handler);
  }, []);

  const src = `${GRAFANA_URL}/d-solo/ebc10/miniclima-ebc10?panelId=1&theme=${theme}&refresh=15s&from=${range}&to=now`;

  return (
    <div className="grafana-panel">
      <div className="grafana-range-bar">
        {RANGES.map((r) => (
          <button
            key={r.value}
            className={`grafana-range-btn${range === r.value ? " grafana-range-active" : ""}`}
            onClick={() => setRange(r.value)}
          >
            {r.label}
          </button>
        ))}
      </div>
      <iframe src={src} className="grafana-iframe" />
    </div>
  );
}

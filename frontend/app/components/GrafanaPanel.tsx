"use client";

import { useState, useEffect } from "react";
import { getTheme } from "./ThemeToggle";

const GRAFANA_URL = process.env.NEXT_PUBLIC_GRAFANA_URL ?? "http://localhost:3001";

export default function GrafanaPanel() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    setTheme(getTheme());
    const handler = (e: Event) => setTheme((e as CustomEvent).detail);
    window.addEventListener("theme-change", handler);
    return () => window.removeEventListener("theme-change", handler);
  }, []);

  const src = `${GRAFANA_URL}/d-solo/ebc10/miniclima-ebc10?panelId=1&theme=${theme}&refresh=15s&from=now-4h&to=now`;

  return (
    <div className="grafana-panel">
      <iframe src={src} className="grafana-iframe" />
    </div>
  );
}

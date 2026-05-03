"use client";

import { useState, useEffect } from "react";
import ThemeToggle from "./ThemeToggle";

const GRAFANA_URL = process.env.NEXT_PUBLIC_GRAFANA_URL ?? "http://localhost:3001";
const PROMETHEUS_URL = process.env.NEXT_PUBLIC_PROMETHEUS_URL ?? "http://localhost:9090";

function useElapsed(lastUpdate: Date | null, active: boolean): string {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);

  if (!lastUpdate || !active) return "";
  const sec = Math.floor((now - lastUpdate.getTime()) / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const rem = sec % 60;
  return `${min}m ${rem.toString().padStart(2, "0")}s`;
}

interface AppHeaderProps {
  flash: { ok: boolean; msg: string } | null;
  connErr: boolean;
  isRunning: boolean;
  isStandby: boolean;
  loading: boolean;
  serial?: string;
  staleness: "ok" | "stale" | "offline";
  lastUpdate: Date | null;
  lastDeviceContact: Date | null;
  deviceOff?: boolean;
  connecting?: boolean;
}

export default function AppHeader({ flash, connErr, isRunning, isStandby, loading, serial, staleness, lastUpdate, lastDeviceContact, deviceOff, connecting }: AppHeaderProps) {
  const stale = staleness !== "ok";
  const showElapsed = !!deviceOff || !!connecting || stale;
  const elapsed = useElapsed(lastDeviceContact, showElapsed);

  let stateKey: string;
  let stateText: string;

  if (deviceOff) {
    stateKey = "offline";
    stateText = elapsed ? `NO DEVICE · ${elapsed}` : "NO DEVICE";
  } else if (connecting) {
    stateKey = "connecting";
    stateText = elapsed ? `CONNECTING · ${elapsed}` : "CONNECTING···";
  } else if (stale) {
    stateKey = staleness === "offline" ? "offline" : "stale";
    const label = staleness === "offline" ? "OFFLINE" : "STALE";
    stateText = elapsed ? `${label} · ${elapsed}` : label;
  } else if (isRunning) {
    stateKey = "running";
    stateText = "RUNNING";
  } else if (isStandby) {
    stateKey = "standby";
    stateText = "STANDBY";
  } else {
    stateKey = "unknown";
    stateText = "UNKNOWN";
  }

  return (
    <header className="app-header">
      <div className="header-brand">
        <span className="header-title">EBC10 CLIMATE CONTROL</span>
        <span className="header-subtitle">miniClima Schönbauer GmbH</span>
      </div>

      <div className="header-center">
        {flash && (
          <span className={`flash ${flash.ok ? "flash-ok" : "flash-err"}`}>
            {flash.msg}
          </span>
        )}
        {connErr && !flash && (
          <span className="flash flash-err">NO CONNECTION</span>
        )}
      </div>

      <div className="header-right">
        <nav className="header-nav" aria-label="Monitoring">
          <a className="nav-link" href={GRAFANA_URL} target="_blank" rel="noopener noreferrer">
            Grafana
          </a>
          <a className="nav-link amber" href={PROMETHEUS_URL} target="_blank" rel="noopener noreferrer">
            Prometheus
          </a>
        </nav>

        <div className="status-indicator">
          <span className={`status-dot ${stateKey}${(isRunning && !stale) || stale || deviceOff || connecting ? " dot-pulse" : ""}`} />
          <span className={`status-label ${stateKey}`}>
            {loading ? "···" : stateText}
          </span>
        </div>

        {serial && <span className="header-serial">{serial}</span>}
        <ThemeToggle />
      </div>
    </header>
  );
}

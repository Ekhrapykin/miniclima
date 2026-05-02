import ThemeToggle from "./ThemeToggle";

const GRAFANA_URL = process.env.NEXT_PUBLIC_GRAFANA_URL ?? "http://localhost:3001";
const PROMETHEUS_URL = process.env.NEXT_PUBLIC_PROMETHEUS_URL ?? "http://localhost:9090";

function formatAge(lastUpdate: Date | null): string {
  if (!lastUpdate) return "";
  const sec = Math.floor((Date.now() - lastUpdate.getTime()) / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  return `${min}m ago`;
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
}

export default function AppHeader({ flash, connErr, isRunning, isStandby, loading, serial, staleness, lastUpdate }: AppHeaderProps) {
  const stale = staleness !== "ok";
  const stateKey = stale
    ? (staleness === "offline" ? "offline" : "stale")
    : isRunning ? "running" : isStandby ? "standby" : "unknown";
  const stateText = stale
    ? `${staleness === "offline" ? "OFFLINE" : "STALE"} · ${formatAge(lastUpdate)}`
    : isRunning ? "RUNNING" : isStandby ? "STANDBY" : "UNKNOWN";

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
          <span className={`status-dot ${stateKey}${isRunning && !stale ? " dot-pulse" : stale ? " dot-pulse" : ""}`} />
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

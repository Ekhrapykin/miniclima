const GRAFANA_URL = process.env.NEXT_PUBLIC_GRAFANA_URL ?? "http://localhost:3001";
const PROMETHEUS_URL = process.env.NEXT_PUBLIC_PROMETHEUS_URL ?? "http://localhost:9090";

interface AppHeaderProps {
  flash: { ok: boolean; msg: string } | null;
  connErr: boolean;
  isRunning: boolean;
  isStandby: boolean;
  loading: boolean;
  serial?: string;
}

export default function AppHeader({ flash, connErr, isRunning, isStandby, loading, serial }: AppHeaderProps) {
  const stateKey = isRunning ? "running" : isStandby ? "standby" : "unknown";
  const stateText = isRunning ? "RUNNING" : isStandby ? "STANDBY" : "UNKNOWN";

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
          <span className={`status-dot ${stateKey}${isRunning ? " dot-pulse" : ""}`} />
          <span className={`status-label ${stateKey}`}>
            {loading ? "···" : stateText}
          </span>
        </div>

        {serial && <span className="header-serial">{serial}</span>}
      </div>
    </header>
  );
}

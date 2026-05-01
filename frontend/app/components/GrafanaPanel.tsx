const GRAFANA_URL = process.env.NEXT_PUBLIC_GRAFANA_URL ?? "http://localhost:3001";

export default function GrafanaPanel() {
  const src = `${GRAFANA_URL}/d-solo/ebc10/miniclima-ebc10?panelId=1&theme=dark&refresh=15s`;

  return (
    <div className="grafana-panel">
      <iframe src={src} className="grafana-iframe" />
    </div>
  );
}

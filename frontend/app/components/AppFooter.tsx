interface AppFooterProps {
  serial?: string;
  firmware?: string;
  lastUpdate: Date | null;
  staleness: "ok" | "stale" | "offline";
}

export default function AppFooter({ serial, firmware, lastUpdate, staleness }: AppFooterProps) {
  const color = staleness === "offline" ? "var(--err)" : staleness === "stale" ? "var(--amb)" : undefined;

  return (
    <footer className="app-footer">
      <span className="footer-device">
        {serial ?? "---"} &nbsp;·&nbsp; FW {firmware ?? "---"}
      </span>
      <span className="footer-updated" style={color ? { color } : undefined}>
        {lastUpdate ? `UPDATED ${lastUpdate.toLocaleTimeString()}` : "CONNECTING···"}
      </span>
    </footer>
  );
}

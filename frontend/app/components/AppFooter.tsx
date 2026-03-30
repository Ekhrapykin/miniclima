interface AppFooterProps {
  serial?: string;
  firmware?: string;
  lastUpdate: Date | null;
}

export default function AppFooter({ serial, firmware, lastUpdate }: AppFooterProps) {
  return (
    <footer className="app-footer">
      <span className="footer-device">
        {serial ?? "---"} &nbsp;·&nbsp; FW {firmware ?? "---"}
      </span>
      <span className="footer-updated">
        {lastUpdate ? `UPDATED ${lastUpdate.toLocaleTimeString()}` : "CONNECTING···"}
      </span>
    </footer>
  );
}

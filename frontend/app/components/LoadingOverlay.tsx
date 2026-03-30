export default function LoadingOverlay() {
  return (
    <div className="loading-overlay">
      <svg width="40" height="40" viewBox="0 0 40 40">
        <circle cx="20" cy="20" r="16" fill="none" stroke="var(--ph-dim)" strokeWidth="3" />
        <circle
          cx="20" cy="20" r="16"
          fill="none"
          stroke="var(--ph)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="25 76"
          className="loading-spinner-arc"
        />
      </svg>
      <span className="loading-text">CONNECTING···</span>
    </div>
  );
}

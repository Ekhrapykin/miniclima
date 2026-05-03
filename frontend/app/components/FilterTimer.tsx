"use client";

import { useState, useEffect } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const YEAR_MS = 365.25 * 24 * 60 * 60 * 1000;
const WARN_MS = 90 * 24 * 60 * 60 * 1000;

function formatCountdown(ms: number): string {
  const days = Math.floor(Math.abs(ms) / (24 * 60 * 60 * 1000));
  if (days > 60) {
    const months = Math.floor(days / 30);
    const rem = days % 30;
    return rem > 0 ? `${months}mo ${rem}d` : `${months}mo`;
  }
  return `${days}d`;
}

export default function FilterTimer() {
  const [changedDate, setChangedDate] = useState<Date | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch(`${API}/filter-date`)
      .then((r) => r.json())
      .then((d) => {
        if (d.date) setChangedDate(new Date(d.date));
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  const handleReset = async () => {
    const now = new Date();
    try {
      await fetch(`${API}/filter-date`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: now.toISOString() }),
      });
      setChangedDate(now);
    } catch {
      setChangedDate(now);
    }
  };

  if (!loaded) return null;

  if (!changedDate) {
    return (
      <div className="cell cell-full filter-timer filter-unknown">
        <span className="cell-label">Filter Status</span>
        <div className="filter-timer-content">
          <span className="cell-val dim">No data</span>
          <button className="btn filter-reset-btn" onClick={handleReset}>
            Mark as changed today
          </button>
        </div>
      </div>
    );
  }

  const nextChange = new Date(changedDate.getTime() + YEAR_MS);
  const remaining = nextChange.getTime() - Date.now();
  const overdue = remaining < 0;
  const warning = !overdue && remaining < WARN_MS;
  const status = overdue ? "overdue" : warning ? "warning" : "ok";

  return (
    <div className={`cell cell-full filter-timer filter-${status}`}>
      <span className="cell-label">Filter Change</span>
      <div className="filter-timer-content">
        <div className="filter-timer-info">
          {overdue ? (
            <span className="cell-val filter-overdue-text">
              OVERDUE {formatCountdown(remaining)}
            </span>
          ) : (
            <span className={`cell-val${warning ? "" : " dim"}`} style={warning ? { color: "var(--amb)" } : undefined}>
              {formatCountdown(remaining)} remaining
            </span>
          )}
          <span className="filter-date">
            Changed: {changedDate.toLocaleDateString()} · Due: {nextChange.toLocaleDateString()}
          </span>
        </div>
        <button className="btn filter-reset-btn" onClick={handleReset}>
          Reset
        </button>
      </div>
    </div>
  );
}

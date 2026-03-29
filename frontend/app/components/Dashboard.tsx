"use client";

import { useState, useEffect, useRef } from "react";

// ─── API ─────────────────────────────────────────────────────────────────────
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── SVG gauge geometry ───────────────────────────────────────────────────────
const R = 80;
const CX = 100;
const CY = 100;
const CIRC = 2 * Math.PI * R;
const SWEEP = 240;
const ARC = CIRC * (SWEEP / 360);
const ROTATE = 150;

function clockRad(deg: number) {
  return (deg - 90) * (Math.PI / 180);
}
function pctToDeg(pct: number) {
  return 240 + (Math.max(0, Math.min(100, pct)) / 100) * 240;
}
function gaugePoint(pct: number, r: number): [number, number] {
  const a = clockRad(pctToDeg(pct));
  return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
}

// ─── types ────────────────────────────────────────────────────────────────────
interface Sernum {
  serial?: string;
  firmware?: string;
  sp?: number;
  lo?: number;
  hi?: number;
  hy?: number;
  lt?: number;
  to?: number;
}
interface Vals {
  state?: string;
  rh?: number;
  t1?: number;
  t2?: number;
  flag?: string;
}

// ─── sub-components ───────────────────────────────────────────────────────────
function Cell({
  label,
  value,
  amber,
  dim,
}: {
  label: string;
  value: string | number;
  amber?: boolean;
  dim?: boolean;
}) {
  return (
    <div className="cell">
      <span className="cell-label">{label}</span>
      <span className={`cell-val${amber ? " amber" : dim ? " dim" : ""}`}>
        {value}
      </span>
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────
export default function Dashboard() {
  const [sernum, setSernum] = useState<Sernum>({});
  const [vals, setVals] = useState<Vals>({});
  const [ophours, setOphours] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [connErr, setConnErr] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [spDraft, setSpDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<{ ok: boolean; msg: string } | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [logDraft, setLogDraft] = useState("");
  const [readRate, setReadRate] = useState(5);

  // init SP input once when first non-null SP arrives
  const spInitRef = useRef(false);
  useEffect(() => {
    if (!spInitRef.current && sernum.sp != null) {
      setSpDraft(String(sernum.sp));
      spInitRef.current = true;
    }
  }, [sernum.sp]);

  // init log interval input once when first non-null lt arrives
  const ltInitRef = useRef(false);
  useEffect(() => {
    if (!ltInitRef.current && sernum.lt != null) {
      setLogDraft(String(sernum.lt));
      ltInitRef.current = true;
    }
  }, [sernum.lt]);

  const showFlash = (ok: boolean, msg: string) => {
    setFlash({ ok, msg });
    setTimeout(() => setFlash(null), 3000);
  };

  // WebSocket connection with reconnect
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectDelay = 1000;
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      const wsUrl = API.replace(/^http/, "ws") + "/ws";
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        reconnectDelay = 1000;
        setConnErr(false);
      };

      ws.onmessage = (ev) => {
        try {
          const d = JSON.parse(ev.data);
          setSernum(d.sernum ?? {});
          setVals(d.vals ?? {});
          if (d.ophours != null) setOphours(d.ophours);
          setLastUpdate(new Date());
          setConnErr(false);
          setLoading(false);
        } catch { /* ignore malformed messages */ }
      };

      ws.onclose = () => {
        if (cancelled) return;
        setConnErr(true);
        setTimeout(connect, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 30000);
      };

      ws.onerror = () => {
        ws?.close();
      };
    }

    connect();
    return () => {
      cancelled = true;
      ws?.close();
    };
  }, []);

  const post = async (path: string, body?: object) => {
    setBusy(true);
    try {
      const r = await fetch(`${API}${path}`, {
        method: "POST",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      showFlash(r.ok, r.ok ? "OK" : `Error ${r.status}`);
    } catch {
      showFlash(false, "Connection error");
    } finally {
      setBusy(false);
    }
  };

  // ── derived values ──────────────────────────────────────────────────────────
  const rh = vals.rh ?? 0;
  const sp = sernum.sp ?? 50;
  const isRunning = vals.state === "running";
  const isStandby = vals.state === "standby";

  const rhArc = (rh / 100) * ARC;
  const [spX1, spY1] = gaugePoint(sp, 71);
  const [spX2, spY2] = gaugePoint(sp, 93);

  const stateColor = isRunning ? "var(--run)" : isStandby ? "var(--sby)" : "var(--tx-dim)";
  const stateText = isRunning ? "RUNNING" : isStandby ? "STANDBY" : "UNKNOWN";

  const stepSp = (delta: number) => {
    const current = spDraft !== "" ? parseInt(spDraft) || sp : sp;
    setSpDraft(String(Math.max(0, Math.min(99, current + delta))));
  };

  // ── render ──────────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: "auto 1fr auto auto auto",
        minHeight: "100vh",
        fontFamily: "var(--font-sans)",
      }}
    >
      {/* ── LOADING OVERLAY ── */}
      {loading && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "var(--bg)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 16,
            zIndex: 100,
          }}
        >
          <svg width="40" height="40" viewBox="0 0 40 40">
            <circle
              cx="20" cy="20" r="16"
              fill="none"
              stroke="var(--ph-dim)"
              strokeWidth="3"
            />
            <circle
              cx="20" cy="20" r="16"
              fill="none"
              stroke="var(--ph)"
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray="25 76"
              style={{ transformOrigin: "20px 20px", animation: "spin 1s linear infinite" }}
            />
          </svg>
          <span
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: 11,
              letterSpacing: "0.22em",
              color: "var(--tx-label)",
            }}
          >
            CONNECTING···
          </span>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* ── HEADER ── */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 28px",
          borderBottom: "1px solid var(--border)",
          background: "var(--surface)",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
          <span
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: 13,
              letterSpacing: "0.22em",
              fontWeight: 700,
              color: "var(--tx)",
            }}
          >
            EBC10 CLIMATE CONTROL
          </span>
          <span
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: 10,
              letterSpacing: "0.14em",
              color: "var(--tx-label)",
            }}
          >
            miniClima Schönbauer GmbH
          </span>
        </div>

        <div style={{ minWidth: 160, textAlign: "center" }}>
          {flash && (
            <span
              className="flash"
              style={{
                color: flash.ok ? "var(--ph)" : "var(--err)",
                letterSpacing: "0.14em",
                fontFamily: "var(--font-sans)",
                fontWeight: 600,
              }}
            >
              {flash.msg}
            </span>
          )}
          {connErr && !flash && (
            <span
              className="flash"
              style={{
                color: "var(--err)",
                letterSpacing: "0.14em",
                fontFamily: "var(--font-sans)",
              }}
            >
              NO CONNECTION
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              className={isRunning ? "dot-pulse" : ""}
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: stateColor,
                display: "inline-block",
                boxShadow: isRunning ? "0 0 8px var(--run)" : "none",
              }}
            />
            <span
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: 11,
                letterSpacing: "0.16em",
                color: stateColor,
                fontWeight: 600,
              }}
            >
              {loading ? "···" : stateText}
            </span>
          </div>
          {sernum.serial && (
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--tx-label)",
                letterSpacing: "0.1em",
              }}
            >
              {sernum.serial}
            </span>
          )}
        </div>
      </header>

      {/* ── MAIN ── */}
      <main
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
        }}
      >
        {/* left: gauge panel */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "40px 32px",
            borderRight: "1px solid var(--border)",
            gap: 20,
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: 9,
              letterSpacing: "0.28em",
              color: "var(--tx-label)",
              textTransform: "uppercase",
            }}
          >
            Relative Humidity
          </span>

          <svg
            viewBox="0 0 200 200"
            style={{ width: "min(300px, 80vw)" }}
            aria-label={`Humidity: ${rh}%`}
          >
            <defs>
              <filter id="ph-glow" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur in="SourceGraphic" stdDeviation="2.5" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="amb-glow" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur in="SourceGraphic" stdDeviation="1.8" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <circle
              cx={CX} cy={CY} r={R}
              fill="none"
              stroke="var(--ph-dim)"
              strokeWidth={5}
              strokeLinecap="round"
              strokeDasharray={`${ARC} ${CIRC - ARC}`}
              transform={`rotate(${ROTATE} ${CX} ${CY})`}
            />
            <circle
              cx={CX} cy={CY} r={R}
              fill="none"
              stroke="var(--ph)"
              strokeWidth={5}
              strokeLinecap="round"
              strokeDasharray={`${rhArc} ${CIRC - rhArc}`}
              transform={`rotate(${ROTATE} ${CX} ${CY})`}
              filter="url(#ph-glow)"
              className="gauge-arc"
            />
            <line
              x1={spX1} y1={spY1} x2={spX2} y2={spY2}
              stroke="var(--amb)"
              strokeWidth={2.5}
              strokeLinecap="round"
              filter="url(#amb-glow)"
            />
            <text
              x={CX} y={CY - 10}
              textAnchor="middle"
              fill="var(--ph)"
              fontSize={46}
              fontFamily="var(--font-mono)"
              filter="url(#ph-glow)"
            >
              {loading ? "--" : rh}
            </text>
            <text
              x={CX} y={CY + 18}
              textAnchor="middle"
              fill="rgba(0,232,162,0.5)"
              fontSize={12}
              fontFamily="var(--font-sans)"
              letterSpacing="4"
              fontWeight="600"
            >
              % RH
            </text>
            <text
              x={gaugePoint(sp, 60)[0]}
              y={gaugePoint(sp, 60)[1]}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="var(--amb)"
              fontSize={8}
              fontFamily="var(--font-sans)"
              letterSpacing="1"
            >
              SP
            </text>
            {vals.flag === "p" && (
              <text
                x={CX} y={CY + 40}
                textAnchor="middle"
                fill="rgba(0,232,162,0.5)"
                fontSize={8}
                fontFamily="var(--font-sans)"
                letterSpacing="3"
              >
                PELTIER
              </text>
            )}
            {vals.flag === "*" && (
              <text
                x={CX} y={CY + 40}
                textAnchor="middle"
                fill="var(--err)"
                fontSize={8}
                fontFamily="var(--font-sans)"
                letterSpacing="3"
              >
                SENSOR ERR
              </text>
            )}
          </svg>

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                width: 20,
                height: 2,
                background: "var(--amb)",
                display: "inline-block",
                borderRadius: 1,
              }}
            />
            <span
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: 10,
                letterSpacing: "0.14em",
                color: "var(--tx-label)",
              }}
            >
              SETPOINT {sp}%
            </span>
          </div>
        </div>

        {/* right: readings panel */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gridTemplateRows: "auto auto auto",
            background: "var(--border)",
            alignContent: "start",
            padding: "40px 32px",
            gap: 12,
          }}
        >
          <Cell label="T1 cold side" value={vals.t1 != null ? `${vals.t1}°C` : "--"} />
          <Cell label="T2 hot side"  value={vals.t2 != null ? `${vals.t2}°C` : "--"} />
          <Cell label="Setpoint"     value={sernum.sp != null ? `${sernum.sp}%` : "--"} amber />
          <Cell label="Hysteresis"   value={sernum.hy != null ? `×${sernum.hy}` : "--"} amber />
          <Cell label="Alarm Lo"     value={sernum.lo != null ? `${sernum.lo}%` : "--"} dim />
          <Cell label="Alarm Hi"     value={sernum.hi != null ? `${sernum.hi}%` : "--"} dim />
          <Cell label="Log interval" value={sernum.lt != null ? `${sernum.lt} min` : "--"} dim />
          <Cell label="Temp offset"  value={sernum.to != null ? `${sernum.to > 0 ? "+" : ""}${sernum.to}°C` : "--"} dim />
          <div className="cell" style={{ gridColumn: "1 / -1" }}>
            <span className="cell-label">Operating hours</span>
            <span
              className="cell-val dim"
              style={{ fontSize: 28, fontFamily: "var(--font-mono)" }}
            >
              {ophours != null ? String(ophours).padStart(6, "0") : "------"}
            </span>
          </div>
        </div>
      </main>

      {/* ── CONTROLS ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "20px 28px",
          borderTop: "1px solid var(--border)",
          background: "var(--surface)",
          flexWrap: "wrap",
        }}
      >
        <button
          className="btn"
          disabled={busy || isRunning}
          onClick={() => post("/start")}
          style={isRunning ? { borderColor: "var(--run)", color: "var(--run)" } : {}}
        >
          ▶ Start
        </button>
        <button
          className="btn"
          disabled={busy || isStandby}
          onClick={() => post("/stop")}
        >
          ■ Stop
        </button>

        <div style={{ width: 1, height: 32, background: "var(--border-hi)", margin: "0 8px" }} />

        {/* setpoint setter */}
        <span
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: 10,
            letterSpacing: "0.16em",
            color: "var(--tx-label)",
          }}
        >
          SET SP
        </span>
        <button
          className="btn amber"
          disabled={busy}
          onClick={() => stepSp(-1)}
          style={{ padding: "10px 14px" }}
        >
          −
        </button>
        <input
          type="number"
          min={0}
          max={99}
          value={spDraft}
          onChange={(e) => setSpDraft(e.target.value)}
          className="sp-input"
          onKeyDown={(e) => {
            if (e.key === "Enter" && spDraft) {
              post("/setpoint", { rh_percent: parseInt(spDraft) });
            }
          }}
        />
        <button
          className="btn amber"
          disabled={busy}
          onClick={() => stepSp(1)}
          style={{ padding: "10px 14px" }}
        >
          +
        </button>
        <span
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: 10,
            letterSpacing: "0.1em",
            color: "var(--tx-label)",
          }}
        >
          %
        </span>
        <button
          className="btn amber"
          disabled={busy || !spDraft}
          onClick={() => post("/setpoint", { rh_percent: parseInt(spDraft) })}
        >
          Apply
        </button>

        <div style={{ flex: 1 }} />

        {/* settings toggle */}
        <button
          className="btn"
          onClick={() => setSettingsOpen((v) => !v)}
          style={{ marginLeft: "auto" }}
        >
          ⚙ Settings {settingsOpen ? "▴" : "▾"}
        </button>
      </div>

      {/* ── SETTINGS PANEL ── */}
      {settingsOpen && (
        <div
          style={{
            borderTop: "1px solid var(--border)",
            background: "var(--surface-2)",
            padding: "24px 28px",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
              gap: 12,
              marginBottom: 16,
            }}
          >
            {/* read-only alarm / hy cells */}
            <div className="cell">
              <span className="cell-label">Alarm Lo (read-only)</span>
              <span className="cell-val dim">
                {sernum.lo != null ? `${sernum.lo}%` : "--"}
              </span>
            </div>
            <div className="cell">
              <span className="cell-label">Alarm Hi (read-only)</span>
              <span className="cell-val dim">
                {sernum.hi != null ? `${sernum.hi}%` : "--"}
              </span>
            </div>
            <div className="cell">
              <span className="cell-label">Hysteresis (read-only)</span>
              <span className="cell-val dim">
                {sernum.hy != null ? `×${sernum.hy}` : "--"}
              </span>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            {/* log interval */}
            <span
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: 10,
                letterSpacing: "0.16em",
                color: "var(--tx-label)",
              }}
            >
              LOG INTERVAL
            </span>
            <input
              type="number"
              min={1}
              max={99}
              value={logDraft}
              onChange={(e) => setLogDraft(e.target.value)}
              className="sp-input"
              onKeyDown={(e) => {
                if (e.key === "Enter" && logDraft)
                  post("/set-log-time", { minutes: parseInt(logDraft) });
              }}
            />
            <span
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: 10,
                letterSpacing: "0.1em",
                color: "var(--tx-label)",
              }}
            >
              min
            </span>
            <button
              className="btn amber"
              disabled={busy || !logDraft}
              onClick={() => post("/set-log-time", { minutes: parseInt(logDraft) })}
            >
              Apply
            </button>

            <div style={{ width: 1, height: 32, background: "var(--border-hi)", margin: "0 16px" }} />

            {/* data read rate */}
            <span
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: 10,
                letterSpacing: "0.16em",
                color: "var(--tx-label)",
              }}
            >
              READ RATE
            </span>
            <input
              type="number"
              min={1}
              max={60}
              value={readRate}
              onChange={(e) => setReadRate(Math.max(1, parseInt(e.target.value) || 5))}
              className="sp-input"
            />
            <span
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: 10,
                letterSpacing: "0.1em",
                color: "var(--tx-label)",
              }}
            >
              sec
            </span>
          </div>
        </div>
      )}

      {/* ── FOOTER ── */}
      <footer
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 28px",
          borderTop: "1px solid var(--border)",
          background: "var(--surface-2)",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--tx-dim)",
            letterSpacing: "0.08em",
          }}
        >
          {sernum.serial ?? "---"} &nbsp;·&nbsp; FW {sernum.firmware ?? "---"}
        </span>
        <span
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: 10,
            color: "var(--tx-dim)",
            letterSpacing: "0.1em",
          }}
        >
          {lastUpdate
            ? `UPDATED ${lastUpdate.toLocaleTimeString()}`
            : "CONNECTING···"}
        </span>
      </footer>
    </div>
  );
}

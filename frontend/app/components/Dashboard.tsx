"use client";

import { useState, useEffect, useRef } from "react";
import type { Sernum, Vals } from "../types";
import AppHeader from "./AppHeader";
import AppFooter from "./AppFooter";
import Controls from "./Controls";
import HumidityGauge from "./HumidityGauge";
import LoadingOverlay from "./LoadingOverlay";
import ReadingsGrid from "./ReadingsGrid";
import SettingsPanel from "./SettingsPanel";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  const [importState, setImportState] = useState<{ loading: boolean; ok?: boolean; msg?: string } | null>(null);

  const spInitRef = useRef(false);
  useEffect(() => {
    if (!spInitRef.current && sernum.sp != null) {
      setSpDraft(String(sernum.sp));
      spInitRef.current = true;
    }
  }, [sernum.sp]);

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

      ws.onerror = () => { ws?.close(); };
    }

    connect();
    return () => { cancelled = true; ws?.close(); };
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

  const rh = vals.rh ?? 0;
  const sp = sernum.sp ?? 50;
  const isRunning = vals.state === "running";
  const isStandby = vals.state === "standby";

  const importHistory = async () => {
    setImportState({ loading: true });
    try {
      const r = await fetch(`${API}/dump/import`, { method: "POST" });
      const json = await r.json();
      const typesSummary = json.types
        ? Object.entries(json.types as Record<string, number>)
            .map(([t, n]) => `${n}×${t}`)
            .join(", ")
        : "";
      setImportState({
        loading: false,
        ok: r.ok,
        msg: r.ok
          ? `Pushed ${json.pushed} series (${typesSummary})`
          : `Error ${r.status}`,
      });
    } catch {
      setImportState({ loading: false, ok: false, msg: "Connection error" });
    }
  };

  const stepSp = (delta: number) => {
    const current = spDraft !== "" ? parseInt(spDraft) || sp : sp;
    setSpDraft(String(Math.max(0, Math.min(99, current + delta))));
  };

  return (
    <div className="dashboard">
      {loading && <LoadingOverlay />}

      <AppHeader
        flash={flash}
        connErr={connErr}
        isRunning={isRunning}
        isStandby={isStandby}
        loading={loading}
        serial={sernum.serial}
      />

      <main className="main-grid">
        <HumidityGauge rh={rh} sp={sp} loading={loading} flag={vals.flag} />
        <ReadingsGrid vals={vals} sernum={sernum} ophours={ophours} />
      </main>

      <Controls
        busy={busy}
        isRunning={isRunning}
        isStandby={isStandby}
        spDraft={spDraft}
        setSpDraft={setSpDraft}
        settingsOpen={settingsOpen}
        setSettingsOpen={setSettingsOpen}
        onPost={post}
        stepSp={stepSp}
      />

      <SettingsPanel
        open={settingsOpen}
        busy={busy}
        logDraft={logDraft}
        setLogDraft={setLogDraft}
        onPost={post}
        importState={importState}
        onImport={importHistory}
      />

      <AppFooter
        serial={sernum.serial}
        firmware={sernum.firmware}
        lastUpdate={lastUpdate}
      />
    </div>
  );
}

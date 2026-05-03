"use client";

import { useState, useEffect } from "react";
import type { Sernum, Vals } from "../types";
import AppHeader from "./AppHeader";
import AppFooter from "./AppFooter";
import Controls from "./Controls";
import GrafanaPanel from "./GrafanaPanel";
import HumidityGauge from "./HumidityGauge";
import LoadingOverlay from "./LoadingOverlay";
import ReadingsGrid from "./ReadingsGrid";
import SettingsModal from "./SettingsModal";
import ExportModal from "./ExportModal";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Dashboard() {
  const [sernum, setSernum] = useState<Sernum>({});
  const [vals, setVals] = useState<Vals>({});
  const [ophours, setOphours] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [connErr, setConnErr] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [lastDeviceContact, setLastDeviceContact] = useState<Date | null>(null);

  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<{ ok: boolean; msg: string } | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [importState, setImportState] = useState<{ loading: boolean; ok?: boolean; msg?: string; startedAt?: number } | null>(null);
  const [staleness, setStaleness] = useState<"ok" | "stale" | "offline">("ok");
  const [deviceStatus, setDeviceStatus] = useState<true | false | "connecting">("connecting");

  useEffect(() => {
    const interval = setInterval(() => {
      if (!lastUpdate) return;
      const age = Date.now() - lastUpdate.getTime();
      if (age > 300_000) setStaleness("offline");
      else if (age > 60_000) setStaleness("stale");
      else setStaleness("ok");
    }, 5000);
    return () => clearInterval(interval);
  }, [lastUpdate]);

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
          const ds = d.device_connected === true ? true : d.device_connected === false ? false : "connecting" as const;
          setDeviceStatus(ds);
          if (ds === true) {
            setSernum(d.sernum ?? {});
            setVals(d.vals ?? {});
            if (d.ophours != null) setOphours(d.ophours);
          }
          if (d.last_contact) setLastDeviceContact(new Date(d.last_contact));
          setLastUpdate(new Date());
          setConnErr(false);
          setStaleness("ok");
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

  const isRunning = vals.state === "running";
  const isStandby = vals.state === "standby";
  const deviceOff = !loading && deviceStatus === false;
  const connecting = !loading && deviceStatus === "connecting";
  const rh = vals.rh ?? 0;
  const sp = sernum.sp ?? 50;

  const importHistory = async () => {
    setImportState({ loading: true, startedAt: Date.now() });
    try {
      const r = await fetch(`${API}/dump/import`, { method: "POST" });
      const json = await r.json();
      if (r.ok) {
        const typesSummary = json.types
          ? Object.entries(json.types as Record<string, number>)
              .map(([t, n]) => `${n}×${t}`)
              .join(", ")
          : "";
        console.log(`[import] Pushed ${json.pushed} series (${typesSummary})`);
      } else {
        console.error(`[import] Error ${r.status}`, json);
      }
      setImportState({ loading: false });
    } catch (e) {
      console.error("[import] Connection error", e);
      setImportState({ loading: false });
    }
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
        staleness={staleness}
        lastUpdate={lastUpdate}
        lastDeviceContact={lastDeviceContact}
        deviceOff={deviceOff}
        connecting={connecting}
      />

      <main className="main-grid">
        <HumidityGauge rh={rh} sp={sp} lo={sernum.lo} hi={sernum.hi} loading={loading} flag={vals.flag} t={vals.t} deviceOff={deviceOff} />
        <div className="right-column">
          <ReadingsGrid vals={vals} sernum={sernum} ophours={ophours} deviceOff={deviceOff} />
          <GrafanaPanel />
        </div>
      </main>

      <Controls
        busy={busy}
        isRunning={isRunning}
        isStandby={isStandby}
        onPost={post}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenExport={() => setExportOpen(true)}
        importState={importState}
        onImport={importHistory}
      />

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        busy={busy}
        sernum={sernum}
        onPost={post}
      />

      <ExportModal
        open={exportOpen}
        onClose={() => setExportOpen(false)}
      />

      <AppFooter
        serial={sernum.serial}
        firmware={sernum.firmware}
        lastUpdate={lastUpdate}
        staleness={staleness}
      />
    </div>
  );
}

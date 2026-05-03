"""
miniClima EBC10 — FastAPI server with WebSocket push.

Run:
    uvicorn api.main:app --reload

Config via env vars:
    EBC10_PORT          (default: /dev/ttyACM0)
    EBC10_BAUD          (default: 9600)
    EBC10_POLL_INTERVAL (default: 5, seconds between device polls)
    CORS_ORIGINS        (default: *, comma-separated list of allowed origins)
    PROMETHEUS_URL      (default: http://prometheus:9090)
    LOG_LEVEL           (default: INFO — set DEBUG to see ebc10 serial traffic)
"""

import asyncio
import json
import logging
import os
import urllib.request
import urllib.parse
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import api.connection as conn
from api.poll import poll_loop
from api.prometheus import metrics_response, push_records_to_prometheus
from api.store import load as load_state, get_last_poll, get_last_contact, get_filter_date, set_filter_date
from ebc10.utils import parse_dump_records

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

log = logging.getLogger("api")


# --- app lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger("ebc10").setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    load_state()
    saved = get_last_poll()
    if saved:
        saved["device_connected"] = "connecting"
        saved["last_contact"] = get_last_contact()
        conn._latest = saved
    conn._lock = asyncio.Lock()
    task = asyncio.create_task(poll_loop())
    yield
    task.cancel()
    conn.close_client()


app = FastAPI(title="miniClima EBC10 API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    conn._ws_clients.add(ws)
    if conn._latest:
        await ws.send_text(json.dumps(conn._latest))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        conn._ws_clients.discard(ws)


# --- Prometheus scrape endpoint ---

@app.get("/metrics")
async def metrics():
    return metrics_response()


# --- read endpoints (return cached _latest when available) ---

@app.get("/status")
async def status():
    if conn._latest:
        return conn._latest
    async with conn._lock:
        return await asyncio.to_thread(conn.read_status)


@app.get("/vals")
async def vals():
    if conn._latest and "vals" in conn._latest:
        return conn._latest["vals"]
    async with conn._lock:
        return await asyncio.to_thread(lambda: conn.ensure_connected().read_vals())


@app.get("/sernum")
async def sernum():
    if conn._latest and "sernum" in conn._latest:
        return conn._latest["sernum"]
    async with conn._lock:
        return await asyncio.to_thread(lambda: conn.ensure_connected().read_sernum())


@app.get("/date")
async def date():
    async with conn._lock:
        return {"date": await asyncio.to_thread(lambda: conn.ensure_connected().read_date())}


@app.get("/time")
async def time_():
    async with conn._lock:
        return {"time": await asyncio.to_thread(lambda: conn.ensure_connected().read_time())}


@app.get("/ophours")
async def ophours():
    if conn._latest and "ophours" in conn._latest:
        return {"ophours": conn._latest["ophours"]}
    async with conn._lock:
        return {"ophours": await asyncio.to_thread(lambda: conn.ensure_connected().read_ophours())}


@app.get("/dump")
async def dump():
    async with conn._lock:
        return {"data": await asyncio.to_thread(lambda: conn.ensure_connected().dump())}


@app.post("/dump/import")
async def dump_import():
    """Retrieve full history dump, parse records, and push to Prometheus as historical samples."""
    async with conn._lock:
        hex_str = await asyncio.to_thread(lambda: conn.ensure_connected().clean_dump())
        conn._draining = True  # set before releasing lock so poll skips its next cycle
    records = parse_dump_records(bytearray.fromhex(hex_str))
    log.debug(f"records: {records}")
    pushed = await asyncio.to_thread(push_records_to_prometheus, records)
    type_counts: dict[str, int] = {}
    for r in records:
        type_counts[r["type"]] = type_counts.get(r["type"], 0) + 1
    asyncio.create_task(_drain_after_dump())
    return {"total": len(records), "pushed": pushed, "types": type_counts}


async def _drain_after_dump():
    async with conn._lock:
        try:
            await asyncio.to_thread(conn.ensure_connected().drain_to_terminator)
        except Exception as e:
            log.warning("background drain failed: %s", e)
        finally:
            conn._draining = False


# --- write endpoints ---

async def _write(method: str, *args) -> bool:
    async with conn._lock:
        return await asyncio.to_thread(conn.exec_write, method, *args)


@app.post("/start")
async def start():
    ok = await _write("start")
    if not ok:
        raise HTTPException(status_code=502, detail="start command failed")
    return {"ok": True}


@app.post("/stop")
async def stop():
    ok = await _write("stop")
    if not ok:
        raise HTTPException(status_code=502, detail="stop command failed")
    return {"ok": True}


class SetValRequest(BaseModel):
    val: int


@app.post("/setpoint")
async def setpoint(req: SetValRequest):
    ok = await _write("set_setpoint", req.val)
    if not ok:
        raise HTTPException(status_code=502, detail="set_setpoint command failed")
    return {"ok": True}


@app.post("/log-time")
async def set_log_time(req: SetValRequest):
    ok = await _write("set_log_time", req.val)
    if not ok:
        raise HTTPException(status_code=502, detail="set_log_time command failed")
    return {"ok": True}


@app.post("/alarm-min")
async def set_alarm_min(req: SetValRequest):
    ok = await _write("set_alarm_min", req.val)
    if not ok:
        raise HTTPException(status_code=502, detail="set_alarm_min command failed")
    return {"ok": True}

@app.post("/alarm-max")
async def set_alarm_max(req: SetValRequest):
    ok = await _write("set_alarm_max", req.val)
    if not ok:
        raise HTTPException(status_code=502, detail="set_alarm_max command failed")
    return {"ok": True}


@app.post("/hysteresis")
async def set_hysteresis(req: SetValRequest):
    ok = await _write("set_hysteresis", req.val)
    if not ok:
        raise HTTPException(status_code=502, detail="set_hysteresis command failed")
    return {"ok": True}


@app.post("/rhcorr")
async def set_rhcorr(req: SetValRequest):
    ok = await _write("set_rhcorr", req.val)
    if not ok:
        raise HTTPException(status_code=502, detail="set_rhcorr command failed")
    return {"ok": True}


class SetDateRequest(BaseModel):
    date: str  # DD.MM.YY


@app.post("/date")
async def set_date(req: SetDateRequest):
    ok = await _write("set_date", req.date)
    if not ok:
        raise HTTPException(status_code=502, detail="set_date command failed")
    return {"ok": True}


class SetTimeRequest(BaseModel):
    time: str  # HH:MM


@app.post("/time")
async def set_time(req: SetTimeRequest):
    ok = await _write("set_time", req.time)
    if not ok:
        raise HTTPException(status_code=502, detail="set_time command failed")
    return {"ok": True}


# --- filter date ---

@app.get("/filter-date")
async def get_filter_date_endpoint():
    return {"date": get_filter_date()}


class FilterDateRequest(BaseModel):
    date: str


@app.post("/filter-date")
async def set_filter_date_endpoint(req: FilterDateRequest):
    set_filter_date(req.date)
    return {"ok": True}


# --- export data from Prometheus ---

PROMETHEUS_BASE = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

EXPORT_METRICS = {
    "humidity":  "ebc10_humidity_percent",
    "setpoint":  "ebc10_setpoint_percent",
    "alarm_min": "ebc10_humidity_min",
    "alarm_max": "ebc10_humidity_max",
    "t_ambient": 'ebc10_temperature_celsius{sensor="t_out"}',
}

PERIOD_SECONDS = {
    "1w": 7 * 86400,
    "1m": 30 * 86400,
    "3m": 90 * 86400,
    "1y": 365 * 86400,
}

STEP_FOR_PERIOD = {
    "1w": "5m",
    "1m": "15m",
    "3m": "1h",
    "1y": "6h",
}


@app.get("/export-data")
async def export_data(period: str = Query(default="1m")):
    if period not in PERIOD_SECONDS:
        raise HTTPException(status_code=400, detail=f"Invalid period. Use: {list(PERIOD_SECONDS.keys())}")

    import time
    end = time.time()
    start = end - PERIOD_SECONDS[period]
    step = STEP_FOR_PERIOD[period]

    async def query_metric(name: str, expr: str) -> dict:
        params = urllib.parse.urlencode({"query": expr, "start": start, "end": end, "step": step})
        url = f"{PROMETHEUS_BASE}/api/v1/query_range?{params}"
        try:
            resp = await asyncio.to_thread(lambda: urllib.request.urlopen(url, timeout=15).read())
            data = json.loads(resp)
            if data.get("status") == "success" and data["data"]["result"]:
                values = data["data"]["result"][0]["values"]
                return {"name": name, "values": [[int(ts), float(val)] for ts, val in values]}
        except Exception as e:
            log.warning("Prometheus query failed for %s: %s", name, e)
        return {"name": name, "values": []}

    results = await asyncio.gather(*[query_metric(name, expr) for name, expr in EXPORT_METRICS.items()])
    return {"period": period, "step": step, "metrics": {r["name"]: r["values"] for r in results}}

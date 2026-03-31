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
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import api.connection as conn
from api.poll import poll_loop
from api.prometheus import metrics_response, push_records_to_prometheus
from ebc10.utils import parse_dump_records

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

log = logging.getLogger("api")


# --- app lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger("ebc10").setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
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
    records = parse_dump_records(bytearray.fromhex(hex_str))
    log.debug(f"records: {records}")
    pushed = await asyncio.to_thread(push_records_to_prometheus, records)
    type_counts: dict[str, int] = {}
    for r in records:
        type_counts[r["type"]] = type_counts.get(r["type"], 0) + 1
    return {"total": len(records), "pushed": pushed, "types": type_counts}


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


class SetpointRequest(BaseModel):
    rh_percent: int


@app.post("/setpoint")
async def setpoint(req: SetpointRequest):
    ok = await _write("set_setpoint", req.rh_percent)
    if not ok:
        raise HTTPException(status_code=502, detail="set_setpoint command failed")
    return {"ok": True}


class SetLogTimeRequest(BaseModel):
    minutes: int


@app.post("/set-log-time")
async def set_log_time(req: SetLogTimeRequest):
    ok = await _write("set_log_time", req.minutes)
    if not ok:
        raise HTTPException(status_code=502, detail="set_log_time command failed")
    return {"ok": True}


class SetDateRequest(BaseModel):
    date: str  # DD.MM.YY


@app.post("/set-date")
async def set_date(req: SetDateRequest):
    ok = await _write("set_date", req.date)
    if not ok:
        raise HTTPException(status_code=502, detail="set_date command failed")
    return {"ok": True}


class SetTimeRequest(BaseModel):
    time: str  # HH:MM


@app.post("/set-time")
async def set_time(req: SetTimeRequest):
    ok = await _write("set_time", req.time)
    if not ok:
        raise HTTPException(status_code=502, detail="set_time command failed")
    return {"ok": True}

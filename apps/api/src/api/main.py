"""
miniClima EBC10 — FastAPI server with WebSocket push.

Run:
    uvicorn api.main:app --reload

Config via env vars:
    EBC10_PORT          (default: /dev/ttyACM0)
    EBC10_BAUD          (default: 9600)
    EBC10_POLL_INTERVAL (default: 5, seconds between device polls)
    CORS_ORIGINS        (default: *, comma-separated list of allowed origins)
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from pydantic import BaseModel

from ebc10 import Client

# --- Prometheus metrics ---
_m_humidity = Gauge("ebc10_humidity_percent", "Relative humidity reading (%RH)")
_m_temp = Gauge("ebc10_temperature_celsius", "Temperature (°C)", ["sensor"])
_m_sp = Gauge("ebc10_setpoint_percent", "Humidity setpoint (%RH)")
_m_ophours = Gauge("ebc10_operating_hours", "Operating hours")
_m_running = Gauge("ebc10_device_running", "1 if device is running, 0 if standby")
_m_poll_errors = Counter("ebc10_poll_errors_total", "Total number of poll errors")

log = logging.getLogger("api")

PORT = os.getenv("EBC10_PORT", "/dev/ttyACM0")
BAUD = int(os.getenv("EBC10_BAUD", "9600"))
POLL_INTERVAL = int(os.getenv("EBC10_POLL_INTERVAL", "5"))

# --- shared state (initialised in lifespan) ---
_lock: asyncio.Lock
_client: Client | None = None
_ws_clients: set[WebSocket] = set()
_latest: dict = {}


# --- blocking serial helpers (run via to_thread while holding _lock) ---

def _ensure_connected() -> Client:
    """Open serial connection if needed. Must be called under _lock."""
    global _client
    if _client is not None and _client._ser.is_open:
        return _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = Client(PORT, BAUD)
    log.info("connected to %s", PORT)
    return _client


def _close_client():
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None


def _read_status() -> dict:
    c = _ensure_connected()
    return {
        "sernum": c.read_sernum(),
        "vals": c.read_vals(),
        "ophours": c.read_ophours(),
    }


def _exec_write(method: str, *args) -> bool:
    c = _ensure_connected()
    return getattr(c, method)(*args)


# --- background poll + broadcast ---

async def _poll_loop():
    global _latest
    while True:
        try:
            async with _lock:
                data = await asyncio.to_thread(_read_status)
            _latest = data
            # update Prometheus metrics
            vals = data.get("vals", {})
            sernum = data.get("sernum", {})
            if vals.get("rh") is not None:
                _m_humidity.set(vals["rh"])
            if vals.get("t1") is not None:
                _m_temp.labels(sensor="t1").set(vals["t1"])
            if vals.get("t2") is not None:
                _m_temp.labels(sensor="t2").set(vals["t2"])
            if sernum.get("sp") is not None:
                _m_sp.set(sernum["sp"])
            if data.get("ophours") is not None:
                _m_ophours.set(data["ophours"])
            _m_running.set(1 if vals.get("state") == "running" else 0)
            msg = json.dumps(data)
            dead = []
            for ws in _ws_clients:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                _ws_clients.discard(ws)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("poll error: %s", e)
            _m_poll_errors.inc()
            _close_client()
            await asyncio.sleep(10)
            continue
        await asyncio.sleep(POLL_INTERVAL)


# --- app lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _lock
    _lock = asyncio.Lock()
    task = asyncio.create_task(_poll_loop())
    yield
    task.cancel()
    _close_client()


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
    _ws_clients.add(ws)
    if _latest:
        await ws.send_text(json.dumps(_latest))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


# --- Prometheus scrape endpoint ---

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --- read endpoints (return cached _latest when available) ---

@app.get("/status")
async def status():
    if _latest:
        return _latest
    async with _lock:
        return await asyncio.to_thread(_read_status)


@app.get("/vals")
async def vals():
    if _latest and "vals" in _latest:
        return _latest["vals"]
    async with _lock:
        return await asyncio.to_thread(lambda: _ensure_connected().read_vals())


@app.get("/sernum")
async def sernum():
    if _latest and "sernum" in _latest:
        return _latest["sernum"]
    async with _lock:
        return await asyncio.to_thread(lambda: _ensure_connected().read_sernum())


@app.get("/date")
async def date():
    async with _lock:
        return {"date": await asyncio.to_thread(lambda: _ensure_connected().read_date())}


@app.get("/time")
async def time_():
    async with _lock:
        return {"time": await asyncio.to_thread(lambda: _ensure_connected().read_time())}


@app.get("/ophours")
async def ophours():
    if _latest and "ophours" in _latest:
        return {"ophours": _latest["ophours"]}
    async with _lock:
        return {"ophours": await asyncio.to_thread(lambda: _ensure_connected().read_ophours())}


@app.get("/dump")
async def dump():
    async with _lock:
        return {"data": await asyncio.to_thread(lambda: _ensure_connected().dump())}


# --- write endpoints ---

async def _write(method: str, *args) -> bool:
    async with _lock:
        return await asyncio.to_thread(_exec_write, method, *args)


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

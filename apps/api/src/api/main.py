"""
miniClima EBC10 — FastAPI server.

Run:
    uvicorn api.main:app --reload

Config via env vars:
    EBC10_PORT  (default: /dev/ttyACM0)
    EBC10_BAUD  (default: 9600)
"""

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ebc10 import Client

PORT = os.getenv("EBC10_PORT", "/dev/ttyACM0")
BAUD = int(os.getenv("EBC10_BAUD", "9600"))

app = FastAPI(title="miniClima EBC10 API")


def _client() -> Client:
    return Client(PORT, BAUD)


# --- read endpoints ---

@app.get("/status")
def status():
    with _client() as c:
        return {"sernum": c.read_sernum(), "vals": c.read_vals()}


@app.get("/vals")
def vals():
    with _client() as c:
        return c.read_vals()


@app.get("/sernum")
def sernum():
    with _client() as c:
        return c.read_sernum()


@app.get("/date")
def date():
    with _client() as c:
        return {"date": c.read_date()}


@app.get("/time")
def time():
    with _client() as c:
        return {"time": c.read_time()}


@app.get("/ophours")
def ophours():
    with _client() as c:
        return {"ophours": c.read_ophours()}


@app.get("/dump")
def dump():
    with _client() as c:
        return {"data": c.dump()}


# --- write endpoints ---

@app.post("/start")
def start():
    with _client() as c:
        ok = c.start()
    if not ok:
        raise HTTPException(status_code=502, detail="start command failed")
    return {"ok": True}


@app.post("/stop")
def stop():
    with _client() as c:
        ok = c.stop()
    if not ok:
        raise HTTPException(status_code=502, detail="stop command failed")
    return {"ok": True}


class SetpointRequest(BaseModel):
    rh_percent: int


@app.post("/setpoint")
def setpoint(req: SetpointRequest):
    with _client() as c:
        ok = c.set_setpoint(req.rh_percent)
    if not ok:
        raise HTTPException(status_code=502, detail="set_setpoint command failed")
    return {"ok": True}


class SetLogTimeRequest(BaseModel):
    minutes: int


@app.post("/set-log-time")
def set_log_time(req: SetLogTimeRequest):
    with _client() as c:
        ok = c.set_log_time(req.minutes)
    if not ok:
        raise HTTPException(status_code=502, detail="set_log_time command failed")
    return {"ok": True}


class SetDateRequest(BaseModel):
    date: str  # DD.MM.YY


@app.post("/set-date")
def set_date(req: SetDateRequest):
    with _client() as c:
        ok = c.set_date(req.date)
    if not ok:
        raise HTTPException(status_code=502, detail="set_date command failed")
    return {"ok": True}


class SetTimeRequest(BaseModel):
    time: str  # HH:MM


@app.post("/set-time")
def set_time(req: SetTimeRequest):
    with _client() as c:
        ok = c.set_time(req.time)
    if not ok:
        raise HTTPException(status_code=502, detail="set_time command failed")
    return {"ok": True}

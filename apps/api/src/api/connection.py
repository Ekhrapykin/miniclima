"""
Serial connection state and blocking helpers.
Import this module as an alias to get live module-level bindings:

    import api.connection as conn
    async with conn._lock:
        data = await asyncio.to_thread(conn.read_status)
    conn._latest = data
"""

import asyncio
import logging
import os

from fastapi import WebSocket

from ebc10 import Client

log = logging.getLogger("api")

PORT = os.getenv("EBC10_PORT", "/dev/ttyACM0")
BAUD = int(os.getenv("EBC10_BAUD", "9600"))

# Initialised in lifespan (main.py) before the poll task starts.
_lock: asyncio.Lock

_client: Client | None = None
_ws_clients: set[WebSocket] = set()
_latest: dict = {}


def ensure_connected() -> Client:
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


def close_client():
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None


def read_status() -> dict:
    c = ensure_connected()
    return {
        "sernum":  c.read_sernum(),
        "vals":    c.read_vals(),
        "ophours": c.read_ophours(),
    }


def exec_write(method: str, *args) -> bool:
    c = ensure_connected()
    return getattr(c, method)(*args)

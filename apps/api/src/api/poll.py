"""
Background poll loop — reads device status, updates shared state,
broadcasts to WebSocket clients, and updates Prometheus gauges.
"""

import asyncio
import json
import logging
import os

import api.connection as conn
from api.prometheus import m_poll_errors, update_live_metrics

log = logging.getLogger("api")

POLL_INTERVAL = int(os.getenv("EBC10_POLL_INTERVAL", "5"))


async def poll_loop():
    while True:
        try:
            async with conn._lock:
                data = await asyncio.to_thread(conn.read_status)
            conn._latest = data
            update_live_metrics(data)
            msg = json.dumps(data)
            dead = []
            for ws in conn._ws_clients:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                conn._ws_clients.discard(ws)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("poll error: %s", e)
            m_poll_errors.inc()
            conn.close_client()
            await asyncio.sleep(10)
            continue
        await asyncio.sleep(POLL_INTERVAL)

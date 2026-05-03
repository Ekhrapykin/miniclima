"""
Background poll loop — reads device status, updates shared state,
broadcasts to WebSocket clients, and updates Prometheus gauges.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import api.connection as conn
from api.prometheus import m_poll_errors, set_device_offline, update_live_metrics
from api.store import set_last_poll, get_last_contact, set_last_contact

log = logging.getLogger("api")

POLL_INTERVAL = int(os.getenv("EBC10_POLL_INTERVAL", "5"))
OFFLINE_THRESHOLD = int(os.getenv("EBC10_OFFLINE_THRESHOLD", "3"))

_fail_count = 0


def _is_valid(data: dict) -> bool:
    vals = data.get("vals", {})
    return vals.get("state") in ("running", "standby")


async def poll_loop():
    global _fail_count

    while True:
        try:
            data = None
            async with conn._lock:
                if not conn._draining:
                    data = await asyncio.to_thread(conn.read_status)
            if data is None:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            if _is_valid(data):
                _fail_count = 0
                update_live_metrics(data)
                now = datetime.now(timezone.utc).isoformat()
                data["device_connected"] = True
                data["last_contact"] = now
                conn._latest = data
                set_last_contact(now)
                set_last_poll(data)
            else:
                _fail_count += 1
                if _fail_count >= OFFLINE_THRESHOLD:
                    set_device_offline()
                status = "connecting" if _fail_count < OFFLINE_THRESHOLD else False
                if conn._latest:
                    conn._latest["device_connected"] = status
                else:
                    data["device_connected"] = status
                    data["last_contact"] = get_last_contact()
                    conn._latest = data

            msg = json.dumps(conn._latest)
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
            _fail_count += 1
            conn.close_client()
            if conn._latest:
                conn._latest["device_connected"] = "connecting" if _fail_count < OFFLINE_THRESHOLD else False
                msg = json.dumps(conn._latest)
                dead = []
                for ws in conn._ws_clients:
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    conn._ws_clients.discard(ws)
            await asyncio.sleep(10)
            continue
        await asyncio.sleep(POLL_INTERVAL)

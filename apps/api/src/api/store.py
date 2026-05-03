"""
Simple JSON file store for persistent state across restarts.
Stores: last valid poll data, filter change date.
"""

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("api")

STATE_PATH = Path(os.getenv("EBC10_STATE_FILE", "/data/state.json"))

_state: dict = {}


def load():
    global _state
    if STATE_PATH.exists():
        try:
            _state = json.loads(STATE_PATH.read_text())
            log.info("loaded state from %s", STATE_PATH)
        except Exception as e:
            log.warning("failed to load state: %s", e)
            _state = {}
    else:
        _state = {}


def _save():
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(_state, default=str))
    except Exception as e:
        log.warning("failed to save state: %s", e)


def get_last_poll() -> dict | None:
    return _state.get("last_poll")


def set_last_poll(data: dict):
    _state["last_poll"] = data
    _save()


def get_last_contact() -> str | None:
    return _state.get("last_contact")


def set_last_contact(iso: str):
    _state["last_contact"] = iso
    _save()


def get_filter_date() -> str | None:
    return _state.get("filter_date")


def set_filter_date(date: str):
    _state["filter_date"] = date
    _save()

"""
Prometheus metrics, live-update helper, protobuf encoder, and remote write.
"""

import logging
import os
import struct
import urllib.request
from datetime import datetime, timedelta, timezone

import snappy
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

log = logging.getLogger("api")

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090") + "/api/v1/write"
CUTOFF_DAYS = os.getenv("CUTOFF_DAYS", "60")

# --- Gauges / Counters ---
m_humidity    = Gauge("ebc10_humidity_percent",    "Relative humidity reading (%RH)")
m_temp        = Gauge("ebc10_temperature_celsius", "Temperature (°C)", ["sensor"])
m_sp          = Gauge("ebc10_setpoint_percent",    "Humidity setpoint (%RH)")
m_ophours     = Gauge("ebc10_operating_hours",     "Operating hours")
m_running     = Gauge("ebc10_device_running",      "1 if device is running, 0 if standby")
m_poll_errors = Counter("ebc10_poll_errors_total", "Total number of poll errors")


def update_live_metrics(data: dict):
    """Update Prometheus gauges from a fresh poll result."""
    vals   = data.get("vals", {})
    sernum = data.get("sernum", {})
    if vals.get("rh") is not None:
        m_humidity.set(vals["rh"])
    if vals.get("t1") is not None:
        m_temp.labels(sensor="t1").set(vals["t1"])
    if vals.get("t2") is not None:
        m_temp.labels(sensor="t2").set(vals["t2"])
    if sernum.get("sp") is not None:
        m_sp.set(sernum["sp"])
    if data.get("ophours") is not None:
        m_ophours.set(data["ophours"])
    m_running.set(1 if vals.get("state") == "running" else 0)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --- Minimal protobuf encoder for Prometheus remote write ---
# WriteRequest → repeated TimeSeries → (repeated Label, repeated Sample)

def _varint(n: int) -> bytes:
    out = []
    while n > 0x7F:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def _len_field(field_num: int, payload: bytes) -> bytes:
    tag = _varint((field_num << 3) | 2)
    return tag + _varint(len(payload)) + payload


def _encode_label(name: str, value: str) -> bytes:
    return _len_field(1, name.encode()) + _len_field(2, value.encode())


def _encode_sample(value: float, ts_ms: int) -> bytes:
    # field 1: double (wire type 1 = 64-bit), field 2: int64 (wire type 0 = varint)
    f1 = _varint((1 << 3) | 1) + struct.pack("<d", value)
    f2 = _varint((2 << 3) | 0) + _varint(ts_ms)
    return f1 + f2


def _encode_timeseries(labels: list[tuple[str, str]], samples: list[tuple[float, int]]) -> bytes:
    out = b""
    for name, val in labels:
        out += _len_field(1, _encode_label(name, val))
    for v, ts in samples:
        out += _len_field(2, _encode_sample(v, ts))
    return out


def push_records_to_prometheus(records: list[dict]) -> int:
    """Build remote write payload from dump records and POST to Prometheus.
    Returns number of distinct time series pushed.
    """
    log.debug("Pushing %d records to Prometheus", len(records))
    series: dict[tuple, list[tuple[float, int]]] = {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=CUTOFF_DAYS)
    for r in records:
        if r["ts"] is None:
            continue
        if r["ts"] < cutoff:
            log.debug(f"skipping old record: {r}")
            continue

        ts_ms = int(r["ts"].timestamp() * 1000)
        rtype = r["type"]
        data = r.get("data") or {}

        if rtype == "measure":
            if data.get("rh") is not None:
                series.setdefault(("ebc10_humidity_percent", ()), []).append(
                    (float(data["rh"]), ts_ms))
            for sensor in ("t1", "t2", "t_out"):
                if data.get(sensor) is not None:
                    series.setdefault(("ebc10_temperature_celsius", (("sensor", sensor),)), []).append(
                        (float(data[sensor]), ts_ms))

        elif rtype == "settings":
            if data.get("sp") is not None:
                series.setdefault(("ebc10_setpoint_percent", ()), []).append(
                    (float(data["sp"]), ts_ms))
            if data.get("lo") is not None:
                series.setdefault(("ebc10_humidity_lo", ()), []).append(
                    (float(data["lo"]), ts_ms))
            if data.get("hi") is not None:
                series.setdefault(("ebc10_humidity_hi", ()), []).append(
                    (float(data["hi"]), ts_ms))

        elif rtype == "start":
            series.setdefault(("ebc10_device_running", ()), []).append((1.0, ts_ms))

        elif rtype == "stop":
            series.setdefault(("ebc10_device_running", ()), []).append((0.0, ts_ms))

    ts_list = []
    for (metric_name, extra_labels), samples in series.items():
        if not samples:
            continue
        # Sort by timestamp and deduplicate (Prometheus requires strict ascending order)
        seen: dict[int, float] = {}
        for value, ts_ms in samples:
            seen[ts_ms] = value  # last write wins for same timestamp
        ordered = sorted(seen.items())  # (ts_ms, value)
        labels = [("__name__", metric_name), ("job", "ebc10-history")] + list(extra_labels)
        ts_list.append(_encode_timeseries(labels, [(v, t) for t, v in ordered]))

    if not ts_list:
        return 0

    payload = b""
    for ts in ts_list:
        payload += _len_field(1, ts)

    compressed = snappy.compress(payload)
    req = urllib.request.Request(
        PROMETHEUS_URL,
        data=compressed,
        headers={
            "Content-Type":                       "application/x-protobuf",
            "Content-Encoding":                   "snappy",
            "X-Prometheus-Remote-Write-Version":  "0.1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 204):
                log.warning("remote write returned %s", resp.status)
    except Exception as e:
        log.warning(f"remote write failed: {e}")
        return 0

    return len(ts_list)

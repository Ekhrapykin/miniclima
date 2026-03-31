import logging
from datetime import datetime, timezone

log = logging.getLogger("ebc10")

# --- History dump parsing ---

def _bcd(b: int) -> int:
    return (b >> 4) * 10 + (b & 0xF)


def _first_control(payload) -> int | None:
    """Return index of first control byte (0xF0-0xFF) in payload, or None."""
    return next((idx for idx, p in enumerate(payload) if p >= 0xF0), None)


def _make_ts(payload: bytearray, offset: int = 0) -> datetime:
    """Decode a 5-byte BCD timestamp at payload[offset:offset+5] into a UTC datetime."""
    return datetime(
        2000 + _bcd(payload[offset]),
        _bcd(payload[offset + 1]),
        _bcd(payload[offset + 2]),
        _bcd(payload[offset + 3]),
        _bcd(payload[offset + 4]),
        tzinfo=timezone.utc,
    )


_EVENT_TYPES = {
    0xF0: "log",
    0xF1: "init",
    0xF4: "pump_stop",
    0xF5: "pump_start",
    0xF9: "alarm",
    0xFA: "start",
    0xFD: "stop",
    0xFE: "error",
}


def parse_dump_records(raw: bytearray) -> list[dict]:
    """Parse binary-decoded dump bytes into structured records using a state machine.

    Accepts the binary bytearray (after hex-decoding the ASCII hex dump stream).
    Returns a list of uniform dicts:
        {"ts": datetime | None, "type": str, "data": dict | None}

    Timestamp propagation: last_ts is updated on every event record and
    inherited by following settings and measurement records. Multiple
    measurements under the same event each get their own record with that ts.
    """
    log.debug("dump raw (first 20 bytes): %s", raw[:20].hex())
    start = next((idx for idx, b in enumerate(raw) if 0xF0 <= b <= 0xFF), None)
    if start is None:
        log.warning("no control byte found in dump, skipping")
        return []
    if start > 0:
        log.debug("skipped %d prefix bytes to align to first record", start)
        raw = raw[start:]

    records = []
    last_ts: datetime | None = None
    i = 0

    while i < len(raw):
        b = raw[i]

        if b == 0xFF:
            break  # Empty flash memory reached

        # --- Settings Snapshot: FB + 9 data bytes (plain hex, not BCD) ---
        if b == 0xFB:
            if i + 10 > len(raw):
                break
            payload = raw[i + 1:i + 10]
            if (s := _first_control(payload)) is not None:
                i += 1 + s
                continue
            to_raw = payload[4]
            records.append({
                "ts": last_ts,
                "type": "settings",
                "data": {
                    "sp":  payload[0],
                    "lo":  payload[1],
                    "hi":  payload[2],
                    "hy":  payload[3],
                    "to":  -(to_raw & 0x7F) if (to_raw & 0x80) else to_raw,
                    "alm": payload[5],
                    "lt":  payload[7],
                },
            })
            i += 10

        # --- Extended events: F9, F4, F5 — 7 bytes: TYPE + sub + 5 BCD ts ---
        elif b in (0xF9, 0xF4, 0xF5):
            if i + 7 > len(raw):
                break
            payload = raw[i + 1:i + 7]
            if (s := _first_control(payload)) is not None:
                i += 1 + s
                continue
            try:
                last_ts = _make_ts(payload, offset=1)
            except ValueError:
                i += 1
                continue
            records.append({"ts": last_ts, "type": _EVENT_TYPES[b], "data": None})
            i += 7

        # --- Standard events: F0, F1, FA, FD, FE — 6 bytes: TYPE + 5 BCD ts ---
        elif b >= 0xF0:
            if i + 6 > len(raw):
                break
            payload = raw[i + 1:i + 6]
            if (s := _first_control(payload)) is not None:
                i += 1 + s
                continue
            try:
                last_ts = _make_ts(payload, offset=0)
            except ValueError:
                i += 1
                continue
            records.append({"ts": last_ts, "type": _EVENT_TYPES.get(b, f"{b:02X}"), "data": None})
            i += 6

        # --- Periodic Measurement: 4 bytes (RH, T_out, T1, T2) ---
        else:
            if i + 4 > len(raw):
                break
            payload = raw[i:i + 4]
            if (s := _first_control(payload)) is not None:
                i += s
                continue
            records.append({
                "ts": last_ts,
                "type": "measure",
                "data": {
                    "rh":    payload[0],
                    "t_out": int.from_bytes([payload[1]], signed=True),
                    "t1":    int.from_bytes([payload[2]], signed=True),
                    "t2":    int.from_bytes([payload[3]], signed=True),
                },
            })
            i += 4

    return records


def encode_nibbles(value: str) -> bytes:
    """
    Encode a string of digits (and '.' / ':') for EBC write payload.
    Each decimal digit → its raw value (0x01 for '1', not ASCII 0x31).
    Separator chars '.' and ':' are sent as-is (0x2E, 0x3A).
    Terminated with CR (0x0D).

    Examples:
        "15"       → b'\\x01\\x05\\x0d'
        "26.03.26" → b'\\x02\\x06\\x2e\\x00\\x03\\x2e\\x02\\x06\\x0d'
        "14:54"    → b'\\x01\\x04\\x3a\\x05\\x04\\x0d'
    """
    out = bytearray()
    for ch in value:
        out.append(int(ch) if ch.isdigit() else ord(ch))
    out.append(0x0D)
    return bytes(out)

# 50 69 39 off 03D eng
# t 26 24 25/26
# up 4
# rh corr-05%
# hyst 04%
#
#
# ---------
# 31 mar 2026 17.04
# 17.12 bottle alarm
# 17.18 - stop()
# pumping
# 17.18 stop pumping
# ------------------------
# 31 mar 2026 18.02
# disconnect COM port 18.02
# start at 18.06
# stop at 18.08
# connect com port at 18.10
# start reading from port(docker up) - 18.12
# read dump - 18.14 - 18.16
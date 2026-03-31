import logging

log = logging.getLogger("ebc10")

# --- History dump parsing ---

def _bcd(b: int) -> int:
    return (b >> 4) * 10 + (b & 0xF)


def _first_control(payload) -> int | None:
    """Return index of first control byte (0xF0-0xFF) in payload, or None."""
    return next((idx for idx, p in enumerate(payload) if p >= 0xF0), None)


def parse_dump_records(hex_str: bytearray) -> list[dict]:
    """Parse raw ASCII hex from dump() into structured records using a state machine.

    The stream uses a variable-length format where 0xF0-0xFF act as absolute
    control markers. If a control marker is found mid-payload, it indicates
    a flash write interruption, and the parser will instantly resync.
    """
    log.debug("dump hex (first 100): %s", hex_str[:100])
    # clean = hex_str.strip().replace(" ", "").replace("\r", "").replace("\n", "")
    # log.debug("dump hex (first 100): %s", clean[:100])
    #
    # if len(clean) % 2:
    #     clean = clean[:-1]  # drop trailing nibble
    # try:
    #     raw = bytearray.fromhex(clean)
    # except ValueError as e:
    #     log.warning("dump hex decode error: %s", e)
    #     return []
    raw = hex_str
    # Scan for first control byte to align (skip "yes\r" echo residuals)
    start = next((idx for idx, b in enumerate(raw) if 0xF0 <= hex(b) <= 0xFF), None)
    if start is None:
        log.warning("no control byte found in dump, skipping")
        return []
    if start > 0:
        log.debug("skipped %d prefix bytes to align to first record", start)
        raw = raw[start:]

    records = []
    i = 0
    while i < len(raw):
        b = raw[i]
        log.debug(f"b: {b}, i: {i}")

        if b == 0xFF:
            break  # Empty flash memory reached

        # Settings Snapshot: FB + 9 data bytes (Plain Hex)
        if b == 0xFB:
            if i + 10 > len(raw):
                break
            payload = raw[i + 1:i + 10]

            # Resync check: Settings shouldn't naturally contain values >= 0xF0
            if (s := _first_control(payload)) is not None:
                i += 1 + s
                continue

            to_raw = payload[4]
            record = {
                "type": "FB",
                "sp": payload[0],
                "lo": payload[1],
                "hi": payload[2],
                "hy": payload[3],
                "to": -(to_raw & 0x7F) if (to_raw & 0x80) else to_raw,
                "unk": payload[5],
                "lt": payload[7],
            }
            records.append(record)
            i += 10

        # Extended Event: F9 + 00 + 5 BCD Timestamp bytes
        elif b == 0xF9:
            if i + 7 > len(raw):
                break
            payload = raw[i + 1:i + 7]

            if (s := _first_control(payload)) is not None:
                i += 1 + s
                continue

            ts = {
                "year": 2000 + _bcd(payload[1]),
                "month": _bcd(payload[2]),
                "day": _bcd(payload[3]),
                "hour": _bcd(payload[4]),
                "minute": _bcd(payload[5]),
            }
            records.append({"type": "F9", "ts": ts})
            i += 7

        # Standard Event: F0, F1, FA, FD, FE + 5 BCD Timestamp bytes
        elif b >= 0xF0:
            if i + 6 > len(raw):
                break
            payload = raw[i + 1:i + 6]

            if (s := _first_control(payload)) is not None:
                i += 1 + s
                continue

            ts = {
                "year": 2000 + _bcd(payload[0]),
                "month": _bcd(payload[1]),
                "day": _bcd(payload[2]),
                "hour": _bcd(payload[3]),
                "minute": _bcd(payload[4]),
            }
            records.append({"type": f"{b:02X}", "ts": ts})
            i += 6

        # Periodic Measurement: 4 bytes (RH, YY, T1, T2)
        else:
            if i + 4 > len(raw):
                break
            payload = raw[i:i + 4]

            if (s := _first_control(payload)) is not None:
                i += s
                continue

            record = {
                "type": "meas",
                "rh": payload[0],
                "unk_yy": payload[1],
                "t1": int.from_bytes([payload[2]], signed=True),
                "t2": int.from_bytes([payload[3]], signed=True),
            }
            records.append(record)
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
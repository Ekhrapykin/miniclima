#!/usr/bin/env python3
"""
protocol.py — Frame builder/parser for miniClima EBC10 proprietary RS232 protocol.

STATUS: ALL command IDs and frame structure are TODO placeholders.
Fill in after completing sniffing session (see docs/SNIFFING_PLAN.md).
"""

# ---------------------------------------------------------------------------
# TODO: Fill in all constants below after sniffing
# ---------------------------------------------------------------------------

FRAME_START = 0x02   # TODO: confirm
FRAME_END   = 0x03   # TODO: confirm

class Cmd:
    HANDSHAKE      = 0x00  # TODO
    SET_SETPOINT   = 0x00  # TODO
    SET_HYSTERESIS = 0x00  # TODO
    SET_ALARM_MIN  = 0x00  # TODO
    SET_ALARM_MAX  = 0x00  # TODO
    SET_LOG_RATE   = 0x00  # TODO
    START_UNIT     = 0x00  # TODO (firmware >= 111215 only)
    STOP_UNIT      = 0x00  # TODO
    SYNC_TIME      = 0x00  # TODO
    READ_HISTORY   = 0x00  # TODO


def calc_checksum(data: bytes) -> int:
    """TODO: replace with actual algorithm from sniff (XOR / sum / CRC)."""
    return sum(data) & 0xFF


def build_frame(cmd_id: int, payload: bytes = b"") -> bytes:
    """
    Build a binary command frame.
    Assumed: [STX][CMD][LEN][PAYLOAD...][CHK][ETX]
    TODO: confirm structure from hex dump.
    """
    body = bytes([cmd_id, len(payload)]) + payload
    chk  = calc_checksum(body)
    return bytes([FRAME_START]) + body + bytes([chk, FRAME_END])


def parse_frame(raw: bytes) -> dict | None:
    """
    Parse a binary response frame.
    TODO: confirm structure from hex dump.
    """
    if len(raw) < 4:
        return None
    if raw[0] != FRAME_START or raw[-1] != FRAME_END:
        return None
    cmd_id  = raw[1]
    length  = raw[2]
    payload = raw[3:3 + length]
    chk     = raw[3 + length] if (3 + length) < len(raw) else None
    exp_chk = calc_checksum(raw[1:3 + length])
    return {
        "cmd_id":       cmd_id,
        "payload":      payload,
        "checksum_ok":  chk == exp_chk,
    }

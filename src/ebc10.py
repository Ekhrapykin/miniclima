#!/usr/bin/env python3
"""
miniClima EBC10 — RS232 ASCII protocol client.
"""

import logging

import serial

log = logging.getLogger("ebc10")

_MAX_READ_LINES = 4  # max lines to scan before giving up on a response


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


class Ebc10Client:
    READ_TIMEOUT = 2.0

    def __init__(self, port: str, baud: int = 9600):
        self._ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=self.READ_TIMEOUT,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self._ser.is_open:
            self._ser.close()

    # --- low-level I/O -------------------------------------------------------

    def _flush_input(self):
        self._ser.reset_input_buffer()

    def _readline(self) -> str:
        return self._ser.readline().decode("ascii", errors="replace").strip()

    def _send(self, data: bytes):
        self._ser.write(data)
        self._ser.flush()

    def _cmd(self, cmd: str) -> str:
        """Send a read command; return first non-echo, non-empty response line."""
        self._flush_input()
        self._send((cmd + "\r").encode("ascii"))
        for _ in range(_MAX_READ_LINES):
            line = self._readline()
            if not line or line == cmd:
                continue
            return line
        return ""

    def _write_cmd(self, cmd: str, value: str = "", raw_payload: bytes | None = None) -> bool:
        """
        Send a write command: cmd\\r → wait for '?' prompt → send payload.
        Pass `value` for nibble-encoded writes, or `raw_payload` for binary payloads.
        Returns True on '!' (success).
        """
        self._flush_input()
        self._send((cmd + "\r").encode("ascii"))
        for _ in range(_MAX_READ_LINES):
            if self._readline() == "?":
                break
        else:
            log.warning(f"write_cmd({cmd!r}): no '?' prompt received")
            return False
        self._send(raw_payload if raw_payload is not None else encode_nibbles(value))
        resp = self._readline()
        if resp != "!":
            log.warning(f"write_cmd({cmd!r}): unexpected response {resp!r}")
            return False
        return True

    def _read_int(self, cmd: str) -> int | None:
        try:
            return int(self._cmd(cmd))
        except ValueError:
            return None

    def _echo_cmd(self, cmd: str) -> bool:
        """Send a command that responds with an echo (start/stop pattern)."""
        self._flush_input()
        self._send((cmd + "\r").encode("ascii"))
        return cmd in self._readline().lower()

    # --- read commands -------------------------------------------------------

    def read_sernum(self) -> dict:
        """
        Returns dict: serial, model, firmware, sp, lo, hi, hy, lt, to, xx
        Raw format: #004537 M 170908.04 Set:55 40 70 02 15 -05 04
        """
        raw = self._cmd("sernum")
        result = {"raw": raw}
        try:
            parts = raw.split()
            result["serial"]   = parts[0]
            result["model"]    = parts[1]
            result["firmware"] = parts[2]
            if "Set:" in raw:
                sp_parts = raw.split("Set:")[1].split()
                if len(sp_parts) >= 6:
                    result["sp"] = int(sp_parts[0])
                    result["lo"] = int(sp_parts[1])
                    result["hi"] = int(sp_parts[2])
                    result["hy"] = int(sp_parts[3])
                    result["lt"] = int(sp_parts[4])
                    result["to"] = int(sp_parts[5])
                if len(sp_parts) >= 7:
                    result["xx"] = sp_parts[6]
        except (IndexError, ValueError) as e:
            log.debug(f"sernum parse error: {e}  raw={raw!r}")
        return result

    def read_vals(self) -> dict:
        """
        Returns dict: state, rh, unknown, t1, t2, flag.
        Both Running and Stand by states include sensor readings.
        Raw format: "Running  67  27  +06  +36  00  p"
                 or "Stand by 70  26  +24  +24  00"
        """
        raw = self._cmd("vals")
        result = {"raw": raw, "state": "unknown"}
        try:
            parts = raw.split()
            if raw.startswith("Stand"):
                result["state"] = "standby"
                offset = 2  # "Stand by" occupies two tokens
            elif raw.startswith("Running"):
                result["state"] = "running"
                offset = 1
            else:
                offset = None
            if offset is not None and len(parts) > offset + 3:
                result["rh"]      = int(parts[offset])
                result["unknown"] = int(parts[offset + 1])
                result["t1"]      = int(parts[offset + 2].lstrip("+"))
                result["t2"]      = int(parts[offset + 3].lstrip("+"))
                result["flag"]    = parts[offset + 5] if len(parts) > offset + 5 else ""
        except (IndexError, ValueError) as e:
            log.debug(f"vals parse error: {e}  raw={raw!r}")
        return result

    def read_date(self) -> str:
        return self._cmd("date")

    def read_time(self) -> str:
        return self._cmd("time")

    def read_setlog_time(self) -> int | None:
        return self._read_int("setLogTime")

    def read_ophours(self) -> int | None:
        return self._read_int("ophours")

    def keepalive(self):
        self._send(b"\r")

    # --- write commands ------------------------------------------------------

    def set_log_time(self, minutes: int) -> bool:
        if not 1 <= minutes <= 99:
            raise ValueError(f"minutes must be 1–99, got {minutes}")
        return self._write_cmd("setLogTime", str(minutes).zfill(2))

    def set_date(self, date_str: str) -> bool:
        return self._write_cmd("date", date_str)

    def set_time(self, time_str: str) -> bool:
        return self._write_cmd("time", time_str)

    def set_setpoint(self, rh_percent: int) -> bool:
        """
        Set humidity setpoint via #setPoint command (confirmed write, no 's').
        Payload after '?' prompt: \\x00\\x00 + nibble-encoded tens + units + CR
        E.g. SP=57 → b'\\x00\\x00\\x05\\x07\\x0d'
        """
        if not 0 <= rh_percent <= 99:
            raise ValueError(f"setpoint must be 0–99%, got {rh_percent}")
        tens  = rh_percent // 10
        units = rh_percent % 10
        return self._write_cmd("#setPoint", raw_payload=bytes([0x00, 0x00, tens, units, 0x0D]))

    def start(self) -> bool:
        return self._echo_cmd("start")

    def stop(self) -> bool:
        return self._echo_cmd("stop")

    def dump(self) -> str:
        """
        Retrieve full history log.
        Returns raw ASCII hex string (each byte = 2 hex chars, no spaces).
        """
        self._flush_input()
        self._send(b"dump\r")
        for _ in range(_MAX_READ_LINES):
            if "really" in self._readline().lower():
                break
        else:
            log.warning("dump: no 'really?' prompt received")
            return ""
        self._send(b"yes\r")
        data = bytearray()
        while True:
            chunk = self._ser.read(256)
            if not chunk:
                break
            data += chunk
            if b"!" in chunk:
                break
        return data.decode("ascii", errors="replace").rstrip("!\r\n")

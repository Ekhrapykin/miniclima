#!/usr/bin/env python3
"""
miniClima EBC10 — RS232 ASCII client

Usage:
    python src/client.py --port /dev/ttyUSB0 status
    python src/client.py --port /dev/ttyUSB0 vals
    python src/client.py --port /dev/ttyUSB0 set-sp 55
    python src/client.py --port /dev/ttyUSB0 start
    python src/client.py --port /dev/ttyUSB0 stop
    python src/client.py --port /dev/ttyUSB0 set-log-time 15
    python src/client.py --port /dev/ttyUSB0 dump
"""

import argparse
import logging

import serial

log = logging.getLogger("ebc10")


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

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
        if ch.isdigit():
            out.append(int(ch))
        else:
            out.append(ord(ch))
    out.append(0x0D)
    return bytes(out)


# ---------------------------------------------------------------------------
# EBC10 client
# ---------------------------------------------------------------------------

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
        for _ in range(4):
            line = self._readline()
            if not line:
                continue
            if line.rstrip("\r") == cmd:
                continue  # skip echo
            return line
        return ""

    def _write_cmd(self, cmd: str, value: str) -> bool:
        """
        Send a write command: cmd\r → wait for '?' prompt → send nibble-encoded value.
        Returns True on '!' (success).
        """
        self._flush_input()
        self._send((cmd + "\r").encode("ascii"))
        for _ in range(4):
            line = self._readline()
            if line == "?":
                break
        else:
            log.warning(f"write_cmd({cmd!r}): no '?' prompt received")
            return False
        self._send(encode_nibbles(value))
        resp = self._readline()
        if resp != "!":
            log.warning(f"write_cmd({cmd!r}, {value!r}): unexpected response {resp!r}")
            return False
        return True

    # --- read commands -------------------------------------------------------

    def read_sernum(self) -> dict:
        """
        Returns dict: serial, model, firmware, sp, lo, hi, hy, lt, to, xx
        Raw format: #004537 M 170908.04 Set:55 40 70 02 15 -05 04
        """
        raw = self._cmd("sernum")
        result: dict = {"raw": raw}
        try:
            parts = raw.split()
            result["serial"]   = parts[0]   # #004537
            result["model"]    = parts[1]   # M
            result["firmware"] = parts[2]   # 170908.04
            if "Set:" in raw:
                sp_str = raw.split("Set:")[1]
                sp_parts = sp_str.split()
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
        Returns dict: state, rh, t1, t2, flag (or just state='standby').
        Raw format: "Running  67  27  +06  +36  00  p"
                 or "Stand by ..."
        """
        raw = self._cmd("vals")
        result: dict = {"raw": raw, "state": "unknown"}
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
        raw = self._cmd("setLogTime")
        try:
            return int(raw)
        except ValueError:
            return None

    def read_ophours(self) -> int | None:
        raw = self._cmd("ophours")
        try:
            return int(raw)
        except ValueError:
            return None

    def keepalive(self):
        self._send(b"\r")

    # --- write commands ------------------------------------------------------

    def set_log_time(self, minutes: int) -> bool:
        """Set log interval (1–99 min)."""
        if not 1 <= minutes <= 99:
            raise ValueError(f"minutes must be 1–99, got {minutes}")
        return self._write_cmd("setLogTime", str(minutes).zfill(2))

    def set_date(self, date_str: str) -> bool:
        """Set date. date_str format: 'DD.MM.YY' e.g. '26.03.26'"""
        return self._write_cmd("date", date_str)

    def set_time(self, time_str: str) -> bool:
        """Set time. time_str format: 'HH:MM' e.g. '14:54'"""
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
        payload = bytes([0x00, 0x00, tens, units, 0x0D])
        self._flush_input()
        self._send(b"#setPoint\r")
        for _ in range(4):
            line = self._readline()
            if line == "?":
                break
        else:
            log.warning("set_setpoint: no '?' prompt received")
            return False
        self._send(payload)
        resp = self._readline()
        if resp != "!":
            log.warning(f"set_setpoint({rh_percent}): unexpected response {resp!r}")
            return False
        return True

    def start(self) -> bool:
        self._flush_input()
        self._send(b"start\r")
        resp = self._readline()
        return "start" in resp.lower()

    def stop(self) -> bool:
        self._flush_input()
        self._send(b"stop\r")
        resp = self._readline()
        return "stop" in resp.lower()

    def dump(self) -> str:
        """
        Retrieve full history log.
        Returns raw ASCII hex string (each byte = 2 hex chars, no spaces).
        """
        self._flush_input()
        self._send(b"dump\r")
        for _ in range(4):
            line = self._readline()
            if "really" in line.lower():
                break
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="miniClima EBC10 RS232 client")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baud", default=9600, type=int)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status",       help="Read sernum + vals")
    sub.add_parser("vals",         help="Read current sensor values")
    sub.add_parser("sernum",       help="Read serial/firmware/settings")
    sub.add_parser("date",         help="Read device date")
    sub.add_parser("time",         help="Read device time")
    sub.add_parser("ophours",      help="Read operating hours")
    sub.add_parser("dump",         help="Dump full history log (ASCII hex)")

    p = sub.add_parser("set-sp",       help="Set humidity setpoint (%%)")
    p.add_argument("value", type=int)

    p = sub.add_parser("set-log-time", help="Set log interval (min)")
    p.add_argument("value", type=int)

    p = sub.add_parser("set-date",     help="Set date (DD.MM.YY)")
    p.add_argument("value")

    p = sub.add_parser("set-time",     help="Set time (HH:MM)")
    p.add_argument("value")

    sub.add_parser("start",        help="Start the unit")
    sub.add_parser("stop",         help="Stop the unit")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    with Ebc10Client(args.port, args.baud) as c:
        if args.cmd == "status":
            s = c.read_sernum()
            v = c.read_vals()
            print(f"Serial:   {s.get('serial', '?')}  FW: {s.get('firmware', '?')}")
            print(f"Settings: SP={s.get('sp', '?')}%  LO={s.get('lo', '?')}%  "
                  f"HI={s.get('hi', '?')}%  HY={s.get('hy', '?')}  "
                  f"LT={s.get('lt', '?')}min  TO={s.get('to', '?')}")
            print(f"State:    {v.get('state', '?')}")
            if "rh" in v:
                print(f"Sensor:   RH={v.get('rh', '?')}%  "
                      f"T1={v.get('t1', '?')}°C  T2={v.get('t2', '?')}°C  "
                      f"flag={v.get('flag') or 'none'}")
        elif args.cmd == "vals":
            print(c.read_vals())
        elif args.cmd == "sernum":
            print(c.read_sernum())
        elif args.cmd == "date":
            print(c.read_date())
        elif args.cmd == "time":
            print(c.read_time())
        elif args.cmd == "ophours":
            print(f"{c.read_ophours()} hours")
        elif args.cmd == "dump":
            print(c.dump())
        elif args.cmd == "set-sp":
            print("OK" if c.set_setpoint(args.value) else "FAIL")
        elif args.cmd == "set-log-time":
            print("OK" if c.set_log_time(args.value) else "FAIL")
        elif args.cmd == "set-date":
            print("OK" if c.set_date(args.value) else "FAIL")
        elif args.cmd == "set-time":
            print("OK" if c.set_time(args.value) else "FAIL")
        elif args.cmd == "start":
            print("OK" if c.start() else "FAIL")
        elif args.cmd == "stop":
            print("OK" if c.stop() else "FAIL")


if __name__ == "__main__":
    main()

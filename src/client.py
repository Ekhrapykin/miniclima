#!/usr/bin/env python3
"""
miniClima EBC10 — RS232 Python Client (DRAFT)

STATUS: Placeholder implementation.
Protocol fields marked TODO must be filled in after sniffing session.
See docs/SNIFFING_PLAN.md and captures/ directory.

Usage:
    python src/client.py --port /dev/ttyUSB0 --baud 9600
"""

import serial
import threading
import argparse
import logging
import csv
from datetime import datetime
from dataclasses import dataclass

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ebc10")

# ---------------------------------------------------------------------------
# Serial config
# ---------------------------------------------------------------------------

@dataclass
class SerialConfig:
    port: str = "/dev/ttyUSB0"
    baud: int = 9600          # TODO: confirm from sniffing
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1
    timeout: float = 1.0


# ---------------------------------------------------------------------------
# Protocol constants  (ALL TODO — fill in after sniffing)
# ---------------------------------------------------------------------------

FRAME_START  = 0x02   # TODO: confirm STX byte
FRAME_END    = 0x03   # TODO: confirm ETX byte

class Cmd:
    HANDSHAKE      = 0x00  # TODO
    SET_SETPOINT   = 0x00  # TODO
    SET_HYSTERESIS = 0x00  # TODO
    SET_ALARM_MIN  = 0x00  # TODO
    SET_ALARM_MAX  = 0x00  # TODO
    SET_LOG_RATE   = 0x00  # TODO
    START_UNIT     = 0x00  # TODO  (firmware >= 111215 only)
    STOP_UNIT      = 0x00  # TODO
    SYNC_TIME      = 0x00  # TODO
    READ_HISTORY   = 0x00  # TODO


# ---------------------------------------------------------------------------
# Frame builder / parser
# ---------------------------------------------------------------------------

def calc_checksum(data: bytes) -> int:
    """TODO: replace with actual checksum algorithm (XOR / sum / CRC)."""
    return sum(data) & 0xFF  # placeholder: sum mod 256

def build_frame(cmd_id: int, payload: bytes = b"") -> bytes:
    """
    Builds a command frame.
    Assumed structure: [STX][CMD][LEN][PAYLOAD...][CHK][ETX]
    TODO: verify structure and checksum from sniffed captures.
    """
    body = bytes([cmd_id, len(payload)]) + payload
    chk  = calc_checksum(body)
    return bytes([FRAME_START]) + body + bytes([chk, FRAME_END])

def parse_response(raw: bytes) -> dict | None:
    """
    Parse a binary response frame from the EBC.
    TODO: fill in real structure after sniffing.
    """
    if len(raw) < 4:
        return None
    if raw[0] != FRAME_START or raw[-1] != FRAME_END:
        log.warning(f"Unexpected frame boundaries: {raw.hex()}")
        return None
    cmd_id  = raw[1]
    length  = raw[2]
    payload = raw[3:3+length]
    chk     = raw[3+length]
    expected_chk = calc_checksum(raw[1:3+length])
    if chk != expected_chk:
        log.warning(f"Checksum mismatch: got {chk:#04x}, expected {expected_chk:#04x}")
    return {"cmd_id": cmd_id, "payload": payload, "checksum_ok": chk == expected_chk}


# ---------------------------------------------------------------------------
# Pushed CSV parser (no protocol knowledge needed — device sends automatically)
# ---------------------------------------------------------------------------

def parse_pushed_line(line: str) -> dict | None:
    """
    Parse a semicolon-delimited measurement line pushed by the EBC:
      date;time;T/°C;RH/%;set/%;alarmMin/%;alarmMax/%;timeDiff_seconds
    """
    parts = line.strip().split(";")
    if len(parts) < 7:
        return None
    try:
        return {
            "date":          parts[0],
            "time":          parts[1],
            "temperature_c": float(parts[2]),
            "rh_percent":    float(parts[3]),
            "setpoint_pct":  float(parts[4]),
            "alarm_min_pct": float(parts[5]),
            "alarm_max_pct": float(parts[6]),
            "time_diff_s":   int(parts[7]) if len(parts) > 7 else None,
            "received_at":   datetime.now().isoformat(),
        }
    except (ValueError, IndexError) as e:
        log.debug(f"Could not parse line: {line!r} — {e}")
        return None


# ---------------------------------------------------------------------------
# EBC10 Client
# ---------------------------------------------------------------------------

class Ebc10Client:
    def __init__(self, cfg: SerialConfig):
        self.cfg = cfg
        self.ser = serial.Serial(
            port=cfg.port,
            baudrate=cfg.baud,
            bytesize=cfg.bytesize,
            parity=cfg.parity,
            stopbits=cfg.stopbits,
            timeout=cfg.timeout,
        )
        self._running = False
        self._listener_thread: threading.Thread | None = None
        self._csv_writer = None
        self._csv_file = None

    # --- connection --------------------------------------------------------

    def connect(self):
        if not self.ser.is_open:
            self.ser.open()
        log.info(f"Connected to {self.cfg.port} @ {self.cfg.baud} baud")
        self._start_listener()
        self._handshake()

    def disconnect(self):
        self._running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=2)
        if self.ser.is_open:
            self.ser.close()
        if self._csv_file:
            self._csv_file.close()
        log.info("Disconnected")

    # --- background listener -----------------------------------------------

    def _start_listener(self):
        self._running = True
        self._listener_thread = threading.Thread(
            target=self._listen_loop, daemon=True
        )
        self._listener_thread.start()

    def _listen_loop(self):
        """Reads incoming data continuously; routes CSV lines vs binary frames."""
        buffer = ""
        while self._running:
            try:
                raw = self.ser.read(self.ser.in_waiting or 1)
                if not raw:
                    continue
                text = raw.decode("ascii", errors="replace")
                buffer += text
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if ";" in line:
                        data = parse_pushed_line(line)
                        if data:
                            log.info(f"PUSHED: {data}")
                            self._write_csv(data)
                    else:
                        log.debug(f"RAW: {line!r}")
            except Exception as e:
                log.error(f"Listener error: {e}")
                break

    # --- CSV logging -------------------------------------------------------

    def start_csv_log(self, path: str = "ebc10_log.csv"):
        self._csv_file = open(path, "a", newline="")
        fieldnames = [
            "received_at", "date", "time", "temperature_c",
            "rh_percent", "setpoint_pct", "alarm_min_pct",
            "alarm_max_pct", "time_diff_s",
        ]
        self._csv_writer = csv.DictWriter(self._csv_file, fieldnames=fieldnames)
        if self._csv_file.tell() == 0:
            self._csv_writer.writeheader()

    def _write_csv(self, data: dict):
        if self._csv_writer:
            self._csv_writer.writerow(data)
            self._csv_file.flush()

    # --- commands ----------------------------------------------------------

    def _send(self, frame: bytes) -> bytes:
        log.debug(f"TX: {frame.hex()}")
        self.ser.write(frame)
        self.ser.flush()
        resp = self.ser.read(64)  # TODO: adjust expected response length
        log.debug(f"RX: {resp.hex()}")
        return resp

    def _handshake(self):
        """Initial connection handshake. TODO: fill in real frame."""
        frame = build_frame(Cmd.HANDSHAKE)
        resp  = self._send(frame)
        parsed = parse_response(resp)
        log.info(f"Handshake response: {parsed}")

    def set_setpoint(self, rh_percent: int):
        """Set target relative humidity (15–85%). TODO: confirm encoding."""
        if not 15 <= rh_percent <= 85:
            raise ValueError(f"Setpoint must be 15–85%, got {rh_percent}")
        frame = build_frame(Cmd.SET_SETPOINT, bytes([rh_percent]))
        resp  = self._send(frame)
        log.info(f"set_setpoint({rh_percent}%) → {parse_response(resp)}")

    def set_alarm_min(self, rh_percent: int):
        """Set low alarm threshold. TODO: confirm encoding."""
        frame = build_frame(Cmd.SET_ALARM_MIN, bytes([rh_percent]))
        resp  = self._send(frame)
        log.info(f"set_alarm_min({rh_percent}%) → {parse_response(resp)}")

    def set_alarm_max(self, rh_percent: int):
        """Set high alarm threshold. TODO: confirm encoding."""
        frame = build_frame(Cmd.SET_ALARM_MAX, bytes([rh_percent]))
        resp  = self._send(frame)
        log.info(f"set_alarm_max({rh_percent}%) → {parse_response(resp)}")

    def set_hysteresis(self, value: int):
        """Set hysteresis (1–4). TODO: confirm encoding."""
        if not 1 <= value <= 4:
            raise ValueError(f"Hysteresis must be 1–4, got {value}")
        frame = build_frame(Cmd.SET_HYSTERESIS, bytes([value]))
        resp  = self._send(frame)
        log.info(f"set_hysteresis({value}) → {parse_response(resp)}")

    def set_log_rate(self, minutes: int):
        """Set datalogger interval in minutes (1–99). TODO: confirm encoding."""
        if not 1 <= minutes <= 99:
            raise ValueError(f"Log rate must be 1–99 min, got {minutes}")
        frame = build_frame(Cmd.SET_LOG_RATE, bytes([minutes]))
        resp  = self._send(frame)
        log.info(f"set_log_rate({minutes} min) → {parse_response(resp)}")

    def start_unit(self):
        """Start the EBC unit. Requires firmware >= 111215. TODO: confirm."""
        frame = build_frame(Cmd.START_UNIT)
        resp  = self._send(frame)
        log.info(f"start_unit() → {parse_response(resp)}")

    def stop_unit(self):
        """Stop the EBC unit. Requires firmware >= 111215. TODO: confirm."""
        frame = build_frame(Cmd.STOP_UNIT)
        resp  = self._send(frame)
        log.info(f"stop_unit() → {parse_response(resp)}")

    def sync_time(self):
        """Sync device clock to current PC time. TODO: confirm date encoding."""
        now = datetime.now()
        # Placeholder: send year/month/day/hour/min/sec as individual bytes
        payload = bytes([
            now.year % 100,  # 2-digit year — TODO: confirm format
            now.month,
            now.day,
            now.hour,
            now.minute,
            now.second,
        ])
        frame = build_frame(Cmd.SYNC_TIME, payload)
        resp  = self._send(frame)
        log.info(f"sync_time({now}) → {parse_response(resp)}")

    def read_history(self):
        """Request full history log from device (up to 15,000 entries). TODO."""
        frame = build_frame(Cmd.READ_HISTORY)
        # History response is likely large — read until ETX or timeout
        self.ser.write(frame)
        self.ser.flush()
        result = bytearray()
        while True:
            chunk = self.ser.read(256)
            if not chunk:
                break
            result += chunk
            if FRAME_END in chunk:
                break
        log.info(f"read_history(): received {len(result)} bytes")
        return bytes(result)  # TODO: parse into list of measurement dicts


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="miniClima EBC10 RS232 client")
    parser.add_argument("--port",   default="/dev/ttyUSB0")
    parser.add_argument("--baud",   default=9600, type=int)
    parser.add_argument("--log",    default="ebc10_log.csv")
    args = parser.parse_args()

    cfg    = SerialConfig(port=args.port, baud=args.baud)
    client = Ebc10Client(cfg)

    try:
        client.connect()
        client.start_csv_log(args.log)
        print("Listening for pushed data. Press Ctrl+C to stop.")
        while True:
            pass
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()

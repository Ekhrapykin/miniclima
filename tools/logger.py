#!/usr/bin/env python3
"""
logger.py — Passive listener for miniClima EBC10 pushed CSV data.

No protocol knowledge required — the device pushes measurements automatically.
Run this on Raspberry Pi to start logging immediately.

Usage:
    python src/logger.py --port /dev/ttyUSB0 --baud 9600 --output ebc10_log.csv
"""

import serial
import csv
import argparse
from datetime import datetime

def parse_line(line: str) -> dict | None:
    parts = line.strip().split(";")
    if len(parts) < 7:
        return None
    try:
        return {
            "received_at":   datetime.now().isoformat(),
            "date":          parts[0],
            "time":          parts[1],
            "temperature_c": float(parts[2]),
            "rh_percent":    float(parts[3]),
            "setpoint_pct":  float(parts[4]),
            "alarm_min_pct": float(parts[5]),
            "alarm_max_pct": float(parts[6]),
            "time_diff_s":   int(parts[7]) if len(parts) > 7 else None,
        }
    except (ValueError, IndexError):
        return None

def main():
    parser = argparse.ArgumentParser(description="miniClima EBC10 passive logger")
    parser.add_argument("--port",   default="/dev/ttyUSB0")
    parser.add_argument("--baud",   default=9600, type=int)
    parser.add_argument("--output", default="ebc10_log.csv")
    args = parser.parse_args()

    fieldnames = [
        "received_at", "date", "time", "temperature_c",
        "rh_percent", "setpoint_pct", "alarm_min_pct",
        "alarm_max_pct", "time_diff_s",
    ]

    print(f"Listening on {args.port} @ {args.baud} baud → {args.output}")
    print("Press Ctrl+C to stop.\n")

    with serial.Serial(args.port, args.baud, timeout=60) as ser, \
         open(args.output, "a", newline="") as f:

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if f.tell() == 0:
            writer.writeheader()

        while True:
            try:
                raw  = ser.readline().decode("ascii", errors="replace")
                data = parse_line(raw)
                if data:
                    writer.writerow(data)
                    f.flush()
                    print(f"{data['received_at']}  RH={data['rh_percent']}%  "
                          f"T={data['temperature_c']}°C  set={data['setpoint_pct']}%")
            except KeyboardInterrupt:
                print("\nStopping logger.")
                break

if __name__ == "__main__":
    main()

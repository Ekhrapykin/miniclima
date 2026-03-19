#!/usr/bin/env python3
"""
relay.py — COM port relay for sniffing miniClima EBC10 RS232 protocol.

Run this on Windows BEFORE opening miniClima Tool.
Then point miniClima Tool to TOOL_PORT instead of the real device port.

Requires: pip install pyserial
"""

import serial
import threading
import datetime

TOOL_PORT   = "COM4"   # virtual port — miniClima Tool connects here
DEVICE_PORT = "COM3"    # real EBC10 device
BAUD        = 9600      # change to 19200 or 38400 if CSV looks garbled

log_file = open("serial_capture.txt", "w", buffering=1)

def log(direction: str, data: bytes):
    ts        = datetime.datetime.now().strftime("%H:%M:%S.%f")
    hex_str   = " ".join(f"{b:02X}" for b in data)
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
    line = f"{ts} [{direction}] HEX: {hex_str}  ASCII: {ascii_str}"
    print(line)
    log_file.write(line + "\n")

def relay(src: serial.Serial, dst: serial.Serial, direction: str):
    while True:
        try:
            data = src.read(src.in_waiting or 1)
            if data:
                log(direction, data)
                dst.write(data)
        except Exception as e:
            print(f"Relay error ({direction}): {e}")
            break

tool_side   = serial.Serial(TOOL_PORT,   BAUD, timeout=0.05)
device_side = serial.Serial(DEVICE_PORT, BAUD, timeout=0.05)

print(f"Relay running: {TOOL_PORT} <-> {DEVICE_PORT}")
print(f"Connect miniClima Tool to {TOOL_PORT}")
print("Press Ctrl+C to stop and save capture.\n")

t1 = threading.Thread(target=relay, args=(tool_side,   device_side, "TOOL -> EBC"), daemon=True)
t2 = threading.Thread(target=relay, args=(device_side, tool_side,   "EBC -> TOOL"), daemon=True)
t1.start()
t2.start()

try:
    while True:
        pass
except KeyboardInterrupt:
    print("\nStopping relay. Capture saved to serial_capture.txt")
    log_file.close()

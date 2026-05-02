#!/usr/bin/env python3
"""Restore settings to reasonable values."""
import serial
import sys
import time

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
ser = serial.Serial(PORT, 9600, timeout=2)

def readline():
    return ser.readline().decode("ascii", errors="replace").strip()

def send(data):
    ser.write(data)
    ser.flush()

def read_sernum():
    ser.reset_input_buffer()
    send(b"sernum\r")
    for _ in range(6):
        line = readline()
        if "Set:" in line:
            return line
    return "?"

def setpoint(field, tens, units):
    payload = b"#setPoint" + bytes([0x00, field, tens, units, 0x0D])
    ser.reset_input_buffer()
    send(payload)
    for _ in range(4):
        if "!" in readline():
            return True
    return False

send(b"\r")
time.sleep(0.3)
print(f"BEFORE: {read_sernum()}")

# Restore: SP=55 LO=40 HI=70 HY=04
setpoint(0, 5, 5)  # SP=55
setpoint(1, 7, 0)  # HI=70
setpoint(2, 4, 0)  # LO=40
setpoint(3, 0, 4)  # HY=04

print(f"AFTER:  {read_sernum()}")
ser.close()

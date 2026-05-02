#!/usr/bin/env python3
"""Brute-force # command probing for RH correction write on EBC10."""
import serial
import sys
import time

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
ser = serial.Serial(PORT, 9600, timeout=0.5)

def readline():
    return ser.readline().decode("ascii", errors="replace").strip()

def send(data):
    ser.write(data)
    ser.flush()

def drain():
    time.sleep(0.15)
    while ser.in_waiting:
        ser.read(ser.in_waiting)
        time.sleep(0.05)

def read_sernum():
    ser.reset_input_buffer()
    send(b"sernum\r")
    for _ in range(6):
        line = readline()
        if "Set:" in line:
            return line
    return "?"

def test_hash_cmd(name):
    """Send #name as blob (no CR between # and name). Check for ! response."""
    cmd = f"#{name}"
    payload = cmd.encode("ascii") + b"\r"
    ser.reset_input_buffer()
    send(payload)
    responses = []
    for _ in range(4):
        line = readline()
        if not line:
            break
        responses.append(line)
        if "!" in line:
            return True, responses
        if line == "?":
            return False, responses
    return False, responses

def test_hash_blob(name, extra_bytes):
    """Send #name + raw bytes + CR as one blob (like #setPoint protocol)."""
    payload = f"#{name}".encode("ascii") + extra_bytes + b"\x0D"
    ser.reset_input_buffer()
    send(payload)
    responses = []
    for _ in range(6):
        line = readline()
        if not line:
            break
        responses.append(line)
        if "!" in line:
            return True, responses
        if line == "?":
            return False, responses
    return False, responses

send(b"\r")
time.sleep(0.3)
drain()

print(f"BEFORE: {read_sernum()}")
print()

# --- Phase 1: Systematic # command names ---
# Based on known commands: sernum, vals, date, time, ophours, setLogTime,
# start, stop, dump, #setPoint, #setPoints
# Try device-plausible names for RHC / correction / calibration
print("=== Phase 1: # command names ===")
hash_names = [
    # short forms
    "rh", "rhc", "RH", "RHC", "Rh",
    "cor", "corr", "Cor", "Corr",
    "cal", "Cal", "CAL",
    "off", "Off",
    "adj", "Adj",
    "trim", "Trim",
    # camelCase (device uses setLogTime, setPoint style)
    "rhCorr", "rhcorr", "RhCorr",
    "setRH", "setRh", "setrh",
    "setRHC", "setRhc", "setrhc",
    "setCorr", "setcorr", "SetCorr",
    "rhOffset", "rhoffset", "RhOffset",
    "setOffset", "setoffset", "SetOffset",
    "rhCal", "rhcal", "RhCal",
    "setCal", "setcal", "SetCal",
    "tempCorr", "tempcorr", "TempCorr",
    "tempOff", "tempoff", "TempOff",
    "correction", "Correction",
    "calibrate", "Calibrate",
    "offset", "Offset",
    # German (Schönbauer is Austrian)
    "korr", "Korr", "korrektur", "Korrektur",
    "kal", "Kal",
    "abgleich", "Abgleich",
    "fkorr", "Fkorr", "fKorr",
    "rHkorr", "rHKorr", "rhKorr",
    # patterns from setPoint / setPoints
    "setPoint2", "setpoint2",
    "setParam", "setparam", "SetParam",
    "setPar", "setpar",
    "config", "Config", "conf", "Conf",
    "param", "Param", "par", "Par",
    "setting", "Setting", "settings", "Settings",
    # single letters / numbers (maybe #C, #R, etc.)
    "c", "C", "r", "R", "k", "K", "o", "O",
    # maybe firmware-style
    "fw", "FW", "ver", "Ver", "version",
]

hits = []
for name in hash_names:
    ok, resp = test_hash_cmd(name)
    # "interesting" = got ! or got something other than masked-echo + ?
    is_interesting = ok
    if not ok and resp:
        # check if response has anything besides #*** and ?
        non_trivial = [r for r in resp if r != "?" and not r.startswith("#")]
        if non_trivial:
            is_interesting = True
    marker = " <<<" if is_interesting else ""
    if ok:
        marker = " <<< OK!"
    print(f"  #{name:20s} -> {resp}{marker}")
    if is_interesting:
        hits.append(name)
    drain()

print()
if hits:
    print(f"Interesting hits: {hits}")
else:
    print("No interesting hits from names.")

print(f"AFTER phase 1: {read_sernum()}")
print()

# --- Phase 2: #setPoint with different prefix byte ---
# Known: #setPoint + 0x00 + field + tens + units + CR
# Maybe RHC needs a different prefix byte instead of 0x00
print("=== Phase 2: #setPoint with prefix bytes 0x01-0x0F, field=0, val=03 ===")
for prefix in range(0x01, 0x10):
    ok, resp = test_hash_blob("setPoint", bytes([prefix, 0x00, 0x00, 0x03]))
    status = "OK!" if ok else "nope"
    marker = " <<<" if ok else ""
    print(f"  prefix=0x{prefix:02X} field=0 val=03 -> {status}  {resp}{marker}")
    drain()

print()
print(f"AFTER phase 2: {read_sernum()}")
print()

# --- Phase 3: #setPoint with negative value encoding ---
# Maybe field 0-3 with special tens byte for negative?
# In dump, RHC uses 0x80 bit for sign. Try tens=0x80+value
print("=== Phase 3: #setPoint fields 0-3 with sign-bit tens ===")
for field in range(4):
    # Try 0x80 | 0 as tens, 3 as units (= -03?)
    ok, resp = test_hash_blob("setPoint", bytes([0x00, field, 0x80, 0x03]))
    status = "OK!" if ok else "nope"
    marker = " <<<" if ok else ""
    print(f"  field={field} tens=0x80 units=3 -> {status}  {resp}{marker}")
    drain()

print()
print(f"FINAL: {read_sernum()}")
ser.close()

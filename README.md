# miniClima EBC10 — RS232 Python Client

A Python library and CLI tool to communicate with the **miniClima EBC10** constant humidity device over RS232, running on a Raspberry Pi.

## Background

The miniClima EBC10 is a humidity controller for museum display cases made by Schönbauer GmbH (Austria). It exposes an RS232 "PC" port on the front panel. The device uses a **proprietary binary protocol** for commands, reverse-engineered by sniffing the official miniClima Tool (Windows) communication. The device also pushes human-readable semicolon-delimited CSV measurements automatically.

## Hardware Setup

```
EBC10 "PC" RS232 port
        │
   RS232→USB adapter
        │
   Raspberry Pi USB
   (/dev/ttyUSB0)
```

### Serial Parameters
| Parameter | Value |
|---|---|
| Baud rate | 9600 (TBC) |
| Data bits | 8 |
| Parity | None |
| Stop bits | 1 |
| Flow control | None |

> ⚠️ Parameters marked TBC must be confirmed from sniffing session. See `docs/SNIFFING_PLAN.md`.

## Installation

```bash
git clone https://github.com/youruser/miniclima-rs232.git
cd miniclima-rs232
pip install -r requirements.txt
```

### requirements.txt
```
pyserial>=3.5
```

## Usage

### Passive logger (works immediately, no protocol knowledge needed)
```bash
python src/logger.py --port /dev/ttyUSB0 --baud 9600 --output ebc10_log.csv
```

### Interactive client (requires protocol to be fully decoded)
```bash
python src/client.py --port /dev/ttyUSB0 --baud 9600
```

## Pushed Data Format

The EBC10 automatically emits CSV lines at each datalogger interval:
```
date;time;T/°C;RH/%;set/%;alarmMin/%;alarmMax/%;timeDiff_seconds
26.05.09;09:47:32;26;50;50;40;60;0;
```

| Field | Description |
|---|---|
| date | DD.MM.YY |
| time | HH:MM:SS |
| T/°C | Temperature in Celsius |
| RH/% | Measured relative humidity |
| set/% | Current setpoint |
| alarmMin/% | Low alarm threshold |
| alarmMax/% | High alarm threshold |
| timeDiff_seconds | Seconds since last log entry |

## Protocol — Command Frames (INCOMPLETE — update after sniffing)

> ⚠️ The sections below are placeholders. Fill in after completing `docs/SNIFFING_PLAN.md`.

### Frame Structure (hypothesis)
```
[STX] [CMD_ID] [LENGTH] [PAYLOAD...] [CHECKSUM] [ETX]
```
All fields to be confirmed from captured hex dumps.

### Known Command IDs (TBC)
| Command | CMD_ID | Payload | Notes |
|---|---|---|---|
| Handshake | 0x?? | — | TBC |
| Set setpoint | 0x?? | 1 byte: RH% | TBC |
| Set hysteresis | 0x?? | 1 byte | TBC |
| Set alarmMin | 0x?? | 1 byte: RH% | TBC |
| Set alarmMax | 0x?? | 1 byte: RH% | TBC |
| Set log rate | 0x?? | 1 byte: minutes | TBC |
| Start unit | 0x?? | — | FW >= 111215 |
| Stop unit | 0x?? | — | FW >= 111215 |
| Sync time | 0x?? | date+time bytes | TBC |
| Read history | 0x?? | — | up to 15,000 entries |

## File Overview

| File | Purpose |
|---|---|
| `src/relay.py` | Windows relay script for sniffing via com0com |
| `src/logger.py` | Passive listener — logs pushed CSV to file |
| `src/protocol.py` | Frame builder/parser — fill in after sniffing |
| `src/client.py` | High-level EBC10 client |
| `docs/SNIFFING_PLAN.md` | Step-by-step sniffing guide |
| `captures/` | Raw hex dumps from sniffing sessions |

## References
- miniClima EBC Series Manual (llfa.de)
- miniClima Tool Manual (llfa.de)
- miniClima product page: https://miniclima.com

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install / sync all workspace packages
uv sync

# CLI — read device status
uv run ebc10 --port /dev/ttyACM0 status

# CLI — all subcommands: vals sernum date time ophours dump start stop set-sp set-log-time set-date set-time
uv run ebc10 --port /dev/ttyACM0 <cmd> [value]

# API server (hot-reload, port 8000)
uv run --package miniclima-api uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Passive logger (streams pushed data to CSV)
uv run python tools/logger.py --port /dev/ttyACM0

# Task runner (just must be installed: brew install just)
just          # list all recipes
just sync     # uv sync
just api      # start API server
just cli <args>  # CLI passthrough — e.g. just cli set-sp 55
just push     # rsync to bill + uv sync there
```

---

# miniClima EBC10 — RS232 Integration Project

## Project Goal
Build a Python client on Raspberry Pi to read logs and send commands to the miniClima EBC10 constant humidity device over RS232.

## Device
- **Model**: miniClima EBC10 (Schönbauer GmbH, Austria)
- **Serial**: #004537, Firmware: 170908.04 (2017-09-08 rev 4)
- **Function**: Constant humidity controller for museum display cases
- **RS232 port**: Front panel "PC" port
- **Serial settings**: 9600 baud, 8N1, no flow control (confirmed via sniffing)

## Protocol (reverse-engineered — 5 sniffing sessions completed)

The protocol is **plain 7-bit ASCII**, not binary. No framing, no checksums. Behaves like an interactive terminal:
- Host sends `command\r`
- EBC responds with value or `?\r\n` (prompt) if expecting input
- For writes: host sends nibble-encoded value + `\r`
- EBC responds `!\r\n` (success) or `?\r\n` (fail/out-of-range)

### Value encoding for writes
Each decimal digit is sent as its raw numeric value, not ASCII code:
- `15` → `01 05 0D`
- `26.03.23` → `02 06 2E 00 03 2E 02 03 0D` (`.` sent as-is `0x2E`)

### Confirmed READ commands
| Command | Response |
|---|---|
| `\r` | `\r` (keepalive, every ~2s) |
| `sernum\r` | `#004537 M 170908.04 Set:SP LO HI HY LT TO ??\r\n` |
| `date\r` | `26.03.26\r\n` (DD.MM.YY) |
| `time\r` | `14:54\r\n` (HH:MM) |
| `setLogTime\r` | `15\r\n` (minutes) |
| `vals\r` | `Running XX YY +T1 +T2 00 [p/*]\r\n` or `Stand by ...` |
| `ophours\r` | `000004\r\n` (6-digit operating hours) |
| `q\r` | multi-line status dump (full format not yet captured cleanly) |
| `#setPoints+000\r` | `#**************\r\n` (14 asterisks — read/poll form; always sent) |
| `#setPoints+NNN\r` | `#**************\r\n` (write-attempt form; NNN = target SP in 3-digit decimal, e.g. `+050`; sent right after `+000` when Tool wants to change SP; whether it actually writes SP needs live test) |
| `dump\r` → `yes\r` | ASCII hex data stream + `!\r\n` (full history log) |

### Confirmed WRITE commands
| Command | Payload example | Meaning |
|---|---|---|
| `setLogTime\r` → value | `01 05 0D` = 15 min | Set log interval (1–99 min) |
| `date\r` → value | `02 06 2E 00 03 2E 02 03 0D` = 26.03.23 | Set date |
| `time\r` → value | nibble-encoded HH:MM | Set time |
| `#setPoint\x00\x00 SP1 SP2\r` | `00 00 05 07 0D` = SP 57% | Set setpoint (no 's' — different from read) |
| `start\r` | — | Start the unit |
| `stop\r` | — | Stop the unit |

### `vals` response format
```
Running  67    27    +06   +36   00   p
  │       │     │     │     │    │    │
  │       │     │     │     │    │    └─ Flag: 'p' (Peltier active), '*' (error), empty
  │       │     │     │     │    └────── Unknown (always 00)
  │       │     │     │     └─────────── T2 (hot side °C)
  │       │     │     └───────────────── T1 (cold side °C)
  │       │     └─────────────────────── Unknown (26–28, possibly dewpoint or 2nd RH)
  │       └───────────────────────────── Humidity reading (%, possibly case RH)
  └─────────────────────────────────────── State: "Running" or "Stand by"
```

### `sernum` field layout
```
#004537 M 170908.04 Set:55 40 70 02 15 -05 04
                        SP LO HI HY LT  TO ??
```
`??` correlates with HY (HY=1→02, HY=2→04) but exact meaning unknown.

### History dump protocol (confirmed)
```
TX: dump\r  →  RX: dump\r\nreally?\r\n  →  TX: yes\r  →  RX: yes\r<hex stream>!\r\n
```
- Data is ASCII hex text (each byte = 2 hex chars). Empty flash = `FF`.
- Records are 16 bytes / 32 hex chars: `TYPE YY MM DD HH MM <10 data bytes>` (BCD)
- TYPE: `FA`=event, `F1`/`FB`=data records; data bytes = settings/sensor snapshot
- Full record decode still in progress.

### `#setPoints+NNN` — dual-form command
- `#setPoints+000\r` = read/poll query (sent every cycle after `sernum`)
- `#setPoints+NNN\r` (NNN ≠ 000) = write-attempt form, sent ~100ms after the `+000` in same cycle
- EBC always responds `#**...**\r\n` (14 asterisks); `?\r\n` seen after asterisks in captures is from concurrent keepalive bytes, NOT part of this response
- NNN hypothesis: 3-digit decimal of target SP (e.g. `+050` = SP 50%). Inconsistent variants (`+444` for SP=54, `+555` for SP=57, `+111`/`+222` transitionally) seen across sessions — encoding not fully confirmed
- `# TODO: confirm` — whether `#setPoints+NNN` actually changes the SP on the EBC needs live testing

### NOT YET DECODED
- AlarmMin / AlarmMax / Hysteresis write commands (LO, HI, HY)
- Temperature offset write command
- `#setPoint \x00\x00` prefix — observed constant, purpose unknown
- Full `q\r` response format
- History dump record format — full field decode
- `#setPoints+NNN` write-form effect — confirmed via captures but not tested live

### Autonomous push messages (EBC → host, no request)
- Periodic: `XX YY +T1 +T2 00 [flag]\r\n` (same fields as vals, no state prefix)
- Stop event: `26.03.26 09:32 Stop\r\n`
- Start event: `26.03.26 08:59 Start\r\nSet:57 39 69 02 15 -05 04\r\n68 27 +15 +35 00 \r\n`
- Settings change: `26.03.26 09:45 Set:57 39 69 02 15 -05 04\r\n` (after `#setPoint` write)
- Error: `26.03.26 14:55 Signal Error\r\n`

## Repository Structure

uv workspace — three members (`packages/ebc10`, `apps/cli`, `apps/api`).

```
packages/ebc10/src/ebc10/
  client.py     — Client class: _cmd / _write_cmd / _echo_cmd low-level I/O; all read/write methods
  cmd_enum.py   — Cmd(str, Enum) subcommand names; __str__ = str.__str__ fixes Python 3.11 argparse regression
  __init__.py   — re-exports Client, encode_nibbles, Cmd

apps/cli/src/cli/main.py   — argparse entry point; uses Client as context manager
apps/api/src/api/main.py   — FastAPI; PORT/BAUD from EBC10_PORT/EBC10_BAUD env; each handler opens fresh Client
tools/logger.py            — passive listener, logs autonomous EBC pushes to CSV (no protocol knowledge needed)
tools/relay.py             — Windows-only COM-port relay for protocol sniffing; hardcoded TOOL_PORT/DEVICE_PORT
```

## How to Help Me (Claude Instructions)
- Protocol is ASCII text, not binary — do not suggest binary framing or checksums.
- When I paste hex dumps, help identify: command names, nibble-encoded values, response codes.
- Protocol is implemented in `packages/ebc10/src/ebc10/client.py` (`Client`); CLI in `apps/cli/src/cli/main.py`.
- When implementing writes, use nibble encoding (digit value, not ASCII code).
- `#setPoint` takes the SP value as `\x00\x00[tens_nibble][units_nibble]\r` — the `\x00\x00` prefix is confirmed but purpose unknown; use it as-is.
- `start\r` and `stop\r` respond with a command echo, NOT `!\r\n` — check for echo string, not `!`.
- History dump: `dump\r` → EBC says `really?\r\n` → send `yes\r` → receive ASCII hex stream ending with `!\r\n`. Each byte encoded as 2 hex chars.
- `#setPoints+NNN`: Tool sends `+000` as the poll query each cycle, then optionally `+NNN` (NNN = 3-digit decimal SP target) as a write attempt. Whether this actually sets SP needs live confirmation — mark with `# TODO: confirm`. The confirmed SP write is `#setPoint` (no 's') with `\x00\x00` prefix and nibble encoding.
- `_write_cmd()` accepts `raw_payload: bytes` for binary payloads (e.g. `#setPoint` with `\x00\x00` prefix). Use `raw_payload=` instead of `value=` to skip nibble encoding.
- `dump()` reads the response with `ser.read(256)` in a loop (not readline) — the hex stream is not line-delimited.
- Flag unconfirmed behaviour with `# TODO: confirm` comments.
- Target: Python 3.10+, pyserial, Raspberry Pi (`/dev/ttyACM0` with QinHeng CH34x adapter).
- Keep it simple — this is a single-device integration, not a general library.
- Do NOT use `uvicorn[standard]` on low-RAM ARM devices (Orange Pi Zero etc.) — it pulls in `uvloop` which OOMs during compilation. Use plain `uvicorn`.

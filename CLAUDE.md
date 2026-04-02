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

# Task runner (just must be installed: brew install just / sudo apt install just)
just                  # list all recipes
just sync             # uv sync
just api              # start API server
just cli <args>       # CLI passthrough — e.g. just cli set-sp 55
just push             # rsync to bill + uv sync there
just frontend-dev     # Next.js dev server (port 3000)
just frontend-build   # production build

# Docker — build images
just docker-build-api       # build API image
just docker-build-frontend  # build frontend image (bakes NEXT_PUBLIC_API_URL)

# Docker — run full stack (API + frontend + Prometheus + Grafana)
just docker-restart      # build -> down -> up -> ps
just docker-up           # start all services
just docker-down         # stop all services
just docker-ps           # check status
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

### History dump protocol (confirmed)
```
TX: dump\r  →  RX: dump\r\nreally?\r\n  →  TX: yes\r  →  RX: yes\r<hex stream>!\r\n
```
- Data is ASCII hex text (each byte = 2 hex chars). Empty flash = `FF`.
- **Variable Length Structure:** The stream uses control bytes (`0xF0`–`0xFF`) as absolute sync markers.
  - `0xFF`: Empty flash (skipped).
  - `0xFB`: Settings snapshot. 10 bytes total. Plain hex. `[FB, SP, LO, HI, HY, TO, ??, pad, LT, pad]`. (TO uses `0x80` bit for negative).
  - `0xF9`: Extended event. 7 bytes total. `[F9, 00, YY, MM, DD, HH, MM]` (BCD timestamp).
  - `0xF0, F1, FA, FD, FE`: Standard events. 6 bytes total. `[TYPE, YY, MM, DD, HH, MM]` (BCD timestamp).
  - `< 0xF0`: Periodic measurement. 4 bytes total. `[RH, YY, T1, T2]`. (T1/T2 > 127 are negative).
- `parse_dump_records(hex_str)` in `ebc10/utils.py` uses a state machine. It aborts the current record and resyncs if it encounters an unexpected `0xF0`-`0xFF` byte mid-payload (caused by flash write interruptions).

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
  client.py     — Client class: _cmd / _write_cmd / _echo_cmd low-level I/O; all read/write methods; dump() strips "yes\r" echo prefix
  utils.py      — utilities functions: _bcd / _first_control / parse_dump_records / encode_nibbles
  cmd_enum.py   — Cmd(str, Enum) subcommand names; __str__ = str.__str__ fixes Python 3.11 argparse regression
  __init__.py   — re-exports Client, encode_nibbles, parse_dump_records, Cmd

apps/cli/src/cli/main.py   — argparse entry point; uses Client as context manager
apps/api/src/api/
  main.py        — thin wiring layer: lifespan, middleware, all endpoints (~140 lines)
  connection.py  — serial state (_lock, _client, _ws_clients, _latest); blocking helpers (ensure_connected, read_status, exec_write, close_client)
  prometheus.py  — Gauge/Counter metrics; update_live_metrics(); hand-rolled protobuf + snappy remote write; push_records_to_prometheus()
  poll.py        — background poll loop; broadcasts to WebSocket clients; reconnects on error
tools/logger.py            — passive listener, logs autonomous EBC pushes to CSV (no protocol knowledge needed)
tools/relay.py             — Windows-only COM-port relay for protocol sniffing; hardcoded TOOL_PORT/DEVICE_PORT

frontend/                  — Next.js 16 app (npm run dev / build / lint)
  NOTE: Next.js 16 has breaking changes vs earlier versions.
  Read node_modules/next/dist/docs/ before writing frontend code.

Dockerfile                 — API-only image; copies packages/ebc10 + apps/api, excludes frontend/cli/tools
.dockerignore              — excludes frontend/, apps/cli/, tools/, .venv/, node_modules/
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
- API modules: `connection.py` (serial state + blocking helpers), `prometheus.py` (metrics + remote write), `poll.py` (background loop), `main.py` (FastAPI wiring only). Import shared state as `import api.connection as conn; conn._latest` — never copy to a local var.
- `LOG_LEVEL` env var configures both API logger and `ebc10` logger — set `DEBUG` for raw serial traffic in container logs.
- `python-snappy` (Prometheus remote write dep) requires system `libsnappy` — not available on macOS without `brew install snappy`. Only needed in Docker; local import errors are expected.
- Prometheus remote write: `POST /dump/import` retrieves full dump, parses, pushes historical samples. Requires `--web.enable-remote-write-receiver` on Prometheus (already in docker-compose.yml).
- Target: Python 3.10+, pyserial, Raspberry Pi (`/dev/ttyACM0` with QinHeng CH34x adapter).
- Do NOT use `uvicorn[standard]` on low-RAM ARM devices (Orange Pi Zero etc.) — it pulls in `uvloop` which OOMs during compilation. Use plain `uvicorn`.

## Deployment Notes

### Remote host
Target device is `ben` (Raspberry Pi 4B, `/home/khrap/miniclima`). Use `ssh ben` and `just push` to sync.
Alternative device is `bill` (Orange Pi Zero, `/home/khrap/miniclima`). Use `ssh bill` and `just push` to sync.
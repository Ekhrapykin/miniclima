# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install / sync all workspace packages
uv sync

# CLI — read device status
uv run ebc10 --port /dev/ttyACM0 status

# CLI — all subcommands: vals sernum date time ophours dump start stop set-sp set-alarm-min set-alarm-max set-hysteresis set-log-time set-date set-time
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

## Protocol

Full protocol reference: [PROTOCOL.md](./PROTOCOL.md). Key points for writing code:
- Plain 7-bit ASCII, not binary. No framing, no checksums.
- `?` is the device's idle prompt (sent after any `\r` input), not a write-specific prompt.
- Write commands (`setLogTime`, `date`, `time`): send command + payload back-to-back with ~100ms delay. Do NOT wait for `?`.
- `#setPoint` (no 's'): blob protocol — `#setPoint\x00[field_id][tens][units]\r` as one contiguous write. Field IDs: 0=SP, 1=HI, 2=LO, 3=HY.
- `#setPoints+NNN` (with 's'): polling heartbeat only — confirmed NO write effect.
- `start`/`stop`: respond with echo, NOT `!`.
- RHC write: not yet reverse-engineered (`set_rhcorr` raises `NotImplementedError`).

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
- Protocol is implemented in `packages/ebc10/src/ebc10/client.py` (`Client`); CLI in `apps/cli/src/cli/main.py`.
- Read [PROTOCOL.md](./PROTOCOL.md) before modifying serial communication code.
- When I paste hex dumps, help identify: command names, nibble-encoded values, response codes.
- `_write_cmd()` accepts `raw_payload: bytes` for binary payloads. Use `raw_payload=` instead of `value=` to skip nibble encoding.
- API modules: `connection.py` (serial state + blocking helpers), `prometheus.py` (metrics + remote write), `poll.py` (background loop), `main.py` (FastAPI wiring only). Import shared state as `import api.connection as conn; conn._latest` — never copy to a local var.
- `LOG_LEVEL` env var configures both API logger and `ebc10` logger — set `DEBUG` for raw serial traffic in container logs.
- `python-snappy` (Prometheus remote write dep) requires system `libsnappy` — not available on macOS without `brew install snappy`. Only needed in Docker; local import errors are expected.
- Prometheus remote write: `POST /dump/import` retrieves full dump, parses, pushes historical samples. Requires `--web.enable-remote-write-receiver` on Prometheus (already in docker-compose.yml).
- Target: Python 3.10+, pyserial, Raspberry Pi (`/dev/ttyACM0` with QinHeng CH34x adapter).
- Do NOT use `uvicorn[standard]` on low-RAM ARM devices (Orange Pi Zero etc.) — it pulls in `uvloop` which OOMs during compilation. Use plain `uvicorn`.

## Deployment Notes

### Remote host
Target device is `ben` (Raspberry Pi 4B, `/home/khrap/miniclima`). Use `ssh ben` and `just push` to sync. Frontend available on `http://ben.local:3000/`. Deployment via docker.
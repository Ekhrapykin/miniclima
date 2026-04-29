# miniClima EBC10 — RS232 Python Client

A Python library and CLI tool to communicate with the **miniClima EBC10** constant humidity device over RS232, running on a Raspberry Pi.

## Background

The miniClima EBC10 is a humidity controller for museum display cases made by Schönbauer GmbH (Austria). It exposes an RS232 "PC" port on the front panel. The manufacturer describes the protocol as "proprietary" — however, five sniffing sessions with the official miniClima Tool (Windows) revealed it is a **plain 7-bit ASCII text protocol** with no binary framing, no checksums, and no STX/ETX wrapping. The interface behaves like an interactive serial terminal.

## Hardware Setup

```
EBC10 "PC" RS232 port
        │
   RS232→USB adapter
        │
   Raspberry Pi USB
   (/dev/ttyUSB0)
```

### Serial Parameters (confirmed)

| Parameter | Value |
|---|---|
| Baud rate | 9600 |
| Data bits | 8 |
| Parity | None |
| Stop bits | 1 |
| Flow control | None |
| TX line ending | `\r` (0x0D) |
| RX line ending | `\r\n` (0x0D 0x0A) |

## Installation

```bash
# Build dependencies (Debian/Ubuntu/Raspberry Pi OS)
sudo apt update
sudo apt install -y build-essential python3-dev

git clone https://github.com/ekhrapykin/miniclima.git
cd miniclima
uv sync

# Optional: install just task runner
sudo apt install just   # Debian/Ubuntu/Raspberry Pi OS
# brew install just       # macOS

# Docker
sudo apt update

curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
sudo apt install -y docker-compose-plugin

curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Usage

### Via task runner (recommended)
```bash
just status                    # quick device status
just cli vals                  # live readings
just cli set-sp 55             # set setpoint to 55%
just cli dump                  # retrieve history log
just api                       # start API server (port 8000)
just frontend-dev              # start Next.js dashboard (port 3000)
```

### Via CLI directly
```bash
uv run ebc10 --port /dev/ttyACM0 status
uv run ebc10 --port /dev/ttyACM0 vals
uv run ebc10 --port /dev/ttyACM0 start
uv run ebc10 --port /dev/ttyACM0 stop
uv run ebc10 --port /dev/ttyACM0 set-sp 55
uv run ebc10 --port /dev/ttyACM0 set-log-time 15
uv run ebc10 --port /dev/ttyACM0 set-date 26.03.26
uv run ebc10 --port /dev/ttyACM0 set-time 14:54
uv run ebc10 --port /dev/ttyACM0 dump
```

Add `-v` for verbose serial debug output.

## Docker — full stack

| Service    | Default port | URL                     |
|------------|--------------|-------------------------|
| frontend   | 3000         | http://ben.local:3000   |
| api        | 8000         | http://ben.local:8000   |
| prometheus | 9090         | http://ben.local:9090   |
| grafana    | 3002         | http://ben.local:3002   |

Ports are configurable via `.env` (`API_PORT`, `FRONTEND_PORT`, `PROMETHEUS_PORT`, `GRAFANA_PORT`).

```bash
# Build images (run on the target device)
just docker-build-api
just docker-build-frontend

# Start / stop all services
docker compose up -d
docker compose down
docker compose ps

# Rebuild and restart everything
just docker-restart
```

**Serial device permissions (rootless Docker):** The container runs as uid/gid 1000 and won't inherit the host's `dialout` group. Fix with a udev rule on the target device:

```bash
echo 'KERNEL=="ttyACM[0-9]*", GROUP="khrap", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-ttyacm.rules
sudo udevadm control --reload-rules && sudo udevadm trigger --name-match=ttyACM0
```

**Grafana first run:** Add a Prometheus data source with URL `http://prometheus:9090`. The EBC10 dashboard will auto-provision.

**Debug serial traffic:** Set `LOG_LEVEL=DEBUG` in `.env` to see raw ebc10 serial exchange in container logs (`docker compose logs -f api`).

---

## [Protocol Reference](./PROTOCOL.md) 
 
## File Overview

| Path | Purpose                                                                                                |
|---|--------------------------------------------------------------------------------------------------------|
| `packages/ebc10/` | `Client` class — protocol library (pyserial), `utils.py` - used for parse_dump_records, encode_nibbles |
| `apps/api/` | FastAPI server split into: `main.py` (routes), `connection.py` (serial), `prometheus.py` (metrics + remote write), `poll.py` (background loop) |
| `apps/cli/` | `ebc10` CLI entry point                                                                                |
| `frontend/` | Next.js dashboard; WebSocket client with exponential backoff reconnect                                 |
| `tools/logger.py` | Passive listener — logs pushed data to CSV                                                             |
| `tools/relay.py` | Windows COM-port relay for protocol sniffing                                                           |
| `Dockerfile` | API image (python:3.13-slim, ARM-compatible)                                                           |
| `frontend/Dockerfile` | Frontend image (node:22-slim, ARM-compatible)                                                          |
| `docker-compose.yml` | Full stack: api, frontend, prometheus, grafana                                                         |
| `prometheus/prometheus.yml` | Scrape config targeting `api:8000/metrics`                                                             |
| `grafana/dashboards/` | Provisioned EBC10 dashboard (humidity, temp, setpoint, errors)                                         |
| `justfile` | Task runner — `just --list` for all recipes                                                            |

## Device Info (unit on hand)

- Serial: `#004537`
- Model: `M` (EBC10)
- Firmware: `170908.04` (2017-09-08 rev 4)

## What's next?

1. **Frontend import loader** — add visual feedback (spinner/disabled state) to the dump import button
2. **Alarm events over polling** — investigate how/whether alarm events (F9) appear in the regular poll cycle vs. only in history dump
3. **Frontend label/value validation** — verify that metric labels and values from WebSocket match the poll response structure
4. **Write command validation** — live-test `setPoint`, `SetAlarmMin`, `SetAlarmMax`, and other write commands against the device
5. **Frontend design** — isolate settings panel, increase base font sizes
6. **Settings comparison** — diff dump settings snapshots against live settings to detect drift
7. **Grafana reports review** — audit whether current panels cover all needed signals; add or remove as needed
8. **Retention period**
9. **Embed grafana to web interface**
10. **hardware** - need to calculate for device, need to adjust power consumption, power supply
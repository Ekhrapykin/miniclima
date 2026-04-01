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

## Protocol Reference

### Overview

The EBC10 uses a plain ASCII terminal protocol:

1. Host sends a command name followed by `\r`
2. EBC responds with the value, or with `?\r\n` as a prompt if it expects a value next
3. For write operations, host sends the value payload followed by `\r`
4. EBC responds with `!\r\n` on success or `?\r\n` on failure/out-of-range

The EBC also **autonomously pushes** measurement and event lines at the configured log interval — no request needed.

---

### Value Encoding for WRITE Operations

When writing numeric values, **each decimal digit is sent as its raw numeric nibble** — not as an ASCII character:

| Decimal digit | Wire byte |
|---|---|
| `0` | `0x00` |
| `1` | `0x01` |
| `5` | `0x05` |
| `9` | `0x09` |

The `.` separator in dates is sent as-is (`0x2E`). The `:` separator in times is sent as-is (`0x3A`).

**Example — set log interval to 15 minutes:**
```
TX: 01 05 0D
```

**Example — set date to 26.03.23:**
```
TX: 02 06 2E 00 03 2E 02 03 0D
```

---

### READ Commands

All commands are plain ASCII + `\r`.

#### Keepalive
```
TX: \r  (0x0D)
RX: \r  (0x0D)
```
Sent by the Tool every ~2 seconds.

#### `sernum` — Device identity and all current settings
```
TX: sernum\r
RX: #004537 M 170908.04 Set:55 40 70 02 15 -05 04\r\n
```

Field breakdown:
```
#004537  M    170908.04   Set:55  40   70   02   15   -05  04
  │       │    │               │   │    │    │    │    │    │
  │       │    │               │   │    │    │    │    │    └─ Hyst. (0.1-0.4, %)
  │       │    │               │   │    │    │    │    └────── rH corr (signed %)
  │       │    │               │   │    │    │    └─────────── Log interval (minutes)
  │       │    │               │   │    │    └──────────────── Alarm Code (e.g 01D, 04D)
  │       │    │               │   │    └───────────────────── AlarmMax (% RH)
  │       │    │               │   └────────────────────────── AlarmMin (% RH)
  │       │    │               └────────────────────────────── Setpoint (% RH)
  │       │    └────────────────────────────────────────────── Firmware (YY.MM.DD.rev)
  │       └─────────────────────────────────────────────────── Model (M = EBC10)
  └─────────────────────────────────────────────────────────── Serial number
```

#### `date` — Read current date
```
TX: date\r
RX: 26.03.23\r\n     (DD.MM.YY)
```

#### `time` — Read current time
```
TX: time\r
RX: 14:54\r\n        (HH:MM)
```

#### `setLogTime` — Read current log interval
```
TX: setLogTime\r
RX: 15\r\n           (minutes, plain ASCII decimal)
```

#### `vals` — Read live sensor readings
```
TX: vals\r
RX: Running 67 27 +06 +36 00 p\r\n
```
or when stopped:
```
RX: Stand by 64 27 +04 +39 00 \r\n
```

Field breakdown:
```
Running  67    27    +06   +36   00   p
  │       │     │     │     │    │    │
  │       │     │     │     │    │    └─ Flag: 'p' (Peltier active), '*' (sensor error), empty (ok)
  │       │     │     │     │    └────── Unknown (always 00 in captures)
  │       │     │     │     └─────────── Temperature inner sensor 2 (hot side, °C)
  │       │     │     └───────────────── Temperature inner sensor 1 (cold side, °C)
  │       │     └─────────────────────── Temperature outer sensor (°C)
  │       └───────────────────────────── Humidity outer sensor (%, possibly case RH)
  └─────────────────────────────────────── Device state: "Running" or "Stand by"
```

Note: `T1` = cold side (probe inside cabinet), `T2` = hot side (EBC unit heat sink). Typical T2 is 35–40°C when actively dehumidifying.

#### `ophours` — Read operating hours counter
```
TX: ophours\r
RX: 000004\r\n       (6-digit decimal, total operating hours)
```

#### `#setPoints+NNN` — Setpoint query and write attempt

This command has **two forms** used in the same polling cycle:

**Form 1 — Read query (always sent):**
```
TX: #setPoints+000\r
RX: #**************\r\n    (14 asterisks, meaning of masked content unknown)
```

**Form 2 — Write attempt (sent immediately after Form 1, ~100ms later, when Tool wants to change SP):**
```
TX: #setPoints+NNN\r
RX: #**************\r\n    (same response regardless of NNN)
```

The `?\r\n` that sometimes appears after the asterisks in captures is **not** part of this command's response — it comes from concurrent keepalive `\r` bytes in the buffer.

**Observed `+NNN` variants across all 5 sessions:**

| NNN | SP at time | Notes |
|-----|-----------|-------|
| `+000` | any | Read query — always present in polling cycle |
| `+050` | 50% | 3-digit decimal of SP=50 — direct match |
| `+444` | 54% | Seen in sessions 3 and 4 when SP=54; encoding unclear (`054` expected) |
| `+555` | 57% | Session 4, after SP written to 57; encoding unclear (`057` expected) |
| `+111` | 55%, then 54% | Session 3, transitional — appears right after a settings change, before settling |
| `+222` | 55% | Session 3, before settings change |
| `-555` | 55% | Session 2; `-` sign unexpected, likely garbled |

**Working hypothesis:** NNN encodes the target SP value in 3-digit decimal (e.g. `+050` = SP 50%). The inconsistent variants (`+444`, `+555`) may be a Tool bug, a different encoding scheme in some firmware version, or communication noise. Whether `#setPoints+NNN` actually writes the SP or is purely a status sync is **not confirmed** — needs live testing. The confirmed SP write command is `#setPoint` (no 's').

---

### WRITE Commands

#### `setLogTime` — Set log interval (confirmed)
```
TX: setLogTime\r
RX: ?\r\n                  <- prompt
TX: D1 D2 0D               <- nibble-encoded minutes
RX: setLogTime\r\n         <- command echo
RX: NN\r\n                 <- new value echo (ASCII decimal)
RX: !\r\n                  <- success  (or ?\r\n if out of range)
```
Valid range: 1–99 minutes.

#### `date` — Set device date (confirmed)
```
TX: date\r
RX: ?\r\n
TX: D1 D2 2E D3 D4 2E D5 D6 0D    <- DD.MM.YY in nibbles, '.' as-is
RX: !\r\n
```

#### `time` — Set device time (confirmed)
```
TX: time\r
RX: ?\r\n
TX: H1 H2 3A M1 M2 0D             <- HH:MM in nibbles, ':' as-is
RX: !\r\n
```

#### `#setPoint` — Set setpoint RH (confirmed)

Note: this is `#setPoint` (no 's') — distinct from the read query `#setPoints+000`.

```
TX: #setPoint\x00\x00 SP1 SP2 0D    <- SP value nibble-encoded, \x00\x00 prefix (unknown purpose)
RX: #*************\r\n              <- 13 asterisks ack
RX: !\r\n                           <- success
RX: DD.MM.YY HH:MM Set:SP LO HI HY LT TO ??\r\n  <- event push confirming new settings
```

**Confirmed examples:**
```
SP 54 → 57:  TX: 23 73 65 74 50 6F 69 6E 74 00 00 05 07 0D
             (= #setPoint + \x00\x00 + nibble(5) + nibble(7) + CR)

SP 57 → 50:  TX: 23 73 65 74 50 6F 69 6E 74 00 00 05 00 0D
             (= #setPoint + \x00\x00 + nibble(5) + nibble(0) + CR)
```

The `\x00\x00` prefix is consistent across both captures — purpose unknown (possibly flags or padding).

#### `start` — Start the unit (confirmed)
```
TX: start\r
RX: start\r\n            <- echo
```
After starting, EBC autonomously pushes: `DD.MM.YY HH:MM Start\r\nSet:...\r\nXX YY +T1 +T2 ZZ FLAG\r\n`

#### `stop` — Stop the unit (confirmed)
```
TX: stop\r
RX: stop\r\n?\r\n        <- echo + prompt
```
After stopping, `vals` response changes from `Running` to `Stand by`. EBC autonomously pushes: `DD.MM.YY HH:MM Stop\r\n`

#### `dump` — Retrieve history log (confirmed)
```
TX: dump\r
RX: dump\r\nreally?\r\n    <- echo + confirmation prompt
TX: yes\r
RX: yes\r\n<data>!\r\n     <- data stream terminated by !
```
The data stream is **ASCII hex text**: each flash memory byte is encoded as two ASCII hex characters (e.g., `FB` in the stream = byte `0xFB`). Empty (erased) slots appear as `FF`.

**Empty flash padding.** The EBC transmits the *entire* flash contents — valid records followed by all remaining erased bytes — before sending `!`. On a lightly used device, valid data may occupy only ~6 KB while the device streams 60+ KB of `FF` padding, costing roughly 2 minutes of serial read time at 9600 baud.

`dump()` mitigates this by stopping early on the first even-aligned `FF` pair, since `0xFF` is the unambiguous end-of-data marker in the record format. `clean_dump()` applies the same trim as a post-processing safety net (useful for replaying saved captures).

**Trade-off.** The early-exit heuristic checks `data[-2:] == b"FF"` at even alignment after each 256-byte chunk. Edge case: a valid measurement record whose last two hex chars happen to be `FF` (e.g. T = −1 = `0xFF`) and which lands exactly at a chunk boundary would cause a premature stop. In practice this is rare and the worst outcome is a truncated dump — `parse_dump_records` handles partial streams gracefully. The `clean_dump` post-processing strips any residual FF tail in either case.

**Serial buffer pollution.** Early exit leaves the remaining FF stream unread in the OS serial buffer. Without cleanup, the next command (e.g. `sernum`) reads that garbage instead of its real response. Two options were considered:

- *Synchronous drain* — loop reading until `!` before returning. Correct, but costs the same ~2 min the early exit was trying to avoid.
- *Background drain* (implemented) — `dump()` returns data immediately; a background asyncio task acquires the serial lock and drains to `!` while the HTTP response is already on its way to the client. Measured improvement: ~25 s response vs ~2.3 min with synchronous drain.

To prevent the poll loop from reading garbage between early exit and the drain task acquiring the lock, `_draining = True` is set **inside the lock** before `dump_import` releases it. The poll loop checks this flag and skips its serial read for that cycle. The drain task clears the flag in a `finally` block once `!` is received or the connection times out.

**Record Format (Variable Length)**

The EBC10 history log does NOT use fixed blocks. It uses a tightly packed stream where bytes `0xF0`–`0xFF` act as absolute synchronization markers. Records are distinguished by their first byte.

Timestamps are BCD encoded: `26 03 31 17 00` = 2026-03-31 17:00.

#### Record type table

| First byte | Name | Total size | Layout |
|---|---|---|---|
| `0x00`–`0xEF` | **Measurement** | 4 bytes | `[RH, T, T1, T2]` |
| `F0` | **Log marker** | 6 bytes | `[F0, YY, MM, DD, HH, MM]` |
| `F1` | **First record** | 6 bytes | `[F1, YY, MM, DD, HH, MM]` — once only, oldest entry |
| `F4` | **Pump stop** | 7 bytes | `[F4, 00, YY, MM, DD, HH, MM]` |
| `F5` | **Pump start** | 7 bytes | `[F5, 04, YY, MM, DD, HH, MM]` |
| `F9` | **Alarm event** | 7 bytes | `[F9, 00, YY, MM, DD, HH, MM]` |
| `FA` | **Start** | 6 bytes | `[FA, YY, MM, DD, HH, MM]` |
| `FB` | **Settings snapshot** | 10 bytes | `[FB, SP, LO, HI, HY, TO, ??, pad, LT, pad]` |
| `FD` | **Stop** | 6 bytes | `[FD, YY, MM, DD, HH, MM]` |
| `FE` | **Error** | 6 bytes | `[FE, YY, MM, DD, HH, MM]` |
| `FF` | **Empty flash** | — | End of valid data; stream stops here |

#### Measurement record fields

```
RH   T    T1   T2
│    │    │    │
│    │    │    └─ Inner sensor 2 — hot side of Peltier (°C, signed)
│    │    └────── Inner sensor 1 — cold side / probe (°C, signed)
│    └─────────── Outer temperature sensor (°C, signed) — independent of T1/T2
└──────────────── Relative humidity, outer sensor (%)
```

Values > 127 are negative (interpret as signed byte, i.e. subtract 256).

#### Settings snapshot (`FB`) fields

```
SP   LO   HI   HY   TO   ??   pad  LT   pad
│    │    │    │    │                │
│    │    │    │    │                └─ Log interval (minutes)
│    │    │    │    └────────────────── rH correction offset (°C, 0x80 bit = negative, e.g. 0x85 = -5)
│    │    │    └─────────────────────── Hysteresis (%)
│    │    └──────────────────────────── Alarm max (% RH)
│    └───────────────────────────────── Alarm min (% RH)
└────────────────────────────────────── Setpoint (% RH)
```

All fields are plain hex (not BCD).

#### Known event sequences

**Start sequence** — always `FA` immediately followed by `FB`:
```
FA [timestamp]
FB [settings]
```

**Stop sequence** — `FD` + settings + optional measurements:
```
FD [timestamp]
FB [settings]
[meas] ...
```

**Alarm triplet** — appears after every stop; all three share the same timestamp:
```
F9 00 [timestamp]   ← alarm triggered
F0    [timestamp]   ← logged
FE    [timestamp]   ← error flagged
```

**Pump cycle** — `F5`/`F4` alternate; measurements only appear after `F4` (pump-off):
```
F5 04 [timestamp]   ← pump on
F4 00 [timestamp]   ← pump off
[meas] ...          ← readings taken after pump stops
```

**F1** appears only once as the absolute first record in the flash, marking device first power-on or first use. Not seen in subsequent log rolls.

`POST /dump/import` API endpoint retrieves full dump, parses records, pushes to Prometheus as historical samples via remote write.

#### AlarmMin / AlarmMax / Hysteresis / Temperature offset writes
**Status: NOT YET DECODED.** Write attempts during session 5 failed due to severe communication noise — no clean TX packet was captured. Need a stable sniffing session dedicated to changing these parameters.

---

### Response Codes

| Bytes | ASCII | Meaning |
|---|---|---|
| `21 0D 0A` | `!\r\n` | Success |
| `3F 0D 0A` | `?\r\n` | Failure, out-of-range, or waiting for value |

---

### Autonomous Push Messages (EBC → Host)

The EBC pushes these without any request.

#### Periodic measurement (every LT minutes)
```
XX YY +T1 +T2 ZZ FLAG\r\n
```
Same fields as `vals` response but without the `Running`/`Stand by` prefix.

#### Stop event
```
26.03.26 09:32 Stop\r\n
```

#### Start event
```
26.03.26 08:59 Start\r\n
Set:57 39 69 02 15 -05 04\r\n
68 27 +15 +35 00 \r\n
```
Includes full settings snapshot and current sensor readings at time of start.

#### Settings change event (after `#setPoint` write)
```
26.03.26 09:45 Set:57 39 69 02 15 -05 04\r\n
```
Pushed immediately after a successful `#setPoint` write.

#### Signal Error event
```
26.03.26 14:55 Signal Error\r\n
```

---

## Known Unknowns

| Item | Status |
|---|---|
| `#setPoint \x00\x00` prefix — exact meaning | Observed constant, purpose unclear |
| AlarmMin / AlarmMax write command | Not captured |
| Hysteresis write command | Not captured |
| Temperature offset write command | Not captured |
| `F4`/`F5` sub-byte meaning | Sub-bytes observed: `F5`=`04`, `F4`=`00`; likely pump index or mode — not confirmed |
| `F0` exact semantics | Always follows `F9` in the alarm triplet; meaning of the distinction unclear |
| Alarm triplet vs real error | `F9`+`F0`+`FE` fires after every stop — unclear if it signals an actual fault or is a normal stop log entry |
| `#setPoints+NNN` write form — effect confirmed? | Variants +000/+050/+111/+222/+444/+555/-555 seen; NNN likely = target SP in 3-digit decimal; whether it actually writes SP needs live test |

---

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
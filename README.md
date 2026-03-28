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
```

## Usage

### Read device status
```bash
python src/client.py --port /dev/ttyACM0 status
python src/client.py --port /dev/ttyACM0 vals
python src/client.py --port /dev/ttyACM0 sernum
python src/client.py --port /dev/ttyACM0 date
python src/client.py --port /dev/ttyACM0 time
python src/client.py --port /dev/ttyACM0 ophours
```

### Control
```bash
python src/client.py --port /dev/ttyACM0 start
python src/client.py --port /dev/ttyACM0 stop
python src/client.py --port /dev/ttyACM0 set-sp 55
python src/client.py --port /dev/ttyACM0 set-log-time 15
python src/client.py --port /dev/ttyACM0 set-date 26.03.26
python src/client.py --port /dev/ttyACM0 set-time 14:54
```

### History dump
```bash
python src/client.py --port /dev/ttyACM0 dump
```

Add `-v` for verbose serial debug output.

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
  │       │    │               │   │    │    │    │    │    └─ Unknown (correlates with HY: HY=1→02, HY=2→04)
  │       │    │               │   │    │    │    │    └────── Temperature offset (signed °C)
  │       │    │               │   │    │    │    └─────────── Log interval (minutes)
  │       │    │               │   │    │    └──────────────── Hysteresis (% RH)
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
  │       │     │     │     └─────────── Temperature sensor 2 (hot side, °C)
  │       │     │     └───────────────── Temperature sensor 1 (cold side, °C)
  │       │     └─────────────────────── Unknown field (26–28 range, possibly dewpoint or 2nd RH sensor)
  │       └───────────────────────────── Humidity reading (%, possibly case RH)
  └─────────────────────────────────────── Device state: "Running" or "Stand by"
```

Note: `T1` = cold side (probe inside cabinet), `T2` = hot side (EBC unit heat sink). Typical T2 is 35–40°C when actively dehumidifying.

#### `ophours` — Read operating hours counter
```
TX: ophours\r
RX: 000004\r\n       (6-digit decimal, total operating hours)
```

#### `q` — Full status dump
```
TX: q\r
RX: <multi-line block: date, time, sernum, current readings>
```
Full response format not cleanly captured yet.

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
The data stream is **ASCII hex text**: each flash memory byte is encoded as two ASCII hex characters (e.g., `FB` in the stream = byte `0xFB`). Empty (erased) slots appear as `FF`. The dump covers the entire history flash — on a unit with 4 operating hours the stream ran for ~2 minutes at 9600 baud.

**Partial record format** (16 bytes per record, 32 hex chars):
```
<TYPE> <YY> <MM> <DD> <HH> <MM> <10 bytes settings/measurement>
  1B     1B   1B   1B   1B   1B
```
- All bytes are BCD-encoded
- `TYPE` byte: `FA` = Start/event, `FD`/`FE` = other events, `F1`/`FB` = data records
- Timestamp: YY MM DD HH MM (e.g. `26 03 26 10 33` = 26.03.2026 10:33)
- Data bytes: settings snapshot (SP LO HI HY LT TO ??) packed as raw bytes
- Full record encoding not yet fully decoded — needs dedicated analysis session

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
| `vals` fields XX, YY — exact meaning | Partially understood (humidity-related) |
| `q\r` full response format | Partially seen, needs clean capture |
| History dump record format — full decode | Command known, 16-byte record structure partially identified |
| Last field in `sernum` (`04`) | Correlates with HY but meaning unclear |
| `#setPoints+NNN` write form — effect confirmed? | Variants +000/+050/+111/+222/+444/+555/-555 seen; NNN likely = target SP in 3-digit decimal; whether it actually writes SP needs live test |

---

## File Overview

| File | Purpose |
|---|---|
| `src/ebc10.py` | `Ebc10Client` class — protocol implementation |
| `src/client.py` | CLI entry point |
| `src/logger.py` | Passive listener — logs pushed data to CSV |
| `src/relay.py` | Windows relay for sniffing via com0com |
| `docs/SNIFFING_PLAN.md` | Step-by-step sniffing guide |
| `captures/` | Raw hex dumps from sniffing sessions |

## Device Info (unit on hand)

- Serial: `#004537`
- Model: `M` (EBC10)
- Firmware: `170908.04` (2017-09-08 rev 4)
- Settings at last capture: SP=50%, LO=39%, HI=69%, HY=2, LT=1min, TO=-5°C
- Operating hours at last capture: 4 hours

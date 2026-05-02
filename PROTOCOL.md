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

#### `#setPoints+NNN` — Polling heartbeat (NO write effect)

**Confirmed: this command does NOT change any device settings.** Analysis of a dedicated capture session (2026-05-02) where SP was changed multiple times via `#setPoints+NNN` showed the setpoint value remained unchanged throughout all 2922 lines. The actual SP write command is `#setPoint` (no 's') with the blob protocol described above.

The Windows miniClima Tool sends this command in two forms each polling cycle:

**Form 1 — Read query (always sent):**
```
TX: #setPoints+000\r
RX: #**************\r\n    (14 asterisks, masked content unknown)
```

**Form 2 — Sent ~100ms after Form 1 when Tool has a pending SP change:**
```
TX: #setPoints+NNN\r
RX: #**************\r\n    (same response regardless of NNN)
```

The `?\r\n` that sometimes appears after the asterisks is the device's **idle prompt** from concurrent keepalive `\r` bytes, not part of this command's response.

**Observed `+NNN` variants across 6 sessions:**

| NNN | SP at time | Notes |
|-----|-----------|-------|
| `+000` | any | Read query — always present in polling cycle |
| `+050` | 50% | 3-digit decimal of SP=50 |
| `+444` | 54% | Encoding unclear |
| `+555` | 57% | Encoding unclear |
| `+111` | transitional | Appears right after settings changes |
| `+222` | 55% | Before settings change |
| `-555` | 55% | Sign unexpected, likely garbled |

The NNN value likely encodes something related to SP but the encoding is inconsistent and the command has no observable effect on device state. It appears to be a status sync or heartbeat mechanism used by the Windows Tool.

---

### WRITE Commands

#### `setLogTime` — Set log interval (confirmed)
```
TX: setLogTime\r
    (wait ~100ms)
TX: D1 D2 0D               <- nibble-encoded minutes, sent back-to-back
RX: setLogTime\r\n         <- command echo
RX: NN\r\n                 <- new value echo (ASCII decimal)
RX: !\r\n                  <- success  (or ?\r\n if out of range)
```
Valid range: 1–99 minutes. The host sends the value ~100ms after the command without waiting for `?`.

#### `date` — Set device date (confirmed)
```
TX: date\r
    (wait ~100ms)
TX: D1 D2 2E D3 D4 2E D5 D6 0D    <- DD.MM.YY in nibbles, '.' as-is
RX: !\r\n
```

#### `time` — Set device time (confirmed)
```
TX: time\r
    (wait ~100ms)
TX: H1 H2 3A M1 M2 0D             <- HH:MM in nibbles, ':' as-is
RX: !\r\n
```

#### `#setPoint` — Set device parameters (confirmed)

Note: this is `#setPoint` (no 's') — distinct from the read query `#setPoints+000`.

The command uses a **blob protocol**: the entire payload is sent as one contiguous write with no prompt/response exchange in the middle. Format:

```
TX: #setPoint + \x00 + FIELD_ID + TENS + UNITS + \r    (all as one blob)
RX: #*************\r\n              <- asterisk-masked echo
RX: !\r\n                           <- success
RX: DD.MM.YY HH:MM Set:SP LO HI ALR LT RHC HY\r\n  <- settings broadcast
```

**Field IDs (confirmed via live testing):**

| Field ID | Parameter | Valid range | Example |
|----------|-----------|-------------|---------|
| `0x00`   | Setpoint (SP) | 0–99% | `#setPoint\x00\x00\x05\x05\r` → SP=55 |
| `0x01`   | Alarm max (HI) | 0–99% | `#setPoint\x00\x01\x07\x00\r` → HI=70 |
| `0x02`   | Alarm min (LO) | 0–99% | `#setPoint\x00\x02\x04\x00\r` → LO=40 |
| `0x03`   | Hysteresis (HY) | 1–10% | `#setPoint\x00\x03\x00\x04\r` → HY=4 |

The first `\x00` byte after `#setPoint` is constant across all field IDs — purpose unknown (possibly a padding/flags byte). The second byte selects the field.

**Confirmed capture examples (SP write):**
```
SP 54 → 57:  TX: 23 73 65 74 50 6F 69 6E 74 00 00 05 07 0D
             (= #setPoint + \x00 + field=0 + tens=5 + units=7 + CR)

SP 57 → 50:  TX: 23 73 65 74 50 6F 69 6E 74 00 00 05 00 0D
             (= #setPoint + \x00 + field=0 + tens=5 + units=0 + CR)
```

**Important:** The device responds with an asterisk-masked echo followed by a `Set:` settings broadcast, then `!`. The `!` can arrive 2–3 lines after the echo, so readers must scan multiple lines.

**Not yet discovered:** RH correction (RHC) write. Field IDs 4–8 do not work with `#setPoint`. The mechanism for writing RHC is unknown.

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

| First byte    | Name                  | Total size | Layout                                               |
|---------------|-----------------------|------------|------------------------------------------------------|
| `0x00`–`0xEF` | **Measurement**       | 4 bytes    | `[RH, T, T1, T2]`                                    |
| `F0`          | **Log marker**        | 6 bytes    | `[F0, YY, MM, DD, HH, MM]`                           |
| `F1`          | **First record**      | 6 bytes    | `[F1, YY, MM, DD, HH, MM]` — once only, oldest entry |
| `F4`          | **Pump stop**         | 7 bytes    | `[F4, 00, YY, MM, DD, HH, MM]`                       |
| `F5`          | **Pump start**        | 7 bytes    | `[F5, 04, YY, MM, DD, HH, MM]`                       |
| `F9`          | **Alarm event**       | 7 bytes    | `[F9, 00, YY, MM, DD, HH, MM]`                       |
| `FA`          | **Start**             | 6 bytes    | `[FA, YY, MM, DD, HH, MM]`                           |
| `FB`          | **Settings snapshot** | 10 bytes   | `[FB, SP, LO, HI, HY, RHC, ??, pad, LT, pad]`        |
| `FD`          | **Stop**              | 6 bytes    | `[FD, YY, MM, DD, HH, MM]`                           |
| `FE`          | **Error**             | 6 bytes    | `[FE, YY, MM, DD, HH, MM]`                           |
| `FF`          | **Empty flash**       | —          | End of valid data; stream stops here                 |

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
SP   LO   HI   HY   RHC  ??   pad  LT   pad
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

#### AlarmMin / AlarmMax / Hysteresis writes — via `#setPoint` blob (confirmed)

These use the same `#setPoint` blob protocol as the setpoint write, with different field IDs. See the `#setPoint` section above for the full protocol and field ID table.

```
Set LO=40:  TX: #setPoint\x00\x02\x04\x00\r
Set HI=70:  TX: #setPoint\x00\x01\x07\x00\r
Set HY=4:   TX: #setPoint\x00\x03\x00\x04\r
```

All confirmed via live testing (2026-05-02).

#### RH correction / Temperature offset write
**Status: NOT AVAILABLE OVER RS232.** Systematic probing (2026-05-02) tested:
- `#setPoint` field IDs 4–15 (unsigned and 0x80 sign-bit encodings) — all rejected
- `#setPoint` with alternate prefix bytes 0x01–0x0F — all rejected
- ~90 guessed `#`-prefixed command names (`#rhCorr`, `#setRHC`, `#correction`, `#offset`, `#cal`, German variants, etc.) — all returned masked echo + `?`
- Plain command names (`rhCorr`, `setRHC`, `corr`, `offset`, `cal`, etc.) with nibble-encoded payloads — all rejected

The miniClima Tool (Windows) also does not expose RHC. This setting appears to be **front-panel only**.

---

### Response Codes

| Bytes | ASCII | Meaning |
|---|---|---|
| `21 0D 0A` | `!\r\n` | Success / command accepted |
| `3F 0D 0A` | `?\r\n` | Idle prompt — sent after any input (keepalive, unrecognized command, or write failure) |

Note: `?` is the device's **idle prompt**, not specifically a write prompt or error indicator. It appears after any `\r` input (including keepalive bytes) and after failed/out-of-range write attempts. For write commands like `setLogTime`, `date`, and `time`, the host sends the value payload ~100ms after the command — it does not wait for `?` first.

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
| `#setPoint` first `\x00` byte — exact meaning | Constant across all field IDs; possibly padding or flags |
| RH correction (RHC) write command | Not available over RS232 — front-panel only (confirmed via brute-force probing) |
| `F4`/`F5` sub-byte meaning | Sub-bytes observed: `F5`=`04`, `F4`=`00`; likely pump index or mode — not confirmed |
| `F0` exact semantics | Always follows `F9` in the alarm triplet; meaning of the distinction unclear |
| Alarm triplet vs real error | `F9`+`F0`+`FE` fires after every stop — unclear if it signals an actual fault or is a normal stop log entry |
| `#setPoints+NNN` encoding | NNN variants inconsistent (+444 for SP=54, +555 for SP=57); confirmed to have no write effect |


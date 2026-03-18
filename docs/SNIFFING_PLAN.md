# Sniffing Plan — miniClima EBC10 RS232 Protocol

## Objective
Capture raw TX/RX bytes between the official miniClima Tool (Windows) and the EBC10 device in order to reverse-engineer the proprietary RS232 command protocol.

## Prerequisites
- [ ] Windows PC
- [ ] miniClima EBC10 connected to **COM3** via RS232→USB adapter
- [ ] miniClima Tool installed
- [ ] Python 3.x installed with pyserial (`pip install pyserial`)
- [ ] com0com installed (virtual null-modem driver)

---

## Phase 1 — Install com0com

1. Download com0com: https://sourceforge.net/projects/com0com/
2. Run installer **as Administrator**.
3. Open **com0com Setup** from the Start Menu.
4. Create a virtual COM pair: **COM10** ↔ **COM11**.
5. For both ports, check **"use Ports class"** — required so apps recognise them as real COM ports.
6. Click **Apply** and close.
7. Verify in Device Manager → Ports (COM & LPT) that COM10 and COM11 appear.

---

## Phase 2 — Start the relay script

The relay script sits between miniClima Tool (COM10) and the real EBC10 (COM3), forwarding all bytes and logging them to `serial_capture.txt`.

1. Open a terminal (cmd or PowerShell).
2. Run:
   ```
   python src/relay.py
   ```
3. You should see: `Relay running: COM10 <-> COM3`
4. Leave this terminal running throughout the entire sniffing session.

> If the relay fails to open COM3, check that miniClima Tool is **not** already connected to COM3.
> If bytes look garbled (non-ASCII CSV), try changing BAUD in relay.py to 19200 or 38400.

---

## Phase 3 — Connect miniClima Tool via COM10

1. Open miniClima Tool.
2. Go to **Settings / Connection** and change the COM port to **COM10**.
3. Click **Connect**.
4. You should see the tool connect and live RH/temperature data appear.
5. In the relay terminal, you should see `EBC→TOOL` lines with readable ASCII CSV data — this confirms the baud rate is correct.

---

## Phase 4 — Capture actions (do these SLOWLY, one at a time)

Wait **~10 seconds between each action** so the log is easy to segment.

| # | Action | What to note |
|---|---|---|
| 1 | Initial connect (already done) | First TOOL→EBC bytes = handshake |
| 2 | Wait 60 seconds idle | EBC→TOOL pushed CSV lines |
| 3 | Change **setpoint** from current value to +5% (e.g. 50 → 55) | TOOL→EBC command |
| 4 | Change **setpoint** back (55 → 50) | Compare with step 3 — only value byte should differ |
| 5 | Change **alarmMin** by +2% | TOOL→EBC command |
| 6 | Change **alarmMax** by −2% | TOOL→EBC command |
| 7 | Change **hysteresis** | TOOL→EBC command |
| 8 | Change **datalogger rate** | TOOL→EBC command |
| 9 | Issue **Stop unit** command (if available in Tool UI) | TOOL→EBC command |
| 10 | Issue **Start unit** command | TOOL→EBC command |
| 11 | Issue **Date/time sync** | TOOL→EBC command |
| 12 | Trigger **history readout** (if Tool has this option) | May produce a long burst |

Keep a written note of the **wall clock time** for each action (e.g. "16:34:12 — changed setpoint 50→55").

---

## Phase 5 — Collect the capture

1. Press **Ctrl+C** in the relay terminal to stop.
2. Open `serial_capture.txt`.
3. Cross-reference your written notes with timestamps in the log.

---

## Phase 6 — Analyse frames

Look for these patterns in `TOOL→EBC` lines:

### 1. Start/end bytes
Common framing patterns:
- `02 ... 03` (STX / ETX — very common in proprietary protocols)
- `7E ... 7E` (flag byte framing)
- Fixed-length frames (all commands same number of bytes)

### 2. Value encoding
For the setpoint change (50 → 55):
- ASCII encoding: `0x32` → `0x37`
- Decimal byte: `0x32` (50 dec) → `0x37` (55 dec)
- BCD: `0x50` → `0x55`
Find which byte changed and by exactly +5 — that is the RH value field.

### 3. Checksum
- Try **XOR** of all bytes between STX and ETX.
- Try **sum modulo 256** of all payload bytes.
- Try **CRC-8** or **CRC-16** if the above don't match.

### 4. Command ID
The byte that stays constant within one command type but differs between (e.g.) "set setpoint" vs "set alarmMin" is the command ID byte.

---

## Deliverables from this session

After completing the above, you should be able to fill in `src/protocol.py` with:
- Confirmed baud rate
- Frame structure (start byte, cmd byte, length, payload, checksum, end byte)
- Command ID for each operation
- Value encoding rules

Paste the hex dump of at least 3–4 `TOOL→EBC` frames into the project chat for protocol decoding assistance.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| COM10/COM11 not visible in miniClima Tool | Reinstall com0com with "use Ports class" checked |
| Garbled CSV in relay output | Wrong baud rate — try 19200 or 38400 |
| Relay opens but no data flows | Try adding `rtscts=True` to both Serial() calls in relay.py |
| miniClima Tool won't connect on COM10 | Make sure relay.py is running first |
| COM3 already in use error | Close any other program that may have COM3 open |

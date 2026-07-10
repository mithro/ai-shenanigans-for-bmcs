# I2C / SMBus — AST2050 driver + faithfulness doc

**Base 0x1E78A000.** **7 I2C/SMBus engines** (datasheet §31). One MMIO region:
global registers `0x00–0x3F`, then seven 64-byte per-engine blocks, then a shared
256-byte pool at `0x200`. Engine base (QEMU / DTS 0-indexed bus N):
`0x1E78A000 + 0x40*(N+1)` — so bus 0 = `0x1E78A040`, bus 3 (C410X `&i2c3`) =
`0x1E78A100`. Full detail: **[`DATASHEET-I2C.md`](DATASHEET-I2C.md)**. OpenBMC uses
I2C for LM75 temp sensors, EEPROMs, and PSUs.

## 1. Per-engine registers (old Aspeed layout)

| Off | Register | Notes |
|---|---|---|
| 0x00 | function control | `[0]` MASTER_EN |
| 0x04/0x08 | clock & AC timing | PCLK-derived |
| 0x0C | interrupt control | |
| 0x10 | interrupt status | TX_ACK[0] TX_NAK[1] RX_DONE[2] NORMAL_STOP[4] (W1C) |
| 0x14 | **command / status** | START[0] TX[1] RX[3] RX_LAST[4] STOP[5]; state in high bits |
| 0x18 | slave device address | 7-bit |
| 0x20 | Tx/Rx byte buffer | TX low byte, RX `[15:8]` |

**Master flow:** enable master; write the addr byte to the byte buffer; write CMD
`START` (sends the address) then `TX`/`RX`; poll interrupt-status; `STOP`.

## 2. QEMU faithfulness

`peripherals/i2c/fwtest.c` vs the current model:
- ✓ **function-control resets to 0** and **MASTER_EN is RW**.
- ✓ **the master engine executes a command**: writing `START` auto-clears the START
  bit and advances the CMD status/state field (`0x00480000`) — the state machine runs.
- ◐ **deferred:** the full transaction result did not surface via the bare probe used
  here — this model reports ACK/NAK/state in the **CMD register's status field** rather
  than only interrupt-status, and the machine's seeded device is an **`smbus_eeprom`**
  that expects the SMBus command protocol (command byte), not a plain I2C address probe.
  A full device readback (read the seeded MAC bytes back) needs that exact sequence —
  captured as a follow-up. The *register interface + engine execution* are faithful.

**Gap:** the AST2400-based model exposes more I2C engines than the G3's **7** (AST2400
has up to 14); a strictly-faithful G3 machine would present 7. G3 firmware only uses the
buses it declares in the DTS, so this is low-impact; narrowing it is oracle-gated.

## 3. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ register + engine-execution (device readback deferred) |
| 2 | doc (this + `DATASHEET-I2C.md`) | ☑ |
| 3 | QEMU model | ◐ register + master-engine faithful; full-transaction readback + 7-bus narrowing deferred |
| 4 | integration test (`../../integration/test_i2c.py`) | ☑ (readback xfail) |

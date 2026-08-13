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
- ✓ **held in reset by SCU04[2]** at power-up (reset default = held): register writes are
  inert until firmware unlocks the SCU (key `0x1688A8A8`) and de-asserts the I2C reset bit.
  The G3 SoC wires SCU04[2] → the `g3-i2c-rst` line that disables the whole 7-engine I2C
  MMIO region (reads fall through to 0, writes dropped) until de-asserted — the g3-clk /
  reset-hold faithfulness work (`hw/arm/aspeed_ast2400.c` §"clock-stop / reset-hold",
  datasheet §18 p.205). This is real silicon behaviour and the fwtest exercises it.
- ✓ **function-control resets to 0** and **MASTER_EN is RW**.
- ✓ **the master engine executes a command**: writing `START` auto-clears the START bit
  and advances the CMD status/state field (`0x00480000`) — the state machine runs.
- ✓ **address probe ACK/NAK is faithful**: a bare `addr+W` START of the EEPROM at
  bus 0 / 0x50 sets **TX_ACK** (I2CD10[0]); an unused address (0x55) sets **TX_NAK**
  (I2CD10[1]) — exactly what silicon reports (datasheet §31.5) and what an i2cdetect-style
  probe sees. **Prerequisite (the earlier "gap"):** the ACK/NAK interrupts must be *enabled*
  in I2CD0C first. This is the **datasheet-documented** master-transmit sequence
  (`DATASHEET-I2C.md` §4.1 init + §4.3 worked example: write `I2CD10=0xFFFFFFFF`, then `I2CD0C=0x000000BF` to
  enable, *then* poll `I2CD10`), and real firmware (Linux `i2c-aspeed`, U-Boot `ast_i2c`,
  the Avocent vendor driver, i2cdetect's kernel driver) always does it. QEMU's old-mode
  model masks I2CD10 by the I2CD0C enable (`aspeed_i2c_bus_raise_interrupt`,
  `intr_sts &= intr_ctrl_mask` in non-packet mode), so a probe that leaves I2CD0C=0 sees
  nothing. The fwtest now enables them like firmware, so the ACK surfaces. **No model
  change was needed — the engine was already faithful; the earlier fwtest simply skipped
  the interrupt-enable step firmware performs.**

### 2.1 What device is at bus 0 / 0x50 — faithfulness boundary

The `kgpe-d16-bmc` QEMU machine is **shared** by both faithfulness oracles: our OpenBMC
kernel (C2) and the **Dell C410X Avocent vendor firmware** (C4). The EEPROM the probe ACKs
at **bus 0 / 0x50 is a Dell C410X device**, not a KGPE-D16 one: it is the C410X's 32 KB
MAC / board-config store (`dell-c410x-firmware/ANALYSIS.md` §"EEPROM 0x50+ I2C0: MAC
address and board config storage"). The C410X vendor ftgmac driver refuses to bring up
`eth0` without a valid MAC read from it, so the machine seeds it (Avocent OUI `00:e0:81`)
purely for the **C4** oracle (`hw/arm/aspeed.c:kgpe_d16_bmc_i2c_init`).

**Honest finding for the KGPE-D16 board itself:** it has **no separately-attested,
probe-able master-side BMC I2C EEPROM.** The only attested BMC-bus peripheral is the
**W83795G** hwmon at **bus 1 / 0x2f** (Raptor's AST2050 OpenBMC port + coreboot
`devicetree.cb`; modelled here). The motherboard **FRU is populated in software**, not read
from an I2C EEPROM — the project ships a static IPMI FRU blob via
`openbmc/recipes/ipmi/kgpe-d16-fru-populate.bb`, whose own summary is *"Populate the
KGPE-D16 motherboard FRU inventory in QEMU (no EEPROM)"*. DIMM **SPD** EEPROMs exist but sit
behind a **host-side SPD mux** (BMC GPIOF4/F5 `CTL_REQ_SPD_MUX_S1/S0`,
`HW-WIRING-power-sensors.md`), not on a directly-probed BMC master bus. The KGPE-D16 QEMU
DTS therefore declares **no `eeprom@` node** and does not even enable `&i2c0`. We did **not**
invent a KGPE-D16 EEPROM; the test proves the shared **AST2050 I2C *master engine*'s**
probe-ACK/NAK behaviour (the SoC-level fact that is genuinely faithful and common to both
boards) against the one real device the machine carries.

> **Earlier (incorrect) note, retained for history:** a 2026-07-10 pass concluded the
> `smbus_eeprom` "does not ACK a bare probe" and that a full SMBus command sequence was
> required. That was a mis-diagnosis (compounded by a stale prebuilt QEMU): the SMBus
> device *does* ACK the addr+W probe (`smbus_i2c_event` returns 0 for `I2C_START_SEND`),
> and the AST2050 master latches that ACK into I2CD10[0]. The real gap was the missing
> I2CD0C interrupt-enable in the test harness.

**Gap:** the AST2400-based model exposes more I2C engines than the G3's **7** (AST2400
has up to 14); a strictly-faithful G3 machine would present 7. G3 firmware only uses the
buses it declares in the DTS, so this is low-impact; narrowing it is oracle-gated.

## 3. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ reset-hold + register + engine + **address-probe ACK/NAK** (0x50 ACK, 0x55 NAK) |
| 2 | doc (this + `DATASHEET-I2C.md`) | ☑ |
| 3 | QEMU model | ☑ register + master-engine + probe ACK/NAK faithful (no model change needed). Depth gap: full byte-level readback of the seeded MAC via the SMBus command sequence not yet asserted. 7-bus narrowing (vs AST2400's ≤14) oracle-gated. |
| 4 | integration test (`../../integration/test_i2c.py`) | ☑ EEPROM probe-ACK **passes** (was xfail, task #63) |

# LPC host interface — AST2050 driver + faithfulness doc

**Base 0x1E789000.** The host↔BMC interface: **KCS** (IPMI Keyboard-Controller-Style
channels), **BT** (Block Transfer), SuperIO, and the **iLPC2AHB** bridge (host reaches
the BMC AHB — the culvert `ilpc` path). Full detail: **[`DATASHEET-LPC.md`](DATASHEET-LPC.md)**.

## 1. G3 register layout (datasheet §)

| Group | Offsets | Notes |
|---|---|---|
| KCS IDR1-3 (data-in) | 0x24 / 0x28 / 0x2C | H8S/2168-compatible |
| KCS ODR1-3 (data-out) | 0x30 / 0x34 / 0x38 | |
| KCS STR1-3 (status) | 0x3C / 0x40 / 0x44 | OBF/IBF/C-D bits |
| BT | 0x48–0x68 | BTCR ctrl @0x58, BTDTR data @0x5C |
| iLPC2AHB | HICR5-8 @0x80–0x8C | `ENL2H` + HWMBASE/ADRBASE/ADRMASK |

OpenBMC: IPMI KCS/BT drivers + port-80h POST-code snoop.

## 2. QEMU faithfulness — WRONG LAYOUT

`peripherals/lpc/fwtest.c` observations: the G3 KCS/BT/iLPC2AHB offsets (0x24–0x8C)
read **0**. The LPC MMIO region *does* respond (QEMU `aspeed_lpc`), but that model puts
**KCS/iBT at the AST2400 `0x140` offsets**, so the G3 KCS/BT are **not** at 0x24–0x68,
and `0x80` is an AST2400 HICR (not the G3 iLPC2AHB `ENL2H`). So OpenBMC's IPMI KCS/BT and
the culvert `ilpc` bridge are **not faithfully addressable** on this machine.

## 3. Faithful-model plan (oracle-gated)

A G3 `aspeed.lpc-ast2050`: KCS IDR/ODR/STR at 0x24–0x44, BT at 0x48–0x68, iLPC2AHB
(HICR5-8) at 0x80–0x8C bridging host LPC reads/writes to the BMC AHB. Coordinate with
the AST2400 aspeed_lpc so the legacy boots (which use the AST2400 layout, if at all) stay
green — oracle-gated.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ observes the G3 offsets (unmodelled) |
| 2 | doc (this + `DATASHEET-LPC.md`) | ☑ |
| 3 | QEMU model | ☐ G3 KCS/BT/iLPC2AHB layout (aspeed_lpc uses AST2400 0x140) |
| 4 | integration test (`../../integration/test_lpc.py`) | ◐ region present; G3-layout xfail |

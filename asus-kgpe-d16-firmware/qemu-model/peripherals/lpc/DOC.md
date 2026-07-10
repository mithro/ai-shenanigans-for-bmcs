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

## 2. QEMU faithfulness — G3 LAYOUT MODELLED (register-accurate)

**Fixed 2026-07-10.** A G3-only `aspeed.lpc-ast2050` device replaces the AST2400
`aspeed_lpc` for the AST2050 SoC (gated on `silicon_rev == AST2050_A1_SILICON_REV`,
mapped at 0x1E789000). It presents the **G3 register layout** — HICR0-4, LADR,
KCS IDR/ODR/STR (0x24-0x44), BT (0x48-0x68), SERIRQ, iLPC2AHB HICR5-8 (0x80-0x8C),
snoop — with datasheet resets. Config registers (HICR/…) are RW; KCS status
registers (STR1-3) are read-only (reset 0). `test_g3_lpc_layout` now PASSES
(`str1.reset`, `hicr0.rw`, the iLPC2AHB `hicr5.rw`), proving the KCS/BT/iLPC2AHB
registers are addressable at the G3 offsets, **not** the AST2400 0x140.

Refinements (documented, not yet modelled): the full KCS/BT OBF/IBF state machines
and the iLPC2AHB→AHB bridging (the culvert `ilpc` data path). There is no LPC host
in this machine, so the registers are the observable surface. C1–C5 boots stay
green (C2 re-verified; the vendor firmware's KCS pokes hit the register model).

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
| 3 | QEMU model | ◐ **G3 register layout modelled** (`aspeed.lpc-ast2050`, ☑); KCS/BT state machines + iLPC2AHB bridging still ☐ |
| 4 | integration test (`../../integration/test_lpc.py`) | ☑ `str1.reset` + `hicr0.rw` + `hicr5.rw` PASS |

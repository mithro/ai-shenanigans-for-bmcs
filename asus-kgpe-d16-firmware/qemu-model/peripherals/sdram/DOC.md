# SDRAM controller (DDR2) — AST2050 driver + faithfulness doc

**Base 0x1E6E0000.** The AST2050 memory controller is **DDR2** — not the AST2400/G4
DDR3 that stock QEMU `aspeed_sdmc` models. Register file 0x00–0x7C (no ECC block on
G3). Full page-cited reference: **[`DATASHEET-SDRAM.md`](DATASHEET-SDRAM.md)**
(datasheet §17, pp.183–203).

## 1. Key registers (§17)

| Off | Register | Reset | Notes |
|---|---|---|---|
| 0x00 | protection (lock-latch) | 0 (locked) | unlock = write `0xFC600309`; reads **0=locked / 1=unlocked** |
| 0x04 | configuration (MCR04) | **0** | firmware writes it; DDR2 geometry (below) |
| 0x0C | refresh timing | 0 | refresh disabled at reset |
| 0x2C | mode-set / DDR-type | X | DDR vs DDR2 select lives here + MCR30/MCR60 |
| 0x100 | AST2000-compat M-PLL/misc shadow | `0x000000A8` | legacy compat |

**MCR04 config layout (§17 p185–186):** `[1:0]` column bits, **`[3:2]` total capacity
(00 ≤32M / 01 64M / 10 128M / 11 256M)**, `[5:4]` VGA aperture (from SCU70[3:2]),
`[7]` burst length, **`[9:8]` bus width (01 = 16-bit)**, `[10]` auto-precharge,
`[11]` bank count (0=4 / 1=8). **No DDR-type bit** in MCR04. Raptor: `0xD89` =
8-bank/128 MB/10-col, `0x585` = 4-bank/64 MB (`platform.S`).

## 2. Driver notes (U-Boot / firmware)

- **DRAM size is NOT auto-detected** on the AST2050 — no SPD, no strap, no probe.
  Firmware **writes MCR04 from a compile-time constant** for the soldered DRAM, then
  later reads it back to discover geometry. (SCU70 carries only the *VGA aperture*
  size, not total DRAM — datasheet p217–218.)
- DDR2 init (Raptor `platform.S`, `DDR2-INIT-REVERSE-ENGINEERING.md`): unlock MCR00,
  program timing/mode (MCR10/MCR20/…), MRS/EMRS with DDR2 fields (WR, OCD, ODT
  75/150Ω), DLL, then enable refresh + CKE. WL = CL−1T; SSTL18 IO; 12 MHz refresh base.

## 3. QEMU faithfulness — current gaps (fwtest baseline)

`peripherals/sdram/fwtest.c` vs the current DDR3-based `aspeed_sdmc`:

| Check | Golden (G3 DDR2) | Current QEMU | Status |
|---|---|---|---|
| protect reset (0=locked) | 0 | 0 | ✓ |
| unlock (`0xFC600309`→reads 1) | 1 | 1 | ✓ |
| refresh reset | 0 | 0 | ✓ |
| **config (MCR04) reset** | **0** | `0x41` (DDR3 synth) | ✗ |
| **config write stored verbatim** | `0xD89` | `0x5c1` (recomputed) | ✗ |
| **MCR100 compat shadow** | `0xA8` | `0` (unmodelled) | ✗ |

Root cause: `aspeed_sdmc` (a) **synthesises MCR04 from the machine RAM size** using
the **DDR3/AST2400 encoding** and pre-fills it at reset (real HW resets 0), (b)
**recomputes** MCR04 on write instead of storing the value, and (c) does not model
the AST2000-compat shadow at 0x100.

## 4. Faithful-model plan — **gated on the C1–C4 boot check**

A **`aspeed.sdmc-ast2050`** DDR2 variant:
- MCR04 resets **0**; stores the written value **verbatim** (no recompute); DDR2
  `[3:2]/[9:8]/[11]` geometry decode.
- MCR100 reads `0x000000A8`.
- Keep protect (`0xFC600309`) + lock-latch read-back (already correct).

**Risk:** MCR04 feeds U-Boot's DRAM sizing. Resetting it to 0 / changing the encoding
could break the flash/U-Boot boot path (the from-source and vendor stacks). So this
change lands **only after** the CI `d16-qemu-stack` C1–C4 boot jobs confirm the
current SCU+VIC changes are green, and is itself re-validated by the next CI boot
run. Until then the three gaps are `xfail` in the integration test — tracked, not
hidden.

## 5. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ 6 checks (3 pass, 3 documented gaps) |
| 2 | doc (this + `DATASHEET-SDRAM.md`) | ☑ |
| 3 | QEMU model (`aspeed.sdmc-ast2050`) | ☐ §4 (gated on boot check) |
| 4 | integration test (`../../integration/test_sdram.py`) | ◐ 3 assert, 3 xfail until §4 |

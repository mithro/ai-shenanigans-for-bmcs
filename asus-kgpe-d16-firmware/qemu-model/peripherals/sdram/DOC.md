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

## 3. QEMU faithfulness — gaps closed by `aspeed.sdmc-ast2050`

`peripherals/sdram/fwtest.c` vs the faithful DDR2 model (all checks now PASS):

| Check | Golden (G3 DDR2) | DDR3 `aspeed_sdmc` (old) | `aspeed.sdmc-ast2050` |
|---|---|---|---|
| protect reset (0=locked) | 0 | 0 ✓ | 0 ✓ |
| unlock (`0xFC600309`→reads 1) | 1 | 1 ✓ | 1 ✓ |
| refresh reset | 0 | 0 ✓ | 0 ✓ |
| **config (MCR04) reset** | **0** | `0x41` (DDR3 synth) ✗ | **0 ✓** |
| **config write stored verbatim** | `0x585` | `0x5c1` (recomputed) ✗ | **`0x585` ✓** |
| **MCR100 compat shadow** | `0xA8` | `0` (unmodelled) ✗ | **`0xA8` ✓** |
| geom decode (cap/width/bank) | 64 MB / 16-bit / 4-bank | — | **64 MB / 16-bit / 4-bank ✓** |

Root cause the DDR2 model fixes: the DDR3 `aspeed_sdmc` (a) **synthesised MCR04 from
the machine RAM size** using the **DDR3/AST2400 encoding** and pre-filled it at reset
(real HW resets 0), (b) **recomputed** MCR04 on write instead of storing the value,
and (c) did not model the AST2000-compat shadow at 0x100.

## 4. Faithful model — landed (`aspeed.sdmc-ast2050`)

Implemented in the QEMU fork (`hw/misc/aspeed_sdmc.c`, `TYPE_ASPEED_2050_SDMC`),
wired into the G3 SoC in `hw/arm/aspeed_ast2400.c` gated on the AST2050 silicon rev
(the same pattern as the G3 SCU/VIC/RTC):
- MCR04 resets **0**; stored **verbatim** on write (no recompute, no ram_size
  synthesis); read back to discover the DDR2 `[3:2]/[9:8]/[11]` geometry.
- MCR100 reads `0x000000A8`; MCR170 reads `0` (both read-only, datasheet p201).
- Protect (`0xFC600309`) + 1-bit lock-latch read-back preserved; resets locked.
- No DDR3 PHY block populated at reset.

MCR04[6] (read-only bus-width status decoded from [9:8] in the datasheet) is **not**
mirrored: MCR04 is a plain RW latch so a read-back equals the firmware-written value
(0x585), matching the only value captured on real silicon (JTAG). A bit6 mirror would
make the read-back 0x5C5, for which there is no capture — flagged in the model source.

**Risk that was retired:** MCR04 feeds U-Boot/firmware DRAM sizing, so resetting it to
0 could have broken the boot path. Verified green: the C2 (from-source kernel → SSH)
and C4 (Dell C410X vendor firmware → BMC web) boots both still pass with the DDR2
model wired — the vendor init writes the SDMC directly, so C4 is the real oracle.

## 5. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ 9 checks, all pass (6 baseline + 3 geometry) |
| 2 | doc (this + `DATASHEET-SDRAM.md`) | ☑ |
| 3 | QEMU model (`aspeed.sdmc-ast2050`) | ☑ landed + SoC-wired (§4) |
| 4 | integration test (`../../integration/test_sdram.py`) | ☑ 9 assert, 0 xfail |

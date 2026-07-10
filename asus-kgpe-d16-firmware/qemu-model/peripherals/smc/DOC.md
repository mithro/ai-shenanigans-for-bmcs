# SMC (SPI flash controller) — AST2050 driver + faithfulness doc

**Control regs 0x16000000; flash data mapped at 0x10000000 (CE0) / 0x12000000 (CE1)
/ 0x14000000 (CE2).** The **legacy SMC** (datasheet §11) — *not* the AST2400 FMC at
0x1E620000 (data 0x20000000) that mainline QEMU's `aspeed_smc` models. Full detail:
**[`DATASHEET-SMC.md`](DATASHEET-SMC.md)**. We boot from RAM (netboot) so the flash
controller is only probed, but a faithful G3 must present it.

## 1. Registers

| Off | Register | Reset | Notes |
|---|---|---|---|
| 0x00 | config (CE type + segment) | `0x00000240` | CE0=NOR/CE1=NAND/CE2=SPI, 32 MB |
| 0x04/0x08/0x0C | per-CE control | | SPI: `[10:8]` clk HCLK/16, `[5]` MSB-first, `[1:0]` cmd-mode |
| 0x10–0x1C | misc / NAND ECC | | |

Boot CE is aliased to `0x0` until the AHBC address-remap (`0x1E60008C`). The AST2050
is **SPI-only** in practice, though the register set is a NOR/NAND/SPI superset.

## 2. QEMU faithfulness — UNMODELLED

`peripherals/smc/fwtest.c` vs the current model — **all checks FAIL**: `0x16000000`
reads 0 (not the `0x240` reset), and the flash data window `0x10000000` reads 0 (not
mapped). Mainline QEMU models only the **FMC (0x1E620000)**; the **legacy SMC
(0x16000000) is not modelled** (the machine's "tolerate unmodelled MMIO → 0" flag
returns 0). The current boots load the flash via the FMC / `-drive if=mtd`, so this gap
does **not** affect them.

## 3. Faithful-model plan (oracle-gated, larger change)

Add an `aspeed.smc-ast2050` legacy-SMC device: config `0x240` + per-CE control at
`0x16000000`, and map the SPI flash data at `0x10000000` (CE0) with the boot alias to
`0x0` pre-remap. This is a new device + a flash-mapping change; it must keep the C1–C4
boots green (which currently use the FMC path), so it is oracle-gated and coordinated
with the AHBC remap model.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ (documents the unmodelled legacy SMC) |
| 2 | doc (this + `DATASHEET-SMC.md`) | ☑ |
| 3 | QEMU model | ☐ new `aspeed.smc-ast2050` + flash map (§3, oracle-gated) |
| 4 | integration test (`../../integration/test_smc.py`) | ◐ checks xfail until §3 |

# AHB controller — AST2050 driver + faithfulness doc

**Base 0x1E600000** (Raptor `hwreg.h`: protection key 0x00, priority ctrl 0x80,
interrupt ctrl 0x88, **address remap 0x8C**). The AHB controller arbitrates the AHB
bus and owns the boot **address remap** — at reset address 0x0 aliases the boot
flash; firmware programs the remap so 0x0 maps to DRAM. *(Its own datasheet chapter
is not yet extracted — register golden values are pending; the base/offsets are from
`hwreg.h`.)*

## 1. QEMU faithfulness — UNMODELLED (but not boot-blocking)

`peripherals/ahb/fwtest.c` (observations): `0x1E600000` (prot / priority / interrupt
/ remap) all read **0** and writes are ignored — the AHB controller is **not modelled**
(the machine's "tolerate unmodelled MMIO → 0" flag).

**Why this is OK for now:** QEMU maps DRAM at `0x0` directly via the machine memory
layout (`arm_load_kernel` / the SoC memmap), so the guest sees the post-remap address
space without programming the AHBC remap register. The legacy boots don't depend on the
AHBC being present, so leaving it unmodelled keeps the oracle green. A strictly-faithful
model would present the remap register (and honor the 0x0↔flash/DRAM aliasing across the
remap write) — needed only if firmware reads the AHBC back.

## 2. Faithful-model plan (low priority, oracle-safe)

Extract the AHB chapter; add an `aspeed.ahbc-ast2050` device with the protection key,
priority, and remap registers, and (optionally) model the 0x0 aliasing so a bare-metal
remap test passes. Low priority since the boot address space is already correct.

## 3. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ probe (documents the unmodelled block) |
| 2 | doc (this) | ◐ base/offsets from hwreg.h; datasheet chapter TBD |
| 3 | QEMU model | ☐ unmodelled (not boot-blocking; §2) |
| 4 | integration test (`../../integration/test_ahb.py`) | ☑ (halt only; behaviour is observation) |

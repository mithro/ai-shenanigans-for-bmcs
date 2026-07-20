# Zephyr AST2050 / KGPE-D16 port — actionable plan (D14)

**Feasibility: SETTLED, tractable.** Zephyr gained ARM926EJ-S (ARMv5TEJ)
support via Microchip's SAM9X7 work. This plan is derived from the actual
upstream artifacts (verified 2026-07-18): the Kconfig scaffolding is merged in
`main` (PR #101016), and the ARM9 arch core + a working ARM926 SoC/board
precedent are in **open PR #103557** (`TonyHan11/zephyr:arm9_4_sam9x7`).

## Where the pieces are (verified)

- **Arch core** — the PR folds ARM9 into the existing AArch32 core:
  `arch/arm/core/cortex_a_r/{reset,switch,exc,isr_wrapper,vector_table}.S`,
  `thread.c`, `swap_helper.S`. `arch/arm/core/arm9/Kconfig` (the merged
  scaffolding) selects `CPU_ARM926EJ_S → ARMV5TEJ`, `-mcpu=arm926ej-s`
  (`cmake/gcc-m-cpu.cmake`), `CPU_HAS_MMU`. **We reuse this verbatim — do not
  author an arch port.**
- **Linker** — `include/zephyr/arch/arm/cortex_a_r/scripts/linker.ld`
  (set as `SOC_LINKER_SCRIPT` by the SoC CMakeLists).
- **SoC precedent** — `soc/microchip/sam/sam9/sam9x7/{Kconfig.soc,
  Kconfig.defconfig,soc.c,soc.h,CMakeLists.txt}` + `soc/microchip/sam/sam9/
  {soc.yml,Kconfig.soc,CMakeLists.txt}`. The SoC CMakeLists points
  SOC_LINKER_SCRIPT at the cortex_a_r linker.
- **Board precedent** — `boards/microchip/sam/sam9x75_curiosity/{board.yml,
  *.dts,*_defconfig,Kconfig.*,*.yaml}`.
- **Console** — Zephyr's existing `drivers/serial/uart_ns16550.c` fits the
  AST2050 UART directly (NS16550-compatible) → **no new console driver**.
- Local checkout + fetched PR: the research clone is at
  `<scratchpad>/zephyr` with branch `pr103557`; SDK at
  `/home/tim/zephyr-sdk-0.17.0` (`arm-zephyr-eabi`).

## AST2050 hardware facts for the port (from this repo's RE)

| Item | Value |
|---|---|
| Core | ARM926EJ-S (ARMv5TEJ), MMU (not MPU) |
| DRAM | 0x40000000, 64 MB (SDMC; MCR04=0x585) |
| UART console | 0x1e784000 (ttyS4/UART2, NS16550, 115200) |
| Interrupt controller | compact VIC @ 0x1e6c0000 (NOT the AST2400 0x1e6c0080 map) — `ARM_CUSTOM_INTERRUPT_CONTROLLER` + `GEN_ISR_TABLES` |
| Timer | 0x1e782000 (aspeed timer) |
| SCU | 0x1e6e2000 |
| Ref clock | 24 MHz |
| HW strap (SCU70) | 0x00819582 (measured) |

## Files to create (out-of-tree, or upstream layout mirrored here)

Mirror the sam9x7 structure under a new vendor `aspeed`:
- `soc/aspeed_g3/ast2050/{Kconfig.soc,Kconfig.defconfig,soc.c,soc.h,CMakeLists.txt}`
  + `soc/aspeed_g3/{soc.yml,Kconfig.soc,CMakeLists.txt}` — `SOC_ASPEED_AST2050`
  selects `CPU_ARM926EJ_S`; CMakeLists sets `SOC_LINKER_SCRIPT` = the
  cortex_a_r linker; `soc.c` does minimal early init (MMU/caches off first).
- `boards/aspeed/kgpe_d16_bmc/{board.yml, kgpe_d16_bmc.dts,
  kgpe_d16_bmc_defconfig, Kconfig.kgpe_d16_bmc, kgpe_d16_bmc.yaml}` — DTS with
  cpu@0 `arm,arm926ej-s`, `memory@40000000` (64 MB), `serial@1e784000`
  (ns16550, `chosen { zephyr,console }`), and (Milestone 1) `intc@1e6c0000`.

## Milestone ladder (each a real, testable deliverable)

- **M0 — banner in QEMU.** MMU/caches off, `CONFIG_SYS_CLOCK_EXISTS=n`,
  interrupts off; build `samples/hello_world` for `kgpe_d16_bmc`; run under the
  repo's faithful `qemu-system-arm -M kgpe-d16-bmc`
  (`-kernel zephyr.elf`). Reset → prep_c → arch_switch → main → NS16550
  banner. Proves the whole arch core end-to-end.
- **M1 — preemptive kernel.** Add a VIC intc driver for 0x1e6c0000
  (`ARM_CUSTOM_INTERRUPT_CONTROLLER`, model on
  `drivers/interrupt_controller/intc_mchp_aic_g1.c`) + an aspeed system-timer
  driver (0x1e782000). Result: scheduler tick + `samples/synchronization` +
  the shell.
- **M2 — silicon.** JTAG-load `zephyr.bin` into trained DRAM via the same
  `openocd/boot-silicon-uboot.sh` 3-step chain (reset→train→load→PC), banner
  on the real UART. Then per-device Zephyr drivers (gpio/i2c/wdt/eth), each
  validated QEMU then silicon per DEVICE-MATRIX.md.

## Build approach

A `build.sh` will: create a west workspace pinned to Zephyr `main` + cherry
PR #103557 (or use the branch directly), point `BOARD_ROOT`/`SOC_ROOT` at this
dir, `west build -b kgpe_d16_bmc samples/hello_world` with the
`/home/tim/zephyr-sdk-0.17.0` toolchain, then boot the ELF under the repo QEMU.

## Status

**D14 FOUNDATION LAID (2026-07-18):** feasibility settled, upstream artifacts
identified + PR fetched, memory map + file structure + milestone ladder fixed.
**Next: author the SoC/board files (M0) and get the banner in QEMU.** This is
the honest state — no Zephyr driver is validated yet; the whole ZQ/ZS column
in DEVICE-MATRIX.md remains ⬜ until M0 lands.

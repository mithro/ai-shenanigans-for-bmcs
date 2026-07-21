# ASUS KGPE-D16 — AST2050 BMC open-firmware work

The ASUS KGP(M)E-D16 is a dual-socket AMD Opteron server board whose BMC is an
**Aspeed AST2050** (G3 generation, ARM926EJ-S, 64 MB DDR2). This directory is
the **source of truth for all SoC-level AST2050 work** in the repo: the other
Aspeed board (`../dell-c410x-firmware/`) reuses the kernel/U-Boot/QEMU work done
here and adds only its own board specifics (see
[`../dell-c410x-firmware/REUSING-KGPE-D16-WORK.md`](../dell-c410x-firmware/REUSING-KGPE-D16-WORK.md)).

Unlike the C410X (which runs vendor firmware), this board's BMC arrived with
**no functional firmware**, so everything here is built around getting our own
code onto a dead-firmware AST2050 — first over the P2A (PCIe-to-AHB) back-door,
then JTAG, then a full Linux/OpenBMC boot chain.

There is no `STATUS.md` here; start with
[`RAPTOR_AST2050_SUMMARY.md`](RAPTOR_AST2050_SUMMARY.md).

## Document map

### Raptor Engineering analysis (the porting baseline)

Raptor Engineering shipped the only known working open Linux port for the
AST2050 (kernel 2.6.28.9 + U-Boot). These documents reverse-engineer it as the
baseline for a mainline port:

- [`RAPTOR_AST2050_SUMMARY.md`](RAPTOR_AST2050_SUMMARY.md) — quick-reference entry point.
- [`RAPTOR-PORTING-GUIDE.md`](RAPTOR-PORTING-GUIDE.md) — the actionable
  Raptor→mainline mapping (26 components).
- [`RAPTOR_ENGINEERING_AST2050_ANALYSIS.md`](RAPTOR_ENGINEERING_AST2050_ANALYSIS.md)
  — full kernel/U-Boot modification detail behind the guide.
- [`RAPTOR-UBOOT-ANALYSIS.md`](RAPTOR-UBOOT-ANALYSIS.md) /
  [`RAPTOR-UBOOT-BUILD.md`](RAPTOR-UBOOT-BUILD.md) — U-Boot internals, and how
  to build it for P2A boot.
- [`DDR2-INIT-REVERSE-ENGINEERING.md`](DDR2-INIT-REVERSE-ENGINEERING.md) —
  line-by-line RE of the DDR2 SDRAM controller init.
- `ast2050.h` / `hwreg.h` / `platform.S` / `platform-ast2100-ya-mouse.S` —
  register definitions and DRAM-init assembly extracted from Raptor's tree.

### Booting the dead BMC (P2A boot chain)

Read in order — each continues the previous:

1. [`CULVERT-BMC-ACCESS.md`](CULVERT-BMC-ACCESS.md) — reaching the AST2050
   in-band from the x86 host with culvert (P2A/AHB back-door).
2. [`P2A-DRAM-BOOT-SEQUENCE.md`](P2A-DRAM-BOOT-SEQUENCE.md) — starting the ARM
   from DRAM over P2A (load → remap → release).
3. [`RAPTOR-UBOOT-BUILD.md`](RAPTOR-UBOOT-BUILD.md) — building the U-Boot image
   that boot chain loads.
4. [`LINUX-TFTP-BOOT.md`](LINUX-TFTP-BOOT.md) — TFTP-booting Linux from that
   U-Boot to a root shell (no SPI flash or JTAG needed).

Supporting docs and tools:

- [`CULVERT-G3-HARDWARE-RESULTS.md`](CULVERT-G3-HARDWARE-RESULTS.md) —
  hardware-verified results of the culvert AST2050 (G3) port.
- [`CULVERT-UART-JTAG-DEBUG.md`](CULVERT-UART-JTAG-DEBUG.md) — culvert's
  Debug-UART/software-JTAG analysis (and why the AST2050 lacks the UART
  debug shell — see [`../datasheets/README.md`](../datasheets/README.md)).
- `culvert/` — **git submodule**: [mithro/culvert](https://github.com/mithro/culvert)
  branch `ast2050-support`. `culvert-arm/` holds meson cross files for building
  a musl-static ARM culvert that runs *on* the BMC.
- `arm-stub/` — minimal UART-hello ARM stub + `boot-p2a.py` for first-code-on-core
  experiments. `bmc-uart-p2a.py`, `ddr2-init-p2a.py`, `remap-test-p2a.py`,
  `p2a-image-boot.py`, `uboot-console.py`, `linux-boot.py` — the P2A boot
  tooling (PEP 723 scripts; run with `uv run`).

### Kernel: mainline port status

- [`MODERN-KERNEL-STATUS.md`](MODERN-KERNEL-STATUS.md) — modern Linux (6.6.x)
  on the real AST2050: what works, what's patched.
- [`TIMER-CLOCKEVENT-ROOT-CAUSE.md`](TIMER-CLOCKEVENT-ROOT-CAUSE.md) — root
  cause of the timer clockevent hang that masqueraded as a NIC bug.
- [`NIC-MAC-REGISTER-COMPARISON.md`](NIC-MAC-REGISTER-COMPARISON.md) — U-Boot
  (working) vs Linux (broken) ftgmac100 register-level comparison.
- `kernel/` — `kgpe-d16-realhw.config` + `patches/` for the real-hardware
  kernel; built by `build-realhw-kernel.py`, initramfs by
  `build-bmc-initramfs.py`.
- `dts/` — device trees: `aspeed-bmc-asus-kgpe-d16-realhw.dts` (real hardware)
  and `kgpe-d16-g3vic.dts` (G3 VIC variant).
- `nfsroot/` — minimal init files for NFS-root boots;
  `openbmc-qemu/` — scripts to stage/run an OpenBMC NFS root (QEMU and real HW).

### JTAG (second access path)

- [`JTAG-HEADERS.md`](JTAG-HEADERS.md) — the two unpopulated JTAG headers.
- [`HEADER-PINOUTS.md`](HEADER-PINOUTS.md) — physical pinout diagrams.
- [`RPI4-OPENOCD-JTAG-WIRING.md`](RPI4-OPENOCD-JTAG-WIRING.md) — wiring a
  Raspberry Pi 4B as the OpenOCD adapter.
- [`JTAG-USAGE-GUIDE.md`](JTAG-USAGE-GUIDE.md) — operational guide (halt,
  memory access over JTAG).
- `openocd/` — the OpenOCD configs (`ast2050.cfg`, `kgpe-d16-bmc.cfg`,
  `rpi4-jtag.cfg`) plus `ddr2-init.tcl` and bring-up scripts.

### Host (x86) side: BIOS and netboot

- [`HARDWARE-ACCESS.md`](HARDWARE-ACCESS.md) — operational reference for
  driving the rig (power, serial, video capture).
- [`BIOS-SERIAL-CONSOLE-BRINGUP.md`](BIOS-SERIAL-CONSOLE-BRINGUP.md) — driving
  the AMIBIOS setup menu over serial via an emulated USB keyboard.
- [`BIOS-CONFIG-WITHOUT-MENU.md`](BIOS-CONFIG-WITHOUT-MENU.md) — changing BIOS
  settings by editing CMOS directly; tooling in `bios-cmos/`
  (`bios_cmos.py` + decoded `cmos_map.json`).
- [`HOST-NETBOOT.md`](HOST-NETBOOT.md) — PXE-booting the x86 host into a rescue
  Linux over the RPi bridge.
- `amibcp/` — AMIBCP screenshots of the BIOS ROM's option tables (see its README).
- `backup/` — the original AMI BIOS 3309 ROM dump (irreplaceable source material).
- `hardware-inventory/` — captured `dmidecode`/`lspci`/`dmesg`/… output from
  the running host.
- `rig/` / `rig-tools/` — systemd units, udev rules, and serial/video helper
  daemons for the RPi-based test rig.

### QEMU model

- `qemu-firmware/` — the custom-QEMU firmware stack: a faithful `kgpe-d16-bmc`
  AST2050 machine model (submodule [mithro/qemu](https://github.com/mithro/qemu)
  branch `d16-ast2050-machine`), its kernel/dts/initramfs build inputs, and
  `AST2050-PERIPHERAL-MODELING.md` + `PLAN.md`. Legacy/proprietary firmware is
  the faithfulness oracle: the vendor images must always keep booting.

### Reference

- `datasheets/` — board-specific datasheets (AST2050, AMD SR5690/SP5100
  chipset, W83795G hwmon, SPI-NOR flash, …) with `download_datasheets.py`.
  Shared Aspeed-generation datasheets live in [`../datasheets/`](../datasheets/).
- `uboot-patches/` — patches on Raptor U-Boot for the P2A DRAM boot.

## Conventions

All Python here is PEP 723 self-contained; run any script as
`uv run asus-kgpe-d16-firmware/<script>.py`. Every factual claim in the docs
carries evidence (register offset, datasheet section, or captured command
output) — match that standard when editing.

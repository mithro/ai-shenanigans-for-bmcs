# ai-shenanigans-for-bmcs

Docs, reverse engineering notes, and other assets for replacing the
proprietary BMC firmware on boards using the Aspeed AST2050 (also sold
as AST1100) with open-source alternatives (OpenBMC / u-bmc). Generated
with assistance from Claude Code / claude.ai.

See [`resources.md`](resources.md) for the full project context, and
[`CLAUDE.md`](CLAUDE.md) for repository-specific guidance.

## The Aspeed AST2050

The AST2050 is an older Aspeed BMC SoC with an ARM926EJ-S CPU at
200 MHz. It is **not supported in mainline Linux** -- the earliest
supported generation is the AST2400 (G4). Adding AST2050 support
requires creating a new device tree include (`aspeed-g3.dtsi`) and
adding `aspeed,ast2050-*` compatible strings to the existing mainline
Aspeed drivers.

The SoC-level kernel work is shared across all boards using the AST2050.
Each board then needs its own device tree describing the specific I2C
topology, GPIO wiring, sensors, and peripherals.

## Board Directories

### [`asus-kgpe-d16-firmware/`](asus-kgpe-d16-firmware/)

Analysis of [Raptor Engineering's](https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php)
work porting OpenBMC to the ASUS KGPE-D16 server motherboard (AST2050).
Raptor created a working Linux 2.6.28.9 kernel with full AST2050
driver support, archived in 2018. This is the starting point for
adding AST2050 support to the modern mainline kernel.

Key files:
- [`RAPTOR-PORTING-GUIDE.md`](asus-kgpe-d16-firmware/RAPTOR-PORTING-GUIDE.md) --
  Every change from Raptor's kernel mapped to the corresponding mainline
  subsystem, with specific porting actions for each of 26 components.
- [`RAPTOR_ENGINEERING_AST2050_ANALYSIS.md`](asus-kgpe-d16-firmware/RAPTOR_ENGINEERING_AST2050_ANALYSIS.md) --
  Detailed analysis of Raptor's repositories (kernel, U-Boot, Yocto/OpenBMC).
- [`RAPTOR_AST2050_SUMMARY.md`](asus-kgpe-d16-firmware/RAPTOR_AST2050_SUMMARY.md) --
  Quick reference summary.
- [`ASUS-KCMA-D8.md`](asus-kgpe-d16-firmware/ASUS-KCMA-D8.md) --
  Board reference for the ASUS KCMA-D8, the KGPE-D16's Socket-C32 sibling
  (same chipset and the same AST2050 BMC on an ASMB4/ASMB5 module), mirrored
  from the 15h.org wiki; every PDF that page links is committed in
  [`datasheets/`](asus-kgpe-d16-firmware/datasheets/) (see
  [`15H-ORG-MIRROR.md`](asus-kgpe-d16-firmware/datasheets/15H-ORG-MIRROR.md)).
- [`RAPTOR-UBOOT-ANALYSIS.md`](asus-kgpe-d16-firmware/RAPTOR-UBOOT-ANALYSIS.md) --
  Analysis of Raptor's U-Boot port and board bring-up.
- [`DDR2-INIT-REVERSE-ENGINEERING.md`](asus-kgpe-d16-firmware/DDR2-INIT-REVERSE-ENGINEERING.md) --
  Reverse engineering of the DDR2 memory controller initialisation sequence.
- [`JTAG-HEADERS.md`](asus-kgpe-d16-firmware/JTAG-HEADERS.md) --
  Documentation of both unpopulated JTAG debug headers: the BMC JTAG
  (AST_JTAG1) and the AMD HDT CPU debug connector, including pinouts,
  signal descriptions, and compatible debug probes.
- [`RPI4-OPENOCD-JTAG-WIRING.md`](asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md) --
  How to wire a Raspberry Pi 4B as an OpenOCD JTAG adapter (plus UART console
  and SPI flashing) to the AST2050 BMC debug headers, with Raptor-verified
  OpenOCD configs in `openocd/`.
- [`HEADER-PINOUTS.md`](asus-kgpe-d16-firmware/HEADER-PINOUTS.md) --
  Per-header pinout diagrams (AST_JTAG1, AST_UART1, BMC_FW1, ...) with
  verification status and an unknown-header probing procedure.
- [`ast2050.h`](asus-kgpe-d16-firmware/ast2050.h),
  [`hwreg.h`](asus-kgpe-d16-firmware/hwreg.h),
  [`platform.S`](asus-kgpe-d16-firmware/platform.S), and
  [`platform-ast2100-ya-mouse.S`](asus-kgpe-d16-firmware/platform-ast2100-ya-mouse.S) --
  Register definitions and low-level platform init assembly.

### [`dell-c410x-firmware/`](dell-c410x-firmware/)

Reverse engineering of the Dell PowerEdge C410X BMC firmware (AST2050).
The C410X is a 3U, 16-slot PCIe GPU expansion chassis (not a server)
managed entirely by its BMC. The proprietary Avocent MergePoint firmware
(v1.35) has been fully analysed.

Key files:
- [`aspeed-bmc-dell-c410x.dts`](dell-c410x-firmware/aspeed-bmc-dell-c410x.dts) --
  Complete Linux device tree, reverse-engineered from firmware binaries.
- [`ANALYSIS.md`](dell-c410x-firmware/ANALYSIS.md) -- Full firmware reverse
  engineering (hardware, drivers, I2C topology, IPMI sensors, boot sequence).
- [`STATUS.md`](dell-c410x-firmware/STATUS.md) -- Current state and open items.
- [`REUSING-KGPE-D16-WORK.md`](dell-c410x-firmware/REUSING-KGPE-D16-WORK.md) --
  How to apply the KGPE-D16 kernel porting work to the C410X (shared SoC
  drivers, board-specific DTS).
- [`aspeed-mainline-drivers-analysis.md`](dell-c410x-firmware/aspeed-mainline-drivers-analysis.md)
  and [`aspeed-driver-quick-reference.md`](dell-c410x-firmware/aspeed-driver-quick-reference.md) --
  Which mainline Aspeed drivers cover which on-board peripherals.
- [`io-tables/`](dell-c410x-firmware/io-tables/) -- All five binary
  configuration tables decoded (192 hardware devices, 72 IPMI sensors,
  118 GPIO pins).
- [`pex-i2c-analysis/`](dell-c410x-firmware/pex-i2c-analysis/) -- Reverse
  engineering of the I2C commands the BMC sends to the PLX PEX8696/PEX8647
  PCIe switches for GPU slot power, hot-plug, and multi-host control. The
  master reference is
  [`PEX-I2C-COMMANDS.md`](dell-c410x-firmware/pex-i2c-analysis/PEX-I2C-COMMANDS.md).
- [`kernel/`](dell-c410x-firmware/kernel/),
  [`initramfs/`](dell-c410x-firmware/initramfs/), and
  [`tftp_boot.py`](dell-c410x-firmware/tftp_boot.py) -- Kernel config plus
  AST2050 patches, a BusyBox initramfs builder, and a serial/TFTP boot
  harness for running new firmware on real hardware.
- [`datasheets/`](dell-c410x-firmware/datasheets/) -- Component datasheets
  for all major ICs on the board.

### [`hpe-ipdu-firmware/`](hpe-ipdu-firmware/)

Analysis of the HPE Intelligent Modular PDU (iPDU, model AF531A) firmware.
Unlike the other boards this uses a Digi NS9360 SoC (ARM926EJ-S) rather
than an Aspeed part, and its stock firmware is **NET+OS** (a ThreadX-based
RTOS), not Linux. Three firmware versions were obtained and
reverse-engineered (Digi `bootHdr` format, LZSS2 decompression, NET+OS /
RomPager internals, web UI, and security posture). An open U-Boot port for
the NS9360 -- the path to open firmware for this board -- now boots under
QEMU and passes a basic smoke test.

Key files:
- [`ANALYSIS.md`](hpe-ipdu-firmware/ANALYSIS.md) -- Board component inventory,
  NS9360 I/O architecture, and firmware internals.
- [`STATUS.md`](hpe-ipdu-firmware/STATUS.md) -- Current state and open items.
- [`RESOURCES.md`](hpe-ipdu-firmware/RESOURCES.md) -- Firmware URLs,
  datasheets, and documentation links.
- [`HEADERS-J1-J6.md`](hpe-ipdu-firmware/HEADERS-J1-J6.md) -- Debug/JTAG
  header documentation.
- [`uboot-port/`](hpe-ipdu-firmware/uboot-port/) -- An open U-Boot port for the
  NS9360 that boots under QEMU:
  - `u-boot/` submodule ([`mithro/u-boot@hpe-ipdu-port`](https://github.com/mithro/u-boot/tree/hpe-ipdu-port)) --
    NS9360 SoC + AF531A board support (serial, GPIO, clock, I2C, Ethernet, CFI
    NOR flash).
  - `qemu/qemu-10.0.7/` submodule ([`mithro/qemu@ns9360-machine`](https://github.com/mithro/qemu/tree/ns9360-machine)) --
    a QEMU `ns9360` machine model (ARM926EJ-S, SDRAM, dual CFI flash) for running
    the port without hardware.
  - [`test/`](hpe-ipdu-firmware/uboot-port/test/) -- `mkflash.py` assembles the
    8 MiB NOR flash image; `qemu_smoke_test.py` boots U-Boot under
    `qemu-system-arm -M ns9360` and checks the prompt, `bdinfo`, SDRAM/flash
    access, GPIO and I2C.
  - Porting plans ([incremental](hpe-ipdu-firmware/uboot-port/PLAN-INCREMENTAL-PORT.md),
    [QEMU-first](hpe-ipdu-firmware/uboot-port/PLAN-FULL-FEATURED-PORT.md)) and
    [reference material](hpe-ipdu-firmware/uboot-port/REFERENCE-MATERIAL.md),
    including Digi's NS9360 U-Boot source.
- Firmware tooling: ~20 Python analysis scripts, including
  [`extract_firmware.py`](hpe-ipdu-firmware/extract_firmware.py) and
  [`decompress_firmware.py`](hpe-ipdu-firmware/decompress_firmware.py)
  (LZSS2), covering ARM disassembly, web-UI extraction, NET+OS / RomPager
  security assessment, and MAXQ3180 / display-MCU / extension-bar protocol
  analysis.

## Hardware access

Two Raspberry Pi 4B **bridges** put the target boards on the network — each
carries the JTAG / UART / SPI-flash / Ethernet harnesses to one board and is
reachable over SSH, so the QEMU-developed firmware can be exercised against real
silicon remotely. [`HARDWARE-ACCESS.md`](HARDWARE-ACCESS.md) documents the
bridge hosts, attached adapters (with MACs), SSH access, remote board-power
control, the live target networks (TFTP/NFS/PXE), and the remaining setup
gaps. The physical wiring for the AST2050 side is in
[`asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md`](asus-kgpe-d16-firmware/RPI4-OPENOCD-JTAG-WIRING.md).

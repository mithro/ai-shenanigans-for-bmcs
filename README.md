# ai-shenanigans-for-bmcs

Docs, reverse engineering notes, and other assets for replacing the
proprietary BMC firmware on boards using the Aspeed AST2050 (also sold
as AST1100) with open-source alternatives (OpenBMC / u-bmc). Generated
with assistance from Claude Code / claude.ai.

## The Aspeed AST2050

The AST2050 is an older Aspeed BMC SoC with an ARM926EJ-S CPU at
200 MHz. It is **not supported in mainline Linux** -- the earliest
supported generation is the AST2400 (G4). Adding AST2050 support
requires creating a new device tree include (`aspeed-g3.dtsi`) and
adding `aspeed,ast2050-*` compatible strings to the existing mainline
Aspeed drivers. See `resources.md` for the full project context.

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
- **`RAPTOR-PORTING-GUIDE.md`** -- Every change from Raptor's kernel
  mapped to the corresponding mainline subsystem, with specific porting
  actions for each of 26 components.
- **`JTAG-HEADERS.md`** -- Documentation of both unpopulated JTAG debug
  headers: the BMC JTAG (AST_JTAG1) and the AMD HDT CPU debug connector,
  including pinouts, signal descriptions, and compatible debug probes.
- `RAPTOR_ENGINEERING_AST2050_ANALYSIS.md` -- Detailed analysis of
  Raptor's repositories (kernel, U-Boot, Yocto/OpenBMC).
- `RAPTOR_AST2050_SUMMARY.md` -- Quick reference summary.

### [`dell-c410x-firmware/`](dell-c410x-firmware/)

Reverse engineering of the Dell PowerEdge C410X BMC firmware (AST2050).
The C410X is a 3U, 16-slot PCIe GPU expansion chassis (not a server)
managed entirely by its BMC. The proprietary Avocent MergePoint firmware
(v1.35) has been fully analysed.

Key files:
- **`aspeed-bmc-dell-c410x.dts`** -- Complete Linux device tree,
  reverse-engineered from firmware binaries.
- **`REUSING-KGPE-D16-WORK.md`** -- How to apply the KGPE-D16 kernel
  porting work to the C410X (shared SoC drivers, board-specific DTS).
- `ANALYSIS.md` -- Full firmware reverse engineering (hardware, drivers,
  I2C topology, IPMI sensors, boot sequence).
- `io-tables/` -- All five binary configuration tables decoded (192
  hardware devices, 72 IPMI sensors, 118 GPIO pins).
- `datasheets/` -- Component datasheets for all major ICs on the board.

### [`hpe-ipdu-firmware/`](hpe-ipdu-firmware/)

Analysis of the HPE Intelligent Power Distribution Unit (iPDU) firmware.

# PEX I2C Analysis

Reverse engineering of the I2C commands that the Dell C410X BMC firmware
(`fullfw` ELF binary) sends to the PLX/Broadcom PEX8696 and PEX8647
PCIe switches.

## Background

The Dell C410X is a 16-slot GPU expansion chassis with an AST2050 BMC
running Avocent MergePoint firmware. The BMC communicates with two types
of PLX PCIe switches over I2C:

- **PEX8696** -- 96-lane primary PCIe switch (I2C addresses 0x18/0x1A/0x19/0x1B)
- **PEX8647** -- 48-lane secondary PCIe switch (upstream/host links)

Both switches are accessed via I2C bus 0xF3 (AST2050 I2C engine 3).

The PLX I2C protocol uses 16-bit register addresses (big-endian) and
32-bit values (little-endian). Reference implementation and register
definitions are available at https://github.com/mithro/plxtools.

## Goal

Produce a complete `PEX-I2C-COMMANDS.md` document that describes every
I2C transaction the BMC firmware performs with the PEX switches, including:

- Register addresses and their names/purpose
- Values written and their meaning
- Sequencing and dependencies between operations
- Functions involved (e.g. `pex8696_slot_power_on`, `pex8696_hp_ctrl`,
  `pex8647_cfg_multi_host_*`)

## Directory Structure

```
pex-i2c-analysis/
  README.md          -- This file
  research/          -- Research notes and reference material
                        (PLX specs, plxtools register definitions, etc.)
  tools/             -- Python scripts and analysis tools
                        (firmware extraction, symbol dumping, decompilation helpers)
  analysis/          -- Raw analysis outputs
                        (symbol tables, decompiled code, Ghidra exports, etc.)
```

## Source Material

The primary source is the `fullfw` ELF binary extracted from the BMC
firmware image at `dell-c410x-firmware/backup/c410xbmc135.zip`. This
is a SquashFS filesystem image containing the Avocent MergePoint firmware.

## References

- [plxtools](https://github.com/mithro/plxtools) -- PLX I2C protocol
  implementation and PEX8696 register definitions
- Dell C410X firmware analysis in `../ANALYSIS.md`
- Dell C410X device tree in `../aspeed-bmc-dell-c410x.dts`

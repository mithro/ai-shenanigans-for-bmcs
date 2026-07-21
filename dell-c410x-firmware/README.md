# Dell PowerEdge C410X — BMC firmware reverse engineering

The Dell PowerEdge C410X is a 3U, 16-slot external PCIe GPU expansion chassis.
It has **no host CPU** — the whole chassis (power sequencing, cooling, PCIe
switch configuration, slot assignment) is managed by its BMC, an **Aspeed
AST2050** running Avocent MergePoint firmware. This directory reverse-engineers
that firmware so the board can run open firmware instead.

SoC-level work (kernel port, U-Boot, QEMU model) is shared with the other
AST2050 board and lives in [`../asus-kgpe-d16-firmware/`](../asus-kgpe-d16-firmware/);
[`REUSING-KGPE-D16-WORK.md`](REUSING-KGPE-D16-WORK.md) explains how it applies
here. This directory contains only what is C410X-specific.

## Start here

- [`STATUS.md`](STATUS.md) — current state and open items.
- [`ANALYSIS.md`](ANALYSIS.md) — the full firmware reverse engineering
  (hardware inventory, drivers, boot flow).
- [`RESOURCES.md`](RESOURCES.md) — firmware download URLs and sources.

## Key outputs

- [`aspeed-bmc-dell-c410x.dts`](aspeed-bmc-dell-c410x.dts) — the
  hand-reconstructed device tree, the directory's central deliverable. Based on
  `aspeed-g4.dtsi` (AST2400) because no upstream G3/AST2050 binding exists and
  the SoCs are register-compatible enough. Validate it against the raw firmware
  with `uv run dell-c410x-firmware/cross_check_dts.py`.
- [`io-tables/`](io-tables/README.md) — decoding of the five binary IO
  configuration tables (`IO/IS/IX/FT_fl.bin`, `oemdef.bin`) that describe the
  board's GPIO/sensor wiring; decoded by `parse_io_tables.py`, mapped in
  `io-tables/gpio-pin-mapping.md`.
- [`pex-i2c-analysis/`](pex-i2c-analysis/README.md) — the PLX PEX8696/PEX8647
  PCIe-switch I2C protocol.
  [`pex-i2c-analysis/PEX-I2C-COMMANDS.md`](pex-i2c-analysis/PEX-I2C-COMMANDS.md)
  is the master protocol reference; `analysis/` holds the supporting Ghidra
  decompilation, `tools/` the extraction and live-control scripts
  (`c410x_control.py`).
- [`aspeed-mainline-drivers-analysis.md`](aspeed-mainline-drivers-analysis.md) /
  [`aspeed-driver-quick-reference.md`](aspeed-driver-quick-reference.md) —
  which mainline Linux drivers cover which AST2050 peripherals.

## Vendor firmware (`backup/`)

`backup/` holds the vendor firmware archives (v1.10–v1.35 plus support
scripts). They are **committed on purpose** — large, but the irreplaceable
source material. Everything *derived* from them is gitignored and regenerated:

```sh
uv run dell-c410x-firmware/extract_firmware.py                    # IO tables: zip -> SquashFS -> evb/*.bin
uv run dell-c410x-firmware/pex-i2c-analysis/tools/extract_fullfw.py   # main BMC ELF /sbin/fullfw
```

## Build and deploy

```sh
uv run dell-c410x-firmware/initramfs/build.py     # BusyBox initramfs -> uInitrd-c410x
uv run dell-c410x-firmware/tftp_boot.py --kernel uImage-c410x --initrd uInitrd-c410x
```

The kernel itself is cross-compiled in CI
(`.github/workflows/build-bmc-firmware.yml`): `aspeed_g4_defconfig` merged with
[`kernel/c410x.config`](kernel/c410x.config) plus the AST2050 clock patches in
`kernel/patches/`, producing a legacy `uImage`.

`check_tmp100_driver.py` sanity-checks the TMP100 sensor driver assumptions;
`datasheets/` vendors the C410X-specific component datasheets (AST2050, PEX
switch briefs, the sensor fan-out — shared Aspeed datasheets are in
[`../datasheets/`](../datasheets/)).

All Python is PEP 723 self-contained — always `uv run`, never bare `python`.

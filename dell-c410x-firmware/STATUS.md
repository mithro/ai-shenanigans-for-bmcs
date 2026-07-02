# Dell C410X Firmware Reverse Engineering -- Project Status

## Completed Work

### Firmware Extraction and Analysis
- Downloaded firmware v1.35 (BM3P135.pec) and archived all available versions
- Extracted SquashFS root filesystem using binwalk
- Identified BMC SoC as Aspeed AST2050 (ARM926EJ-S, also sold as AST1100)
- Identified firmware platform as Avocent MergePoint (Linux 2.6.23.1)
- Documented firmware structure in ANALYSIS.md

### IO Table Documentation (io-tables/)
All five binary configuration tables fully reverse-engineered and documented:

| File | Status | Description |
|------|--------|-------------|
| IO_fl.bin.md | Complete | 192 hardware device entries across 16 device types |
| IS_fl.bin.md | Complete | 72 IPMI sensor definitions with hardware mapping |
| IX_fl.bin.md | Complete | 85-entry index cross-reference with lookup algorithm |
| FT_fl.bin.md | Complete | Per-driver configuration (fan zones, mux channels) |
| oemdef.bin.md | Complete | 100 factory default values (network, credentials, etc.) |
| README.md | Complete | Architecture overview tying all tables together |

### GPIO Pin Mapping (io-tables/gpio-pin-mapping.md)
Complete mapping of all 118 GPIO pins:
- 38 on-chip AST2050 GPIO pins with specific hardware connections
- 80 PCA9555 I2C GPIO expander pins across 5 chips
- Front-panel LED system (power, status, identify, fan, GPU LEDs)
- Interrupt routing for 6 IRQ sources
- Full 12-step power sequencing flow

### Device Tree (aspeed-bmc-dell-c410x.dts)
Complete Linux device tree source reverse-engineered from firmware:
- 6 I2C buses with full device topology (16x INA219, 2x ADT7462,
  16x TMP75, 5x PCA9555, 2x PCA9548, 1x PCA9544A, 1x EEPROM)
- 38 named GPIO lines with functional descriptions
- 9 GPIO hogs for fixed-function outputs (power control, resets)
- Front-panel LED and button definitions
- SPI flash partitions
- Based on aspeed-g4.dtsi (AST2400) due to register compatibility

## Hardware Summary

| Component | Details |
|-----------|---------|
| BMC SoC | Aspeed AST2050 (ARM926EJ-S) |
| PCIe Slots | 16x x16 for GPUs/accelerators |
| PCIe Switches | PLX PEX8696 (96-lane primary) + PEX8647 (48-lane upstream) |
| Power Supplies | 4x hot-swappable |
| Cooling | 8 fans, 2x ADT7462 controllers |
| IPMI Sensors | 72 total (temp, power, fan, presence) |
| GPIO Pins | 38 on-chip + 80 I2C expander = 118 total |
| Dell Codename | "Titanium" |

### Cross-Check Against Raw Firmware Binaries
DTS cross-checked against raw firmware data and corrected:

| Item | Before | After | Source |
|------|--------|-------|--------|
| Memory size | 32 MB | 128 MB | U-Boot: `mem=96M` + VGA at 0x47800000 |
| UART | uart5/ttyS4 | uart1/ttyS0 | U-Boot: `console=ttyS0` |
| Ethernet | use-ncsi | phy-mode rmii | U-Boot: `mac0intf=1` (RMII_PHY) |
| Flash: kernel offset | 0x050000 | 0x100000 | U-Boot: `kernel_start=14100000` |
| Flash: rootfs offset | 0x250000 | 0x300000 | U-Boot: `rootfs_start=14300000` |
| Flash: rootfs size | 0xDB0000 | 0xD00000 | U-Boot: `rootfs_size=D00000` |
| TMP100 I2C address | 0x4E | 0x5C | IS_fl.bin raw sensor table |

Analysis scripts created: `extract_firmware.py`, `parse_io_tables.py`,
`cross_check_dts.py`, `check_tmp100_driver.py`.

## Open Items

- Device tree not validated against physical hardware (no board available)
- PCA9548 mux I2C addresses assumed as 0x70/0x71 (need board verification)
- INA219 shunt resistor values estimated at 2 milliohm
- PLX PCIe switch I2C slave addresses not confirmed
- PMBus PSU physical bus connection not identified (IS_fl.bin PSU entries
  have bus=0x00, dev_addr=0x00 -- handled internally by PMBus driver)
- Per-slot GPU power LED PCA9555 pin mapping partially resolved
- AST2050 on-chip LED controller has no standard Linux DT binding
- U-Boot/env flash partition boundary within first 1 MB is estimated
- MAC0 phy-handle and pinctrl for RMII mode may need further investigation
- FT_fl.bin PCA9548 channel mask 0xBE (channels 0,6 disabled) conflicts
  with IS_fl.bin showing TMP100 sensors on all 8 channels per mux

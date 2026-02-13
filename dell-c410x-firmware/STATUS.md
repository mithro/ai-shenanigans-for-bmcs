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

## Open Items

- Device tree not validated against physical hardware (no board available)
- TMP75/TMP100 I2C addresses need verification (firmware reports 0x5C which
  is non-standard; DTS uses 0x4E as best estimate)
- PCA9548 mux I2C addresses assumed as 0x70/0x71 (need board verification)
- INA219 shunt resistor values estimated at 2 milliohm
- PLX PCIe switch I2C slave addresses not confirmed
- PMBus PSU physical bus connection not identified
- Per-slot GPU power LED PCA9555 pin mapping partially resolved
- AST2050 on-chip LED controller has no standard Linux DT binding

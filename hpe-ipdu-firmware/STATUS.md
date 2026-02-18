# HPE Intelligent Modular PDU -- Project Status

## Completed Work

### Board Identification and Component Inventory
- Identified all major ICs from physical board photos (30 images analysed)
- Main CPU: Digi NS9360B-0-C177 (ARM926EJ-S, NOT NS7520 as initially assumed)
- Memory: 32 MB SDRAM + 16 MB NOR Flash
- Power measurement: Maxim MAXQ3180-RAN 3-phase AFE
- Sub-MCU: Toshiba TMP89FM42LUG for display/LED management
- 3-4x TI MAX3243EI RS-232 level shifters
- All crystals identified (29.4912, 25.000, 8.000, 3.6864 MHz)
- Debug headers identified: J25 "Digi UART", J11 "Mox SPI", J10 "PIC JTAG", J27 "I2C"
- Debug/JTAG headers identified: J1 (large ribbon connector), J6 (black 2x5 header)
- Extension bar bus connector pairs identified: J2/J29, J3/J30, J4/J31

### NS9360 Datasheet Analysis
- Downloaded NS9360 datasheet (Rev D, 91001326_D.pdf)
- Documented complete GPIO MUX table (73 pins, 4 mux options each)
- Documented system address map and BBus peripheral map
- Documented boot configuration (NOR Flash boot, PLL settings)
- Documented serial port assignments (4x UART/SPI)
- Documented I2C and Ethernet pin assignments

### Firmware Research
- Identified firmware codename "Henning" and 10 known versions (1.1 to 2.0.51.12)
- Identified HP Power Device Flash Utility for firmware flashing
- Determined AF531A shares platform with AF520A and other iPDU models
- Documented firmware update methods (Serial Flash and FTP Flash)
- Serial console settings: 115200/8/N/1/None

### Ethernet PHY Identified
- U10 (marked "P47932M / 1893AFLF") is an ICS 1893AFLF Ethernet PHY Transceiver
- Initially misidentified as a clock generator
- 10Base-T/100Base-TX Integrated PHYceiver (Renesas/IDT)
- Pairs with NS9360 on-chip Ethernet MAC via MII/RMII interface

### Documentation Created
| File | Status | Description |
|------|--------|-------------|
| ANALYSIS.md | Complete | Board component inventory, NS9360 I/O architecture |
| RESOURCES.md | Complete | Firmware URLs, datasheets, documentation links |
| STATUS.md | Complete | This file |
| HEADERS-J1-J6.md | Partial | J1/J6 extension bar bus connector documentation |
| datasheets/NS9360_datasheet_91001326_D.pdf | Downloaded | 80-page NS9360 datasheet |
| datasheets/NS9360_HW_Reference_90000675_J.pdf | Downloaded | NS9360 register-level HW reference (2.7 MB) |
| datasheets/MAXQ3180_datasheet.pdf | Downloaded | MAXQ3180 power measurement AFE (1.2 MB) |

## Hardware Summary

| Component | Details |
|-----------|---------|
| CPU | Digi NS9360B-0-C177 (ARM926EJ-S, ~177 MHz) |
| SDRAM | 32 MB (ISSI IS42S32800D-7BLI) |
| NOR Flash | 16 MB (2x Macronix MX29LV640EBXEI) |
| Power Meas. | Maxim MAXQ3180-RAN (3-phase AFE, SPI) |
| Sub-MCU | Toshiba TMP89FM42LUG (8-bit, display/LED) |
| Serial Ports | 4x NS9360 UART/SPI + RS-232 (MAX3243EI) |
| Ethernet | 10/100 (NS9360 MAC + ICS1893AFLF PHY, 25 MHz xtal) |
| I2C | 1x bus (gpio[34]=SCL, gpio[35]=SDA) |
| GPIO | Up to 73 pins (muxed with peripherals) |
| System Crystal | 29.4912 MHz |
| Debug Header | J25 "Digi UART" |

## Open Items

### Firmware Acquisition (Blocked)
- HPE firmware downloads require HPE Passport account authentication
- All support.hpe.com and myenterpriselicense.hpe.com URLs return auth walls
- Eaton ePDU firmware may be compatible (OEM rebrand theory) but not confirmed
- Need to either: obtain HPE account, find mirror, or dump flash from hardware

### Hardware Investigation (Requires Physical Access)
- Boot log not yet captured (user will provide at a later date)
- J25 "Digi UART" debug console output not yet captured
- NOR flash contents not dumped
- PLL bootstrap pin configuration not measured (determines CPU speed)
- J11 "Mox SPI" connection target unknown (MAXQ3180? SPI flash? external?)
- J10 "PIC JTAG" sub-MCU programming interface not traced
- J1 and J6 debug headers documented in [HEADERS-J1-J6.md](HEADERS-J1-J6.md) --
  physical form factors identified, exact pinouts require board tracing
- Extension bar bus protocol (J2/J29, J3/J30, J4/J31 connector pairs) not documented

### Firmware Analysis (Blocked on Firmware Acquisition)
- Firmware binary not yet obtained for analysis
- Bootloader type and version unknown
- Linux kernel version unknown (expected 2.6.x)
- Filesystem type unknown (likely JFFS2, SquashFS, or CramFS)
- Flash memory layout not mapped
- I/O configuration tables not extracted
- GPIO pin assignments not confirmed from firmware

### Datasheet Gaps
- TMP89FM42LUG datasheet not yet downloaded (URL found, ~5 MB / 408 pages)
- ICS1893AFLF Ethernet PHY datasheet not yet downloaded (URL found)
- NS9360 HW Reference downloaded; GPIO register addresses extracted into ANALYSIS.md

### Cross-References Needed
- Confirm serial port assignment (which NS9360 port maps to which connector)
- Confirm SPI port assignment (which NS9360 SPI connects to MAXQ3180)
- Determine if I2C bus has any devices (test point visible but usage unknown)
- Map NS9360 GPIO pins to board-level functions from firmware analysis

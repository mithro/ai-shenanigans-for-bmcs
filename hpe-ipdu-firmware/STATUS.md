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
- Debug headers identified: J25 "Digi UART", J11 "Mox SPI", J10 "PLC DIAG"

### NS9360 Datasheet Analysis
- Downloaded NS9360 datasheet (Rev D, 91001326_D.pdf)
- Documented complete GPIO MUX table (73 pins, 4 mux options each)
- Documented system address map and BBus peripheral map
- Documented boot configuration (NOR Flash boot, PLL settings)
- Documented serial port assignments (4x UART/SPI)
- Documented I2C and Ethernet pin assignments
- Extracted GPIO Configuration Register map from HW Reference Manual

### Ethernet PHY Identified
- U10 (marked "P47932M / 1893AFLF") is an ICS 1893AFLF Ethernet PHY Transceiver
- Initially misidentified as a clock generator
- 10Base-T/100Base-TX Integrated PHYceiver (Renesas/IDT)
- Pairs with NS9360 on-chip Ethernet MAC via MII/RMII interface

### Firmware Obtained and Analysed
- Three firmware versions obtained: 1.6.16.12, 2.0.22.12, 2.0.51.12
- **OS identified: NET+OS (Digi ThreadX-based RTOS)** -- NOT Linux
- Board codename identified: "Brookline" (firmware codename: "Henning")
- Confirmed AF531A is a supported model in firmware v2.0.51.12 README
- Image format: Digi bootHdr (48-byte header + monolithic ARM binary)
- Web server: Allegro RomPager Version 4.01
- Firmware is a flat binary with embedded web UI, no filesystem
- Documented upgrade path: 1.0.9.09 → 1.3.11.09 → 1.6.16.12 → 2.0.49.12
- Created extract_firmware.py for automated analysis

### Firmware Decompression (LZSS2)
- Identified compression algorithm: Digi LZSS2 (Lempel-Ziv-Storer-Szymanski variant)
- Ported decompressor from C# reference (gsuberland/open-network-ms)
- Successfully decompressed all 3 firmware versions
- Confirmed decompressed output is valid big-endian ARM code (ARM926EJ-S)
- ARM vector table verified: `LDR PC, [PC, #0x38]` reset vector + NOPs
- RAM load address: 0x00004000
- Flash address: 0x00020000
- Created parse_header.py, disasm_payload.py, decompress_firmware.py

### Documentation Created
| File | Status | Description |
|------|--------|-------------|
| ANALYSIS.md | Complete | Board inventory, NS9360 I/O, firmware internals |
| RESOURCES.md | Complete | Firmware URLs, datasheets, documentation links |
| STATUS.md | Complete | This file |
| extract_firmware.py | Complete | Firmware extraction and analysis script |
| parse_header.py | Complete | Detailed bootHdr header parser and cross-version comparison |
| disasm_payload.py | Complete | ARM disassembly of raw payload (confirmed compression) |
| decompress_firmware.py | Complete | LZSS2 decompressor (Python port of gsuberland C# reference) |
| analyse_decompressed.py | Complete | Full disassembly, MMIO reference scan, string analysis |
| extract_gpio_init.py | Complete | GPIO init function cluster analysis |
| trace_bsp_init.py | Complete | Reset handler trace, BSP GPIO table search |
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
| OS | NET+OS (ThreadX-based RTOS) |
| Web Server | Allegro RomPager 4.01 |
| Board Codename | "Brookline" |

## Open Items

### Hardware Investigation (Requires Physical Access)
- Boot log not yet captured (user will provide at a later date)
- J25 "Digi UART" debug console output not yet captured
- NOR flash contents not dumped
- PLL bootstrap pin configuration not measured (determines CPU speed)
- J11 "Mox SPI" connection target unknown (MAXQ3180? SPI flash? external?)
- J10 "PLC DIAG" Power Line Communication circuit not traced
- Extension bar bus protocol (J1, J6 connectors) not documented

### Firmware Deep Analysis
- **Firmware decompressed** -- all 3 versions decompressed with LZSS2, load address 0x4000
- **Full ARM disassembly** performed -- MMIO references mapped, function calls traced
- **Reset handler traced** -- boot sequence from 0xB7F64 through BSP init chain
- **Default config table found** -- board name, default IPs, MAC OUI, credentials
- **GPIO init functions located** -- 4 code clusters referencing GPIO config registers
- GPIO configuration VALUES not yet fully extracted (passed via stack, needs decompiler)
- MAXQ3180 SPI communication protocol not extracted
- TMP89FM42LUG serial protocol not extracted
- PLC (Power Line Communication) modem interface not identified
- RomPager CVE-2014-9222 ("Misfortune Cookie") vulnerability not assessed
- NVRAM/configuration storage format not documented
- Web UI resource extraction not complete (embedded in binary)
- CRC32 algorithm not yet matched (stored CRC doesn't match simple crc32 of data)

### Datasheet Gaps
- TMP89FM42LUG datasheet not yet downloaded (URL found, ~5 MB / 408 pages)
- ICS1893AFLF Ethernet PHY datasheet not yet downloaded (URL found)

### Cross-References Needed
- Confirm serial port assignment (which NS9360 port maps to which connector)
- Confirm SPI port assignment (which NS9360 SPI connects to MAXQ3180)
- Determine if I2C bus has any devices (test point visible but usage unknown)
- Map NS9360 GPIO pins to board-level functions from firmware disassembly

# HPE Intelligent Modular PDU -- Firmware Analysis

## Product Identification

| Field | Value |
|-------|-------|
| Product | HPE Intelligent Modular 4.9kVA/L6 Kit |
| HP Part Number | AF531A |
| Spare Part Number | 500496-001 |
| Assembly Number | 572201-001 |
| HP Internal Name | HSTNR-P018-1 |
| Firmware Codename | "Henning" |
| Related Models | AF520A, AF521A, AF522A, AF523A, AF525A, AF526A, AF527A, AF533A, AF901A |

The AF531A is part of HP's Intelligent Modular PDU family. The core controller board
appears to be shared across models (the Google Photos album is labelled "HP PDU AF520A
Core Parts"). These iPDUs may be OEM rebrands of Eaton ePDU products.

## Board Component Inventory

Identified from physical board inspection (Google Photos album:
https://photos.google.com/share/AF1QipOlajnfRlw4bCdkUFzp4Ti6VZBmPwLn1eyXQCJaOMjkgSEMFuxiXs21xtg1u3QJMA?key=TjdOQno3d2FLbzJYSFhBM3RoZ2RfU2xxclJaT05n).

### Main CPU

| Field | Value |
|-------|-------|
| Ref Des | U1 |
| Part | Digi (NetSilicon) NS9360B-0-C177 |
| Core | ARM926EJ-S, 32-bit |
| Speed | Up to 177 MHz (103/155/177 MHz speed grades) |
| Package | 272-pin BGA |
| GPIO | Up to 73 programmable pins (muxed with peripherals) |
| Serial Ports | 4x multi-function (UART or SPI each) |
| I2C | 1x master/slave, 100/400 kHz |
| Ethernet | 10/100 MII/RMII MAC |
| USB | Host + Device (OHCI), internal PHY |
| LCD | Built-in controller (up to 64K colour TFT) |
| Timers | 8x 16/32-bit |
| DMA | 27-channel distributed DMA |
| Date Code | 16050959, TAIWAN1417HAL, DA9762A |
| MAC Address | F0:92:1C:B3:6A:E3 (label: CM-2) |

The NS9360 is part of the NET+ARM family of network-attached processors. It runs
Linux, VxWorks, WinCE, or ThreadX RTOS. The 29.4912 MHz crystal (Y1) on the board
matches the NS9360's reference design for full-speed operation at 176.9 MHz.

### Memory

| Ref Des | Part | Type | Size | Notes |
|---------|------|------|------|-------|
| U29 | ISSI IS42S32800D-7BLI | SDRAM | 32 MB (256 Mbit) | 32-bit wide, 143 MHz |
| U2 | Macronix MX29LV640EBXEI | NOR Flash | 8 MB (64 Mbit) | Bottom boot sector |
| U3 | Macronix MX29LV640EBXEI | NOR Flash | 8 MB (64 Mbit) | Bottom boot sector |

Total memory: 32 MB SDRAM + 16 MB NOR Flash (2x 8 MB, likely addressed as one
contiguous 16 MB region via two static chip selects).

### Power Measurement

| Ref Des | Part | Function | Notes |
|---------|------|----------|-------|
| U15 | Maxim MAXQ3180-RAN | 3-phase power/energy measurement AFE | Connected to 8 MHz crystal (Y4) |
| Y4 | 8.000 MHz crystal | MAXQ3180 clock | FS8.000P |
| PT1 | KSZT770 (kSkyb.com) | 2mA:2mA current transformer | For AC current sensing |

The MAXQ3180 is a high-accuracy poly-phase power measurement Analog Front End
(AFE) with MAXQ20 microcontroller core. It communicates with the main CPU via SPI.
It measures voltage, current, active/reactive/apparent power, power factor, and
frequency for up to 3 phases.

### Sub-Microcontroller (Display/LED Management)

| Ref Des | Part | Function | Notes |
|---------|------|----------|-------|
| U45 | Toshiba TMP89FM42LUG | 8-bit MCU (TLCS-870/C family) | Connected to 3.6864 MHz crystal (Y6) |
| Y6 | 3.6864 MHz crystal | TMP89 clock | FS3.686P, UART baud rate crystal |

The TMP89FM42LUG is a Toshiba TLCS-870/C 8-bit microcontroller. The 3.6864 MHz
crystal is a standard UART baud rate crystal (divides evenly to 115200, 57600, 38400,
19200, 9600 baud). This MCU likely manages the front-panel LCD display and LEDs,
communicating with the main NS9360 over a serial link.

### RS-232 Level Shifters

| Ref Des | Part | Function | Notes |
|---------|------|----------|-------|
| U11 area | TI MAX3243EI (x3-4) | RS-232 level shifters | 3x or 4x units on board |

Multiple MAX3243EI RS-232 transceivers provide serial port interfaces. The NS9360 has
4 serial ports, and the PDU has multiple serial connections:
- Debug UART (J25 "Digi UART" header)
- Display Unit communication
- Daisy-chain to additional iPDU units

### Ethernet PHY

| Ref Des | Part | Function |
|---------|------|----------|
| U10 | ICS 1893AFLF (marked P47932M) | 10/100 Ethernet PHY Transceiver |

The ICS1893AFLF is a 3.3V 10Base-T/100Base-TX Integrated PHYceiver (Ethernet PHY),
manufactured by ICS (now Renesas/IDT). Initially misidentified as a clock generator.
The "P47932M" marking is likely a date/lot code. This is the external Ethernet PHY
that pairs with the NS9360's on-chip Ethernet MAC.

### Crystals Summary

| Ref Des | Frequency | Function |
|---------|-----------|----------|
| Y1 | 29.4912 MHz (KDS 4K) | NS9360 main system clock |
| Y2 | 25.000 MHz (KDS) | Ethernet PHY reference clock |
| Y4 | 8.000 MHz (FS8.000P) | MAXQ3180 power measurement clock |
| Y6 | 3.6864 MHz (FS3.686P) | TMP89FM42 sub-MCU clock |

### Other Components

| Ref Des | Part | Function |
|---------|------|----------|
| U4 | ROHM BU251 | Voltage regulator |
| BT1 | Coin cell battery | RTC backup |

### Connectors and Headers

| Ref Des | Label | Function |
|---------|-------|----------|
| J25 | "Digi UART" | Debug UART header (serial console) |
| J11 | "Mox SPI" | SPI header (possibly for MAXQ3180 or SPI flash) |
| J10 | "PLC DIAG" | Power Line Communication diagnostics |
| J1, J6 | White connectors | Extension bar bus connectors |
| J28 | Pin header | Unknown |
| J5 | Connector | Unknown |
| -- | "BIST EN" | Built-In Self Test enable test point |
| -- | "I2C" | I2C bus test point |
| -- | RJ-45 | Ethernet management port |

### Board Markings

- "HP invent" logo silkscreen
- "Development Company" silkscreen
- "POWER SUPPLY" section with 400V 22uF capacitors (mains-rated)

## NS9360 SoC -- I/O Architecture

### System Address Map

| Address Range | Size | Function |
|---------------|------|----------|
| 0x0000_0000 - 0x0FFF_FFFF | 256 MB | Dynamic memory CS0 (SDRAM) |
| 0x1000_0000 - 0x3FFF_FFFF | 768 MB | Dynamic memory CS1-3 (unused) |
| 0x4000_0000 - 0x4FFF_FFFF | 256 MB | Static memory CS0 (NOR Flash bank 1) |
| 0x5000_0000 - 0x5FFF_FFFF | 256 MB | Static memory CS1 (NOR Flash bank 2) |
| 0x6000_0000 - 0x7FFF_FFFF | 512 MB | Static memory CS2-3 |
| 0x9000_0000 - 0x9FFF_FFFF | 256 MB | BBus peripherals |
| 0xA040_0000 | 1 MB | BBus-to-AHB bridge |
| 0xA060_0000 | 1 MB | Ethernet Communication module |
| 0xA070_0000 | 1 MB | Memory controller |
| 0xA080_0000 | 1 MB | LCD controller |
| 0xA090_0000 | 1 MB | System Control module |

### BBus Peripheral Map

| Base Address | Peripheral |
|-------------|------------|
| 0x9000_0000 | BBus DMA controller |
| 0x9020_0000 | SER Port B |
| 0x9020_0040 | SER Port A |
| 0x9030_0000 | SER Port C |
| 0x9030_0040 | SER Port D |
| 0x9040_0000 | IEEE 1284 controller |
| 0x9050_0000 | I2C controller |
| 0x9060_0000 | BBus utility (GPIO config registers) |
| 0x9070_0000 | Real Time Clock |
| 0x9080_0000 | USB Host |
| 0x9090_0000 | USB Device |

### GPIO MUX Table (73 pins)

Each GPIO pin has 4 mux options (00, 01, 02, 03). Option 03 is always GPIO mode.
Option 00 is the default peripheral function. The BBus utility registers at 0x9060_0000
control pin muxing.

#### Serial Port Pins (likely UART usage on this board)

| GPIO | Pin | Mux 00 (UART/SPI) | Likely Board Function |
|------|-----|--------------------|-----------------------|
| gpio[0] | W5 | Ser B TXData / SPI B dout | RS-232 TX (to Display Unit?) |
| gpio[1] | V6 | Ser B RXData / SPI B din | RS-232 RX (from Display Unit?) |
| gpio[2] | Y5 | Ser B RTS | RS-232 flow control |
| gpio[3] | W6 | Ser B CTS | RS-232 flow control |
| gpio[4] | V7 | Ser B DTR | RS-232 flow control |
| gpio[5] | Y6 | Ser B DSR | RS-232 flow control |
| gpio[6] | W7 | Ser B RI / SPI B clk | RS-232 RI or SPI clock |
| gpio[7] | Y7 | Ser B DCD / SPI B enable | RS-232 DCD or SPI CS |
| gpio[8] | V8 | Ser A TXData / SPI A dout | Debug UART TX (J25 "Digi UART") |
| gpio[9] | W8 | Ser A RXData / SPI A din | Debug UART RX (J25 "Digi UART") |
| gpio[10] | Y8 | Ser A RTS | Debug UART flow control |
| gpio[11] | V9 | Ser A CTS | Debug UART flow control |
| gpio[20] | Y12 | Ser C DTR | Daisy-chain UART or SPI? |
| gpio[22] | V12 | Ser C RI / SPI C clk | |
| gpio[23] | Y13 | Ser C DCD / SPI C enable | |
| gpio[40] | V17 | Ser C TXData / SPI C dout | |
| gpio[41] | W18 | Ser C RXData / SPI C din | |
| gpio[44] | U19 | Ser D TXData / SPI D dout | MAXQ3180 SPI? |
| gpio[45] | U20 | Ser D RXData / SPI D din | MAXQ3180 SPI? |
| gpio[46] | T19 | Ser D RTS | |
| gpio[47] | R18 | Ser D CTS | |

Note: Serial Port A is the most likely debug UART (connects to J25 "Digi UART"
header). Serial Port B likely connects to the Display Unit over RS-232 via MAX3243EI.
One of Port C or D is likely configured as SPI for the MAXQ3180 power measurement
AFE.

#### I2C Pins

| GPIO | Pin | Mux 00 Function |
|------|-----|-----------------|
| gpio[34] | Y17 | iic_scl |
| gpio[35] | U15 | iic_sda |

These must be set to mux option 00 for I2C operation. The I2C bus likely connects to
the "I2C" test point visible on the board.

#### Ethernet Pins (MII/RMII)

| GPIO | Pin | MII Function | RMII Function |
|------|-----|-------------|---------------|
| gpio[50] | K2 | MDIO | MDIO |
| gpio[51] | U3 | rx_dv | N/C |
| gpio[52] | V1 | rx_er | rx_er |
| gpio[53] | N3 | rxd[0] | rxd[0] |
| gpio[54] | N2 | rxd[1] | rxd[1] |
| gpio[55] | N1 | rxd[2] | N/C |
| gpio[56] | M3 | rxd[3] | N/C |
| gpio[57] | M2 | tx_en | tx_en |
| gpio[58] | M1 | tx_er | N/C |
| gpio[59] | L3 | txd[0] | txd[0] |
| gpio[60] | L1 | txd[1] | txd[1] |
| gpio[61] | K1 | txd[2] | N/C |
| gpio[62] | K3 | txd[3] | N/C |
| gpio[63] | P2 | collision | N/C |
| gpio[64] | R1 | carrier sense | crs_dv |
| gpio[65] | P1 | enet_phy_int_n | enet_phy_int_n |

The 25 MHz crystal (Y2) provides the reference clock for the ICS1893AFLF Ethernet PHY
(U10), which connects to the NS9360's MII/RMII MAC interface.

### GPIO Configuration Registers (BBus Utility @ 0x9060_0000)

The GPIO system is controlled through three register groups in the BBus Utility block.
Each GPIO pin has a 4-bit configuration field with bits: D03=DIR, D02=INV, D01:D00=FUNC.
All pins reset to 0x3 (GPIO input mode, no inversion).

#### Configuration Registers (4 bits per pin: DIR/INV/FUNC)

| Register | Address | GPIO Pins | Bits per Pin |
|----------|---------|-----------|-------------|
| GPIO Config #1 | 0x9060_0010 | gpio[0]-gpio[7] | D[3:0]=gpio[0], D[7:4]=gpio[1], ... D[31:28]=gpio[7] |
| GPIO Config #2 | 0x9060_0014 | gpio[8]-gpio[15] | Same pattern |
| GPIO Config #3 | 0x9060_0018 | gpio[16]-gpio[23] | Same pattern |
| GPIO Config #4 | 0x9060_001C | gpio[24]-gpio[31] | Same pattern |
| GPIO Config #5 | 0x9060_0020 | gpio[32]-gpio[39] | Same pattern |
| GPIO Config #6 | 0x9060_0024 | gpio[40]-gpio[47] | Same pattern |
| GPIO Config #7 | 0x9060_0028 | gpio[48]-gpio[49] | Only D[7:0] used |
| GPIO Config #8 | 0x9060_0100 | gpio[50]-gpio[57] | Same pattern |
| GPIO Config #9 | 0x9060_0104 | gpio[58]-gpio[65] | Same pattern |
| GPIO Config #10 | 0x9060_0108 | gpio[66]-gpio[72] | Only D[27:0] used |

Config bit field per pin:
- **D03 (DIR)**: 0=input, 1=output (only applies when FUNC=11 GPIO mode)
- **D02 (INV)**: 0=normal, 1=inverted (only applies when FUNC=11 GPIO mode)
- **D01:D00 (FUNC)**: 00=Mux0 (default peripheral), 01=Mux1, 10=Mux2, 11=GPIO mode

#### Control Registers (write output values)

| Register | Address | GPIO Pins |
|----------|---------|-----------|
| GPIO Control #1 | 0x9060_0030 | gpio[0]-gpio[31] |
| GPIO Control #2 | 0x9060_0034 | gpio[32]-gpio[49] |
| GPIO Control #3 | 0x9060_0120 | gpio[50]-gpio[72] |

Each bit controls the output level of the corresponding GPIO pin (when configured as output).

#### Status Registers (read input values)

| Register | Address | GPIO Pins |
|----------|---------|-----------|
| GPIO Status #1 | 0x9060_0040 | gpio[0]-gpio[31] |
| GPIO Status #2 | 0x9060_0044 | gpio[32]-gpio[49] |
| GPIO Status #3 | 0x9060_0130 | gpio[50]-gpio[72] |

Each bit reflects the current level of the corresponding GPIO pin.

### Boot Configuration

The NS9360 boots from NOR Flash via the system memory bus (RESET_DONE = 1,
default). The flash is connected to static memory chip selects. With 2x MX29LV640EB
(64 Mbit each, bottom boot sector), the total flash is 16 MB.

Configuration pins at powerup determine:
- **gpio[24], gpio[20]**: CS1 data width (likely 01 = 8-bit or 11 = 32-bit)
- **gpio[49]**: CS polarity (0 = active high, 1 = active low)
- **gpio[44]**: Endian mode (0 = big endian, 1 = little endian)
- **gpio[17,12,10,8,4]**: PLL multiplier (ND[4:0])
- **gpio[2], gpio[0]**: PLL frequency select (FS[1:0])

With Y1 = 29.4912 MHz and PLL configured for full speed:
- CPU clock: 176.9 MHz
- AHB bus: 88.5 MHz
- BBus (peripheral): 44.2 MHz

## Serial Console

| Parameter | Value |
|-----------|-------|
| Baud Rate | 115200 |
| Data Bits | 8 |
| Parity | None |
| Stop Bits | 1 |
| Flow Control | None |
| Header | J25 "Digi UART" |

## Core Unit Connector Layout (from HP iPDU Manual)

| Callout | Description |
|---------|-------------|
| 1-6 | Circuit breakers for load segments 1-6 (phases A/B/C on 3-phase models) |
| 7 | Serial connector for additional iPDU daisy-chain |
| 8 | Serial connector for Display Unit connection |
| 9 | Network connector (Ethernet RJ-45) |
| 10 | Reset button (maintains outlet power, resets management only) |
| 11-16 | IEC-320 C19 outlets for load segments 6 through 1 |

Total of 6 load segments per Core Unit. Up to 6 Extension Bars can be connected,
providing up to 30 IEC-320 C13 outlets total.

## Firmware Structure

The firmware is distributed as `image.bin` inside ZIP files with names like
`Henning_<version>_<part>.zip`. Configuration is in `config.bin`. Flashing modes:
1. **Serial Flash Mode**: Through the Display Unit's serial port (requires "LED
   Pass-Through mode" to be set first, firmware only)
2. **FTP Flash Mode**: Over the network via FTP (supports firmware and config,
   single or multiple units)

Known firmware versions (codename "Henning"):

| Version | Date | Notes |
|---------|------|-------|
| 1.0.09.09 | ~2010 | Initial release (IPv6 link-local support) |
| 1.1.02.09 | ~2010 | Redundancy management |
| 1.2.10.09 | ~2011 | Config download/upload |
| 1.3.11.09 | ~2011 | Daisy-chain, group control, outlet delay |
| 1.4.13.09 | ~2013 | AF547A support, IE9 |
| 1.5.16.09 | 2012-10-08 | Location Discovery Services |
| 1.6.16.12 | 2013-10-11 | Energy metering, 1024-bit SSL |
| 2.0.21.12 | 2015-02-03 | New web server, LDAP auth |
| 2.0.22.12 | 2015-09-02 | Rack View optimization |
| 2.0.49.12 | 2018-05-22 | New H/W enablement |
| 2.0.51.12 | 2019-03-06 | Latest known (Z7550-02475) |

**Upgrade path**: 1.0.9.09 → 1.3.11.09 → 1.6.16.12 → 2.0.49.12 (FTP only for
v1.6→v2.0 upgrade; serial mode does not work for this transition).

Supported iPDU models (from v2.0.51.12 README): AF520A, AF521A, AF522A, AF523A,
**AF531A**, AF532A, AF533A, AF534A, AF535A, AF537A, AF538A, AF525A, AF526A,
AF527A, AF900A, AF901A, AF902A.

## Firmware Internals (Confirmed from Binary Analysis)

The firmware runs **NET+OS** (Digi's ThreadX-based RTOS), **NOT Linux**. The
`image.bin` is a monolithic flat ARM binary, not a filesystem image.

### Operating System
- **RTOS**: Digi NET+OS (ThreadX-based), confirmed by "netos" and "netos_stubs.c"
  strings in the binary. Source file reference: `netos_stubs.c`
- **NOT Linux**: No Linux kernel strings, no filesystem (SquashFS/JFFS2/CramFS)
- **Board codename**: "Brookline" (from string: "NS9360 Brookline Board Debug
  Output Serial port")
- **Firmware codename**: "Henning" (from ZIP file names)

### Web Server
- **Allegro RomPager Version 4.01** -- (C) 1995-2000 S&S Software Development Corp.
- Known embedded HTTP server for RTOS platforms
- Note: RomPager has known vulnerabilities (CVE-2014-9222 "Misfortune Cookie")
- Web UI uses jQuery, Raphael.js (for rack view), and stringencoders library

### Image Format (Digi NET+OS bootHdr)

The firmware uses the Digi NET+OS `bootHdr` format with LZSS2 compression.
All header fields are big-endian. The format was confirmed by cross-referencing
with the [gsuberland/open-network-ms](https://github.com/gsuberland/open-network-ms)
NET+OS firmware parser (Eaton/MGE UPS cards use the same Digi platform).

| Offset | Size | Field | Value (all versions) | Description |
|--------|------|-------|---------------------|-------------|
| 0x00 | 4 | Complete header size | 0x0000002C (44) | Total header including custom section |
| 0x04 | 4 | NET+OS header size | 0x00000024 (36) | Standard header (pre-7.4 format) |
| 0x08 | 8 | Signature | "bootHdr\0" | Digi boot header magic |
| 0x10 | 4 | Version | 0x00000000 | NET+OS version (pre-7.4) |
| 0x14 | 4 | Flags | 0x00000009 | BL_WRITE_TO_FLASH \| BL_LZSS2_COMPRESSED |
| 0x18 | 4 | Flash address | 0x00020000 | Where to store in NOR flash (128K offset) |
| 0x1C | 4 | RAM address | 0x00004000 | Where to decompress to in RAM (16K offset) |
| 0x20 | 4 | Image size | varies | Compressed data size (= file_size - 48) |
| 0x24 | 8 | Custom header | "HPPDU00\0" | OEM product identifier |
| 0x2C | ... | LZSS2 data | | Compressed ARM firmware |
| last 4 | 4 | CRC32 | varies | Checksum (algorithm TBD) |

**Header flags** (from NET+OS bootloader source):
- Bit 0: `BL_WRITE_TO_FLASH` -- write image to flash storage
- Bit 1: `BL_LZSS_COMPRESSED_MAYBE` -- original LZSS compression
- Bit 2: `BL_EXECUTE_FROM_ROM` -- execute directly from flash
- Bit 3: `BL_LZSS2_COMPRESSED` -- LZSS2 compression (used here)
- Bit 4: `BL_BYPASS_CRC_CHECK` -- skip CRC verification
- Bit 5: `BL_BYPASS_IMGLEN_CHECK` -- skip image length check

Compressed data sizes across firmware versions:
- v1.6.16.12: 2,893,415 bytes → 5,710,958 bytes decompressed (1.97x)
- v2.0.22.12: 3,654,385 bytes → 7,948,582 bytes decompressed (2.18x)
- v2.0.51.12: 3,663,764 bytes → 7,965,684 bytes decompressed (2.17x)

### LZSS2 Compression

The firmware payload is compressed using Digi's LZSS2 algorithm (a variant of
Lempel-Ziv-Storer-Szymanski). Parameters:

| Parameter | Value |
|-----------|-------|
| Window size (N) | 4096 bytes |
| Look-ahead buffer (F) | 18 bytes |
| Minimum match (Threshold) | 2 bytes |
| Ring buffer init | Spaces (0x20) |
| Flag byte | 8 bits per flag byte, bit 0 = first |

Each flag byte controls 8 subsequent tokens. If the flag bit is 1, the next
byte is a literal. If 0, the next 2 bytes encode a back-reference: 12-bit
position in the ring buffer and 4-bit length (+threshold).

Implementation: `decompress_firmware.py` (Python port of the C# reference
from gsuberland/open-network-ms).

### Decompressed Firmware Structure

After LZSS2 decompression, the firmware is a flat big-endian ARM binary
loaded at address 0x00004000 in RAM.

**ARM Vector Table** (at load address 0x00004000):
- 0x00: `LDR PC, [PC, #0x38]` -- Reset vector (jumps via literal pool)
- 0x04-0x3C: `NOP` (MOV R0, R0) -- Unused exception vectors
- 0x40+: Literal pool with handler addresses

**Binary Structure** (v2.0.51.12, 7,965,684 bytes):

| Region | Content | Entropy |
|--------|---------|---------|
| 0x000000-0x0000FF | ARM vector table + literal pool | Low |
| 0x000100-~0x500000 | ARM code (functions, libraries) | ~5.8 bits/byte |
| ~0x500000-~0x680000 | Web UI resources (HTML, CSS, JS, GIF) | Mixed |
| ~0x680000-~0x798000 | String tables, config, SNMP MIBs | Low entropy |

Key strings found in decompressed binary:
- "NS9360 Brookline Board Debug Output Serial port"
- "NET+ARM", "NET+OS", "netos_stubs.c"
- "ThreadX" (underlying RTOS)
- "Allegro RomPager Version 4.01" (web server)
- "MAXQ" (power measurement IC communication)
- SNMP MIBs, HTML/JavaScript web UI, FTP/Telnet service strings
- HP Copyright 2003-2013

Overall: ~52% printable bytes (extensive embedded web UI content).

## Default Configuration (from firmware data table)

The firmware contains a default configuration data table near the board
name string at 0x0069C784:

| Field | Default Value |
|-------|---------------|
| Board name | "Brookline" |
| Admin username | "admin" |
| IP address | 172.16.100.102 |
| Subnet mask | 255.255.0.0 |
| Gateway | 172.16.0.1 |
| DNS server 1 | 129.6.15.29 |
| DNS server 2 | 129.6.15.28 |
| Serial number | N99999999 (placeholder) |
| MAC address 1 | 00:40:9d:43:35:97 |
| MAC address 2 | 00:40:9d:43:35:98 |
| Phase config | "Single Phase" |

The MAC OUI `00:40:9d` is registered to Digi International, confirming
this is a Digi-based platform. The DNS servers 129.6.15.x are NIST
time servers (time.nist.gov).

## Boot Sequence (from reset handler trace)

The ARM reset vector at 0x4000 loads PC from literal pool → 0x000B7F64.

| Step | Address | Function |
|------|---------|----------|
| 1 | 0x000B7F64 | CP15 setup (alignment check, cache enable) |
| 2 | 0x000B7F80 | System control register init (0xA0900000) |
| 3 | 0x000B7FB4 | PLL and clock configuration |
| 4 | 0x000B7FD4 | Mode switch to SVC, stack setup (SP = 0x4000) |
| 5 | 0x000B84B4 | BL 0x000A817C -- BSP system init |
| 6 | 0x000B8510 | BL 0x000A81A8 -- BSP peripheral init |
| 7 | 0x000B85A4 | BL 0x000A86CC -- BSP GPIO/serial init |

The GPIO configuration registers at 0x9060_xxxx are written from functions
in the 0x000A9xxx range, called from the BSP init chain. Values are passed
through the stack (not hardcoded in literal pools), making static extraction
difficult without a full decompiler.

## Communication Architecture

```
                    Ethernet (RJ-45, connector 9)
                         |
                    [NS9360 CPU]
                    /    |    \     \
               UART-A  UART-B  SPI   I2C     UART-C or D?
                |        |      |      |          |
            Debug     Display  MAXQ   Test    Daisy-chain
            (J25)     Unit    3180   Point   to next iPDU
                    (conn 8)                  (conn 7)
                       |
                    [MAX3243EI]
                       |
                    RS-232
                       |
                    Serial Console
                    (host computer)
```

The Display Unit acts as the serial console gateway -- you cannot bypass it for console
access without connecting directly to J25 "Digi UART". The reset button (connector 10)
resets management only; outlet power is maintained.

### Serial Port Analysis (from firmware register references)

Searching the decompressed firmware for NS9360 serial port register addresses reveals
which ports are actively used and how they are configured:

| Port | Base Address | Register Refs | DMA | Usage |
|------|-------------|---------------|-----|-------|
| Port B | 0x9020_0000 | 13 (6 types) | Yes | Primary communication (Display Unit?) |
| Port C | 0x9030_0000 | 3 (FIFO only) | Yes | Secondary communication (daisy-chain?) |
| Port A | 0x9020_0040 | 1 (FIFO only) | No | Debug UART (J25, polled/interrupt) |
| Port D | 0x9030_0040 | 1 (FIFO only) | No | Minimal use (MAXQ3180 SPI?) |

**Port B** has by far the most register references (Control A, Control B, Bit Rate,
Status A, RX Char Timer), indicating it is the primary communication port with full
configuration. A DMA descriptor table at ~0x757130 maps Port B and Port C to dedicated
DMA channels, while Port A and Port D are absent (polled or interrupt-driven).

Port B Control A value `0x83030A00` found in literal pool at 0xACC38 -- but this is
written to the FIFO register during init, not to Control A itself. The actual UART
configuration (baud rate, mode) is set through the NET+OS serial driver API.

The firmware contains baud rate divisor values for 115200 baud (divisor 23, 47 occurrences)
and 9600 baud (divisor 287, 6 occurrences), suggesting both rates are used.

Key strings: "NS9360 Brookline Board Debug Output Serial port" (Port A/J25),
"Display serial statistics (port 1-4)", "Serial Debug CLI",
"error when change baud rate in Dialog.c", "calibrate maxim voltage" (MAXQ3180 over SPI).

## Cross-Version Firmware Comparison

### Size and Complexity

| Version | Size | Functions | Printable | Copyright |
|---------|------|-----------|-----------|-----------|
| v1.6.16.12 | 5.4 MB | ~5,863 | 53% | 2003-2012 |
| v2.0.22.12 | 7.6 MB | ~6,871 | 52% | 2003-2014 |
| v2.0.51.12 | 7.6 MB | ~6,912 | 52% | 2003-2016 |

- v1.6 → v2.0.22: **+39% growth** (+2.2 MB, +1,008 functions) -- major rewrite
- v2.0.22 → v2.0.51: **+0.2% growth** (+17 KB, +41 functions) -- minor patch

### Feature Evolution (v1.6 → v2.0)

Major additions in v2.0:
- **LDAP authentication** (OpenLDAP, SASL, DIGEST-MD5)
- **SSL/TLS** with OpenSSL 0.9.7b (certificate management, HTTPS)
- **Rack View** with Raphael.js vector graphics (14U-60U rack sizes)
- **SNMP managers** (up to 5, configurable access)
- **jQuery 1.10.2** (replacing inline JavaScript)
- **KLone web framework** (www.koanlogic.com) alongside RomPager
- **NTP time sync** (dual server support)
- **IPv6 validation** (partial)
- **XML configuration** import/export

Web UI rewrite: 359 → 1,439 URL paths, 2 → 10 RomPager directive types, added
AJAX (XMLHttpRequest), session tracking, Japanese localisation.

### Unchanged Between Versions

- Default configuration (Brookline, admin, 172.16.100.102, Digi MAC OUI)
- RomPager 4.01 (never updated)
- ThreadX ARM7/Green Hills Version G4.0.4.0 (never updated)
- OpenSSL 0.9.7b from 2003 (never updated)
- YAFFS filesystem module (v1.6.4.1, 2007)

## Security Assessment

### CVE-2014-9222: Misfortune Cookie (RomPager)

| Field | Value |
|-------|-------|
| CVE | CVE-2014-9222 |
| Affected | Allegro RomPager < 4.34 |
| Firmware Version | 4.01 (**VULNERABLE**) |
| CVSS | 9.8 (Critical) |
| Disclosed | 2014-12-23 |
| Patched in firmware | **Never** (all 3 versions use 4.01) |

The vulnerability allows remote code execution without authentication via a
crafted HTTP Cookie header. The firmware contains cookie handling code ("Set-Cookie: C"
at 0x722490, "cookie" at 0x7234D0) and full HTTP header parsing.

### OpenSSL 0.9.7b (2003)

The firmware includes OpenSSL 0.9.7b dated 2003-04-10. This version has hundreds
of known CVEs including:
- Heartbleed (CVE-2014-0160) -- may not apply if TLS heartbeat not compiled in
- POODLE (CVE-2014-3566) -- SSLv3 padding oracle
- FREAK (CVE-2015-0204) -- export cipher downgrade
- Numerous buffer overflow, null pointer, and DoS vulnerabilities

### Attack Surface Summary

| Service | Protocol | Port | Authentication |
|---------|----------|------|----------------|
| HTTP | TCP | 80 | Cookie-based session |
| HTTPS | TCP | 443 | SSL/TLS + cookie |
| Telnet | TCP | 23 | Username/password |
| FTP | TCP | 21 | Username/password |
| SNMP | UDP | 161/162 | Community strings |

All services are network-accessible through the Ethernet management port.
The SNMP implementation has 257 references in the binary.

### Recommendations

1. **Isolate management network** -- place iPDU management port on dedicated VLAN
2. **Restrict access** -- ACL/firewall to allow only trusted management hosts
3. **Disable unnecessary services** -- turn off Telnet, restrict FTP access
4. **Monitor** -- watch for exploit attempts (malformed cookies, unusual HTTP)
5. **Physical security** -- protect J25 debug UART header from unauthorized access

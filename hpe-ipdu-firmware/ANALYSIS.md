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
| gpio[0] | W5 | Ser B TXData / SPI B dout | **GPIO input** (SPI B disabled, see below) |
| gpio[1] | V6 | Ser B RXData / SPI B din | **GPIO input** (SPI B disabled) |
| gpio[2] | Y5 | Ser B RTS | **GPIO input** |
| gpio[3] | W6 | Ser B CTS | **GPIO input** |
| gpio[4] | V7 | Ser B DTR | **GPIO input** |
| gpio[5] | Y6 | Ser B DSR | **GPIO input** |
| gpio[6] | W7 | Ser B RI / SPI B clk | **GPIO input** (SPI B disabled) |
| gpio[7] | Y7 | Ser B DCD / SPI B enable | **GPIO input** (SPI B disabled) |
| gpio[8] | V8 | Ser A TXData / SPI A dout | GPIO output (mux=1) |
| gpio[9] | W8 | Ser A RXData / SPI A din | **Ser A RX** (mux=0, peripheral mode) |
| gpio[10] | Y8 | Ser A RTS | GPIO output (mux=1) |
| gpio[11] | V9 | Ser A CTS | **Ser A CTS** (mux=0, peripheral mode) |
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
| last 4 | 4 | CRC32 | varies | Integrity checksum (see below) |

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

### CRC32 Integrity Checksum

The trailing 4 bytes of each firmware image contain a CRC32 integrity checksum.
The bootloader validates this CRC during boot via the `isImageValid()` function
(in `blmain.c` of the NET+OS BSP). The `BL_BYPASS_CRC_CHECK` flag (bit 4 = 0x10)
can disable validation, but all known HPE iPDU firmware images have this flag
clear (flags = 0x09).

**Algorithm identified** (verified against all 3 firmware versions):

| Parameter | Value |
|-----------|-------|
| Polynomial | 0x04C11DB7 (standard CRC-32 polynomial) |
| Bit order | Non-reflected (MSB-first, big-endian) |
| Initial value | 0x00000000 |
| Final XOR | 0x00000000 |
| CRC stored as | Big-endian, trailing 4 bytes |
| Data range | Header + compressed payload (all bytes except trailing 4) |
| Closest named algorithm | CRC-32/MPEG-2 with init=0 (non-standard init) |

This is **not** the standard CRC-32 (ISO-HDLC/zlib), which uses init=0xFFFFFFFF,
xor_out=0xFFFFFFFF, and reflected bit order. The Digi implementation uses the
simplest possible form of CRC-32: no initialization, no finalization, no reflection.
This is consistent with a minimal bootloader CRC implementation on a big-endian
ARM platform (the NS9360 runs in big-endian mode).

The CRC-32 polynomial constant 0x04C11DB7 was also found in the decompressed
firmware binary at offset 0x000B3D58 (address 0x000B7D58), confirming the
polynomial is embedded in the application image as well.

Verification:

| Version | Stored CRC (BE) | Computed CRC | Match |
|---------|----------------|--------------|-------|
| v1.6.16.12 | 0xA8B1DCFB | 0xA8B1DCFB | Yes |
| v2.0.22.12 | 0x928D9048 | 0x928D9048 | Yes |
| v2.0.51.12 | 0x5CA35970 | 0x5CA35970 | Yes |

To compute the CRC in Python:
```python
import crcmod
crc_func = crcmod.mkCrcFun(0x104C11DB7, initCrc=0, rev=False, xorOut=0)
crc = crc_func(data[:-4])  # CRC of everything except trailing 4 bytes
```

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
in the 0x000A9xxx range, called from the BSP init chain. Some values are
visible in literal pools, others passed through the stack.

### GPIO Configuration Values (partial, from literal pool analysis)

Four GPIO init code clusters were found. Cluster 1 (at 0x000A97CC) had
config values in its literal pool:

| Register | Value | Meaning |
|----------|-------|---------|
| GPIO Config #1 (pins 0-7) | 0x33333333 | **All 8 pins as GPIO inputs** -- SPI B completely disabled |
| GPIO Config #2 (pins 8-15) | 0x13130101 | Mixed: pin 9 (Ser A RX) and pin 11 (CTS) in peripheral mode, rest GPIO |

**Key finding: SPI B is NOT used.** All SPI B pins (gpio[0] CLK, gpio[1] DIN, gpio[6] CLK, gpio[7] EN)
are reconfigured as GPIO inputs. The MAXQ3180 must connect via a different SPI port.

GPIO Config #2 shows Serial Port A is partially active with RX (pin 9) and CTS (pin 11) in
peripheral mode. Pins 8, 10, 13, 15 are set to mux=1 (GPIO output or LCD function), and
pins 12, 14 are GPIO inputs.

Cluster 4 (at 0x0029B378) contained a repeating pattern of 0x06000000 values, which configure
one pin per register (pin position 6) as interrupt-capable GPIO input with signal inversion.
These may be templates or default configurations.

### NS9360 Peripheral Address Map (from firmware MMU table)

A peripheral memory region table was found at 0x757114, used by NET+OS to configure the
ARM926EJ-S MMU. This confirms the complete peripheral address ranges:

| Base Address | End Address | Size | Peripheral |
|-------------|-------------|------|------------|
| 0x9000_0000 | 0x9000_01D3 | 468 B | System / DMA controller |
| 0x9020_0000 | 0x9020_007B | 124 B | Serial Ports B + A |
| 0x9030_0000 | 0x9030_007B | 124 B | Serial Ports C + D |
| 0x9040_0000 | 0x9040_017B | 380 B | Ethernet MAC |
| 0x9050_0000 | 0x9050_000F | 16 B | I2C controller (4 registers) |
| 0x9060_0000 | 0x9060_0093 | 148 B | GPIO / BBus utility |
| 0x9070_0000 | 0x9070_0034 | 52 B | Timer |
| 0x9080_0000 | 0x9080_1FFF | 8 KB | Endian / USB module |
| 0x9090_0000 | 0x9091_FFFF | 128 KB | LCD controller |

## Communication Architecture

```
                    Ethernet (RJ-45, connector 9)
                         |
                    [NS9360 CPU]
                    /    |    \     \
               UART-A  UART-B  SPI   I2C     UART-C or D?
                |        |      |      |          |
            Debug     Display  MAXQ   ???     Daisy-chain
            (J25)     Unit    3180            to next iPDU
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

### Inter-PDU Communication ("Core DC Proto")

The firmware implements a daisy-chain protocol for connecting multiple iPDU units,
managed by dedicated RTOS tasks:

| Task Name | Description |
|-----------|-------------|
| Core DC Proto Task | Daisy-chain protocol handler task |
| Core DC Proto Que | Daisy-chain protocol message queue |
| Core Async | Core asynchronous processing |
| Core Proto | Core protocol handler |
| Stick Async | Extension bar asynchronous processing |
| Ipd | IPMI protocol handler |

**Connection Types** (from web UI JavaScript):
- `connectionType == 0`: Standalone PDU (single unit)
- `connectionType == 1`: Cascaded PDU (primary/secondary pair)
- `connectionType == 2`: Extended cascaded configuration

**Physical Link Detection**: The `detectpins` CLI command "Tests Upstream & Downstream
Detect Pins", confirming that physical GPIO pins are used to detect which end of a
daisy-chain a unit is connected to.

**Discovery**: Extension bars are detected as either "Monitored stick" or "Non Monitored
stick" (0x0069_D468/0x0069_D484). "Discovery Capable Device Connected/Disconnected"
events track hotplug of discovery-capable devices.

### PLC Modem -- Not Present

Despite the "PLC DIAG" label on header J10, the firmware contains **no Power Line
Communication protocol references** (no HomePlug, X10, INSTEON, or Z-Wave strings).
All "power line" references relate to SVG drawing in the web UI.

The "PLC" in J10's label likely refers to either:
- Programmable Logic Controller diagnostics
- An optional module not supported by this firmware version
- A planned but never implemented feature

### Redundancy Management

The firmware supports redundant PDU pairs for high-availability power distribution:

| Feature | Details |
|---------|---------|
| Pairing | Primary/Secondary PDU pair via IP network |
| XML Tags | `<PAIRED_PDU_IP>`, `<PAIRED_PDU_cUUID>`, `<PAIRED_PDU_AC_FEED>` |
| Status | "Redundant Communication OK" / "Redundant Communication Error" |
| Outlet Control | Grouped redundant outlet control across paired PDUs |
| Requirements | Different power feeds, matching user credentials, matching model |

Error conditions: IP mismatch, power feed mismatch, model mismatch, credential
mismatch, loss of redundant power, exceeded outlet redundancy limits.

### Firmware Module Names

The firmware binary contains a product identification and module table (0x0069_EDD8):

| Address | String | Purpose |
|---------|--------|---------|
| 0x0069_EDD8 | `bootHdr` | Boot header identifier |
| 0x0069_EDE0 | `HP Intelligent PDU Management : Running` | System startup banner |
| 0x0069_EE54 | `HP Intelligent Modular PDU Display Module` | Display unit firmware |
| 0x0069_EF18 | `2.0.51.12` | Firmware version |
| 0x0069_EF24 | `Ipd` | IPD/IPMI protocol module |
| 0x0069_EF28 | `AF528A` | Supported model AF528A |
| 0x0069_EF30 | `AF529A` | Supported model AF529A |
| 0x0069_EF38 | `AF547A` | Supported model AF547A |
| 0x0069_EF40 | `AF475A` | Supported model AF475A |
| 0x0069_EF68 | `Managed Ext. Bar Firmware not found.` | Extension bar firmware load |
| 0x0069_EFBC | `HP AC Module, Single Phase, Intlgnt Firmware not found.` | AC module firmware |

This confirms the firmware supports multiple HP iPDU models and can update extension
bar firmware over the daisy-chain link.

### Serial Port Analysis (from firmware register references)

Searching the decompressed firmware for NS9360 serial port register addresses reveals
which ports are actively used and how they are configured:

| Port | Base Address | Register Refs | Ctrl A Refs | DMA | Usage |
|------|-------------|---------------|-------------|-----|-------|
| Port B | 0x9020_0000 | 14 (7 types) | 6 | Yes | Primary communication (Display Unit?) |
| Port C | 0x9030_0000 | 4 (Ctrl A only) | 4 | Yes | Secondary communication (daisy-chain?) |
| Port A | 0x9020_0040 | 1 (Ctrl A only) | 1 | No | Debug UART (J25, polled/interrupt) |
| Port D | 0x9030_0040 | 1 (Ctrl A only) | 1 | No | Minimal use |

**Port B** has by far the most register references (Control A, Control B, Bit Rate,
Status A, RX Buf Gap Timer, RX Match, RX Match Mask), indicating it is the primary
communication port with full configuration. A peripheral memory region table at 0x757114
maps Port B and Port C into DMA-capable address ranges, while Port A and Port D use
polled or interrupt-driven I/O.

Port B Control A value `0x83030A00` found in literal pool at 0xACC38 -- but this is
written to the FIFO register during init, not to Control A itself. The actual UART
configuration (baud rate, mode) is set through the NET+OS serial driver API.

**DMA Channel Usage** (from deep binary analysis):

| DMA Channel | Base Address | References | Likely Assignment |
|-------------|-------------|------------|-------------------|
| Channel 7 | 0xA070_00E0 | 23 | Port B (primary serial) |
| Channel 15 | 0xA070_01E0 | 7 | Port C (secondary serial) |
| Channel 0 | 0xA070_0000 | 3 | System / other |
| Channel 4 | 0xA070_0080 | 1 | Minimal use |
| Channel 8 | 0xA070_0100 | 1 | Minimal use |

Channel 7's dominant reference count (23) correlates with Port B's heavy usage (14 register refs).
Channel 15's secondary count (7) aligns with Port C's moderate usage (4 refs).

The firmware contains baud rate divisor values for 115200 baud (divisor 23, 47 occurrences)
and 9600 baud (divisor 287, 6 occurrences), suggesting both rates are used.

Key strings: "NS9360 Brookline Board Debug Output Serial port" (Port A/J25),
"Display serial statistics (port 1-4)", "Serial Debug CLI",
"error when change baud rate in Dialog.c", "calibrate maxim voltage" (MAXQ3180 over SPI).

### MAXQ3180 Power Measurement AFE -- SPI Communication

The MAXQ3180 is a 3-phase power/energy measurement Analog Front-End (AFE) from Maxim,
connected to the NS9360 via SPI. It provides voltage, current, power, energy, power
factor and frequency measurements for each load segment.

#### SPI Interface

The firmware uses **DMA-based SPI transfers** to communicate with the MAXQ3180. Four
SPI error strings are present in the firmware:

| Address | String |
|---------|--------|
| 0x0072_1D8C | `spi tx DMA Cache error` |
| 0x0072_1DA4 | `spi rx DMA Cache error` |
| 0x0073_05CC | `spi slave rx DMA Cache error` |
| 0x0073_05EC | `spi slave tx DMA Cache error` |

The presence of both "spi" and "spi slave" error strings suggests the NS9360 may
operate in both SPI master mode (communicating with the MAXQ3180) and SPI slave mode
(communicating with extension bars or daisy-chained units).

NS9360 serial port register reference counts:

| Port | Base Address | Ctrl A Refs | Bit Rate Refs | Likely Role |
|------|-------------|-------------|---------------|-------------|
| Port B | 0x9020_0000 | 6 | 1 | Primary UART (DMA Ch7, display unit) |
| Port C | 0x9030_0000 | 4 | 0 | **Possibly SPI** (DMA Ch15, no Bit Rate ref) |
| Port A | 0x9020_0040 | 1 | 0 | Debug UART (J25, polled) |
| Port D | 0x9030_0040 | 1 | 0 | Minimal use |

**SPI port not yet definitively identified**: SPI B is confirmed disabled (GPIO Config #1
= 0x33333333, all SPI B pins repurposed as GPIO inputs). The firmware uses no named SPI
API calls (no `NSSerialSPIConfig`, `NSSPIConfig`, etc.) — all SPI access is through direct
register manipulation. Port C is the strongest candidate for the MAXQ3180 SPI connection
because it has Control A references but no Bit Rate register references (SPI mode uses a
clock divider in Control A, not the separate Bit Rate register). However, the actual
Control A register values are not accessible from static literal pool analysis alone.

#### Calibration

The firmware implements a voltage and current calibration system for the MAXQ3180,
accessible through the debug CLI:

| CLI Command | Description |
|-------------|-------------|
| `gmcal` | Calibrate maxim voltage |
| `gmcal` (variant) | Calibrate maxim current (p\|c) |
| `gmsave` | Saves calibrated results into FLASH |
| `gmstats` | Reads calibrated results for verification |
| `gmstats2` | Reads secondary PDU metering data |
| `mgain` | Metering Gain Values |

Calibration status strings indicate a multi-step process:

1. **Voltage Calibration** (0x0069_D4AC): "Voltage Calibration Failed" / "Voltage Calibration Completed"
2. **Current Calibration** (0x0069_D4E8): "Current Calibration Failed" / "Current Calibration Completed"
3. **Verify Calibration** (0x0069_D554): "Verify calibration Failed" / "Verify calibration Completed"
4. **Gain Check** (0x0069_D014): "Failed To Read Gain Values" / "Metering Gain Values"

Calibrated results are persisted to NOR flash via `gmsave`, and can be read back with
`gmstats` for verification.

#### Measured Parameters

The MAXQ3180 provides the following measurements (extracted from RIBCL XML responses
and web UI):

| Parameter | XML Tag | Unit |
|-----------|---------|------|
| Total Watts | `<TOTAL_WATTS>` | W |
| Total VA | `<TOTAL_VA>` | VA |
| Total Load Percent | `<TOTAL_LOAD_PERCENT>` | % |
| Voltage | `<VOLTAGE>` | V (VAC) |
| Current | per-outlet / per-segment | A |
| Power Factor | per-segment | ratio |
| Frequency | system | Hz |
| Energy | `<ENERGY>` | Wh |
| KVA Rating | `<KVA_RATING>` | kVA |

Per-segment data is reported via XML with core and load segment IDs:
```xml
<ID CORE="%d" LOAD="%d">
  <WARNING VALUE="%d"/>
  <CRITICAL VALUE="%d"/>
</ID>
```

The web UI formats data as `Core%dr%dVA` (per-core, per-row VA), `Core%dr%dPF`
(power factor), `Core%dr%dc%dPF` (per-core, per-row, per-column).

#### Extension Bar ("Stick") Protocol

The iPDU supports up to 6 extension bars ("sticks") per core, with up to 2 cores.
The firmware has extensive UI support for stick management:

- **spstats**: "Monitored stick protocol statistics" -- debug CLI command
- **mpstats**: "Metering protocol statistics" -- metering data from extension bars
- **detectpins**: "Tests Upstream & Downstream Detect Pins" -- physical link detection
- **Stick Identification**: identification command in debug CLI
- **STICK_HISTORY**: XML tag for per-stick historical data (`<STICK_HISTORY CORE="%d" LOAD="%d">`)

Each stick has:
- UID (Unique ID) LED control (blue indicator, toggled via web UI)
- Per-outlet voltage, current, watts, power factor measurements
- Per-outlet power on/off/cycle control
- Model and part number fields (`LNG_STICK_MODEL`, `LNG_STICK_PARTNUMBER`)

The web UI references arrays for up to 6 load segments/sticks per core:
- `Secondary_Voltage_Array[0..5]` / `Secondary_Current_Array[0..5]` / `Secondary_Load_Array[0..5]`
- `Voltage_Array[0..5]` / `Current_Array[0..5]`
- Color bar visualisation functions: `stick_paintColorBar()`, `stick_paintColorBar2()`,
  `stick_VpaintColorBar2()`

#### IPMI Protocol

An unexpected finding: the firmware includes IPMI (Intelligent Platform Management
Interface) support, revealed by two debug CLI commands:

| CLI Command | Description |
|-------------|-------------|
| `dipd` | Debug IPMI protocol |
| `ipd_dump` | Dump IPD data |

This suggests the iPDU may use IPMI for inter-device communication, possibly with
extension bars or for integration with server management systems.

### I2C Bus Analysis

The NS9360 I2C controller at 0x9050_0000 is **actively used** in the firmware,
with 20 total register references and a semaphore-protected driver:

| Register | Address | References |
|----------|---------|------------|
| I2C Slave Address | 0x9050_0000 | 10 |
| I2C Data | 0x9050_0004 | 2 |
| I2C Status | 0x9050_0008 | 3 |
| I2C Master Address | 0x9050_000C | 5 |

**I2C Driver Strings**:
- `I2C_SEM` (0x0072_1DBC) -- semaphore for bus access serialisation
- `I2C_HOST_SEMAPHORE` (0x0072_1DC4) -- host-level access serialisation
- `i2cHostEvent` (0x0072_1DD8) -- event notification string
- `I2C open failed.` (0x0072_1DE8) -- error handling
- `I2C Bus:` (0x006A_0FD4) -- debug/diagnostic output

The dual semaphore architecture (bus-level + host-level) suggests the I2C bus is accessed
from multiple RTOS threads. The "I2C Bus:" debug string appears in the diagnostic output
region, indicating a debug CLI command can show I2C status.

**I2C device addresses not extractable from static analysis** -- the I2C driver is
generic and takes device addresses as function parameters rather than using hardcoded
immediate values. The driver functions at 0x000BAD74-0x000BB5F0 implement standard
I2C master transactions (start, address, read/write, stop) with the address passed in
a register. Device addresses would need to be traced through function call chains from
the application layer, requiring a decompiler.

Possible I2C devices based on the board design: EEPROM for board identification/serial
number, temperature sensor, or RTC. The test point visible on the PCB near the I2C
pull-up resistors suggests HP used it for manufacturing test.

### Display MCU -- TMP89FM42LUG Serial Communication

The front panel display unit is identified in firmware as "HP Intelligent Modular PDU
Display Module" (0x0069_EE54). It contains a Toshiba TMP89FM42LUG 8-bit TLCS-870/C
microcontroller that manages the 7-segment display, LEDs, and buzzer.

#### Serial Protocol ("Dialog")

Communication with the display MCU is implemented in the firmware source file `Dialog.c`.
The serial port is defined by the `APP_DIALOG_PORT` macro (error message at 0x0072_FF40:
"APP_DIALOG_PORT improperly defined").

The protocol identifier string `HpBlSeR09` (0x0069_D3C0) suggests a proprietary HP
Bezel Serial protocol at revision 09. This string appears alongside firmware update
and hardware discovery messages, indicating it may serve as a handshake/identification
sequence between the main CPU and the display MCU.

Key error string: "error when change baud rate in Dialog.c" (0x0072_FF64) confirms
the serial link operates at a configurable baud rate.

#### Display Capabilities

The front panel display unit provides:

- **7-segment display**: Confirmed by `7seg` CLI command ("Detects 7 segment display")
- **Error LED**: Controllable via CLI ("Turn the error LED on and off (on|off)")
- **UID LEDs**: Blue identification LEDs per stick/outlet (toggled via web UI)
- **Buzzer**: Confirmed by "Please Report The LED Beep Code To Support" (0x0072_19D9)
- **LED Beep Codes**: Error reporting via LED blink patterns and buzzer tones

#### Health Monitoring

The firmware monitors display MCU connectivity as a configurable alarm:

| Event | String |
|-------|--------|
| Display Connected | `Display Connected` (0x006E_1098) |
| Display Disconnected | `Display Disconnected` (0x006E_10AC) |
| Alarm Enable | `Display Communications Alarm Enabled, Please save and reboot` (0x006A_4526) |
| Alarm Disable | `Display Communications Alarm Disabled, Please save and reboot` (0x006A_4676) |

The Display Communication alarm can be toggled via the serial console menu:
"1. Toggle Display Communication On/Off" (under PDU Configuration).

#### Front Bezel Testing (FBT)

Two test initialisation commands exist for the display unit:

| CLI Command | Description | Status Messages |
|-------------|-------------|-----------------|
| `fbt_init` | Enables FBT Testing | "FBT Init Successful" / "FBT Init Failed" |
| `fbt_init2` | Enables Secondary FBT Testing | (same status messages) |

### Firmware Thread Architecture

The firmware binary contains task/thread names that reveal the internal architecture:

| Thread Name | Description |
|-------------|-------------|
| Core Async | Core asynchronous processing |
| Core Proto | Core protocol handler |
| Core DC Proto Task | Core daisy-chain protocol task |
| Core DC Proto Que | Core daisy-chain protocol queue |
| LED Task | LED management task (display MCU communication) |
| LED Module Communication | LED module communication handler |
| Ribcl | RIBCL XML command processing |
| Stick Async | Extension bar asynchronous processing |

### Debug CLI -- Complete Command Reference

The debug CLI is accessible via J25 "Digi UART" header and provides 34+ commands:

#### System Commands

| Command | Description |
|---------|-------------|
| `exit` | Close this debug window |
| `help` | Display this help dialog |
| `reset` | Restart the card |
| `endCLI` | This removes the debug CLI thread |
| `haltRTC` | This Halts the RTC |
| `vers` | Display the firmware version numbers |
| `boot` | Gets the board boot version |

#### Network & Serial

| Command | Description |
|---------|-------------|
| `ips` | Display current interface configuration |
| `nets` | Display network statistics |
| `tnet` | Test the network loopback device (i\|e) |
| `tser` | Test the serial loopback device (port 1-6) |
| `uart` | Display serial statistics (port 1-4) |

#### ThreadX RTOS Inspection

| Command | Description |
|---------|-------------|
| `txev` | List available threadx event flags |
| `txmu` | List available threadx mutexes |
| `txqu` | List available threadx message queues |
| `txse` | List available threadx semaphores |
| `txth` | List available threadx threads |
| `txti` | List available threadx timers |

#### Power Metering & Calibration

| Command | Description |
|---------|-------------|
| `gmcal` | Calibrate maxim voltage |
| `cc` | Calibrate maxim current (p\|c) |
| `gmsave` | Saves calibrated results into FLASH |
| `gmstats` | Reads calibrated results for verification |
| `gmstats2` | Reads secondary PDU metering data |
| `mgain` | Metering Gain Values |

#### Extension Bar & Display

| Command | Description |
|---------|-------------|
| `sd` | Stick Identification |
| `uuid` | UUID test |
| `7seg` | Detects 7 segment display |
| `spstats` | Monitored stick protocol statistics |
| `mpstats` | Metering protocol statistics |
| `detectpins` | Tests Upstream & Downstream Detect Pins |

#### IPMI & NVRAM

| Command | Description |
|---------|-------------|
| `dipd` | Debug IPMI protocol |
| `ipd_dump` | Dump IPD data |
| `w_ser` | Writes NVRAM Serial Number |
| `restoreall` | Restores NVRAM and Logs |

#### Testing

| Command | Description |
|---------|-------------|
| `fbt_init` | Enables FBT Testing |
| `fbt_init2` | Enables Secondary FBT Testing |

### Serial Console Menu Structure

The firmware includes a full serial console menu accessible via telnet or the display
unit's serial connection. Access is restricted to admin users ("ONLY ADMIN USERS WILL
GET ACCESS TO TELNET MENU").

```
Main Menu
├── 1. Network Configuration
│   ├── 1. IPV4 Network Settings
│   │   ├── 1. IPV4 Static Address
│   │   ├── 2. IPV4 Static Subnet Mask
│   │   ├── 3. IPV4 Static Gateway
│   │   ├── 4. IPV4 Toggle Boot Mode
│   │   └── 5. IPV4 Ping Utility
│   ├── 2. IPV6 Network Settings
│   ├── 3. Remote Console
│   ├── 4. Web Access
│   ├── 5. File Transfer (FTP)
│   ├── 6. SNMP
│   ├── 7. Emails
│   ├── 8. Session Settings
│   └── 9. IP Connections
├── 2. System Configuration
│   ├── 1. Date/Time Configuration
│   │   ├── 1. Network Time Protocol (NTP)
│   │   ├── 2. Manual Date/Time
│   │   └── 3. Daylight Savings Time
│   └── (other items)
├── 3. User Accounts
│   ├── 1. Change User Name
│   ├── 2. Change Password
│   ├── 3. Administrator Privilege
│   └── 4. Delete User
├── 4. PDU Configuration
│   ├── 1. Toggle Display Communication On/Off
│   ├── 2. Toggle Topology Discovery On/Off
│   ├── 1. Toggle Outlet Control On/Off
│   ├── 2. Alarm Configuration
│   ├── 3. Reset Energy Measurement Data
│   └── 4. Force Firmware Flash on Secondary Core/Upper Row Core
├── 5. My Account
├── x. Exit Without Saving
├── s. Save New Changes and Restart
└── d. Restore Configuration to Manufacturer Settings
```

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

## NVRAM / Configuration Storage

### Storage Architecture

The firmware uses a multi-layer configuration storage system:

1. **YAFFS Filesystem on NOR Flash** -- persistent file storage
2. **NVRAM Sections** -- structured data with per-section corruption detection
3. **XML Configuration** -- import/export format for configuration backup
4. **KLone Web Framework** -- configuration for the v2.0+ web server

### YAFFS Filesystem

YAFFS (Yet Another Flash File System) v1.6.4.1 (2007) is used for persistent
storage on NOR Flash. Key configuration:

| Parameter | Notes |
|-----------|-------|
| Source | `yaffscfg2k.c,v 1.2.2.10 2007/06/04` |
| Build date | 2018-10-03 13:26:44 (in v2.0.51.12) |
| Author | jlacombe (Digi International) |
| Block size | Reports startBlock, endBlock for partition |
| ECC | YAFFS software ECC (eccFixed/eccUnfixed counters) |
| NOR Flash ID | Reports nManufID, nDeviceID (MX29LV640EB) |
| Endianness | isLittleEndian flag (likely 0 = big-endian) |

YAFFS filesystem paths found in firmware:
- `/etc/kloned.conf` -- KLone web server configuration
- `/etc/kloned.pem` -- SSL/TLS certificate
- `/tmp` -- temporary storage
- `/www/...` -- web content served by KLone
- `/Eventlog.csv` -- event log export

### NVRAM Data Sections

The NVRAM is divided into 12 independently managed sections, each with corruption
detection and factory-default restoration capability. The section names are
derived from the "Restoring Corrupt..." recovery messages:

| # | Section | Description |
|---|---------|-------------|
| 1 | Board Parameters | Hardware-specific: serial number, MAC address, board revision |
| 2 | System Data | System name, contact info, location |
| 3 | Time Data | NTP settings, timezone, DST configuration |
| 4 | Configuration Data | Network settings, DHCP/static IP |
| 5 | SNMP Data | SNMP managers, community strings, trap receivers |
| 6 | User Account Data | Usernames, passwords, admin privileges |
| 7 | Device Data | Outlet device assignments, UUID mappings |
| 8 | Threshold Data | Warning/critical thresholds per load segment |
| 9 | Pairing Data | Redundancy pairing configuration |
| 10 | Event Settings | Event notification configuration |
| 11 | Certificate | SSL/TLS certificate and private key |
| 12 | Rack Data | Rack location, height, row, room information |

NVRAM access is protected by a mutex ("NVRam Mutex") and updates are logged
("NVRAM Update Completed Successfully!"). A corruption detection mechanism
identifies damaged sections and restores them to factory defaults individually.

### NOR Flash Partition Layout (Inferred)

Based on flash address references in the firmware (CS0 at 0x40000000,
CS1 at 0x50000000), the MX29LV640EB (8MB each, 2 chips) has this layout:

| Region | CS0 Address | Flash Offset | Size | Contents |
|--------|------------|--------------|------|----------|
| Boot sector | 0x40000000 | 0x000000 | 64K-128K | Bootloader ROM |
| Application | 0x40020000 | 0x020000 | ~3.5-3.6MB | image.bin (header + LZSS2 data + CRC) |
| Config area | 0x40590000 | 0x590000 | ~2.7MB? | YAFFS / NVRAM storage |
| Second chip | 0x50000000 | -- | 8MB | CS1 (possibly YAFFS continuation) |

Partition-like address references found at code address 0x002A8818:
- 0x40240000 (2304K), 0x40590000 (5696K) -- these may be firmware region boundaries

### XML Configuration Format (config.bin)

The configuration import/export uses an XML format. The root element is
`<PDU_GENERAL_CONFIG>` with product="HP iPDU" and firmware version. The XML
structure maps directly to the NVRAM sections:

```xml
<?xml version="1.0"?>
<PDU_GENERAL_CONFIG PRODUCT="HP iPDU" VERSION="%s">
  <LOGIN USER_LOGIN="%s" PASSWORD="%s">
  <USER_CONFIGURATION>...</USER_CONFIGURATION>
  <NETWORK_SETTINGS>
    <DHCPENABLED/> <STATICENABLED/> <IPv4ADDRESS/>
    <NETMASK/> <DEFAULTGATEWAY/>
    <IPv6LINKLOCALADDRESS/> <IPv6AAUTOCONFIGUREDADDRES/>
  </NETWORK_SETTINGS>
  <NTP_CONFIGURATION>...</NTP_CONFIGURATION>
  <DATE_CONFIGURATION>...</DATE_CONFIGURATION>
  <MANUALTIME_CONFIGURATION>...</MANUALTIME_CONFIGURATION>
  <CONTACT_CONFIGURATION>
    <SYSTEMNAME/> <CONTACTNAME/> <CONTACTNUMBER/>
    <CONTACTEMAIL/> <CONTACTLOCATION/>
  </CONTACT_CONFIGURATION>
  <SNMP_CONFIGURATION>
    <SNMP_MANAGER_%d>
      <ENABLE/> <IP/> <READ_COMMUNITY/>
      <WRITE_COMMUNITY/> <ACCESS_TYPE/>
    </SNMP_MANAGER_%d>
  </SNMP_CONFIGURATION>
  <!-- ...plus TRAP, EMAIL, EVENT, REMOTEACCESS, THRESHOLD,
       OUTLETCONTROL, OUTLETDEVICEASSIGNMENT, RACKLOCATION sections -->
</PDU_GENERAL_CONFIG>
```

A second XML document `<PDU_SPECIFIC_CONFIG>` handles per-outlet and per-load-segment
configuration. These are used by the "Download Configuration" and "Upload Configuration"
web UI features, and correspond to config.bin in the firmware ZIP.

### RIBCL XML Command Interface

The firmware also implements an HP RIBCL (Remote Insight Board Command Language)
compatible XML command interface, similar to HP iLO. Commands include:

- `RESTORE_PDU_FACTORY_DEFAULTS` -- reset all settings
- `GET_PDU_COMMAND_SUPPORT` -- query available commands
- `GET/SET_PDU_SPATIAL_INFO` -- rack location management
- `GET_PDU_PAIRING_TOPOLOGY` -- redundancy topology
- `SET_PDU_REDUNDANCY_CONFIG` -- pairing configuration
- `SET_REMOTE_PDU_REBOOT_FLAG` -- remote reboot
- `PDU_SPECIFIC_CONFIG` -- per-outlet configuration

### Debug CLI Commands

A serial debug CLI (accessible via J25 "Digi UART") provides direct hardware
access including flash and NVRAM operations:

| Command | Description |
|---------|-------------|
| `flash` | Examine data in flash memory (loaddr hiaddr (b\|w\|q)) |
| `mem` | Examine data in memory (hiaddr loaddr (b\|w\|q)) |
| `w_ser` | Writes NVRAM Serial Number |
| `restoreall` | Restores NVRAM and Logs |
| `gmcal` | Calibrate maxim voltage |
| `gmsave` | Saves calibrated results into FLASH |
| `gmstats` | Reads calibrated results for verification |
| `gmstats2` | Reads secondary PDU metering data |
| `boot` | Gets the board boot version |
| `vers` | Display the firmware version numbers |
| `uart` | Display serial statistics (port 1-4) |
| `nets` | Display network statistics |
| `rtc` | Examine real time clock registers |
| `spstats` | Monitored stick protocol statistics |
| `mpstats` | Metering protocol statistics |
| `uuid` | UUID test |
| `7seg` | Detects 7 segment display |
| `detectpins` | Tests Upstream & Downstream Detect Pins |
| `dipd` | Debug IPMI protocol |
| `ipd_dump` | Dump IPD data |

ThreadX RTOS debug commands: `txev` (event flags), `txmu` (mutexes),
`txqu` (message queues), `txse` (semaphores), `txth` (threads), `txti` (timers).

### KLone Web Framework (v2.0+)

Firmware v2.0+ uses the KLone embedded web framework (www.koanlogic.com) alongside
RomPager. KLone configuration is stored at `/etc/kloned.conf` in the YAFFS
filesystem. Key KLone infrastructure:

- `u_config_save_to_buf` -- save config to buffer
- `u_config_do_load_drv` -- load config driver
- `u_config_include` -- include sub-configuration
- `drv_fs_open` -- filesystem driver
- Serves web content from `/www/` prefix (`.kl1` extension = KLone pages)

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

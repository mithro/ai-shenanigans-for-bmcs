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

## Firmware Structure

The firmware is distributed as `image.bin` inside ZIP files with names like
`Henning_<version>_<part>.zip`. The firmware can be flashed via:
1. **Serial Flash Mode**: Through the Display Unit's serial port
2. **FTP Flash Mode**: Over the network via FTP

Known firmware versions (codename "Henning"):

| Version | Date | Notes |
|---------|------|-------|
| 1.1 | ~2010 | Initial release |
| 1.2 | ~2011 | |
| 1.3 | ~2012 | |
| 1.4 | ~2013 | |
| 2.0.0 | ~2014 | Major version bump |
| 2.0.1 | ~2015 | |
| 2.0.2 | ~2016 | |
| 2.0.3 | ~2017 | |
| 2.0.51 | ~2018 | |
| 2.0.51.12 | 2019 | Latest known (Z7550-09130) |

Note: AF531A is NOT listed in the supported models for the latest firmware release.
Supported models are: AF520A, AF521A, AF522A, AF523A, AF525A, AF526A, AF527A,
AF533A, AF901A.

## Firmware Internals (Expected)

Based on the NS9360 platform and NET+ARM SDK:
- **Bootloader**: Likely Digi/NetSilicon bootstrap loader in first flash sector
- **Kernel**: Linux 2.6.x (NET+ARM kernel) or possibly ThreadX RTOS
- **Filesystem**: Could be JFFS2, SquashFS, or CramFS in NOR flash
- **Application**: iPDU management daemon (IPMI-like), web server, SNMP agent

The firmware `image.bin` file likely contains:
1. A header with version info and checksums
2. Kernel image (compressed)
3. Root filesystem image
4. Possibly a separate configuration partition

## Communication Architecture

```
                    Ethernet (RJ-45)
                         |
                    [NS9360 CPU]
                    /    |    \     \
               UART-A  UART-B  SPI   I2C
                |        |      |      |
            Debug     Display  MAXQ   Test
            (J25)     Unit    3180   Point
                       |
                    [MAX3243EI]
                       |
                    RS-232
                       |
                    Serial
                    Console
```

The Display Unit acts as the serial console gateway -- you cannot bypass it for console
access without connecting directly to J25 "Digi UART".

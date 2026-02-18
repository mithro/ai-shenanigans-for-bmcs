# HPE Intelligent Modular PDU -- J1 and J6 Debug Headers

## Summary

J1 and J6 are debug/programming headers on the HP iPDU Core Unit controller board,
likely providing JTAG and/or serial debug access to the Digi NS9360 ARM926EJ-S
processor. They are **not** extension bar bus connectors (the extension bar bus
uses the white connector pairs J2/J29, J3/J30, and J4/J31).

## Physical Description

### J1 -- Large Ribbon-Style Connector

| Property | Value |
|----------|-------|
| Ref Des | J1 |
| Form Factor | Large ribbon-style connector |
| Likely Type | 2x10 (20-pin) 0.100" pitch IDC box header |
| Likely Function | NS9360 ARM JTAG debug header |
| Visible In | [Board photos](https://photos.google.com/share/AF1QipOlajnfRlw4bCdkUFzp4Ti6VZBmPwLn1eyXQCJaOMjkgSEMFuxiXs21xtg1u3QJMA?key=TjdOQno3d2FLbzJYSFhBM3RoZ2RfU2xxclJaT05n) |

J1's large ribbon-style form factor is consistent with the standard 20-pin ARM JTAG
connector used in the NS9360 reference design (labelled "JTAG 20 PIN HEADER" in the
datasheet schematic, specified as `HEADER 10X2.1SP`). The ConnectCore 9P 9360
development board uses an identical 20-pin header (X13) for ARM JTAG debug.

### J6 -- Black 2x5 Pin Header

| Property | Value |
|----------|-------|
| Ref Des | J6 |
| Form Factor | Black 2x5 (10-pin) standard pin header |
| Pitch | Likely 0.100" (2.54 mm) |
| Likely Function | Secondary debug or serial header (see analysis below) |
| Visible In | [Board photos](https://photos.google.com/share/AF1QipOlajnfRlw4bCdkUFzp4Ti6VZBmPwLn1eyXQCJaOMjkgSEMFuxiXs21xtg1u3QJMA?key=TjdOQno3d2FLbzJYSFhBM3RoZ2RfU2xxclJaT05n) |

J6 is a black 2x5 standard pin header. Possible functions include:

- **Reduced JTAG header** -- carrying the 5 essential JTAG signals (TCK, TDI, TDO,
  TMS, TRST_n) plus ground pins, without RTCK/nSRST/DBGRQ/5V
- **Secondary JTAG** -- for programming another device on the board (similar to the
  ConnectCore 9P 9360's X12 "JTAG Booster" header for its CPLD)
- **Serial debug header** -- providing access to one of the NS9360's four serial
  ports with handshaking signals

Board tracing is required to confirm which signals are present on J6.

## NS9360 JTAG Interface

The NS9360 ARM926EJ-S processor has a standard IEEE 1149.1 JTAG interface with ARM
adaptive clocking support (RTCK). The JTAG signals on the NS9360 BGA272 are:

| BGA Pin | Signal | Direction | Pull | Drive | Description |
|---------|--------|-----------|------|-------|-------------|
| G18 | `tck` | Input | None | -- | Test Clock |
| D20 | `tdi` | Input | Internal pull-up | -- | Test Data In |
| G19 | `tdo` | Output | None | 2 mA | Test Data Out |
| F19 | `tms` | Input | Internal pull-up | -- | Test Mode Select |
| F20 | `trst_n` | Input | Internal pull-up | -- | Test Reset (active low) |
| Y4 | `rtck` | I/O | Internal pull-up | 2 mA | Return Test Clock |

Source: NS9360 Datasheet Rev D (91001326_D.pdf), Table 17.

### Debug Mode Enable

ARM debug mode on the NS9360 is controlled by the `bist_en_n` pin (BGA ball V5):

| Mode | `bist_en_n` (V5) | `scan_en_n` (Y3) | `pll_test_n` (U6) |
|------|-------------------|-------------------|--------------------|
| Normal operation | Pull-down (2.4K) | Pull-down (2.4K) | Pull-up |
| ARM debug mode | Pull-up (10K) | Pull-down (2.4K) | Pull-up |

The NS9360 reference design uses a resistor option (R6/R9) to switch between debug
enabled and disabled. The datasheet notes: *"Debug mode must be disabled on customer
units in production."*

The HPE iPDU board has a **"BIST EN"** test point, which corresponds to the
`bist_en_n` signal. On the production board, this is likely pulled low (debug
disabled). To enable JTAG debug, the pull-down would need to be changed to a
pull-up.

### Debug Capabilities

The NS9360's ARM926EJ-S core provides:

- **EmbeddedICE-RT** -- halt-mode debug (hardware breakpoints, watchpoints,
  single-step, register read/write via JTAG)
- **JTAG boundary scan** -- IEEE 1149.1 compliant, with BSDL file available

The NS9360 does **not** have an ETM (Embedded Trace Macrocell) -- no trace port
pins are present in the BGA272 package. Debug is limited to halt-mode JTAG and
UART serial console.

### Standard 20-Pin ARM JTAG Pinout

If J1 follows the standard ARM Multi-ICE 20-pin connector (as used in the NS9360
reference design), its pinout would be:

| Pin | Signal | Pin | Signal |
|-----|--------|-----|--------|
| 1 | VTref (3.3V) | 2 | VCC or NC |
| 3 | nTRST | 4 | GND |
| 5 | TDI | 6 | GND |
| 7 | TMS | 8 | GND |
| 9 | TCK | 10 | GND |
| 11 | RTCK | 12 | GND |
| 13 | TDO | 14 | GND |
| 15 | nSRST | 16 | GND |
| 17 | DBGRQ | 18 | GND |
| 19 | 5V-Supply | 20 | GND |

The NS9360 reference design includes series resistors (e.g., 33 ohm on TDO and
RTCK) and a MAX811 reset monitor for clean reset generation on pin 15 (nSRST).

### Compatible JTAG Debuggers

The NS9360 ARM926EJ-S can be debugged with standard ARM JTAG tools:

- SEGGER J-Link
- Ronetix PEEDI
- Lauterbach TRACE32
- OpenOCD with FTDI-based adapter
- Any ARM Multi-ICE compatible 20-pin debugger

## Relationship to Other Debug Headers

The iPDU controller board has several debug and programming headers. J1 and J6 sit
alongside these other interfaces:

| Ref Des | Label | Function | Processor |
|---------|-------|----------|-----------|
| **J1** | -- | ARM JTAG debug (20-pin ribbon, likely) | NS9360 |
| **J6** | -- | Secondary debug (2x5 black header) | NS9360 or sub-MCU |
| J25 | "Digi UART" | Debug serial console (115200/8/N/1) | NS9360 Serial Port A |
| J11 | "Mox SPI" | SPI bus access | MAXQ3180 or SPI flash |
| J10 | "PIC JTAG" | Sub-MCU JTAG/programming | TMP89FM42LUG or other |
| J27 | "I2C" | I2C bus header | NS9360 I2C bus |
| -- | "BIST EN" | Debug mode enable test point | NS9360 `bist_en_n` (V5) |

### Extension Bar Bus Connectors (Not J1/J6)

The extension bar bus uses **white connector pairs** on the board:

| Connector Pair | Function |
|----------------|----------|
| J2 / J29 | Extension bar bus connector pair |
| J3 / J30 | Extension bar bus connector pair |
| J4 / J31 | Extension bar bus connector pair |

These white connector pairs are separate from J1 and J6 and carry signals between
the controller board and the power distribution / outlet section of the Core Unit.

## Open Investigation Items

The following require physical board access to confirm:

- [ ] Verify J1 pinout matches standard 20-pin ARM JTAG (probe against NS9360 BGA
  pins G18/D20/G19/F19/F20/Y4)
- [ ] Determine J6 function -- trace pins to identify connected signals (JTAG,
  serial, or other)
- [ ] Check if J6 connects to the NS9360 or to another device (TMP89FM42LUG
  sub-MCU, MAXQ3180, etc.)
- [ ] Determine if J1 is populated or just an unpopulated footprint on production
  boards
- [ ] Check the `bist_en_n` resistor configuration -- is debug mode enabled or
  disabled on this board?
- [ ] Determine the exact connector part numbers for J1 and J6
- [ ] Attempt JTAG connection via J1 to confirm functionality and read NS9360
  device ID via boundary scan
- [ ] Check if the NS9360 TRST_n line is properly pulsed at boot (required when
  debugger is not attached)

## References

- [NS9360 Datasheet Rev D](https://ftp1.digi.com/support/documentation/91001326_D.pdf)
  -- Table 17 (JTAG pinout), Figure 6 (reference design JTAG schematic)
- [NS9360 Hardware Reference Manual Rev J](https://ftp1.digi.com/support/documentation/90000675_J.pdf)
  -- JTAG interface section, test/debug registers
- [ConnectCore 9P 9360 Hardware Reference](https://ftp1.digi.com/support/documentation/90000769_C.pdf)
  -- X13 (standard ARM JTAG) and X12 (JTAG Booster) headers
- [ANALYSIS.md](ANALYSIS.md) -- Full board component inventory and NS9360 I/O
  architecture
- [RESOURCES.md](RESOURCES.md) -- Datasheets and documentation links
- [STATUS.md](STATUS.md) -- Project status and open items
- [Board Photos](https://photos.google.com/share/AF1QipOlajnfRlw4bCdkUFzp4Ti6VZBmPwLn1eyXQCJaOMjkgSEMFuxiXs21xtg1u3QJMA?key=TjdOQno3d2FLbzJYSFhBM3RoZ2RfU2xxclJaT05n)
  -- Google Photos album "HP PDU AF520A Core Parts"

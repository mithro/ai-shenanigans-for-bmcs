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

### Power Pins on the 20-Pin Header

The JTAG header **cannot** power the target board. The two power-related pins
serve reference and adapter purposes only:

| Pin | Signal | Purpose |
|-----|--------|---------|
| 1 | VTref | **Voltage reference input** -- driven by the *target board* to tell the debugger what logic level to use (3.3V on the iPDU). This is not a power input to the target. |
| 19 | 5V-Supply | **Debugger adapter power** -- optional 5V from the debugger, intended to power small adapter circuits (e.g., level shifters on a debug adapter board). Current capacity is minimal (typically <100 mA). Not for powering the target. |

The NS9360, its 32 MB SDRAM, 16 MB NOR flash, and support circuitry draw far more
power than any JTAG debugger or RPi GPIO header could supply. The iPDU board
**must** be powered from its own mains AC power supply for JTAG debugging to work.

In practice: plug in and power up the iPDU first, then connect the JTAG debugger.
The VTref pin on J1 lets the debugger (or OpenOCD on the RPi) detect that the
target is powered and at what voltage level.

### Compatible JTAG Debuggers

The NS9360 ARM926EJ-S uses the **EmbeddedICE-RT** debug architecture, accessed via
raw JTAG scan chains. This is fundamentally different from the **CoreSight DAP**
(ADIv5) used by modern Cortex-M/A/R processors. Any debugger must support legacy
ARM9 JTAG -- adapters that only speak CoreSight DAP (such as CMSIS-DAP probes)
**will not work**.

The 20-pin ARM JTAG header accepts any standard ARM Multi-ICE compatible debugger.
These connect via a 20-pin IDC ribbon cable.

**Dedicated ARM JTAG debuggers:**

| Debugger | Interface | ARM926EJ-S | RTCK | Software | Notes |
|----------|-----------|------------|------|----------|-------|
| SEGGER J-Link | USB | Yes | Yes (adaptive clocking) | J-Link GDB Server (best), OpenOCD, J-Link Commander | Best option; handles ARM9 caches natively via JTAG without target code |
| Lauterbach TRACE32 | USB/Ethernet | Yes | Yes | TRACE32 IDE | High-end professional tool |
| Ronetix PEEDI | Ethernet | Yes | Yes | GDB, Telnet | Network-attached JTAG; good for remote/headless setups |
| Amontec JTAGkey | USB (FT2232) | Yes | Yes | OpenOCD | Confirmed working with NS9360 ([OpenOCD mailing list](https://sourceforge.net/p/openocd/mailman/message/28340950/)) |

**FTDI-based generic adapters:**

| Adapter | Chip | ARM926EJ-S | RTCK | Notes |
|---------|------|------------|------|-------|
| TIAO TUMPA (TIMO1499) | FT2232H | Yes | Yes | Ships with 20-pin ARM JTAG header; [OpenOCD config](https://github.com/arduino/OpenOCD/blob/master/tcl/interface/ftdi/tumpa.cfg) included |
| Dangerous Prototypes Bus Blaster | FT2232H | Yes | Yes | Open hardware |
| Olimex ARM-USB-OCD | FT2232 | Yes | Yes | Widely available |
| Generic FT2232H breakout | FT2232H | Yes | Yes | Cheapest option; requires OpenOCD config |
| Generic FT232H breakout | FT232H | Yes | No | Single-channel variant; no RTCK |

All FTDI-based adapters use OpenOCD's `ftdi` interface driver and connect to the
20-pin header via ribbon cable. The FT2232**H** (high-speed) variants support
adaptive clocking (RTCK) via the MPSSE engine; older FT2232C/D do not.

**SBC-based GPIO bitbang adapters:**

Any single-board computer with GPIO and OpenOCD support can bitbang the JTAG
protocol. See the Raspberry Pi Zero W section below.

### Incompatible Debugger Types

The following adapter types **cannot** debug the NS9360 ARM926EJ-S:

| Adapter Type | Example | Why It Fails |
|-------------|---------|--------------|
| **CMSIS-DAP** | IDAP-Link, DAPLink, any "CMSIS-DAP" probe | CMSIS-DAP protocol only speaks CoreSight DAP (ADIv5 DP/AP registers). ARM926EJ-S has no CoreSight DAP -- it uses EmbeddedICE-RT accessed via raw JTAG scan chains. The protocol has no mechanism for arbitrary IR/DR scans. |
| **SWD-only probes** | ST-Link (SWD mode), Black Magic Probe (SWD mode) | SWD (Serial Wire Debug) is a CoreSight-era 2-wire protocol. ARM926EJ-S only supports JTAG. Some probes (like ST-Link V2) have a JTAG mode, but it is limited to Cortex targets via CoreSight DAP. |
| **Keil ULINK2** (limited) | ULINK2, ULINK-ME | Technically supports ARM9 JTAG, but **locked to Keil uVision/MDK IDE** -- no OpenOCD driver, no GDB server, no open-source toolchain support. Requires Keil MDK license. RTCK support is unclear. Only useful if you already have a Keil MDK setup with NS9360 device support. |

The distinction is architectural: EmbeddedICE-RT (ARM7/ARM9) debug requires the
host to perform raw JTAG scan chain operations (IR scan, DR scan) to access
EmbeddedICE registers. CoreSight DAP (Cortex) debug works at a higher abstraction
level through DAP register reads/writes (CSW, TAR, DRW). A CoreSight-only adapter
literally cannot form the JTAG commands needed to talk to an ARM926EJ-S.

### Recommended Adapter for This Project

For the NS9360 iPDU board, the recommended adapters in order of preference:

1. **SEGGER J-Link** -- Use with J-Link GDB Server for best performance. Supports
   RTCK adaptive clocking, handles ARM9 I-Cache/D-Cache coherency natively via
   JTAG (no target-side code needed), and works with standard `arm-none-eabi-gdb`.
   The J-Link EDU (~$60) is sufficient for non-commercial use.

2. **TIAO TUMPA** -- Use with OpenOCD. Same FT2232H chip family as the Amontec
   JTAGkey confirmed working with the NS9360. Ships with the 20-pin ARM JTAG
   header and has an OpenOCD config file (`interface/ftdi/tumpa.cfg`) included in
   the OpenOCD distribution. Requires writing an NS9360 target config (see the
   [OpenOCD configuration section](#openocd-configuration-for-ns9360-via-rpi-zero-w)
   for the target definition).

3. **Raspberry Pi Zero W** -- Use with OpenOCD `bcm2835gpio` driver. See the
   [dedicated section below](#using-a-raspberry-pi-zero-w-as-a-remote-jtag-adapter)
   for wiring and configuration. Best for persistent remote debug access.

## Using a Raspberry Pi Zero W as a Remote JTAG Adapter

A Raspberry Pi Zero W can serve as a wireless, network-accessible JTAG debug
adapter for the NS9360 by bitbanging the JTAG protocol through its GPIO pins
using OpenOCD. This is a practical approach for this project since the Pi can be
mounted near or inside the iPDU chassis for persistent remote debug access.

### Why the RPi Zero W is a Good Fit

- **3.3V GPIO** -- the RPi Zero W GPIO runs at 3.3V, directly level-compatible
  with the NS9360's 3.3V JTAG signals; no level shifter needed
- **Built-in WiFi** -- provides wireless access without extra hardware
- **OpenOCD runs natively** -- the Pi acts as both the JTAG adapter and the
  OpenOCD host; no USB link to a separate computer
- **Network GDB** -- OpenOCD exposes a GDB server over TCP, allowing any
  workstation on the network to connect for debugging
- **Small form factor** -- the Pi Zero W can fit inside or next to the PDU chassis

### OpenOCD GPIO Driver Options

| Driver | Method | Speed | RPi Zero W |
|--------|--------|-------|------------|
| `bcm2835gpio` | Direct BCM2835 peripheral register access | Fastest | Best choice (native BCM2835) |
| `sysfsgpio` | Linux sysfs `/sys/class/gpio` | Slower | Works, portable |
| `linuxgpiod` | Linux libgpiod | Medium | Works on newer kernels |

The `bcm2835gpio` driver directly accesses the BCM2835 GPIO peripheral registers
for maximum bitbang speed and is the recommended choice for the Pi Zero W.

### Wiring: RPi Zero W GPIO to J1 (20-Pin ARM JTAG)

Using the pin assignments from OpenOCD's `raspberrypi-native.cfg`:

| JTAG Signal | J1 Pin | RPi GPIO | RPi Header Pin | Direction (from Pi) |
|-------------|--------|----------|----------------|---------------------|
| TCK | 9 | GPIO 11 (SPI0_SCLK) | 23 | Output |
| TMS | 7 | GPIO 25 | 22 | Output |
| TDI | 5 | GPIO 10 (SPI0_MOSI) | 19 | Output |
| TDO | 13 | GPIO 9 (SPI0_MISO) | 21 | Input |
| nTRST | 3 | GPIO 7 (SPI0_CE1) | 26 | Output |
| nSRST | 15 | GPIO 24 | 18 | Output |
| GND | 4,6,8,10,12,14,16,18,20 | GND | 6,9,14,20,25 | -- |
| VTref | 1 | 3.3V | 1 | Input (reference only) |

Note: VTref on J1 pin 1 is a voltage reference input to the debugger, not a power
supply. Connect it to the Pi's 3.3V pin so OpenOCD can detect the target voltage.
Do **not** attempt to power the iPDU board from the Pi.

### Building OpenOCD on the RPi Zero W

```bash
# Install dependencies
sudo apt-get install git autoconf libtool make pkg-config libusb-1.0-0-dev

# Clone and build OpenOCD with BCM2835 GPIO support
git clone https://git.code.sf.net/p/openocd/code openocd
cd openocd
./bootstrap
./configure --enable-bcm2835gpio --enable-sysfsgpio
make -j1    # Pi Zero W is single-core
sudo make install
```

### OpenOCD Configuration for NS9360 via RPi Zero W

Create a file `ns9360-rpi.cfg`:

```tcl
# Interface: Raspberry Pi Zero W GPIO bitbang
adapter driver bcm2835gpio
bcm2835gpio_peripheral_base 0x20000000    # BCM2835 (Pi Zero/1) base
bcm2835gpio_speed_coeffs 113714 28        # Calibrated for Pi Zero W clock

# JTAG pin assignments (BCM GPIO numbers)
bcm2835gpio_jtag_nums 11 25 10 9          # TCK TMS TDI TDO
bcm2835gpio_trst_num 7                    # nTRST
bcm2835gpio_srst_num 24                   # nSRST

# Transport and speed
transport select jtag
adapter speed 1000                        # 1 MHz, start conservative

# NS9360 JTAG TAP
set _CHIPNAME ns9360
jtag newtap $_CHIPNAME cpu -irlen 4 \
    -ircapture 0x9 -irmask 0x0f \
    -expected-id 0x09105031

# ARM926EJ-S target
set _TARGETNAME $_CHIPNAME.cpu
target create $_TARGETNAME arm926ejs \
    -endian little -chain-position $_TARGETNAME

# Reset configuration
reset_config trst_and_srst
```

Source for NS9360 JTAG TAP parameters: [OpenOCD mailing list](https://sourceforge.net/p/openocd/mailman/message/28340950/)
(IRLen=4, IDCODE=0x09105031, confirmed with Amontec JTAGkey).

### Running OpenOCD and Connecting Remotely

```bash
# On the Raspberry Pi Zero W:
sudo openocd -f ns9360-rpi.cfg -c "bindto 0.0.0.0"

# From any workstation on the network:
arm-none-eabi-gdb
(gdb) target remote <pi-zero-ip>:3333
(gdb) monitor reset halt
(gdb) monitor mdw 0x00000000 16          # Read first 64 bytes of flash
```

OpenOCD listens on three ports by default:

| Port | Protocol | Purpose |
|------|----------|---------|
| 3333 | GDB Remote Serial Protocol | GDB debugging |
| 4444 | OpenOCD Telnet | Interactive OpenOCD commands |
| 6666 | OpenOCD TCL | Scripted access |

By default OpenOCD only listens on localhost. The `-c "bindto 0.0.0.0"` flag is
required to accept remote connections over WiFi.

### Known NS9360 OpenOCD Issue

An [OpenOCD mailing list thread](https://sourceforge.net/p/openocd/mailman/message/28340950/)
reported an error with the NS9360:

> unknown EmbeddedICE version (comms ctrl: 0x00000000)

This likely indicates that ARM debug mode is disabled in hardware. On the iPDU
board, check the **"BIST EN"** test point -- if `bist_en_n` is pulled low (normal
operation mode), the EmbeddedICE registers will be inaccessible and read as all
zeros. The fix is to change the `bist_en_n` pull-down to a pull-up (see the
[Debug Mode Enable](#debug-mode-enable) section above).

### Alternative: Raspberry Pi as USB Gadget Serial + UART

If JTAG debug is not feasible (e.g., `bist_en_n` cannot be changed), the RPi
Zero W can alternatively be used as a WiFi-to-serial bridge for the J25 "Digi UART"
debug console. The Pi Zero W's UART (GPIO 14 TX / GPIO 15 RX) can be wired directly
to J25 at 115200/8/N/1 and accessed remotely via `ser2net`, `socat`, or an SSH
session running `minicom`.

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

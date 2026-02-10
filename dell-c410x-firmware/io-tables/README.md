# Dell C410X BMC IO Table Files

## What Is This?

The **Dell PowerEdge C410X** is a 16-slot PCIe expansion chassis designed to hold GPUs
and other accelerator cards. It has no CPU or memory of its own -- it connects to a host
server via PCIe cables and provides power, cooling, and management for up to 16 PCIe
cards.

The chassis contains a **Baseboard Management Controller (BMC)** -- a small embedded
computer (Aspeed AST2050 SoC, ARM9 core) running Linux that monitors temperatures,
fan speeds, power consumption, and card presence for all 16 slots. The BMC communicates
with administrators over Ethernet using the **IPMI protocol** (Intelligent Platform
Management Interface), allowing remote monitoring and control even when the host server
is powered off.

The BMC firmware is built on the **Avocent MergePoint** platform (Avocent is now part
of Vertiv). Rather than hardcoding hardware configuration into the firmware binary, the
MergePoint platform uses a set of **binary configuration tables** that describe the
complete hardware layout. These tables tell the firmware what sensors exist, where they
are on the I2C bus, which GPIO pins control what, and how to read each device.

This directory contains reverse-engineered documentation for each of these table files,
extracted from firmware version 1.35 (`BM3P135.pec`).

## Where Do These Files Live?

On the BMC's root filesystem (SquashFS), in:
```
/etc/default/ipmi/evb/
```

The file `bmcsetting` in that directory maps logical names to file paths:
```
[IOTABLE]   -> IO_fl.bin
[IOSTABLE]  -> IS_fl.bin
[IOXTABLE]  -> IX_fl.bin
[FTTABLE]   -> FunctionTable.bin  (= FT_fl.bin)
[DEFAULT]   -> oemdef.bin
[SDR]       -> NVRAM_SDR00.dat
```

## How the Tables Work Together

When the BMC firmware starts, its main engine (`sbin/fullfw`, a ~1.2MB ELF binary)
loads these tables in a specific order. Together, they form a layered system:

```
  IPMI Commands from the network (e.g., "read sensor 0x50")
         |
         v
  +----------------------------------------------+
  |  IS_fl.bin -- Sensor Table                    |
  |                                               |
  |  "Sensor 0x50 (PCIE 1 Watt) is read using    |
  |   the INA219 power driver, talking to the     |
  |   I2C device at address 0x40 on bus 0xF0"     |
  +----------------------------------------------+
         |
         |  (For some operations, an extra lookup step)
         v
  +----------------------------------------------+
  |  IX_fl.bin -- Index Table                     |
  |                                               |
  |  Maps a compact index number to a specific    |
  |  driver type + sub-index, so the firmware     |
  |  can find the right hardware entry without    |
  |  knowing the physical layout.                 |
  +----------------------------------------------+
         |
         v
  +----------------------------------------------+
  |  IO_fl.bin -- Master IO Table                 |
  |                                               |
  |  192 entries describing every piece of        |
  |  hardware the BMC talks to: GPIO pins, I2C    |
  |  devices, LEDs, fans, PSUs, serial ports,     |
  |  Ethernet, NVRAM. Each entry includes a       |
  |  pointer to the correct driver.               |
  +----------------------------------------------+
         |
         v
  +----------------------------------------------+
  |  FT_fl.bin -- Driver Configuration            |
  |                                               |
  |  One byte per driver type. Tells each driver  |
  |  how many channels to enable, which I2C mux   |
  |  channels are populated, etc.                 |
  +----------------------------------------------+

  +----------------------------------------------+
  |  oemdef.bin -- Factory Defaults               |
  |                                               |
  |  Default IP address (192.168.0.120), default  |
  |  credentials (root/root), serial port config, |
  |  SNMP community ("public"), alert filters.    |
  |  Used when NVRAM is blank or after a reset.   |
  +----------------------------------------------+
```

## File Reference

| File | Size | What It Contains | Details |
|------|------|-----------------|---------|
| [IO_fl.bin](IO_fl.bin.md) | 2,456 bytes | 192 hardware device entries | Every GPIO pin, I2C device, LED, fan, PSU, and communication channel |
| [IS_fl.bin](IS_fl.bin.md) | 1,590 bytes | 72 sensor definitions | Maps each IPMI sensor number to its physical hardware |
| [IX_fl.bin](IX_fl.bin.md) | 344 bytes | 85 index cross-references | Indirection layer decoupling sensor IDs from hardware layout |
| [FT_fl.bin](FT_fl.bin.md) | 26 bytes | 24 driver config bytes | Per-driver settings (fan zones, I2C mux channels, etc.) |
| [oemdef.bin](oemdef.bin.md) | 1,710 bytes | 100 factory default values | Network config, credentials, serial port, alert filters |

### Supporting Files (not documented in detail)

| File | What It Contains |
|------|-----------------|
| `NVRAM_SDR00.dat` | IPMI Sensor Data Records -- 73 records defining sensor names, units, and thresholds |
| `NVRAM_FRU00.dat` | Field Replaceable Unit data -- chassis model/serial number |
| `NVRAM_Storage00.dat` | Persistent NVRAM storage -- runtime settings that survive reboots |
| `bmcsetting` | Text file mapping section names to binary file paths |
| `ID_devid.bin` | Device ID for IPMI Get Device ID command |
| `FI_fwid.bin` | Firmware version string |

## Hardware at a Glance

### What the BMC Monitors

| What | How Many | Sensor Type | Hardware |
|------|----------|-------------|----------|
| Board temperatures | 6 zones | Analog (degrees C) | ADT7462 thermal management ICs |
| GPU slot temperatures | 16 slots | Analog (degrees C) | TMP100 sensors, one per slot |
| Front board temperature | 1 | Analog (degrees C) | Dedicated sensor |
| Fan speeds | 8 fans | Analog (RPM) | ADT7462 tachometer inputs |
| GPU slot power draw | 16 slots | Analog (watts) | INA219 current/power sensors |
| PSU power output | 4 PSUs | Analog (watts) | PMBus protocol |
| GPU slot card presence | 16 slots | Discrete (yes/no) | PCA9555 GPIO expanders |
| PSU presence | 4 PSUs | Discrete (yes/no) | PCA9555 GPIO expanders |
| System power state | 1 | Discrete | GPIO |
| **Total** | **72 sensors** | | |

### Physical I2C Bus Layout

The BMC talks to all these sensors over four I2C buses, using multiplexers to reach
devices that would otherwise have conflicting addresses:

```
Aspeed AST2050 BMC SoC
|
+-- I2C Bus 0xF0: Power monitoring
|   |
|   +-- INA219 @ 0x40 -- Slot 1 power     Each INA219 has a shunt
|   +-- INA219 @ 0x41 -- Slot 2 power     resistor on the 12V rail
|   +-- ...                                to its PCIe slot, measuring
|   +-- INA219 @ 0x4F -- Slot 16 power    current and computing watts.
|
+-- I2C Bus 0xF1: Fan and board temperature control
|   |
|   +-- PCA9544A mux @ 0x70 (4-channel I2C multiplexer)
|   |   |
|   |   +-- Channel via 0xB0 --> ADT7462 #1
|   |   |   Monitors: Board Temp 1-3, controls: Fan 1, 2, 5, 6
|   |   |
|   |   +-- Channel via 0xB8 --> ADT7462 #2
|   |       Monitors: Board Temp 4-6, controls: Fan 3, 4, 7, 8
|   |
|   +-- PCA9555 @ 0x20 -- Additional GPIO/status signals
|
+-- I2C Bus 0xF4: Per-slot temperature sensing
|   |
|   +-- PCA9548 mux #1 (8-channel I2C multiplexer)
|   |   +-- Ch 0: TMP100 -- Slot 1 temp    All TMP100 sensors share
|   |   +-- Ch 1: TMP100 -- Slot 2 temp    the same I2C address (0x5C).
|   |   +-- ...                             The mux ensures only one
|   |   +-- Ch 7: TMP100 -- Slot 8 temp    is on the bus at a time.
|   |
|   +-- PCA9548 mux #2 (8-channel I2C multiplexer)
|       +-- Ch 0: TMP100 -- Slot 9 temp
|       +-- ...
|       +-- Ch 7: TMP100 -- Slot 16 temp
|
+-- I2C Bus 0xF6: Slot management and front board
|   |
|   +-- PCA9555 @ 0x20 -- Slots 1-8 card presence (16 GPIO pins)
|   +-- PCA9555 @ 0x21 -- Slots 9-16 card presence
|   +-- PCA9555 @ 0x22 -- Slot power enable/disable control
|   +-- PCA9555 @ 0x23 -- Slot status LEDs and signals
|   +-- Front board temp sensor @ 0x9E
|
+-- I2C Bus 0xF2: Non-volatile storage
|   +-- 24Cxx EEPROM @ 0xA0 (FRU data, serial numbers)
|
+-- PMBus: Power supply management
    +-- PSU 1-4 (hot-swappable, communicate power/status via PMBus protocol)
```

### GPIO Pin Usage

The AST2050 has on-chip GPIO organized into port groups of 8 pins each. The firmware
uses 38 on-chip GPIO pins across four groups:

| GPIO Group | Register Base | Pins Used | Primary Function |
|------------|---------------|-----------|-----------------|
| GPIOA-D | 0x1E780000 | 10 | Interrupt-enabled inputs (sensor alerts, hardware events) |
| GPIOE-H | 0x1E780020 | 7 | Mixed I/O (I2C interrupt lines, status signals) |
| GPIOI-L | 0x1E780070 | 16 | Data lines for PCIe/system status monitoring |
| GPIOM-P | 0x1E780078 | 5 | System control outputs (power control, resets) |

In addition, five PCA9555 I2C GPIO expander chips provide 80 more GPIO pins for PCIe
slot management (presence detect, power control, status LEDs).

## Key Design Observations

1. **The C410X is all about PCIe slots.** Of 72 sensors, 48 (two-thirds) are dedicated
   to monitoring the 16 PCIe slots: temperature, power, and presence for each one.

2. **Massive I2C multiplexing.** 16 identical TMP100 temperature sensors all share the
   same I2C address, so two 8-channel PCA9548 multiplexers select one at a time. Similarly,
   the two ADT7462 chips share an address and sit behind a PCA9544A mux.

3. **Table-driven, not hardcoded.** The `fullfw` binary is generic Avocent MergePoint
   code. All Dell C410X-specific hardware details live in these table files. In theory,
   the same binary could manage a completely different board by swapping the tables.

4. **Two-tier driver model.** Low-level hardware access (reading an I2C register, toggling
   a GPIO pin) is handled by **IOAPI** drivers. Higher-level sensor operations (converting
   a raw ADC value to degrees Celsius) are handled by **IOSAPI** drivers. This separation
   lets the same I2C driver serve both temperature and fan speed readings from the same chip.

## Firmware Loading Sequence

The `HWInit()` function in fullfw loads the tables in this order:

| Step | Function | File | What It Does |
|------|----------|------|-------------|
| 1 | `HWInitIOTableV3()` | IO_fl.bin | Loads master hardware map |
| 2 | `HWInitIOSensorTable()` | IS_fl.bin | Loads sensor definitions |
| 3 | `HWInitSmartIOIndexTable()` | IX_fl.bin | Loads index cross-references |
| 4 | `HWInitFunctionTable()` | FT_fl.bin | Loads driver configuration |
| 5 | `HWInitTOC()` | (internal) | Initializes table of contents |
| 6 | `HWInitFWInfo()` | FI_fwid.bin | Reads firmware version |
| 7 | `HWInitNVRAMSubSystem()` | NVRAM files | Sets up persistent storage |
| 8 | `HWLoadDefaultValueTable()` | oemdef.bin | Loads factory defaults |

## Factory Defaults (from oemdef.bin)

| Setting | Default Value |
|---------|---------------|
| IP Address | 192.168.0.120 |
| Subnet Mask | 255.255.255.0 |
| IP Source | DHCP |
| Username | root |
| Password | root |
| SNMP Community | public |
| Serial Over LAN | Enabled, 115200 baud |
| Serial Console | 115200 baud, 8N1 |

## How This Was Reverse Engineered

1. Firmware image (`BM3P135.pec`) extracted using binwalk to get the SquashFS root filesystem
2. The `fullfw` ELF binary was disassembled (ARM926EJ-S instruction set) to find the
   table-loading functions and understand field meanings
3. Symbol names were extracted from the ELF's symbol table (the binary was not stripped)
4. Binary table files were decoded by cross-referencing the parsing code with the raw data
5. IPMI Sensor Data Records (SDR) were parsed to get human-readable sensor names
6. I2C device datasheets (ADT7462, TMP100, INA219, PCA9555, PCA9544A, PCA9548) were
   consulted to verify register addresses and device behavior

## Related Files

- [../ANALYSIS.md](../ANALYSIS.md) -- Full firmware reverse engineering analysis
- [../RESOURCES.md](../RESOURCES.md) -- Firmware download links and Dell documentation

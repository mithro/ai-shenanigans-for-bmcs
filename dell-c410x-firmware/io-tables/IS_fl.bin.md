# IS_fl.bin -- Sensor Table

## What This File Does

IS_fl.bin tells the BMC firmware how to read each of its 72 sensors. When an IPMI
"Get Sensor Reading" command arrives (or the sensor polling loop runs), the firmware
looks up the sensor number in this table to find out:

- Which **I2C bus** and **device address** to talk to
- Which **register** to read on that device
- Which **I2C mux channel** to select first (if the device is behind a multiplexer)
- Which **IOSAPI driver** knows how to interpret the raw hardware value and convert
  it into meaningful units (degrees C, RPM, watts, etc.)

This is the bridge between IPMI sensor numbers (abstract identifiers like 0x50 for
"PCIE 1 Watt") and the physical hardware (INA219 power sensor at I2C address 0x40
on bus 0xF0).

| Property | Value |
|----------|-------|
| **Location on BMC filesystem** | `/etc/default/ipmi/evb/IS_fl.bin` |
| **bmcsetting section name** | `[IOSTABLE]` |
| **Size** | 1,590 bytes |
| **Loading function in fullfw** | `HWInitIOSensorTable()` |

## File Structure

```
Bytes 0-3:       Header (version, sensor counts)
Bytes 4-1587:    72 sensor entries, 22 bytes each
Bytes 1588-1589: Footer (0xBF 0x33)
```

### Header

| Byte | Value | Meaning |
|------|-------|---------|
| 0 | 0x01 | Table version 1 |
| 1 | 0x00 | Reserved |
| 2 | 0x33 (51) | Number of **analog sensor** slots (temperature, fan, power) |
| 3 | 0x15 (21) | Number of **discrete sensor** slots (presence detect, power state) |

Total: 51 + 21 = 72 sensors.

### Entry Format (22 bytes each)

Each entry contains a mix of IPMI metadata and hardware addressing. The most important
fields are:

| Offset | Size | Field | Meaning |
|--------|------|-------|---------|
| 0 | 1 | Sensor number | The IPMI sensor number (e.g., 0x50 for "PCIE 1 Watt") |
| 1 | 1 | Sensor flags | Reading type: 0x04=threshold analog, 0x05=tachometer, 0x03=power, 0x01=discrete |
| 14-15 | 2 | I2C device + bus | Low byte = device address, high byte = I2C bus ID |
| 16 | 1 | Register / mux index | Which register to read, or which mux channel to select |
| 18-21 | 4 | IOSAPI driver pointer | Address of the sensor-reading driver vtable in fullfw |

Bytes 2-13 contain IPMI entity information (owner ID, entity ID, configuration
parameters) that are mostly common across all entries.

## IOSAPI Drivers -- How Sensor Readings Work

Unlike IO_fl.bin's IOAPI drivers (which handle raw hardware access), IOSAPI drivers
handle the **sensor-level logic**: selecting the right I2C mux channel, reading the
device register, and converting the raw value into IPMI sensor units.

| IOSAPI Driver | Address in fullfw | What It Reads |
|---------------|-------------------|---------------|
| ADT7462 Temperature | 0x000fcbcc | Temperature registers on ADT7462 chips |
| ADT7462 Fan | 0x000fcbdc | Fan tachometer registers on ADT7462 chips |
| TMP100 Temperature | 0x000fcbfc | TMP100 I2C temperature sensors (via PCA9548 mux) |
| INA219 Power | 0x000fcc0c | Power register on INA219 current sensors |
| Front Board Temperature | 0x000fc344 | Special front-board temperature sensor |
| PMBus PSU | 0x000fc3d4 | Power supply wattage via PMBus protocol |
| PCIe Presence | 0x0010a5a8 | GPIO-based PCIe card presence detection |
| PSU Presence | 0x0010a5b0 | GPIO-based power supply presence detection |
| System Power Monitor | 0x0010a5b8 | System power state GPIO |

## All 72 Sensors Decoded

### Board Temperature -- ADT7462 Chips (Sensors 0x01-0x06)

Six temperature readings from two ADT7462 thermal management ICs. The ADT7462 is a
multi-channel temperature monitor that also controls fans. Each chip provides three
temperature readings: two from external thermal diodes ("Remote Temp 1" and "Remote
Temp 2") and one from its own internal sensor ("Local Temp").

| Sensor# | Name | Chip | I2C Mux Select | Register | What It Measures |
|---------|------|------|---------------|----------|-----------------|
| 0x01 | Board Temp 1 | ADT7462 #1 (bus 0xF1, mux 0xB0) | PCA9544A ch 0 | 0x8B (Remote Temp 1) | External diode near board region 1 |
| 0x02 | Board Temp 2 | ADT7462 #1 | same | 0x8D (Remote Temp 2) | External diode near board region 1 |
| 0x03 | Board Temp 3 | ADT7462 #1 | same | 0x8F (Local Temp) | ADT7462 #1 die temperature |
| 0x04 | Board Temp 4 | ADT7462 #2 (bus 0xF1, mux 0xB8) | PCA9544A ch 1 | 0x8B (Remote Temp 1) | External diode near board region 2 |
| 0x05 | Board Temp 5 | ADT7462 #2 | same | 0x8D (Remote Temp 2) | External diode near board region 2 |
| 0x06 | Board Temp 6 | ADT7462 #2 | same | 0x8F (Local Temp) | ADT7462 #2 die temperature |

To read Board Temp 1, the firmware:
1. Writes to PCA9544A mux at I2C 0x70 to select channel 0xB0
2. Reads register 0x8B from the ADT7462 on that channel
3. The ADT7462 Temperature IOSAPI converts the raw byte to degrees Celsius

### PCIe Slot Temperature -- TMP100 Sensors (Sensors 0x07-0x16)

Each of the 16 PCIe slots has its own TMP100 temperature sensor mounted near the
slot connector. Since all 16 TMP100s have the same I2C address (0x5C, 7-bit), they
sit behind two PCA9548 8-channel I2C multiplexers on bus 0xF4. The firmware selects
the right mux channel before reading.

| Sensor# | Name | Mux Channel | Mux # | I2C Address |
|---------|------|-------------|-------|-------------|
| 0x07 | PCIE 1 Temp | 0x00 (channel 0) | PCA9548 #1 | 0x5C |
| 0x08 | PCIE 2 Temp | 0x01 (channel 1) | PCA9548 #1 | 0x5C |
| 0x09 | PCIE 3 Temp | 0x02 | PCA9548 #1 | 0x5C |
| 0x0A | PCIE 4 Temp | 0x03 | PCA9548 #1 | 0x5C |
| 0x0B | PCIE 5 Temp | 0x04 | PCA9548 #1 | 0x5C |
| 0x0C | PCIE 6 Temp | 0x05 | PCA9548 #1 | 0x5C |
| 0x0D | PCIE 7 Temp | 0x06 | PCA9548 #1 | 0x5C |
| 0x0E | PCIE 8 Temp | 0x07 | PCA9548 #1 | 0x5C |
| 0x0F | PCIE 9 Temp | 0x10 (channel 0) | PCA9548 #2 | 0x5C |
| 0x10 | PCIE 10 Temp | 0x11 | PCA9548 #2 | 0x5C |
| 0x11 | PCIE 11 Temp | 0x12 | PCA9548 #2 | 0x5C |
| 0x12 | PCIE 12 Temp | 0x13 | PCA9548 #2 | 0x5C |
| 0x13 | PCIE 13 Temp | 0x14 | PCA9548 #2 | 0x5C |
| 0x14 | PCIE 14 Temp | 0x15 | PCA9548 #2 | 0x5C |
| 0x15 | PCIE 15 Temp | 0x16 | PCA9548 #2 | 0x5C |
| 0x16 | PCIE 16 Temp | 0x17 | PCA9548 #2 | 0x5C |

The mux index encoding: values 0x00-0x07 select channels on PCA9548 #1, and values
0x10-0x17 select channels on PCA9548 #2 (high nibble identifies the mux).

### Front Board Temperature (Sensor 0x17)

| Sensor# | Name | I2C Bus | Device | Register |
|---------|------|---------|--------|----------|
| 0x17 | FB Temp | 0xF6 | 0x9E | 0x00 |

A standalone temperature sensor on the main board, separate from the PCIe slot sensors.
Uses a dedicated IOSAPI driver (0x000fc344), distinct from the TMP100 driver, suggesting
it's a different sensor type or requires special handling.

### Fan Speed -- ADT7462 Tachometers (Sensors 0x80-0x87)

The same two ADT7462 chips that measure board temperatures also have four tachometer
inputs each, measuring fan RPM. The C410X has 8 fans total:

| Sensor# | Name | Chip | Tach Register | Tach Input |
|---------|------|------|--------------|------------|
| 0x80 | FAN 1 | ADT7462 #1 (mux 0xB0) | 0x9E | TACH4 |
| 0x81 | FAN 2 | ADT7462 #1 | 0x9C | TACH3 |
| 0x82 | FAN 3 | ADT7462 #2 (mux 0xB8) | 0x9C | TACH3 |
| 0x83 | FAN 4 | ADT7462 #2 | 0x9E | TACH4 |
| 0x84 | FAN 5 | ADT7462 #1 | 0x9A | TACH2 |
| 0x85 | FAN 6 | ADT7462 #1 | 0x98 | TACH1 |
| 0x86 | FAN 7 | ADT7462 #2 | 0x98 | TACH1 |
| 0x87 | FAN 8 | ADT7462 #2 | 0x9A | TACH2 |

Note that the sensor numbers are **not sequential** with respect to the physical
tachometer inputs. This mapping reflects how the fans are physically wired to the
ADT7462 TACH pins, which doesn't match the logical numbering on the chassis.

**Fan-to-chip summary:**
- ADT7462 #1 (mux 0xB0): controls FAN 1, 2, 5, 6
- ADT7462 #2 (mux 0xB8): controls FAN 3, 4, 7, 8

### PCIe Slot Power -- INA219 Current Sensors (Sensors 0x50-0x5F)

Each PCIe slot has a dedicated INA219 high-side current/power monitor on its 12V power
rail. The INA219 measures voltage across a shunt resistor to calculate current and power.
All 16 sit on I2C bus 0xF0 with consecutive addresses:

| Sensor# | Name | I2C Address (7-bit) | Register |
|---------|------|---------------------|----------|
| 0x50 | PCIE 1 Watt | 0x40 | 0x04 (Power register) |
| 0x51 | PCIE 2 Watt | 0x41 | 0x04 |
| 0x52 | PCIE 3 Watt | 0x42 | 0x04 |
| 0x53 | PCIE 4 Watt | 0x43 | 0x04 |
| 0x54 | PCIE 5 Watt | 0x44 | 0x04 |
| 0x55 | PCIE 6 Watt | 0x45 | 0x04 |
| 0x56 | PCIE 7 Watt | 0x46 | 0x04 |
| 0x57 | PCIE 8 Watt | 0x47 | 0x04 |
| 0x58 | PCIE 9 Watt | 0x48 | 0x04 |
| 0x59 | PCIE 10 Watt | 0x49 | 0x04 |
| 0x5A | PCIE 11 Watt | 0x4A | 0x04 |
| 0x5B | PCIE 12 Watt | 0x4B | 0x04 |
| 0x5C | PCIE 13 Watt | 0x4C | 0x04 |
| 0x5D | PCIE 14 Watt | 0x4D | 0x04 |
| 0x5E | PCIE 15 Watt | 0x4E | 0x04 |
| 0x5F | PCIE 16 Watt | 0x4F | 0x04 |

INA219 register 0x04 is the Power register, which returns a value proportional to the
product of voltage and current. The IOSAPI driver applies a scaling factor (based on
the shunt resistor value and calibration register) to convert this into watts.

Unlike the TMP100 sensors, the INA219s don't need multiplexers because they each have
a unique I2C address (0x40 through 0x4F are set by hardware address pins on each chip).

### PSU Power -- PMBus Protocol (Sensors 0x60-0x63)

The four power supplies report their output power via the PMBus protocol:

| Sensor# | Name | PSU Unit | PMBus Index |
|---------|------|----------|-------------|
| 0x60 | PSU 1 Watt | Unit 0 | 0x0000 |
| 0x61 | PSU 2 Watt | Unit 1 | 0x0101 |
| 0x62 | PSU 3 Watt | Unit 2 | 0x0202 |
| 0x63 | PSU 4 Watt | Unit 3 | 0x0303 |

The PMBus PSU IOSAPI driver handles the PMBus command sequence to read power output.
Category 150 (0x96) in these entries links them to the PMBus PSU entries in IO_fl.bin.

### Discrete Sensors (Entries 51-71)

The last 21 entries are **discrete** (on/off) sensors rather than analog readings:

#### PCIe Slot Presence (Sensors 0xA0-0xAF)

16 sensors that detect whether a PCIe card is physically installed in each slot.
These read the PCIe PRSNT# (present) signal through the PCA9555 GPIO expanders on
I2C bus 0xF6.

| Sensor# | Name | Slot | Hardware Index |
|---------|------|------|---------------|
| 0xA0-0xAF | PCIE 1-16 | Slots 1-16 | 0x0000-0x000F |

When a card is inserted or removed, the BMC detects the change and logs it to the
System Event Log.

#### PSU Presence (Sensors 0x30-0x33)

| Sensor# | Name | PSU Bay |
|---------|------|---------|
| 0x30 | PSU 1 | Bay 0 |
| 0x31 | PSU 2 | Bay 1 |
| 0x32 | PSU 3 | Bay 2 |
| 0x33 | PSU 4 | Bay 3 |

Detects whether each power supply is physically installed in its bay.

#### System Power Monitor (Sensor 0x34)

A single discrete sensor tracking the overall system power state (on/off/standby).

## I2C Bus Summary

| Bus ID | What's On It | Why a Separate Bus |
|--------|--------------|--------------------|
| 0xF0 | 16 INA219 power sensors (0x40-0x4F) | Dedicated bus avoids interference with other I2C traffic during frequent power polling |
| 0xF1 | PCA9544A mux -> 2x ADT7462 + PCA9555 | Fan/thermal management on its own bus for reliability |
| 0xF4 | 2x PCA9548 mux -> 16x TMP100 | Per-slot temperature needs multiplexing; isolated bus avoids conflicts |
| 0xF6 | 4x PCA9555 GPIO expanders + FB temp | Slot management (presence, power control, LEDs) |

## Sensor Number Map (Quick Reference)

| Range | Count | Category |
|-------|-------|----------|
| 0x01-0x06 | 6 | Board temperatures (ADT7462) |
| 0x07-0x16 | 16 | PCIe slot temperatures (TMP100) |
| 0x17 | 1 | Front board temperature |
| 0x30-0x33 | 4 | PSU presence (discrete) |
| 0x34 | 1 | System power state (discrete) |
| 0x50-0x5F | 16 | PCIe slot power draw (INA219) |
| 0x60-0x63 | 4 | PSU power output (PMBus) |
| 0x80-0x87 | 8 | Fan speeds (ADT7462 tachometer) |
| 0xA0-0xAF | 16 | PCIe slot card presence (discrete) |
| **Total** | **72** | |

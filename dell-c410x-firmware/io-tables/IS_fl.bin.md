# IS_fl.bin - IO Sensor Table

## Overview

| Property | Value |
|----------|-------|
| **File** | `etc/default/ipmi/evb/IS_fl.bin` |
| **Size** | 1590 bytes |
| **Format** | Binary, little-endian |
| **bmcsetting section** | `[IOSTABLE]` |
| **Loading function** | `HWInitIOSensorTable()` in fullfw |
| **Global pointers** | `G_sIOSensorTableHeaderPtr`, `G_sIOSensorTablePtr` |

IS_fl.bin maps every IPMI sensor number to its physical hardware interface. Each entry
specifies the I2C bus, device address, register, mux configuration, and IOSAPI driver
needed to read a sensor value. This is the primary table the BMC's Sensor Manager uses
to poll hardware sensors at runtime.

## Binary Layout

```
Offset  Size    Content
------  ------  --------------------------------------------------
0x0000  4       Header
0x0004  1584    Entry table (72 entries x 22 bytes)
0x0634  2       Footer (0xBF 0x33)
```

## Header (4 bytes)

```
Offset  Type  Value  Meaning
------  ----  -----  -------
0x00    u8    0x01   Table version
0x01    u8    0x00   Reserved
0x02    u8    0x33   Number of analog sensor slots = 51
0x03    u8    0x15   Number of TB (threshold-based) extra entries = 21
```

Total entries = 51 + 21 = 72. The first 51 are analog sensors (temperature, fan speed,
power). The last 21 are discrete sensors (PCIe presence, PSU presence, system power).

## Entry Format (22 bytes)

```c
struct io_sensor_entry {
    uint8_t   sensor_num;     // byte 0: IPMI sensor number
    uint8_t   sensor_type;    // byte 1: sensor reading type/flags
    uint8_t   owner_id;       // byte 2: sensor owner ID (0x20 = BMC)
    uint8_t   owner_lun;      // byte 3: sensor owner LUN
    uint8_t   entity_id;      // byte 4: IPMI entity ID
    uint8_t   entity_inst;    // byte 5: IPMI entity instance
    uint8_t   category;       // byte 6: sensor category (0xA8 common)
    uint8_t   config_a;       // byte 7: config parameter A (0x90 common)
    uint8_t   config_b;       // byte 8: config parameter B (0x07 common)
    uint8_t   config_c;       // byte 9: config parameter C
    uint16_t  hw_index;       // bytes 10-11: hardware sub-index (LE)
    uint8_t   scan_mode;      // byte 12: scanning mode (0=auto, 1=polling)
    uint8_t   reserved;       // byte 13: 0x00 or 0xFF
    uint8_t   i2c_dev_lo;     // byte 14: I2C device address low byte
    uint8_t   i2c_bus;        // byte 15: I2C bus identifier
    uint8_t   i2c_register;   // byte 16: I2C register to read
    uint8_t   i2c_param;      // byte 17: I2C parameter (0xFF common)
    uint32_t  iosapi_ptr;     // bytes 18-21: pointer to IOSAPI driver vtable (LE)
};
```

## IOSAPI Driver Structures

Each IOSAPI struct is a sensor-reading vtable in the `.rodata` section of fullfw:

| Address | Symbol | Sensor Type | Hardware |
|---------|--------|-------------|----------|
| 0x000fcbcc | ADT7462 Temperature IOSAPI | Analog | ADT7462 temperature registers |
| 0x000fcbdc | ADT7462 Fan IOSAPI | Analog | ADT7462 fan tachometer registers |
| 0x000fcbfc | TMP100 Temperature IOSAPI | Analog | TMP100 I2C temperature sensor |
| 0x000fcc0c | INA219 Power IOSAPI | Analog | INA219 current/power sensor |
| 0x000fc344 | FB Temperature IOSAPI | Analog | Front-board temperature |
| 0x000fc3d4 | PMBus PSU IOSAPI | Analog | PMBus power supply telemetry |
| 0x0010a5a8 | PCIe Presence IOSAPI | Discrete | PCIe slot presence detection |
| 0x0010a5b0 | PSU Presence IOSAPI | Discrete | Power supply presence detection |
| 0x0010a5b8 | System Power Monitor IOSAPI | Discrete | System power state |

## Complete Sensor Decode

### Analog Sensors (Entries 0-50)

#### Board Temperature Sensors (0x01-0x06) - ADT7462

Two ADT7462 chips, each providing 3 temperature readings:

| Entry | Sensor# | Name | I2C Bus | Mux Addr | Register | IOSAPI |
|-------|---------|------|---------|----------|----------|--------|
| 0 | 0x01 | Board Temp 1 | 0xF1 | 0xB0 (PCA9544A @ 0x58) | 0x8B | ADT7462_TEMP |
| 1 | 0x02 | Board Temp 2 | 0xF1 | 0xB0 | 0x8D | ADT7462_TEMP |
| 2 | 0x03 | Board Temp 3 | 0xF1 | 0xB0 | 0x8F | ADT7462_TEMP |
| 3 | 0x04 | Board Temp 4 | 0xF1 | 0xB8 (PCA9544A @ 0x5C) | 0x8B | ADT7462_TEMP |
| 4 | 0x05 | Board Temp 5 | 0xF1 | 0xB8 | 0x8D | ADT7462_TEMP |
| 5 | 0x06 | Board Temp 6 | 0xF1 | 0xB8 | 0x8F | ADT7462_TEMP |

ADT7462 register mapping:
- 0x8B = Remote Temperature 1 reading
- 0x8D = Remote Temperature 2 reading
- 0x8F = Local Temperature reading

#### PCIe Slot Temperature Sensors (0x07-0x16) - TMP100

16 TMP100 temperature sensors, one per PCIe slot, accessed via I2C mux:

| Entry | Sensor# | Name | I2C Bus | Device | Mux Index | IOSAPI |
|-------|---------|------|---------|--------|-----------|--------|
| 6 | 0x07 | PCIE 1 Temp | 0xF4 | 0x5C (TMP100) | 0x00 | TMP100_TEMP |
| 7 | 0x08 | PCIE 2 Temp | 0xF4 | 0x5C | 0x01 | TMP100_TEMP |
| 8 | 0x09 | PCIE 3 Temp | 0xF4 | 0x5C | 0x02 | TMP100_TEMP |
| 9 | 0x0A | PCIE 4 Temp | 0xF4 | 0x5C | 0x03 | TMP100_TEMP |
| 10 | 0x0B | PCIE 5 Temp | 0xF4 | 0x5C | 0x04 | TMP100_TEMP |
| 11 | 0x0C | PCIE 6 Temp | 0xF4 | 0x5C | 0x05 | TMP100_TEMP |
| 12 | 0x0D | PCIE 7 Temp | 0xF4 | 0x5C | 0x06 | TMP100_TEMP |
| 13 | 0x0E | PCIE 8 Temp | 0xF4 | 0x5C | 0x07 | TMP100_TEMP |
| 14 | 0x0F | PCIE 9 Temp | 0xF4 | 0x5C | 0x10 | TMP100_TEMP |
| 15 | 0x10 | PCIE 10 Temp | 0xF4 | 0x5C | 0x11 | TMP100_TEMP |
| 16 | 0x11 | PCIE 11 Temp | 0xF4 | 0x5C | 0x12 | TMP100_TEMP |
| 17 | 0x12 | PCIE 12 Temp | 0xF4 | 0x5C | 0x13 | TMP100_TEMP |
| 18 | 0x13 | PCIE 13 Temp | 0xF4 | 0x5C | 0x14 | TMP100_TEMP |
| 19 | 0x14 | PCIE 14 Temp | 0xF4 | 0x5C | 0x15 | TMP100_TEMP |
| 20 | 0x15 | PCIE 15 Temp | 0xF4 | 0x5C | 0x16 | TMP100_TEMP |
| 21 | 0x16 | PCIE 16 Temp | 0xF4 | 0x5C | 0x17 | TMP100_TEMP |

The mux index (byte 16) selects which PCA9548 I2C mux channel to use before reading
the TMP100. Indices 0x00-0x07 map to mux channels 0-7, and 0x10-0x17 map to a second
PCA9548 mux's channels 0-7.

#### Front Board Temperature (0x17) - Special

| Entry | Sensor# | Name | I2C Bus | Device | Mux Index | IOSAPI |
|-------|---------|------|---------|--------|-----------|--------|
| 22 | 0x17 | FB Temp | 0xF6 | 0x9E | 0x00 | FB_TEMP |

This sensor uses a special IOSAPI (0x000fc344) distinct from the standard temperature
drivers, likely because it's measuring the main board area rather than a PCIe slot.

#### Fan Speed Sensors (0x80-0x87) - ADT7462 Tachometer

8 fan speed sensors from the two ADT7462 chips:

| Entry | Sensor# | Name | I2C Bus | Mux Addr | Tach Register | IOSAPI |
|-------|---------|------|---------|----------|---------------|--------|
| 23 | 0x85 | FAN 6 | 0xF1 | 0xB0 | 0x98 | ADT7462_FAN |
| 24 | 0x84 | FAN 5 | 0xF1 | 0xB0 | 0x9A | ADT7462_FAN |
| 25 | 0x81 | FAN 2 | 0xF1 | 0xB0 | 0x9C | ADT7462_FAN |
| 26 | 0x80 | FAN 1 | 0xF1 | 0xB0 | 0x9E | ADT7462_FAN |
| 27 | 0x86 | FAN 7 | 0xF1 | 0xB8 | 0x98 | ADT7462_FAN |
| 28 | 0x87 | FAN 8 | 0xF1 | 0xB8 | 0x9A | ADT7462_FAN |
| 29 | 0x82 | FAN 3 | 0xF1 | 0xB8 | 0x9C | ADT7462_FAN |
| 30 | 0x83 | FAN 4 | 0xF1 | 0xB8 | 0x9E | ADT7462_FAN |

ADT7462 tachometer register mapping:
- 0x98 = TACH1 reading
- 0x9A = TACH2 reading
- 0x9C = TACH3 reading
- 0x9E = TACH4 reading

Note: sensor numbers are NOT sequential with entry order. The firmware maps
logical fan numbers to physical tachometer inputs based on wiring.

**Fan-to-ADT7462 Chip Mapping:**
- ADT7462 #1 (behind PCA9544A mux @ 0xB0/0x58): FAN 1, 2, 5, 6
- ADT7462 #2 (behind PCA9544A mux @ 0xB8/0x5C): FAN 3, 4, 7, 8

#### PCIe Slot Power Sensors (0x50-0x5F) - INA219

16 INA219 high-side current/power sensors, one per PCIe slot:

| Entry | Sensor# | Name | I2C Bus | INA219 Addr (8-bit) | 7-bit Addr | Command | IOSAPI |
|-------|---------|------|---------|---------------------|------------|---------|--------|
| 31 | 0x50 | PCIE 1 Watt | 0xF0 | 0x80 | 0x40 | 0x04 | INA219_POWER |
| 32 | 0x51 | PCIE 2 Watt | 0xF0 | 0x82 | 0x41 | 0x04 | INA219_POWER |
| 33 | 0x52 | PCIE 3 Watt | 0xF0 | 0x84 | 0x42 | 0x04 | INA219_POWER |
| 34 | 0x53 | PCIE 4 Watt | 0xF0 | 0x86 | 0x43 | 0x04 | INA219_POWER |
| 35 | 0x54 | PCIE 5 Watt | 0xF0 | 0x88 | 0x44 | 0x04 | INA219_POWER |
| 36 | 0x55 | PCIE 6 Watt | 0xF0 | 0x8A | 0x45 | 0x04 | INA219_POWER |
| 37 | 0x56 | PCIE 7 Watt | 0xF0 | 0x8C | 0x46 | 0x04 | INA219_POWER |
| 38 | 0x57 | PCIE 8 Watt | 0xF0 | 0x8E | 0x47 | 0x04 | INA219_POWER |
| 39 | 0x58 | PCIE 9 Watt | 0xF0 | 0x90 | 0x48 | 0x04 | INA219_POWER |
| 40 | 0x59 | PCIE 10 Watt | 0xF0 | 0x92 | 0x49 | 0x04 | INA219_POWER |
| 41 | 0x5A | PCIE 11 Watt | 0xF0 | 0x94 | 0x4A | 0x04 | INA219_POWER |
| 42 | 0x5B | PCIE 12 Watt | 0xF0 | 0x96 | 0x4B | 0x04 | INA219_POWER |
| 43 | 0x5C | PCIE 13 Watt | 0xF0 | 0x98 | 0x4C | 0x04 | INA219_POWER |
| 44 | 0x5D | PCIE 14 Watt | 0xF0 | 0x9A | 0x4D | 0x04 | INA219_POWER |
| 45 | 0x5E | PCIE 15 Watt | 0xF0 | 0x9C | 0x4E | 0x04 | INA219_POWER |
| 46 | 0x5F | PCIE 16 Watt | 0xF0 | 0x9E | 0x4F | 0x04 | INA219_POWER |

INA219 register 0x04 = Power register (returns power in watts). The 16 INA219 devices
sit on I2C bus 0xF0 at consecutive 7-bit addresses 0x40-0x4F. Each has a shunt
resistor on the 12V power rail to the corresponding PCIe slot.

#### PSU Power Sensors (0x60-0x63) - PMBus

4 power supply wattage sensors:

| Entry | Sensor# | Name | hw_index | Category | IOSAPI |
|-------|---------|------|----------|----------|--------|
| 47 | 0x60 | PSU 1 Watt | 0x0000 | 150 (0x96) | PMBUS_PSU |
| 48 | 0x61 | PSU 2 Watt | 0x0101 | 150 (0x96) | PMBUS_PSU |
| 49 | 0x62 | PSU 3 Watt | 0x0202 | 150 (0x96) | PMBUS_PSU |
| 50 | 0x63 | PSU 4 Watt | 0x0303 | 150 (0x96) | PMBUS_PSU |

PSU sensors use the PMBus protocol. The hw_index encodes the PSU unit number (0-3).
Category 150 (0x96) = the same as the IO_fl.bin entry hint, linking these to the
main IO table's PSU type 31 entries.

### Discrete Sensors (Entries 51-71, "TB Extra")

#### PCIe Slot Presence (0xA0-0xAF)

16 discrete presence-detect sensors:

| Entry | Sensor# | Name | hw_index | IOSAPI |
|-------|---------|------|----------|--------|
| 51 | 0xA0 | PCIE 1 Presence | 0x0000 | PCIE_PRESENCE |
| 52 | 0xA1 | PCIE 2 Presence | 0x0001 | PCIE_PRESENCE |
| ... | ... | ... | ... | ... |
| 66 | 0xAF | PCIE 16 Presence | 0x000F | PCIE_PRESENCE |

These sensors use GPIO-based detection via the PCA9555 I2C GPIO expanders
documented in IO_fl.bin. The hw_index (0-15) maps to the slot number.

#### PSU Presence (0x30-0x33)

| Entry | Sensor# | Name | hw_index | IOSAPI |
|-------|---------|------|----------|--------|
| 67 | 0x30 | PSU 1 Presence | 0x0000 | PSU_PRESENCE |
| 68 | 0x31 | PSU 2 Presence | 0x0001 | PSU_PRESENCE |
| 69 | 0x32 | PSU 3 Presence | 0x0002 | PSU_PRESENCE |
| 70 | 0x33 | PSU 4 Presence | 0x0003 | PSU_PRESENCE |

#### System Power Monitor (0x34)

| Entry | Sensor# | Name | hw_index | IOSAPI |
|-------|---------|------|----------|--------|
| 71 | 0x34 | Sys Pwr Monitor | 0x0000 | SYS_PWR_MON |

## I2C Bus Identifier Mapping

The high byte in the I2C address fields encodes the bus:

| Bus ID | Physical Bus | Devices |
|--------|-------------|---------|
| 0xF0 | I2C bus for INA219 sensors | 16x INA219 (0x40-0x4F) |
| 0xF1 | I2C bus with PCA9544A mux | 2x ADT7462 (via mux), PCA9555 (0x20) |
| 0xF4 | I2C bus with PCA9548 mux | 16x TMP100 (via mux channels) |
| 0xF6 | I2C bus for PCA9555 expanders | 4x PCA9555 (0x20-0x23), FB temp |

## Sensor Number Summary

| Range | Count | Type | Sensor Name Pattern |
|-------|-------|------|-------------------|
| 0x01-0x06 | 6 | Board Temperature | Board Temp 1-6 (ADT7462) |
| 0x07-0x16 | 16 | PCIe Temperature | PCIE 1-16 Temp (TMP100) |
| 0x17 | 1 | Board Temperature | FB Temp (front board) |
| 0x30-0x33 | 4 | Discrete Presence | PSU 1-4 |
| 0x34 | 1 | Discrete Power | Sys Pwr Monitor |
| 0x50-0x5F | 16 | PCIe Power | PCIE 1-16 Watt (INA219) |
| 0x60-0x63 | 4 | PSU Power | PSU 1-4 Watt (PMBus) |
| 0x80-0x87 | 8 | Fan Speed | FAN 1-8 (ADT7462 tach) |
| 0xA0-0xAF | 16 | Discrete Presence | PCIE 1-16 |
| **Total** | **72** | | |

## Physical I2C Device Topology

```
AST2050 BMC
├── I2C Bus 0xF0 (INA219 power monitoring)
│   ├── INA219 @ 0x40 ── PCIe Slot 1 power (0x50)
│   ├── INA219 @ 0x41 ── PCIe Slot 2 power (0x51)
│   ├── ...
│   └── INA219 @ 0x4F ── PCIe Slot 16 power (0x5F)
│
├── I2C Bus 0xF1 (Fan/Temp via PCA9544A mux)
│   ├── PCA9544A @ 0x58 (mux selector 0xB0)
│   │   └── ADT7462 #1 @ 0x55 ── Board Temp 1-3, FAN 1,2,5,6
│   ├── PCA9544A @ 0x5C (mux selector 0xB8)
│   │   └── ADT7462 #2 @ 0x55 ── Board Temp 4-6, FAN 3,4,7,8
│   └── PCA9555 @ 0x20 ── Additional GPIO/status
│
├── I2C Bus 0xF4 (PCIe slot temperatures via PCA9548 mux)
│   ├── PCA9548 #1 (channels 0-7)
│   │   └── TMP100 @ 0x5C per channel ── PCIE 1-8 Temp
│   └── PCA9548 #2 (channels 0-7)
│       └── TMP100 @ 0x5C per channel ── PCIE 9-16 Temp
│
├── I2C Bus 0xF6 (PCA9555 GPIO expanders)
│   ├── PCA9555 @ 0x20 ── PCIe slot presence (1-8)
│   ├── PCA9555 @ 0x21 ── PCIe slot presence (9-16)
│   ├── PCA9555 @ 0x22 ── PCIe slot power control
│   ├── PCA9555 @ 0x23 ── PCIe slot status/LED
│   └── FB Temp sensor @ 0x9E
│
└── PMBus (PSU communication)
    ├── PSU 1 ── PSU 1 Watt (0x60)
    ├── PSU 2 ── PSU 2 Watt (0x61)
    ├── PSU 3 ── PSU 3 Watt (0x62)
    └── PSU 4 ── PSU 4 Watt (0x63)
```

## Footer

The 2-byte footer (0xBF 0x33) at offset 0x634 likely serves as a checksum or
end-of-table marker. 0x33 = 51 matches the sensor slot count.

## Further Investigation

- [ ] Verify ADT7462 register assignments against ADT7462 datasheet
- [ ] Confirm TMP100 mux channel mapping to physical PCIe slot positions
- [ ] Determine INA219 shunt resistor values for power calculation
- [ ] Investigate PMBus PSU addressing scheme
- [ ] Cross-reference sensor thresholds from SDR records

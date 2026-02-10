# FT_fl.bin - Function Table

## Overview

| Property | Value |
|----------|-------|
| **File** | `etc/default/ipmi/evb/FT_fl.bin` |
| **Size** | 26 bytes |
| **Format** | Binary, little-endian |
| **bmcsetting section** | `[FTTABLE]` |
| **Loading function** | `HWInitFunctionTable()` at 0x0007a4b4 in fullfw |
| **Global pointer** | `G_u32FunTblStartAddr` at 0x00110bb0 |

FT_fl.bin provides per-driver-type runtime configuration parameters. Unlike the other
IO table files which use `MakeMemFileV2()`, this file uses the simpler `MakeMemFile()`
which just reads the raw file into a malloc'd buffer without adding a wrapper header.

## Raw Content

```
Offset  Hex                                              ASCII
------  -----------------------------------------------  --------
0x0000  01 18 00 00 00 00 00 00 01 10 00 00 18 00 00 00  ................
0x0010  00 00 00 00 00 00 00 be 00 00                    ..........
```

## Structure

```c
struct function_table {
    uint8_t  version;              // byte 0: version = 1
    uint8_t  max_driver_type;      // byte 1: max type index = 24 (0x18)
    uint8_t  config[24];           // bytes 2-25: one byte per driver type (0-23)
};
```

## Per-Driver-Type Configuration

The 24 configuration bytes (one per driver type index 0-23):

| Index | Driver Type | Config | Interpretation |
|-------|------------|--------|----------------|
| 0 | ISR Controller | 0x00 | Default |
| 1 | GPIO Sensor | 0x00 | Default |
| 2 | OEM Power | 0x00 | Default |
| 3 | LED Controller | 0x00 | Default |
| 4 | IRQ Handler | 0x00 | Default |
| 5 | GPIO Control | 0x00 | Default |
| 6 | **Fan Controller** | **0x01** | **1 fan controller zone active** |
| 7 | **PMBus PSU** | **0x10** | **PMBus config parameter (16)** |
| 8 | Fan IOSAPI | 0x00 | Default |
| 9 | EEPROM | 0x00 | Default |
| 10 | **Virtual Other** | **0x18** | **Virtual driver config = 24** |
| 11 | PMBus Sensor | 0x00 | Default |
| 12 | - | 0x00 | Unused |
| 13 | - | 0x00 | Unused |
| 14 | - | 0x00 | Unused |
| 15 | - | 0x00 | Unused |
| 16 | - | 0x00 | Unused |
| 17 | - | 0x00 | Unused |
| 18 | - | 0x00 | Unused |
| 19 | - | 0x00 | Unused |
| 20 | - | 0x00 | Unused |
| 21 | **PCA9548 I2C Mux** | **0xBE** | **I2C mux channel enable bitmask** |
| 22 | PCA9555 GPIO | 0x00 | Default |
| 23 | GPU Hot-Plug | 0x00 | Default |

### Notable Configuration Values

**Index 6 = 0x01 (Fan Controller):** Indicates 1 fan controller zone is active.
The Dell C410X treats all 8 fans as a single cooling zone.

**Index 7 = 0x10 (PMBus PSU):** PMBus configuration parameter, likely the bus
number (16 = 0x10) or an address offset used during PMBus device enumeration.

**Index 10 = 0x18 (Virtual Other):** Virtual driver parameter = 24, possibly
referencing the number of virtual sensor entries or a configuration table size.

**Index 21 = 0xBE (PCA9548 I2C Mux):** This is a channel-enable bitmask for the
PCA9548 8-channel I2C multiplexer:

```
0xBE = 10111110 binary

Bit 7 (0x80): Channel 7 = ENABLED
Bit 6 (0x40): Channel 6 = DISABLED
Bit 5 (0x20): Channel 5 = ENABLED
Bit 4 (0x10): Channel 4 = ENABLED
Bit 3 (0x08): Channel 3 = ENABLED
Bit 2 (0x04): Channel 2 = ENABLED
Bit 1 (0x02): Channel 1 = ENABLED
Bit 0 (0x01): Channel 0 = DISABLED
```

6 of 8 PCA9548 channels are active. Channels 0 and 6 are disabled, likely because
those I2C bus segments have no downstream devices populated on the C410X board. This
matches the hardware where not all possible I2C mux paths connect to physical sensors.

## Relationship to System Init

The firmware initialization sequence (`HWInit`) loads FT_fl.bin after IO_fl.bin,
IS_fl.bin, and IX_fl.bin:

```
1. HWInitIOTableV3()         -- IO_fl.bin
2. HWInitIOSensorTable()     -- IS_fl.bin
3. HWInitSmartIOIndexTable() -- IX_fl.bin
4. HWInitFunctionTable()     -- FT_fl.bin  ← this file
5. HWInitTOC()               -- table of contents
6. HWInitFWInfo()            -- firmware info
7. HWInitNVRAMSubSystem()    -- NVRAM
8. HWLoadDefaultValueTable() -- oemdef.bin
```

Individual IOAPI drivers read their configuration byte from FT_fl.bin during their
initialization phase (called from `G_aSysPostInitFunctionTable`). The `MakeMemFile`
loader keeps the entire 26-byte file in memory for quick access.

## Hardcoded Function Tables in fullfw

The firmware also contains four hardcoded function pointer arrays in `.rodata` that
are NOT configured by FT_fl.bin but work alongside it:

| Table | Address | Entries | Purpose |
|-------|---------|---------|---------|
| `G_aSysPreInitFunctionTable` | 0x000f6e80 | 25 | Pre-initialization functions |
| `G_aSysPostInitFunctionTable` | 0x000f6ee8 | 35 | Post-initialization functions |
| `G_aCalcMemSizeFunctionTable` | 0x000f6f78 | 20 | Memory size calculation |
| `G_aSysPrepareStopFuncionTable` | 0x000fc5b0 | 5 | Shutdown preparation |

## Further Investigation

- [ ] Verify PCA9548 channel mapping matches physical PCIe slot wiring
- [ ] Determine which OEM dispatch table indices correspond to which driver types
- [ ] Cross-reference fan zone configuration with ADT7462 PWM control

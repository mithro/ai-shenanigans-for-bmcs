# FT_fl.bin -- Driver Configuration Table (Function Table)

## What This File Does

FT_fl.bin is a tiny configuration file -- just 26 bytes -- that tells each hardware
driver how to behave at startup. Each driver type gets a single configuration byte.
Most drivers use the default value (0x00), but a few need specific settings to match
the C410X hardware: how many fan zones to manage, which I2C mux channels have devices
connected, and other per-driver parameters.

Unlike the other IO table files (which use `MakeMemFileV2()` and get a 16-byte wrapper),
this file is loaded with the simpler `MakeMemFile()` -- just a raw malloc'd buffer with
no wrapper header.

| Property | Value |
|----------|-------|
| **Location on BMC filesystem** | `/etc/default/ipmi/evb/FT_fl.bin` |
| **bmcsetting section name** | `[FTTABLE]` |
| **Size** | 26 bytes |
| **Loading function in fullfw** | `HWInitFunctionTable()` at address 0x0007a4b4 |
| **Global pointer** | `G_u32FunTblStartAddr` at 0x00110bb0 |

## File Structure

```c
struct function_table {
    uint8_t  version;           // Byte 0: format version (= 1)
    uint8_t  max_driver_type;   // Byte 1: highest driver type index (= 24)
    uint8_t  config[24];        // Bytes 2-25: one config byte per driver type
};
```

## Raw File Contents

```
Offset  Hex                                              ASCII
------  -----------------------------------------------  --------
0x0000  01 18 00 00 00 00 00 00 01 10 00 00 18 00 00 00  ................
0x0010  00 00 00 00 00 00 00 be 00 00                    ..........
```

## Configuration Byte Meanings

Most driver types use 0x00 (default/unconfigured). The four non-zero values configure
specific hardware features:

### Index 6 = 0x01: Fan Controller -- One Cooling Zone

The Dell C410X treats all 8 fans as a single cooling zone. This means all fans ramp
up and down together based on the hottest temperature reading anywhere on the board.
A value of 0x01 tells the fan controller driver "you have 1 zone to manage."

Some other MergePoint-based BMCs use multiple zones (e.g., separate front and rear
fan banks), which would use a higher value here.

### Index 7 = 0x10: PMBus PSU Configuration

Value 16 (0x10) is a PMBus configuration parameter used during power supply enumeration.
This likely specifies the bus identifier or an address offset that the PMBus driver uses
when scanning for the four hot-swappable power supply units.

### Index 10 = 0x18: Virtual Driver Parameter

Value 24 (0x18) configures the "virtual other" driver. This may reference the number of
virtual sensor entries or a configuration table size used by the software-defined sensor
management layer.

### Index 21 = 0xBE: PCA9548 I2C Mux Channel Enable Mask

This is the most interesting configuration byte. The C410X uses two PCA9548 8-channel
I2C multiplexers on bus 0xF4 to reach the 16 TMP100 per-slot temperature sensors. This
byte is a bitmask telling the firmware which of the 8 mux channels have devices connected:

```
0xBE = 1 0 1 1 1 1 1 0  (binary, MSB first)
       | | | | | | | |
       | | | | | | | +-- Channel 0: DISABLED (no device)
       | | | | | | +---- Channel 1: ENABLED
       | | | | | +------ Channel 2: ENABLED
       | | | | +-------- Channel 3: ENABLED
       | | | +---------- Channel 4: ENABLED
       | | +------------ Channel 5: ENABLED
       | +-------------- Channel 6: DISABLED (no device)
       +---------------- Channel 7: ENABLED
```

Six of 8 channels are active. Channels 0 and 6 are disabled because those I2C mux paths
don't connect to physical sensors on the C410X board. The firmware skips these channels
during sensor polling, avoiding I2C bus errors from addressing non-existent devices.

This matches the physical hardware: the C410X has 16 PCIe slots served by two PCA9548
muxes, but not every possible mux channel connects to a temperature sensor. The board
layout routes TMP100 sensors through specific channels based on PCB trace routing
constraints.

## Complete Configuration Table

| Index | Driver Type | Config | Meaning |
|-------|------------|--------|---------|
| 0 | ISR Controller | 0x00 | Default |
| 1 | GPIO Sensor | 0x00 | Default |
| 2 | OEM Power | 0x00 | Default |
| 3 | LED Controller | 0x00 | Default |
| 4 | IRQ Handler | 0x00 | Default |
| 5 | GPIO Control | 0x00 | Default |
| **6** | **Fan Controller** | **0x01** | **1 fan cooling zone** |
| **7** | **PMBus PSU** | **0x10** | **PMBus bus/address config (16)** |
| 8 | Fan IOSAPI | 0x00 | Default |
| 9 | EEPROM | 0x00 | Default |
| **10** | **Virtual Other** | **0x18** | **Virtual driver parameter (24)** |
| 11 | PMBus Sensor | 0x00 | Default |
| 12-20 | (unused) | 0x00 | Reserved for future driver types |
| **21** | **PCA9548 I2C Mux** | **0xBE** | **Channel enable mask: channels 1-5,7 active** |
| 22 | PCA9555 GPIO | 0x00 | Default |
| 23 | GPU Hot-Plug | 0x00 | Default |

## How Drivers Use This Table

During the firmware initialization sequence, after all four table files are loaded into
memory, each IOAPI driver's init function reads its configuration byte:

```
1. HWInitIOTableV3()         -- loads IO_fl.bin (hardware map)
2. HWInitIOSensorTable()     -- loads IS_fl.bin (sensor definitions)
3. HWInitSmartIOIndexTable() -- loads IX_fl.bin (index cross-references)
4. HWInitFunctionTable()     -- loads FT_fl.bin (THIS FILE)
5. Driver init functions run (called from G_aSysPostInitFunctionTable)
   - Fan controller reads config[6] = 0x01 -> sets up 1 cooling zone
   - PCA9548 driver reads config[21] = 0xBE -> enables 6 of 8 channels
   - PMBus driver reads config[7] = 0x10 -> configures bus parameters
   - etc.
```

The firmware also contains four hardcoded function pointer arrays in `.rodata` that
work alongside this table during initialization:

| Table | Address | Entries | When It Runs |
|-------|---------|---------|-------------|
| `G_aSysPreInitFunctionTable` | 0x000f6e80 | 25 | Before hardware init |
| `G_aSysPostInitFunctionTable` | 0x000f6ee8 | 35 | After table loading (reads FT_fl.bin) |
| `G_aCalcMemSizeFunctionTable` | 0x000f6f78 | 20 | Memory allocation planning |
| `G_aSysPrepareStopFuncionTable` | 0x000fc5b0 | 5 | Shutdown/cleanup |

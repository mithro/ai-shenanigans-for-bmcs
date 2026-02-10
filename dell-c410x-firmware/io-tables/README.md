# Dell C410X BMC - IO Table Files Reference

## Summary

The Dell PowerEdge C410X BMC firmware (Avocent MergePoint platform, Aspeed AST2050 SoC)
uses a set of binary configuration tables to define the complete hardware I/O mapping.
These files live in `etc/default/ipmi/evb/` on the firmware's SquashFS root filesystem
and are loaded during BMC initialization by the `fullfw` IPMI engine binary.

This directory contains reverse-engineered documentation for each table file.

## Architecture Overview

The Avocent MergePoint IOAPI framework uses a layered table design:

```
┌─────────────────────────────────────────────────────────────────┐
│                     IPMI Command Layer                          │
│               (Get Sensor Reading, Set LED, etc.)               │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│  IS_fl.bin (Sensor Table)          IX_fl.bin (Index Table)      │
│  ┌─────────────────────┐           ┌──────────────────┐        │
│  │ sensor_num → IOSAPI │           │ index → (type,   │        │
│  │ + I2C bus/dev/reg   │           │          sub_idx) │        │
│  └────────┬────────────┘           └────────┬─────────┘        │
│           │                                 │                   │
│           ▼                                 ▼                   │
│  IOSAPI Drivers                    IO_fl.bin (IO Table)         │
│  (Sensor Reading)                  ┌──────────────────┐        │
│  ┌──────────────┐                  │ dispatch[type]   │        │
│  │ ADT7462 Temp │                  │ + sub_index      │        │
│  │ ADT7462 Fan  │                  │ = IOAPI entry    │        │
│  │ TMP100 Temp  │                  └────────┬─────────┘        │
│  │ INA219 Power │                           │                   │
│  │ PMBus PSU    │                           ▼                   │
│  │ GPIO Presence│                  IOAPI Drivers               │
│  └──────────────┘                  (Hardware Access)            │
│                                    ┌──────────────┐            │
│                                    │ On-chip GPIO │            │
│                                    │ PCA9555 GPIO │            │
│  FT_fl.bin                         │ ADT7462 Fan  │            │
│  (Function Table)                  │ LED Control  │            │
│  ┌──────────────┐                  │ PMBus PSU    │            │
│  │ Per-driver   │                  │ PCA9544 Mux  │            │
│  │ config bytes │                  │ IPMB/KCS/LAN │            │
│  └──────────────┘                  │ UART/EEPROM  │            │
│                                    └──────────────┘            │
│  oemdef.bin                                                     │
│  (OEM Defaults)                                                 │
│  ┌──────────────┐                                               │
│  │ Factory config│                                              │
│  │ IP, users,   │                                               │
│  │ SNMP, PEF    │                                               │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

## File Summary

| File | Size | Entries | Purpose | Doc |
|------|------|---------|---------|-----|
| **IO_fl.bin** | 2456 B | 192 | Master hardware I/O table with IOAPI driver pointers | [IO_fl.bin.md](IO_fl.bin.md) |
| **IS_fl.bin** | 1590 B | 72 | Sensor-to-hardware mapping (I2C addresses, IOSAPI drivers) | [IS_fl.bin.md](IS_fl.bin.md) |
| **IX_fl.bin** | 344 B | 85 | Index cross-reference (linear index → driver_type + sub_index) | [IX_fl.bin.md](IX_fl.bin.md) |
| **FT_fl.bin** | 26 B | 24 | Per-driver-type configuration bytes | [FT_fl.bin.md](FT_fl.bin.md) |
| **oemdef.bin** | 1710 B | 100 | Factory default configuration values | [oemdef.bin.md](oemdef.bin.md) |

### Supporting Files (Not Documented Here)

| File | Size | Purpose |
|------|------|---------|
| NVRAM_SDR00.dat | 3946 B | IPMI Sensor Data Records (73 records, 72 sensor names) |
| NVRAM_FRU00.dat | 512 B | Field Replaceable Unit data |
| NVRAM_Storage00.dat | 16384 B | Persistent NVRAM storage |
| bmcsetting | 382 B | Maps section names to file paths |
| ID_devid.bin | 14 B | Device ID information |
| FI_fwid.bin | 13 B | Firmware ID string |

## Initialization Sequence

The `HWInit()` function in fullfw loads these files in order:

```
1. HWInitIOTableV3()          →  IO_fl.bin   (MakeMemFileV2)
2. HWInitIOSensorTable()      →  IS_fl.bin   (MakeMemFileV2)
3. HWInitSmartIOIndexTable()   →  IX_fl.bin   (MakeMemFileV2)
4. HWInitFunctionTable()       →  FT_fl.bin   (MakeMemFile)
5. HWInitTOC()                 →  TOC / config
6. HWInitFWInfo()              →  Firmware info
7. HWInitNVRAMSubSystem()      →  NVRAM setup
8. HWLoadDefaultValueTable()   →  oemdef.bin  (MakeMemFile)
```

## Hardware Summary

### Sensor Inventory (72 sensors)

| Category | Count | Sensor Numbers | Hardware | Driver |
|----------|-------|----------------|----------|--------|
| Board Temperature | 6 | 0x01-0x06 | ADT7462 | ADT7462_TEMP IOSAPI |
| PCIe Slot Temperature | 16 | 0x07-0x16 | TMP100 via PCA9548 mux | TMP100_TEMP IOSAPI |
| Front Board Temperature | 1 | 0x17 | Special | FB_TEMP IOSAPI |
| Fan Speed | 8 | 0x80-0x87 | ADT7462 tachometer | ADT7462_FAN IOSAPI |
| PCIe Slot Power | 16 | 0x50-0x5F | INA219 current sensor | INA219_POWER IOSAPI |
| PSU Power | 4 | 0x60-0x63 | PMBus | PMBUS_PSU IOSAPI |
| PCIe Slot Presence | 16 | 0xA0-0xAF | PCA9555 GPIO | PCIE_PRESENCE IOSAPI |
| PSU Presence | 4 | 0x30-0x33 | PCA9555 GPIO | PSU_PRESENCE IOSAPI |
| System Power Monitor | 1 | 0x34 | GPIO | SYS_PWR_MON IOSAPI |

### I2C Device Map

```
AST2050 BMC SoC
│
├── I2C Bus 0xF0 ─── 16x INA219 @ 0x40-0x4F (PCIe slot power monitoring)
│
├── I2C Bus 0xF1 ─┬─ PCA9544A mux @ 0x58 → ADT7462 #1 (Board Temp 1-3, Fan 1,2,5,6)
│                 ├─ PCA9544A mux @ 0x5C → ADT7462 #2 (Board Temp 4-6, Fan 3,4,7,8)
│                 └─ PCA9555 @ 0x20 (additional GPIO)
│
├── I2C Bus 0xF4 ─┬─ PCA9548 mux #1 (ch 0-7) → TMP100 @ 0x5C (PCIE 1-8 Temp)
│                 └─ PCA9548 mux #2 (ch 0-7) → TMP100 @ 0x5C (PCIE 9-16 Temp)
│
├── I2C Bus 0xF6 ─┬─ PCA9555 @ 0x20 (PCIe 1-8 presence)
│                 ├─ PCA9555 @ 0x21 (PCIe 9-16 presence)
│                 ├─ PCA9555 @ 0x22 (PCIe power control)
│                 ├─ PCA9555 @ 0x23 (PCIe status/LED)
│                 └─ FB temp sensor @ 0x9E
│
├── I2C Bus 0xF2 ─── 24Cxx EEPROM @ 0xA0
│
└── PMBus ────────── 4x PSU (hot-pluggable power supplies)
```

### GPIO Pin Allocation

**AST2050 On-Chip GPIO (38 pins used):**
- **GPIOA-D** (group 0x4000): Interrupt-enabled sensor inputs (10 pins)
- **GPIOE-H** (group 0x4002): Mixed I/O - I2C interrupt, status signals (7 pins)
- **GPIOI-L** (group 0x4004): 16 data lines for PCIe/system status
- **GPIOM-P** (group 0x4006): System control outputs (5 pins)

**PCA9555 I2C GPIO Expanders (80 pins across 5 devices):**
- 4x PCA9555 on bus 0xF6 (16 pins each = 64 pins for PCIe slot management)
- 1x PCA9555 on bus 0xF1 (16 pins for additional status/control)

### Other IO Resources

| Resource | Count | Notes |
|----------|-------|-------|
| LEDs | 34 | Front panel status indicators |
| IPMB channels | 8 | 1 hardware + 7 virtual sub-channels |
| KCS interfaces | 2 | 1 hardware (0x0CA2) + 1 virtual |
| Ethernet | 1 | IPMI management LAN |
| UART | 1 | Serial console / SOL |
| EEPROM | 1 | 24Cxx at I2C 0xA0 |
| NVRAM stores | 3 | SDR (4KB) + SEL (8KB) + PS (12KB) |
| I2C mux channels | 4 | PCA9544A at 0x70 (7-bit) |
| IRQ lines | 6 | Hardware interrupt sources |
| PMBus PSUs | 4 | Hot-pluggable power supplies |

## Factory Default Configuration

| Setting | Value |
|---------|-------|
| IP Address | 192.168.0.120 |
| Subnet Mask | 255.255.255.0 |
| IP Source | DHCP |
| Username | root |
| Password | root |
| SNMP Community | public |
| SOL | Enabled, 115200 baud |
| Serial | 115200 baud, 8N1 |

## Key Observations

1. **The Dell C410X is purely a PCIe expansion chassis** - it has no CPU/memory of its
   own. The 72 IPMI sensors are dominated by PCIe slot monitoring (16 temp, 16 power,
   16 presence = 48 PCIe-related sensors).

2. **Massive I2C topology** - The BMC manages 4 distinct I2C buses with multiple levels
   of multiplexing (PCA9544A and PCA9548 muxes). This is necessary to address 16
   individually-monitored PCIe slots with dedicated temperature and power sensors.

3. **Two-tier driver architecture** - IOAPI handles low-level hardware access (GPIO
   reads/writes, I2C transactions), while IOSAPI handles sensor-level operations (read
   temperature, read fan speed, read power). This separation allows the same IOAPI
   driver to be shared across different sensor types.

4. **Table-driven design** - Nearly all hardware configuration is externalized into
   binary tables rather than hardcoded. This allows the same `fullfw` binary to support
   different Avocent MergePoint boards by swapping the table files.

5. **Avocent MergePoint platform** - The IO table architecture (IOAPI/IOSAPI, bmcsetting
   file mapping, MakeMemFile loading) is generic Avocent infrastructure, not Dell-specific.
   The Dell customization is entirely in the table contents, not the framework.

## Related Files

- [ANALYSIS.md](../ANALYSIS.md) - Full firmware reverse engineering analysis
- [RESOURCES.md](../RESOURCES.md) - Firmware download links and documentation references

## Methodology

This documentation was produced through:
1. Binary hex analysis of each table file
2. ARM disassembly of the `fullfw` binary (ELF, ARM926EJ-S) focusing on:
   - `HWInitIOTableV3`, `HWInitIOSensorTable`, `HWInitSmartIOIndexTable`
   - `HWInitFunctionTable`, `HWLoadDefaultValueTable`
   - `RawIOIdxTblGetIdx`, `SearchDefaultTable`
3. Symbol table extraction from the fullfw ELF binary
4. Cross-referencing IOAPI/IOSAPI structure addresses with their symbol names
5. SDR record parsing for IPMI sensor name resolution
6. Cross-referencing with I2C device datasheets (ADT7462, TMP100, INA219, PCA9555,
   PCA9544, PCA9548)

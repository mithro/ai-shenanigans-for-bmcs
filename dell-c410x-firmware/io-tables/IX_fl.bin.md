# IX_fl.bin - IO Index Cross-Reference Table

## Overview

| Property | Value |
|----------|-------|
| **File** | `etc/default/ipmi/evb/IX_fl.bin` |
| **Size** | 344 bytes |
| **Format** | Binary, little-endian |
| **bmcsetting section** | `[IOXTABLE]` |
| **Loading function** | `HWInitSmartIOIndexTable()` at 0x0007a340 in fullfw |
| **Lookup function** | `RawIOIdxTblGetIdx()` at 0x0008b9a8 in fullfw |
| **Global pointers** | `G_sIOIdxTblHeaderPtr`, `G_sIOIdxTblPtr` |

IX_fl.bin is an indirection layer that maps compact linear indices to (driver_type,
sub_index) tuples. This allows IPMI sensor numbers and other references to be decoupled
from the underlying hardware layout. When the system needs to find a sensor or IO
device, it looks up the linear index here to get the driver type and sub-index, then
uses those to find the correct entry in IO_fl.bin's dispatch table.

## Binary Layout

```
Offset  Size    Content
------  ------  --------------------------------------------------
0x0000  4       Header
0x0004  340     Entry table (85 entries x 4 bytes)
```

## Header (4 bytes)

```
Offset  Type   Value   Meaning
------  ----   -----   -------
0x00    u8     0x01    Table version
0x01    u8     0x00    Reserved
0x02    u16LE  0x0055  Number of entries = 85
```

## In-Memory Format

`HWInitSmartIOIndexTable()` loads the file via `MakeMemFileV2()`, which adds a 16-byte
wrapper header. The entry pointer is then `G_sIOIdxTblPtr = G_sIOIdxTblHeaderPtr + 0x10`.

## Entry Format (4 bytes)

```c
struct ix_entry {
    uint16_t driver_type;   // LE - index into OEM IOAPI dispatch table
    uint16_t sub_index;     // LE - sub-index within that driver's IO entries
};
```

## RawIOIdxTblGetIdx() Function

This function (420 bytes at 0x0008b9a8) implements a dual-mode lookup:

```c
int RawIOIdxTblGetIdx(uint16_t io_ref, uint16_t expected_driver_type, uint16_t *out_sub_index);
```

**Mode 1 - Direct (bit 15 clear):** `io_ref` itself IS the sub_index. The function
stores it directly into `*out_sub_index` and returns 0. No table lookup occurs.

**Mode 2 - Table Lookup (bit 15 set):** The lower 10 bits (`io_ref & 0x3FF`) serve as
an index into IX_fl.bin. The function:
1. Validates the index is within `entry_count`
2. Reads `entries[index].driver_type` and compares to `expected_driver_type`
3. If matched, stores `entries[index].sub_index` into `*out_sub_index`, returns 0
4. Returns 1 on any validation failure

## Driver Type Definitions

The `driver_type` field indexes into the **OEM IOAPI Dispatch Table** at 0x000f6fcc
in fullfw's `.rodata` section. This is a 30-entry array of pointers to IOAPI/IOSAPI
structures, initialized by `OEMDriverInit()` at 0x0000d758.

The four driver types used in IX_fl.bin:

| Type | Decimal | Symbol | Hardware Purpose |
|------|---------|--------|-----------------|
| 0x0E | 14 | ADT7462 I2C Fan/Temp IOSAPI | Temperature and fan tachometer reading (8 channels) |
| 0x0F | 15 | ADT7462 I2C Fan/Temp IOAPI | Fan/temp IO control - PWM, GPIO, config registers (37 channels) |
| 0x18 | 24 | PSU Event IOSAPI | Power supply event/status monitoring (6 channels) |
| 0x19 | 25 | OEM Sensor Housekeeping API | General-purpose sensor polling and maintenance (34 channels) |

## Complete Entry Decode

### Driver Type Distribution Summary

| Type | Count | Sub-Index Range | Purpose |
|------|-------|-----------------|---------|
| 0x0E (ADT7462 IOSAPI) | 8 | 0-7 | 8 ADT7462 analog sensor channels |
| 0x0F (ADT7462 IOAPI) | 37 | 1-101 (sparse) | ADT7462 control/config channels |
| 0x18 (PSU Event) | 6 | 0-5 | 6 PSU event channels |
| 0x19 (OEM Sensor HK) | 34 | 0-33 | 34 sensor housekeeping tasks |
| **Total** | **85** | | |

### All 85 Entries

```
Index  Type  Sub   Description
-----  ----  ----  -----------
  0    0x18    0   PSU Event channel 0
  1    0x18    1   PSU Event channel 1
  2    0x0E    3   ADT7462 sensor: Remote Temp 2 (#1)
  3    0x0E    2   ADT7462 sensor: Remote Temp 1 (#1)
  4    0x0E    6   ADT7462 sensor: Remote Temp 2 (#2)
  5    0x0E    7   ADT7462 sensor: Local Temp (#2)
  6    0x0E    1   ADT7462 sensor: Remote Temp 1 (#1) alt
  7    0x0E    0   ADT7462 sensor: base channel
  8    0x0E    4   ADT7462 sensor: Local Temp (#1)
  9    0x0E    5   ADT7462 sensor: Remote Temp 1 (#2)
 10    0x19    0   OEM Sensor HK: task 0
 11    0x18    3   PSU Event channel 3
 12    0x18    4   PSU Event channel 4
 13    0x18    5   PSU Event channel 5
 14    0x19   32   OEM Sensor HK: task 32 (0x20)
 15    0x19    6   OEM Sensor HK: task 6
 16    0x19    7   OEM Sensor HK: task 7
 17    0x19    8   OEM Sensor HK: task 8
 18    0x19    9   OEM Sensor HK: task 9
 19    0x19    2   OEM Sensor HK: task 2
 20    0x19    3   OEM Sensor HK: task 3
 21    0x19    4   OEM Sensor HK: task 4
 22    0x19    5   OEM Sensor HK: task 5
 23    0x19   10   OEM Sensor HK: task 10 (0x0A)
 24    0x19   11   OEM Sensor HK: task 11 (0x0B)
 25    0x19   12   OEM Sensor HK: task 12 (0x0C)
 26    0x19   13   OEM Sensor HK: task 13 (0x0D)
 27    0x19   14   OEM Sensor HK: task 14 (0x0E)
 28    0x19   15   OEM Sensor HK: task 15 (0x0F)
 29    0x19   16   OEM Sensor HK: task 16 (0x10)
 30    0x19   17   OEM Sensor HK: task 17 (0x11)
 31    0x19   18   OEM Sensor HK: task 18 (0x12)
 32    0x19   19   OEM Sensor HK: task 19 (0x13)
 33    0x19   20   OEM Sensor HK: task 20 (0x14)
 34    0x19   21   OEM Sensor HK: task 21 (0x15)
 35    0x19   22   OEM Sensor HK: task 22 (0x16)
 36    0x19   23   OEM Sensor HK: task 23 (0x17)
 37    0x19   24   OEM Sensor HK: task 24 (0x18)
 38    0x19   25   OEM Sensor HK: task 25 (0x19)
 39    0x19   26   OEM Sensor HK: task 26 (0x1A)
 40    0x19   27   OEM Sensor HK: task 27 (0x1B)
 41    0x19   28   OEM Sensor HK: task 28 (0x1C)
 42    0x19   30   OEM Sensor HK: task 30 (0x1E)
 43    0x19   31   OEM Sensor HK: task 31 (0x1F)
 44    0x19   29   OEM Sensor HK: task 29 (0x1D)
 45    0x0F   30   ADT7462 IO: channel 30 (0x1E)
 46    0x0F   31   ADT7462 IO: channel 31 (0x1F)
 47    0x0F   32   ADT7462 IO: channel 32 (0x20)
 48    0x0F   33   ADT7462 IO: channel 33 (0x21)
 49    0x0F   99   ADT7462 IO: channel 99 (0x63)
 50    0x18    2   PSU Event channel 2
 51    0x0F  100   ADT7462 IO: channel 100 (0x64)
 52    0x0F  101   ADT7462 IO: channel 101 (0x65)
 53    0x0F    1   ADT7462 IO: channel 1
 54    0x0F    6   ADT7462 IO: channel 6
 55    0x0F    7   ADT7462 IO: channel 7
 56    0x0F    8   ADT7462 IO: channel 8
 57    0x0F    9   ADT7462 IO: channel 9
 58    0x0F    2   ADT7462 IO: channel 2
 59    0x0F    3   ADT7462 IO: channel 3
 60    0x0F    4   ADT7462 IO: channel 4
 61    0x0F    5   ADT7462 IO: channel 5
 62    0x0F   11   ADT7462 IO: channel 11 (0x0B)
 63    0x0F   13   ADT7462 IO: channel 13 (0x0D)
 64    0x0F   14   ADT7462 IO: channel 14 (0x0E)
 65    0x0F   15   ADT7462 IO: channel 15 (0x0F)
 66    0x0F   16   ADT7462 IO: channel 16 (0x10)
 67    0x0F   17   ADT7462 IO: channel 17 (0x11)
 68    0x0F   18   ADT7462 IO: channel 18 (0x12)
 69    0x0F   19   ADT7462 IO: channel 19 (0x13)
 70    0x0F   20   ADT7462 IO: channel 20 (0x14)
 71    0x0F   21   ADT7462 IO: channel 21 (0x15)
 72    0x0F   22   ADT7462 IO: channel 22 (0x16)
 73    0x0F   23   ADT7462 IO: channel 23 (0x17)
 74    0x0F   24   ADT7462 IO: channel 24 (0x18)
 75    0x0F   25   ADT7462 IO: channel 25 (0x19)
 76    0x0F   26   ADT7462 IO: channel 26 (0x1A)
 77    0x0F   27   ADT7462 IO: channel 27 (0x1B)
 78    0x0F   28   ADT7462 IO: channel 28 (0x1C)
 79    0x0F   29   ADT7462 IO: channel 29 (0x1D)
 80    0x0F   82   ADT7462 IO: channel 82 (0x52)
 81    0x19    1   OEM Sensor HK: task 1
 82    0x19   33   OEM Sensor HK: task 33 (0x21)
 83    0x0F   35   ADT7462 IO: channel 35 (0x23)
 84    0x0F   37   ADT7462 IO: channel 37 (0x25)
```

## Relationship to Other Tables

```
  Sensor Read Request
         │
         ▼
  ┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
  │ IS_fl.bin        │────▶│ IX_fl.bin     │────▶│ IO_fl.bin    │
  │ (Sensor Table)   │     │ (Index Table) │     │ (IO Table)   │
  │                  │     │               │     │              │
  │ sensor_num ──┐   │     │ idx ──────┐   │     │ dispatch[type]│
  │ IOSAPI ptr   │   │     │ driver_type│   │     │  + sub_index │
  │ I2C params   │   │     │ sub_index  │   │     │  = entry[]   │
  └──────────────┘   │     └────────────┘   │     │  = IOAPI ptr │
                     │                      │     └──────────────┘
                     ▼                      ▼
              IOSAPI Driver          IOAPI Driver
              (Read Sensor)          (Access Hardware)
```

1. **IS_fl.bin** maps an IPMI sensor number to its IOSAPI driver and I2C parameters
2. **IX_fl.bin** provides an additional indirection for IO references that need to
   resolve to a specific IO_fl.bin entry via (driver_type, sub_index)
3. **IO_fl.bin** contains the actual hardware access descriptors with IOAPI pointers

## Further Investigation

- [ ] Map ADT7462 IO sub_indices (type 0x0F) to specific register operations
- [ ] Determine which sensor manager functions use table-lookup mode (bit 15 set)
- [ ] Cross-reference OEM Sensor HK tasks with fullfw's sensor polling loop
- [ ] Investigate why some ADT7462 IO sub_indices are sparse (gaps at 10, 12, etc.)

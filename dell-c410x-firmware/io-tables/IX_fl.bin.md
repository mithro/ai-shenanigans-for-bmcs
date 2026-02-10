# IX_fl.bin -- Index Cross-Reference Table

## What This File Does

IX_fl.bin is a translation layer that converts abstract index numbers into specific
hardware driver lookups. Think of it as a phone book: when the firmware has a sensor
reference number, it looks it up in this table to find out which driver handles that
sensor and which channel within the driver to use.

This indirection exists so that sensor numbering can stay stable even if the underlying
hardware layout changes. A sensor reference always means the same thing, even if the
driver mapping behind it is reorganized.

| Property | Value |
|----------|-------|
| **Location on BMC filesystem** | `/etc/default/ipmi/evb/IX_fl.bin` |
| **bmcsetting section name** | `[IOXTABLE]` |
| **Size** | 344 bytes |
| **Loading function in fullfw** | `HWInitSmartIOIndexTable()` at address 0x0007a340 |
| **Lookup function in fullfw** | `RawIOIdxTblGetIdx()` at address 0x0008b9a8 |

## File Structure

```
Bytes 0-3:     Header (version and entry count)
Bytes 4-343:   85 entries, 4 bytes each
```

### Header

- **Byte 0** = 0x01: Table version 1
- **Byte 1** = 0x00: Reserved
- **Bytes 2-3** = 85 (little-endian): Number of entries

### Entry Format

Each 4-byte entry is a pair:

```c
struct ix_entry {
    uint16_t  driver_type;   // Which OEM driver handles this device
    uint16_t  sub_index;     // Which channel within that driver
};
```

The `driver_type` indexes into the OEM IOAPI Dispatch Table (a 30-entry array of
driver pointers at 0x000f6fcc in fullfw). The `sub_index` tells that driver which
of its many channels to use.

## How the Firmware Looks Up an Index

The lookup function `RawIOIdxTblGetIdx()` (420 bytes at 0x0008b9a8) has two modes,
selected by the top bit of the reference number:

**Direct mode** (bit 15 = 0): The reference number IS the sub-index. No table lookup
happens at all. The firmware just uses the number directly. This is the fast path for
simple cases where the mapping is one-to-one.

**Table lookup mode** (bit 15 = 1): The lower 10 bits of the reference number become
an index into this table. The firmware reads the entry, checks that the `driver_type`
matches what was expected, and returns the `sub_index`. This is used when the mapping
is non-trivial (e.g., sensor 5 maps to ADT7462 channel 7, not channel 5).

```c
int RawIOIdxTblGetIdx(uint16_t io_ref, uint16_t expected_driver_type, uint16_t *out_sub_index)
{
    if (!(io_ref & 0x8000)) {
        // Direct mode: reference number IS the sub-index
        *out_sub_index = io_ref;
        return 0;
    }
    // Table lookup mode: use lower 10 bits as index
    int idx = io_ref & 0x3FF;
    if (idx >= entry_count) return 1;           // Out of range
    if (entries[idx].driver_type != expected_driver_type) return 1;  // Wrong driver
    *out_sub_index = entries[idx].sub_index;
    return 0;
}
```

## The Four Driver Types in This Table

All 85 entries use one of four driver types:

### Type 0x0E -- ADT7462 Sensor Readings (8 entries)

The ADT7462 IOSAPI (IO Sensor API) driver reads analog values from the two ADT7462
thermal management chips. Each entry represents one sensor channel: a temperature
reading or a fan tachometer input.

The 8 channels map to the ADT7462 entries in IO_fl.bin (see IO_fl.bin.md, Type 13):
- Channels 0-3: ADT7462 chip #1 (board region 1 temperatures and fan tachs)
- Channels 4-7: ADT7462 chip #2 (board region 2 temperatures and fan tachs)

### Type 0x0F -- ADT7462 Hardware Control (37 entries)

The ADT7462 IOAPI driver provides low-level register access to the ADT7462 chips.
Unlike the sensor reading driver above, this one handles configuration and control:
PWM fan speed settings, GPIO pins on the ADT7462, interrupt configuration, and direct
register reads/writes.

The 37 entries use sparse sub-indices (1-101), suggesting they map to specific ADT7462
register groups rather than sequential channels. Notable clusters:
- Sub-indices 1-9: Core configuration registers
- Sub-indices 11-29: Fan PWM and tachometer control registers
- Sub-indices 30-37: Extended configuration and status
- Sub-indices 82, 99-101: Special-purpose registers (possibly OEM extensions)

### Type 0x18 -- Power Supply Events (6 entries)

The PSU Event IOSAPI driver monitors the four hot-swappable power supplies for
status changes (insertion, removal, fault conditions). The 6 channels cover:
- Channels 0-1: Primary PSU status monitoring
- Channel 2: PSU enumeration/discovery
- Channels 3-5: Additional PSU event sources (fault, over-current, thermal)

### Type 0x19 -- Sensor Housekeeping (34 entries)

The OEM Sensor Housekeeping driver handles periodic sensor maintenance tasks: polling
sensors that don't generate interrupts, updating cached values, checking thresholds,
and triggering platform events when values go out of range.

The 34 tasks (sub-indices 0-33) correspond to sensor groups that need periodic
attention. The sensor polling loop in fullfw iterates through these entries on a
regular timer to keep all sensor readings current.

## Entry-by-Entry Decode

### ADT7462 Sensor Channels (indices 0-9, type 0x0E)

| Index | Sub-Index | Sensor |
|-------|-----------|--------|
| 2 | 3 | ADT7462 #1: Remote Temperature 2 |
| 3 | 2 | ADT7462 #1: Remote Temperature 1 |
| 6 | 1 | ADT7462 #1: Fan Tachometer (channel B) |
| 7 | 0 | ADT7462 #1: Fan Tachometer (channel A) |
| 8 | 4 | ADT7462 #1: Local (on-chip) Temperature |
| 5 | 7 | ADT7462 #2: Local (on-chip) Temperature |
| 4 | 6 | ADT7462 #2: Remote Temperature 2 |
| 9 | 5 | ADT7462 #2: Remote Temperature 1 |

### Power Supply Events (indices 0-1, 11-13, 50, type 0x18)

| Index | Sub-Index | Channel |
|-------|-----------|---------|
| 0 | 0 | PSU event channel 0 |
| 1 | 1 | PSU event channel 1 |
| 50 | 2 | PSU event channel 2 |
| 11 | 3 | PSU event channel 3 |
| 12 | 4 | PSU event channel 4 |
| 13 | 5 | PSU event channel 5 |

### Sensor Housekeeping Tasks (indices 10, 14-44, 81-82, type 0x19)

| Index | Sub-Index | Index | Sub-Index | Index | Sub-Index |
|-------|-----------|-------|-----------|-------|-----------|
| 10 | 0 | 23 | 10 | 36 | 23 |
| 81 | 1 | 24 | 11 | 37 | 24 |
| 19 | 2 | 25 | 12 | 38 | 25 |
| 20 | 3 | 26 | 13 | 39 | 26 |
| 21 | 4 | 27 | 14 | 40 | 27 |
| 22 | 5 | 28 | 15 | 41 | 28 |
| 15 | 6 | 29 | 16 | 44 | 29 |
| 16 | 7 | 30 | 17 | 42 | 30 |
| 17 | 8 | 31 | 18 | 43 | 31 |
| 18 | 9 | 32 | 19 | 14 | 32 |
|    |   | 33 | 20 | 82 | 33 |
|    |   | 34 | 21 |    |    |
|    |   | 35 | 22 |    |    |

### ADT7462 Hardware Control Channels (indices 45-84, type 0x0F)

| Index | Sub-Index | Index | Sub-Index | Index | Sub-Index |
|-------|-----------|-------|-----------|-------|-----------|
| 53 | 1 | 66 | 16 | 45 | 30 |
| 58 | 2 | 67 | 17 | 46 | 31 |
| 59 | 3 | 68 | 18 | 47 | 32 |
| 60 | 4 | 69 | 19 | 48 | 33 |
| 61 | 5 | 70 | 20 | 83 | 35 |
| 54 | 6 | 71 | 21 | 84 | 37 |
| 55 | 7 | 72 | 22 | 80 | 82 |
| 56 | 8 | 73 | 23 | 49 | 99 |
| 57 | 9 | 74 | 24 | 51 | 100 |
| 62 | 11 | 75 | 25 | 52 | 101 |
| 63 | 13 | 76 | 26 |    |     |
| 64 | 14 | 77 | 27 |    |     |
| 65 | 15 | 78 | 28 |    |     |
|    |    | 79 | 29 |    |     |

Note: Sub-indices 10, 12, 34, 36, and 38-81 are absent, suggesting those ADT7462
register groups are not used on the C410X hardware.

## How This Table Fits Into the Big Picture

```
  IPMI "Read Sensor" command
         |
         v
  IS_fl.bin (Sensor Table)
  "Sensor 0x50 uses IOSAPI driver X, and its IO reference has bit 15 set"
         |
         v
  IX_fl.bin (this file)
  "IO reference 0x8032 -> index 50 -> driver_type=0x18, sub_index=2"
         |
         v
  IO_fl.bin (Master IO Table)
  "driver_type 0x18, sub_index 2 -> PSU on I2C bus 0xF1, address 0x58"
         |
         v
  Actual hardware I2C transaction
```

The IS_fl.bin sensor table identifies the IOSAPI driver (high-level sensor logic)
and the IO reference. If the IO reference uses table-lookup mode (bit 15 set), this
table translates it into the (driver_type, sub_index) pair that IO_fl.bin needs to
find the right hardware descriptor. If the IO reference uses direct mode (bit 15 clear),
this table is skipped entirely.

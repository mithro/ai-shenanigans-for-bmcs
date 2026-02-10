# oemdef.bin - OEM Default Value Table

## Overview

| Property | Value |
|----------|-------|
| **File** | `etc/default/ipmi/evb/oemdef.bin` |
| **Size** | 1710 bytes (0x06AE) |
| **Format** | Binary, little-endian |
| **bmcsetting section** | `[DEFAULT]` |
| **Loading function** | `HWLoadDefaultValueTable()` in fullfw |
| **Lookup function** | `SearchDefaultTable()` in fullfw |
| **Global pointers** | `G_DefaultTableTOCPtr`, `G_pDefaultTableList`, `G_DefaultTableSizeList` |

oemdef.bin contains all factory default configuration values for the BMC. When NVRAM
Private Storage is uninitialized (all 0xFF) or when a "reset to factory defaults" is
performed, the BMC reads configuration values from this table. Each entry is addressed
by a (set_selector, channel, parameter) triple that maps to IPMI configuration commands.

## Binary Layout

```
Offset   Size    Content
------   ------  --------------------------------------------------
0x0000   4       File header
0x0004   56      Table of Contents (7 sections x 8 bytes)
0x003C   72      Section 0:  18 entries x  4 bytes (1-byte payloads)
0x0084   168     Section 1:  21 entries x  8 bytes (5-byte payloads)
0x012C   204     Section 2:  17 entries x 12 bytes (9-byte payloads)
0x01F8   64      Section 3:   4 entries x 16 bytes (13-byte payloads)
0x0238   380     Section 4:  19 entries x 20 bytes (17-byte payloads)
0x03B4   312     Section 5:  13 entries x 24 bytes (21-byte payloads)
0x04EC   448     Section 6:   8 entries x 56 bytes (53-byte payloads)
0x06AC   2       Trailing padding (zeros)
```

Total: 100 entries across 7 sections.

## File Header (4 bytes)

```
01 01 00 00
```

- Byte 0: version = 1
- Byte 1: sub-version/format = 1
- Bytes 2-3: reserved (0x0000)

## Table of Contents (56 bytes)

Seven 8-byte entries: `{ uint32_t offset, uint32_t entry_count }` (both LE):

| Section | Offset | Count | Entry Size | Data Payload | Section Bytes |
|---------|--------|-------|------------|--------------|---------------|
| 0 | 0x003C | 18 | 4 | 1 byte | 72 |
| 1 | 0x0084 | 21 | 8 | 5 bytes | 168 |
| 2 | 0x012C | 17 | 12 | 9 bytes | 204 |
| 3 | 0x01F8 | 4 | 16 | 13 bytes | 64 |
| 4 | 0x0238 | 19 | 20 | 17 bytes | 380 |
| 5 | 0x03B4 | 13 | 24 | 21 bytes | 312 |
| 6 | 0x04EC | 8 | 56 | 53 bytes | 448 |

**Key design insight:** Sections are grouped by data payload size, not by subsystem.
All IPMI parameters needing 1 byte of data go in section 0; those needing 5 bytes
go in section 1; etc. `SearchDefaultTable()` only scans the section matching the
expected data size for a given parameter, making lookups efficient.

## Entry Format (Common)

Each entry has a 3-byte key followed by a variable-length data payload:

```c
struct oemdef_entry {
    uint8_t  set_selector;   // Sub-index (user ID, filter #, destination #)
    uint8_t  channel;        // IPMI channel / PS group ID
    uint8_t  param;          // IPMI configuration parameter number
    uint8_t  data[];         // Payload (entry_size - 3 bytes)
};
```

### IPMI Channel Mapping

| Channel | Subsystem | Description |
|---------|-----------|-------------|
| 0 | User/Channel Access | Global user management and channel configuration |
| 1 | LAN Configuration (Primary) | Primary Ethernet interface |
| 2 | LAN Configuration (Secondary) | Secondary Ethernet (or shared NIC) |
| 3 | Serial/Modem + PEF | Serial port and Platform Event Filtering |
| 5 | SOL Configuration | Serial Over LAN |
| 6 | Chassis/System | Chassis power control and identification |
| 7 | System Timers | Watchdog and session timers |

---

## Section 0: Single-Byte Parameters (18 entries)

| # | Sel | Ch | Param | Value | Meaning |
|---|-----|----|-------|-------|---------|
| 0 | 0x00 | 0 | 0x05 | 0x10 | Channel access: privilege limit = Admin |
| 1 | 0x01 | 0 | 0x04 | 0x10 | Channel access: alternate privilege |
| 2 | 0x00 | 1 | 0x69 | 0x00 | LAN ch1: Dell OEM param 105 = disabled |
| 3 | 0x00 | 1 | 0x04 | **0x02** | **LAN ch1: IP Source = DHCP** |
| 4 | 0x00 | 2 | 0x03 | 0x84 | LAN ch2: auth type support |
| 5 | 0x00 | 2 | 0x04 | **0x02** | **LAN ch2: IP Source = DHCP** |
| 6 | 0x00 | 2 | 0x06 | 0x00 | LAN ch2: VLAN disabled |
| 7 | 0x00 | 3 | 0x01 | **0x03** | **Serial: Direct + Modem mode** |
| 8 | 0x00 | 3 | 0x02 | **0x0B** | **Serial: 115200 baud, 8N1** |
| 9 | 0x00 | 3 | 0x03 | 0x3C | Serial: session timeout = 60 |
| 10 | 0x00 | 3 | 0x04 | 0x3C | Serial: termination timeout = 60 |
| 11 | 0x00 | 3 | 0x50 | 0x28 | Serial: Dell OEM param 80 = 40 |
| 12 | 0x00 | 5 | 0x01 | **0x01** | **SOL: Enabled** |
| 13 | 0x00 | 5 | 0x02 | 0x84 | SOL: Force auth + encryption |
| 14 | 0x00 | 5 | 0x05 | **0x0A** | **SOL: 115200 baud** |
| 15 | 0x00 | 6 | 0x00 | 0x22 | Chassis: param 0 = 0x22 |
| 16 | 0x00 | 6 | 0x01 | 0x04 | Chassis: param 1 = 0x04 |
| 17 | 0x00 | 7 | 0x0E | 0x64 | System timer: param 14 = 100 |

## Section 1: 5-Byte Parameters (21 entries)

### LAN Alert Destination Types (entries 0-3)

| # | Sel | Ch | Param | Data | Meaning |
|---|-----|----|-------|------|---------|
| 0-3 | 0x00/0x08/0x10/0x18 | 1 | 0x12 | `00 00 00 00 00` | 4 alert destinations, all empty |

### LAN Authentication and Network (entries 4-6)

| # | Sel | Ch | Param | Data | Meaning |
|---|-----|----|-------|------|---------|
| 4 | 0x00 | 1 | 0x02 | `17 17 17 17 00` | **Auth types: None+MD2+MD5+Password at all privilege levels** |
| 5 | 0x00 | 1 | 0x03 | `C0 A8 00 78 00` | **Default IP: 192.168.0.120** |
| 6 | 0x00 | 1 | 0x06 | `FF FF FF 00 00` | **Subnet mask: 255.255.255.0** |

### LAN Channel 2 (entries 7-10)

| # | Sel | Ch | Param | Data | Meaning |
|---|-----|----|-------|------|---------|
| 7 | 0x00 | 2 | 0x02 | `17 17 17 17 00` | Same auth types as ch1 |
| 8 | 0x00 | 2 | 0x07 | `00 07 00 00 00` | IPv4 header params |
| 9 | 0x00 | 2 | 0x08 | `06 08 00 00 00` | RMCP port config |
| 10 | 0x00 | 2 | 0x1D | `23 11 00 00 00` | Bad password threshold = 35, reset interval |

### Serial/Modem Init (entries 11-18)

| # | Sel | Ch | Param | Data | Meaning |
|---|-----|----|-------|------|---------|
| 11-18 | 0x00-0x07 | 3 | 0x09 | various | 8 modem init string / terminal config blocks |

### SOL Configuration (entries 19-20)

| # | Sel | Ch | Param | Data | Meaning |
|---|-----|----|-------|------|---------|
| 19 | 0x00 | 5 | 0x03 | `0A FF 00 00 00` | **SOL: char accumulate 10ms, threshold 255 bytes** |
| 20 | 0x00 | 5 | 0x04 | `07 30 00 00 00` | **SOL: retry count 7, interval 480ms** |

## Section 2: 9-Byte Parameters (17 entries)

### Per-User Channel Access (entries 0-15)

Per-channel access rights for all 16 IPMI user slots (param 0x02, channel 0):

| User | Access Bytes | Decoded |
|------|-------------|---------|
| 0 (system) | `B4 B4 B4 B4 B4 34 34 34 00` | Admin, enabled on ch0-4; messaging+link on ch5-7 |
| 1 ("root") | `34 34 34 34 34 34 34 34 00` | **Admin privilege, messaging+link auth on all channels** |
| 2-15 (empty) | `8F 8F 8F 8F 8F 8F 8F 8F 00` | **No Access (priv=0xF), disabled** |

### Cipher Suite Privilege Levels (entry 16)

| # | Sel | Ch | Param | Data | Meaning |
|---|-----|----|-------|------|---------|
| 16 | 0x00 | 1 | 0x18 | `00 44 44 44 44 44 44 44 04` | All cipher suites require Admin privilege |

## Section 3: 13-Byte Parameters (4 entries)

### LAN Alert Destination Addresses

All 4 entries (sel 0x00/0x08/0x10/0x18, ch1, param 0x13) contain 13 zero bytes =
unconfigured alert destinations.

## Section 4: 17-Byte Parameters (19 entries)

### User Credentials (entries 0-2)

| # | Sel | Ch | Param | Data | Meaning |
|---|-----|----|-------|------|---------|
| 0 | 0x00 | 0 | 0x03 | `02 00` repeated x8 + `00` | System user access |
| 1 | 0x01 | 0 | 0x00 | **`root\0\0\0\0\0\0\0\0\0\0\0\0`** | **Default username = "root"** |
| 2 | 0x01 | 0 | 0x01 | **`root\0\0\0\0\0\0\0\0\0\0\0\0`** | **Default password = "root"** |

### User Access Rights (entries 3-17)

| # | Sel (User) | Param | Data | Meaning |
|---|------------|-------|------|---------|
| 3 | 1 (root) | 0x03 | `02 00` x8 + `00` | root: User-level privilege on all channels |
| 4-17 | 2-15 | 0x03 | all zeros | Disabled/unconfigured users |

### System Timer Configuration (entry 18)

| # | Sel | Ch | Param | Data (decoded LE) | Meaning |
|---|-----|----|-------|-------------------|---------|
| 18 | 0x00 | 7 | 0x11 | enabled=1, retries=0xFFFF, min=1000ms, max=3600000ms (1hr), interval=60s | Session/watchdog timer |

## Section 5: 21-Byte Parameters (13 entries)

### SNMP Community String (entry 0)

| # | Sel | Ch | Param | Data | Meaning |
|---|-----|----|-------|------|---------|
| 0 | 0x00 | 1 | 0x10 | **`public\0...`** | **SNMP community = "public"** |

### PEF Event Filter Templates (entries 1-12)

Platform Event Filtering rules with 21-byte payloads (18 standard + 3 OEM):

| Filter | Sensor Type | Event Type | Severity | Action | Description |
|--------|-------------|------------|----------|--------|-------------|
| 0 | 0x04 (Fan) | 0x01 (Threshold) | Critical | None | Fan critical alert template |
| 1 | 0x04 (Fan) | 0x01 (Threshold) | Non-critical | None | Fan warning template |
| 2 | 0x01 (Temperature) | 0x01 (Threshold) | Critical | None | Temperature critical template |
| 3 | 0x01 (Temperature) | 0x01 (Threshold) | Non-critical | None | Temperature warning template |
| 4 | 0xC0 (OEM/PCIe) | 0x01 (Threshold) | Critical | None | PCIe/GPU critical (Dell OEM) |
| 5 | 0xC0 (OEM/PCIe) | 0x01 (Threshold) | Non-critical | None | PCIe/GPU warning (Dell OEM) |
| 6 | 0x09 (Power Unit) | 0x6F (Sensor-specific) | Critical | None | Power unit event |
| 7 | 0x08 (Power Supply) | 0x6F (Sensor-specific) | Critical | None | PSU event |
| 8-11 | (Empty) | -- | -- | None | Unconfigured filter slots |

All filters default to Action=None (0x00). Actions are configured at deployment time
via IPMI Set PEF Configuration commands. Sensor type 0xC0 is Dell-specific for
PCIe/GPU slot monitoring.

## Section 6: 53-Byte Parameters (8 entries)

### PEF Alert Strings (all empty)

8 entries (sel 0-7, ch3, param 0x0C) all containing 53 zero bytes. These are PEF alert
string templates that can hold up to 53 characters of alert text.

## Factory Default Configuration Summary

| Setting | Default Value |
|---------|---------------|
| **IP Address** | 192.168.0.120 |
| **Subnet Mask** | 255.255.255.0 |
| **IP Source** | DHCP |
| **Username** | root |
| **Password** | root |
| **User Privilege** | User-level (2) on all channels |
| **Auth Types** | None, MD2, MD5, Straight Password |
| **SNMP Community** | public |
| **SOL** | Enabled, 115200 baud, authentication + encryption |
| **Serial** | 115200 baud, 8N1, 60s timeout |
| **PEF Filters** | 8 templates (fan, temp, OEM, power), all inactive |
| **Alert Destinations** | 4 slots, all empty |
| **Alert Strings** | 8 slots, all empty |
| **Cipher Suites** | All require Administrator privilege |
| **Users 2-15** | Disabled (No Access) |
| **Session Timeout** | Min 1s, Max 1hr, Default 60s |

## Security Notes

The factory defaults include some common IPMI security considerations:
- Default credentials `root`/`root` are well-known
- SNMP community `public` provides read access
- All authentication types enabled including `None` and weak `MD2`
- Only 1 user configured out of 16 available slots

These are typical of enterprise BMC firmware from this era (circa 2011-2013).

## Further Investigation

- [ ] Decode serial/modem init string fragments (section 1, entries 11-18)
- [ ] Verify PEF filter event data masks against IPMI specification
- [ ] Cross-reference Dell OEM sensor type 0xC0 with PCIe slot monitoring
- [ ] Map channel access byte format to IPMI v2.0 specification Table 6-1

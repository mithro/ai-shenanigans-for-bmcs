# oemdef.bin -- Factory Default Configuration

## What This File Does

oemdef.bin contains every factory default setting for the BMC. When the BMC's
persistent storage (NVRAM) is blank -- first boot, after a factory reset, or when a
specific setting has never been changed -- the firmware looks up the default value in
this table instead.

The file stores 100 configuration entries covering network settings, user accounts,
serial port configuration, SNMP communities, security options, and alert filters.
These are the settings an administrator sees when they first connect to a brand-new
Dell C410X over IPMI.

| Property | Value |
|----------|-------|
| **Location on BMC filesystem** | `/etc/default/ipmi/evb/oemdef.bin` |
| **bmcsetting section name** | `[DEFAULT]` |
| **Size** | 1,710 bytes |
| **Loading function in fullfw** | `HWLoadDefaultValueTable()` |
| **Lookup function in fullfw** | `SearchDefaultTable()` |

## How the Lookup Works

Each entry has a 3-byte key: **(set_selector, channel, parameter)**. These map directly
to IPMI configuration commands. When the firmware needs a default value, it calls
`SearchDefaultTable()` with the expected data size and the (set_selector, channel,
parameter) triple. The function only searches the section that matches the expected
data size, making lookups efficient.

```c
struct oemdef_entry {
    uint8_t  set_selector;   // Sub-index (user ID, filter number, destination number)
    uint8_t  channel;        // IPMI channel number
    uint8_t  param;          // IPMI configuration parameter number
    uint8_t  data[];         // Payload (varies by section)
};
```

### IPMI Channel Numbers Used

| Channel | What It Controls |
|---------|-----------------|
| 0 | User management and channel access rights |
| 1 | Primary Ethernet (LAN) interface |
| 2 | Secondary Ethernet interface |
| 3 | Serial/modem port and Platform Event Filtering |
| 5 | Serial Over LAN (SOL) |
| 6 | Chassis power control |
| 7 | System timers (watchdog, session timeout) |

## File Layout

The file groups entries by data payload size, not by subsystem. All 1-byte payloads
are in section 0, all 5-byte payloads are in section 1, and so on up to 53-byte
payloads in section 6. This size-based grouping makes lookups fast because the firmware
only needs to scan entries of the right size.

```
Bytes 0-3:        File header (version 1.1)
Bytes 4-59:       Table of contents (7 sections x 8 bytes)
Bytes 60-131:     Section 0:  18 entries x  4 bytes (1-byte payloads)
Bytes 132-299:    Section 1:  21 entries x  8 bytes (5-byte payloads)
Bytes 300-503:    Section 2:  17 entries x 12 bytes (9-byte payloads)
Bytes 504-567:    Section 3:   4 entries x 16 bytes (13-byte payloads)
Bytes 568-947:    Section 4:  19 entries x 20 bytes (17-byte payloads)
Bytes 948-1259:   Section 5:  13 entries x 24 bytes (21-byte payloads)
Bytes 1260-1707:  Section 6:   8 entries x 56 bytes (53-byte payloads)
Bytes 1708-1709:  Trailing padding (zeros)
```

Total: **100 entries** across 7 sections.

---

## The Factory Defaults -- What You Get Out of the Box

### Network Configuration

When first powered on, the BMC listens on a static IP address while also trying DHCP:

| Setting | Default | How It's Stored |
|---------|---------|----------------|
| **IP address** | 192.168.0.120 | Section 1, entry 5: `C0 A8 00 78` = 192.168.0.120 |
| **Subnet mask** | 255.255.255.0 | Section 1, entry 6: `FF FF FF 00` |
| **IP source** | DHCP | Section 0, entry 3: param 0x04 = 0x02 (DHCP) |
| **VLAN** | Disabled | Section 0, entry 6: param 0x06 = 0x00 |

Both LAN channels (1 and 2) default to DHCP. The static IP 192.168.0.120 is used as a
fallback when DHCP fails or during initial configuration.

Authentication types enabled on both LAN channels:
- **None** (no authentication required)
- **MD2** (weak hash, deprecated)
- **MD5** (moderate hash)
- **Straight password** (plaintext)

All four types are enabled at all privilege levels, stored as `17 17 17 17` in the auth
type entries.

### User Accounts

The BMC supports 16 user slots (0-15). Out of the box, only two are configured:

| User Slot | Username | Password | Privilege | Status |
|-----------|----------|----------|-----------|--------|
| 0 (system) | (internal) | (none) | Admin on channels 0-4, messaging on 5-7 | Always active |
| **1** | **root** | **root** | **Admin** | **Enabled on all channels** |
| 2-15 | (empty) | (empty) | No Access (0x0F) | Disabled |

The default credentials **root/root** are well-known across virtually all IPMI BMCs of
this era. The username and password are stored as null-padded 16-byte strings in
section 4 (17-byte payload entries).

User 0 is a special system account that cannot be deleted. Its access byte pattern
`B4 B4 B4 B4 B4 34 34 34` means Admin privilege with full access on channels 0-4, and
messaging+link-auth privilege on channels 5-7.

Users 2-15 all have access bytes `8F 8F 8F 8F 8F 8F 8F 8F` meaning No Access (privilege
level 0x0F) and disabled on all channels.

### Serial Port and Serial Over LAN (SOL)

| Setting | Default | Details |
|---------|---------|---------|
| **Serial mode** | Direct + Modem | Both connection types accepted |
| **Baud rate** | 115200, 8N1 | Standard BMC serial console speed |
| **Session timeout** | 60 seconds | Inactivity before disconnect |
| **Termination timeout** | 60 seconds | Time to wait for modem hangup |
| **SOL** | Enabled | Remote serial console access is on by default |
| **SOL baud rate** | 115200 | Matches physical serial port |
| **SOL authentication** | Required | Auth + encryption enforced |
| **SOL char accumulate** | 10ms | Buffer characters for 10ms before sending |
| **SOL threshold** | 255 bytes | Send when buffer reaches 255 bytes |
| **SOL retries** | 7 | Retry failed packets up to 7 times |
| **SOL retry interval** | 480ms | Wait between retries |

SOL being enabled by default means an administrator can immediately access the host
server's serial console remotely through the BMC, without any additional configuration.

### SNMP

| Setting | Default |
|---------|---------|
| **Community string** | `public` |

The SNMP community string `public` provides read access to BMC status via SNMP. This is
standard for enterprise hardware but is a well-known default that should be changed in
production environments.

### Platform Event Filtering (PEF)

PEF allows the BMC to take automatic actions (send alerts, power cycle, etc.) when
specific hardware events occur. The factory defaults define 8 filter templates that
match common events, but all have their action set to "None" -- meaning they detect
events but don't do anything about them until an administrator configures the actions.

| Filter | What It Matches | Severity |
|--------|----------------|----------|
| 0 | Fan speed crossed **critical** threshold | Critical |
| 1 | Fan speed crossed **warning** threshold | Non-critical |
| 2 | Temperature crossed **critical** threshold | Critical |
| 3 | Temperature crossed **warning** threshold | Non-critical |
| 4 | PCIe/GPU slot **critical** event (Dell OEM sensor type 0xC0) | Critical |
| 5 | PCIe/GPU slot **warning** event (Dell OEM sensor type 0xC0) | Non-critical |
| 6 | Power unit event (sensor type 0x09) | Critical |
| 7 | Power supply event (sensor type 0x08) | Critical |

Four additional filter slots (8-11) are empty, available for custom rules.

Sensor type 0xC0 is a Dell-specific OEM sensor type used for PCIe/GPU slot monitoring.
This is not part of the standard IPMI specification.

### Alert Destinations

4 alert destination slots, all empty (unconfigured). These would hold IP addresses or
hostnames where the BMC sends SNMP traps or IPMI PET alerts when PEF filters trigger.

### Alert Strings

8 PEF alert string slots, each holding up to 53 characters. All empty by default. These
templates can contain human-readable text that gets included in alert notifications.

### Cipher Suites and Security

All IPMI cipher suites require Administrator privilege level. This is the most
restrictive setting, meaning only users with Admin access can establish encrypted
sessions. Stored as `00 44 44 44 44 44 44 44 04` in section 2.

### Chassis and System Timers

| Setting | Default |
|---------|---------|
| Chassis param 0 | 0x22 |
| Chassis param 1 | 0x04 |
| Bad password threshold | 35 attempts before lockout |
| Session timeout range | Min 1 second, Max 1 hour |
| Default session timeout | 60 seconds |
| Watchdog retries | 0xFFFF (effectively unlimited) |

### IPv4 Header and RMCP Configuration

For LAN channel 2, the defaults include IPv4 header parameters (0x00070000) and RMCP
(Remote Management and Control Protocol) port configuration (0x06080000). These control
low-level network packet formatting for IPMI-over-LAN communication.

---

## Section-by-Section Detailed Decode

### Section 0: Single-Byte Parameters (18 entries)

| # | Set | Ch | Param | Value | Meaning |
|---|-----|----|-------|-------|---------|
| 0 | 0x00 | 0 | 0x05 | 0x10 | Channel access: privilege limit = Admin |
| 1 | 0x01 | 0 | 0x04 | 0x10 | Channel access: alternate privilege = Admin |
| 2 | 0x00 | 1 | 0x69 | 0x00 | LAN ch1: Dell OEM parameter 105 = disabled |
| 3 | 0x00 | 1 | 0x04 | 0x02 | LAN ch1: IP source = DHCP |
| 4 | 0x00 | 2 | 0x03 | 0x84 | LAN ch2: auth type support flags |
| 5 | 0x00 | 2 | 0x04 | 0x02 | LAN ch2: IP source = DHCP |
| 6 | 0x00 | 2 | 0x06 | 0x00 | LAN ch2: VLAN disabled |
| 7 | 0x00 | 3 | 0x01 | 0x03 | Serial: Direct + Modem mode |
| 8 | 0x00 | 3 | 0x02 | 0x0B | Serial: 115200 baud, 8N1 |
| 9 | 0x00 | 3 | 0x03 | 0x3C | Serial: session timeout = 60 seconds |
| 10 | 0x00 | 3 | 0x04 | 0x3C | Serial: termination timeout = 60 seconds |
| 11 | 0x00 | 3 | 0x50 | 0x28 | Serial: Dell OEM parameter 80 = 40 |
| 12 | 0x00 | 5 | 0x01 | 0x01 | SOL: Enabled |
| 13 | 0x00 | 5 | 0x02 | 0x84 | SOL: Force authentication + encryption |
| 14 | 0x00 | 5 | 0x05 | 0x0A | SOL: 115200 baud |
| 15 | 0x00 | 6 | 0x00 | 0x22 | Chassis: configuration parameter 0 |
| 16 | 0x00 | 6 | 0x01 | 0x04 | Chassis: configuration parameter 1 |
| 17 | 0x00 | 7 | 0x0E | 0x64 | System timer: parameter 14 = 100 |

### Section 1: 5-Byte Parameters (21 entries)

| # | Set | Ch | Param | Data (hex) | Meaning |
|---|-----|----|-------|------------|---------|
| 0-3 | 0x00-0x18 | 1 | 0x12 | `00 00 00 00 00` | 4 alert destinations, all empty |
| 4 | 0x00 | 1 | 0x02 | `17 17 17 17 00` | Auth types: None+MD2+MD5+Password at all levels |
| 5 | 0x00 | 1 | 0x03 | `C0 A8 00 78 00` | Default IP: 192.168.0.120 |
| 6 | 0x00 | 1 | 0x06 | `FF FF FF 00 00` | Subnet mask: 255.255.255.0 |
| 7 | 0x00 | 2 | 0x02 | `17 17 17 17 00` | LAN ch2: same auth types |
| 8 | 0x00 | 2 | 0x07 | `00 07 00 00 00` | LAN ch2: IPv4 header params |
| 9 | 0x00 | 2 | 0x08 | `06 08 00 00 00` | LAN ch2: RMCP port config |
| 10 | 0x00 | 2 | 0x1D | `23 11 00 00 00` | Bad password threshold: 35, reset interval |
| 11-18 | 0x00-0x07 | 3 | 0x09 | (various) | 8 serial/modem init string blocks |
| 19 | 0x00 | 5 | 0x03 | `0A FF 00 00 00` | SOL: 10ms accumulate, 255-byte threshold |
| 20 | 0x00 | 5 | 0x04 | `07 30 00 00 00` | SOL: 7 retries, 480ms interval |

### Section 2: 9-Byte Parameters (17 entries)

Per-user channel access rights for all 16 IPMI user slots:

| User | Access Bytes (9 bytes) | Meaning |
|------|----------------------|---------|
| 0 (system) | `B4 B4 B4 B4 B4 34 34 34 00` | Admin on ch0-4; messaging+link on ch5-7 |
| 1 (root) | `34 34 34 34 34 34 34 34 00` | Admin privilege, messaging+link auth, all channels |
| 2-15 | `8F 8F 8F 8F 8F 8F 8F 8F 00` | No Access, disabled on all channels |

Plus one cipher suite entry (LAN ch1, param 0x18): `00 44 44 44 44 44 44 44 04` --
all cipher suites require Admin privilege.

### Section 3: 13-Byte Parameters (4 entries)

Four LAN alert destination address entries (ch1, param 0x13), all zeros = unconfigured.

### Section 4: 17-Byte Parameters (19 entries)

| # | Set | Ch | Param | Data | Meaning |
|---|-----|----|-------|------|---------|
| 0 | 0x00 | 0 | 0x03 | `02 00` repeated x 8, `00` | System user access template |
| 1 | 0x01 | 0 | 0x00 | `root` + 12 null bytes | Default username |
| 2 | 0x01 | 0 | 0x01 | `root` + 12 null bytes | Default password |
| 3 | 0x01 | 0 | 0x03 | `02 00` repeated x 8, `00` | User 1 (root): user-level on all channels |
| 4-17 | 0x02-0x0F | 0 | 0x03 | all zeros | Users 2-15: disabled |
| 18 | 0x00 | 7 | 0x11 | timer config (LE encoded) | Session timer: enabled, min=1s, max=1hr, interval=60s |

### Section 5: 21-Byte Parameters (13 entries)

| # | Set | Ch | Param | Data | Meaning |
|---|-----|----|-------|------|---------|
| 0 | 0x00 | 1 | 0x10 | `public` + 15 null bytes | SNMP community string |
| 1-12 | (various) | 3 | 0x11 | PEF filter data (21 bytes) | 12 Platform Event Filter templates |

PEF filter format: 18 bytes standard IPMI + 3 bytes Dell OEM extension.

### Section 6: 53-Byte Parameters (8 entries)

Eight PEF alert string slots (ch3, param 0x0C), all 53 bytes of zeros = empty templates.

---

## Security Observations

These factory defaults reflect typical enterprise BMC firmware from the 2011-2013 era:

- **Default credentials** `root`/`root` are well-known and should be changed immediately
- **SNMP community** `public` provides unauthenticated read access to BMC status
- **Authentication type "None"** is enabled, allowing unauthenticated IPMI sessions
- **MD2 authentication** is enabled but cryptographically weak (deprecated in IPMI v2.0)
- Only **1 of 16** user slots is configured, leaving plenty of room for proper user management
- All PEF alert **actions are disabled** -- events are detected but no alerts are sent until configured
- **SOL is enabled** by default with authentication required, which is reasonable for remote management

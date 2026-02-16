# PEX I2C Command Reference -- Dell C410X

Comprehensive reference for controlling PEX8696 and PEX8647 PCIe switches via
I2C on the Dell C410X GPU expansion chassis. This document covers the complete
set of I2C register transactions needed to power on/off GPU slots, configure
multi-host mode, and access PLX switch EEPROMs.

## Source

Reverse engineered from the Dell C410X BMC firmware:

- **Firmware:** Avocent MergePoint embedded firmware v1.35
- **Binary:** `fullfw` (ARM 32-bit little-endian ELF, not stripped, 3983 symbols)
- **Extracted from:** `backup/c410xbmc135.zip` -> SquashFS -> `/sbin/fullfw`
- **Decompiler:** Ghidra 11.3.1
- **Date:** 2026-02-16

## Target Hardware

- **Chassis:** Dell C410X (16-slot PCIe GPU expansion chassis)
- **BMC:** ASPEED AST2050 (ARM926EJ-S)
- **Downstream switches:** 4x Broadcom (PLX) PEX8696 (96-lane, 24-port, PCIe Gen2)
- **Upstream switches:** 2x Broadcom (PLX) PEX8647 (48-lane, 3-port, PCIe Gen2)
- **GPU slots:** 16 x16 PCIe slots, 4 per PEX8696 switch

---

## 1. Overview

The Dell C410X uses its AST2050 BMC to manage 16 GPU slots through I2C
register writes to PLX PCIe switches. The BMC performs three main categories
of operations:

1. **Slot power control** -- Power on/off individual GPU slots by writing
   PCIe Slot Control registers and triggering the PLX hardware power controller
2. **Multi-host mode switching** -- Reconfigure the PCIe lane topology to
   support 2:1, 4:1, or 8:1 host-to-GPU fan-out ratios
3. **EEPROM access** -- Read/write the PLX switch EEPROM for configuration
   persistence and serial numbers

All PLX switch register access uses the **PLX I2C slave protocol** -- a
4-byte command format that encodes the target port, register address, and
byte enables. This is a different (extended) protocol from the simpler
2-byte address protocol used by plxtools for smaller PLX switches.

---

## 2. I2C Bus Topology

### 2.1 Bus Configuration

All PEX switches are on **I2C bus 3** of the AST2050, with **no I2C mux**.

The firmware encodes bus and mux channel in a single byte: `0xF3`
- Lower nibble (`0x3`) = bus number 3
- Upper nibble (`0xF`) = mux channel 15 = no mux

The kernel driver is accessed via:
- **Device node:** `/dev/aess_i2cdrv` (Avocent Embedded Software Services)
- **Ioctl:** `0xC010B702` (read+write, 16-byte struct, type 0xB7, cmd 2)

### 2.2 I2C Address Map

| Device          | 8-bit Addr | 7-bit Addr | Function                          |
|-----------------|------------|------------|-----------------------------------|
| PEX8696 #0      | 0x30       | 0x18       | Downstream switch -- GPU slots 1, 2, 15, 16 |
| PEX8696 #1      | 0x34       | 0x1A       | Downstream switch -- GPU slots 3, 4, 13, 14 |
| PEX8696 #2      | 0x32       | 0x19       | Downstream switch -- GPU slots 5, 6, 11, 12 |
| PEX8696 #3      | 0x36       | 0x1B       | Downstream switch -- GPU slots 7, 8, 9, 10  |
| PEX8647 #0      | 0xD4       | 0x6A       | Upstream switch -- hosts 0-1                 |
| PEX8647 #1      | 0xD0       | 0x68       | Upstream switch -- hosts 2-3                 |

All addresses are in the **GBT (General Bus Target)** 8-bit format (7-bit address
left-shifted by 1). The kernel driver handles the R/W bit.

### 2.3 Physical Topology

```
                    iPass Cables (to hosts)
                     |   |   |   |
              +------+---+---+------+
              | PEX8647 #0 (0xD4)   |  Upstream switches
              | PEX8647 #1 (0xD0)   |  (host-side links)
              +------+---+---+------+
                     |   |   |
              +------+---+---+------+
              | PEX8696 #0 (0x30)   |  Downstream switches
              | PEX8696 #1 (0x34)   |  (GPU-side links)
              | PEX8696 #2 (0x32)   |  4 GPU slots per switch
              | PEX8696 #3 (0x36)   |
              +------+---+---+------+
                |  |  |  |  |  |  |
               GPU slots 1-16
```

---

## 3. PLX I2C Register Protocol

The PEX8696 and PEX8647 use the **PLX PEX8xxx I2C slave protocol** for
register access. This uses a 4-byte command header rather than a simple
2-byte register address.

### 3.1 Command Format

```
4-byte command:  [cmd] [stn_port] [enables_reg_hi] [reg_lo]

    Byte [0]: Command type
              0x03 = PLX_CMD_I2C_WRITE  (write 4 data bytes to register)
              0x04 = PLX_CMD_I2C_READ   (read 4 data bytes from register)

    Byte [1]: Station/Port selection
              bits [7:1] = (station << 1) | (port >> 1)
              bit  [0]   = 0 (always, for even ports within station)

    Byte [2]: Byte enables + register address high + port low bit
              bit  [7]   = port & 1  (low bit of port number)
              bits [5:2] = byte enable mask (0xF = all 4 bytes)
              bits [1:0] = register DWORD index bits [9:8]

    Byte [3]: Register DWORD index bits [7:0]
```

The register DWORD index = `(byte[2] & 0x03) << 8 | byte[3]`.
The register byte address = DWORD_index * 4.

In the Dell C410X firmware, byte[2] is almost always `0x3C` (byte enables =
all 4 bytes, reg_hi = 0, port_low = 0), so the DWORD index is simply byte[3].

### 3.2 Write Transaction

An I2C write transfers 8 bytes (4-byte command + 4-byte data):

```
I2C bus:  [START] [slave_addr+W] [cmd] [stn_port] [enables] [reg_lo]
                                 [val0] [val1] [val2] [val3] [STOP]

    bytes [0-3] = PLX command (cmd=0x03 for write)
    bytes [4-7] = 32-bit register value (little-endian)
```

### 3.3 Read Transaction

An I2C read uses a combined write-then-read (repeated start):

```
Phase 1 -- Write 4 bytes (command):
    [START] [slave_addr+W] [cmd=0x04] [stn_port] [enables] [reg_lo]

Phase 2 -- Read 4 bytes (data):
    [REPEATED START] [slave_addr+R] [val0] [val1] [val2] [val3] [STOP]
```

The 4 bytes read back are the 32-bit register value in little-endian order.

### 3.4 Byte Ordering

| Component               | Endianness      | Notes                                      |
|--------------------------|-----------------|---------------------------------------------|
| PLX command bytes        | Device-specific | 4 bytes sent as-is per PLX protocol          |
| Register value (read)    | Little-endian   | val[0] = bits [7:0], val[3] = bits [31:24]  |
| Register value (write)   | Little-endian   | Same byte order as read                      |
| I2C slave address        | 8-bit format    | 7-bit addr << 1 (e.g. 0x18 -> 0x30)         |

### 3.5 Comparison with plxtools 2-Byte Protocol

| Feature            | plxtools (2-byte addr) | Dell firmware (4-byte cmd)             |
|--------------------|------------------------|----------------------------------------|
| Address format     | 2 bytes (big-endian)   | 4 bytes (cmd, stn/port, enables, reg)  |
| Port selection     | Via BAR offset         | Encoded in bytes [1] and [2]           |
| Register offset    | 16-bit flat            | 10-bit DWORD index, per-port           |
| Byte enables       | Implicit (always 32b)  | Explicit in byte[2] bits [5:2]         |
| Target switches    | Smaller PLX parts      | PEX8696, PEX8647, and similar          |

The 4-byte protocol is necessary for the PEX8696 because it has 24 ports
organised into 6 stations. The port selection is packed into the I2C command
bytes. The plxtools I2C backend would need to be extended to support this
protocol for per-port register access on the PEX8696.

---

## 4. Register Reference

All registers are in the PEX8696/PEX8647 per-port configuration space,
addressed via the PLX 4-byte I2C command. The PCIe Express Capability base
is at offset **0x068** in PLX PEX8500/8600/8696 series switches (confirmed by
the PLX SDK `RegDefs.c`).

### 4.1 Complete Register Table

| Byte Addr | DWORD Idx | I2C byte[3] | Classification | Register Name | Chip | Used By |
|-----------|-----------|-------------|----------------|---------------|------|---------|
| 0x07C | 0x1F | 0x1F | PCIe Std (PLX-modified) | Slot Capabilities / Write Protect | PEX8696 | `pex8696_un_protect_reg` |
| 0x080 | 0x20 | 0x20 | PCIe Standard | Slot Control / Slot Status | PEX8696 | `pex8696_slot_power_on_reg`, `pex8696_slot_power_ctrl`, `all_slot_power_off_reg` |
| 0x1DC | 0x77 | 0x77 | PLX Proprietary | Port Merging / Aggregation | PEX8647 | `pex8647_cfg_multi_host_8`, `pex8647_cfg_multi_host_2_4` |
| 0x204 | 0x81 | 0x81 | PLX Proprietary | Port Control Mask | PEX8696 | `pex8696_cfg` |
| 0x228 | 0x8A | 0x8A | PLX Proprietary | Hot-Plug LED / MRL Control | PEX8696 | `pex8696_slot_power_on_reg`, `pex8696_slot_power_ctrl` |
| 0x234 | 0x8D | 0x8D | PLX Proprietary | Hot-Plug Power Controller | PEX8696/8647 | `pex8696_slot_power_on_reg`, `pex8647_cfg_multi_host_*` |
| 0x380 | 0xE0 | 0xE0 | PLX Proprietary | Lane Config (lower) | PEX8696 | `pex8696_cfg_multi_host_2`, `pex8696_cfg_multi_host_4` |
| 0x384 | 0xE1 | 0xE1 | PLX Proprietary | Lane Config (upper) | PEX8696 | `pex8696_cfg_multi_host_2`, `pex8696_cfg_multi_host_4` |
| 0x3AC | 0xEB | 0xEB | PLX Proprietary | NT Bridge Setup | PEX8696 | `pex8696_multi_host_mode_reg_set` |
| 0xB90 | 0x2E4 | 0xE4 | PLX Proprietary | SerDes EQ Coefficient 1 | PEX8696 | `pex8696_cfg` |
| 0xB9C | 0x2E7 | 0xE7 | PLX Proprietary | SerDes EQ Coefficient 2 | PEX8696 | `pex8696_cfg` |
| 0xBA4 | 0x2E9 | 0xE9 | PLX Proprietary | SerDes De-emphasis 1 | PEX8696 | `pex8696_cfg` |
| 0xBA8 | 0x2EA | 0xEA | PLX Proprietary | SerDes De-emphasis 2 | PEX8696 | `pex8696_cfg` |

**Note on SerDes registers:** For DWORD indices >= 0x100, byte[2] encodes
the high bits: DWORD index = `(byte[2] & 0x03) << 8 | byte[3]`. For 0x2E4,
byte[2] = `0x3E` (enables=0xF, reg_hi=2) and byte[3] = `0xE4`.

### 4.2 PCIe Standard Registers

#### Register 0x07C -- Slot Capabilities (PCIe Capability + 0x14)

PLX SDK name: `"PCIe Cap: Slot Capabilities"`

Standard PCIe bit fields (read-only from PCIe bus):

| Bits | Field | Description |
|------|-------|-------------|
| 0 | ABP | Attention Button Present |
| 1 | PCP | Power Controller Present |
| 2 | MRLSP | MRL Sensor Present |
| 3 | AIP | Attention Indicator Present |
| 4 | PIP | Power Indicator Present |
| 5 | HPS | Hot-Plug Surprise |
| 6 | HPC | Hot-Plug Capable |
| 14:7 | SPLV | Slot Power Limit Value |
| 16:15 | SPLS | Slot Power Limit Scale |
| 17 | EIP | Electromechanical Interlock Present |
| **18** | **NCCS/WP** | **PLX: Write Protect Enable (writable via I2C)** |
| 31:19 | PSN | Physical Slot Number |

**PLX extension:** Bit 18 is repurposed as a writable write-protect control when
accessed via I2C. When set (1), VS1 registers (0x200+) are write-protected.
Must be cleared before modifying hot-plug or lane configuration registers.

#### Register 0x080 -- Slot Control / Slot Status (PCIe Capability + 0x18)

PLX SDK name: `"PCIe Cap: Slot Status | Slot Control"`

Lower 16 bits = Slot Control (read-write):

| Bits | Mask | Field | Description |
|------|------|-------|-------------|
| 0 | 0x0001 | ABPE | Attention Button Pressed Enable |
| 1 | 0x0002 | PFDE | Power Fault Detected Enable |
| 2 | 0x0004 | MRLSCE | MRL Sensor Changed Enable |
| 3 | 0x0008 | PDCE | Presence Detect Changed Enable |
| 4 | 0x0010 | CCIE | Command Completed Interrupt Enable |
| 5 | 0x0020 | HPIE | Hot-Plug Interrupt Enable |
| 7:6 | 0x00C0 | AIC | Attention Indicator Control |
| **9:8** | **0x0300** | **PIC** | **Power Indicator Control** |
| **10** | **0x0400** | **PCC** | **Power Controller Control** |
| 11 | 0x0800 | EIC | Electromechanical Interlock Control |
| 12 | 0x1000 | DLLSCE | Data Link Layer State Changed Enable |

Upper 16 bits = Slot Status (read-only / RW1C):

| Bits | Mask | Field | Description |
|------|------|-------|-------------|
| 16 | 0x0001 | ABP | Attention Button Pressed (RW1C) |
| 17 | 0x0002 | PFD | Power Fault Detected (RW1C) |
| 18 | 0x0004 | MRLSC | MRL Sensor Changed (RW1C) |
| 19 | 0x0008 | PDC | Presence Detect Changed (RW1C) |
| 20 | 0x0010 | CC | Command Completed (RW1C) |
| 21 | 0x0020 | MRLSS | MRL Sensor State (RO) |
| 22 | 0x0040 | PDS | Presence Detect State (RO) |

**Indicator encoding (AIC and PIC):**

| Value | Meaning |
|-------|---------|
| 00b | Reserved |
| 01b | On |
| 10b | Blink |
| 11b | Off |

**PCC semantics:** 0 = Power On (slot powered), 1 = Power Off (slot not powered).

### 4.3 PLX Proprietary Registers

#### Register 0x228 -- Hot-Plug LED / MRL Control

| Bit | Firmware Use | Function |
|-----|-------------|----------|
| 21 | Set during power-on | Hot-Plug LED enable / MRL sensor override |

Only ever set (never cleared). Enables hardware hot-plug LED for the port.

#### Register 0x234 -- Hot-Plug Power Controller Control

| Bit | Firmware Use | Function |
|-----|-------------|----------|
| 0 | Pulsed (assert, wait 100ms, de-assert) | Hardware power sequence trigger |
| 8 | Mode-dependent (PEX8647) | Primary/secondary host port select |

**PEX8696 usage:** Bit 0 is pulsed to trigger the PLX hardware power controller.
The firmware asserts bit 0, waits ~100ms, then clears it. This initiates the
hardware-managed power-on sequence with inrush current control.

**PEX8647 usage:** During multi-host mode switching, bit 8 selects which upstream
port is the primary host port. Values differ between 8:1 and 2:1/4:1 modes.

#### Register 0x380/0x384 -- Port/Lane Configuration

Written to station 0, port 0 (the upstream/configuration port) during multi-host
mode switching. These registers control the PEX8696's internal crossbar routing
between upstream and downstream ports.

| Mode | Reg 0x384 | Reg 0x380 | Key Difference |
|------|-----------|-----------|----------------|
| 2:1 | 0x00101100 | 0x11010000 | Bits 8,12 set in 0x384 |
| 4:1 | 0x00100000 | 0x11011100 | Bits 8,12 set in 0x380 |
| 8:1 | 0x00100000 | 0x11011100 | Same as 4:1 (PEX8647 differs) |

#### Register 0x3AC -- NT Bridge Setup

Written to station 3, port 3 (global port 15) during multi-host configuration.
Value 0x01000000 configures the Non-Transparent Bridge port for inter-switch
communication.

#### Registers 0xB90-0xBA8 -- SerDes PHY Configuration

Written to all ports on all switches during mode switching. These control PCIe
Gen2 signal integrity parameters tuned for the C410X backplane:

| Register | DWORD | Value | Purpose |
|----------|-------|-------|---------|
| 0xB90 | 0x2E4 | 0x130E0E0E | Equalization coefficient 1 |
| 0xB9C | 0x2E7 | 0x1C151515 | Equalization coefficient 2 |
| 0xBA4 | 0x2E9 | 0x88888888 | De-emphasis 1 |
| 0xBA8 | 0x2EA | 0x88888888 | De-emphasis 2 |

#### Register 0x1DC (PEX8647) -- Port Merging / Aggregation

| Bit | 8:1 Mode | 2:1/4:1 Mode | Function |
|-----|----------|--------------|----------|
| 19 | 1 | 0 | Port merge enable (aggregates upstream ports) |

In 8:1 mode, setting bit 19 merges the PEX8647's two upstream ports to create
a wider aggregated link, allowing a single host to access 8 GPU slots.

---

## 5. Slot-to-Switch Mapping

### 5.1 Lookup Tables

The firmware uses two 16-entry lookup tables at ROM addresses `0xF7B06` and
`0xF7B16` to map slot index (0-15) to I2C address and PLX station/port
encoding. Three copies of the `get_PEX8696_addr_port` function (at `0x2E66C`,
`0x317E4`, `0x37F7C`) all reference identical table data.

**I2C Address Table (16 bytes):**
```
Raw hex: 30 30 34 34 32 32 36 36 36 36 32 32 34 34 30 30
```

**Port Number Table (16 bytes):**
```
Raw hex: 04 0A 04 0A 04 0A 02 08 04 0A 02 08 02 08 02 08
```

The "port number" is the pre-computed PLX I2C command byte[1] value, encoding
both station and port: `byte[1] = (station << 1) | (port >> 1)`.

### 5.2 Complete Slot Mapping

| Slot Idx | Phys Slot | I2C (8b) | I2C (7b) | Switch | Port Byte | Station | Port | Global Port |
|----------|-----------|----------|----------|--------|-----------|---------|------|-------------|
| 0 | Slot 1 | 0x30 | 0x18 | #0 | 0x04 | 2 | 0 | 8 |
| 1 | Slot 2 | 0x30 | 0x18 | #0 | 0x0A | 5 | 0 | 20 |
| 2 | Slot 3 | 0x34 | 0x1A | #1 | 0x04 | 2 | 0 | 8 |
| 3 | Slot 4 | 0x34 | 0x1A | #1 | 0x0A | 5 | 0 | 20 |
| 4 | Slot 5 | 0x32 | 0x19 | #2 | 0x04 | 2 | 0 | 8 |
| 5 | Slot 6 | 0x32 | 0x19 | #2 | 0x0A | 5 | 0 | 20 |
| 6 | Slot 7 | 0x36 | 0x1B | #3 | 0x02 | 1 | 0 | 4 |
| 7 | Slot 8 | 0x36 | 0x1B | #3 | 0x08 | 4 | 0 | 16 |
| 8 | Slot 9 | 0x36 | 0x1B | #3 | 0x04 | 2 | 0 | 8 |
| 9 | Slot 10 | 0x36 | 0x1B | #3 | 0x0A | 5 | 0 | 20 |
| 10 | Slot 11 | 0x32 | 0x19 | #2 | 0x02 | 1 | 0 | 4 |
| 11 | Slot 12 | 0x32 | 0x19 | #2 | 0x08 | 4 | 0 | 16 |
| 12 | Slot 13 | 0x34 | 0x1A | #1 | 0x02 | 1 | 0 | 4 |
| 13 | Slot 14 | 0x34 | 0x1A | #1 | 0x08 | 4 | 0 | 16 |
| 14 | Slot 15 | 0x30 | 0x18 | #0 | 0x02 | 1 | 0 | 4 |
| 15 | Slot 16 | 0x30 | 0x18 | #0 | 0x08 | 4 | 0 | 16 |

### 5.3 Switch-to-Slot Summary

Each PEX8696 manages exactly 4 GPU slots using stations 1, 2, 4, and 5
(global ports 4, 8, 16, and 20). Stations 0 and 3 are used for upstream
and NT bridge ports respectively.

| PEX8696 Switch | I2C Addr (8b) | Slots (1-based) | PLX Stations | Global Ports |
|----------------|---------------|-----------------|--------------|-------------|
| #0 (0x18) | 0x30 | 1, 2, 15, 16 | 1, 2, 4, 5 | 4, 8, 16, 20 |
| #1 (0x1A) | 0x34 | 3, 4, 13, 14 | 1, 2, 4, 5 | 4, 8, 16, 20 |
| #2 (0x19) | 0x32 | 5, 6, 11, 12 | 1, 2, 4, 5 | 4, 8, 16, 20 |
| #3 (0x1B) | 0x36 | 7, 8, 9, 10 | 1, 2, 4, 5 | 4, 8, 16, 20 |

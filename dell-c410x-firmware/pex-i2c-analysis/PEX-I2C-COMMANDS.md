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

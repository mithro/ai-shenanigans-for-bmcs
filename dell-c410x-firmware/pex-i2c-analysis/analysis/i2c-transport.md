# I2C Transport Layer Analysis - Dell C410X BMC Firmware

Analysis of the I2C transport functions in the Dell C410X BMC `fullfw` binary,
documenting how the firmware communicates with PLX PEX8696/PEX8647 PCIe switches
over I2C.

- **Binary:** `fullfw` (ARM 32-bit little-endian ELF, Avocent MergePoint firmware)
- **Decompiler:** Ghidra 11.3.1
- **Key functions analysed:**
  - `PI2CWriteRead` at `0x253C4` (760 bytes) -- core I2C transaction
  - `PI2CMuxWriteRead` at `0x256C4` (264 bytes) -- direct I2C (no mux)
  - `write_pex8696_register` at `0x2EAD4` (276 bytes) -- PLX register write
  - `read_pex8696_register` at `0x2EBF0` (296 bytes) -- PLX register read
  - `get_PEX8696_addr_port` at `0x2E66C` (160 bytes) -- slot-to-I2C mapping
  - `write_pex8647_register` at `0x36AD0` (276 bytes)
  - `read_pex8647_register` at `0x36998` (296 bytes)
  - `read_pex_register` at `0xDD0F8` (296 bytes) -- generic PLX register read
  - `write_pex_register` at `0xDD230` (276 bytes) -- generic PLX register write
  - `read_plx_eeprom` at `0xDD6CC` (268 bytes)
  - `write_plx_eeprom` at `0xDD7F0` (364 bytes)

---

## 1. I2C Bus Architecture

### 1.1 Bus/Mux Encoding

The firmware packs the I2C bus number and I2C mux channel into a single byte:

```
    bus_mux byte:  0xMB
                     │└─ lower nibble (bits 3:0) = bus number (0-6)
                     └── upper nibble (bits 7:4) = mux channel (0x0F = no mux)
```

From `PI2CWriteRead`:
```c
local_1b = param_1 & 0x0F;         // bus number (0-6)
local_1c = (param_1 & 0xF0) >> 4;  // mux channel (0x0F = none)
if (local_1b > 6) return 1;        // only buses 0-6 are valid
```

**For PEX switches:** The bus_mux value is always `0xF3`, meaning:
- Bus 3 (lower nibble `0x3`)
- No mux (upper nibble `0xF` = channel 15 = disabled)

This corresponds to the AST2050 I2C engine 3, which is directly connected
to the PEX8696 and PEX8647 switches without any I2C mux.

### 1.2 Kernel Driver Interface

The firmware communicates with the kernel via:

- **Device node:** `/dev/aess_i2cdrv` (Avocent Embedded Software Services I2C driver)
- **File descriptor:** stored at global `S_u32I2CDrvFD` (`0x10B52C`)
- **Ioctl number:** `0xC010B702`

#### Ioctl Number Decoding

```
    0xC010B702
    ├─ C  = direction: read+write (kernel reads struct AND writes back)
    ├─ 010 = struct size: 16 bytes (0x10)
    ├─ B7 = driver type magic: 0xB7
    └─ 02 = command number: 2 (I2C transfer)
```

#### Ioctl Structure Layout (16 bytes)

Reconstructed from ARM assembly at `0x25558`-`0x25594` (where the struct
fields are stored before the ioctl call at `0x255B0`):

```c
struct aess_i2c_xfer {
    void    *write_buf;    /* offset 0x00: pointer to write data buffer      */
    void    *read_buf;     /* offset 0x04: pointer to read data buffer       */
    uint8_t  bus_num;      /* offset 0x08: I2C bus number (0-6)              */
    uint8_t  slave_addr;   /* offset 0x09: 8-bit I2C slave address           */
    uint8_t  status;       /* offset 0x0A: result status (written by kernel) */
    uint8_t  write_len;    /* offset 0x0B: number of bytes to write          */
    uint8_t  read_len;     /* offset 0x0C: number of bytes to read           */
    uint8_t  flags;        /* offset 0x0D: transaction flags                 */
    uint8_t  _pad[2];      /* offset 0x0E: padding to 16 bytes               */
};  /* total size: 0x10 (16) bytes */
```

**Assembly evidence** (struct base at `fp - 0x2c`):

| Assembly                          | Field Assignment                          | Struct Offset |
|-----------------------------------|-------------------------------------------|---------------|
| `strb r3, [fp, #-0x24]`          | `bus_num = bus_number`                    | `+0x08`       |
| `strb r3, [fp, #-0x23]`          | `slave_addr = param_2`                    | `+0x09`       |
| `str  r3, [fp, #-0x2c]`          | `write_buf = param_4`                     | `+0x00`       |
| `strb r3, [fp, #-0x21]`          | `write_len = param_3`                     | `+0x0B`       |
| `str  r3, [fp, #8] -> [fp,-0x28]`| `read_buf = param_6`                      | `+0x04`       |
| `strb r3, [fp, #-0x20]`          | `read_len = param_5`                      | `+0x0C`       |
| `strb #0, [fp, #-0x22]`          | `status = 0` (cleared before call)        | `+0x0A`       |
| `strb r3, [fp, #-0x1f]`          | `flags = param_7`                         | `+0x0D`       |

**Note:** The `slave_addr` field uses **8-bit I2C addressing** (the address
left-shifted by 1, with the R/W bit in bit 0). The kernel driver handles
the R/W bit based on the write_len/read_len fields. For example, PEX8696 at
7-bit address `0x18` is passed as `0x30` (8-bit address).

### 1.3 Status Return Codes

After the ioctl call, the kernel writes a status byte back into the struct
at offset `0x0A`. `PI2CWriteRead` maps this to return codes:

| Kernel Status | PI2CWriteRead Return | Meaning                       |
|---------------|----------------------|-------------------------------|
| `0`           | `0`                  | Success                       |
| `1`           | `3`                  | NAK (no acknowledge)          |
| `2`           | `4`                  | Bus error                     |
| other         | `1`                  | General failure               |
| (ioctl fail)  | `1`                  | Ioctl system call failed      |
| (semaphore)   | `2`                  | Semaphore timeout (20 ticks)  |

### 1.4 Bus State Array

Each I2C bus has a 52-byte (0x34) state structure stored in the global
array `G_asI2CDrvBus` at `0x112634`:

```c
bus_state = G_asI2CDrvBus + (bus_num * 0x34);
```

Key fields within the state structure:
- `+0x10`: Semaphore handle (for mutual exclusion)
- `+0x21`: Bus operational flag (if 0 and transaction fails, force return 1)
- `+0x24`: Initialisation flag (`0x00` = not initialised, `0x01` = ready)

### 1.5 Concurrency Protection

`PI2CWriteRead` provides thread safety:
1. **Semaphore:** `_lx_SemaphoreGet(bus_state + 0x10, 0x14)` acquires a
   per-bus semaphore with a 20-tick timeout. Returns error code 2 on timeout.
2. **Mux handling:** If mux channel is not `0x0F` and flags is not `0x01`,
   calls `I2CMuxHandler(bus_mux, 0)` before the transaction and
   `I2CMuxHandler(bus_mux, 1)` after.
3. **PI2CMuxWriteRead** is a stripped-down variant that:
   - Forces mux channel to `0x0F` (no mux handling)
   - Has NO semaphore protection
   - Makes a direct ioctl call

---

## 2. PLX I2C Register Protocol

The PLX (Broadcom) PEX8696 and PEX8647 switches use a specific I2C
protocol for register access. The Dell C410X firmware implements this
in `write_pex8696_register` / `read_pex8696_register` and the
equivalent PEX8647 and generic functions.

### 2.1 Register Address Format

**Background:** Smaller PLX switches (e.g. PEX8733) use a simple 16-bit
register address space accessible via a 2-byte I2C address (big-endian).
This is the protocol implemented in
[plxtools](https://github.com/mithro/plxtools/blob/main/src/plxtools/backends/i2c.py):
```
Write: [START] [addr+W] [reg_hi] [reg_lo] [val0] [val1] [val2] [val3] [STOP]
Read:  [START] [addr+W] [reg_hi] [reg_lo]
       [RS]    [addr+R] [val0] [val1] [val2] [val3] [STOP]
```

**The PEX8696** is a much larger switch (96 lanes, 24 ports) with a
per-port register space. In PCIe BAR space, each port has a 0x1000-byte
register window (port N's registers are at offset `N * 0x1000`). Over
I2C, the PEX8696 uses an **extended 4-byte address format** that includes
both the port number and the register offset within that port.

In the firmware, registers are accessed via:

- `param_3` ("reg_start_byte"): A mode/byte-enable field
- `param_4` ("value_ptr"): A pointer to a buffer containing the port
  number, register offset, and (for writes) the register value

The actual register address and data are packed into the I2C write buffer
differently for read vs write operations.

### 2.2 Register Write Transaction

**Function:** `write_pex8696_register(bus_mux, i2c_addr, reg_start_byte, value_ptr)`

From the decompiled code:
```c
// local_20 is a uint32 on the stack
local_20 = (uint)param_3;                    // byte 0 = reg_start_byte
memcpy((void *)((int)&local_20 + 1), param_4, 7);  // bytes 1-7 = from value_ptr

PI2CWriteRead(bus_mux, i2c_addr, 8, &local_20, 0, 0, 0);
//             bus      addr     wr_len wr_buf  rd_len rd_buf flags
```

This builds an **8-byte write buffer**:

```
    Byte:  [0]    [1]    [2]    [3]    [4]    [5]    [6]    [7]
           │      └──────────── copied from value_ptr (7 bytes) ───────────┘
           └── reg_start_byte (param_3)

    On the I2C bus (write-only, no read phase):
    [START] [slave_addr+W] [byte0] [byte1] [byte2] [byte3] [byte4] [byte5] [byte6] [byte7] [STOP]
```

**Debug output** (format string at `0xF7BE0`):
```
LMD : cmd %02X %02X %02X %02X %02X %02X %02X %02X %02X
```
This prints: i2c_addr, then 8 bytes of the write buffer (total 9 values).

**Interpreting the 8 bytes using the PLX I2C slave protocol:**

The PLX PEX8xxx I2C slave protocol uses a 4-byte command followed by 4 data
bytes. The command byte format is documented in Chapter 7 ("I2C/SMBus Slave
Interface Operation") of PLX switch datasheets and confirmed by the
[Linux kernel PEX8xxx I2C driver patch](https://patchwork.kernel.org/patch/5000551/):

```c
// From the kernel patch (Danielle Costantino's implementation):
#define PLX_CMD_LEN             4
#define PLX_CMD_I2C_READ        0x04
#define PLX_CMD_I2C_WRITE       0x03
#define PLX_CMD3_EN_ALL_BYTES   0x3c     // bits 5:2 = 0b1111
#define PLX_REG_MASK            0xffc
#define PLX_REGISTER_ADDR(a)    ((uint16_t)((a & PLX_REG_MASK) >> 2))
#define PLX_PORT_SEL_B1(port)   (port >> 1)
#define PLX_PORT_SEL_B0(port)   ((port & 1) << 7)
```

**4-byte command structure:**
```
    Byte [0]: Command type
              0x03 = PLX_CMD_I2C_WRITE (write 4 data bytes)
              0x04 = PLX_CMD_I2C_READ  (read 4 data bytes)

    Byte [1]: Station/Port selection (high bits)
              [6:1] = station number (0-5 for PEX8696's 6 stations)
              [0]   = port high bit (port >> 1)
              Combined: (station << 1) | (port >> 1)

    Byte [2]: Byte enables + register address high + port low
              [7]   = port low bit ((port & 1) << 7)
              [5:2] = byte enable mask (0xF = all 4 bytes)
              [1:0] = register address bits [9:8]
              For all-bytes access: 0x3C | (reg_hi & 3) | (port_low << 7)

    Byte [3]: Register address low byte
              [7:0] = register address bits [7:0]
              The register DWORD index = (byte[2] & 3) << 8 | byte[3]
              The register BYTE address = DWORD_index << 2
```

**Write transaction (8 bytes):**
```
    [cmd=0x03] [station/port_hi] [enables|reg_hi|port_lo] [reg_lo] [val0] [val1] [val2] [val3]
    └────────── 4-byte command ──────────────────────────┘ └────── 4-byte value (LE) ──────┘
```

**Read transaction (4-byte write + 4-byte read):**
```
    Write: [cmd=0x04] [station/port_hi] [enables|reg_hi|port_lo] [reg_lo]
    Read:  [val0] [val1] [val2] [val3]  (4 bytes, little-endian)
```

### 2.3 Register Read Transaction

**Function:** `read_pex8696_register(bus_mux, i2c_addr, reg_start_byte, value_ptr)`

From the decompiled code:
```c
// local_1c is a uint32 on the stack
local_1c = (uint)param_3;                          // byte 0 = reg_start_byte
memcpy((void *)((int)&local_1c + 1), param_4, 3);  // bytes 1-3 = from value_ptr

PI2CWriteRead(bus_mux, i2c_addr, 4, &local_1c, 4, &local_1c, 0);
//             bus      addr     wr_len wr_buf  rd_len rd_buf  flags
```

This performs a **combined write-then-read** I2C transaction:

```
    Phase 1 - Write 4 bytes (register address):
    [START] [slave_addr+W] [byte0] [byte1] [byte2] [byte3]

    Phase 2 - Read 4 bytes (register value):
    [REPEATED START] [slave_addr+R] [data0] [data1] [data2] [data3] [STOP]
```

The 4-byte write buffer is the PLX I2C command (see Section 2.2):
```
    Byte [0]: reg_start_byte (param_3) = PLX command (0x04 = READ)
    Byte [1]: value_ptr[0]  = station/port encoding
    Byte [2]: value_ptr[1]  = byte enables | reg_hi | port_lo
    Byte [3]: value_ptr[2]  = register DWORD index low byte
```

The 4 bytes read back are the 32-bit register value (little-endian),
stored into `local_1c` and then copied out:
```c
memcpy(DAT_0002ed24, &local_1c, 4);  // -> PEX8696_Reg_Value global
```

**Debug output** (format string at `0xF7C18` and `0xF7C3C`):
```
LMD : cmd %02X %02X %02X %02X %02X        (i2c_addr + 4 address bytes)
LMD : value %02X %02X %02X %02X           (4 register value bytes)
```

### 2.4 Byte Ordering Summary

| Component               | Endianness     | Evidence                                   |
|--------------------------|----------------|--------------------------------------------|
| I2C register address     | Device-specific| 4 bytes sent MSB-first as per PLX protocol |
| Register value (read)    | Little-endian  | ARM stores natively; `value & 0xFF` = LSB  |
| Register value (write)   | Little-endian  | Copied from ARM memory directly             |
| I2C slave address        | 8-bit format   | Left-shifted 7-bit addr (e.g. 0x18 -> 0x30)|

### 2.5 PLX Register Address Construction by Callers

To understand the 4-byte register address, we can look at how callers
build the `value_ptr` buffer before calling `read/write_pex8696_register`.

From `pex8696_slot_power_on_reg` at `0x2F7C4`:
```c
get_PEX8696_addr_port(slot_index, &local_1b, &local_1c);
// local_1b = I2C address (e.g. 0x30)
// local_1c = PLX station/port encoding (e.g. 4)

*DAT_0002fa84 = local_1c;       // byte[0] = PLX station/port byte
DAT_0002fa84[1] = 0x3c;         // byte[1] = byte enables (all bytes)
DAT_0002fa84[2] = 0x20;         // byte[2] = register address low byte

read_pex8696_register(bus_mux, local_1b, 4, param_4);
//                     0xF3    addr      ^command=READ(4)
```

Inside `read_pex8696_register`, on little-endian ARM:
```c
local_1c = (uint)param_3;                          // byte 0 = 4 (command)
memcpy((void *)((int)&local_1c + 1), param_4, 3);  // bytes 1-3 from buffer
```

So the 4 bytes sent on the I2C wire are:
```
    Wire byte [0] = 0x04  (PLX_CMD_I2C_READ)
    Wire byte [1] = station/port encoding (from lookup table)
    Wire byte [2] = 0x3C  (PLX_CMD3_EN_ALL_BYTES, with reg_hi=0, port_lo=0)
    Wire byte [3] = 0x20  (register DWORD index low byte)
```

**Decoding the register addresses used in the firmware:**

The register DWORD index = `(byte[2] & 0x03) << 8 | byte[3]`.
The register byte address = DWORD_index * 4.
Since byte[2] is always `0x3C` (bits [1:0] = 0), DWORD_index = byte[3].

| Operation                 | byte[0] | byte[1]      | byte[2] | byte[3] | DWORD Idx | Byte Addr | PCIe Register |
|---------------------------|---------|--------------|----------|----------|-----------|-----------|---------------|
| Read Slot Control/Status  | 0x04    | stn/port     | 0x3C     | 0x20    | 0x020     | 0x080     | Per-port config 0x080 |
| Write Slot Control/Status | 0x03    | stn/port     | 0x3C     | 0x20    | 0x020     | 0x080     | Per-port config 0x080 |
| Read Hot-plug register    | 0x04    | stn/port     | 0x3C     | 0x8D    | 0x08D     | 0x234     | Per-port config 0x234 |
| Write Hot-plug register   | 0x03    | stn/port     | 0x3C     | 0x8D    | 0x08D     | 0x234     | Per-port config 0x234 |
| Read link/status register | 0x04    | stn/port     | 0x3C     | 0x8A    | 0x08A     | 0x228     | Per-port config 0x228 |
| Read write-protect reg    | 0x04    | stn/port     | 0x3C     | 0x1F    | 0x01F     | 0x07C     | Per-port config 0x07C |

**Comparison with plxtools 2-byte protocol:**

| Feature            | plxtools (2-byte addr) | Dell firmware (4-byte addr)            |
|--------------------|------------------------|----------------------------------------|
| Address format     | 2 bytes (big-endian)   | 4 bytes (cmd, stn/port, enables, reg)  |
| Port selection     | Via BAR offset         | Via byte[1] (station + port encoding)  |
| Register offset    | 16-bit flat            | 10-bit DWORD index, per-port           |
| Byte enables       | Implicit (always 32b)  | Explicit in byte[2] bits[5:2]          |
| Target switches    | Smaller PLX parts      | PEX8696, PEX8647, and similar          |

The 4-byte protocol is necessary for the PEX8696 because it has 24 ports
organised into 6 stations of 4 ports each. The port selection is packed
into bytes [1] and [2] of the I2C command.

---

## 3. Slot-to-I2C-Address Mapping

### 3.1 Mapping Function

**Function:** `get_PEX8696_addr_port(slot_index, &i2c_addr, &port_number)`
at `0x2E66C` (160 bytes).

```c
void get_PEX8696_addr_port(byte slot_index, byte *i2c_addr, byte *port_number) {
    byte addr_table[16];
    byte port_table[16];
    memcpy(addr_table, /* ptr at 0xF7B06 */, 16);
    memcpy(port_table, /* ptr at 0xF7B16 */, 16);
    *i2c_addr = addr_table[slot_index];
    *port_number = port_table[slot_index];
}
```

### 3.2 Lookup Table Data

Extracted from `fullfw` binary at file offsets `0xEFB06` (virtual `0xF7B06`)
and `0xEFB16` (virtual `0xF7B16`):

**All three copies of this function** (at `0x2E66C`, `0x317E4`, `0x37F7C`)
reference different pointer locations but all resolve to **identical table data**.

#### I2C Address Table (16 bytes at 0xF7B06)

```
Raw: 30 30 34 34 32 32 36 36 36 36 32 32 34 34 30 30
```

#### Port Number Table (16 bytes at 0xF7B16)

```
Raw: 04 0A 04 0A 04 0A 02 08 04 0A 02 08 02 08 02 08
```

### 3.3 Complete Slot Mapping

The "port number" in the lookup table is actually the pre-computed PLX I2C
byte[1] value, which encodes both the station and port-within-station:
`byte[1] = (station << 1) | (port >> 1)`.

| Slot Idx | Phys Slot | I2C (8b) | I2C (7b) | Switch | Port Byte | Station | Port | Global Port |
|----------|-----------|----------|----------|--------|-----------|---------|------|-------------|
| 0        | Slot 1    | 0x30     | 0x18     | #0     | 4         | 2       | 0    | 8           |
| 1        | Slot 2    | 0x30     | 0x18     | #0     | 10        | 5       | 0    | 20          |
| 2        | Slot 3    | 0x34     | 0x1A     | #1     | 4         | 2       | 0    | 8           |
| 3        | Slot 4    | 0x34     | 0x1A     | #1     | 10        | 5       | 0    | 20          |
| 4        | Slot 5    | 0x32     | 0x19     | #2     | 4         | 2       | 0    | 8           |
| 5        | Slot 6    | 0x32     | 0x19     | #2     | 10        | 5       | 0    | 20          |
| 6        | Slot 7    | 0x36     | 0x1B     | #3     | 2         | 1       | 0    | 4           |
| 7        | Slot 8    | 0x36     | 0x1B     | #3     | 8         | 4       | 0    | 16          |
| 8        | Slot 9    | 0x36     | 0x1B     | #3     | 4         | 2       | 0    | 8           |
| 9        | Slot 10   | 0x36     | 0x1B     | #3     | 10        | 5       | 0    | 20          |
| 10       | Slot 11   | 0x32     | 0x19     | #2     | 2         | 1       | 0    | 4           |
| 11       | Slot 12   | 0x32     | 0x19     | #2     | 8         | 4       | 0    | 16          |
| 12       | Slot 13   | 0x34     | 0x1A     | #1     | 2         | 1       | 0    | 4           |
| 13       | Slot 14   | 0x34     | 0x1A     | #1     | 8         | 4       | 0    | 16          |
| 14       | Slot 15   | 0x30     | 0x18     | #0     | 2         | 1       | 0    | 4           |
| 15       | Slot 16   | 0x30     | 0x18     | #0     | 8         | 4       | 0    | 16          |

**Note:** The "Global Port" is the PEX8696 port number (station*4 + port).
Since byte[2] bit 7 is always 0 (port_low=0), only even-numbered ports
within each station are used. The PEX8696 uses stations 1, 2, 4, and 5
for downstream GPU ports. Stations 0 and 3 are likely used for upstream
(host-facing) ports.

### 3.4 Switch-to-Slot Summary

| PEX8696 Switch | I2C Addr | Slots (index)      | PLX Stations Used  | Global Ports    |
|----------------|----------|---------------------|--------------------|-----------------|
| #0 (0x18)      | 0x30     | 0, 1, 14, 15       | 1, 2, 4, 5        | 4, 8, 16, 20   |
| #1 (0x1A)      | 0x34     | 2, 3, 12, 13       | 1, 2, 4, 5        | 4, 8, 16, 20   |
| #2 (0x19)      | 0x32     | 4, 5, 10, 11       | 1, 2, 4, 5        | 4, 8, 16, 20   |
| #3 (0x1B)      | 0x36     | 6, 7, 8, 9         | 1, 2, 4, 5        | 4, 8, 16, 20   |

Each PEX8696 manages exactly 4 GPU slots using global ports 4, 8, 16, and 20
(stations 1, 2, 4, and 5, port 0 within each station). These correspond to
x16 downstream ports on the 96-lane, 24-port PEX8696 switch.

### 3.5 GPU Power Sequencing Groups

The firmware powers GPUs in staggered groups to distribute inrush current:

| Group                   | Slots (1-based)   | Pattern               |
|-------------------------|-------------------|-----------------------|
| `gpu_power_on_4_8_12_16` | 4, 8, 12, 16   | One per PEX8696 switch |
| `gpu_power_on_3_7_11_15` | 3, 7, 11, 15   | One per PEX8696 switch |
| `gpu_power_on_2_6_10_14` | 2, 6, 10, 14   | One per PEX8696 switch |
| `gpu_power_on_1_5_9_13`  | 1, 5, 9, 13    | One per PEX8696 switch |

Each group activates one slot from each of the 4 PEX8696 switches simultaneously,
spreading the power load across the chassis.

---

## 4. Caller Usage Examples

### 4.1 Slot Power-On Sequence (`pex8696_slot_power_on_reg`)

For each active slot (determined by a 16-bit bitmask):

```
Step 1: Read register at DWORD index 0x20 (byte address 0x080)
    PEX8696_Command[0] = station_port_byte  // from lookup table
    PEX8696_Command[1] = 0x3C               // byte enables (all)
    PEX8696_Command[2] = 0x20               // register DWORD index
    read_pex8696_register(0xF3, i2c_addr, 4, &PEX8696_Command)
    // I2C: [04] [stn/port] [3C] [20]  -> read 4 bytes

Step 2: Modify and write (power indicator and attention bits)
    value[5] = (value[5] & 0xFC) | 0x01    // Set power indicator = ON
    value[5] = value[5] & 0xFB             // Clear attention indicator
    write_pex8696_register(0xF3, i2c_addr, 3, &PEX8696_Command)
    // I2C: [03] [stn/port] [3C] [20] [val0] [val1] [val2] [val3]

Step 3: Read register at DWORD index 0x8D (byte address 0x234)
    PEX8696_Command[1] = 0x3C
    PEX8696_Command[2] = 0x8D
    read_pex8696_register(0xF3, i2c_addr, 4, &PEX8696_Command)

Step 4: Assert power controller control (bit 0 of value[4])
    value[4] |= 0x01
    write_pex8696_register(0xF3, i2c_addr, 3, &PEX8696_Command)
    sleep(10 ticks)

Step 5: De-assert power controller control
    value[4] &= 0xFE
    write_pex8696_register(0xF3, i2c_addr, 3, &PEX8696_Command)

Step 6: Read register at DWORD index 0x8A (byte address 0x228) and set bit
    PEX8696_Command[1] = 0x3C
    PEX8696_Command[2] = 0x8A
    read_pex8696_register(0xF3, i2c_addr, 4, &PEX8696_Command)
    value[6] |= 0x20                     // Set MRL sensor present or LED bit
    write_pex8696_register(0xF3, i2c_addr, 3, &PEX8696_Command)
```

### 4.2 Write-Protection Removal (`pex8696_un_protect_reg`)

```
For each active slot:
    PEX8696_Command[0] = station_port_byte
    PEX8696_Command[1] = 0x3C
    PEX8696_Command[2] = 0x1F               // register DWORD index 0x1F (byte addr 0x07C)
    read_pex8696_register(0xF3, i2c_addr, 4, &PEX8696_Command)
    value[6] &= 0xFB                        // Clear write-protect bit
    write_pex8696_register(0xF3, i2c_addr, 3, &PEX8696_Command)
```

---

## 5. PEX8647 Access

### 5.1 Register Functions

The PEX8647 register access functions are **structurally identical** to
their PEX8696 counterparts:

| PEX8696 Function            | PEX8647 Function            | Difference |
|-----------------------------|-----------------------------|------------|
| `write_pex8696_register`    | `write_pex8647_register`    | Only debug strings and result globals |
| `read_pex8696_register`     | `read_pex8647_register`     | Only debug strings and result globals |

Both use the exact same I2C protocol:
- Write: 8 bytes (4 addr + 4 data), write-only
- Read: 4 bytes write (address), then 4 bytes read (data)

The only difference: `read_pex8647_register` copies only 2 bytes of the
result to its global (`memcpy(DAT, &local_1c, 2)` vs 4 bytes for PEX8696).
This may be a bug or may reflect that only 16-bit values are needed from
the PEX8647 in the multi-host configuration context.

### 5.2 PEX8647 I2C Addresses

From `pex8647_multi_host_mode_cfg` at `0x37944`:

```c
if (local_11 == 0) {
    local_18._0_2_ = 0xd4f3;   // bus_mux=0xF3, i2c_addr=0xD4
} else {
    local_18._0_2_ = 0xd0f3;   // bus_mux=0xF3, i2c_addr=0xD0
}
```

| PEX8647 Switch | 8-bit I2C Addr | 7-bit I2C Addr | Purpose                  |
|----------------|----------------|----------------|--------------------------|
| #0             | 0xD4           | 0x6A           | Upstream switch (hosts 0-1) |
| #1             | 0xD0           | 0x68           | Upstream switch (hosts 2-3) |

**Note:** The PEX8647 switches handle upstream/host-side PCIe links,
while the PEX8696 switches handle downstream/GPU-side PCIe links.

### 5.3 Multi-Host Configuration

The firmware supports 2-host, 4-host, and 8-host configurations via:
- `pex8696_cfg_multi_host_2` / `pex8696_cfg_multi_host_4` -- configure PEX8696 partitioning
- `pex8647_cfg_multi_host_2_4` / `pex8647_cfg_multi_host_8` -- configure PEX8647 routing
- `pex8696_multi_host_mode_cfg` -- iterates over all 4 PEX8696 switches
- `pex8647_multi_host_mode_cfg` -- iterates over both PEX8647 switches

In `pex8696_multi_host_mode_cfg`, each PEX8696 switch is addressed directly:

| Switch Index | bus_mux_and_addr encoding | I2C Addr |
|-------------|---------------------------|----------|
| 0           | `0x30F3`                  | 0x30     |
| 1           | `0x34F3`                  | 0x34     |
| 2           | `0x32F3`                  | 0x32     |
| 3           | `0x36F3`                  | 0x36     |

---

## 6. Generic PEX and EEPROM Access

### 6.1 Generic PEX Register Functions

`read_pex_register` at `0xDD0F8` and `write_pex_register` at `0xDD230`
are **structurally identical** to the PEX8696 versions. They use the same:
- 4-byte write address, 4-byte read data for reads
- 8-byte write (4 addr + 4 data) for writes
- Same `PI2CWriteRead` call conventions

These generic versions are used by the EEPROM and serial number subsystems
that work with any PLX switch.

### 6.2 PLX EEPROM Access

EEPROM access uses a **different path** -- it sends commands via a
message queue (`_lx_QueueSend`) rather than calling `PI2CWriteRead` directly.
This suggests EEPROM operations are handled asynchronously by a worker task.

From `read_plx_eeprom(param_1, param_2, param_3)`:
```c
// param_1: bus info, param_2: address info, param_3: 16-bit EEPROM offset
// Sends a queue message with:
//   - bus_mux = 0xF3
//   - slave_addr = determined by find_slave_addr()
//   - operation type = 4 (read EEPROM)
```

From `write_plx_eeprom(param_1, param_2, param_3, param_4)`:
```c
// param_4: pointer to 4 bytes of data to write
// Sends a queue message with:
//   - bus_mux = 0xF3
//   - slave_addr = determined by find_slave_addr()
//   - operation type = 3 (write EEPROM)
//   - 4 bytes of data copied from param_4
```

The queue message format includes the operation type, bus/address info,
and data, which is processed by `read_plx_eeprom_process` / `write_plx_eeprom_process`.

---

## 7. Hot-Plug GPIO Control

The `pex8696_hp_on` and `pex8696_hp_off` functions use `system()` calls
(16 switch cases for 16 slots) rather than I2C register writes. This
suggests hot-plug signalling uses GPIO lines controlled via shell commands
(likely through `/sys/class/gpio` or similar sysfs interfaces on the AST2050).

---

## 8. Complete I2C Address Map

All I2C devices on bus 3 (bus_mux `0xF3`) used by the PEX subsystem:

| Device          | 8-bit Addr | 7-bit Addr | Function                          |
|-----------------|------------|------------|-----------------------------------|
| PEX8696 #0      | 0x30       | 0x18       | GPU slots 1, 2, 15, 16           |
| PEX8696 #1      | 0x34       | 0x1A       | GPU slots 3, 4, 13, 14           |
| PEX8696 #2      | 0x32       | 0x19       | GPU slots 5, 6, 11, 12           |
| PEX8696 #3      | 0x36       | 0x1B       | GPU slots 7, 8, 9, 10            |
| PEX8647 #0      | 0xD4       | 0x6A       | Host upstream switch (hosts 0-1)  |
| PEX8647 #1      | 0xD0       | 0x68       | Host upstream switch (hosts 2-3)  |

**I2C bus:** AST2050 I2C engine 3, no mux (`bus_mux = 0xF3`)

---

## 9. PI2CWriteRead Full Parameter Mapping

```c
int PI2CWriteRead(
    byte  bus_mux,      // param_1: (mux_channel << 4) | bus_number
    byte  slave_addr,   // param_2: 8-bit I2C slave address
    byte  write_len,    // param_3: number of bytes to write (0-255)
    void *write_buf,    // param_4: pointer to write data buffer
    byte  read_len,     // param_5: number of bytes to read (0-255)
    void *read_buf,     // param_6: pointer to read data buffer
    char  flags         // param_7: flags (0x01 = skip mux handling)
);
// Returns: 0=success, 1=ioctl/general fail, 2=semaphore timeout, 3=NAK, 4=bus error
```

For a **write-only** transaction: `read_len = 0`, `read_buf = NULL`
For a **write-then-read** transaction: both `write_len > 0` and `read_len > 0`

---

## 10. Summary of Key Findings

1. **The I2C transport** uses the Avocent `aess_i2cdrv` kernel driver via
   a 16-byte ioctl struct (`0xC010B702`).

2. **PLX register access** uses the standard PLX I2C protocol:
   - **Write:** 8-byte I2C write = 4-byte address + 4-byte value
   - **Read:** 4-byte I2C write (address) + 4-byte I2C read (value)

3. **Register addresses** use the PLX 4-byte I2C command format:
   `[command, station/port_hi, byte_enables|reg_hi|port_lo, reg_lo]`
   where command is 0x03 (write) or 0x04 (read), as confirmed by the
   [Linux kernel PEX8xxx I2C driver](https://patchwork.kernel.org/patch/5000551/).

4. **All PEX switch types** (PEX8696, PEX8647, generic) use the **identical
   I2C register protocol**. The firmware has multiple copies of the same
   read/write functions linked into different subsystems.

5. **Slot mapping** uses a pair of 16-entry lookup tables mapping slot index
   (0-15) to I2C address and PLX station/port encoding. Each PEX8696 has
   4 GPU slots on global ports 4, 8, 16, and 20 (stations 1, 2, 4, 5).

6. **Concurrency** is handled by per-bus semaphores (20-tick timeout).
   `PI2CMuxWriteRead` bypasses this for direct, unprotected access.

7. **EEPROM access** is asynchronous via message queues, not direct I2C.

8. **Hot-plug control** uses GPIO (system() calls), not I2C registers.

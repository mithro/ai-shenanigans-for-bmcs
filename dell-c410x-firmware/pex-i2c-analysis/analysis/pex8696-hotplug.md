# PEX8696 Hot-Plug and Slot Power Control Analysis

Analysis of the PEX8696 hot-plug and slot power control functions in the Dell C410X
BMC `fullfw` binary, documenting the exact I2C register sequences used for GPU slot
power management.

- **Binary:** `fullfw` (ARM 32-bit little-endian ELF, Avocent MergePoint firmware)
- **Decompiler:** Ghidra 11.3.1
- **Prerequisite:** [I2C Transport Layer Analysis](i2c-transport.md)

---

## 1. Overview

The Dell C410X manages GPU slot power through a combination of:

1. **I2C register writes** to PEX8696 PCIe switch registers (slot power indicators,
   power controller control, hot-plug registers)
2. **GPIO commands** via `system()` calls (hot-plug attention signal assertion)
3. **Message queue operations** dispatching work to a background task

### Function Call Hierarchy

```
Start_GPU_Power_Sequence
  |
  +-- PSU_PGOOD() check
  |
  +-- [sets flag to trigger power-on sequence]
        |
        gpu_power_on_4_8_12_16    (group 1: slots 4, 8, 12, 16)
        gpu_power_on_3_7_11_15    (group 2: slots 3, 7, 11, 15)
        gpu_power_on_2_6_10_14    (group 3: slots 2, 6, 10, 14)
        gpu_power_on_1_5_9_13     (group 4: slots 1, 5, 9, 13)
          |
          +-- gpu_un_protect()          [GPU-side write protection removal]
          +-- pex8696_un_protect()      [PEX switch register unprotect via queue]
          |     +-- pex8696_un_protect_reg()  [actual I2C: read-modify-write reg 0x07C]
          +-- filter_on_gpu()           [filter slot bitmask by present GPUs]
          +-- pex8696_slot_power_on()   [slot power-on via queue]
          |     +-- pex8696_slot_power_on_reg()  [actual I2C: regs 0x080, 0x234, 0x228]
          +-- gpu_power_attention_pulse()  [attention indicator pulse]

pex8696_slot_power_ctrl             [called during runtime slot control]
  |
  +-- (power off path): sets indicator bits only
  +-- (power on path):  regs 0x080, 0x234, 0x228 + pex8696_hp_ctrl(1)
  +-- write_pex8696_register()
  +-- RawIRQEnable()

all_slot_power_off                  [emergency power-off via queue]
  +-- all_slot_power_off_reg()      [actual I2C: reg 0x080, set power-off bits]

pex8696_all_slot_power_off          [another power-off variant via queue]
  +-- pex8696_all_slot_off()        [I2C: write pre-built register data to all ports]
```

---

## 2. Hot-Plug GPIO Control

### 2.1 pex8696_hp_ctrl (at 0x00031454, 228 bytes)

This is the **dispatch function** for hot-plug GPIO control. It iterates over a
16-bit slot bitmask (stored as two bytes at `DAT_00031538`) and calls either
`pex8696_hp_on` or `pex8696_hp_off` for each active slot.

```c
void pex8696_hp_ctrl(char param_1) {
    for (local_12 = 0; local_12 < 2; local_12++) {      // 2 bytes of bitmask
        for (local_13 = 0; local_13 < 8; local_13++) {  // 8 bits per byte
            if ((DAT_00031538[local_12] >> local_13) & 1) {
                slot_index = local_12 * 8 + local_13;
                if (param_1 == 1)
                    pex8696_hp_off(slot_index);    // param_1=1 means DISABLE
                else
                    pex8696_hp_on(slot_index);     // param_1=0 means ENABLE
            }
        }
    }
}
```

**Key observations:**
- `param_1 == 1` triggers `pex8696_hp_off` (counter-intuitive: "1" = off)
- `param_1 != 1` (typically 0) triggers `pex8696_hp_on`
- The bitmask at `DAT_00031538` selects which slots to operate on
- Slot indices 0-15 map to physical slots 1-16

### 2.2 pex8696_hp_on (at 0x00031184, 232 bytes)

Enables hot-plug attention for a single slot via GPIO `system()` call.

```c
void pex8696_hp_on(undefined param_1) {
    switch(param_1) {
        case 0:  system(DAT_000312ac); break;  // Slot 1
        case 1:  system(DAT_000312b0); break;  // Slot 2
        ...
        case 15: system(DAT_000312e8); break;  // Slot 16
    }
}
```

The string data pointers (`DAT_000312ac` through `DAT_000312e8`) are spaced 4 bytes
apart, each pointing to a shell command string. These are likely GPIO sysfs commands
such as:
```
echo 1 > /sys/class/gpio/gpioN/value
```

**This function does NOT use I2C.** Hot-plug attention signalling is purely GPIO-based
on the AST2050 BMC.

### 2.3 pex8696_hp_off (at 0x000312ec, 232 bytes)

Disables hot-plug attention for a single slot via GPIO `system()` call.

Structurally identical to `pex8696_hp_on` but with different string data pointers
(`DAT_00031414` through `DAT_00031450`), presumably writing `0` instead of `1` to
the same GPIO pins.

**This function does NOT use I2C.**

---

## 3. Register Write-Protection Removal

Before modifying PEX8696 registers for slot power control, the firmware must remove
the write-protection on the target port registers. This is a prerequisite step
performed before any power-on sequence.

### 3.1 pex8696_un_protect (at 0x0002fdf8, 248 bytes) -- Queue Dispatcher

This function dispatches the unprotect operation via a message queue. It does not
directly perform I2C transactions.

```c
void pex8696_un_protect(byte *param_1) {
    printf("...", param_1[0], param_1[1]);   // log the slot bitmask

    // Copy 2-byte slot bitmask to shared buffer
    DAT_0002fef4[0] = param_1[0];
    DAT_0002fef4[1] = param_1[1];

    // Send queue message to trigger pex8696_un_protect_reg
    local_20 = DAT_0002fef8;    // callback function pointer
    local_24 = DAT_0002fefc;    // callback context
    local_18 = 0x430F3;         // bus_mux=0xF3, i2c_addr=0x30(?), cmd=0x04(?)
    _lx_QueueSend(DAT_0002ff00, &local_24, 0);
}
```

The `local_18 = 0x430F3` value encodes I2C parameters:
- `0xF3` = bus_mux (I2C bus 3, no mux)
- `0x43` likely encodes: `0x04` (read command) + `0x03` (write command), or
  serves as an operation type identifier for the queue handler

### 3.2 pex8696_un_protect_reg (at 0x0002fc74, 372 bytes) -- I2C Implementation

This is the actual register-level implementation. For each active slot in the
16-bit bitmask, it performs a **read-modify-write** on the write-protect register.

```c
undefined4 pex8696_un_protect_reg(
    undefined param_1,  // bus_mux (0xF3)
    undefined param_2,  // i2c_addr (from queue)
    undefined param_3,  // command byte (3 or 4)
    undefined4 param_4  // pointer to PEX8696_Command buffer
) {
    for (local_19 = 0; local_19 < 2; local_19++) {       // 2 bitmask bytes
        for (local_1a = 0; local_1a < 8; local_1a++) {   // 8 bits each
            if ((DAT_0002fde8[local_19] >> local_1a) & 1) {
                slot_index = local_19 * 8 + local_1a;
                get_PEX8696_addr_port(slot_index, &local_1b, &local_1c);

                // Step 1: READ register 0x07C (DWORD index 0x1F)
                DAT_0002fdec[0] = local_1c;    // station/port byte
                DAT_0002fdec[1] = 0x3C;        // byte enables (all 4 bytes)
                DAT_0002fdec[2] = 0x1F;        // register DWORD index
                read_pex8696_register(0xF3, local_1b, 4, param_4);
                memcpy(DAT_0002fdf0, DAT_0002fdf4, 4);  // save read value

                // Step 2: CLEAR write-protect bit and WRITE back
                DAT_0002fdec[6] &= 0xFB;      // clear bit 2 of byte[6]
                write_pex8696_register(0xF3, local_1b, 3, param_4);
            }
        }
    }
    return 0;
}
```

### 3.3 Unprotect I2C Transaction Detail

For each slot, the unprotect operation consists of exactly **2 I2C transactions**:

#### Transaction 1: Read Write-Protect Register

```
I2C Bus:      0xF3 (bus 3, no mux)
I2C Address:  varies per slot (0x30, 0x32, 0x34, or 0x36)
Operation:    Write 4 bytes, then Read 4 bytes

Write bytes (PLX command):
  [0] = 0x04                    PLX_CMD_I2C_READ
  [1] = <station/port byte>    from get_PEX8696_addr_port() lookup table
  [2] = 0x3C                   byte enables = all 4 bytes, reg_hi = 0
  [3] = 0x1F                   register DWORD index low byte

Register decoded:
  DWORD index = (0x3C & 0x03) << 8 | 0x1F = 0x001F
  Byte address = 0x1F * 4 = 0x007C
  This is a PLX proprietary register at offset 0x07C within the port's
  configuration space.
```

#### Transaction 2: Write Modified Value Back

```
I2C Bus:      0xF3
I2C Address:  same as read
Operation:    Write 8 bytes (no read)

Write bytes (PLX command + data):
  [0] = 0x03                    PLX_CMD_I2C_WRITE
  [1] = <station/port byte>    same as read
  [2] = 0x3C                   byte enables = all 4 bytes
  [3] = 0x1F                   same register
  [4] = <value[0]>             original byte 0 (unchanged)
  [5] = <value[1]>             original byte 1 (unchanged)
  [6] = <value[2]> & 0xFB      byte 2 with bit 2 CLEARED
  [7] = <value[3]>             original byte 3 (unchanged)

Modification:
  Register byte address 0x07C, byte offset 2 (i.e. bits [23:16] of the 32-bit reg)
  Bit 2 of that byte = bit 18 of the 32-bit register value
  Cleared to 0 = remove write protection
```

### 3.4 Register 0x07C Identification

Register byte address `0x07C` in PLX PEX8696 per-port configuration space corresponds
to the **Port Configuration** register area. In PLX datasheets, registers in the
`0x070-0x07F` range are typically part of the PLX-proprietary port control registers.

Bit 18 (byte 2, bit 2) being a write-protect bit is consistent with PLX switches
having a "VS0 Write Protect" or similar mechanism that prevents modification of
downstream port registers until explicitly cleared by the management controller.

---

## 4. Slot Power-On Sequence

### 4.1 pex8696_slot_power_on (at 0x0002fa90, 440 bytes) -- Queue Dispatcher

This function dispatches the slot power-on operation by sending **three** queue
messages, each triggering a different operation on a different subsystem.

```c
void pex8696_slot_power_on(byte *param_1) {
    printf("...", param_1[0], param_1[1]);    // log slot bitmask

    // Copy 2-byte slot bitmask to shared buffer
    DAT_0002fc4c[0] = param_1[0];
    DAT_0002fc4c[1] = param_1[1];

    // Message 1: PEX8696 register power-on sequence
    local_20 = DAT_0002fc50;     // callback: pex8696_slot_power_on_reg
    local_24 = DAT_0002fc54;     // context
    local_18 = 0x430F3;          // bus 3, no mux
    _lx_QueueSend(DAT_0002fc58, &local_24, 0);

    // Message 2: Secondary operation (different bus?)
    local_20 = DAT_0002fc60;     // callback
    local_24 = DAT_0002fc64;     // context
    local_18 = 0x80F0;           // bus 0, mux channel 8?
    _lx_QueueSend(DAT_0002fc58, &local_24, 0);

    // Message 3: Third operation (yet another bus)
    local_20 = DAT_0002fc68;     // callback
    local_24 = DAT_0002fc6c;     // context
    local_18 = 0x5CF4;           // bus 4, mux channel 5?
    _lx_QueueSend(DAT_0002fc58, &local_24, 0);
}
```

**Queue message parameters decoded:**
| Message | Bus/Mux  | Bus | Mux  | Likely Target                 |
|---------|----------|-----|------|-------------------------------|
| 1       | `0x430F3` | 3  | 0xF (none) | PEX8696 register ops via I2C bus 3 |
| 2       | `0x80F0`  | 0  | 8    | GPU/device on I2C bus 0, mux ch 8 |
| 3       | `0x5CF4`  | 4  | 5    | Another device on I2C bus 4, mux ch 5 |

Messages 2 and 3 likely control GPU power regulators or presence detection
on different I2C buses. The PEX8696 hot-plug register operations are in Message 1.

### 4.2 pex8696_slot_power_on_reg (at 0x0002f7c4, 700 bytes) -- I2C Implementation

This is the core slot power-on function. For each active slot in the bitmask,
it performs a sequence of **read-modify-write operations** on three PEX8696
port registers.

```c
undefined4 pex8696_slot_power_on_reg(
    undefined param_1,  // bus_mux (0xF3)
    undefined param_2,  // i2c_addr
    undefined param_3,  // command byte
    undefined4 param_4  // pointer to PEX8696_Command buffer
) {
    for (local_19 = 0; local_19 < 2; local_19++) {
        for (local_1a = 0; local_1a < 8; local_1a++) {
            if ((DAT_0002fa80[local_19] >> local_1a) & 1) {
                slot_index = local_19 * 8 + local_1a;
                get_PEX8696_addr_port(slot_index, &i2c_addr, &port_byte);

                // --- PHASE 1: Slot Control/Status Register (0x080) ---
                // Step 1a: READ register
                PEX8696_Command[0] = port_byte;
                PEX8696_Command[1] = 0x3C;      // byte enables
                PEX8696_Command[2] = 0x20;       // DWORD index
                read_pex8696_register(0xF3, i2c_addr, 4, param_4);
                memcpy(save_buf, read_result, 4);

                // Step 1b: Modify power/attention indicators
                PEX8696_Command[5] = (PEX8696_Command[5] & 0xFC) | 0x01;
                //                    clear bits [1:0], set to 01
                PEX8696_Command[5] = PEX8696_Command[5] & 0xFB;
                //                    clear bit 2

                // Step 1c: WRITE modified value back
                write_pex8696_register(0xF3, i2c_addr, 3, param_4);

                // --- PHASE 2: Hot-Plug Control Register (0x234) ---
                // Step 2a: READ register
                PEX8696_Command[1] = 0x3C;
                PEX8696_Command[2] = 0x8D;       // DWORD index
                read_pex8696_register(0xF3, i2c_addr, 4, param_4);
                memcpy(save_buf, read_result, 4);

                // Step 2b: Assert Power Controller Control
                PEX8696_Command[4] |= 0x01;      // set bit 0 of byte[4]
                write_pex8696_register(0xF3, i2c_addr, 3, param_4);

                // Step 2c: Wait 10 ticks (~100ms)
                _lx_ThreadSleep(10);

                // Step 2d: De-assert Power Controller Control
                PEX8696_Command[4] &= 0xFE;      // clear bit 0 of byte[4]
                write_pex8696_register(0xF3, i2c_addr, 3, param_4);

                // --- PHASE 3: Link Control Register (0x228) ---
                // Step 3a: READ register
                PEX8696_Command[1] = 0x3C;
                PEX8696_Command[2] = 0x8A;       // DWORD index
                read_pex8696_register(0xF3, i2c_addr, 4, param_4);
                memcpy(save_buf, read_result, 4);

                // Step 3b: Set MRL/LED bit
                PEX8696_Command[6] |= 0x20;      // set bit 5 of byte[6]
                write_pex8696_register(0xF3, i2c_addr, 3, param_4);
            }
        }
    }
    return 0;
}
```

### 4.3 Slot Power-On I2C Transaction Detail

For each slot, the power-on sequence consists of **8 I2C transactions**
(4 reads + 4 writes) across 3 registers:

#### Phase 1: Slot Control/Status Register (0x080)

**Register:** DWORD index 0x20 = byte address 0x080

This register corresponds to the **PCIe Slot Control / Slot Status** register
area within the PEX8696 port's configuration space. In the PCIe specification,
the Slot Control register is at offset 0x18 from the PCIe Capability structure.
In PLX switches, the PCIe capability is typically at offset 0x68, so Slot Control
is at 0x68 + 0x18 = 0x080.

**Transaction 1a: Read Slot Control/Status**
```
I2C Write (4 bytes):
  [0] = 0x04                    PLX_CMD_I2C_READ
  [1] = <station/port byte>    from lookup table
  [2] = 0x3C                   enables=all, reg_hi=0
  [3] = 0x20                   DWORD index = 0x20, byte addr = 0x080
I2C Read (4 bytes):
  [4..7] = register value (little-endian 32-bit)
```

**Transaction 1b: Write Modified Slot Control/Status**
```
I2C Write (8 bytes):
  [0] = 0x03                    PLX_CMD_I2C_WRITE
  [1] = <station/port byte>
  [2] = 0x3C
  [3] = 0x20
  [4] = <value byte 0>         unchanged
  [5] = <modified byte 1>      bits [1:0] = 01, bit 2 = 0
  [6] = <value byte 2>         unchanged
  [7] = <value byte 3>         unchanged
```

**Bit modifications in byte offset 1 of the register value (bits [15:8]):**

| Bits   | Original | New | Field (PCIe Slot Control)             |
|--------|----------|-----|---------------------------------------|
| [9:8]  | xx       | 01  | Power Indicator Control = ON (01b)    |
| [10]   | x        | 0   | Attention Indicator Control = OFF     |

In the PCIe Slot Control register (offset 0x18 from PCIe Capability):
- Bits [9:8] = Power Indicator Control: 01b = On, 10b = Blink, 11b = Off
- Bits [7:6] = Attention Indicator Control: 01b = On, 10b = Blink, 11b = Off

The firmware sets the power indicator to ON and clears the attention indicator,
signalling that the slot is powered and there are no attention conditions.

#### Phase 2: Hot-Plug Control Register (0x234)

**Register:** DWORD index 0x8D = byte address 0x234

This register is in the PLX-proprietary extended configuration space. Byte
address 0x234 is beyond the standard PCIe configuration space (which ends
at 0x0FF for Type 1 headers). In PLX PEX8696 switches, registers above 0x200
are proprietary extensions.

Register 0x234 appears to be a **PLX Hot-Plug Control** register, likely part
of the PLX VS1 (Vendor-Specific 1) capability that manages hardware-assisted
hot-plug operations.

**Transaction 2a: Read Hot-Plug Control**
```
I2C Write (4 bytes):
  [0] = 0x04
  [1] = <station/port byte>
  [2] = 0x3C
  [3] = 0x8D
I2C Read (4 bytes):
  [4..7] = register value
```

**Transaction 2b: Write with Power Controller Control asserted**
```
I2C Write (8 bytes):
  [0] = 0x03
  [1] = <station/port byte>
  [2] = 0x3C
  [3] = 0x8D
  [4] = <byte 0> | 0x01         bit 0 SET (Power Controller Control)
  [5] = <byte 1>                unchanged
  [6] = <byte 2>                unchanged
  [7] = <byte 3>                unchanged
```

**Sleep: 10 ticks (~100ms)**

The firmware asserts the Power Controller Control bit, waits for the power
supply to stabilise, then de-asserts it.

**Transaction 2c: Write with Power Controller Control de-asserted**
```
I2C Write (8 bytes):
  [0] = 0x03
  [1] = <station/port byte>
  [2] = 0x3C
  [3] = 0x8D
  [4] = <byte 0> & 0xFE         bit 0 CLEARED
  [5..7] = unchanged
```

**Bit modifications in byte offset 0 of the register value (bits [7:0]):**

| Bit | Assert | De-assert | Field                              |
|-----|--------|-----------|------------------------------------|
| 0   | 1      | 0         | Power Controller Control (pulse)   |

This is a **pulsed control**: the bit is set, held for ~100ms, then cleared.
This triggers the PLX switch's hardware power controller to initiate the
slot power-on sequence.

#### Phase 3: Link/MRL Control Register (0x228)

**Register:** DWORD index 0x8A = byte address 0x228

Also in the PLX proprietary register space. Register 0x228 appears related
to link control or MRL (Manual Retention Latch) sensor configuration.

**Transaction 3a: Read Link/MRL Register**
```
I2C Write (4 bytes):
  [0] = 0x04
  [1] = <station/port byte>
  [2] = 0x3C
  [3] = 0x8A
I2C Read (4 bytes):
  [4..7] = register value
```

**Transaction 3b: Write with MRL/LED bit set**
```
I2C Write (8 bytes):
  [0] = 0x03
  [1] = <station/port byte>
  [2] = 0x3C
  [3] = 0x8A
  [4] = <byte 0>               unchanged
  [5] = <byte 1>               unchanged
  [6] = <byte 2> | 0x20         bit 5 SET
  [7] = <byte 3>               unchanged
```

**Bit modifications in byte offset 2 of the register value (bits [23:16]):**

| Bit  | Value | Field                                    |
|------|-------|------------------------------------------|
| 21   | 1     | MRL Sensor Present or Hot-Plug LED enable |

Bit 21 of the 32-bit register at 0x228 being set likely enables the
hot-plug LED or indicates MRL sensor presence for the port. In PLX
switches, this register area controls extended link and hot-plug
hardware features.

---

## 5. Runtime Slot Power Control

### 5.1 pex8696_slot_power_ctrl (at 0x000332ac, 676 bytes)

This is the **runtime** slot power control function, called when an individual
slot needs to be powered on or off during normal operation (as opposed to the
bulk power-on during boot). It handles both power-on and power-off paths, and
is notably the only function that calls `pex8696_hp_ctrl`.

Unlike `pex8696_slot_power_on_reg` which iterates over a bitmask, this function
operates on a **single pre-selected port** -- the caller has already resolved
the slot to its I2C address and station/port encoding.

```c
undefined4 pex8696_slot_power_ctrl(
    undefined param_1,  // bus_mux (0xF3)
    undefined param_2,  // i2c_addr (pre-resolved)
    undefined param_3,  // PLX command byte (3=write, 4=read)
    undefined4 param_4  // pointer to PEX8696_Command buffer
) {
    // Setup: copy station/port and register address for reg 0x080
    DAT_00033550[0] = *DAT_00033554;    // station/port byte (pre-set by caller)
    DAT_00033550[1] = 0x3C;             // byte enables
    DAT_00033550[2] = 0x20;             // DWORD index 0x20 = reg 0x080
    memcpy(DAT_00033558, DAT_0003355c, 4);  // save current register value

    if (*DAT_00033560 == 1) {
        // ---- POWER OFF PATH ----
        printf("power off...");
        DAT_00033550[5] |= 0x03;        // Power Indicator = OFF (11b)
        DAT_00033550[5] |= 0x04;        // Attention Indicator = ON
    }
    else {
        // ---- POWER ON PATH ----
        printf("power on...");

        // Phase 1: Slot Control/Status (0x080) - set indicators
        DAT_00033550[5] = (DAT_00033550[5] & 0xFC) | 0x01;  // Power Ind = ON (01b)
        DAT_00033550[5] &= 0xFB;                             // Attention Ind = OFF
        write_pex8696_register(0xF3, i2c_addr, 3, param_4);

        // Phase 2: Hot-Plug Control (0x234) - pulse power controller
        DAT_00033550[1] = 0x3C;
        DAT_00033550[2] = 0x8D;
        read_pex8696_register(0xF3, i2c_addr, 4, param_4);
        memcpy(DAT_00033558, DAT_0003355c, 4);
        DAT_00033550[4] |= 0x01;          // Assert Power Controller Control
        write_pex8696_register(0xF3, i2c_addr, 3, param_4);
        _lx_ThreadSleep(10);               // Wait ~100ms
        DAT_00033550[4] &= 0xFE;          // De-assert Power Controller Control
        write_pex8696_register(0xF3, i2c_addr, param_3, param_4);

        // Phase 3: Link/MRL Control (0x228) - enable LED/MRL
        DAT_00033550[1] = 0x3C;
        DAT_00033550[2] = 0x8A;
        read_pex8696_register(0xF3, i2c_addr, 4, param_4);
        memcpy(DAT_00033558, DAT_0003355c, 4);
        DAT_00033550[6] |= 0x20;          // Set MRL/LED bit

        // Phase 4: Disable hot-plug attention GPIO
        pex8696_hp_ctrl(1);                // param=1 -> call pex8696_hp_off for each slot
    }

    // Common: Write final register value (0x228 for power-on, 0x080 for power-off)
    write_pex8696_register(0xF3, i2c_addr, param_3, param_4);

    // Re-enable IRQ
    memset(DAT_0003356c, 0, 2);
    RawIOIdxTblGetIdx(0x800C, 0x18, &local_1a);
    RawIRQEnable(local_1a);
    *DAT_00033570 = 0;
    return 0;
}
```

### 5.2 Power-On Path I2C Transactions (Single Slot)

The power-on path is nearly identical to `pex8696_slot_power_on_reg` but operates
on a single pre-selected slot. The I2C transactions are:

| # | Op    | Register | DWORD Idx | Modification                        |
|---|-------|----------|-----------|-------------------------------------|
| 1 | WRITE | 0x080    | 0x20      | Byte[5]: bits [1:0]=01, bit 2=0     |
| 2 | READ  | 0x234    | 0x8D      | (read current value)                |
| 3 | WRITE | 0x234    | 0x8D      | Byte[4]: bit 0=1 (assert PCC)       |
| 4 | sleep | --       | --        | 10 ticks (~100ms)                   |
| 5 | WRITE | 0x234    | 0x8D      | Byte[4]: bit 0=0 (de-assert PCC)    |
| 6 | READ  | 0x228    | 0x8A      | (read current value)                |
| 7 | GPIO  | --       | --        | pex8696_hp_ctrl(1) -> hp_off GPIOs  |
| 8 | WRITE | 0x228    | 0x8A      | Byte[6]: bit 5=1 (MRL/LED)          |

**Notable difference from pex8696_slot_power_on_reg:**
- The initial register 0x080 read is skipped (value already read by caller)
- `pex8696_hp_ctrl(1)` is called to disable hot-plug GPIOs after power-on
- IRQ is re-enabled at the end via `RawIRQEnable`

### 5.3 Power-Off Path I2C Transactions (Single Slot)

The power-off path is much simpler -- only **one write** to register 0x080:

| # | Op    | Register | DWORD Idx | Modification                        |
|---|-------|----------|-----------|-------------------------------------|
| 1 | WRITE | 0x080    | 0x20      | Byte[5]: bits [1:0]=11, bit 2=1     |

**Bit modifications for power-off (byte offset 1, bits [15:8] of reg 0x080):**

| Bits   | Value | Field (PCIe Slot Control)              |
|--------|-------|----------------------------------------|
| [9:8]  | 11    | Power Indicator Control = OFF (11b)    |
| [10]   | 1     | Attention Indicator Control = ON (01b) |

This sets the power indicator to OFF and turns the attention indicator ON,
signalling that the slot has been powered down and may need operator attention.

**The power-off path does NOT:**
- Touch the hot-plug control register (0x234) -- no power controller pulse
- Touch the link/MRL register (0x228)
- Call any GPIO functions

This suggests that the power-off is purely a "soft" indication change. The actual
power removal may be handled by the GPU power supply subsystem reacting to these
indicator changes, or by separate GPIO controls not visible in this function.

### 5.4 IRQ and State Management

After both paths, `pex8696_slot_power_ctrl` performs housekeeping:

```c
memset(DAT_0003356c, 0, 2);              // Clear 2-byte state buffer
RawIOIdxTblGetIdx(0x800C, 0x18, &local_1a);  // Get IRQ index for device 0x800C
RawIRQEnable(local_1a);                   // Re-enable hot-plug interrupt
*DAT_00033570 = 0;                        // Clear busy flag
```

The IRQ at index `0x800C` with sub-index `0x18` appears to be the hot-plug
event interrupt. It is disabled before the power sequence (by `Start_GPU_Power_Sequence`)
and re-enabled here after the sequence completes.

---

## 6. All-Slot Power-Off Sequences

There are **four** functions related to powering off all slots, operating at
different levels of the firmware stack.

### 6.1 all_slot_power_off (at 0x0002f2fc, 272 bytes) -- Queue Dispatcher

Sends **two** queue messages to power off all slots:

```c
void all_slot_power_off(void) {
    printf("all slot power off...");

    // Message 1: PEX8696 register power-off
    local_1c = DAT_0002f410;     // callback: all_slot_power_off_reg
    local_20 = DAT_0002f414;     // context
    local_14 = 0x430F3;          // bus 3, no mux
    _lx_QueueSend(DAT_0002f418, &local_20, 0);

    // Message 2: Secondary power-off (different bus)
    local_1c = DAT_0002f420;     // callback
    local_20 = DAT_0002f424;     // context
    local_14 = 0x80F0;           // bus 0, mux channel 8
    _lx_QueueSend(DAT_0002f418, &local_20, 0);
}
```

**Compared to `pex8696_slot_power_on` which sends 3 messages, this only sends 2.**
The third message (bus 4, mux 5) is absent -- likely because the device on that
bus only needs to be configured during power-on, not power-off.

### 6.2 all_slot_power_off_reg (at 0x0002f188, 360 bytes) -- I2C Implementation

This iterates over **all 16 slots** (unconditionally, no bitmask check) and sets
the power-off indicator bits on register 0x080.

```c
undefined4 all_slot_power_off_reg(
    undefined param_1,  // bus_mux (0xF3)
    undefined param_2,  // i2c_addr
    undefined param_3,  // command byte
    undefined4 param_4  // PEX8696_Command buffer
) {
    for (local_19 = 0; local_19 < 2; local_19++) {
        for (local_1a = 0; local_1a < 8; local_1a++) {
            // NOTE: No bitmask check -- operates on ALL 16 slots
            slot_index = local_19 * 8 + local_1a;
            get_PEX8696_addr_port(slot_index, &i2c_addr, &port_byte);

            // READ register 0x080
            DAT_0002f2f0[0] = port_byte;
            DAT_0002f2f0[1] = 0x3C;
            DAT_0002f2f0[2] = 0x20;     // DWORD index 0x20 = byte addr 0x080
            read_pex8696_register(0xF3, i2c_addr, 4, param_4);
            memcpy(DAT_0002f2f4, DAT_0002f2f8, 4);

            // MODIFY: set power-off indicators
            DAT_0002f2f0[5] |= 0x03;     // bits [1:0] = 11 (Power Indicator = OFF)
            DAT_0002f2f0[5] |= 0x04;     // bit 2 = 1 (Attention Indicator = ON)

            // WRITE back
            write_pex8696_register(0xF3, i2c_addr, 3, param_4);
        }
    }
    return 0;
}
```

#### Per-Slot I2C Transactions (x16 slots)

For each of the 16 slots:

**Transaction 1: Read Slot Control/Status**
```
I2C Write (4 bytes):  [04] [stn/port] [3C] [20]
I2C Read  (4 bytes):  [val0] [val1] [val2] [val3]
```

**Transaction 2: Write Modified Slot Control/Status**
```
I2C Write (8 bytes):  [03] [stn/port] [3C] [20] [val0] [modified_val1] [val2] [val3]
```

Where `modified_val1` has:
- Bits [1:0] = 11 (Power Indicator = OFF)
- Bit 2 = 1 (Attention Indicator = ON)

**Total: 32 I2C transactions (16 reads + 16 writes) across 4 PEX8696 switches.**

### 6.3 pex8696_all_slot_power_off (at 0x0003836c, 192 bytes) -- Alternate Queue Dispatcher

A separate all-slot-off dispatcher used in a different code path (likely the
multi-host configuration subsystem, given its address proximity to other
0x38xxx functions).

```c
void pex8696_all_slot_power_off(void) {
    printf("all slot power off...");
    memset(DAT_00038430, 0, 8);      // zero out 8-byte shared buffer

    // Single queue message
    local_1c = DAT_00038434;          // callback: pex8696_all_slot_off
    local_20 = DAT_00038430;          // context (zeroed buffer)
    local_14 = 0x330F3;              // bus 3, no mux
    _lx_QueueSend(DAT_00038438, &local_20, 0);
}
```

**Note the different queue parameter:** `0x330F3` instead of `0x430F3`. The
`0x33` prefix (vs `0x43`) may indicate a different operation type to the queue
handler -- perhaps a "write-all-ports" operation vs "per-slot" operation.

### 6.4 pex8696_all_slot_off (at 0x000375b8, 288 bytes) -- Bulk Port Write

This function takes a **different approach** from the per-slot functions. Instead
of iterating over a slot mapping table, it iterates over **all I2C addresses**
(0x30 to 0x36 in steps of 2) and writes pre-built register data to multiple
station/port targets on each switch.

```c
undefined4 pex8696_all_slot_off(
    undefined param_1,  // bus_mux (0xF3)
    byte param_2,       // starting I2C address (e.g. 0x30)
    undefined param_3,  // command byte
    undefined4 param_4  // PEX8696_Command buffer
) {
    // Load pre-built data from ROM
    memcpy(auStack_20, DAT_000376d8, 4);    // 4 station/port bytes
    memcpy(auStack_2c, DAT_000376dc, 6);    // 6 bytes of register data

    // Iterate over all PEX8696 I2C addresses
    for (local_19 = param_2; local_19 < 0x38; local_19 += 2) {
        // Iterate over 4 station/port targets
        for (local_21 = 0; local_21 < 4; local_21++) {
            DAT_000376e0[0] = auStack_20[local_21];   // station/port byte
            memcpy(DAT_000376e4, auStack_2c, 6);      // register data
            write_pex8696_register(0xF3, local_19, param_3, param_4);
        }
    }
    return 0;
}
```

**Address iteration:** Starting from `param_2` (likely 0x30) up to 0x36 (exclusive < 0x38),
stepping by 2. This covers all 4 PEX8696 I2C addresses:

| Iteration | I2C Addr (8-bit) | I2C Addr (7-bit) | PEX8696 Switch |
|-----------|------------------|-------------------|----------------|
| 0         | 0x30             | 0x18              | #0             |
| 1         | 0x32             | 0x19              | #2             |
| 2         | 0x34             | 0x1A              | #1             |
| 3         | 0x36             | 0x1B              | #3             |

**Station/port iteration:** The 4 bytes from `DAT_000376d8` are likely the 4
station/port bytes used for each switch's downstream ports. Based on the slot
mapping from i2c-transport.md, each PEX8696 uses global ports 4, 8, 16, 20
(station/port bytes 0x02, 0x04, 0x08, 0x0A).

**Register data:** The 6 bytes from `DAT_000376dc` are pre-built and contain
the byte-enable field, register DWORD index, and 4 bytes of register value.
These likely set the power-off indicators for register 0x080.

**Total: 16 write-only I2C transactions (4 addresses x 4 ports), no reads.**

This is more efficient than `all_slot_power_off_reg` because:
1. It skips the read phase (writes pre-built values directly)
2. It does not need the slot mapping lookup table
3. It covers all ports on all switches without a bitmask check

---

## 7. PEX8696 Register Map

### 7.1 Registers Accessed by Hot-Plug Functions

All registers are in the PEX8696 per-port configuration space, addressed via the
PLX 4-byte I2C command format: `[cmd] [stn/port] [enables|reg_hi] [reg_lo]`.

| Byte Addr | DWORD Idx | I2C byte[3] | Name                      | Access   | Functions                    |
|-----------|-----------|-------------|---------------------------|----------|------------------------------|
| 0x07C     | 0x1F      | 0x1F        | Write-Protect Control     | R/W      | pex8696_un_protect_reg       |
| 0x080     | 0x20      | 0x20        | Slot Control / Status     | R/W      | pex8696_slot_power_on_reg, pex8696_slot_power_ctrl, all_slot_power_off_reg, pex8696_all_slot_off |
| 0x228     | 0x8A      | 0x8A        | Link / MRL Control        | R/W      | pex8696_slot_power_on_reg, pex8696_slot_power_ctrl |
| 0x234     | 0x8D      | 0x8D        | Hot-Plug Power Control    | R/W      | pex8696_slot_power_on_reg, pex8696_slot_power_ctrl |

### 7.2 Register Bit-Field Details

#### Register 0x07C -- Write-Protect Control

```
Bit  31                               16  15                                 0
     +----+----+----+----+----+----+----+----+----+----+----+----+----+----+----+----+
     |    |    |    |    |    |    |    |    |    |    |    |    |    |    |    |    |
     +----+----+----+----+----+----+----+----+----+----+----+----+----+----+----+----+
                          ^
                         bit 18: Write Protect (1=protected, 0=unprotected)
```

- **Bit 18** (byte 2, bit 2): Register write protection flag
  - `1` = Port registers are write-protected (default after reset)
  - `0` = Port registers are writable
  - Must be cleared before modifying Slot Control or Hot-Plug registers

#### Register 0x080 -- Slot Control / Status

This register corresponds to the PCIe Slot Control register. In the PCIe Base
Specification, Slot Control is at PCIe Capability + 0x18. For PLX switches with
PCIe Capability at offset 0x68, this places Slot Control at 0x080.

```
Bit  31                               16  15     10  9   8  7              0
     +----+----+----+----+----+----+----+----+----+----+----+----+----+----+
     |    |    |    |    |    |    |    |    | AI | PI Ctrl |              |
     +----+----+----+----+----+----+----+----+----+----+----+----+----+----+

     byte[5] = bits [15:8] of the register:
       bits [9:8]  (byte[5] bits [1:0]) = Power Indicator Control
       bit  [10]   (byte[5] bit  [2])   = Attention Indicator Control

     In the I2C data layout:
       Wire: [cmd][stn/port][enables][reg_lo][val_byte0][val_byte1][val_byte2][val_byte3]
       PEX8696_Command[4] = register bits [7:0]
       PEX8696_Command[5] = register bits [15:8]  <-- modified by firmware
       PEX8696_Command[6] = register bits [23:16]
       PEX8696_Command[7] = register bits [31:24]
```

**Power Indicator Control (bits [9:8]):**

| Value | Meaning | Firmware Usage                            |
|-------|---------|-------------------------------------------|
| 00b   | Reserved | Not used                                |
| 01b   | ON      | Power-on: `(byte[5] & 0xFC) | 0x01`     |
| 10b   | Blink   | Not used                                 |
| 11b   | OFF     | Power-off: `byte[5] | 0x03`              |

**Attention Indicator Control (bit [10]):**

| Value | Meaning | Firmware Usage                            |
|-------|---------|-------------------------------------------|
| 0     | OFF     | Power-on: `byte[5] & 0xFB`               |
| 1     | ON      | Power-off: `byte[5] | 0x04`              |

**Note:** The PCIe specification defines Attention Indicator Control as a 2-bit field
(bits [7:6]) in the standard layout. The firmware treating bit 10 as a single-bit
attention control suggests the PLX PEX8696 may use a slightly different bit mapping
in its port configuration space compared to the standard PCIe layout, or the register
at 0x080 combines Slot Control and Slot Status fields differently.

#### Register 0x234 -- Hot-Plug Power Control (PLX Proprietary)

```
Bit  31                               16  15                 8  7          0
     +----+----+----+----+----+----+----+----+----+----+----+----+----+----+
     |    |    |    |    |    |    |    |    |    |    |    |    |    | PCC|
     +----+----+----+----+----+----+----+----+----+----+----+----+----+----+

     byte[4] = bits [7:0]:
       bit 0 (byte[4] bit 0) = Power Controller Control (PCC)
```

**Power Controller Control (bit 0):**

| Value | Meaning                | Firmware Usage                          |
|-------|------------------------|-----------------------------------------|
| 0     | Idle                   | Normal state / de-assert after pulse    |
| 1     | Activate               | Assert to trigger power-on              |

The firmware uses this as a **pulsed control**:
1. Read current value
2. Set bit 0 (assert PCC)
3. Write back
4. Sleep 10 ticks (~100ms)
5. Clear bit 0 (de-assert PCC)
6. Write back

This triggers the PLX switch's internal power controller to sequence the slot
power rails via the hardware hot-plug controller. The 100ms delay allows the
power controller to complete its sequence.

#### Register 0x228 -- Link / MRL Control (PLX Proprietary)

```
Bit  31             24  23     21    16  15                                 0
     +----+----+----+----+----+----+----+----+----+----+----+----+----+----+
     |    |    |    |    | MRL|    |    |    |    |    |    |    |    |    |
     +----+----+----+----+----+----+----+----+----+----+----+----+----+----+

     byte[6] = bits [23:16]:
       bit 21 (byte[6] bit 5) = MRL Sensor / Hot-Plug LED enable
```

**MRL/LED Enable (bit 21):**

| Value | Meaning                                   | Firmware Usage              |
|-------|-------------------------------------------|-----------------------------|
| 0     | MRL sensor not present / LED disabled     | Default                     |
| 1     | MRL sensor present / LED enabled          | Set during power-on         |

This bit is only ever SET (never cleared in any analysed function), suggesting
it enables a hardware feature that persists until the next switch reset.

---

## 8. Complete I2C Sequences

### 8.1 Single Slot Power-On Sequence

**Prerequisite:** Register unprotect must have been performed first.

The complete sequence for powering on slot N (0-indexed):

```
Step 0: Resolve slot to I2C parameters
  get_PEX8696_addr_port(N) -> i2c_addr, station_port_byte

Step 1: READ register 0x07C (Write-Protect) -- if not already unprotected
  I2C Write: [04] [stn/port] [3C] [1F]
  I2C Read:  [v0] [v1] [v2] [v3]

Step 2: WRITE register 0x07C -- clear write-protect bit
  I2C Write: [03] [stn/port] [3C] [1F] [v0] [v1] [v2 & 0xFB] [v3]

Step 3: READ register 0x080 (Slot Control/Status)
  I2C Write: [04] [stn/port] [3C] [20]
  I2C Read:  [v0] [v1] [v2] [v3]

Step 4: WRITE register 0x080 -- power indicator ON, attention OFF
  I2C Write: [03] [stn/port] [3C] [20] [v0] [(v1 & 0xFC)|0x01 & 0xFB] [v2] [v3]

Step 5: READ register 0x234 (Hot-Plug Power Control)
  I2C Write: [04] [stn/port] [3C] [8D]
  I2C Read:  [v0] [v1] [v2] [v3]

Step 6: WRITE register 0x234 -- assert Power Controller Control
  I2C Write: [03] [stn/port] [3C] [8D] [v0|0x01] [v1] [v2] [v3]

Step 7: SLEEP 100ms

Step 8: WRITE register 0x234 -- de-assert Power Controller Control
  I2C Write: [03] [stn/port] [3C] [8D] [v0 & 0xFE] [v1] [v2] [v3]

Step 9: READ register 0x228 (Link/MRL Control)
  I2C Write: [04] [stn/port] [3C] [8A]
  I2C Read:  [v0] [v1] [v2] [v3]

Step 10: WRITE register 0x228 -- enable MRL/LED
  I2C Write: [03] [stn/port] [3C] [8A] [v0] [v1] [v2|0x20] [v3]
```

**Total: 10 I2C transactions per slot (5 reads + 5 writes), plus 100ms delay.**

### 8.2 Single Slot Power-Off Sequence

```
Step 0: Resolve slot to I2C parameters

Step 1: READ register 0x080 (Slot Control/Status)
  I2C Write: [04] [stn/port] [3C] [20]
  I2C Read:  [v0] [v1] [v2] [v3]

Step 2: WRITE register 0x080 -- power indicator OFF, attention ON
  I2C Write: [03] [stn/port] [3C] [20] [v0] [v1|0x07] [v2] [v3]
```

**Total: 2 I2C transactions per slot (1 read + 1 write).**

Note: The value `v1|0x07` is the result of `v1 | 0x03 | 0x04` which sets
bits [10:8] = 111b (Power Indicator=OFF, Attention=ON).

### 8.3 All-Slot Power-Off Sequence

**Method 1 (all_slot_power_off_reg):** Read-modify-write for each of 16 slots:
```
For each slot 0-15:
  READ  reg 0x080: [04] [stn/port] [3C] [20]
  WRITE reg 0x080: [03] [stn/port] [3C] [20] [v0] [v1|0x07] [v2] [v3]
```
Total: 32 transactions.

**Method 2 (pex8696_all_slot_off):** Write pre-built values to all ports:
```
For each I2C addr in {0x30, 0x32, 0x34, 0x36}:
  For each station/port in {port0, port1, port2, port3}:
    WRITE: [03] [stn/port] [enables] [reg] [prebuilt value bytes]
```
Total: 16 write-only transactions (faster, no reads needed).

### 8.4 Boot Power-On Sequence (All Slots)

The firmware powers on all 16 slots in 4 groups of 4, with each group activating
one slot per PEX8696 switch to distribute inrush current:

```
Phase 0: PSU Power Good check
  Start_GPU_Power_Sequence -> PSU_PGOOD()
  RawIRQDisable() -- disable hot-plug interrupt

Phase 1: Group 1 -- Slots 4, 8, 12, 16 (one per switch)
  gpu_un_protect(0xFF)
  pex8696_un_protect(bitmask)        -> unprotect via I2C reg 0x07C
  filter_on_gpu(bitmask)             -> filter by present GPUs
  pex8696_slot_power_on(bitmask)     -> power on via I2C regs 0x080/0x234/0x228
  gpu_power_attention_pulse(bitmask) -> attention indicator pulse

Phase 2: Group 2 -- Slots 3, 7, 11, 15
  (same sequence as Phase 1)

Phase 3: Group 3 -- Slots 2, 6, 10, 14
  (same sequence as Phase 1)

Phase 4: Group 4 -- Slots 1, 5, 9, 13
  (same sequence as Phase 1)

Phase 5: Re-enable hot-plug interrupt
  RawIRQEnable()
```

Each phase processes 4 slots, generating up to:
- 4 x 2 = 8 I2C transactions for unprotect (4 read + 4 write)
- 4 x 8 = 32 I2C transactions for power-on (16 read + 16 write + 4 x 100ms delays)
- Total: ~40 I2C transactions per group, ~160 for all 16 slots

---

## 9. Cross-Reference with PCIe and PLX Specifications

### 9.1 PCIe Base Specification Mapping

The PEX8696 maps standard PCIe registers into its per-port configuration space.
Based on the PLX convention of placing the PCIe Capability at offset 0x68:

| PLX Port Offset | PCIe Cap Offset | PCIe Register             |
|-----------------|-----------------|---------------------------|
| 0x068           | +0x00           | PCIe Capability Header    |
| 0x078           | +0x10           | Link Capabilities         |
| 0x07C           | +0x14           | Link Control / Status     |
| 0x080           | +0x18           | Slot Capabilities         |
| 0x084           | +0x1C           | Slot Control / Status     |

**Important note:** The firmware accesses register byte address 0x080, which in
the standard PCIe layout would be Slot Capabilities (read-only). However:

1. PLX switches may combine Slot Capabilities and Slot Control into a single
   32-bit register at this address, or
2. The PCIe Capability offset may not be exactly 0x68, or
3. Register 0x080 may be a PLX-proprietary shadow/alias register

The bit operations (Power Indicator Control, Attention Indicator Control) are
consistent with PCIe Slot Control register fields, confirming that this register
provides Slot Control functionality regardless of the exact capability offset.

### 9.2 PLX Proprietary Registers

| PLX Port Offset | Identity        | Purpose                             |
|-----------------|-----------------|-------------------------------------|
| 0x07C           | Port Control    | Write-protection management         |
| 0x228           | VS1 Hot-Plug    | MRL sensor / hot-plug LED control   |
| 0x234           | VS1 Power Ctrl  | Hardware power controller trigger   |

Registers 0x228 and 0x234 are in the PLX Vendor-Specific (VS1) capability region
(typically starting around offset 0x200 in PLX switches). These registers control
PLX-specific hardware-assisted hot-plug features that go beyond the standard
PCIe hot-plug specification.

### 9.3 Comparison with plxtools

The [plxtools](https://github.com/mithro/plxtools) project uses the simpler 2-byte
I2C address protocol for smaller PLX switches. To access the PEX8696 registers
documented here, plxtools would need to be extended to support the 4-byte protocol:

| plxtools approach             | Dell firmware approach                |
|-------------------------------|---------------------------------------|
| 2-byte register address       | 4-byte command (cmd, stn/port, en, reg) |
| Single address space           | Per-port address space via station/port |
| Implicit 32-bit access        | Explicit byte enables in command      |
| No port selection in I2C       | Port encoded in I2C command bytes     |

---

## 10. Summary of Key Findings

1. **Three control mechanisms:** The firmware uses I2C register writes for PCIe
   slot control indicators and power controller triggering, GPIO system commands
   for hot-plug attention signalling, and message queues for asynchronous dispatch.

2. **Four PEX8696 registers** are accessed for hot-plug/power control:
   - `0x07C`: Write-protect (must clear bit 18 before other writes)
   - `0x080`: Slot Control/Status (power/attention indicators)
   - `0x228`: Link/MRL Control (MRL sensor / LED enable, bit 21)
   - `0x234`: Hot-Plug Power Control (power controller pulse, bit 0)

3. **Power-on requires a pulse:** The Power Controller Control bit at register
   0x234, bit 0 must be asserted for ~100ms then de-asserted to trigger the
   PLX hardware power controller.

4. **Power-off is indicator-only:** The firmware only changes indicator bits
   in register 0x080 (power=OFF, attention=ON). No power controller pulse
   is sent. Actual power removal likely happens through separate GPU power
   supply control.

5. **Two power-off strategies exist:**
   - Per-slot read-modify-write (32 I2C transactions for 16 slots)
   - Bulk pre-built write to all ports (16 write-only transactions)

6. **Boot sequencing staggers power-on** across 4 groups, activating one slot
   per PEX8696 switch per group to manage inrush current. Total boot power-on
   involves approximately 160 I2C transactions across 4 switches.

7. **Hot-plug GPIO is separate from I2C:** The `pex8696_hp_on`/`pex8696_hp_off`
   functions use `system()` calls to toggle AST2050 GPIO pins, not I2C register
   writes. This provides a separate physical signal path for hot-plug events.

8. **IRQ management:** The hot-plug interrupt (index 0x800C, sub-index 0x18) is
   disabled during power sequences and re-enabled afterward, preventing spurious
   hot-plug events during controlled power transitions.

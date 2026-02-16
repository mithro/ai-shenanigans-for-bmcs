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

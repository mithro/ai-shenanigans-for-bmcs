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

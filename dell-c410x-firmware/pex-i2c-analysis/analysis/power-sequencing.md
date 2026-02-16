# GPU Power Sequencing Analysis - Dell C410X BMC Firmware

Analysis of the GPU power-on/power-off sequencing functions in the Dell C410X
BMC `fullfw` binary. This document traces how the BMC orchestrates the staggered
power-on of 16 GPU slots across 4 PEX8696 PCIe switches, documenting the complete
I2C transaction timeline.

- **Binary:** `fullfw` (ARM 32-bit little-endian ELF, Avocent MergePoint firmware)
- **Decompiler:** Ghidra 11.3.1
- **Prerequisites:** [I2C Transport Layer](i2c-transport.md), [PEX8696 Hot-Plug](pex8696-hotplug.md)

---

## 1. Start_GPU_Power_Sequence -- Top-Level Orchestrator

**Address:** `0x00033ae8` (184 bytes)

```c
void Start_GPU_Power_Sequence(undefined param_1, undefined4 param_2) {
    local_1a = 0;
    local_18 = param_2;
    local_11 = param_1;
    printf(DAT_00033ba0);                        // "Starting GPU power sequence..."

    RawIOIdxTblGetIdx(0x800c, 0x18, &local_1a);  // Look up hot-plug IRQ index
    RawIRQDisable(local_1a);                      // DISABLE hot-plug interrupt
    RawIRQClear(local_1a);                        // Clear any pending IRQ

    iVar1 = PSU_PGOOD();                          // Check PSU Power Good signal
    if (iVar1 == 1) {
        *DAT_00033ba4 = 1;                        // Set flag to trigger power-on
    } else {
        RawIRQEnable(local_1a);                   // PSU not ready, re-enable IRQ
    }
    return;
}
```

### 1.1 Orchestration Flow

`Start_GPU_Power_Sequence` does **not** directly call the per-phase power-on
functions. Instead it:

1. **Disables the hot-plug interrupt** (IRQ 0x800C, sub-index 0x18) to prevent
   spurious hot-plug events during the controlled power-on process.
2. **Clears any pending hot-plug IRQ** that may have accumulated.
3. **Checks PSU Power Good** via `PSU_PGOOD()` -- the PSU must be reporting
   stable power before any GPU power-on proceeds.
4. **Sets a flag** (`*DAT_00033ba4 = 1`) that triggers the actual power-on
   sequence in a background task.
5. If PSU is not good, **re-enables the interrupt** and returns without starting
   the sequence.

### 1.2 Indirect Phase Execution

The actual power-on phases are called indirectly by whatever background task
monitors the flag at `DAT_00033ba4`. Based on the function call hierarchy
documented in [pex8696-hotplug.md](pex8696-hotplug.md), the phases execute
in **reverse numerical order**:

| Execution Order | Function Called           | Slots Powered (1-based) | gpu_un_protect Bitmask |
|-----------------|--------------------------|-------------------------|------------------------|
| 1st             | `gpu_power_on_4_8_12_16` | 4, 8, 12, 16           | 0xFF                   |
| 2nd             | `gpu_power_on_3_7_11_15` | 3, 7, 11, 15           | 0x77                   |
| 3rd             | `gpu_power_on_2_6_10_14` | 2, 6, 10, 14           | 0x33                   |
| 4th             | `gpu_power_on_1_5_9_13`  | 1, 5, 9, 13            | 0x11                   |

The reverse ordering (4,8,12,16 first; 1,5,9,13 last) likely reflects physical
slot arrangement or power rail grouping on the C410X chassis.

### 1.3 Prerequisites and Status Checks

| Check                    | When              | Action if Failed            |
|--------------------------|-------------------|-----------------------------|
| PSU Power Good           | Before any phase  | Re-enable IRQ, abort        |
| Hot-plug IRQ disabled    | Before any phase  | Prevents spurious events    |
| GPU presence (per-phase) | Within each phase | `filter_on_gpu()` skips absent slots |

The firmware does **not** check individual slot presence before starting the
sequence. Instead, each phase function calls `filter_on_gpu(bitmask, &result)`
which masks out slots that do not have a GPU physically present. Only slots
with detected GPUs receive power-on I2C commands.

---

## 2. Per-Phase Power-On Functions

All four phase functions share identical structure, differing only in:
1. The 2-byte slot bitmask loaded from ROM (selects which 4 slots to power)
2. The `gpu_un_protect()` parameter byte
3. The debug printf string

### 2.1 Common Structure

```c
void gpu_power_on_X_Y_Z_W(void) {
    memcpy(auStack_14, DAT_bitmask_ptr, 2);  // Load 2-byte slot bitmask from ROM
    local_18 = 0;
    local_17 = 0;
    printf(DAT_string_ptr);                   // Debug log

    gpu_un_protect(bitmask_byte);              // GPU-side write protection removal
    pex8696_un_protect(auStack_14);            // PEX switch register unprotect
    filter_on_gpu(auStack_14, &local_18);      // Filter by present GPUs
    pex8696_slot_power_on(&local_18);          // Slot power-on via I2C
    gpu_power_attention_pulse(&local_18);      // Attention indicator pulse
    return;
}
```

### 2.2 Function Addresses and Parameters

| Phase | Function                  | Address      | Bitmask Source | gpu_un_protect |
|-------|---------------------------|-------------|----------------|----------------|
| 1     | `gpu_power_on_4_8_12_16`  | `0x00030300` | `DAT_00030388` | `0xFF`         |
| 2     | `gpu_power_on_3_7_11_15`  | `0x00030390` | `DAT_00030418` | `0x77`         |
| 3     | `gpu_power_on_2_6_10_14`  | `0x00030420` | `DAT_000304a8` | `0x33`         |
| 4     | `gpu_power_on_1_5_9_13`   | `0x000304b0` | `DAT_00030538` | `0x11`         |

### 2.3 gpu_un_protect Bitmask Analysis

The `gpu_un_protect()` parameter is a single byte that appears to be a cumulative
bitmask controlling GPU-side write protection. This is a **separate** mechanism
from the PEX8696 register write-protection cleared by `pex8696_un_protect()`.

| Phase | Bitmask | Binary     | Interpretation                              |
|-------|---------|------------|---------------------------------------------|
| 1     | 0xFF    | 1111 1111  | Unprotect all GPU-side registers (8 groups)  |
| 2     | 0x77    | 0111 0111  | Unprotect 6 of 8 groups                      |
| 3     | 0x33    | 0011 0011  | Unprotect 4 of 8 groups                      |
| 4     | 0x11    | 0001 0001  | Unprotect 2 of 8 groups                      |

The decreasing pattern (0xFF -> 0x77 -> 0x33 -> 0x11) is consistent with the
phases executing in order 1-4, with phase 1 (slots 4,8,12,16) needing to
unprotect the most groups because it runs first when all slots are still
protected, and phase 4 (slots 1,5,9,13) only needing to unprotect the
remaining slots.

### 2.4 Per-Phase Step Sequence

Each phase function executes 5 sequential operations:

| Step | Operation                      | Mechanism     | Description                                    |
|------|--------------------------------|---------------|------------------------------------------------|
| 1    | `gpu_un_protect(mask)`         | Unknown       | GPU-side write protection removal               |
| 2    | `pex8696_un_protect(bitmask)`  | I2C via queue | Read-modify-write PEX reg 0x07C for each slot  |
| 3    | `filter_on_gpu(bitmask, &out)` | Local check   | Filter bitmask by physically present GPUs       |
| 4    | `pex8696_slot_power_on(&out)`  | I2C via queue | Power-on sequence for each slot (3 registers)   |
| 5    | `gpu_power_attention_pulse()`  | I2C via queue | Attention indicator pulse                        |

Steps 2, 4, and 5 are dispatched via `_lx_QueueSend` to a background I2C
worker task. The queue serialises I2C transactions, so while the dispatch is
asynchronous, the actual I2C operations execute sequentially.

---

## 3. Phase 1: Slots 4, 8, 12, 16 (gpu_power_on_4_8_12_16)

### 3.1 Slot-to-Switch Mapping

Using the lookup tables from [i2c-transport.md](i2c-transport.md):

| Slot (1-based) | Slot Index | I2C Addr (8-bit) | PEX8696 Switch | Port Byte | Global Port |
|----------------|------------|-------------------|----------------|-----------|-------------|
| 4              | 3          | 0x34              | #1 (0x1A)      | 0x0A      | 20          |
| 8              | 7          | 0x36              | #3 (0x1B)      | 0x08      | 16          |
| 12             | 11         | 0x32              | #2 (0x19)      | 0x08      | 16          |
| 16             | 15         | 0x30              | #0 (0x18)      | 0x08      | 16          |

**Each slot is on a different PEX8696 switch** (addresses 0x34, 0x36, 0x32, 0x30),
which distributes the inrush current across all 4 switches.

### 3.2 Processing Order Within Phase

The `pex8696_slot_power_on_reg` function iterates the 16-bit slot bitmask
in a fixed order:

```c
for (byte_idx = 0; byte_idx < 2; byte_idx++) {     // byte 0, then byte 1
    for (bit_idx = 0; bit_idx < 8; bit_idx++) {     // bit 0 through bit 7
        if (bitmask[byte_idx] >> bit_idx & 1) {
            // Process slot (byte_idx * 8 + bit_idx)
        }
    }
}
```

This means slots within a phase are processed **sequentially** in slot index
order (lowest first). For Phase 1 (slots 4,8,12,16 = indices 3,7,11,15):

| Processing Order | Slot Index | Physical Slot | PEX8696 Switch | I2C Addr |
|------------------|------------|---------------|----------------|----------|
| 1st              | 3          | Slot 4        | #1             | 0x34     |
| 2nd              | 7          | Slot 8        | #3             | 0x36     |
| 3rd              | 11         | Slot 12       | #2             | 0x32     |
| 4th              | 15         | Slot 16       | #0             | 0x30     |

### 3.3 I2C Transactions Per Slot (Within Power-On)

For each slot, `pex8696_slot_power_on_reg` performs:

| Txn # | Type  | Register | Byte Addr | Description                          |
|-------|-------|----------|-----------|--------------------------------------|
| 1     | READ  | 0x080    | DWORD 0x20 | Read Slot Control/Status            |
| 2     | WRITE | 0x080    | DWORD 0x20 | Set Power Indicator ON, Attention OFF |
| 3     | READ  | 0x234    | DWORD 0x8D | Read Hot-Plug Power Control         |
| 4     | WRITE | 0x234    | DWORD 0x8D | Assert Power Controller Control     |
| --    | SLEEP | --       | --        | 10 ticks (~100ms)                    |
| 5     | WRITE | 0x234    | DWORD 0x8D | De-assert Power Controller Control  |
| 6     | READ  | 0x228    | DWORD 0x8A | Read Link/MRL Control               |
| 7     | WRITE | 0x228    | DWORD 0x8A | Set MRL/LED enable bit              |

**Total per slot: 7 I2C transactions (3 reads + 4 writes) + 100ms delay**

### 3.4 I2C Transactions for Unprotect Step

Additionally, `pex8696_un_protect_reg` performs 2 transactions per slot:

| Txn # | Type  | Register | Description                             |
|-------|-------|----------|-----------------------------------------|
| 1     | READ  | 0x07C    | Read Write-Protect register             |
| 2     | WRITE | 0x07C    | Clear write-protect bit (bit 18)        |

### 3.5 Phase 1 Transaction Summary

For 4 slots in Phase 1:

| Step                       | Txns Per Slot | Slots | Total Txns | Delays      |
|----------------------------|--------------|-------|------------|-------------|
| `pex8696_un_protect`       | 2            | 4     | 8          | None        |
| `pex8696_slot_power_on`    | 7            | 4     | 28         | 4 x 100ms   |
| `gpu_power_attention_pulse`| TBD          | 4     | TBD        | TBD         |
| **Subtotal (I2C only)**    |              |       | **36+**    | **400ms+**  |

The `pex8696_slot_power_on` dispatcher also sends 2 additional queue messages
(to I2C bus 0/mux 8 and bus 4/mux 5) for each phase, which may add further
transactions for GPU power rail control on other I2C buses.

---

## 4. Phase 2: Slots 3, 7, 11, 15 (gpu_power_on_3_7_11_15)

### 4.1 Slot-to-Switch Mapping

| Slot (1-based) | Slot Index | I2C Addr (8-bit) | PEX8696 Switch | Port Byte | Global Port |
|----------------|------------|-------------------|----------------|-----------|-------------|
| 3              | 2          | 0x34              | #1 (0x1A)      | 0x04      | 8           |
| 7              | 6          | 0x36              | #3 (0x1B)      | 0x02      | 4           |
| 11             | 10         | 0x32              | #2 (0x19)      | 0x02      | 4           |
| 15             | 14         | 0x30              | #0 (0x18)      | 0x02      | 4           |

Again, **one slot per switch** (0x34, 0x36, 0x32, 0x30).

### 4.2 Processing Order Within Phase

| Processing Order | Slot Index | Physical Slot | PEX8696 Switch | I2C Addr |
|------------------|------------|---------------|----------------|----------|
| 1st              | 2          | Slot 3        | #1             | 0x34     |
| 2nd              | 6          | Slot 7        | #3             | 0x36     |
| 3rd              | 10         | Slot 11       | #2             | 0x32     |
| 4th              | 14         | Slot 15       | #0             | 0x30     |

### 4.3 Phase 2 Transaction Summary

Identical structure to Phase 1:

| Step                       | Txns Per Slot | Slots | Total Txns | Delays      |
|----------------------------|--------------|-------|------------|-------------|
| `pex8696_un_protect`       | 2            | 4     | 8          | None        |
| `pex8696_slot_power_on`    | 7            | 4     | 28         | 4 x 100ms   |
| `gpu_power_attention_pulse`| TBD          | 4     | TBD        | TBD         |
| **Subtotal (I2C only)**    |              |       | **36+**    | **400ms+**  |

---

## 5. Phase 3: Slots 2, 6, 10, 14 (gpu_power_on_2_6_10_14)

### 5.1 Slot-to-Switch Mapping

| Slot (1-based) | Slot Index | I2C Addr (8-bit) | PEX8696 Switch | Port Byte | Global Port |
|----------------|------------|-------------------|----------------|-----------|-------------|
| 2              | 1          | 0x30              | #0 (0x18)      | 0x0A      | 20          |
| 6              | 5          | 0x32              | #2 (0x19)      | 0x0A      | 20          |
| 10             | 9          | 0x36              | #3 (0x1B)      | 0x0A      | 20          |
| 14             | 13         | 0x34              | #1 (0x1A)      | 0x08      | 16          |

Again, **one slot per switch** (0x30, 0x32, 0x36, 0x34).

### 5.2 Processing Order Within Phase

| Processing Order | Slot Index | Physical Slot | PEX8696 Switch | I2C Addr |
|------------------|------------|---------------|----------------|----------|
| 1st              | 1          | Slot 2        | #0             | 0x30     |
| 2nd              | 5          | Slot 6        | #2             | 0x32     |
| 3rd              | 9          | Slot 10       | #3             | 0x36     |
| 4th              | 13         | Slot 14       | #1             | 0x34     |

### 5.3 Phase 3 Transaction Summary

| Step                       | Txns Per Slot | Slots | Total Txns | Delays      |
|----------------------------|--------------|-------|------------|-------------|
| `pex8696_un_protect`       | 2            | 4     | 8          | None        |
| `pex8696_slot_power_on`    | 7            | 4     | 28         | 4 x 100ms   |
| `gpu_power_attention_pulse`| TBD          | 4     | TBD        | TBD         |
| **Subtotal (I2C only)**    |              |       | **36+**    | **400ms+**  |

---

## 6. Phase 4: Slots 1, 5, 9, 13 (gpu_power_on_1_5_9_13)

### 6.1 Slot-to-Switch Mapping

| Slot (1-based) | Slot Index | I2C Addr (8-bit) | PEX8696 Switch | Port Byte | Global Port |
|----------------|------------|-------------------|----------------|-----------|-------------|
| 1              | 0          | 0x30              | #0 (0x18)      | 0x04      | 8           |
| 5              | 4          | 0x32              | #2 (0x19)      | 0x04      | 8           |
| 9              | 8          | 0x36              | #3 (0x1B)      | 0x04      | 8           |
| 13             | 12         | 0x34              | #1 (0x1A)      | 0x02      | 4           |

Again, **one slot per switch** (0x30, 0x32, 0x36, 0x34).

### 6.2 Processing Order Within Phase

| Processing Order | Slot Index | Physical Slot | PEX8696 Switch | I2C Addr |
|------------------|------------|---------------|----------------|----------|
| 1st              | 0          | Slot 1        | #0             | 0x30     |
| 2nd              | 4          | Slot 5        | #2             | 0x32     |
| 3rd              | 8          | Slot 9        | #3             | 0x36     |
| 4th              | 12         | Slot 13       | #1             | 0x34     |

### 6.3 Phase 4 Transaction Summary

| Step                       | Txns Per Slot | Slots | Total Txns | Delays      |
|----------------------------|--------------|-------|------------|-------------|
| `pex8696_un_protect`       | 2            | 4     | 8          | None        |
| `pex8696_slot_power_on`    | 7            | 4     | 28         | 4 x 100ms   |
| `gpu_power_attention_pulse`| TBD          | 4     | TBD        | TBD         |
| **Subtotal (I2C only)**    |              |       | **36+**    | **400ms+**  |

---

## 7. Complete Power-On Timeline

### 7.1 Full Sequence of Events

```
T=0      Start_GPU_Power_Sequence()
           |-- Disable hot-plug IRQ (0x800C/0x18)
           |-- Clear pending hot-plug IRQ
           |-- Check PSU_PGOOD() -> must return 1
           |-- Set flag *DAT_00033ba4 = 1

=== Background task picks up flag ===

         Phase 1: gpu_power_on_4_8_12_16()
           |-- gpu_un_protect(0xFF)
           |-- pex8696_un_protect: 4 slots x 2 I2C txns = 8 txns
           |-- filter_on_gpu: filter by present GPUs
           |-- pex8696_slot_power_on:
           |     Slot 4  (idx 3,  0x34 port 0x0A): 7 I2C txns + 100ms sleep
           |     Slot 8  (idx 7,  0x36 port 0x08): 7 I2C txns + 100ms sleep
           |     Slot 12 (idx 11, 0x32 port 0x08): 7 I2C txns + 100ms sleep
           |     Slot 16 (idx 15, 0x30 port 0x08): 7 I2C txns + 100ms sleep
           |-- gpu_power_attention_pulse

         Phase 2: gpu_power_on_3_7_11_15()
           |-- gpu_un_protect(0x77)
           |-- pex8696_un_protect: 4 slots x 2 I2C txns = 8 txns
           |-- filter_on_gpu
           |-- pex8696_slot_power_on:
           |     Slot 3  (idx 2,  0x34 port 0x04): 7 I2C txns + 100ms sleep
           |     Slot 7  (idx 6,  0x36 port 0x02): 7 I2C txns + 100ms sleep
           |     Slot 11 (idx 10, 0x32 port 0x02): 7 I2C txns + 100ms sleep
           |     Slot 15 (idx 14, 0x30 port 0x02): 7 I2C txns + 100ms sleep
           |-- gpu_power_attention_pulse

         Phase 3: gpu_power_on_2_6_10_14()
           |-- gpu_un_protect(0x33)
           |-- pex8696_un_protect: 4 slots x 2 I2C txns = 8 txns
           |-- filter_on_gpu
           |-- pex8696_slot_power_on:
           |     Slot 2  (idx 1,  0x30 port 0x0A): 7 I2C txns + 100ms sleep
           |     Slot 6  (idx 5,  0x32 port 0x0A): 7 I2C txns + 100ms sleep
           |     Slot 10 (idx 9,  0x36 port 0x0A): 7 I2C txns + 100ms sleep
           |     Slot 14 (idx 13, 0x34 port 0x08): 7 I2C txns + 100ms sleep
           |-- gpu_power_attention_pulse

         Phase 4: gpu_power_on_1_5_9_13()
           |-- gpu_un_protect(0x11)
           |-- pex8696_un_protect: 4 slots x 2 I2C txns = 8 txns
           |-- filter_on_gpu
           |-- pex8696_slot_power_on:
           |     Slot 1  (idx 0,  0x30 port 0x04): 7 I2C txns + 100ms sleep
           |     Slot 5  (idx 4,  0x32 port 0x04): 7 I2C txns + 100ms sleep
           |     Slot 9  (idx 8,  0x36 port 0x04): 7 I2C txns + 100ms sleep
           |     Slot 13 (idx 12, 0x34 port 0x02): 7 I2C txns + 100ms sleep
           |-- gpu_power_attention_pulse

=== Power-on complete, hot-plug IRQ re-enabled ===
```

### 7.2 I2C Transaction Count Summary

#### Per-Phase (PEX8696 Bus Only)

| Operation              | Txns/Slot | Slots | Total | Notes                      |
|------------------------|-----------|-------|-------|----------------------------|
| Unprotect (reg 0x07C)  | 2         | 4     | 8     | 4 read + 4 write           |
| Power-on (regs 0x080, 0x234, 0x228) | 7 | 4 | 28  | 12 read + 16 write, 4x100ms delays |
| **Phase subtotal**     |           |       | **36**| PEX8696 I2C bus 3 only     |

#### Additional Queue Messages Per Phase

Each `pex8696_slot_power_on()` dispatch also sends:
- 1 message to bus 0, mux channel 8 (`0x80F0`) -- likely GPU power regulator
- 1 message to bus 4, mux channel 5 (`0x5CF4`) -- likely auxiliary device

These generate additional I2C transactions on other buses that are not part
of the PEX8696 switch control. Their exact transaction count is not determined
from the decompiled PEX functions alone.

#### All 4 Phases Combined

| Metric                           | Count        |
|----------------------------------|-------------|
| Phases                           | 4            |
| Slots per phase                  | 4            |
| Total slots                      | 16           |
| PEX8696 I2C txns per phase      | 36           |
| **Total PEX8696 I2C transactions** | **144**    |
| 100ms delays per phase           | 4            |
| **Total 100ms delays**           | **16**       |
| Total I2C reads                  | 64 (16 unprotect + 48 power-on) |
| Total I2C writes                 | 80 (16 unprotect + 64 power-on) |

### 7.3 Estimated Total Time

The timing depends on:
1. **I2C transaction time:** Each PLX I2C transaction takes ~1-2ms on a standard
   100kHz bus (4-8 bytes per transaction).
2. **100ms sleep per slot:** 16 slots x 100ms = 1600ms of mandatory delays.
3. **Queue processing overhead:** The queue dispatcher adds some latency
   between operations.

**Conservative estimate:**

| Component                        | Time           |
|----------------------------------|----------------|
| 144 I2C transactions @ ~2ms each | ~288ms         |
| 16 x 100ms power controller pulse delays | ~1600ms |
| Queue dispatch overhead          | ~100ms         |
| Inter-phase gap (if any)         | Unknown        |
| **Estimated total**              | **~2.0 seconds** |

The actual time may be longer due to inter-phase delays (not visible in the
decompiled code -- they may be implicit in the queue processing model).

### 7.4 Switch Load Distribution

Each phase activates exactly one slot on each of the 4 PEX8696 switches:

| Phase | Switch #0 (0x30) | Switch #1 (0x34) | Switch #2 (0x32) | Switch #3 (0x36) |
|-------|------------------|------------------|------------------|------------------|
| 1     | Slot 16          | Slot 4           | Slot 12          | Slot 8           |
| 2     | Slot 15          | Slot 3           | Slot 11          | Slot 7           |
| 3     | Slot 2           | Slot 14          | Slot 6           | Slot 10          |
| 4     | Slot 1           | Slot 13          | Slot 5           | Slot 9           |

This ensures that at any point during the power-on sequence, the inrush
current is distributed evenly across all 4 PEX8696 switches and their
associated power domains.

---

## 8. Power-Off Sequences

The firmware provides **two** all-slot power-off mechanisms with different
characteristics.

### 8.1 all_slot_power_off (Queue Dispatcher)

**Address:** `0x0002f2fc` (272 bytes)

Sends 2 queue messages:
1. `0x430F3` -> `all_slot_power_off_reg()` (PEX8696 register power-off)
2. `0x80F0` -> secondary handler (GPU power on bus 0, mux 8)

**No third message** (unlike power-on which sends 3 messages).

### 8.2 all_slot_power_off_reg (I2C Implementation)

**Address:** `0x0002f188` (360 bytes)

Iterates over **all 16 slots unconditionally** (no bitmask filtering):

```c
for (byte_idx = 0; byte_idx < 2; byte_idx++) {
    for (bit_idx = 0; bit_idx < 8; bit_idx++) {
        // No bitmask check -- ALL slots processed
        slot_index = byte_idx * 8 + bit_idx;
        get_PEX8696_addr_port(slot_index, &i2c_addr, &port_byte);

        // READ register 0x080 (Slot Control/Status)
        read_pex8696_register(0xF3, i2c_addr, 4, buf);

        // SET power-off indicators
        buf[5] |= 0x03;    // Power Indicator = OFF (11b)
        buf[5] |= 0x04;    // Attention Indicator = ON (01b)

        // WRITE back
        write_pex8696_register(0xF3, i2c_addr, 3, buf);
    }
}
```

**Key difference from power-on: NO staggering on power-off.** All 16 slots
are powered off sequentially in slot index order (0 through 15) without
any grouping or delays between slots.

#### Per-Slot Power-Off I2C Transactions

| Txn # | Type  | Register | Description                                  |
|-------|-------|----------|----------------------------------------------|
| 1     | READ  | 0x080    | Read Slot Control/Status                     |
| 2     | WRITE | 0x080    | Set Power Indicator=OFF, Attention Indicator=ON |

**Total: 2 I2C transactions per slot, 32 transactions for all 16 slots.**

The power-off path does NOT:
- Pulse the Power Controller Control register (0x234)
- Modify the Link/MRL register (0x228)
- Unprotect any registers (0x07C)
- Perform any GPIO operations
- Include any delays between slots

### 8.3 pex8696_all_slot_power_off (Alternate Dispatcher)

**Address:** `0x0003836c` (192 bytes)

An alternative all-slot power-off that sends only **1** queue message with
parameter `0x330F3` (note: `0x33` vs `0x43` operation type) to
`pex8696_all_slot_off()`.

### 8.4 pex8696_all_slot_off (Bulk Write)

**Address:** `0x000375b8` (288 bytes)

A more efficient bulk power-off that iterates over I2C addresses directly:

```c
for (i2c_addr = 0x30; i2c_addr < 0x38; i2c_addr += 2) {   // 4 switches
    for (port = 0; port < 4; port++) {                       // 4 ports each
        // Write pre-built power-off data
        write_pex8696_register(0xF3, i2c_addr, cmd, buf);
    }
}
```

**Total: 16 write-only I2C transactions** (no reads needed, uses pre-built
register values from ROM).

This is faster than `all_slot_power_off_reg` because:
1. No read phase (writes pre-built values directly)
2. No slot mapping lookup needed
3. Iterates by hardware address rather than logical slot index

### 8.5 Power-Off Comparison

| Feature                | all_slot_power_off_reg | pex8696_all_slot_off |
|------------------------|------------------------|----------------------|
| Total I2C transactions | 32 (16 R + 16 W)      | 16 (write-only)      |
| Requires read first?   | Yes                    | No (pre-built data)  |
| Uses slot mapping?     | Yes (per-slot lookup)  | No (direct addressing) |
| Staggered?             | No                     | No                   |
| Iteration method       | Slot index 0-15        | I2C addr x port      |

---

## 9. Summary

### 9.1 Complete Power-On Phase Ordering and Delays

1. **Phase 1** (`gpu_power_on_4_8_12_16`): Slots 4, 8, 12, 16 -- one per switch
2. **Phase 2** (`gpu_power_on_3_7_11_15`): Slots 3, 7, 11, 15 -- one per switch
3. **Phase 3** (`gpu_power_on_2_6_10_14`): Slots 2, 6, 10, 14 -- one per switch
4. **Phase 4** (`gpu_power_on_1_5_9_13`): Slots 1, 5, 9, 13 -- one per switch

Each phase includes 4 x 100ms delays (one per slot, during power controller
pulse). No explicit inter-phase delays are visible in the decompiled code, but
queue serialisation provides implicit ordering.

### 9.2 Total I2C Transaction Count

| Sequence             | PEX8696 I2C Txns | Delays          |
|----------------------|-------------------|-----------------|
| Full 16-slot power-on | 144              | 16 x 100ms (1.6s) |
| All-slot power-off (method 1) | 32       | None            |
| All-slot power-off (method 2) | 16       | None            |

### 9.3 Power-Off Staggering

**Power-off is NOT staggered.** Both power-off methods process all 16 slots
in a single pass without any delay or grouping between slots. This is
reasonable because:
- Power-off has no inrush current concern
- Only indicator registers (0x080) are modified; no power controller pulse
- The actual power removal may be managed by hardware interlocks

### 9.4 Key Design Decisions

1. **Reverse phase ordering** (4,8,12,16 first) -- slots are powered in
   reverse numerical group order, likely reflecting physical chassis layout.

2. **One slot per switch per phase** -- ensures inrush current from power
   controller activation is distributed across all 4 PEX8696 switches.

3. **Sequential within each phase** -- slots within a phase are processed
   serially via the I2C bus, not in parallel. The I2C bus is a shared
   resource with per-bus semaphore protection.

4. **GPU presence filtering** -- `filter_on_gpu()` prevents sending I2C
   commands to empty slots, saving transaction time when fewer than 16
   GPUs are installed.

5. **Asymmetric power-on/power-off** -- power-on requires 9 I2C transactions
   per slot (2 unprotect + 7 power-on) with a 100ms delay; power-off
   requires only 2 transactions per slot with no delay.

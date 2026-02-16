# PEX Multi-Host Configuration Analysis

Analysis of the multi-host mode switching functions in the Dell C410X BMC
`fullfw` binary, documenting the I2C register sequences used to reconfigure
PCIe lane topology between different host-to-GPU fan-out modes.

- **Binary:** `fullfw` (ARM 32-bit little-endian ELF, Avocent MergePoint firmware)
- **Decompiler:** Ghidra 11.3.1
- **Prerequisite:** [I2C Transport Layer Analysis](i2c-transport.md), [PEX8696 Hot-Plug Analysis](pex8696-hotplug.md)

---

## 1. Overview

### 1.1 Multi-Host Modes

The Dell C410X supports three host-to-GPU fan-out modes:

| Mode | Description | Hosts | GPUs per Host | iPass Cable Usage |
|------|-------------|-------|---------------|-------------------|
| 2:1  | Each iPass cable serves 2 GPU slots | Up to 8 hosts | 2 GPUs | Most hosts, fewest GPUs per host |
| 4:1  | Each iPass cable serves 4 GPU slots | Up to 4 hosts | 4 GPUs | Default mode |
| 8:1  | Each iPass cable serves 8 GPU slots | Up to 2 hosts | 8 GPUs | Fewest hosts, most GPUs per host |

Mode switching is accomplished by reconfiguring the PLX PEX8696 (downstream/GPU)
and PEX8647 (upstream/host) switches via I2C register writes. The switches' lane
assignment and port configuration registers are modified to change how PCIe lanes
are allocated between host links and GPU links.

### 1.2 Switch Architecture

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
              | PEX8696 #2 (0x32)   |  4 slots per switch
              | PEX8696 #3 (0x36)   |
              +------+---+---+------+
                |  |  |  |  |  |  |
               GPU slots 1-16
```

All switches are on I2C bus 3 (`bus_mux = 0xF3`, no I2C mux).

### 1.3 Function Call Hierarchy

```
multi_host_mode_set(param_1)          [IPMI command handler]
  |
  +-- RawIOIdxTblGetIdx / RawDiscreteRead  [Read current mode sensor]
  |
  [orchestrator at 0x38A98]
    |
    +-- pex8696_all_slot_power_off()      [Power off all GPU slots first]
    |     +-- pex8696_all_slot_off()      [Write power-off to all ports]
    |
    +-- pex8696_multi_host_mode_cfg()     [Configure all 4 PEX8696 switches]
    |     +-- is_cfg_multi_host_8()       [Check if 8:1 mode requested]
    |     +-- pex8696_cfg_multi_host_4()  [Write 4:1/8:1 register data]
    |     +-- pex8696_cfg_multi_host_2()  [Write 2:1 register data]
    |
    +-- pex8647_multi_host_mode_cfg()     [Configure both PEX8647 switches]
    |     +-- is_cfg_multi_host_8()       [Check if 8:1 mode requested]
    |     +-- pex8647_cfg_multi_host_8()  [Write 8:1 register data]
    |     +-- pex8647_cfg_multi_host_2_4() [Write 2:1/4:1 register data]
    |
    +-- pex8696_multi_host_mode_reg_set() [Additional register setup]
    |     +-- raw_plx_i2c_write()         [Direct PLX register write]
    |
    +-- pex8696_cfg()                     [General port re-configuration]
```

---

## 2. IPMI Command Interface

### 2.1 multi_host_mode_set (at 0x00038230, 312 bytes)

This is the entry point triggered by an IPMI command. It maps the IPMI
sensor ID to a PEX8696 switch I2C address and reads the current mode.

```c
void multi_host_mode_set(ushort param_1) {
    byte local_16;  // I2C address
    byte local_15;  // Current mode value

    switch (param_1) {
        case 0x802D: local_16 = 0x30; break;  // PEX8696 #0
        case 0x802E: local_16 = 0x32; break;  // PEX8696 #2
        case 0x802F: local_16 = 0x34; break;  // PEX8696 #1
        default:     local_16 = 0x36; break;  // PEX8696 #3
    }

    RawIOIdxTblGetIdx(param_1, 0xF, &local_14);
    RawDiscreteRead(local_14, 0, 0, &local_15);
    printf("LMD : multi_host %02X %02X\n", local_16, local_15);
}
```

**IPMI Sensor-to-Switch Mapping:**

| IPMI Sensor ID | PEX8696 I2C Addr (8-bit) | PEX8696 Switch | 7-bit Addr |
|----------------|--------------------------|----------------|------------|
| 0x802D         | 0x30                     | #0             | 0x18       |
| 0x802E         | 0x32                     | #2             | 0x19       |
| 0x802F         | 0x34                     | #1             | 0x1A       |
| other          | 0x36                     | #3             | 0x1B       |

The mode value read via `RawDiscreteRead` determines whether each switch
pair operates in 2:1, 4:1, or 8:1 mode.

---

## 3. Mode Detection

### 3.1 is_cfg_multi_host_8 (at 0x000376E8, 128 bytes)

This function checks whether a given switch index should be configured
for 8:1 mode. It reads from a mode byte array at `0x0010B8CB`.

The function takes a switch index (0-3) and returns 1 if 8:1 mode is
requested for that switch, 0 otherwise.

**Mode Data Layout at 0x0010B8C7:**

```
Offset:  +0  +1  +2  +3  +4  +5  +6  +7
Data:    00  01  00  0C  00  11  00  00
         └── PEX8696 ──┘  └── PEX8647 ──┘
```

- Bytes 0-3: Mode values for PEX8696 switches 0-3
- Bytes 4-7: Mode values for PEX8647 switches

**Note:** These are runtime-writable values in the `.data` segment.
The values shown are defaults in the binary; actual mode is set by
IPMI commands from the Dell chassis management controller.

### 3.2 Mode Value Interpretation

From the logic in `pex8696_multi_host_mode_cfg`:

```c
if ((mode_array[switch_idx] == 0) || (is_cfg_multi_host_8(switch_idx) == 1)) {
    // Use cfg_multi_host_4 handler (4:1 / 8:1 register values)
    callback = pex8696_cfg_multi_host_4;
} else {
    // Use cfg_multi_host_2 handler (2:1 register values)
    callback = pex8696_cfg_multi_host_2;
}
```

| Mode Value | Interpretation | PEX8696 Handler | PEX8647 Handler |
|------------|----------------|-----------------|-----------------|
| 0          | Unconfigured / default (treated as 4:1 or 8:1) | cfg_multi_host_4 | cfg_multi_host_8 |
| 1          | 2:1 mode (or specific host count) | cfg_multi_host_2 | cfg_multi_host_2_4 |
| 2          | 8:1 mode detection threshold | cfg_multi_host_4 | cfg_multi_host_8 |
| Other      | Non-8:1 (2:1 or 4:1) | cfg_multi_host_2 | cfg_multi_host_2_4 |

**Important naming note:** The Ghidra-assigned function names may be misleading.
`pex8696_cfg_multi_host_4` is the handler called for **both** 4:1 and 8:1 modes
(and the unconfigured/default case). `pex8696_cfg_multi_host_2` is called for
non-8:1 modes (including 2:1).

---

## 4. PEX8696 Multi-Host Configuration

### 4.1 pex8696_multi_host_mode_cfg (at 0x00037768, 448 bytes)

This function iterates over all 4 PEX8696 switches and sends a queue
message to configure each one based on its mode value.

```c
void pex8696_multi_host_mode_cfg(void) {
    printf("...", mode_array[0], mode_array[1], mode_array[2], mode_array[3]);

    for (local_11 = 0; local_11 < 4; local_11++) {
        memset(shared_buffer, 0, 8);

        // Select handler based on mode
        if (mode_array[local_11] == 0 || is_cfg_multi_host_8(local_11) == 1) {
            callback = pex8696_cfg_multi_host_4;  // 0x36CD4
        } else {
            callback = pex8696_cfg_multi_host_2;  // 0x36BEC
        }

        // Set I2C address based on switch index
        switch (local_11) {
            case 0: bus_addr = 0x30F3; break;  // PEX8696 #0
            case 1: bus_addr = 0x34F3; break;  // PEX8696 #1
            case 2: bus_addr = 0x32F3; break;  // PEX8696 #2
            case 3: bus_addr = 0x36F3; break;  // PEX8696 #3
        }

        packed = CONCAT12(3, bus_addr);  // Add PLX write command
        _lx_QueueSend(queue, &message, 0);
    }
}
```

**Queue messages sent (4 total, one per PEX8696 switch):**

| Switch | I2C Addr (8-bit) | bus_mux | PLX cmd | Queue packed value |
|--------|------------------|---------|---------|-------------------|
| #0     | 0x30             | 0xF3    | 0x03    | 0x000330F3        |
| #1     | 0x34             | 0xF3    | 0x03    | 0x000334F3        |
| #2     | 0x32             | 0xF3    | 0x03    | 0x000332F3        |
| #3     | 0x36             | 0xF3    | 0x03    | 0x000336F3        |

### 4.2 pex8696_cfg_multi_host_4 (at 0x00036CD4, 220 bytes)

Called for 4:1 and 8:1 mode configuration. Writes 2 register entries
to station 0, port 0 (global port 0) on the target PEX8696 switch.
Port 0 is the upstream/configuration port.

```c
void pex8696_cfg_multi_host_4(bus_mux, i2c_addr, cmd, buffer_ptr) {
    byte data[12];  // from ROM at 0xF9040
    memcpy(data, ROM_DATA, 12);

    *counter = 0;   // station/port byte = 0 (station 0, port 0)

    for (i = 0; i < 2; i++) {
        memcpy(command_buffer, data + i*6, 6);
        write_pex8696_register(bus_mux, i2c_addr, cmd, buffer_ptr);
    }
}
```

**Register writes for 4:1/8:1 mode (ROM data at 0xF9040):**

| Write | Register | Byte Addr | Value | Description |
|-------|----------|-----------|-------|-------------|
| 1 | DWORD 0x0E1 | 0x384 | 0x00100000 | Port/lane configuration (upper) |
| 2 | DWORD 0x0E0 | 0x380 | 0x11011100 | Port/lane configuration (lower) |

**Wire-level I2C transactions:**

```
Write 1: [03] [00] [3C] [E1] [00] [00] [10] [00]
         cmd  stn   en  reg   val0 val1 val2 val3
         Write stn0/port0  reg 0x384  value 0x00100000

Write 2: [03] [00] [3C] [E0] [00] [11] [01] [11]
         Write stn0/port0  reg 0x380  value 0x11011100
```

### 4.3 pex8696_cfg_multi_host_2 (at 0x00036BEC, 220 bytes)

Called for 2:1 mode configuration. Same structure as cfg_multi_host_4
but with different register values.

**Register writes for 2:1 mode (ROM data at 0xF9034):**

| Write | Register | Byte Addr | Value | Description |
|-------|----------|-----------|-------|-------------|
| 1 | DWORD 0x0E1 | 0x384 | 0x00101100 | Port/lane configuration (upper) |
| 2 | DWORD 0x0E0 | 0x380 | 0x11010000 | Port/lane configuration (lower) |

**Wire-level I2C transactions:**

```
Write 1: [03] [00] [3C] [E1] [00] [11] [10] [00]
         Write stn0/port0  reg 0x384  value 0x00101100

Write 2: [03] [00] [3C] [E0] [00] [00] [01] [11]
         Write stn0/port0  reg 0x380  value 0x11010000
```

### 4.4 Register Comparison: 2:1 vs 4:1/8:1

Both modes write to the same two registers (0x380 and 0x384) on station 0,
port 0. These are PLX proprietary registers in the extended configuration
space, likely controlling port partitioning and lane assignment.

**Register 0x384 (DWORD 0x0E1):**

| Bit | 2:1 Mode | 4:1/8:1 Mode | Description |
|-----|----------|--------------|-------------|
| 8   | 1        | 0            | Port partition control bit |
| 12  | 1        | 0            | Lane assignment control bit |
| Other bits | Same | Same | Unchanged between modes |

**Register 0x380 (DWORD 0x0E0):**

| Bit | 2:1 Mode | 4:1/8:1 Mode | Description |
|-----|----------|--------------|-------------|
| 8   | 0        | 1            | Port partition control bit (inverse of 0x384) |
| 12  | 0        | 1            | Lane assignment control bit (inverse of 0x384) |
| Other bits | Same | Same | Unchanged between modes |

The key difference between modes is bits 8 and 12 in registers 0x380 and 0x384.
These bits are complementary -- when set in 0x384 for 2:1 mode, they are cleared
in 0x380, and vice versa for 4:1/8:1 mode. This likely controls how the switch's
internal crossbar routes lanes between upstream (host) and downstream (GPU) ports.

### 4.5 Register Identification

Registers 0x380 and 0x384 (DWORD indices 0xE0 and 0xE1) on the PEX8696 are
in the PLX Vendor-Specific (VS) extended capability region. Based on PLX
PEX8696 documentation and similar PLX switches:

- **0x380 (DWORD 0xE0):** Multi-Host Mode Configuration Register (lower)
  - Controls port partitioning and lane mapping for multi-host operation
  - Determines which upstream ports are active and how downstream ports
    are grouped

- **0x384 (DWORD 0xE1):** Multi-Host Mode Configuration Register (upper)
  - Additional partitioning control bits
  - Works in conjunction with register 0x380

These registers configure the PEX8696's "Virtual Switch" or "Multi-Host"
feature, which allows the 96-lane switch to be partitioned into multiple
independent switch domains, each serving a different host.

---

## 5. PEX8647 Multi-Host Configuration

### 5.1 pex8647_multi_host_mode_cfg (at 0x00037944, 312 bytes)

This function iterates over the 2 PEX8647 upstream switches with step 2
(indices 0 and 2), checking each for 8:1 mode.

```c
void pex8647_multi_host_mode_cfg(void) {
    printf("...", *mode_byte);

    for (local_11 = 0; local_11 < 4; local_11 += 2) {
        memset(shared_buffer, 0, 8);

        if (is_cfg_multi_host_8(local_11) == 1) {
            callback = pex8647_cfg_multi_host_8;    // 0x36DBC
        } else {
            callback = pex8647_cfg_multi_host_2_4;  // 0x36EF0
        }

        if (local_11 == 0) {
            bus_addr = 0xD4F3;  // PEX8647 #0
        } else {
            bus_addr = 0xD0F3;  // PEX8647 #1
        }

        packed = CONCAT12(3, bus_addr);
        _lx_QueueSend(queue, &message, 0);
    }
}
```

**Queue messages sent (2 total, one per PEX8647 switch):**

| Index | PEX8647 Switch | I2C Addr (8-bit) | 7-bit Addr | Queue packed |
|-------|---------------|------------------|------------|-------------|
| 0     | #0            | 0xD4             | 0x6A       | 0x0003D4F3  |
| 2     | #1            | 0xD0             | 0x68       | 0x0003D0F3  |

### 5.2 pex8647_cfg_multi_host_8 (at 0x00036DBC, 296 bytes)

Called for 8:1 mode configuration of PEX8647 switches.

```c
void pex8647_cfg_multi_host_8(bus_mux, i2c_addr, cmd, buffer_ptr) {
    byte data[18];  // from ROM at 0xF904C
    memcpy(data, ROM_DATA, 18);

    // Step 1: Initial write to station 2, port 0 (global port 8)
    *counter = 4;   // station/port byte = 4 -> station 2, port 0
    memcpy(command_buffer, &data[12], 6);
    write_pex8647_register(bus_mux, i2c_addr, cmd, buffer_ptr);

    // Step 2: Two writes to station 0, port 0 (global port 0)
    *counter = 0;   // station/port byte = 0 -> station 0, port 0
    for (i = 0; i < 2; i++) {
        memcpy(command_buffer, data + i*6, 6);
        write_pex8647_register(bus_mux, i2c_addr, cmd, buffer_ptr);
        _lx_ThreadSleep(0x14);  // 20 tick delay (~200ms)
    }
}
```

**Register writes for 8:1 mode (ROM data at 0xF904C):**

| Step | Target | Register | Byte Addr | Value | Delay |
|------|--------|----------|-----------|-------|-------|
| 1 (initial) | Station 2, Port 0 (global port 8) | DWORD 0x08D | 0x234 | 0x9C040000 | None |
| 2 (loop 0) | Station 0, Port 0 (global port 0) | DWORD 0x08D | 0x234 | 0x9C040100 | 20 ticks |
| 3 (loop 1) | Station 0, Port 0 (global port 0) | DWORD 0x077 | 0x1DC | 0x0F882010 | 20 ticks |

**Wire-level I2C transactions:**

```
Step 1: [03] [04] [3C] [8D] [00] [00] [04] [9C]
        Write stn2/port0  reg 0x234  value 0x9C040000

Step 2: [03] [00] [3C] [8D] [00] [01] [04] [9C]
        Write stn0/port0  reg 0x234  value 0x9C040100
        DELAY 20 ticks

Step 3: [03] [00] [3C] [77] [10] [20] [88] [0F]
        Write stn0/port0  reg 0x1DC  value 0x0F882010
        DELAY 20 ticks
```

### 5.3 pex8647_cfg_multi_host_2_4 (at 0x00036EF0, 296 bytes)

Called for 2:1 and 4:1 mode configuration of PEX8647 switches. Same
structure as cfg_multi_host_8 but with different register values.

**Register writes for 2:1/4:1 mode (ROM data at 0xF905E):**

| Step | Target | Register | Byte Addr | Value | Delay |
|------|--------|----------|-----------|-------|-------|
| 1 (initial) | Station 2, Port 0 (global port 8) | DWORD 0x08D | 0x234 | 0x9C040100 | None |
| 2 (loop 0) | Station 0, Port 0 (global port 0) | DWORD 0x08D | 0x234 | 0x9C040000 | 20 ticks |
| 3 (loop 1) | Station 0, Port 0 (global port 0) | DWORD 0x077 | 0x1DC | 0x0F802010 | 20 ticks |

**Wire-level I2C transactions:**

```
Step 1: [03] [04] [3C] [8D] [00] [01] [04] [9C]
        Write stn2/port0  reg 0x234  value 0x9C040100

Step 2: [03] [00] [3C] [8D] [00] [00] [04] [9C]
        Write stn0/port0  reg 0x234  value 0x9C040000
        DELAY 20 ticks

Step 3: [03] [00] [3C] [77] [10] [20] [80] [0F]
        Write stn0/port0  reg 0x1DC  value 0x0F802010
        DELAY 20 ticks
```

### 5.4 PEX8647 Register Comparison: 8:1 vs 2:1/4:1

**Register 0x234 (DWORD 0x08D) -- Hot-Plug / Power Control:**

This is the same register used for hot-plug power control (see
[pex8696-hotplug.md](pex8696-hotplug.md)), but here it is used for
multi-host configuration rather than individual slot power control.

| Target | 8:1 Mode Value | 2:1/4:1 Mode Value | Diff Bit |
|--------|---------------|--------------------|---------  |
| Station 2, Port 0 (initial) | 0x9C040000 | 0x9C040100 | Bit 8 |
| Station 0, Port 0 (loop)    | 0x9C040100 | 0x9C040000 | Bit 8 |

The key difference is **bit 8** of register 0x234:
- In 8:1 mode: Bit 8 is **set** on station 0/port 0 and **cleared** on station 2/port 0
- In 2:1/4:1 mode: Bit 8 is **cleared** on station 0/port 0 and **set** on station 2/port 0

This complementary pattern suggests bit 8 controls which upstream port
is the "primary" host port versus a "secondary" that can be merged with
the primary for wider (8:1) fan-out.

**Register 0x1DC (DWORD 0x077) -- Link/Port Configuration:**

| Mode | Value | Diff Bit |
|------|-------|----------|
| 8:1  | 0x0F882010 | Bit 19 = 1 |
| 2:1/4:1 | 0x0F802010 | Bit 19 = 0 |

Register 0x1DC at byte address 0x1DC is in the PLX proprietary configuration
space. The only difference is **bit 19**:
- **Set (1)** in 8:1 mode: likely enables port merging/aggregation
- **Cleared (0)** in 2:1/4:1 mode: ports operate independently

This register likely controls the PEX8647's internal lane aggregation
feature. In 8:1 mode, the two upstream ports on each PEX8647 are merged
to provide a wider link to a single host, allowing that host to access
8 GPU slots instead of 4.

---

## 6. Additional PEX8696 Configuration

### 6.1 pex8696_multi_host_mode_reg_set (at 0x00037420, 388 bytes)

This function sends additional register writes via a queue to complete
the multi-host configuration. It only executes when the mode parameter
is not 1 (i.e., for modes other than the simplest 2:1 configuration).

The function sends 3 queue messages, each containing a pre-formatted
PLX I2C write command. The data is sourced from ROM tables:

**Data Set 1 (ROM at 0xF909A, 8 bytes): `03 07 BC EB 00 00 00 01`**

```
PLX WRITE to station 3, port 3 (global port 15)
Register: DWORD 0x0EB = byte addr 0x3AC
Value: 0x01000000
```

**Data Set 2 (ROM at 0xF90A2, 8 bytes): `03 07 BC E1 00 00 00 00`**

```
PLX WRITE to station 3, port 3 (global port 15)
Register: DWORD 0x0E1 = byte addr 0x384
Value: 0x00000000
```

**Data Set 3 (ROM at 0xF90AA, 8 bytes): `03 07 BC E0 00 11 01 10`**

```
PLX WRITE to station 3, port 3 (global port 15)
Register: DWORD 0x0E0 = byte addr 0x380
Value: 0x10011100
```

**Notes on these writes:**

- All three target **station 3, port 3 (global port 15)** on the PEX8696.
  In the slot mapping table, port 15 is NOT assigned to any GPU slot.
  It is likely a **Non-Transparent Bridge (NT) port** or **management port**
  used for inter-switch communication in multi-host configurations.

- Register 0x3AC (DWORD 0xEB) is a PLX proprietary register, possibly
  related to NT bridge configuration or virtual switch partitioning.

- Registers 0x380 and 0x384 are the same multi-host mode registers
  written by `cfg_multi_host_2` and `cfg_multi_host_4`, but here they
  are written to port 15 instead of port 0. This configures the
  partitioning from the NT bridge port's perspective.

- The enables byte 0xBC includes **port_lo bit = 1** (bit 7 set),
  confirming the target is an odd-numbered port (port 3 within station 3).

### 6.2 pex8696_cfg (at 0x000372AC, 356 bytes)

This is a general PEX8696 port configuration function that writes a set
of registers to **every port** on **every PEX8696 switch**. It iterates
over all I2C addresses (0x30 through 0x36, step 2) and all 6 stations
(ports 0-5 per station, using station/port bytes 0x00-0x0A).

**Port iteration (station/port bytes):**

| Index | Stn/Port | Station | Port | Global Port |
|-------|----------|---------|------|-------------|
| 0     | 0x00     | 0       | 0    | 0           |
| 1     | 0x02     | 1       | 0    | 4           |
| 2     | 0x04     | 2       | 0    | 8           |
| 3     | 0x06     | 3       | 0    | 12          |
| 4     | 0x08     | 4       | 0    | 16          |
| 5     | 0x0A     | 5       | 0    | 20          |

**Register writes per port (5 registers, ROM data at 0xF907C):**

| Reg | DWORD | Byte Addr | Value | Description |
|-----|-------|-----------|-------|-------------|
| 1 | 0x2E7 | 0xB9C | 0x1C151515 | Lane equalization / signal integrity |
| 2 | 0x2E4 | 0xB90 | 0x130E0E0E | Lane equalization / signal integrity |
| 3 | 0x2E9 | 0xBA4 | 0x88888888 | De-emphasis / pre-shoot settings |
| 4 | 0x2EA | 0xBA8 | 0x88888888 | De-emphasis / pre-shoot settings |
| 5 | 0x081 | 0x204 | 0xFFFF0000 | Port control / status mask |

**Note:** Registers 0xB90-0xBA8 (DWORD indices 0x2E4-0x2EA) are in the PLX
SerDes (Serializer/Deserializer) configuration region. These control the
analog signal quality parameters for the PCIe lanes. The values 0x15, 0x0E,
0x1C, 0x13, and 0x88 are equalization coefficients and de-emphasis levels.

Register 0x204 (DWORD 0x081) is in the PLX VS0 region and likely controls
port masking or error reporting thresholds.

**Total I2C transactions:** 4 switches x 6 ports x 5 registers = **120 write-only transactions**.

---

## 7. Complete Mode-Switch Sequences

### 7.1 Order of Operations

The orchestration function at 0x38A98 performs the mode switch in this order:

```
1. Power off all GPU slots
   -> pex8696_all_slot_power_off()
   -> 16 write-only I2C transactions (4 switches x 4 ports)

2. Configure PEX8696 downstream switches (mode-specific)
   -> pex8696_multi_host_mode_cfg()
   -> 4 switches x 2 register writes = 8 I2C transactions

3. Configure PEX8647 upstream switches (mode-specific)
   -> pex8647_multi_host_mode_cfg()
   -> 2 switches x 3 register writes = 6 I2C transactions

4. Additional PEX8696 register setup
   -> pex8696_multi_host_mode_reg_set()
   -> 3 I2C transactions (to port 15)

5. General port re-configuration (SerDes, etc.)
   -> pex8696_cfg()
   -> 120 I2C transactions (all ports, all switches)
```

**Total: approximately 153 I2C transactions per mode switch.**

### 7.2 Switching to 2:1 Mode

For each PEX8696 switch (at I2C addresses 0x30, 0x32, 0x34, 0x36):

```
# Step 1: Power off all slots (register 0x080 on all downstream ports)
WRITE [03] [stn/port] [3C] [20] [power-off indicator values]
  x16 slots (4 per switch)

# Step 2: Configure PEX8696 mode registers on port 0
WRITE [03] [00] [3C] [E1] [00] [11] [10] [00]   reg 0x384 = 0x00101100
WRITE [03] [00] [3C] [E0] [00] [00] [01] [11]   reg 0x380 = 0x11010000

# Step 3: Configure PEX8647 (for each at 0xD4, 0xD0)
WRITE [03] [04] [3C] [8D] [00] [01] [04] [9C]   stn2/p0 reg 0x234 = 0x9C040100
WRITE [03] [00] [3C] [8D] [00] [00] [04] [9C]   stn0/p0 reg 0x234 = 0x9C040000
  DELAY 20 ticks
WRITE [03] [00] [3C] [77] [10] [20] [80] [0F]   stn0/p0 reg 0x1DC = 0x0F802010
  DELAY 20 ticks

# Step 4: Additional reg_set writes to PEX8696 port 15
WRITE to port 15: reg 0x3AC = 0x01000000
WRITE to port 15: reg 0x384 = 0x00000000
WRITE to port 15: reg 0x380 = 0x10011100

# Step 5: SerDes re-configuration (all ports, all switches)
WRITE reg 0xB9C = 0x1C151515  (x24 ports x4 switches)
WRITE reg 0xB90 = 0x130E0E0E
WRITE reg 0xBA4 = 0x88888888
WRITE reg 0xBA8 = 0x88888888
WRITE reg 0x204 = 0xFFFF0000
```

### 7.3 Switching to 4:1 Mode (Default)

Same as 2:1 except:

- PEX8696 register 0x384 = **0x00100000** (bits 8,12 cleared)
- PEX8696 register 0x380 = **0x11011100** (bits 8,12 set)
- PEX8647 same as 2:1 (uses cfg_multi_host_2_4 handler)

### 7.4 Switching to 8:1 Mode

Same as 4:1 for PEX8696, but different PEX8647 configuration:

- PEX8696 registers: Same as 4:1 mode (0x380 and 0x384)
- PEX8647 register 0x234:
  - Station 2, Port 0: **0x9C040000** (bit 8 cleared -- swapped from 2:1/4:1)
  - Station 0, Port 0: **0x9C040100** (bit 8 set -- swapped from 2:1/4:1)
- PEX8647 register 0x1DC: **0x0F882010** (bit 19 set for port merging)

---

## 8. PEX8696 Port Topology

### 8.1 Port Usage by Function

Based on the analysis of all multi-host and hot-plug functions:

| Port Range | Station | Ports | Function |
|------------|---------|-------|----------|
| 0          | 0       | 0     | Upstream / Configuration port |
| 1-3        | 0       | 1-3   | Upstream host links (station 0) |
| 4, 8       | 1, 2    | 0     | Downstream GPU slots (group A) |
| 12         | 3       | 0     | Downstream or NT bridge |
| 15         | 3       | 3     | NT bridge / management port |
| 16, 20     | 4, 5    | 0     | Downstream GPU slots (group B) |

**GPU slot assignment (from i2c-transport.md):**

| PEX8696 Switch | Stations for GPU | Global Ports | Slots |
|----------------|------------------|-------------|-------|
| #0 (0x30)      | 1, 2, 4, 5      | 4, 8, 16, 20 | 1, 2, 15, 16 |
| #1 (0x34)      | 1, 2, 4, 5      | 4, 8, 16, 20 | 3, 4, 13, 14 |
| #2 (0x32)      | 1, 2, 4, 5      | 4, 8, 16, 20 | 5, 6, 11, 12 |
| #3 (0x36)      | 1, 2, 4, 5      | 4, 8, 16, 20 | 7, 8, 9, 10 |

### 8.2 How Mode Affects Port Layout

In **4:1 mode** (default):
- Each PEX8696 presents 4 downstream x16 GPU ports and 1 upstream x16 host port
- Each host sees 4 GPU slots through a single PEX8696
- The PEX8647 routes each host link to one PEX8696

In **2:1 mode**:
- The PEX8696 port partitioning changes (bits 8, 12 of registers 0x380/0x384)
- Each host link is narrowed (x8 or x4) to allow more host connections
- Each host sees only 2 GPU slots
- The PEX8647 routes in 2-host-per-switch configuration

In **8:1 mode**:
- The PEX8647 merges its two upstream ports (bit 19 of register 0x1DC)
- A single host gets a wider link (x16 or x32) through the merged PEX8647
- That host can access 8 GPU slots across two PEX8696 switches
- The PEX8696 configuration is the same as 4:1 mode

---

## 9. PLX Register Map for Multi-Host

### 9.1 PEX8696 Registers

All registers are per-port, addressed via the PLX 4-byte I2C command:
`[cmd] [stn/port] [enables|reg_hi|port_lo] [reg_lo]`

| Byte Addr | DWORD | Port(s) | Name | Values | Used By |
|-----------|-------|---------|------|--------|---------|
| 0x080 | 0x020 | GPU ports | Slot Control/Status | Power indicators | pex8696_all_slot_off |
| 0x204 | 0x081 | All (0-20) | Port Control Mask | 0xFFFF0000 | pex8696_cfg |
| 0x380 | 0x0E0 | Port 0 | Multi-Host Config (lo) | Mode-dependent | cfg_multi_host_2/4 |
| 0x384 | 0x0E1 | Port 0 | Multi-Host Config (hi) | Mode-dependent | cfg_multi_host_2/4 |
| 0x380 | 0x0E0 | Port 15 | Multi-Host Config (lo) | 0x10011100 | reg_set |
| 0x384 | 0x0E1 | Port 15 | Multi-Host Config (hi) | 0x00000000 | reg_set |
| 0x3AC | 0x0EB | Port 15 | NT Bridge Config | 0x01000000 | reg_set |
| 0xB90 | 0x2E4 | All (0-20) | SerDes EQ Coefficient 1 | 0x130E0E0E | pex8696_cfg |
| 0xB9C | 0x2E7 | All (0-20) | SerDes EQ Coefficient 2 | 0x1C151515 | pex8696_cfg |
| 0xBA4 | 0x2E9 | All (0-20) | SerDes De-emphasis 1 | 0x88888888 | pex8696_cfg |
| 0xBA8 | 0x2EA | All (0-20) | SerDes De-emphasis 2 | 0x88888888 | pex8696_cfg |

### 9.2 PEX8647 Registers

| Byte Addr | DWORD | Port(s) | Name | Values | Used By |
|-----------|-------|---------|------|--------|---------|
| 0x1DC | 0x077 | Port 0 | Link/Port Config | 0x0F802010 or 0x0F882010 | cfg_multi_host_8, cfg_multi_host_2_4 |
| 0x234 | 0x08D | Port 0, 8 | Hot-Plug/Mode Control | 0x9C040000 or 0x9C040100 | cfg_multi_host_8, cfg_multi_host_2_4 |

### 9.3 Key Mode-Differentiating Bits

| Switch | Register | Bit | 2:1 | 4:1 | 8:1 | Description |
|--------|----------|-----|-----|-----|-----|-------------|
| PEX8696 | 0x384 | 8 | 1 | 0 | 0 | Port partition control |
| PEX8696 | 0x384 | 12 | 1 | 0 | 0 | Lane assignment control |
| PEX8696 | 0x380 | 8 | 0 | 1 | 1 | Port partition (complement) |
| PEX8696 | 0x380 | 12 | 0 | 1 | 1 | Lane assignment (complement) |
| PEX8647 | 0x234 (stn0/p0) | 8 | 0 | 0 | 1 | Primary host port select |
| PEX8647 | 0x234 (stn2/p0) | 8 | 1 | 1 | 0 | Secondary host port select |
| PEX8647 | 0x1DC | 19 | 0 | 0 | 1 | Port merge / aggregation |

---

## 10. Timing and Delays

| Operation | Delay | Context |
|-----------|-------|---------|
| PEX8647 register writes (between loop iterations) | 20 ticks (~200ms) | After each reg 0x234 and 0x1DC write |
| PEX8696 mode register writes | None | Immediate, no delay between writes |
| Power-off before mode switch | None specified | Assumed synchronous via queue |
| Total mode switch time | Estimated 1-2 seconds | Including all I2C transactions and delays |

The 20-tick delays in the PEX8647 configuration suggest the switch needs
time to reconfigure its internal crossbar and link state machine after
each register write. The PEX8696 mode writes appear to be latched
atomically and don't require inter-write delays.

---

## 11. Queue-Based Asynchronous Dispatch

All multi-host configuration operations use the firmware's queue-based
asynchronous dispatch mechanism rather than direct function calls:

### 11.1 Queue Message Format

```c
struct queue_message {
    void *data_ptr;       // Pointer to data buffer / callback context
    void *callback;       // Function to call
    uint32_t unused;      // Always 0
    uint32_t packed;      // bus_mux | (i2c_addr << 8) | (cmd << 16)
};
```

The queue handler extracts the packed field and calls:
```c
callback(bus_mux, i2c_addr, cmd, data_ptr);
```

### 11.2 Callback Functions

| Callback Address | Name | Write Len | Description |
|------------------|------|-----------|-------------|
| 0x36BEC | pex8696_cfg_multi_host_2 | 8 | PLX register write (standard) |
| 0x36CD4 | pex8696_cfg_multi_host_4 | 8 | PLX register write (standard) |
| 0x36DBC | pex8647_cfg_multi_host_8 | 8 | PLX register write (standard) |
| 0x36EF0 | pex8647_cfg_multi_host_2_4 | 8 | PLX register write (standard) |
| 0x36690 | raw_plx_i2c_write | 9 | Direct I2C write (extended) |

The `raw_plx_i2c_write` at 0x36690 is notable because it calls
`PI2CWriteRead` with a 9-byte write length instead of the standard 8 bytes.
This may be an extended PLX I2C command format or the extra byte serves
as a framing/protocol extension for the NT bridge configuration.

### 11.3 Queue Handle

All multi-host operations use the same queue handle at global address
`0x001143E0`. This serialises all PLX switch configuration operations
through a single worker task, preventing concurrent register access.

---

## 12. Summary of Key Findings

1. **Three modes are supported:** 2:1, 4:1 (default), and 8:1 host-to-GPU fan-out.
   Mode selection is triggered via IPMI commands (sensor IDs 0x802D-0x802F+).

2. **Mode switching requires powering off all GPU slots first.** The firmware
   calls `pex8696_all_slot_power_off()` before any configuration changes.

3. **PEX8696 configuration** uses two registers at byte addresses 0x380 and 0x384
   on port 0 (station 0). Only bits 8 and 12 differ between 2:1 and 4:1/8:1 modes.
   4:1 and 8:1 modes share the same PEX8696 configuration.

4. **PEX8647 configuration** uses register 0x234 on two ports (station 0/port 0
   and station 2/port 0) and register 0x1DC on port 0. The key 8:1 mode change
   is bit 19 of register 0x1DC, which enables upstream port merging/aggregation.

5. **The mode switch is entirely driven by register writes** -- no EEPROM
   modifications or switch resets are required. The PLX switches support
   runtime reconfiguration of their port partitioning.

6. **Order of operations:** Power off -> PEX8696 mode regs -> PEX8647 mode regs
   -> PEX8696 NT bridge regs -> PEX8696 SerDes regs. The PEX8696 downstream
   switches are configured before the PEX8647 upstream switches.

7. **Approximately 153 I2C transactions** are needed for a complete mode switch,
   with delays of about 200ms between PEX8647 register writes.

8. **NT bridge port 15** (station 3, port 3) on each PEX8696 receives separate
   configuration during mode switching, suggesting it serves as an inter-switch
   communication port for multi-host coordination.

9. **SerDes re-equalisation** is performed after every mode switch. The same
   equalisation values are written to all ports on all switches, suggesting
   the PCIe link parameters are pre-characterised for the C410X chassis
   backplane and don't change between modes.

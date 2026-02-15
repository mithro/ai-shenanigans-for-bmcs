# PEX PCIe Switch I2C Command Reverse Engineering — Design Document

**Date:** 2026-02-16
**Branch:** `claude/pex-i2c-reverse-engineering`
**Target Hardware:** Dell PowerEdge C410X GPU expansion chassis

## Goal

Reverse engineer and document the exact I2C commands that the Dell C410X BMC
firmware (`fullfw`) sends to the PLX/Broadcom PEX8696 and PEX8647 PCIe switches.
The primary source of truth is the firmware binary itself; public references
(plxtools, PLX SDK docs, Linux kernel drivers) are used to annotate and validate
findings.

## Background

The Dell C410X BMC runs Avocent MergePoint firmware (Linux 2.6.23.1) on an
Aspeed AST2050 SoC. The core IPMI engine (`/sbin/fullfw`, ~1.2MB ARM ELF)
contains functions that communicate with PLX PCIe switches over I2C bus 0xF3
to control:

- **Hot-plug** — Per-slot power enable/disable for 16 GPU slots
- **Power sequencing** — Staggered power-on in groups of 4 to limit inrush
- **Multi-host configuration** — Reconfigure PCIe lane topology (2:1, 4:1, 8:1)
- **Link monitoring** — Read link status, handle interrupts

### I2C Bus Topology

```
AST2050 I2C Engine 3 (bus 0xF3, register base 0x1E78A100)
  ├── PEX8696 #1 @ 0x18 (PLX address) / 0x30 (GBT address)
  ├── PEX8696 #2 @ 0x1A / 0x34
  ├── PEX8696 #3 @ 0x19 / 0x32
  ├── PEX8696 #4 @ 0x1B / 0x36
  └── PEX8647 (address TBD — to be discovered during RE)
```

### PLX I2C Protocol (from plxtools)

- 7-bit slave address
- Register access: 16-bit address (big-endian), 32-bit value (little-endian)
- Read: write 2-byte address → read 4 bytes
- Write: write 2-byte address + 4-byte value

## Target Functions

### PEX8696 (Primary — Slot Power & Hot-Plug)

| Function | Purpose |
|----------|---------|
| `pex8696_slot_power_on` | Power on a single GPU slot via hot-plug controller |
| `pex8696_all_slot_power_off` | Emergency power-off all 16 slots |
| `pex8696_hp_ctrl` | Low-level hot-plug register manipulation |
| `pex8696_hp_on` / `pex8696_hp_off` | Enable/disable hot-plug per port |
| `pex8696_cfg_multi_host_2` | Configure 2:1 host mode |
| `pex8696_cfg_multi_host_4` | Configure 4:1 host mode |

### PEX8647 (Secondary — Upstream Host Link)

| Function | Purpose |
|----------|---------|
| `pex8647_cfg_multi_host_2_4` | Configure 2:1 or 4:1 mode |
| `pex8647_cfg_multi_host_8` | Configure 8:1 mode |
| `pex8647_multi_host_mode_cfg` | Top-level mode selection |

### Supporting Functions

| Function | Purpose |
|----------|---------|
| `PI2CWriteRead` | Private I2C bus read/write primitive |
| `PI2CMuxWriteRead` | I2C access through PCA9548 mux |
| `Start_GPU_Power_Sequence` | Orchestrates staggered power-on |
| `gpu_power_on_*` | Per-group power-on (groups of 4 slots) |

## Approach

### Phase 1: Firmware Extraction

1. Extract `fullfw` from `backup/c410xbmc135.zip` via SquashFS
2. Also extract kernel modules (`aess_i2cdrv.ko`) for I2C driver understanding
3. Verify ELF format, check for debug symbols

### Phase 2: Initial Triage (objdump + Python)

1. `arm-linux-gnueabi-objdump -t fullfw` — dump symbol table
2. `strings fullfw | grep -i pex` — find string references
3. Python script to scan for I2C address patterns and PLX register offsets
4. Map all PEX-related function addresses

### Phase 3: Deep Analysis (Ghidra)

1. Load `fullfw` into Ghidra (ARM little-endian, Linux ELF)
2. Apply known symbol names from Phase 2
3. Decompile each target function
4. Trace every I2C transaction: bus, address, register, value, direction
5. Document read-modify-write patterns and conditional branches

### Phase 4: Cross-Reference & Documentation

1. Match discovered register addresses against:
   - plxtools PEX8696 definitions (pex8696.yaml)
   - PCIe Base Specification hot-plug registers
   - PLX SDK documentation (if available)
2. Annotate each register access with its purpose
3. Build complete I2C transaction sequences for each operation

## Deliverables

All in `dell-c410x-firmware/pex-i2c-analysis/`:

| File | Description |
|------|-------------|
| `README.md` | Overview and how to use the analysis |
| `research/` | Research notes, reference material gathered |
| `tools/extract_fullfw.py` | Script to extract fullfw from firmware zip |
| `tools/scan_i2c_patterns.py` | Binary scanner for I2C address/register patterns |
| `analysis/` | Ghidra exports, decompilation notes, raw findings |
| `analysis/symbol-table.txt` | Full symbol table dump from fullfw |
| `analysis/pex-functions.md` | Per-function decompilation and I2C trace |
| `PEX-I2C-COMMANDS.md` | Final polished document with complete I2C command reference |

## Workflow

- Work in worktree at `.worktrees/pex-i2c-re`
- Branch: `claude/pex-i2c-reverse-engineering`
- Commit after every meaningful unit of work (extract, each function analyzed, etc.)
- Push to GitHub regularly to prevent data loss
- Use plxtools as reference but firmware binary is the ground truth

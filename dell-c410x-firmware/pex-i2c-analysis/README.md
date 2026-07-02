# PEX I2C Analysis -- Dell C410X

Reverse engineering of the I2C commands that the Dell C410X BMC firmware
(`fullfw` ELF binary) sends to the PLX/Broadcom PEX8696 and PEX8647
PCIe switches to control GPU slot power, hot-plug, and multi-host
configuration.

## Key Findings

### PLX I2C Protocol

The PEX8696/PEX8647 use a **4-byte I2C command format** (not the simpler
2-byte address format used by plxtools for smaller PLX switches):

```
[cmd] [stn_port] [enables|reg_hi] [reg_lo]
```

- `cmd` = 0x03 (write) or 0x04 (read)
- `stn_port` encodes the target station and port within the switch
- `enables|reg_hi` packs byte-enable mask and high bits of register index
- `reg_lo` is the low 8 bits of the DWORD register index

Write transactions send 8 bytes (4-byte command + 4-byte little-endian
value). Read transactions use a write-then-repeated-start-read sequence.

### I2C Bus Topology

All 6 PLX switches are on **I2C bus 3** of the AST2050 (bus byte `0xF3`,
no I2C mux):

| Device     | 8-bit Addr | 7-bit Addr | GPU Slots          |
|------------|------------|------------|--------------------|
| PEX8696 #0 | 0x30       | 0x18       | 1, 2, 15, 16      |
| PEX8696 #1 | 0x34       | 0x1A       | 3, 4, 13, 14      |
| PEX8696 #2 | 0x32       | 0x19       | 5, 6, 11, 12      |
| PEX8696 #3 | 0x36       | 0x1B       | 7, 8, 9, 10       |
| PEX8647 #0 | 0xD4       | 0x6A       | Upstream hosts 0-1 |
| PEX8647 #1 | 0xD0       | 0x68       | Upstream hosts 2-3 |

### Registers Used

13 PLX registers documented (2 PCIe standard, 11 PLX proprietary):

| Byte Addr | Name                      | Classification         |
|-----------|---------------------------|------------------------|
| 0x07C     | Slot Capabilities / WP    | PCIe Std (PLX-modified)|
| 0x080     | Slot Control / Status     | PCIe Standard          |
| 0x1DC     | Port Merging/Aggregation  | PLX Proprietary        |
| 0x204     | Port Control Mask         | PLX Proprietary        |
| 0x228     | Hot-Plug LED / MRL        | PLX Proprietary        |
| 0x234     | Hot-Plug Power Controller | PLX Proprietary        |
| 0x380     | Lane Config (lower)       | PLX Proprietary        |
| 0x384     | Lane Config (upper)       | PLX Proprietary        |
| 0x3AC     | NT Bridge Setup           | PLX Proprietary        |
| 0xB90     | SerDes EQ Coefficient 1   | PLX Proprietary        |
| 0xB9C     | SerDes EQ Coefficient 2   | PLX Proprietary        |
| 0xBA4     | SerDes De-emphasis 1      | PLX Proprietary        |
| 0xBA8     | SerDes De-emphasis 2      | PLX Proprietary        |

### Slot Power Control

- **9 I2C transactions per slot** to power on (4 reads + 5 writes + 100ms delay)
- **144 I2C transactions total** for full 16-slot boot (~2.0 seconds)
- Power-on is staggered in 4 phases, one slot per switch per phase, to
  distribute inrush current
- Power-off needs only **1 write per slot** (Slot Control register 0x080)

### Hot-Plug

- Uses both I2C register writes (PLX hardware power controller at 0x234)
  and GPIO (attention indicator pulse, IRQ disable/enable)
- Write protection (bit 18 of register 0x07C) must be cleared before
  modifying PLX VS1 registers

### Multi-Host Modes

- Supports 2:1, 4:1, and 8:1 host-to-GPU fan-out ratios
- Modes differ by only a few register bits in lane configuration
  (registers 0x380/0x384) and port merging (register 0x1DC)
- Both PEX8696 and PEX8647 switches are reconfigured together

## Directory Structure

```
pex-i2c-analysis/
  README.md                                 -- This file
  PEX-I2C-COMMANDS.md                       -- Main reference document (1283 lines, ~49 KB)
  .gitignore                                -- Excludes extracted binaries and Ghidra project
  analysis/                                 -- Raw analysis outputs
    extraction-results.md                   -- Firmware extraction log
    symbol-table.txt                        -- Full symbol table (3983 symbols)
    pex-symbols.md                          -- PEX-related symbol analysis
    i2c-pattern-scan.md                     -- Binary pattern scan for I2C constants
    i2c-transport.md                        -- I2C transport layer protocol details
    pex8696-hotplug.md                      -- Hot-plug register analysis
    pex-multihost.md                        -- Multi-host configuration analysis
    power-sequencing.md                     -- Power sequencing analysis
    decompiled/                             -- 45 Ghidra-decompiled C functions
      INDEX.md                              -- Function index by category
      pex8696_slot_power_on_reg.c           -- Slot power-on sequence
      pex8696_hp_ctrl.c                     -- Hot-plug control
      pex8647_cfg_multi_host_*.c            -- Multi-host configuration
      PI2CWriteRead.c                       -- I2C transport layer
      ... (45 files total)
    fullfw                                  -- Extracted ELF binary (gitignored)
    sbin/, lib/                             -- Extracted firmware files (gitignored)
    ghidra_project/                         -- Ghidra project files (gitignored)
  research/                                 -- Cross-reference material
    plxtools-register-map.md                -- plxtools PEX8696 register definitions
    pcie-hotplug-registers.md               -- PCIe specification hot-plug registers
  tools/                                    -- Python scripts used for analysis
    extract_fullfw.py                       -- Extract fullfw from c410xbmc135.zip SquashFS
    ghidra_export_pex_functions.py          -- Ghidra headless script to decompile functions
    scan_i2c_patterns.py                    -- Scan binary for I2C address/register patterns
    extract_multihost_data.py               -- Extract multi-host register data from binary
    analyze_multihost_regs.py               -- Analyze multi-host register configurations
    decode_raw_write.py                     -- Decode raw I2C write buffers from firmware
    disasm_is_cfg.py                        -- Disassemble and identify cfg-related functions
    trace_orchestrator.py                   -- Trace power-on orchestration call graph
    trace_reg_set_callers.py                -- Trace callers of register-set functions
    verify_buffer_addr.py                   -- Verify I2C buffer addresses in firmware
```

**File counts:** 72 git-tracked files (142 total on disk including gitignored binaries).

## How to Reproduce

### Prerequisites

- `squashfs-tools` -- for extracting the SquashFS firmware image
- `binutils-arm-linux-gnueabi` -- for ARM ELF symbol extraction (`arm-linux-gnueabi-nm`)
- [Ghidra](https://ghidra-sre.org/) 11.3+ -- for decompilation
- Python 3.8+ with `uv` -- for running analysis scripts

### Steps

1. **Extract the firmware binary:**

   ```sh
   uv run tools/extract_fullfw.py
   ```

   This extracts `fullfw` from `../backup/c410xbmc135.zip` via SquashFS
   into `analysis/fullfw`.

2. **Export symbol table:**

   ```sh
   arm-linux-gnueabi-nm -n analysis/fullfw > analysis/symbol-table.txt
   ```

3. **Decompile with Ghidra:**

   Use `tools/ghidra_export_pex_functions.py` as a Ghidra headless
   analyser script to batch-decompile the 45 PEX/I2C-related functions
   into `analysis/decompiled/`.

4. **Run analysis tools:**

   ```sh
   uv run tools/scan_i2c_patterns.py       # Scan for I2C patterns
   uv run tools/extract_multihost_data.py   # Extract multi-host data
   uv run tools/analyze_multihost_regs.py   # Analyze register configs
   uv run tools/trace_orchestrator.py       # Trace power-on sequence
   ```

5. **Cross-reference with plxtools:**

   Compare register definitions against
   [plxtools](https://github.com/mithro/plxtools) source code, particularly
   `PlxApi/Reg8696.h` and `PlxApi/RegDefs.c`.

## Source Material

- **Firmware:** Avocent MergePoint embedded firmware v1.35
- **Binary:** `fullfw` -- ARM 32-bit little-endian ELF, not stripped, 3983 symbols
- **Extracted from:** `dell-c410x-firmware/backup/c410xbmc135.zip` -> SquashFS -> `/sbin/fullfw`
- **Decompiler:** Ghidra 11.3.1 (ARM:LE:32:v5t / ARM926EJ-S)

## References

- [plxtools](https://github.com/mithro/plxtools) -- PLX I2C protocol
  implementation and PEX8696 register definitions
- [PCI Express Base Specification](https://pcisig.com/specifications) --
  Hot-plug chapter (Chapter 6.7) for Slot Control/Status register definitions
- [PLX SDK](https://www.broadcom.com/) -- `PlxApi/RegDefs.c` and
  `PlxApi/Reg8696.h` for proprietary register names and addresses
- Dell C410X firmware analysis: `../ANALYSIS.md`
- Dell C410X device tree: `../aspeed-bmc-dell-c410x.dts`

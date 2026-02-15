# PEX I2C Reverse Engineering — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

> **CRITICAL WORKTREE REMINDER:**
> - **All work happens in:** `/home/tim/github/mithro/ai-shenanigans-for-bmcs/.worktrees/pex-i2c-re`
> - **Branch:** `claude/pex-i2c-reverse-engineering`
> - **Commit after EVERY small piece of progress. Push after every few commits.**
> - **NEVER work in the main repo directory.**

**Goal:** Reverse engineer and document every I2C command the Dell C410X BMC firmware sends to the PLX PEX8696 and PEX8647 PCIe switches.

**Architecture:** Extract the `fullfw` ARM ELF binary from firmware SquashFS, use objdump/nm for initial triage of PEX-related symbols, then Ghidra headless for decompilation of each function. Cross-reference discovered register addresses with plxtools PEX8696 definitions.

**Tech Stack:** Python (via `uv`), ARM binutils, Ghidra (headless), squashfs-tools

---

## Prerequisites

Install required system packages:

```bash
sudo apt-get install -y squashfs-tools binutils-arm-linux-gnueabi
```

Verify:

```bash
which unsquashfs arm-linux-gnueabi-objdump arm-linux-gnueabi-nm arm-linux-gnueabi-readelf
```

---

## Task 1: Create Directory Structure

**Files:**
- Create: `dell-c410x-firmware/pex-i2c-analysis/README.md`
- Create: `dell-c410x-firmware/pex-i2c-analysis/research/`
- Create: `dell-c410x-firmware/pex-i2c-analysis/tools/`
- Create: `dell-c410x-firmware/pex-i2c-analysis/analysis/`

**Step 1: Create directories and README**

```bash
cd /home/tim/github/mithro/ai-shenanigans-for-bmcs/.worktrees/pex-i2c-re
mkdir -p dell-c410x-firmware/pex-i2c-analysis/{research,tools,analysis}
```

Write a `README.md` explaining the analysis directory structure.

**Step 2: Commit**

```bash
git add dell-c410x-firmware/pex-i2c-analysis/
git commit -m "Add PEX I2C analysis directory structure"
git push
```

---

## Task 2: Write Firmware Extraction Script

**Files:**
- Create: `dell-c410x-firmware/pex-i2c-analysis/tools/extract_fullfw.py`

**Step 1: Write extraction script**

Python script (run with `uv run`) that:
1. Opens `backup/c410xbmc135.zip`
2. Finds the .pec firmware image inside
3. Locates SquashFS magic bytes (`hsqs`) in the .pec
4. Writes the SquashFS blob to a temp file
5. Calls `unsquashfs` to extract `/sbin/fullfw` and `/lib/modules/*/aess_i2cdrv.ko`
6. Copies extracted files to `dell-c410x-firmware/pex-i2c-analysis/analysis/`
7. Reports file sizes and `file` command output for verification

**Step 2: Commit the script**

```bash
git add dell-c410x-firmware/pex-i2c-analysis/tools/extract_fullfw.py
git commit -m "Add fullfw extraction script"
git push
```

**Step 3: Run the extraction**

```bash
cd /home/tim/github/mithro/ai-shenanigans-for-bmcs/.worktrees/pex-i2c-re
uv run dell-c410x-firmware/pex-i2c-analysis/tools/extract_fullfw.py
```

Expected output: `fullfw` is an ARM ELF binary, ~1.2MB

**Step 4: Commit extracted binary info (NOT the binary itself)**

Write a `dell-c410x-firmware/pex-i2c-analysis/analysis/extraction-results.md` with
the `file`, `size`, and `md5sum` output. Add the actual binary to `.gitignore`.

```bash
git add dell-c410x-firmware/pex-i2c-analysis/analysis/extraction-results.md
git add .gitignore  # if modified
git commit -m "Document fullfw extraction results"
git push
```

---

## Task 3: Symbol Table Dump and PEX Function Discovery

**Files:**
- Create: `dell-c410x-firmware/pex-i2c-analysis/analysis/symbol-table.txt`
- Create: `dell-c410x-firmware/pex-i2c-analysis/analysis/pex-symbols.md`

**Step 1: Dump the full symbol table**

```bash
arm-linux-gnueabi-nm -n analysis/fullfw > analysis/symbol-table.txt
```

**Step 2: Commit the symbol table**

```bash
git add analysis/symbol-table.txt
git commit -m "Dump fullfw symbol table"
```

**Step 3: Extract PEX-related symbols**

Filter for symbols containing `pex`, `PEX`, `plx`, `PLX`, `hp_ctrl`, `slot_power`,
`multi_host`, `PI2C`, `I2CWriteRead`, `I2CMux`. Write to `pex-symbols.md` with
addresses, sizes, and types.

**Step 4: Commit PEX symbol analysis**

```bash
git add analysis/pex-symbols.md
git commit -m "Identify PEX-related function symbols in fullfw"
git push
```

**Step 5: Also extract strings referencing PEX/I2C**

```bash
arm-linux-gnueabi-strings analysis/fullfw | grep -iE 'pex|plx|slot.*power|hp.*ctrl|multi.*host|i2c.*mux'
```

Document interesting strings in `pex-symbols.md`.

**Step 6: Commit string analysis**

```bash
git add analysis/pex-symbols.md
git commit -m "Add string references for PEX/I2C functions"
git push
```

---

## Task 4: I2C Address Pattern Scanner

**Files:**
- Create: `dell-c410x-firmware/pex-i2c-analysis/tools/scan_i2c_patterns.py`

**Step 1: Write scanner script**

Python script that reads the `fullfw` ELF binary and:
1. Scans for known I2C slave addresses (0x18, 0x19, 0x1A, 0x1B for PEX8696)
2. Scans for known PLX register offsets (0x208 port_control, 0x260 eeprom_ctrl, etc.)
3. Scans for I2C bus identifiers (0xF3)
4. Reports the byte offset and surrounding context (hex dump) for each match
5. Cross-references matches against the symbol table to identify which function
   contains each match

This helps identify which functions touch PEX registers even if the symbol names
aren't obvious.

**Step 2: Commit the scanner**

```bash
git add tools/scan_i2c_patterns.py
git commit -m "Add I2C address pattern scanner tool"
```

**Step 3: Run the scanner and document results**

```bash
uv run tools/scan_i2c_patterns.py analysis/fullfw > analysis/i2c-pattern-scan.md
```

**Step 4: Commit scan results**

```bash
git add analysis/i2c-pattern-scan.md
git commit -m "Document I2C address pattern scan results"
git push
```

---

## Task 5: Ghidra Headless Import and Auto-Analysis

**Files:**
- Create: `dell-c410x-firmware/pex-i2c-analysis/tools/ghidra_import.sh`
- Create: `dell-c410x-firmware/pex-i2c-analysis/tools/ghidra_export_functions.py` (Ghidra script)

**Step 1: Create Ghidra project and import fullfw**

Use Ghidra's `analyzeHeadless` to:
1. Create a new Ghidra project in `analysis/ghidra_project/`
2. Import `fullfw` as ARM:LE:32:v5t (ARM926EJ-S is ARMv5TEJ)
3. Run auto-analysis

```bash
/home/tim/tools/ghidra/support/analyzeHeadless \
  analysis/ghidra_project ProjectName \
  -import analysis/fullfw \
  -processor "ARM:LE:32:v5t" \
  -analysisTimeoutPerFile 600
```

**Step 2: Commit the import script**

```bash
git add tools/ghidra_import.sh
git commit -m "Add Ghidra headless import script"
git push
```

**Step 3: Write Ghidra post-script to export PEX function decompilations**

Ghidra Python script that:
1. Iterates over all functions matching PEX/I2C patterns
2. Decompiles each one using Ghidra's decompiler
3. Writes the decompiled C code to individual files in `analysis/decompiled/`

**Step 4: Run the export and commit each decompiled function**

Each decompiled function file gets its own commit:
- `analysis/decompiled/pex8696_slot_power_on.c`
- `analysis/decompiled/pex8696_hp_ctrl.c`
- etc.

```bash
git add analysis/decompiled/pex8696_slot_power_on.c
git commit -m "Decompile pex8696_slot_power_on"
# repeat for each function
git push
```

---

## Task 6: Analyze I2C Transport Layer

**Files:**
- Create: `dell-c410x-firmware/pex-i2c-analysis/analysis/i2c-transport.md`

**Step 1: Decompile PI2CWriteRead and PI2CMuxWriteRead**

These are the low-level I2C helpers that all PEX functions call. Document:
- Function signatures (parameters: bus, address, register, value, direction)
- How they map to kernel driver ioctl calls (`/dev/aess_i2cdrv`)
- The I2C transaction format (address encoding, register width, value encoding)
- Error handling and retry logic

**Step 2: Commit transport analysis**

```bash
git add analysis/i2c-transport.md
git commit -m "Document I2C transport layer (PI2CWriteRead, PI2CMuxWriteRead)"
git push
```

---

## Task 7: Trace PEX8696 Hot-Plug Functions

**Files:**
- Create: `dell-c410x-firmware/pex-i2c-analysis/analysis/pex8696-hotplug.md`

For each function, document the exact I2C transaction sequence:

**Step 1: Analyze pex8696_hp_ctrl**

This is the lowest-level hot-plug function. Document:
- Which I2C address(es) it writes to
- Which PLX register(s) it reads/writes
- Bit fields manipulated
- Commit findings immediately

**Step 2: Analyze pex8696_hp_on / pex8696_hp_off**

Document how they call pex8696_hp_ctrl with specific register values.
Commit after each function.

**Step 3: Analyze pex8696_slot_power_on**

Document the full power-on sequence for a single slot:
- Which PEX8696 instance (by I2C address) maps to which slots
- Which port registers are written
- Any delays or status polling
- Commit findings

**Step 4: Analyze pex8696_all_slot_power_off**

Document the emergency power-off sequence.
Commit findings.

**Step 5: Push all hot-plug analysis**

```bash
git push
```

---

## Task 8: Trace PEX Multi-Host Configuration Functions

**Files:**
- Create: `dell-c410x-firmware/pex-i2c-analysis/analysis/pex-multihost.md`

**Step 1: Analyze pex8696_cfg_multi_host_2**

Document I2C transactions for 2:1 mode configuration.
Commit.

**Step 2: Analyze pex8696_cfg_multi_host_4**

Document I2C transactions for 4:1 mode configuration.
Commit.

**Step 3: Analyze pex8647_cfg_multi_host_2_4 and pex8647_cfg_multi_host_8**

Document PEX8647 multi-host configuration. This reveals the PEX8647 I2C address.
Commit after each function.

**Step 4: Analyze pex8647_multi_host_mode_cfg**

Document the top-level mode selection logic.
Commit and push.

---

## Task 9: Trace GPU Power Sequencing

**Files:**
- Create: `dell-c410x-firmware/pex-i2c-analysis/analysis/power-sequencing.md`

**Step 1: Analyze Start_GPU_Power_Sequence**

Document the orchestration: which PEX functions are called, in what order,
with what delays. Shows how the staggered groups (1/5/9/13, 2/6/10/14, etc.)
map to PEX8696 instances and port numbers.

**Step 2: Analyze gpu_power_on_* group functions**

Document how each group maps to specific PEX I2C transactions.
Commit after each group.

**Step 3: Push**

---

## Task 10: Cross-Reference with plxtools Register Definitions

**Files:**
- Create: `dell-c410x-firmware/pex-i2c-analysis/research/plxtools-register-map.md`
- Create: `dell-c410x-firmware/pex-i2c-analysis/research/pcie-hotplug-registers.md`

**Step 1: Map discovered registers to plxtools PEX8696 YAML**

Cross-reference every register address found in firmware against:
- `plxtools/src/plxtools/devices/definitions/pex8696.yaml`
- PCIe Base Specification hot-plug control/status register definitions
- Any PLX SDK documentation found online

**Step 2: Document register cross-reference**

For each register: address, name, bit fields, how firmware uses it.
Commit.

**Step 3: Push**

---

## Task 11: Write Final PEX I2C Commands Document

**Files:**
- Create: `dell-c410x-firmware/pex-i2c-analysis/PEX-I2C-COMMANDS.md`

**Step 1: Write I2C Transport Protocol section**

How fullfw talks to PLX switches: bus, address format, register width, byte order.

**Step 2: Commit**

**Step 3: Write Register Reference Table**

All PLX registers accessed by the firmware, with addresses, bit fields, and meanings.

**Step 4: Commit**

**Step 5: Write Per-Function I2C Traces**

For each firmware function, the exact sequence of I2C transactions.

**Step 6: Commit**

**Step 7: Write Power Sequencing section**

Complete startup/shutdown I2C sequences.

**Step 8: Commit**

**Step 9: Write Multi-Host Configuration section**

Lane topology switching sequences.

**Step 10: Commit and push**

---

## Task 12: Final Review and README Update

**Files:**
- Modify: `dell-c410x-firmware/pex-i2c-analysis/README.md`

**Step 1: Update README with summary of all findings**

**Step 2: Verify all analysis files are committed**

```bash
git status
```

**Step 3: Final commit and push**

```bash
git push
```

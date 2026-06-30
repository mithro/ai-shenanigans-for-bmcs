# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is a **reverse-engineering and documentation** project, not a conventional
software product. The goal is to replace proprietary BMC firmware on boards
using the **Aspeed AST2050** SoC (also sold as AST1100) with open-source
alternatives (OpenBMC / u-bmc). The primary deliverables are Markdown analysis
documents, a hand-reconstructed Linux device tree, decompiled C, and Python
control/analysis scripts. There is **no test suite** — "correctness" means the
analysis matches the firmware binaries and datasheets, cross-checked and cited.

Read `resources.md` (project-wide goals and hardware background) and each board
directory's `STATUS.md` (completed work + open items) before starting work in
that area. Every factual claim in the docs is expected to carry evidence (a
firmware offset, decompiled snippet, datasheet quote, or command output) — match
that standard when adding to them.

## Architecture: shared SoC, per-board specifics

The AST2050 is **not supported in mainline Linux** (earliest is the AST2400 /
"G4"). The kernel/SoC porting work is shared across all boards; each board then
contributes only its own device tree describing I2C topology, GPIO wiring, and
sensors. This drives the directory layout:

- **`asus-kgpe-d16-firmware/`** — The *source of truth for SoC-level work.*
  Analysis of Raptor Engineering's working Linux 2.6.28.9 AST2050 port.
  `RAPTOR-PORTING-GUIDE.md` maps each of Raptor's kernel changes to the
  corresponding mainline subsystem. `DDR2-INIT-REVERSE-ENGINEERING.md`,
  `JTAG-HEADERS.md`, and the `*.S`/`*.h` files cover low-level bring-up.
- **`dell-c410x-firmware/`** — A specific board: the Dell PowerEdge C410X, a
  16-slot PCIe GPU expansion chassis (no host CPU; managed entirely by its BMC)
  running Avocent MergePoint firmware. Contains the reverse-engineered device
  tree, IO-table decoding, PEX PCIe-switch I2C analysis, kernel patches, and
  boot/build tooling. `REUSING-KGPE-D16-WORK.md` explains how to apply the
  shared KGPE-D16 SoC work here.
- **`hpe-ipdu-firmware/`** — A different chip entirely (Digi NS9360, *not*
  Aspeed), whose stock firmware is **NET+OS** (a ThreadX RTOS), not Linux.
  Three firmware versions were obtained and reverse-engineered (Digi
  `bootHdr` format, LZSS2 decompression, NET+OS / RomPager internals,
  security assessment); a U-Boot port is being planned under `uboot-port/`.
  This board's open-firmware path is a U-Boot port, not OpenBMC/u-bmc.

The C410X device tree (`aspeed-bmc-dell-c410x.dts`) is based on
`aspeed-g4.dtsi` (AST2400) rather than a G3/AST2050 include, because the AST2050
is register-compatible enough and no upstream G3 binding exists yet.

## Per-board document map (read these first)

**`asus-kgpe-d16-firmware/`** (no STATUS.md — start with the summary):
- `RAPTOR_AST2050_SUMMARY.md` — quick-reference entry point.
- `RAPTOR-PORTING-GUIDE.md` — the actionable Raptor→mainline mapping (26 components).
- `RAPTOR_ENGINEERING_AST2050_ANALYSIS.md` — full detail behind the guide.
- `RAPTOR-UBOOT-ANALYSIS.md`, `DDR2-INIT-REVERSE-ENGINEERING.md`, `JTAG-HEADERS.md`
  — bootloader, DRAM bring-up, and debug-header low-level detail.
- `ast2050.h` / `hwreg.h` / `platform*.S` — register defs and init assembly.

**`dell-c410x-firmware/`**:
- `STATUS.md` — current state and open items. `RESOURCES.md` — firmware URLs/sources.
- `ANALYSIS.md` — full firmware reverse engineering (hardware, drivers, boot).
- `aspeed-bmc-dell-c410x.dts` — the reconstructed device tree (key output).
- `aspeed-mainline-drivers-analysis.md` / `aspeed-driver-quick-reference.md` —
  which mainline drivers cover which peripherals.
- `io-tables/README.md` — how the five binary config tables fit together
  (then the per-table `*.bin.md` and `gpio-pin-mapping.md`).
- `pex-i2c-analysis/README.md` → `PEX-I2C-COMMANDS.md` — the master reference for
  the PLX PEX switch I2C protocol; `analysis/` holds the supporting decompilation.

**`hpe-ipdu-firmware/`** (Digi NS9360, NET+OS RTOS — firmware obtained and analysed):
- `STATUS.md` — completed work and open items. `RESOURCES.md` — firmware/datasheet sources.
- `ANALYSIS.md` — board inventory, NS9360 I/O, and firmware internals.
- `HEADERS-J1-J6.md` — debug/JTAG headers.
- `uboot-port/` — the U-Boot port plans (`PLAN-INCREMENTAL-PORT.md` for a
  hardware-tested phased build, `PLAN-FULL-FEATURED-PORT.md` for a QEMU-first
  build, `REFERENCE-MATERIAL.md` for the hardware spec) plus vendored Digi
  NS9360 U-Boot source under `reference/`.
- `extract_firmware.py`, `decompress_firmware.py`, and the `analyse_*.py`
  scripts — stdlib-only Python (run with `uv run`) for the firmware RE.

## Python tooling: `uv run` + PEP 723

Always run Python with `uv` (never bare `python`/`pip`). Analysis and control
scripts use **PEP 723 inline script metadata** — a `# /// script` block at the
top declares dependencies — so each script is self-contained and run directly:

```sh
uv run dell-c410x-firmware/pex-i2c-analysis/tools/extract_fullfw.py
```

There is intentionally **no central `pyproject.toml` or `requirements.txt`** —
`uv run` resolves each script's declared deps on the fly. When writing a new
script that needs third-party packages, add a `# /// script` block rather than
expecting a project-wide environment.

## Common workflows

### Firmware extraction (regenerates gitignored binaries)
```sh
# C410X IO config tables: .zip -> SquashFS -> etc/default/ipmi/evb/*.bin
uv run dell-c410x-firmware/extract_firmware.py
# C410X main BMC ELF: c410xbmc135.zip -> SquashFS -> /sbin/fullfw
uv run dell-c410x-firmware/pex-i2c-analysis/tools/extract_fullfw.py
```
Vendor firmware archives in `dell-c410x-firmware/backup/*.{zip,exe}` **are
committed** (large but the irreplaceable source material). Everything derived
from them — `extracted/`, `analysis/fullfw`, the Ghidra project, build outputs —
is gitignored and must be regenerated, not committed.

### IO-table / device-tree analysis
```sh
uv run dell-c410x-firmware/parse_io_tables.py     # decode the binary config tables
uv run dell-c410x-firmware/cross_check_dts.py     # validate .dts against raw firmware
```

### Kernel + initramfs build (also runs in CI)
CI (`.github/workflows/build-bmc-firmware.yml`) cross-compiles a kernel for the
C410X: `CROSS_COMPILE=arm-linux-gnueabi-`, `make aspeed_g4_defconfig` merged with
`dell-c410x-firmware/kernel/c410x.config`, plus the AST2050 clock patch in
`kernel/patches/`, producing a legacy `uImage`. U-Boot is built only on manual
dispatch (`build-bmc-uboot.yml`). Locally:
```sh
uv run dell-c410x-firmware/initramfs/build.py     # BusyBox initramfs -> uInitrd-c410x
```

### Deploy / control real hardware
```sh
uv run dell-c410x-firmware/tftp_boot.py --kernel uImage-c410x --initrd uInitrd-c410x
uv run dell-c410x-firmware/pex-i2c-analysis/tools/c410x_control.py status   # also: power-on N, startup, multihost 4:1
```

## Ghidra decompilation via MCP

Firmware decompilation uses Ghidra through MCP servers configured in `.mcp.json`
(`ghidra-mcp`, `pyghidra-mcp`). Both — and the `playwright` server — need an X
display. Bring it up before launching Ghidra:
```sh
scripts/vnc-display.sh start            # X display :99
scripts/ghidra-vnc.sh [project-file]    # then enable GhidraMCPPlugin in the GUI
```
The C410X binary decompiles as `ARM:LE:32:v5t` (ARM926EJ-S), Ghidra 11.3.1.
`GHIDRA_INSTALL_DIR` is `/home/tim/tools/ghidra`.

## Working in this repo

- **Never work directly on `main`.** Before touching anything, create your own
  branch and an isolated git worktree to work in; `main` only ever advances
  through merges, never through commits made on it directly.
- **Commit small, logical units — frequently.** Each self-contained change
  (a script added, a function decoded, an analysis result) is its own commit.
  Don't batch unrelated work together or defer committing to the end; a steady
  stream of focused commits keeps history reviewable and easy to revert or
  cherry-pick.
- **Always merge with a real merge commit** (`git merge --no-ff`), never a
  fast-forward. Every branch's integration should remain a distinct, traceable
  point in the history.
- **Fail loud and fast.** Surface errors the moment they happen rather than
  swallowing them, catching-and-ignoring, or silently falling back to a
  default. No bare `except:`, no `2>/dev/null`, no pressing on past a failed
  command — a wrong or incomplete result must be visible, never hidden.

## Conventions specific to this repo

- **Dates**: ISO 8601 (`YYYY-MM-DD`) or day-first only — never month-first.
  Planning docs in `docs/plans/` are named `YYYY-MM-DD-<slug>.md`.
- **Temp files**: use the project-local `tmp/` (gitignored), never `/tmp/`.
- **stderr**: never redirect to `/dev/null`; diagnostic output must stay visible
  (a specific case of *fail loud and fast*, above).
- License is Apache 2.0.

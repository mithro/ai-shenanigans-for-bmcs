# U-Boot patches for the AST2050 P2A DRAM boot

`0001-ast2050-p2a-dram-boot.patch` — apply on top of Raptor Engineering's U-Boot
tree (board `asus` / `board/aspeed/ast2050`) to build a `u-boot.bin` that boots on
the real AST2050 BMC when loaded into DRAM over culvert P2A (no spispy, no JTAG).
See `../RAPTOR-UBOOT-BUILD.md` for the full build recipe and the reasoning behind
each hunk.

The patch touches four files:

- **`board/aspeed/ast2050/platform.S`** — `MCR04` DDR2 config `0x00000d89` →
  `0x00000585` (this KGPE-D16's DDR2 is 4-bank, 64 MB). Mostly moot at runtime
  because `lowlevel_init` skips DDR2 init when `SCU40[6]` is set (which our
  `ddr2-init-p2a.py` M1 step sets), but correct if it ever runs.
- **`include/configs/asus.h`** — real-HW config: console baud `1200`; init stack
  moved to `SDRAM_BASE + 16 MB` (stock `+0x1000` collides with the DRAM-loaded
  image); environment `= NOWHERE` (compiled-in default; the boot flash can't be
  read over P2A).
- **`board/aspeed/ast2050/flash_spi.c`** — the unknown-flash-ID (`0`) path returns
  a benign 1-sector geometry instead of leaving `sector_count` uninitialised
  (data-abort) or returning `0` (generic wrapper hang).
- **`tools/Makefile`** — the libfdt host-header clash fix (`-I $(SRCTREE)/include`
  + `-DLIBFDT_H`), only needed when building the host tools; the recipe uses
  `SUBDIR_TOOLS=` to skip them entirely.

> Note: the Raptor U-Boot source tree itself is not vendored in this repo (it lives
> under the gitignored `.worktrees/d16-qemu/tmp/raptor-uboot`); this patch records
> exactly the changes made so the real-HW binary is reproducible.

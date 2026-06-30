# C3 — Raptor AST2050 U-Boot + Linux on kgpe-d16-bmc

Goal (acceptance criterion C3): build **Raptor Engineering's** AST2050 firmware
from source and boot it on the custom `kgpe-d16-bmc` QEMU machine.

- U-Boot 2013.07 — <https://github.com/raptor-engineering/ast2050-uboot>
  (board target `asus` / `ast2050` in `boards.cfg`).
- Linux 2.6.28.9 — <https://github.com/raptor-engineering/ast2050-linux-kernel>
  (`arch/arm/mach-aspeed`, `plat-aspeed`).

## Status: vintage toolchain validated; full build + boot is open work

This is the hardest of C1–C3 because the code is from 2008–2013 and does not
build with a modern toolchain. Progress and the concrete obstacle chain:

### Toolchain
- **Modern `gcc-14` cannot build it.** U-Boot needs `compiler-gccN.h` shims and
  hits host `libfdt_env.h` conflicts; the kernel won't compile either.
- **Use a vintage gcc-4.x** from the kernel.org crosstool prebuilts:
  `https://mirrors.edge.kernel.org/pub/tools/crosstool/files/bin/x86_64/4.9.4/x86_64-gcc-4.9.4-nolibc-arm-linux-gnueabi.tar.xz`
  — validated: the kernel now compiles past the early stages.
- That gcc's `cc1` needs **`libmpfr.so.4`** (modern distros ship `.so.6`); symlink
  `libmpfr.so.4 -> libmpfr.so.6.x` and add it to `LD_LIBRARY_PATH`.

### Remaining build obstacles
- **Kernel SoC selection.** `mach/platform.h` has **no `AST1100` branch** — its
  `#if` chain is AST2000/2100/2200/2300/2400/2500/3200. The **AST2050's G3
  platform is `CONFIG_ARCH_AST2100`** (G3 generation), *not* `ARCH_AST1100`
  (which falls through to the `#else #err`). Derive a config from
  `ast2300_defconfig` and set `CONFIG_ARCH_AST2100=y`. (`ast2400_defconfig`
  fails earlier on `SCU_FUN_PIN_MAC1_PHY_LINK undeclared`; `ARCH_AST1100` hits
  the `#err`.)
- **`#err` typo.** `platform.h`'s else-branch uses `#err` (not `#error`); gcc-4.9
  rejects it as an invalid directive. With the correct `ARCH_AST2100` it is not
  reached; otherwise an era gcc-4.3/4.4 or a one-line patch is needed.
- **U-Boot host tools.** The 2013 host `libfdt` clashes with the modern system
  one; build with U-Boot's bundled libfdt or skip the host dtc.

- **Cascading G4-driver references.** Deriving from `ast2300_defconfig` and
  switching to `ARCH_AST2100` then fails in driver files that assume G4 symbols
  (e.g. `plat-aspeed/dev-nand.c` uses `AST_FMC_BASE`, defined only for
  AST2300/2400). A correct AST2050 build needs the **proper AST2050/G3 defconfig
  from Raptor's Yocto/OpenBMC layer** (which disables the G4-only drivers), not a
  hand-switched G4 defconfig — building it up by disabling drivers one-by-one is
  the whack-a-mole that makes this multi-day.

### Boot path that sidesteps device tree
The kernel need not boot via Raptor's (hard-to-build) U-Boot: the **already-built
OpenBMC U-Boot can boot the Raptor kernel via ATAGS** — `setenv machid <id>;
bootm <kernel> <initrd>` with **no dtb** makes U-Boot pass an ATAG list + machine
id instead of a device tree. The Raptor machine id is `MACH_TYPE_ASPEED`
(`MACHINE_START(ASPEED, ...)`), so once the kernel builds this is the route to a
boot — leaving only the G3-vs-G4 register-modelling gap below.

### The real crux: G3 vs G4 machine modelling
The Raptor kernel targets the **AST2050/AST2100 (G3)** register semantics, but
the `kgpe-d16-bmc` QEMU machine currently reuses the **AST2400 (G4)** peripheral
models (that is exactly why the *modern* aspeed-g4 kernel boots on it). The G3
and G4 SCU/clock/SDMC layouts differ in places, so booting the Raptor G3 kernel
will likely need the machine to model AST2050/G3 faithfully (a `qom_socname`
of its own + G3 device variants), not just borrow AST2400. **This — plus the
ATAGS-vs-DT boot path — is the bulk of C3's remaining work, and is what makes it
a multi-day task rather than a defconfig tweak.**

### The boot challenge (after it builds)
The 2.6.28.9 ARM kernel boots via **ATAGS + a fixed `MACH_TYPE`**, whereas QEMU's
aspeed machine is **device-tree** based. Booting the Raptor kernel on
`kgpe-d16-bmc` will likely require the machine to pass ATAGS and the matching
machine number (a small QEMU change), or to boot it through the Raptor U-Boot.

### Next steps
1. Select the correct AST2050 kernel SoC config; finish the kernel build.
2. Fix the U-Boot host-tool libfdt issue; finish the U-Boot build.
3. Make `kgpe-d16-bmc` boot an ATAGS kernel (or chain via Raptor U-Boot), then
   wire a `raptor-boot` CI job mirroring `boot-ssh`.

This is realistically several hours of focused work; the path above is proven as
far as "vintage gcc compiles the kernel".

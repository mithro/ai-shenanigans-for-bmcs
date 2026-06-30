# C3 — Raptor AST2050 U-Boot + Linux on kgpe-d16-bmc

Goal (acceptance criterion C3): build **Raptor Engineering's** AST2050 firmware
from source and boot it on the custom `kgpe-d16-bmc` QEMU machine.

- U-Boot 2013.07 — <https://github.com/raptor-engineering/ast2050-uboot>
  (board target `asus` / `ast2050` in `boards.cfg`).
- Linux 2.6.28.9 — <https://github.com/raptor-engineering/ast2050-linux-kernel>
  (`arch/arm/mach-aspeed`, `plat-aspeed`).

## Status: kernel BUILDS ✅ and ATAGS-launches ✅; early-boot hang is the G3/G4 crux ⏳

Reproducible scripts (this directory):

| Script | What it does | State |
|--------|--------------|-------|
| `scripts/build-raptor-kernel.sh` | vintage gcc-4.9.4 + G3 (`ARCH_AST2100`) config + G4 symbol port → `zImage` → `uImage-raptor` | **works** |
| `scripts/port-g4-symbols.py` | fills the G4-only `AST_*`/`IRQ_*` symbols the unconditionally-built `dev-*.c` files need (guarded `#ifndef`) | **works** |
| `scripts/mkflash-raptor.py` | assembles an 8 MB flash: OpenBMC U-Boot + ATAGS env + `uImage-raptor` + BusyBox `uInitrd` | **works** |

### ✅ Solved: the build (the historically hard part)
- **Modern `gcc-14` cannot build it** (needs `compiler-gccN.h` shims; host
  `libfdt_env.h` conflicts). Use the kernel.org crosstool prebuilt
  **gcc-4.9.4** (`x86_64-gcc-4.9.4-nolibc-arm-linux-gnueabi`); its `cc1` needs
  **`libmpfr.so.4`** (modern distros ship `.so.6`) → symlink it.
- **SoC selection:** the AST2050's G3 platform is **`CONFIG_ARCH_AST2100`**
  (the `#if` chain in `mach/platform.h` has *no* `AST1100` branch — `ARCH_AST1100`
  falls through to `#else #err`; `ARCH_AST2400` fails earlier on
  `SCU_FUN_PIN_MAC1_PHY_LINK`). Derive from `ast2300_defconfig`, set
  `CONFIG_ARCH_AST2100=y`.
- **Cascading G4-driver references:** `plat-aspeed/Makefile` builds every
  `dev-*.c` as `obj-y`; several reference G4-only symbols absent from the G3
  headers (`AST_FMC_BASE`, `AST_UHCI_BASE`, `IRQ_UART3`, …). `port-g4-symbols.py`
  back-fills all of them, each `#ifndef`-guarded so real G3 defines win and the
  devices (not probed during an initramfs boot) merely link. **Kernel now builds
  a 1.8 MB `zImage`.**

### ✅ Solved: the boot path (ATAGS, no device tree)
The kernel need not boot via Raptor's (hard-to-build) U-Boot. The
**already-built OpenBMC U-Boot boots the Raptor kernel via ATAGS**:

```
setenv machid 8888          # MACH_TYPE_ASPEED (arch/arm/tools/mach-types)
bootm <kernel> <initrd>      # only 2 args, NO dtb  -> U-Boot passes ATAGs + machid
```

Verified on `qemu-system-arm -M kgpe-d16-bmc`:

```
## Booting kernel from Legacy Image at 41000000 ...
   Image Name:   Raptor AST2050 Linux 2.6.28
   ...
   Loading Kernel Image ... OK
Using machid 0x8888 from environment
Starting kernel ...
```

So the kernel **receives control** with the correct machine id and an ATAG
list, reusing the same BusyBox+dropbear `uInitrd` as C2. This decouples "launch
a non-DT kernel" (**solved**) from "does the G4 model satisfy a G3 kernel"
(below).

### ⏳ The remaining crux: G3-vs-G4 register modelling
After `Starting kernel ...` the Raptor kernel produces **no console output and
hangs in early init** — even with `console=ttyS0/1/2/4` and `earlyprintk`. This
is *kernel-specific*, not a machine bug: the **modern aspeed-g4 kernel boots to
SSH on this exact machine** (C2 ✅), proving the UART/RAM/timer models work.

The `kgpe-d16-bmc` machine currently reuses the **AST2400 (G4)** peripheral
models (that is *why* the modern G4 kernel boots). The Raptor kernel targets
**AST2050/AST2100 (G3)** register semantics; G3 and G4 differ in the
**SCU / clock / SDMC** layout. The most likely wedge is an early **SCU clock/PLL
read** returning a G4-shaped value → bad divisor → silent hang before any
console. Closing this means teaching QEMU to model the **G3 SCU/clock (and
likely SDMC)** for this SoC — a `qom_socname` of its own plus G3 device
variants, not a borrowed AST2400. **This is the bulk of C3's remaining work and
is what makes it a multi-day, model-level task rather than a config tweak.**

Concrete next diagnostic: rebuild the kernel with `CONFIG_DEBUG_LL` +
`addruart` pinned to `0x1e784000` (the UART QEMU displays) to convert the silent
hang into an exact stop address, then model the offending G3 register in QEMU.

### Raptor U-Boot 2013.07 (secondary — not on the boot path)
Not required for the boot above (OpenBMC U-Boot does the ATAGS launch), but
needed to claim "Raptor's *own* U-Boot builds". Open obstacle: the 2013 host
`libfdt` clashes with the modern system one — build with U-Boot's bundled
libfdt or skip the host `dtc`.

## How to reproduce

```sh
# 1. Toolchain (once):
#    download kernel.org crosstool gcc-4.9.4-nolibc-arm-linux-gnueabi,
#    symlink libmpfr.so.4 -> your libmpfr.so.6 into $XLIBS.
# 2. Sources (once):
git clone https://github.com/raptor-engineering/ast2050-linux-kernel
# 3. Build kernel:
KDIR=$PWD/ast2050-linux-kernel XGCC=…/arm-linux-gnueabi- XLIBS=…/xlibs \
    ./scripts/build-raptor-kernel.sh
# 4. Assemble flash (reuses C2's OpenBMC u-boot.bin + uInitrd):
uv run scripts/mkflash-raptor.py --uboot …/u-boot.bin \
    --kernel out/uImage-raptor --initrd …/uInitrd-kgpe-d16 --out flash-raptor.img
# 5. Boot:
uv run ../scripts/run-qemu.py boot --flash flash-raptor.img \
    --expect "Linux version 2.6"   # <- currently blocked on the G3/G4 crux
```

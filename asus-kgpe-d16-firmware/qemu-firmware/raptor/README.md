# C3 — Raptor AST2050 U-Boot + Linux on kgpe-d16-bmc

Goal (acceptance criterion C3): build **Raptor Engineering's** AST2050 firmware
from source and boot it on the custom `kgpe-d16-bmc` QEMU machine.

- U-Boot 2013.07 — <https://github.com/raptor-engineering/ast2050-uboot>
  (board target `asus` / `ast2050` in `boards.cfg`).
- Linux 2.6.28.9 — <https://github.com/raptor-engineering/ast2050-linux-kernel>
  (`arch/arm/mach-aspeed`, `plat-aspeed`).

## Status: kernel BUILDS ✅, boots to userspace ✅; one piece left = a 2.6.28-compatible libc ⏳

The Raptor 2.6.28.9 kernel builds, ATAGS-launches, and **boots all the way
through to userspace `exec`** on the (AST2400/G4-modelled) `kgpe-d16-bmc`
machine — the earlier "G3-vs-G4 register-modelling crux" hypothesis is
**disproven**: the G4 peripheral models run the G3 kernel fine (SCU clock read
reports `CPU = 200 MHz, AHB = 100 MHz`, all drivers probe, TCP/IP comes up). The
only remaining blocker is the **C2 userspace's modern glibc**, which refuses to
run on a 2.6.28 kernel.

Reproducible scripts (this directory):

| Script | What it does | State |
|--------|--------------|-------|
| `scripts/build-raptor-kernel.sh` | vintage gcc-4.9.4 + G3 (`ARCH_AST2100`) + `ASUSPLATFORM` + `AEABI` config + G4 symbol port → `zImage` → `uImage-raptor` | **works** |
| `scripts/port-g4-symbols.py` | fills the G4-only `AST_*`/`IRQ_*` symbols the unconditionally-built `dev-*.c` files need (guarded `#ifndef`) | **works** |
| `scripts/qemu-safe-devices.py` | trims `init_all_device[]` to the peripherals QEMU models (drops NAND/PWM/PECI/… that abort on probe) | **works** |
| `scripts/mkinitramfs-raptor.py` | pure-Python newc cpio: repacks the C2 rootfs **with static `/dev` nodes** (2.6.28 has no devtmpfs) | **works** |
| `scripts/lower-abi-tag.py` | lowers a binary's `.note.ABI-tag` min-kernel (3.2.0 → 2.6.0) | partial (see below) |
| `scripts/mkflash-raptor.py` | assembles an 8 MB flash: OpenBMC U-Boot + ATAGS env (`machid=22b8`, `console=ttyS1`) + `uImage-raptor` + `uInitrd-raptor` | **works** |

### The full boot-bring-up chain (each step was a distinct, fixed blocker)
1. **`machid=22b8`, not `8888`.** `MACH_TYPE_ASPEED` is 8888 *decimal* = `0x22b8`;
   U-Boot parses `machid` as hex, so `8888` became `0x8888` →
   "unrecognized machine ID". Fixed in `mkflash-raptor.py`.
2. **`CONFIG_ASUSPLATFORM=y`.** The KGPE-D16 is ASUS ASMB4: this selects the
   console UART at `0x1e784000` (the one QEMU exposes) and the ASUS SCU init.
   Without it the kernel ran but printed to an invisible UART.
3. **`console=ttyS1`.** In the Raptor kernel `0x1e784000` registers as `ttyS1`
   (`ttyS0` = `0x1e783000`, not exposed). A bare `console=ttyS0` handed the
   console off to the invisible UART after `earlycon`.
4. **Device trim (`qemu-safe-devices.py`).** `ast_add_all_devices()` probed the
   NAND controller → external abort → panic. QEMU models no NAND; keep only
   uart/gmac/watchdog/rtc.
5. **Static `/dev` nodes + devtmpfs-tolerant `init`.** 2.6.28 predates devtmpfs
   (2.6.32); without `/dev/console` PID 1's `exec /bin/sh` got a closed stdin
   and exited ("Attempted to kill init!"). `mkinitramfs-raptor.py` bakes
   console/null/zero/urandom/ptmx/ttyS0-1 into the cpio.
6. **`CONFIG_AEABI=y` (+`OABI_COMPAT`).** The default G3 config is OABI; our
   EABI userspace needs an EABI/AEABI kernel. (Clean rebuild required.)
7. **glibc min-kernel — the last blocker.** Proven with a freestanding,
   no-libc EABI `/init`: it prints and runs, so the **kernel** execs EABI and
   its syscall path works. The C2 BusyBox/dropbear are **static modern glibc**
   built `--enable-kernel=3.2`, which both gates on `.note.ABI-tag` (3.2.0) and
   *omits pre-3.2 syscall fallbacks*. Lowering the note (`lower-abi-tag.py`)
   clears the gate but not the missing fallbacks, so glibc still dies on 2.6.28.
   **Fix: build the C3 userspace against musl** (static, no version gate,
   conservative syscalls) — a small BusyBox+dropbear rebuild with a musl cross
   toolchain, reusing everything above. This is the one remaining task.

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
setenv machid 22b8          # MACH_TYPE_ASPEED = 8888 dec = 0x22b8 (u-boot reads hex)
bootm <kernel> <initrd>      # only 2 args, NO dtb  -> U-Boot passes ATAGs + machid
```

Verified on `qemu-system-arm -M kgpe-d16-bmc` — boots clean through driver init:

```
Using machid 0x22b8 from environment
Starting kernel ...
Linux version 2.6.28.9 ...
CPU = 200 MHz ,AHB = 100 MHz (2:1)
Memory: 120MB ... ast_gmac_probe ... ast_rtc registered ... NET: protocol family 17
Freeing init memory: 104K          <- reaches userspace exec
```

### ⏳ The one remaining piece: a 2.6.28-compatible libc (musl)
The kernel runs the G4 peripheral models fine — *no* G3/G4 modelling work is
needed. The only failure is the **C2 userspace's modern glibc** (built
`--enable-kernel=3.2`) aborting on the 2.6.28 kernel; see the numbered chain
above (step 7) and `lower-abi-tag.py`. Rebuild BusyBox + dropbear static against
**musl** and repack with `mkinitramfs-raptor.py`; everything else is done.

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
# 4. Trim devices QEMU doesn't model + repack the rootfs with static /dev nodes:
uv run scripts/qemu-safe-devices.py --kdir $PWD/ast2050-linux-kernel   # then rebuild kernel
uv run scripts/mkinitramfs-raptor.py --rootfs …/initramfs/build/rootfs \
    --init …/initramfs/init --out out/uInitrd-raptor
# 5. Assemble flash (reuses C2's OpenBMC u-boot.bin):
uv run scripts/mkflash-raptor.py --uboot …/u-boot.bin \
    --kernel out/uImage-raptor --initrd out/uInitrd-raptor --out flash-raptor.img
# 6. Boot — reaches userspace; a real shell awaits the musl userspace rebuild:
uv run ../scripts/run-qemu.py boot --flash flash-raptor.img --expect "Linux version 2.6"
```

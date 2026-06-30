#!/bin/sh
# Build Raptor Engineering's AST2050 Linux 2.6.28.9 kernel from source (C3).
#
# The 2008-era kernel does NOT build with a modern gcc-14: it needs a vintage
# gcc-4.x. We use the kernel.org crosstool prebuilt gcc-4.9.4, whose cc1 in turn
# needs libmpfr.so.4 (modern distros ship .so.6) — so we symlink it.
#
# Required layout (override via env):
#   KDIR  - Raptor kernel checkout (git clone ast2050-linux-kernel)
#   XGCC  - cross toolchain prefix (…/bin/arm-linux-gnueabi-)
#   XLIBS - dir holding libmpfr.so.4 -> libmpfr.so.6 symlink
# Output: $KDIR/arch/arm/boot/zImage  and  $OUT/uImage-raptor (load 0x40008000)
set -e

here=$(cd "$(dirname "$0")" && pwd)
: "${KDIR:?set KDIR to the ast2050-linux-kernel checkout}"
: "${XGCC:?set XGCC to the gcc-4.9.4 arm-linux-gnueabi- prefix}"
: "${OUT:=$here/../out}"
mkdir -p "$OUT"

[ -n "$XLIBS" ] && export LD_LIBRARY_PATH="$XLIBS:$LD_LIBRARY_PATH"

# 1. AST2050 == G3 platform == CONFIG_ARCH_AST2100 (mach/platform.h has no
#    AST1100 branch; ARCH_AST2100 is the G3 generation that covers AST2050).
make -C "$KDIR" ARCH=arm CROSS_COMPILE="$XGCC" ast2300_defconfig
sed -i 's/^CONFIG_ARCH_AST2300=y/# CONFIG_ARCH_AST2300 is not set\nCONFIG_ARCH_AST2100=y/' \
    "$KDIR/.config"
# Board + ABI config for the kgpe-d16-bmc QEMU boot:
#   ASUSPLATFORM  -> console UART 0x1e784000 (the one QEMU exposes) + ASUS SCU
#   AEABI/OABI_COMPAT -> run our modern EABI userspace
#   DEBUG_LL/EARLY_PRINTK -> early-boot diagnostics on the visible UART
{
  echo "CONFIG_ASUSPLATFORM=y"
  echo "CONFIG_AEABI=y"
  echo "CONFIG_OABI_COMPAT=y"
  echo "CONFIG_DEBUG_KERNEL=y"
  echo "CONFIG_DEBUG_LL=y"
  echo "CONFIG_EARLY_PRINTK=y"
} >> "$KDIR/.config"
yes "" | make -C "$KDIR" ARCH=arm CROSS_COMPILE="$XGCC" oldconfig

# 2. Fill in the G4-only symbols the unconditionally-built dev-*.c files need,
#    and trim the device table to peripherals the QEMU machine models (NAND/PWM/
#    PECI/… abort on probe otherwise).
uv run "$here/port-g4-symbols.py" --kdir "$KDIR"
uv run "$here/qemu-safe-devices.py" --kdir "$KDIR"

# 3. Build. AEABI changes the syscall ABI, so build from clean to avoid stale
#    OABI objects.
make -C "$KDIR" ARCH=arm CROSS_COMPILE="$XGCC" clean
make -C "$KDIR" ARCH=arm CROSS_COMPILE="$XGCC" -j"$(nproc)" zImage

# 4. Wrap as a U-Boot legacy uImage. ATAGS boot from OpenBMC U-Boot:
#       setenv machid 8888; bootm <kernel> <initrd>     (no dtb)
#    MACH_TYPE_ASPEED = 8888 (arch/arm/tools/mach-types).
mkimage -A arm -O linux -T kernel -C none -a 0x40008000 -e 0x40008000 \
    -n "Raptor AST2050 Linux 2.6.28" \
    -d "$KDIR/arch/arm/boot/zImage" "$OUT/uImage-raptor"
echo "RAPTOR_KERNEL_BUILD_DONE: $OUT/uImage-raptor"
ls -la "$KDIR/arch/arm/boot/zImage" "$OUT/uImage-raptor"

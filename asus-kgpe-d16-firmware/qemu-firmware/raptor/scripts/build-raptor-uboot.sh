#!/bin/sh
# Build Raptor Engineering's *G3-aware* AST2050 U-Boot (2013.07) from source and
# assemble a boot flash for the kgpe-d16-bmc (AST2050) QEMU machine (C-UBOOT).
#
# This is the genuinely AST2050-native bootloader: its board/aspeed/ast2050/
# platform.S lowlevel_init runs the REAL AST2050 SCU unlock + M-PLL + DDR2
# controller bring-up. Booted with the faithful G3 SCU reset table
# (`-global driver=aspeed.scu-ast2050,property=g3-resets,value=on`), SCU40[6]
# (DRAM-ready) resets to 0, so lowlevel_init actually RUNS its DDR2 init against
# our faithful SCU + SDMC models -- a third firmware oracle beside C2 (our
# kernel->SSH) and C4 (Dell vendor->web), validating the G3 SCU model that
# unblocked the four SCU-reset-table faithfulness checks. See
# ../../qemu-model/peripherals/scu/DOC.md §4 and RAPTOR-UBOOT-BUILD.md.
#
# The 2013.07 U-Boot needs the vintage gcc-4.9.4 cross toolchain (same one the
# 2.6.28 kernel uses); its cc1 needs libmpfr.so.4 (modern distros ship .so.6) --
# symlinked here. Only two source edits are needed for the QEMU boot
# (patches/0001-ast2050-uboot-qemu-boot.patch): the tools/ libfdt host-header
# clash fix, and CONFIG_ENV_IS_NOWHERE (use the compiled-in default env instead
# of the SPI-flash env -- also drops the un-buildable host-tool CRC chain).
#
# Output: $OUT/u-boot-raptor.bin and $OUT/flash-raptor-uboot.img (16 MB, U-Boot
# at flash offset 0 == the machine's SPI-boot window at 0x0).
set -e

here=$(cd "$(dirname "$0")" && pwd)
qf="$here/../.."                       # qemu-firmware/
: "${TOOLS:=$qf/raptor/tools}"
: "${OUT:=$qf/raptor/out}"
: "${UDIR:=$TOOLS/raptor-uboot}"
: "${UBOOT_URL:=https://github.com/raptor-engineering/ast2050-uboot}"
: "${GCC_URL:=https://mirrors.edge.kernel.org/pub/tools/crosstool/files/bin/x86_64/4.9.4/x86_64-gcc-4.9.4-nolibc-arm-linux-gnueabi.tar.xz}"
mkdir -p "$TOOLS" "$OUT"

# Vintage gcc-4.9.4 (shared with build-raptor-kernel.sh).
xgcc_dir="$TOOLS/gcc-4.9.4-nolibc/arm-linux-gnueabi/bin"
if [ ! -x "$xgcc_dir/arm-linux-gnueabi-gcc" ]; then
    echo "fetching vintage gcc-4.9.4: $GCC_URL"
    wget -q -O "$TOOLS/gcc494.tar.xz" "$GCC_URL"
    tar xf "$TOOLS/gcc494.tar.xz" -C "$TOOLS"
    rm -f "$TOOLS/gcc494.tar.xz"
fi
: "${XGCC:=$xgcc_dir/arm-linux-gnueabi-}"

# That gcc's cc1 needs libmpfr.so.4; modern distros ship .so.6 -- symlink it.
: "${XLIBS:=$TOOLS/xlibs}"
mkdir -p "$XLIBS"
if [ ! -e "$XLIBS/libmpfr.so.4" ]; then
    mpfr6=$(find /usr/lib /lib -name 'libmpfr.so.6*' -type f | head -1)
    [ -n "$mpfr6" ] && ln -sf "$mpfr6" "$XLIBS/libmpfr.so.4"
fi
export LD_LIBRARY_PATH="$XLIBS:$LD_LIBRARY_PATH"

# Raptor U-Boot source.
if [ ! -d "$UDIR" ]; then
    echo "cloning Raptor U-Boot: $UBOOT_URL"
    git clone --depth 1 "$UBOOT_URL" "$UDIR"
fi

# QEMU-boot delta (idempotent: skip if already applied).
if ! grep -q "QEMU kgpe-d16-bmc boot overrides" "$UDIR/include/configs/asus.h"; then
    echo "applying patches/0001-ast2050-uboot-qemu-boot.patch"
    git -C "$UDIR" apply "$qf/raptor/patches/0001-ast2050-uboot-qemu-boot.patch"
fi

# Build u-boot.bin only (SUBDIR_TOOLS= drops the host-tool build dependency; the
# CONFIG_ENV_IS_NOWHERE patch removes the envcrc chain the tools would need).
make -C "$UDIR" ARCH=arm CROSS_COMPILE="$XGCC" distclean
make -C "$UDIR" ARCH=arm CROSS_COMPILE="$XGCC" asus_config
make -C "$UDIR" ARCH=arm CROSS_COMPILE="$XGCC" SUBDIR_TOOLS= -j"$(nproc)" u-boot.bin

cp "$UDIR/u-boot.bin" "$OUT/u-boot-raptor.bin"

# Assemble the 16 MB boot flash: u-boot.bin at offset 0 (== the machine's
# SPI-boot window mapped at 0x0). No kernel image is staged -- the boot exercises
# lowlevel_init + relocation + the interactive prompt; bootcmd fails past that,
# which drops to `boot#` (the C-UBOOT success sentinel).
cp "$OUT/u-boot-raptor.bin" "$OUT/flash-raptor-uboot.img"
truncate -s 16M "$OUT/flash-raptor-uboot.img"

echo "RAPTOR_UBOOT_BUILD_DONE:"
ls -la "$OUT/u-boot-raptor.bin" "$OUT/flash-raptor-uboot.img"

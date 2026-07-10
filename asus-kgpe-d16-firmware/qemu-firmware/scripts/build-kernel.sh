#!/bin/sh
# Build the D16 BMC Linux kernel (zImage + uImage + dtb) from mainline stable,
# with the AST2050 clock patch and the kgpe-d16 device tree. Used by CI and for
# local boots on the kgpe-d16-bmc QEMU machine.
#
# Usage: build-kernel.sh [OUT_DIR]   (env: KERNEL_VERSION, default v6.6.70)
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT="$HERE/.."                       # asus-kgpe-d16-firmware/qemu-firmware
KVER="${KERNEL_VERSION:-v6.6.70}"
SRC="$ROOT/kernel/linux"
OUT="${1:-$ROOT/kernel/out}"

export ARCH=arm
export CROSS_COMPILE=arm-linux-gnueabi-

if [ ! -d "$SRC" ]; then
    git clone --depth 1 --branch "$KVER" \
        https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git "$SRC"
fi
cd "$SRC"

# AST2050 clock support (idempotent guard).
if ! grep -q ast2050 drivers/clk/clk-aspeed.c; then
    git apply "$ROOT/kernel/patches/0001-clk-aspeed-add-ast2050-support.patch"
fi

# Device tree.
cp "$ROOT/dts/aspeed-bmc-asus-kgpe-d16.dts" arch/arm/boot/dts/aspeed/
if ! grep -q kgpe-d16 arch/arm/boot/dts/aspeed/Makefile; then
    echo 'dtb-$(CONFIG_ARCH_ASPEED) += aspeed-bmc-asus-kgpe-d16.dtb' \
        >> arch/arm/boot/dts/aspeed/Makefile
fi

# Config: aspeed_g4_defconfig + D16 fragment.
make aspeed_g4_defconfig
scripts/kconfig/merge_config.sh -m .config "$ROOT/kernel/kgpe-d16.config"
make olddefconfig

# Build.
make -j"$(nproc)" zImage dtbs
make -j"$(nproc)" LOADADDR=0x40008000 uImage

mkdir -p "$OUT"
cp arch/arm/boot/zImage "$OUT/zImage-kgpe-d16"
cp arch/arm/boot/uImage "$OUT/uImage-kgpe-d16"
cp arch/arm/boot/dts/aspeed/aspeed-bmc-asus-kgpe-d16.dtb "$OUT/"
echo "Kernel artifacts in $OUT:"
ls -la "$OUT"

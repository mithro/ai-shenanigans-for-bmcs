#!/bin/sh
# Build the new D16 BMC U-Boot from source. We use the OpenBMC U-Boot
# (v2019.04, AST2400 EVB) — it builds with the modern cross toolchain (unlike
# Raptor's 2013.07 U-Boot, which needs a vintage gcc) and runs on the
# register-compatible kgpe-d16-bmc (AST2050) machine.
#
# Usage: build-uboot.sh [OUT_DIR]
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT="$HERE/.."                       # asus-kgpe-d16-firmware/qemu-firmware
SRC="$ROOT/uboot/u-boot"
OUT="${1:-$ROOT/uboot/out}"

export ARCH=arm
export CROSS_COMPILE=arm-linux-gnueabi-

if [ ! -d "$SRC" ]; then
    git clone --depth 1 --branch v2019.04-aspeed-openbmc \
        https://github.com/openbmc/u-boot.git "$SRC"
fi
cd "$SRC"

# Apply the KGPE-D16 (AST2050) U-Boot patches idempotently: only ones that still
# apply cleanly to this tree (a patch already present, or written for a different
# tree, is skipped with a visible note — NOT silenced to /dev/null).
PATCHDIR="$ROOT/../uboot-patches"
for p in "$PATCHDIR"/*.patch; do
    [ -e "$p" ] || continue
    if git apply --check "$p"; then
        git apply "$p"
        echo "applied $(basename "$p")"
    else
        echo "skip $(basename "$p") (already applied or not for this tree)"
    fi
done

make evb-ast2400_defconfig
make -j"$(nproc)"

mkdir -p "$OUT"
cp u-boot.bin "$OUT/"
echo "u-boot.bin -> $OUT/u-boot.bin"

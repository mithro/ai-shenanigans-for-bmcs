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

# Apply the KGPE-D16 (AST2050) U-Boot patches. FAIL LOUD (repo rule): a patch that
# is meant for this tree but no longer applies must ABORT the build, never be
# silently skipped shipping a broken u-boot.bin. We distinguish three cases:
#   1. applies forward            -> apply it
#   2. already applied (reverses) -> skip quietly (idempotent re-run)
#   3. neither                    -> if its target file is ABSENT it is for a
#      different tree (e.g. 0001 targets the Raptor board/aspeed/ast2050) -> skip
#      with a note; otherwise it is a GENUINE failure -> abort.
PATCHDIR="$ROOT/../uboot-patches"
for p in "$PATCHDIR"/*.patch; do
    [ -e "$p" ] || continue
    name=$(basename "$p")
    if git apply --check "$p"; then
        git apply "$p"
        echo "applied $name"
    elif git apply --reverse --check "$p"; then
        echo "already applied (skip): $name"
    else
        tgt=$(sed -n 's|^+++ b/||p' "$p" | head -1)
        if [ -n "$tgt" ] && [ ! -e "$tgt" ]; then
            echo "not for this tree (target '$tgt' absent), skip: $name"
        else
            echo "ERROR: $name neither applies nor is already applied, and its target '$tgt' exists — aborting (fail loud)" >&2
            exit 1
        fi
    fi
done

make evb-ast2400_defconfig
make -j"$(nproc)"

mkdir -p "$OUT"
cp u-boot.bin "$OUT/"
echo "u-boot.bin -> $OUT/u-boot.bin"

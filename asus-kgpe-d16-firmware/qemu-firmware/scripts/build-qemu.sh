#!/bin/sh
# Build qemu-system-arm (with the custom kgpe-d16-bmc / AST2050 machine) from
# the vendored QEMU submodule. Used by CI and for local rebuilds.
#
# Usage: build-qemu.sh [BUILD_DIR]
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT="$HERE/.."                       # asus-kgpe-d16-firmware/qemu-firmware
SRC="$ROOT/qemu/qemu"                 # the submodule
BUILD="${1:-$ROOT/qemu/build}"

if [ ! -f "$SRC/configure" ]; then
    echo "ERROR: QEMU submodule not initialised at $SRC" >&2
    echo "Run: git submodule update --init $SRC" >&2
    exit 1
fi

mkdir -p "$BUILD"
cd "$BUILD"
if [ ! -f build.ninja ]; then
    "$SRC/configure" --target-list=arm-softmmu --disable-docs --disable-werror
fi
make -j"$(nproc)" qemu-system-arm

echo "Built: $BUILD/qemu-system-arm"
# Fail loudly if the custom machine is not registered.
"$BUILD/qemu-system-arm" -M help | grep -q 'kgpe-d16-bmc'
echo "OK: -M kgpe-d16-bmc is registered"

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

# AST2050 ftgmac100 RMII RX bring-up: reset the RMII PHY for the G3 so the MAC
# RX engine actually pulls frames off the wire (without this, eth0 TX works but
# RX=0 on the real AST2050 / the faithful QEMU model). Idempotent guard.
if ! grep -q is_ast2050 drivers/net/ethernet/faraday/ftgmac100.c; then
    git apply "$ROOT/kernel/patches/0002-ftgmac100-ast2050-rmii-rx.patch"
fi

# Device tree.
cp "$ROOT/dts/aspeed-bmc-asus-kgpe-d16.dts" arch/arm/boot/dts/aspeed/
if ! grep -q kgpe-d16 arch/arm/boot/dts/aspeed/Makefile; then
    echo 'dtb-$(CONFIG_ARCH_ASPEED) += aspeed-bmc-asus-kgpe-d16.dtb' \
        >> arch/arm/boot/dts/aspeed/Makefile
fi

# AST2050 (G3) compact VIC irqchip driver. The mainline irq-aspeed-vic only
# handles the AST2400/2500 two-bank layout and assumes hardwired trigger config;
# the G3 is single-bank and firmware must program SENSE/DUAL/EVENT. See
# kernel/drivers/irq-aspeed-g3-vic.c and qemu-model/peripherals/vic. Wired again
# now that the faithful G3 VIC (TYPE_ASPEED_2050_VIC) + one-pulse-per-expiry timer
# boot the C410X vendor firmware (C4 oracle) as well as our own kernel.
cp "$ROOT/kernel/drivers/irq-aspeed-g3-vic.c" drivers/irqchip/
if ! grep -q irq-aspeed-g3-vic drivers/irqchip/Makefile; then
    echo 'obj-$(CONFIG_ARCH_ASPEED) += irq-aspeed-g3-vic.o' \
        >> drivers/irqchip/Makefile
fi

# Config: aspeed_g4_defconfig + D16 fragment + NFS-root fragment.
# The NFS-root fragment (IP_PNP/DHCP + NFS client + ROOT_NFS + devtmpfs auto-
# mount) is dormant for the initramfs boots (C2/C3 carry no ip=/root=/dev/nfs on
# the cmdline) and enables the Phase-6 boot-nfsroot path from the same kernel.
make aspeed_g4_defconfig
scripts/kconfig/merge_config.sh -m .config \
    "$ROOT/kernel/kgpe-d16.config" "$ROOT/kernel/kgpe-d16-nfsroot.config"
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

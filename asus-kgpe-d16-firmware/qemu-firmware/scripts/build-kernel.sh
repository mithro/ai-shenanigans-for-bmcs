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

# AST2050 ftgmac100 speed-mode fix: ftgmac100_start_hw() must re-derive the MAC
# speed bits (FAST_MODE/GIGA_MODE) from priv->cur_speed rather than only
# preserving them. On the G3 a MAC SW_RST clears MACCR (speed bit included), so
# preserve-only leaves the MAC in 10M timing on a 100M link -> every RX frame is
# mangled -> rx=0 (HW-verified: setting MACCR bit19 FAST_MODE restored RX).
# Idempotent guard on a unique string from the patched comment.
if ! grep -q "Set the speed mode from the current link speed" \
        drivers/net/ethernet/faraday/ftgmac100.c; then
    git apply "$ROOT/kernel/patches/0002-ftgmac100-set-mac-speed-from-cur_speed-g3.patch"
fi

# W83795G hardware-monitor modern-hwmon registration (F3 sensors): the mainline
# drivers/hwmon/w83795.c uses the legacy hwmon_device_register(), which puts the
# sensor attributes on the i2c client device and leaves /sys/class/hwmon/hwmonN
# nameless and without *_input files -- so OpenBMC phosphor-hwmon (which reads
# hwmonN/<type>N_input and hwmonN/name directly) can't see the chip. Convert it to
# hwmon_device_register_with_info() exposing the input channels. Idempotent guard
# on a symbol the patch adds.
if ! grep -q "w83795_hwmon_read" drivers/hwmon/w83795.c; then
    git apply "$ROOT/kernel/patches/0003-hwmon-w83795-modern-hwmon-registration.patch"
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
# kgpe-d16-usb.config + kgpe-d16-kvm.config MUST come last: they re-enable USB
# (kgpe-d16.config sets CONFIG_USB_SUPPORT=n) for the AST2050 USB2.0 device/vhub
# gadget path (F6) and add the V4L2 + aspeed-video KVM screen-capture stack and the
# host-side HID/input layers (F8). See F6-USB.md and F8-KVM.md.
scripts/kconfig/merge_config.sh -m .config \
    "$ROOT/kernel/kgpe-d16.config" "$ROOT/kernel/kgpe-d16-nfsroot.config" \
    "$ROOT/kernel/kgpe-d16-usb.config" "$ROOT/kernel/kgpe-d16-kvm.config"
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

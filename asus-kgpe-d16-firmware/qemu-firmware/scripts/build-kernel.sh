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

# AST2050 ftgmac100 MACCLK: leave the MAC clock at the U-Boot default instead of
# forcing 100MHz via clk_set_rate() (independent of the speed-mode fix above --
# different function, ftgmac100_setup_clk). From main's hardware-verified series
# (asus-kgpe-d16-firmware/kernel/patches, PR #22/#26): correct G3 behaviour --
# U-Boot's AST2050 path never sets MACCLK -- and harmless on QEMU.
# Idempotent guard on a unique string from the patched comment.
if ! grep -q "leaving MACCLK at the U-Boot default" \
        drivers/net/ethernet/faraday/ftgmac100.c; then
    git apply "$ROOT/../kernel/patches/0002-ftgmac100-ast2050-macclk.patch"
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

# KCS holds the LPC clock (G3 SCU0C[8] LCLK is a real gate and the kcs@2c node
# is the only enabled LPC consumer on the KGPE-D16) -- without this,
# clk_disable_unused() kills the host-facing LPC block on real silicon (the
# latent sibling of finding #94; see G3-CLK-PROGRESS.md). Optional clock, so
# other DTs are unaffected. Idempotent guard on the include the patch adds.
if ! grep -q "linux/clk.h" drivers/char/ipmi/kcs_bmc_aspeed.c; then
    git apply "$ROOT/kernel/patches/0004-ipmi-kcs-bmc-aspeed-optional-lpc-clock.patch"
fi

# I2CD04 resets to X (undefined) on the G3: program tBUF/tHDSTA/tACST like the
# vendor driver instead of preserving power-up garbage (hardening for the G3
# I2C bring-up, finding #93). Idempotent guard on the FIELD_PREP the patch adds.
if ! grep -q "ASPEED_I2CD_TIME_TBUF_MASK, 0x7" drivers/i2c/busses/i2c-aspeed.c; then
    git apply "$ROOT/kernel/patches/0005-i2c-aspeed-program-full-ac-timing.patch"
fi

# AST2050 (G3) video-engine JPEG compression: mainline aspeed-video gets the G3
# through mode-detect + capture but the compressor hangs (HW-verified on silicon:
# VR004[18] COMP_BUSY stuck, VR308[3] COMP_COMPLETE never fires, VR078 size=0).
# From the AST2050 datasheet §20 + the working AMI "videocap" G3 driver: mainline
# selects JPEG mode via VR004[8] (reserved-must-be-0 on the G3) and never sets the
# G3's real pure-JPEG select VR060[0]; and it programs the DCT quant-table index
# from the 0-11 quality range, but the G3 has only 8 INTERNAL ROM tables (0-7) --
# index >=8 wedges the compressor. Adds an "aspeed,ast2050-video-engine" compatible
# (jpeg_mode=0, jpeg_only) that sets VR060[0], clamps the DCT selector to 0-7, and
# clears the G4-only HQ fields + AUTO_COMP. Idempotent guard on jpeg_only.
if ! grep -q "jpeg_only" drivers/media/platform/aspeed/aspeed-video.c; then
    git apply "$ROOT/kernel/patches/0006-media-aspeed-video-ast2050-g3-jpeg.patch"
fi

# AST2050 (G3) USB2.0 vhub UDC: the mainline aspeed-vhub (ast2400-targeted) HANGS
# the SoC when it probes the real G3 vhub -- confirmed on silicon (enabling the
# usb-vhub@1e6a0000 node -> no console/network; a clean A/B whose only variable is
# the node). Register offsets are identical G3<->G4, but two semantics differ:
# CTRL[31] PHY-clock is READ-ONLY on the G3 (mirrors SCU0C[14], so the driver's
# write is a no-op), and ISR[18] "USB command bus dead-lock" is a fatal,
# level-triggered IRQ the handler never acts on -> asserting UPSTREAM_CONNECT into
# a not-ready PHY livelocks the CPU. Adds a bounded PHY-clock-ready wait before
# connect + a de-livelock branch that drops UPSTREAM_CONNECT on ISR[18], plus an
# explicit "aspeed,ast2050-usb-vhub" compatible. Datasheet §15 p.154-178; see
# openbmc/bmc-functionality/VHUB-G3-PORT-PLAN.md. Idempotent guard on a patch string.
if ! grep -q "USB command bus dead-lock" drivers/usb/gadget/udc/aspeed-vhub/core.c; then
    git apply "$ROOT/kernel/patches/0007-usb-aspeed-vhub-ast2050-g3.patch"
fi

# AST2050 (G3) pinctrl strap-phantom quirk: the G3's SCU70 strap layout differs
# entirely from the AST2400's (G3 bit19 = "bypass all PLL", not the ACPI mux
# select), so G4-table signal expressions gated purely on HW_STRAP1/2 can read
# "active" from unrelated G3 strap bits and can never be deconfigured -> GPIO
# requests fail -EPERM. Hit on real silicon (SCU70=0x00819582, bit19=0 -> the
# driver refused GPIOF5 = the QU5 I2C-mux select, killing the /i2cmux probe)
# and reproduced byte-identically in QEMU once the machine carried the measured
# strap. New compatible aspeed,ast2050-pinctrl skips strap-only expressions on
# the DISABLE path only (enable-path strap evaluation unchanged -- the MAC's
# RMII pinmux depends on it). Idempotent guard on the flag the patch adds.
if ! grep -q "g3_strap_phantoms" drivers/pinctrl/aspeed/pinmux-aspeed.h; then
    git apply "$ROOT/kernel/patches/0008-pinctrl-aspeed-g3-strap-phantom-quirk.patch"
fi

# 0009: the AST2050 (G3) RTC at 0x1E781000 is COUNTER-style (datasheet §24:
# COUNTER/RELOAD/CONTROL/RESTART), register-incompatible with the mainline
# aspeed-rtc ast2400-rtc (BCD: TIME/YEAR/CTRL@0x10) that the g4.dtsi base binds --
# so Linux got NO working /dev/rtc0 (empirically confirmed). This adds an
# "aspeed,ast2050-rtc" counter-style variant to rtc-aspeed (the board dts re-points
# the node at it). Idempotent guard on the new compatible the patch adds. #187.
if ! grep -q "aspeed,ast2050-rtc" drivers/rtc/rtc-aspeed.c; then
    git apply "$ROOT/kernel/patches/0009-rtc-aspeed-ast2050-counter.patch"
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
    "$ROOT/kernel/kgpe-d16-usb.config" "$ROOT/kernel/kgpe-d16-usbip.config" \
    "$ROOT/kernel/kgpe-d16-kvm.config" \
    "$ROOT/kernel/kgpe-d16-swap.config" "$ROOT/kernel/kgpe-d16-video-cma.config"
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

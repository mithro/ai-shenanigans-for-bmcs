#!/bin/bash
# Phase 6b: stage a built ARMv5 OpenBMC phosphor rootfs into a local NFS export so
# the faithful kgpe-d16-bmc QEMU machine can NFS-root-boot real OpenBMC
# (bmcweb/Redfish), exactly as Phase 6a proved with BusyBox.
#
# The OpenBMC image MUST be ARMv5 (ARM926EJ-S = the AST2050 CPU): build for the
# quanta-q71l or palmetto machine (both ast2400/armv5e). The AST2500 'romulus'
# image is ARMv6 and faults on the ARM926 the faithful machine emulates.
#
# Usage: stage-openbmc-nfsroot.sh <image.squashfs-xz> [EXPORT_DIR]
#   EXPORT_DIR default /export/openbmc-kgpe-d16
#
# Requires: unsquashfs, sudo (to own files as root + configure the NFS export).
# NOTE: no `set -u` beyond our own vars; we do want -e to fail loud.
set -e

IMG="${1:?usage: stage-openbmc-nfsroot.sh <image.squashfs-xz> [EXPORT_DIR]}"
EXPORT_DIR="${2:-/export/openbmc-kgpe-d16}"

[ -f "$IMG" ] || { echo "OpenBMC rootfs image not found: $IMG"; exit 1; }

echo "[1] unsquashfs $IMG -> $EXPORT_DIR (as root, preserving perms/owners)"
sudo rm -rf "$EXPORT_DIR"
sudo mkdir -p "$EXPORT_DIR"
sudo unsquashfs -f -d "$EXPORT_DIR" "$IMG"

echo "[2] NFS-root adaptations: the root is a writable NFS mount, so OpenBMC's"
echo "    read-only rofs + rwfs overlay-on-MTD units must be neutralised or they"
echo "    fail early and block boot (there is no MTD flash on this boot path)."
# Overlay/flash units that assume the squashfs-on-MTD + UBI rwfs layout.
NEUTRALISE="
obmc-flash-bmc-rofs.service
obmc-flash-bmc-rwfs.service
obmc-flash-bmc-static-rofs.service
obmc-flash-bmc-rofs-reset.service
"
for u in $NEUTRALISE; do
    # mask by symlinking to /dev/null in the highest-priority unit dir
    sudo ln -sf /dev/null "$EXPORT_DIR/etc/systemd/system/$u"
done
# Some images gate multi-user on a '*-mtd.mount' / 'mnt-*.mount'; mask any mount
# unit whose What= is an mtdblock device (they can't exist on the NFS root).
if [ -d "$EXPORT_DIR/lib/systemd/system" ]; then
    for m in $(grep -rlE 'What=/dev/mtdblock|What=/dev/ubi' \
                 "$EXPORT_DIR/lib/systemd/system" 2>/dev/null || true); do
        b=$(basename "$m")
        echo "    masking mtd/ubi mount unit: $b"
        sudo ln -sf /dev/null "$EXPORT_DIR/etc/systemd/system/$b"
    done
fi

echo "[3] root fs is provided by the kernel (root=/dev/nfs); keep tmpfs volatiles."
echo "    staged OpenBMC rootfs at $EXPORT_DIR:"
sudo ls "$EXPORT_DIR"
echo "    bmcweb present: $([ -x "$EXPORT_DIR/usr/bin/bmcweb" ] && echo yes || echo NO)"
echo "    rootfs arch: $(sudo readelf -A "$EXPORT_DIR/usr/bin/bmcweb" 2>/dev/null | grep -i 'Tag_CPU_arch:' | head -1 || echo '?')"
echo "[done] now boot with scripts/openbmc-nfsroot-test.py --nfsroot 10.0.2.2:$EXPORT_DIR"

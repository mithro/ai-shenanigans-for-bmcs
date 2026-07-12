#!/bin/sh
# Stage the built palmetto (ARMv5) OpenBMC rootfs onto the Pi's NFS export so the real
# AST2050 can NFS-root-boot it. Run AFTER `bitbake obmc-phosphor-image` for palmetto.
# The rootfs is ARM926/ARMv5TE (matches the AST2050 CPU); the romulus build is ARMv6 and
# will NOT run on the board (see README.md).
set -eu
IMG=/home/tim/openbmc/build/palmetto/tmp/deploy/images/palmetto/obmc-phosphor-image-palmetto.squashfs-xz
DEST=/home/tim/openbmc-palmetto-rofs
PI=asus-bmc
NFS=/srv/nfs/openbmc

[ -f "$IMG" ] || { echo "palmetto rootfs not built yet: $IMG"; exit 1; }

echo "[1] extract the ARMv5 rootfs locally"
rm -rf "$DEST"
unsquashfs -d "$DEST" -q "$IMG"

echo "[2] NFS-root adaptations (writable NFS = no read-only rofs / rwfs overlay needed)"
# OpenBMC's rofs overlay init expects MTD; on a rw NFS root the whole tree is writable, so
# neutralise the overlay/mtd mount units that would fail and block boot.
for u in obmc-flash-bmc-rofs.service obmc-flash-bmc-rwfs.service; do
    rm -f "$DEST/etc/systemd/system/"*"/$u" "$DEST/lib/systemd/system/$u" 2>/dev/null || true
done
# root fs is provided by the kernel (root=/dev/nfs); keep the tmpfs volatiles.
echo "[3] rsync to the Pi NFS export $NFS"
sudo rsync -a --numeric-ids --delete "$DEST/" "$PI:$NFS/" 2>/dev/null || \
    rsync -a --numeric-ids "$DEST/" "$PI:$NFS/"
echo "[4] done. Boot the AST2050 modern kernel with:"
echo "    root=/dev/nfs nfsroot=192.168.66.1:$NFS,vers=3,tcp ip=192.168.66.2:...:eth0:off rw"
echo "    (needs the eth0 ndo_open fix first -- see ../rig/nic-diag/NEXT-SESSION.md)"

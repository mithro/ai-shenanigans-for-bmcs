#!/bin/sh
# Run the built OpenBMC romulus image in QEMU and forward Redfish (443) + SSH (22).
# The OpenBMC filesystem is the built obmc-phosphor-image; QEMU's romulus-bmc machine
# provides the aspeed SoC + NIC (user-net). Once up:
#   Redfish:  curl -k https://localhost:2443/redfish/v1
#   SSH:      ssh -p 2222 root@localhost   (default pw: 0penBmc)
set -eu
IMG_DIR="${IMG_DIR:-/home/tim/openbmc/build/romulus/tmp/deploy/images/romulus}"
MTD="$IMG_DIR/obmc-phosphor-image-romulus.static.mtd"
[ -f "$MTD" ] || MTD="$(ls "$IMG_DIR"/*.static.mtd 2>/dev/null | head -1)"
[ -f "$MTD" ] || { echo "no image at $IMG_DIR (build not finished?)"; exit 1; }
echo "booting $MTD"
exec qemu-system-arm -M romulus-bmc -nographic \
    -drive file="$MTD",format=raw,if=mtd \
    -net nic,model=ftgmac100 \
    -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=tcp::2080-:80

#!/bin/bash
# F-HWPASS — one-command real-silicon boot + deferred-demo capture.
#
# Everything this needs is already built + staged (see HWPASS-PROGRESS.md):
#   * new 64 MB image with kcsbridge + populated ASUSTeK/0x0D16 IDs
#     -> Pi:/srv/nfs/openbmc-hwpass  (F5's /srv/nfs/openbmc-full untouched)
#   * full-featured kernel + combined DTB (kcs@2c + w83795g + vuart + power gpio)
#     -> asus-kgpe-d16-firmware/qemu-firmware/kernel/out/{uImage-kgpe-d16,aspeed-bmc-asus-kgpe-d16.dtb}
#   * KGPE-D16 x86 host powered ON (SystemRescue) = live W83795 rails + KCS peer.
#
# It was NOT run to completion in the F-HWPASS session because the WireGuard
# tunnel to the rig dropped (rig-side; last handshake went stale) after staging.
# Re-run this once `ssh asus-bmc` answers again. STATE-MUTATING (P2A BMC reset +
# NFS-root boot); non-destructive to flash; power-cycle recoverable. Does NOT
# drive host power (the SCU-pinmux-on-shared-pins hazard; host is already on).
set -euo pipefail

REPO=/home/tim/github/mithro/ai-shenanigans-for-bmcs
HW=$REPO/.worktrees/bmc-hwpass/asus-kgpe-d16-firmware
CULVERT=$REPO/.worktrees/culvert-g3-port/asus-kgpe-d16-firmware
EVID=$HW/openbmc/bmc-functionality/evidence/real-hw-hwpass
KOUT=$HW/qemu-firmware/kernel/out
PI=asus-bmc
BOARD=192.168.66.2
EXPORT=/srv/nfs/openbmc-hwpass
# clk_ignore_unused is REQUIRED on real silicon *for kernels built before the
# G3 clock-gate fix*: the AST2400 gate table made clk_disable_unused stop the
# G3's shared UARTCLK (SCU0C[15]) at t=4.16s; late-boot console writes then
# block PID1 and systemd's 2-min aspeed hardware watchdog resets the SoC at
# T+~6min (the 2026-07-12 "regression", root-caused in HWPASS-PROGRESS.md C.8).
# Kernels with the reworked 0001 clk patch + 0004 KCS-LCLK patch (branch
# claude/bmc-g3-clk, G3-CLK-PROGRESS.md) refcount UARTCLK/LCLK properly and
# boot clean WITHOUT it — proven on silicon with uImage-kgpe-g3clk +
# kgpe-g3clk-safe.dtb. Keep the flag here only because this runbook may be
# re-run with the older uImage-kgpe-d16-hwpass artifact.
BOOTARGS="console=ttyS4,115200n8 mem=64M clk_ignore_unused root=/dev/nfs rw ip=192.168.66.2::192.168.66.1:255.255.255.0::eth0:off nfsroot=192.168.66.1:$EXPORT,vers=3,tcp,nolock"

echo "[0] sanity: Pi reachable"
ssh -o BatchMode=yes -o ConnectTimeout=10 "$PI" 'hostname'

echo "[1] stage kernel + combined DTB to Pi TFTP"
scp "$KOUT/uImage-kgpe-d16"                "$PI:/srv/tftp-bmc/uImage-kgpe-d16-hwpass"
scp "$KOUT/aspeed-bmc-asus-kgpe-d16.dtb"   "$PI:/srv/tftp-bmc/kgpe-hwpass-combined.dtb"

echo "[2] ensure realhw daemon masks on the new export (idempotent)"
( cd "$HW/openbmc/bmc-functionality" && \
  uv run f5-realhw-mask.py apply --pi "$PI" --export "$EXPORT" )

echo "[2b] delete phosphor-network's DHCP config from the export (CRITICAL)"
# phosphor-network writes etc/systemd/network/00-bmc-eth0.network (DHCP=true,
# no static Address) into the rw NFS export ~3 min into every run. Writing it
# is inert for THAT run, but on the NEXT boot networkd takes over eth0, flushes
# the kernel-ip= static 192.168.66.2 (eth-bmc has NO DHCP server) and the NFS
# root dies mid-systemd — a perfect hard-freeze mimic (the 2026-07-12 "board
# regression" root cause; see HWPASS-PROGRESS.md Phase C.5). Delete before
# EVERY fresh boot, on whichever export is being booted.
ssh -o BatchMode=yes "$PI" "sudo rm -f $EXPORT/etc/systemd/network/00-bmc-eth0.network && echo '    network-file deleted (or already absent)'"

echo "[3] claim the rig (append intent to the Pi coordination log)"
ssh -o BatchMode=yes "$PI" "printf '%s\n' '- '\"\$(date -Is)\"'  instance-F-HWPASS: P2A cold-boot the new openbmc-hwpass image (kcsbridge + ASUSTeK/0x0D16 IDs) + full kernel + combined DTB over NFS. STATE-MUTATING (P2A DDR2 init + BMC reset-boot); flash untouched; power-cycle recoverable. Host stays ON. Will capture system-id/sensors/host-KCS/power-status/SOL then leave board ON.' | sudo tee -a /home/claude/HARDWARE-COORDINATION.md >/dev/null"

echo "[4] P2A NFS-root boot of the new stack (retry the flaky P2A load up to 3x)"
cd "$CULVERT"
rc=2
for attempt in 1 2 3; do
  echo "  --- boot attempt $attempt ---"
  if uv run linux-boot.py \
        --kernel uImage-kgpe-d16-hwpass \
        --dtb kgpe-hwpass-combined.dtb --no-initrd \
        --bootargs "$BOOTARGS" --watch 240; then
     rc=0; break
  fi
done
if [ $rc -ne 0 ]; then
  echo "[!] boot did not come up cleanly after 3 tries -- see console log above."
  echo "    FALLBACK: restore F5's proven config:"
  echo "      uv run linux-boot.py --kernel uImage-kgpe-d16-rxfix --dtb kgpe-g3vic.dtb --no-initrd \\"
  echo "        --bootargs 'console=ttyS4,115200n8 mem=64M root=/dev/nfs rw ip=192.168.66.2::192.168.66.1:255.255.255.0:kgpe-d16:eth0:off nfsroot=192.168.66.1:/srv/nfs/openbmc-full,vers=3,tcp,nolock'"
  exit 1
fi

echo "[5] capture the deferred demos over IPMI (from the Pi) + host-KCS/sensors"
mkdir -p "$EVID"
cd "$HW/openbmc/bmc-functionality"
uv run hwpass-realhw-capture.py --which both --evidence-dir "$EVID"

echo "[6] host-side KCS round-trip (host is at an OS -> talk to its BMC over KCS)"
# from the running host: ipmitool -I open should reach the BMC via /dev/ipmi-kcs3
# (kcsbridge is enabled in the image; the combined DTB has kcs@2c; the kernel has
# CONFIG_IPMI_KCS_BMC_CDEV_IPMI). Captured by hwpass-realhw-capture.py --which host.

echo "[done] board left ON running the new openbmc-hwpass image (populated IDs)."
echo "       Log completion to HARDWARE-COORDINATION.md + release the rig."

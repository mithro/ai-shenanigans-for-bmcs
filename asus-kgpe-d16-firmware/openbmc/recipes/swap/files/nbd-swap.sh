#!/bin/sh
# Attach the Pi bridge's RAM-backed NBD export as low-priority swap for the
# memory-tight AST2050 (64 MB DDR2 - 8 MB VGA reserve = ~44 MB usable). Swap over
# NBD is deadlock-safe under memory pressure (the nbd driver marks its socket
# SOCK_MEMALLOC and swap I/O runs under PF_MEMALLOC), and it offloads cold pages to
# the Pi's abundant RAM instead of consuming the BMC's own scarce RAM.
#
# Pi side: nbd-server exports `bmcswap` (a tmpfs-backed file) on 192.168.66.1:10809.
# Needs CONFIG_SWAP=y + CONFIG_BLK_DEV_NBD (both in the kgpe-d16-swap kernel).
set -eu

NBD_HOST="${NBD_HOST:-192.168.66.1}"
NBD_NAME="${NBD_NAME:-bmcswap}"
NBD_DEV="${NBD_DEV:-/dev/nbd0}"

case "${1:-on}" in
	on)
		# already attached? (nbd0/size non-zero)
		if [ "$(cat /sys/block/$(basename "$NBD_DEV")/size 2>/dev/null || echo 0)" = "0" ]; then
			nbd-client -N "$NBD_NAME" "$NBD_HOST" "$NBD_DEV"
		fi
		mkswap "$NBD_DEV"
		swapon -p -10 "$NBD_DEV"        # low priority: only used under real pressure
		swapon --show 2>/dev/null || cat /proc/swaps
		;;
	off)
		swapoff "$NBD_DEV" || true
		nbd-client -d "$NBD_DEV" || true
		;;
	*) echo "usage: $0 {on|off}" >&2; exit 2 ;;
esac

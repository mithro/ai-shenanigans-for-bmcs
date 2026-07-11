# F-IMG2 rebuilt image — staging

The rebuilt `obmc-phosphor-image-ast2050-full` (OpenBMC master, with the four
F-IMG2 recipe fixes) is staged for QEMU/NFS **without disturbing the live board**.

## Build output

- OpenBMC tree: `/home/tim/openbmc` (build dir `build/quanta-q71l`).
- Squashfs: `build/quanta-q71l/tmp/deploy/images/quanta-q71l/`
  `obmc-phosphor-image-ast2050-full-quanta-q71l.squashfs-xz`
  (build id `...-20260711174528`, ~22.7 MB, ARMv5TE / ARM926EJ-S).
- Reproduce: `asus-kgpe-d16-firmware/openbmc/recipes/sync-to-openbmc-tree.sh` then
  `bitbake obmc-phosphor-image-ast2050-full` (capped: `systemd-run --user --scope
  -p MemoryMax=20G -p MemoryHigh=18G nice -n 15 ionice -c3 ...`, BB `-j4`).

## Staged NFS export (NEW — does not touch F5's live export)

- **`/export/openbmc-img2`** — a **new** local NFS export (`/etc/exports.d/
  openbmc-img2.exports`, `127.0.0.1(rw,sync,no_subtree_check,no_root_squash,
  insecure)`; reachable from the guest at `10.0.2.2` via slirp). Staged with
  `qemu-firmware/scripts/stage-openbmc-nfsroot.sh <squashfs> /export/openbmc-img2`.
- **F5's live `/export/openbmc-full` and the Pi mirror `asus-bmc:/srv/nfs/
  openbmc-full` were left untouched** (they serve the live real-HW evidence).
- **Not** mirrored to the Pi: pushing to the shared board over NFS is a
  state-mutating real-HW action (the F-HWPASS task, coordinated via the Pi
  `/home/claude/HARDWARE-COORDINATION.md`). This image is QEMU-demonstrated and
  **ready to stage to real HW** — copy the squashfs above to the Pi export and
  boot with the g3vic kernel + a vuart-enabled DTB (the F1/F5 real-HW procedure).

## QEMU demo

`asus-kgpe-d16-firmware/openbmc/bmc-functionality/img2-demo.py` (main, all four
fixes) + `img2-fixup.py` (SOL/FRU re-capture). Boot artifacts: F3's
W83795G-capable `qemu-system-arm`, the g3vic `uImage-kgpe-d16`, and a
vuart-enabled `aspeed-bmc-asus-kgpe-d16.dtb` (`fdtput ... /ahb/apb/serial@1e787000
status okay`). Evidence: `evidence/img2/`.

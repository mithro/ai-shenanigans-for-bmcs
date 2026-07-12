#!/usr/bin/env python3
"""Carve the bootable pieces out of the Dell C410X proprietary BMC firmware
(Avocent MergePoint, AST2050) so they can be booted on the kgpe-d16-bmc QEMU
machine — the C4 "proprietary firmware boots to a running BMC web service" proof.

The user explicitly allowed using Dell resources; the C410X is the only AST2050
proprietary image available, and booting it to its web UI proves the QEMU
emulation is faithful enough to run untouched vendor firmware.

The firmware is a `_DCSI_` (.pec) container (see dell-c410x-firmware/ANALYSIS.md):
  0x000258  uImage  (Linux 2.6.23.1 kernel, load/entry 0x40008000)
  0x18A258  SquashFS v3.1 rootfs (appweb web server + www/ UI)
Outputs (into --out): uImage-c410x, rootfs-c410x.squashfs.
"""
import argparse
import struct
import zipfile

UIMAGE_OFF = 0x000258
SQUASHFS_OFF = 0x18A258
UIMAGE_MAGIC = 0x27051956
SQUASHFS_MAGIC = b"hsqs"


def read_pec_from_zip(zip_path, member_suffix=".pec"):
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.endswith(member_suffix))
        print(f"reading {name} from {zip_path}")
        return z.read(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, help="c410xbmc135.zip")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pec = read_pec_from_zip(args.zip)

    # uImage: 64-byte header; data size is big-endian at header+0x0C.
    magic, = struct.unpack_from(">I", pec, UIMAGE_OFF)
    assert magic == UIMAGE_MAGIC, f"bad uImage magic {magic:#x} at {UIMAGE_OFF:#x}"
    ksize, = struct.unpack_from(">I", pec, UIMAGE_OFF + 0x0C)
    load, ep = struct.unpack_from(">II", pec, UIMAGE_OFF + 0x10)
    kimg = pec[UIMAGE_OFF:UIMAGE_OFF + 64 + ksize]
    open(f"{args.out}/uImage-c410x", "wb").write(kimg)
    print(f"  uImage-c410x: {len(kimg)} bytes (data {ksize}, load {load:#x}, ep {ep:#x})")

    # SquashFS: superblock at offset+0; bytes_used is u64 LE at sb+0x28 (v3:
    # the field layout differs by version, so just carve to EOF — trailing
    # padding is harmless for a read-only mount).
    assert pec[SQUASHFS_OFF:SQUASHFS_OFF + 4] == SQUASHFS_MAGIC, "bad squashfs magic"
    sqfs = pec[SQUASHFS_OFF:]
    open(f"{args.out}/rootfs-c410x.squashfs", "wb").write(sqfs)
    print(f"  rootfs-c410x.squashfs: {len(sqfs)} bytes (to EOF)")


if __name__ == "__main__":
    main()

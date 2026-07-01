#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Build the C4 flash image: the Dell C410X proprietary firmware, patched to run
on the kgpe-d16-bmc QEMU machine and serve its appweb BMC web service.

Orchestrates the individual steps (each a standalone script here) end to end:

  1. extract-c410x.py     carve uImage-c410x + rootfs-c410x.squashfs from the .pec
  2. gunzip              the vendor uImage payload -> kernel.bin (decompressed)
  3. unsquashfs          the rootfs -> vendor busybox + /lib for the wrapper
  4. patch-c410x-mac.py   inject MAC, register MAC0, and unblock ndo_open -> uImage
  5. build-c410x-initramfs.py  wrapper initramfs (loop-mounts the squashfs, brings
                               eth0 up on slirp's guest IP)
  6. mkflash-c410x.py     assemble uboot + env + kernel + wrapper ramdisk -> flash

The result is verified by web-test.py. Needs: gzip, squashfs-tools (unsquashfs),
mkimage (u-boot-tools), mkenvimage.
"""
import argparse
import gzip
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(*cmd):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, help="dell-c410x-firmware/backup/c410xbmc135.zip")
    ap.add_argument("--uboot", required=True, help="OpenBMC AST2400 u-boot.bin")
    ap.add_argument("--out", required=True, help="output directory")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # 1. carve the vendor uImage + squashfs
    run("uv", "run", HERE / "extract-c410x.py", "--zip", args.zip, "--out", out)

    # 2. decompress the vendor uImage (64-byte header + gzip) -> kernel.bin
    uimg = (out / "uImage-c410x").read_bytes()
    magic, = struct.unpack_from(">I", uimg, 0)
    assert magic == 0x27051956, f"bad uImage magic {magic:#x}"
    kernel_bin = gzip.decompress(uimg[64:])
    (out / "kernel.bin").write_bytes(kernel_bin)
    print(f"  kernel.bin: {len(kernel_bin)} bytes (decompressed)")

    # 3. unpack the rootfs for the vendor busybox + /lib. unsquashfs returns 2
    # when it can't create device nodes as non-root ("created 0 devices") — that
    # is benign here (we only need busybox + /lib), so tolerate it and verify.
    sqroot = out / "squashfs-root"
    if sqroot.exists():
        run("rm", "-rf", sqroot)
    print("+", "unsquashfs", "-d", sqroot, out / "rootfs-c410x.squashfs")
    rc = subprocess.run(["unsquashfs", "-d", str(sqroot),
                         str(out / "rootfs-c410x.squashfs")]).returncode
    if rc not in (0, 2):
        sys.exit(f"unsquashfs failed (rc={rc})")
    if not (sqroot / "bin/busybox").exists() or not (sqroot / "lib").is_dir():
        sys.exit("unsquashfs did not extract bin/busybox + /lib")

    # 4. patch the kernel (MAC inject, register MAC0, unblock ndo_open)
    run("uv", "run", HERE / "patch-c410x-mac.py", out / "kernel.bin", out / "uImage-c4")

    # 5. build the wrapper initramfs
    run("uv", "run", HERE / "build-c410x-initramfs.py",
        "--busybox", sqroot / "bin/busybox", "--vendor-lib", sqroot / "lib",
        "--squashfs", out / "rootfs-c410x.squashfs", "--out", out / "uInitrd-c4")

    # 6. assemble the flash
    run("uv", "run", HERE / "mkflash-c410x.py", "--uboot", args.uboot,
        "--kernel", out / "uImage-c4", "--ramdisk-image", out / "uInitrd-c4",
        "--out", out / "flash-c4.img")

    print(f"\nC4 flash ready: {out / 'flash-c4.img'}")
    print("verify with: web-test.py --qemu <qemu-system-arm> "
          f"--flash {out / 'flash-c4.img'}")


if __name__ == "__main__":
    sys.exit(main())

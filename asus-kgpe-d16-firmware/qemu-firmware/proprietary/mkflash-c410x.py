#!/usr/bin/env python3
"""Assemble a flash image that boots the Dell C410X proprietary firmware on the
kgpe-d16-bmc QEMU machine via the OpenBMC U-Boot ATAGS path.

The Dell kernel's native console is ttyS0 (0x1E783000) and its root is
root=/dev/mtdblock3 — so run QEMU with `-machine kgpe-d16-bmc,uart=uart1` to wire
stdio to 0x1E783000, and lay the SquashFS in flash as the 4th MTD region.

Flash layout (matches the Dell partitions, ANALYSIS.md):
  uboot@0  env@0x20000  kernel@0x100000  rootfs(squashfs)@0x300000
A full image (kernel 1.6M + rootfs 8.6M) needs >=16 MB; pass --size 0x1000000.
With --no-rootfs (kernel-only probe) an 8 MB image suffices.
"""
import argparse
import subprocess

# mtdparts so the kernel's /dev/mtdblock3 == the rootfs region we place below.
MTDPARTS = ("mtdparts=spi0.0:0x100000(uboot),0x10000(env),"
            "0x200000(kernel),-(rootfs)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uboot", required=True)
    ap.add_argument("--kernel", required=True, help="uImage-c410x")
    ap.add_argument("--rootfs", help="rootfs-c410x.squashfs (omit for probe)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="0x1000000")  # 16 MB
    ap.add_argument("--machid", default="22b8")
    ap.add_argument("--no-rootfs", action="store_true")
    args = ap.parse_args()

    root = "root=/dev/mtdblock3 rootfstype=squashfs ro" if not args.no_rootfs \
        else "root=/dev/ram0"
    bootcmd = "cp.b 0x20100000 0x41400000 0x200000; "
    if not args.no_rootfs:
        # rootfs stays in (memory-mapped) flash; the kernel's MTD driver reads it.
        bootcmd += "bootm 0x41400000"
    else:
        bootcmd += "bootm 0x41400000"
    env = (
        "bootdelay=0\n"
        f"machid={args.machid}\n"
        f"bootargs=console=ttyS0,115200n8 mem=96M {root} {MTDPARTS} earlyprintk\n"
        f"bootcmd={bootcmd}\n"
    )
    env_txt, env_img = args.out + ".env.txt", args.out + ".env.img"
    open(env_txt, "w").write(env)
    subprocess.run(["mkenvimage", "-s", "0x10000", "-o", env_img, env_txt],
                   check=True)

    flash = bytearray(b"\xff" * int(args.size, 0))

    def place(path, off):
        data = open(path, "rb").read()
        flash[off:off + len(data)] = data
        print(f"  {hex(off):>9} {len(data):>9} {path}")

    place(args.uboot, 0x000000)
    place(env_img, 0x0F0000)   # OpenBMC U-Boot reads its env here (not the Dell 0x20000)
    place(args.kernel, 0x100000)
    if not args.no_rootfs and args.rootfs:
        place(args.rootfs, 0x300000)
    open(args.out, "wb").write(flash)
    print(f"wrote {args.out} ({len(flash)} bytes)")


if __name__ == "__main__":
    main()

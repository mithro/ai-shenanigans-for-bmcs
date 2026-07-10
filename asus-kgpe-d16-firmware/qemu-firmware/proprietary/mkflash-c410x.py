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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uboot", required=True)
    ap.add_argument("--kernel", required=True, help="uImage-c410x")
    ap.add_argument("--rootfs", help="rootfs-c410x.squashfs (omit for probe)")
    ap.add_argument("--ramdisk-image",
                    help="pre-built uImage ramdisk (e.g. the wrapper initramfs); "
                         "boots as a cpio initramfs (rdinit=/init), placed as-is")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="0x1000000")  # 16 MB
    ap.add_argument("--machid", default="232b")      # ASPEED-AST2050 = 9003
    ap.add_argument("--no-rootfs", action="store_true")
    args = ap.parse_args()

    have_rootfs = bool(args.rootfs) and not args.no_rootfs

    # Boot the SquashFS as a RAMDISK, not from flash: the vendor kernel reads
    # flash via the legacy AST2050 SMC controller (0x16000000) which this
    # AST2400-based machine doesn't model (its reads return 0 under
    # ignore_memory_transaction_failures), so it can't actually read mtdblock3.
    # Instead U-Boot copies the rootfs from flash (via the *modelled* FMC) into
    # RAM and the kernel mounts /dev/ram0 — no SMC needed.
    if args.ramdisk_image:
        # The wrapper is a gzip cpio initramfs: the kernel unpacks it and runs
        # /init (which loop-mounts the vendor squashfs + tmpfs /flash, then
        # switch_roots). No root= — the initramfs is the initial root.
        root = "rdinit=/init"
        bootcmd = ("cp.b 0x20100000 0x41400000 0x200000; "
                   "cp.b 0x20300000 0x42600000 0xd00000; "
                   "bootm 0x41400000 0x42600000")
    elif have_rootfs:
        root = "root=/dev/ram0 rootfstype=squashfs ramdisk_size=32768 ro init=/linuxrc"
        bootcmd = ("cp.b 0x20100000 0x41400000 0x200000; "
                   "cp.b 0x20300000 0x42600000 0x900000; "
                   "bootm 0x41400000 0x42600000")
    else:
        root = "root=/dev/ram0"
        bootcmd = "cp.b 0x20100000 0x41400000 0x200000; bootm 0x41400000"
    env = (
        "bootdelay=0\n"
        f"machid={args.machid}\n"
        f"bootargs=console=ttyS0,115200n8 mem=96M {root} earlyprintk\n"
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
    if args.ramdisk_image:
        place(args.ramdisk_image, 0x300000)
    elif have_rootfs:
        # Wrap the raw SquashFS as a legacy U-Boot ramdisk image so bootm can
        # copy it into RAM and hand it to the kernel as /dev/ram0.
        uramdisk = args.out + ".uramdisk"
        subprocess.run(
            ["mkimage", "-A", "arm", "-O", "linux", "-T", "ramdisk", "-C", "none",
             "-n", "c410x squashfs rootfs", "-d", args.rootfs, uramdisk],
            check=True)
        place(uramdisk, 0x300000)
    open(args.out, "wb").write(flash)
    print(f"wrote {args.out} ({len(flash)} bytes)")


if __name__ == "__main__":
    main()

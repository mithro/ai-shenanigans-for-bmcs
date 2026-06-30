#!/usr/bin/env python3
"""Build a small wrapper initramfs that boots the UNMODIFIED Dell C410X vendor
SquashFS while supplying the one thing the emulation can't: a writable
/flash/data0.

On real hardware /flash/data0 is a JFFS2 "Private Storage" partition on the SPI
flash, mounted by the firmware's preinit.sh. This AST2400-based QEMU machine
doesn't model the legacy AST2050 SMC flash controller the vendor kernel uses, so
that partition is absent and the fullfw BMC app (and thus the appweb web server)
can't persist config. Rather than patch the vendor firmware, we wrap it: a tiny
musl-BusyBox initramfs loop-mounts the vendor SquashFS read-only, lays a tmpfs
over /flash, and switch_roots into the vendor init. The firmware boots byte-for-
byte unmodified; only the missing flash partition is emulated with RAM.

Output: a uImage ramdisk (cpio.gz) to place in flash for U-Boot bootm.
"""
import argparse
import gzip
import os
import stat
import struct
import subprocess

S_IFCHR, S_IFBLK = 0o020000, 0o060000

INIT = """#!/bin/busybox sh
/bin/busybox mount -t proc proc /proc
/bin/busybox mount -t sysfs sysfs /sys
/bin/busybox mkdir -p /newroot
# Loop-mount the unmodified vendor SquashFS read-only.
/bin/busybox mount -o loop,ro -t squashfs /rootfs.squashfs /newroot
# Supply the writable persistent-storage partition the (unmodelled) SMC flash
# would hold, as tmpfs, so the vendor BMC app can run.
/bin/busybox mount -t tmpfs tmpfs /newroot/flash
/bin/busybox mkdir -p /newroot/flash/data0
echo "C410X-WRAPPER: handing off to vendor init"
exec /bin/busybox switch_root /newroot /sbin/init
"""

# char: (name, mode, maj, min); block: loop devices for the squashfs mount.
CHR = [("dev/console", 0o600, 5, 1), ("dev/null", 0o666, 1, 3),
       ("dev/tty", 0o666, 5, 0), ("dev/zero", 0o666, 1, 5)]
BLK = [(f"dev/loop{i}", 0o660, 7, i) for i in range(4)]


class Newc:
    def __init__(self):
        self.buf = bytearray(); self.ino = 0

    def _e(self, name, mode, nlink, data=b"", rmaj=0, rmin=0):
        self.ino += 1
        nb = name.encode() + b"\x00"
        h = b"070701"
        for v in (self.ino, mode, 0, 0, nlink, 0, len(data),
                  0, 0, rmaj, rmin, len(nb), 0):
            h += b"%08x" % (v & 0xffffffff)
        h += nb; h += b"\x00" * ((-len(h)) % 4)
        h += data; h += b"\x00" * ((-len(data)) % 4)
        self.buf += h

    def dir(self, n): self._e(n, stat.S_IFDIR | 0o755, 2)
    def file(self, n, m, d): self._e(n, stat.S_IFREG | (m & 0o7777), 1, d)
    def slink(self, n, t): self._e(n, stat.S_IFLNK | 0o777, 1, t.encode())
    def node(self, n, mode, mj, mn): self._e(n, mode, 1, b"", mj, mn)
    def done(self): self._e("TRAILER!!!", 0, 1); return bytes(self.buf)


def copy_lib_tree(c, libdir):
    """Copy the whole vendor /lib into the cpio (files + symlinks). The vendor
    busybox is OABI + dynamically linked against several Avocent libs (libaim,
    libpam, libsm, ...) plus glibc 2.3.6, so the wrapper needs the loader + the
    full lib set to run it; copying everything is simplest and still compresses
    well next to the already-compressed squashfs."""
    for name in sorted(os.listdir(libdir)):
        src = os.path.join(libdir, name)
        dst = "lib/" + name
        if os.path.islink(src):
            c.slink(dst, os.readlink(src))
        elif os.path.isfile(src):
            with open(src, "rb") as f:
                c.file(dst, 0o755, f.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--busybox", required=True,
                    help="vendor busybox (squashfs-root/bin/busybox)")
    ap.add_argument("--vendor-lib", required=True,
                    help="vendor /lib dir (squashfs-root/lib) for loader + libc")
    ap.add_argument("--squashfs", required=True, help="vendor rootfs squashfs")
    ap.add_argument("--out", required=True, help="uImage ramdisk output")
    args = ap.parse_args()

    c = Newc()
    c.dir(".")
    for d in ("bin", "sbin", "lib", "dev", "proc", "sys", "newroot", "flash"):
        c.dir(d)
    with open(args.busybox, "rb") as f:
        c.file("bin/busybox", 0o755, f.read())
    c.slink("bin/sh", "busybox")
    copy_lib_tree(c, args.vendor_lib)
    c.file("init", 0o755, INIT.encode())
    with open(args.squashfs, "rb") as f:
        c.file("rootfs.squashfs", 0o644, f.read())
    for n, m, mj, mn in CHR:
        c.node(n, S_IFCHR | (m & 0o7777), mj, mn)
    for n, m, mj, mn in BLK:
        c.node(n, S_IFBLK | (m & 0o7777), mj, mn)
    raw = c.done()

    gz = args.out + ".cpio.gz"
    with gzip.open(gz, "wb", compresslevel=6) as g:
        g.write(raw)
    print(f"wrapper cpio: {len(raw)} bytes -> {gz}")
    subprocess.run(
        ["mkimage", "-A", "arm", "-O", "linux", "-T", "ramdisk", "-C", "gzip",
         "-n", "c410x wrapper initramfs", "-d", gz, args.out], check=True)


if __name__ == "__main__":
    main()

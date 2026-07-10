#!/usr/bin/env python3
"""Repack the C2 BusyBox+dropbear rootfs into a uInitrd that also boots the
Raptor 2.6.28 kernel, by baking STATIC /dev nodes into the cpio.

Why a separate packer
---------------------
`initramfs/build.py` packs the rootfs with the `cpio` tool, which can only emit
device nodes that already exist on disk — and creating them needs root. The
modern kernel (C2) doesn't care: it mounts devtmpfs and populates /dev itself.
The Raptor kernel (C3) is 2.6.28, which predates devtmpfs (2.6.32), so it needs
/dev/console to give PID 1 its stdio and /dev/urandom etc. for dropbear. Without
them PID 1's `exec /bin/sh` gets a closed stdin, exits, and the kernel panics
("Attempted to kill init!").

This writes the newc cpio format directly in Python (no root, deterministic),
emitting every rootfs file/dir/symlink plus the static device nodes below. The
result also boots the modern kernel (devtmpfs just shadows the static nodes), so
it is a strict superset of build.py's image.

Usage:
    uv run mkinitramfs-raptor.py --rootfs …/initramfs/build/rootfs \\
        --init …/initramfs/init --out …/initramfs/out/uInitrd-raptor
"""
import argparse
import gzip
import os
import stat
import subprocess

S_IFCHR = 0o020000

# Minimal static /dev for a pre-devtmpfs userspace: (name, mode, major, minor).
DEV_NODES = [
    ("dev/console", 0o600, 5, 1),
    ("dev/null",    0o666, 1, 3),
    ("dev/zero",    0o666, 1, 5),
    ("dev/full",    0o666, 1, 7),
    ("dev/random",  0o666, 1, 8),
    ("dev/urandom", 0o666, 1, 9),   # dropbear entropy
    ("dev/tty",     0o666, 5, 0),
    ("dev/ptmx",    0o666, 5, 2),   # + devpts mount -> PTYs for ssh sessions
    ("dev/ttyS0",   0o600, 4, 64),
    ("dev/ttyS1",   0o600, 4, 65),  # console (0x1e784000)
]


class Newc:
    """Minimal SVR4 (newc) cpio writer — the format the kernel initramfs
    unpacker reads. Each header is 110 ASCII bytes of 8-hex fields; header+name
    and file data are each padded to a 4-byte boundary."""

    def __init__(self):
        self.buf = bytearray()
        self.ino = 0

    def _entry(self, name, mode, nlink, data=b"", rmaj=0, rmin=0):
        self.ino += 1
        name_b = name.encode() + b"\x00"
        h = b"070701"
        for v in (self.ino, mode, 0, 0, nlink, 0, len(data),
                  0, 0, rmaj, rmin, len(name_b), 0):
            h += b"%08x" % (v & 0xffffffff)
        h += name_b
        h += b"\x00" * ((-len(h)) % 4)
        h += data
        h += b"\x00" * ((-len(data)) % 4)
        self.buf += h

    def add_dir(self, name):
        self._entry(name, stat.S_IFDIR | 0o755, 2)

    def add_file(self, name, mode, data):
        self._entry(name, stat.S_IFREG | (mode & 0o7777), 1, data)

    def add_symlink(self, name, target):
        self._entry(name, stat.S_IFLNK | 0o777, 1, target.encode())

    def add_node(self, name, mode, major, minor):
        self._entry(name, S_IFCHR | (mode & 0o7777), 1, b"", major, minor)

    def finish(self):
        self._entry("TRAILER!!!", 0, 1)
        return bytes(self.buf)


def build(rootfs, out_cpio_gz):
    c = Newc()
    c.add_dir(".")
    for dirpath, dirnames, filenames in os.walk(rootfs):
        dirnames.sort()
        rel_dir = os.path.relpath(dirpath, rootfs)
        if rel_dir != ".":
            c.add_dir(rel_dir)
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, rootfs)
            st = os.lstat(full)
            if stat.S_ISLNK(st.st_mode):
                c.add_symlink(rel, os.readlink(full))
            elif stat.S_ISREG(st.st_mode):
                with open(full, "rb") as f:
                    c.add_file(rel, st.st_mode, f.read())
            # device nodes in the staged tree (if any) are re-emitted below
    for name, mode, major, minor in DEV_NODES:
        c.add_node(name, mode, major, minor)
    raw = c.finish()
    with gzip.open(out_cpio_gz, "wb", compresslevel=9) as g:
        g.write(raw)
    return len(raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rootfs", required=True)
    ap.add_argument("--init", help="canonical init to drop in as /init")
    ap.add_argument("--out", required=True, help="uInitrd output path")
    args = ap.parse_args()

    if args.init:
        dst = os.path.join(args.rootfs, "init")
        with open(args.init, "rb") as s, open(dst, "wb") as d:
            d.write(s.read())
        os.chmod(dst, 0o755)

    cpio_gz = args.out + ".cpio.gz"
    n = build(args.rootfs, cpio_gz)
    print(f"newc cpio: {n} bytes (+{len(DEV_NODES)} static /dev nodes) -> {cpio_gz}")
    subprocess.run(
        ["mkimage", "-A", "arm", "-O", "linux", "-T", "ramdisk", "-C", "gzip",
         "-n", "KGPE-D16 BMC initramfs (static /dev)", "-d", cpio_gz, args.out],
        check=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Lower a static-glibc binary's `.note.ABI-tag` minimum kernel version so it
will run on the Raptor 2.6.28 kernel.

Modern cross-glibc bakes a minimum supported kernel (here 3.2.0) into the
NT_GNU_ABI_TAG ELF note. At startup static glibc compares the running kernel to
that floor and, if older, calls __libc_fatal("kernel too old") and exits — which
is why BusyBox/dropbear (glibc, kernel-min 3.2.0) silently kill PID 1 on the
2.6.28 kernel even though the kernel execs EABI binaries fine. Rewriting the
note's version to 2.6.0 removes the gate. (BusyBox/dropbear use only long-stable
syscalls, so the lowered floor is safe in practice.)

The note descriptor is 4 little-endian u32: [OS=0(Linux), major, minor, patch].
We match the full ABI-tag note header to avoid touching anything else.

Usage:
    uv run lower-abi-tag.py BIN [BIN ...]            # -> 2.6.0
    uv run lower-abi-tag.py --to 2.6.16 BIN
"""
import argparse
import struct
import sys

# namesz=4, descsz=16, type=1(NT_GNU_ABI_TAG), name="GNU\0"
NOTE_HDR = struct.pack("<III", 4, 16, 1) + b"GNU\x00"


def patch(path, major, minor, patch_):
    data = bytearray(open(path, "rb").read())
    i = data.find(NOTE_HDR)
    if i < 0:
        print(f"  {path}: no NT_GNU_ABI_TAG note found", file=sys.stderr)
        return False
    desc_off = i + len(NOTE_HDR)
    os_, omaj, omin, osub = struct.unpack_from("<IIII", data, desc_off)
    if os_ != 0:
        print(f"  {path}: note OS={os_} not Linux; skipping", file=sys.stderr)
        return False
    struct.pack_into("<IIII", data, desc_off, 0, major, minor, patch_)
    open(path, "wb").write(data)
    print(f"  {path}: min kernel {omaj}.{omin}.{osub} -> {major}.{minor}.{patch_}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", default="2.6.0", help="target min kernel (default 2.6.0)")
    ap.add_argument("bins", nargs="+")
    args = ap.parse_args()
    major, minor, patch_ = (int(x) for x in args.to.split("."))
    ok = all(patch(b, major, minor, patch_) for b in args.bins)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

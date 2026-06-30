#!/usr/bin/env python3
"""Recover the ARM mach-type(s) baked into a decompressed ARM Linux Image by
locating its `struct machine_desc` records (the `.arch.info.init` array).

A 2.6.x machine_desc begins:
    u32 nr; u32 phys_io; u32 io_pg_offst; const char *name; u32 boot_params; ...
The `name` field (offset 0x0C) is a kernel-virtual pointer into rodata. We find
every machine-name-looking string, compute its virtual address, search the image
for a little-endian pointer to it, and read `nr` 0x0C bytes before that pointer.

The Image is linked at PAGE_OFFSET+TEXT_OFFSET = 0xC0008000 (default ARM), so
file_offset = vaddr - 0xC0008000.
"""
import argparse
import re
import struct

LINK_BASE = 0xC0008000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="decompressed kernel Image")
    ap.add_argument("--base", default=hex(LINK_BASE),
                    help="kernel link vaddr (default 0xC0008000)")
    args = ap.parse_args()
    data = open(args.image, "rb").read()
    n = len(data)
    # Try several common ARM link bases for resolving the name pointer.
    bases = [int(args.base, 0), 0xC0008000, 0xC0000000, 0x80008000, 0x40008000]

    def read_cstr(foff):
        end = data.find(b"\x00", foff)
        s = data[foff:end]
        if 1 <= len(s) <= 48 and all(0x20 <= c < 0x7f for c in s):
            return s.decode("latin1")
        return None

    # Anchor on boot_params (machine_desc offset 0x10): the ATAGs pointer sits
    # just above start-of-DRAM (0x40000000), classically 0x40000100. From there,
    # name_ptr is 4 bytes before and nr is 0x10 bytes before.
    found = []
    for bp_off in range(0x10, n - 4, 4):
        boot_params, = struct.unpack_from("<I", data, bp_off)
        if not (0x40000000 <= boot_params <= 0x40010000):
            continue
        nr, phys_io, io_pg, name_ptr = struct.unpack_from("<IIII", data, bp_off - 0x10)
        if not (0 < nr < 0x20000):
            continue
        for base in bases:
            foff = name_ptr - base
            if 0 <= foff < n:
                name = read_cstr(foff)
                if name:
                    found.append((nr, name, phys_io, boot_params, base))
                    break

    print(f"\nmachine_desc candidates ({len(found)}):")
    for nr, name, phys_io, bp, base in sorted(set(found)):
        print(f"  nr={nr} (0x{nr:x})  name={name!r}  phys_io=0x{phys_io:08x}  "
              f"boot_params=0x{bp:08x}  (base 0x{base:08x})")
    if not found:
        print("  (none)")


if __name__ == "__main__":
    main()

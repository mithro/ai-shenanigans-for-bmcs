#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""In-system CMOS editor / learner for the ASUS KGP(M)E-D16 (AMIBIOS8 v3309).

STAGED tool — run as root ON THE BOOTED HOST (it needs the real RTC CMOS via I/O
ports 70h/71h through /dev/port). It is NOT run against hardware from the repo.

Commands:
  dump   [FILE]         read all 128 CMOS bytes, print + optionally save
  diff   A B            byte+bit diff of two dumps (the core of 'learn')
  show                  decode current CMOS values for mapped settings
  learn  NAME           guided: snapshot -> you change ONE option in Setup ->
                        snapshot -> diff => that setting's byte+bits+code
  checksum              compute candidate AMIBIOS checksums vs the stored bytes
  set    NAME=VALUE     compute the write (DRY-RUN); add --apply to actually write
                        (requires --checksum-verified once the checksum is known)

Safe: dump/diff/show/learn/checksum are read-only. `set` is dry-run unless --apply.
CMOS index = 0x00..0x7F; /dev/nvram (offset by 0x0E) is intentionally avoided so the
BIOS setup checksum can be handled explicitly rather than by the kernel nvram driver.
"""
import argparse
import json
import os
import sys
from pathlib import Path

IDX_PORT, DATA_PORT = 0x70, 0x71
MAP_PATH = Path(__file__).with_name("cmos_map.json")


def _portfd():
    try:
        return os.open("/dev/port", os.O_RDWR)
    except OSError as e:
        sys.exit(f"FATAL: cannot open /dev/port ({e}) — run as root on the booted host")


def cmos_read(idx, fd=None):
    own = fd is None
    fd = fd or _portfd()
    try:
        os.pwrite(fd, bytes([idx & 0x7F]), IDX_PORT)
        return os.pread(fd, 1, DATA_PORT)[0]
    finally:
        if own:
            os.close(fd)


def cmos_read_all():
    fd = _portfd()
    try:
        return bytes(cmos_read(i, fd) for i in range(128))
    finally:
        os.close(fd)


def cmos_write(idx, val):
    fd = _portfd()
    try:
        os.pwrite(fd, bytes([idx & 0x7F]), IDX_PORT)
        os.pwrite(fd, bytes([val & 0xFF]), DATA_PORT)
    finally:
        os.close(fd)


def load_map():
    return json.loads(MAP_PATH.read_text())


def hexdump(data):
    for i in range(0, len(data), 16):
        row = data[i:i + 16]
        print(f"  0x{i:02X}: " + " ".join(f"{b:02X}" for b in row))


def cmd_dump(args):
    data = cmos_read_all()
    hexdump(data)
    if args.file:
        Path(args.file).write_bytes(data)
        print(f"saved {len(data)} bytes -> {args.file}")


def cmd_diff(args):
    a = Path(args.a).read_bytes()
    b = Path(args.b).read_bytes()
    if len(a) != len(b):
        sys.exit("dumps differ in length")
    changed = False
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            changed = True
            bits = x ^ y
            print(f"  CMOS 0x{i:02X}: {x:02X} -> {y:02X}  (bits {bits:08b}, "
                  f"field {x & bits:02X}->{y & bits:02X})")
    if not changed:
        print("  no differences")


def _field(byte, mask):
    return byte & mask


def cmd_show(args):
    m = load_map()
    data = cmos_read_all()
    print("Simple-CMOS settings (byte-index decoded; bit within byte = best-effort):")
    for name, e in m["simple_cmos_settings"].items():
        off = e["cmos_byte"]
        raw = data[off]
        print(f"  0x{off:02X}=[{raw:02X}] {name:30} owner={e['byte_owner']}  opts={e['options']}")
    print("\nExtended settings of interest (offset via `learn`):")
    for name, e in m["extended_settings_of_interest"].items():
        print(f"  handle {e['handle']} {name:30} opts={e['options']}")


def cmd_learn(args):
    name = args.name
    print(f"LEARN '{name}':")
    print("  1) taking CMOS snapshot A ...")
    a = cmos_read_all()
    input(f"  2) In BIOS Setup, change ONLY '{name}' to a different value, Save & Exit,\n"
          f"     boot back to this OS, then press Enter here ... ")
    b = cmos_read_all()
    print("  3) diff (A -> B):")
    found = False
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            found = True
            bits = x ^ y
            print(f"     CMOS 0x{i:02X}: {x:02X} -> {y:02X}  changed-bits=0x{bits:02X}")
    if not found:
        print("     (nothing changed — did the value actually change + save?)")
    print("  => the setting's byte is the one that changed; changed-bits is its field mask.")
    print("     Also note which byte(s) the *checksum* lives in (a byte that changes on every save).")


def _amibios_checksums(data):
    # AMIBIOS setup checksum is a 16-bit sum over a byte range, stored in 2 bytes.
    # Range/store vary; try the common candidates and report which matches a stored word.
    cands = []
    for lo, hi, sl, sh in [(0x10, 0x2D, 0x2E, 0x2F), (0x10, 0x2E, 0x2E, 0x2F),
                           (0x10, 0x3D, 0x3E, 0x3F), (0x10, 0x2F, 0x30, 0x31)]:
        s = sum(data[lo:hi + 1]) & 0xFFFF
        stored = data[sl] | (data[sh] << 8)
        stored_be = (data[sl] << 8) | data[sh]
        cands.append((lo, hi, sl, sh, s, stored, stored_be, s in (stored, stored_be)))
    return cands


def cmd_checksum(args):
    data = cmos_read_all()
    print("candidate AMIBIOS checksum ranges (sum over [lo..hi] stored at sl,sh):")
    for lo, hi, sl, sh, s, st_le, st_be, match in _amibios_checksums(data):
        print(f"  range 0x{lo:02X}..0x{hi:02X} store 0x{sl:02X}/0x{sh:02X}: "
              f"sum=0x{s:04X} stored=0x{st_le:04X}(LE)/0x{st_be:04X}(BE) "
              f"{'<-- MATCH' if match else ''}")
    print("The matching row is the live checksum; use it in `set`.")


def cmd_set(args):
    m = load_map()
    name, _, want = args.assignment.partition("=")
    name, want = name.strip(), want.strip()
    e = m["simple_cmos_settings"].get(name)
    if not e:
        sys.exit(f"'{name}' is not a simple-CMOS setting; run `learn '{name}'` first "
                 f"(extended/serial settings need the learned byte+bits).")
    if want not in e["options"]:
        sys.exit(f"value '{want}' not in options {e['options']}")
    code = e["options"].index(want)  # value-code == option index (verify by diff!)
    off = e["cmos_byte"]
    if not e["byte_owner"]:
        sys.exit(f"'{name}' shares CMOS byte 0x{off:02X} with {e['shares_byte_with']}; "
                 f"the exact bits are unknown — run `learn '{name}'` before writing.")
    cur = cmos_read(off)
    width = max(1, (len(e["options"]) - 1).bit_length())
    mask = (1 << width) - 1
    new = (cur & ~mask) | (code & mask)
    print(f"SET {name} = {want} (code {code})")
    print(f"  CMOS 0x{off:02X}: {cur:02X} -> {new:02X}  (assuming field = low {width} bit(s))")
    if not args.apply:
        print("  DRY-RUN (no write). Re-run with --apply --checksum-verified to write.")
        return
    if not args.checksum_verified:
        sys.exit("refusing to write: pass --checksum-verified only after confirming the "
                 "checksum range via `checksum`/`learn` (else the BIOS resets to defaults).")
    cmos_write(off, new)
    print("  WROTE. Now recompute + write the BIOS checksum (see `checksum`).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("dump"); p.add_argument("file", nargs="?"); p.set_defaults(fn=cmd_dump)
    p = sub.add_parser("diff"); p.add_argument("a"); p.add_argument("b"); p.set_defaults(fn=cmd_diff)
    sub.add_parser("show").set_defaults(fn=cmd_show)
    p = sub.add_parser("learn"); p.add_argument("name"); p.set_defaults(fn=cmd_learn)
    sub.add_parser("checksum").set_defaults(fn=cmd_checksum)
    p = sub.add_parser("set"); p.add_argument("assignment")
    p.add_argument("--apply", action="store_true"); p.add_argument("--checksum-verified", action="store_true")
    p.set_defaults(fn=cmd_set)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

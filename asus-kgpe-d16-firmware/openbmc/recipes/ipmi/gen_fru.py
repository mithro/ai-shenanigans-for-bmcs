#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Generate a standard IPMI Platform Management FRU binary for the ASUS KGPE-D16.

phosphor-read-eeprom parses this blob (Common Header + Chassis/Board/Product
Info Areas) and writes the mapped Asset properties onto the D-Bus inventory
object (fruid 0x56 -> /system/chassis/motherboard per the q71l inventory map),
which phosphor-ipmi-host then formats back into `ipmitool fru print`. This makes
`ipmitool fru print` return real board identity in QEMU with no emulated I2C
EEPROM (an image-recipe-only fix). Output: files/motherboard-fru.bin.

FRU format: IPMI Platform Management FRU Information Storage Definition v1.0.
"""
import os
import sys


def tl(s: str) -> bytes:
    """Type/length-encoded field: 0xC0|len (8-bit ASCII) + bytes."""
    b = s.encode("ascii")
    if len(b) > 63:
        raise ValueError(f"field too long: {s!r}")
    return bytes([0xC0 | len(b)]) + b


def finalize_area(head: bytes, len_index: int, fields: bytes) -> bytes:
    """Assemble an info area: head (with a length placeholder at len_index) +
    fields + 0xC1 end marker, zero-pad so total (incl. the trailing checksum) is
    a multiple of 8, set the length byte, then append the area checksum. The
    length MUST be written before the checksum is computed (it is covered by it)."""
    content = head + fields + b"\xC1"
    while (len(content) + 1) % 8 != 0:
        content += b"\x00"
    total_len = len(content) + 1  # + checksum byte
    content = content[:len_index] + bytes([total_len // 8]) + \
        content[len_index + 1:]
    chk = (-sum(content)) & 0xFF
    return content + bytes([chk])


def board_area(mfg: str, product: str, serial: str, part: str,
               fru_file_id: str, mfg_minutes: int) -> bytes:
    head = bytes([0x01, 0x00, 0x00])  # ver, len(placeholder@1), lang
    fields = bytes([
        mfg_minutes & 0xFF,
        (mfg_minutes >> 8) & 0xFF,
        (mfg_minutes >> 16) & 0xFF,
    ])
    fields += tl(mfg) + tl(product) + tl(serial) + tl(part) + tl(fru_file_id)
    return finalize_area(head, 1, fields)


def chassis_area(part: str, serial: str, chassis_type: int = 0x17) -> bytes:
    # 0x17 = Rack Mount Chassis
    head = bytes([0x01, 0x00])  # ver, len(placeholder@1)
    fields = bytes([chassis_type]) + tl(part) + tl(serial)
    return finalize_area(head, 1, fields)


def product_area(mfg: str, name: str, part: str, version: str, serial: str,
                 asset_tag: str, fru_file_id: str) -> bytes:
    head = bytes([0x01, 0x00, 0x00])  # ver, len(placeholder@1), lang
    fields = tl(mfg) + tl(name) + tl(part) + tl(version) + tl(serial)
    fields += tl(asset_tag) + tl(fru_file_id)
    return finalize_area(head, 1, fields)


def build() -> bytes:
    # Board Mfg date: minutes since 1996-01-01 00:00 UTC. Use a fixed epoch
    # (2012-01-01) so the blob is reproducible.
    # (2012-01-01 - 1996-01-01) = 5844 days = 8415360 minutes.
    mfg_minutes = 8415360

    chassis = chassis_area(part="KGPE-D16-CHASSIS",
                           serial="KGPED16-CH-0001")
    board = board_area(mfg="ASUSTeK Computer Inc.",
                       product="KGPE-D16",
                       serial="KGPED16-OPENBMC-0001",
                       part="90-MSVDR0-G0UAY0Z",
                       fru_file_id="KGPED16",
                       mfg_minutes=mfg_minutes)
    product = product_area(mfg="ASUSTeK Computer Inc.",
                           name="KGPE-D16",
                           part="90-MSVDR0-G0UAY0Z",
                           version="Rev 1.xxG",
                           serial="KGPED16-OPENBMC-0001",
                           asset_tag="ASUS-KGPE-D16-AST2050",
                           fru_file_id="KGPED16")

    # Common header: ver, internal, chassis, board, product, multirecord, pad, chk
    # area offsets in 8-byte units; 0 == not present.
    hdr_len = 8
    off = hdr_len
    chassis_off = off // 8
    off += len(chassis)
    board_off = off // 8
    off += len(board)
    product_off = off // 8

    header = bytes([
        0x01,          # format version
        0x00,          # internal use area (none)
        chassis_off,   # chassis info area
        board_off,     # board info area
        product_off,   # product info area
        0x00,          # multirecord area (none)
        0x00,          # pad
    ])
    header += bytes([(-sum(header)) & 0xFF])  # header checksum
    assert len(header) == 8

    return header + chassis + board + product


def main() -> int:
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "files", "motherboard-fru.bin")
    blob = build()
    # sanity: total must be a sane EEPROM size
    if len(blob) > 2048:
        print(f"FRU too large: {len(blob)} bytes", file=sys.stderr)
        return 1
    with open(out, "wb") as f:
        f.write(blob)
    print(f"wrote {out} ({len(blob)} bytes)")
    # dump a hex preview
    print(" ".join(f"{b:02x}" for b in blob[:32]), "...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

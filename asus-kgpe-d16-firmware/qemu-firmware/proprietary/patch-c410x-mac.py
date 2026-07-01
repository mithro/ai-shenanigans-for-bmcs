#!/usr/bin/env python3
"""Patch the Dell C410X vendor kernel to inject a valid MAC so eth0 registers
under QEMU.

The vendor ftgmac driver reads its MAC over I2C from a device this AST2400-based
machine doesn't model; the read fails and the driver bails
("Fail to get the MAC information!") with no random-MAC fallback, so eth0 never
comes up and the (running) appweb web server is unreachable. This is the one
unmodelled peripheral in an otherwise fully-booting BMC (C4).

Rather than reverse-engineer the exact I2C device, inject a valid MAC at the
driver's success/fail branch (found by disassembly). The kernel is ARMv5 (no
movw/movt), so we stash the MAC in the function's existing literal pool and load
it with pc-relative ldr. Result MAC: 00:e0:81:12:34:56 (Avocent OUI).

File offsets are into the DECOMPRESSED Image (linked at 0xC0008000).
"""
import gzip
import struct
import subprocess
import sys

MAC = bytes([0x00, 0xe0, 0x81, 0x12, 0x34, 0x56])

# (offset, expected_original_word_LE, new_word_LE) — words are little-endian u32.
PATCHES = [
    # 0x12518 bne 0x12534 (fail if iface type != 0,1) -> nop, fall through
    (0x12518, 0x1a000005, 0xe1a00000),
    # 0x1251c mov r1,r7        -> ldr r0,[pc,#0x334]  (= MAC word0 @ 0x12858)
    (0x1251c, 0xe1a01007, 0xe59f0334),
    # 0x12520 mov r2,#8        -> str r0,[r7]
    (0x12520, 0xe3a02008, 0xe5870000),
    # 0x12524 bl 0x1a9fe0      -> ldr r0,[pc,#0x330]  (= MAC word1 @ 0x1285c)
    (0x12524, 0xeb065ead, 0xe59f0330),
    # 0x12528 cmp r0,#0        -> strh r0,[r7,#4]
    (0x12528, 0xe3500000, 0xe1c700b4),
    # 0x1252c beq 0x1253c      -> b 0x1253c  (force the success path)
    (0x1252c, 0x0a000002, 0xea000002),
    # literal pool: MAC word0 = dev_addr[0..3] little-endian (00 e0 81 12)
    (0x12858, 0x00024008, struct.unpack('<I', MAC[0:4])[0]),
    # literal pool: MAC word1 = dev_addr[4..5] (34 56 00 00)
    (0x1285c, 0x00024010, struct.unpack('<I', MAC[4:6] + b'\x00\x00')[0]),
    # 0x125c0 bne 0x125d0 (take NCSI path if NCSI_support!=0) -> nop, so the
    # driver always takes the PHY path (bl 0x1c1f84). QEMU models the ftgmac100
    # MII PHY but has no NC-SI responder, so PHY mode lets eth0 register.
    (0x125c0, 0x1a000002, 0xe1a00000),
]


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: patch-c410x-mac.py <kernel.bin in> <uImage out>")
    data = bytearray(open(sys.argv[1], "rb").read())

    for off, orig, new in PATCHES:
        cur, = struct.unpack_from("<I", data, off)
        if cur != orig:
            sys.exit(f"offset 0x{off:x}: expected 0x{orig:08x}, found 0x{cur:08x} "
                     f"— aborting (wrong kernel?)")
        struct.pack_into("<I", data, off, new)
        print(f"  0x{off:06x}: 0x{orig:08x} -> 0x{new:08x}")

    raw = bytes(data)
    gz = sys.argv[2] + ".gz"
    with gzip.open(gz, "wb", compresslevel=9) as g:
        g.write(raw)
    subprocess.run(
        ["mkimage", "-A", "arm", "-O", "linux", "-T", "kernel", "-C", "gzip",
         "-a", "0x40008000", "-e", "0x40008000",
         "-n", "C410X patched (MAC inject)", "-d", gz, sys.argv[2]], check=True)
    print(f"wrote {sys.argv[2]} (MAC 00:e0:81:12:34:56 injected)")


if __name__ == "__main__":
    main()

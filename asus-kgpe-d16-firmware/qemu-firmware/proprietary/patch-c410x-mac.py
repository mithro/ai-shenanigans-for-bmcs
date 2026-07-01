#!/usr/bin/env python3
"""Patch the Dell C410X vendor kernel to inject a valid MAC so eth0 registers
under QEMU.

The vendor ftgmac driver reads an 8-byte "MAC information" blob over I2C from a
device this AST2400-based machine doesn't model; the read fails and the driver
bails ("Fail to get the MAC information!"). The blob layout (recovered by RE, see
AST2050-PERIPHERAL-MODELING.md) is:

    byte 0..5 : MAC address              -> priv+0x13c / priv+0x140
    byte 6    : PORT-ENABLE flag         -> cfg[0x225]   (cfg = priv+0x3a0)
    byte 7    : (secondary flag)         -> cfg[0x226]

At 0xc001a5b8 the probe reads cfg[0x225]; if it is 0 it calls free_netdev and
SILENTLY skips register_netdevice (no error) -> no eth0. So injecting only the
MAC bytes is not enough: byte 6 (the enable flag) must be non-zero, exactly as a
present MAC would report on real hardware.

Rather than reverse-engineer the exact I2C device, we synthesize the full blob at
the driver's success/fail branch. The kernel is ARMv5 (no movw/movt), so we stash
the two blob words in the function's existing literal pool and load them with
pc-relative ldr. Result: MAC 00:e0:81:12:34:56 (Avocent OUI) with enable byte = 1.

NOTE (correction to the earlier version of this script): 0xc001a5c0
`bne 0x125d0` is NOT an "NCSI path" branch — it is the enable gate itself
(`if cfg[0x225] != 0 -> register_netdevice`). The earlier script nop'd it, which
forced the free_netdev path unconditionally and guaranteed eth0 never registered.
We now leave that branch intact and instead set the enable byte in the blob.

File offsets are into the DECOMPRESSED Image (linked at 0xC0008000).
"""
import gzip
import struct
import subprocess
import sys

MAC = bytes([0x00, 0xe0, 0x81, 0x12, 0x34, 0x56])

# (offset, expected_original_word_LE, new_word_LE) — words are little-endian u32.
#
# The gate at 0xc001a5b8 reads cfg[0x225] (the blob's enable byte). Setting the
# enable byte lets *both* MAC0 and MAC1 register — but the kgpe-d16-bmc machine
# models only MAC0 (ASPEED_MAC0_ON); bringing up eth1 on the unmodelled MAC1 at
# 0x1e680000 corrupts the netdev and oopses in rtnl_fill_ifinfo. So instead of
# the enable byte we retarget the gate to the *MAC index* byte at cfg[0x224]
# (set to the port number at 0xc001a4e0) and register only index 0 (eth0/MAC0),
# which is the one QEMU models. (Modelling MAC1 too would let us use the real
# enable byte and register both — a future step.)
PATCHES = [
    # 0x12518 bne 0x12534 (fail if iface type != 0,1) -> nop, fall through
    (0x12518, 0x1a000005, 0xe1a00000),
    # 0x1251c mov r1,r7        -> ldr r0,[pc,#0x334]  (= blob word0 @ 0x12858)
    (0x1251c, 0xe1a01007, 0xe59f0334),
    # 0x12520 mov r2,#8        -> str r0,[r7]         (buffer[0..3] = MAC[0..3])
    (0x12520, 0xe3a02008, 0xe5870000),
    # 0x12524 bl 0x1a9fe0      -> ldr r0,[pc,#0x330]  (= blob word1 @ 0x1285c)
    (0x12524, 0xeb065ead, 0xe59f0330),
    # 0x12528 cmp r0,#0        -> strh r0,[r7,#4]     (buffer[4..5] = MAC[4..5])
    (0x12528, 0xe3500000, 0xe1c700b4),
    # 0x1252c beq 0x1253c      -> b 0x1253c  (force the success path)
    (0x1252c, 0x0a000002, 0xea000002),
    # literal pool: blob word0 = MAC[0..3] little-endian (00 e0 81 12)
    (0x12858, 0x00024008, struct.unpack('<I', MAC[0:4])[0]),
    # literal pool: blob word1 = MAC[4..5] (34 56 00 00)
    (0x1285c, 0x00024010, struct.unpack('<I', MAC[4:6] + b'\x00\x00')[0]),
    # gate: read cfg[0x224] (MAC index) instead of cfg[0x225] (enable byte)...
    (0x12868, 0x00000225, 0x00000224),
    # ...and register only when it is 0 (MAC0): bne 0x125d0 -> beq 0x125d0
    (0x125c0, 0x1a000002, 0x0a000002),
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

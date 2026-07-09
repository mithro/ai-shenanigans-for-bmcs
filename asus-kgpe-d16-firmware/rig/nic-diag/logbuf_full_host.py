#!/usr/bin/env python3
"""Runs ON the host. Read the FULL 64KB __log_buf sequentially in small 0x400 chunks
(each well within the ~2KB reliable P2A window, so few drops), merge in order, and
print every printable line. Use when a marker sits in a region the coarse reader drops."""
import subprocess

C = "/root/culvert-g3/build/src/culvert"
BASE = 0x40cffa2c
LEN = 0x10000
STEP = 0x400
buf = bytearray()
for off in range(0, LEN, STEP):
    r = subprocess.run([C, "read", "--type", "ram", hex(BASE + off), hex(STEP), "via", "p2a", "vga"],
                       capture_output=True)
    buf += r.stdout
open("/root/lb_full2.bin", "wb").write(buf)
s = subprocess.run(["strings", "-n", "6", "/root/lb_full2.bin"], capture_output=True, text=True)
for line in s.stdout.splitlines():
    print(line)

#!/usr/bin/env python3
"""Runs ON the host. The AST2050-VIC pr_warn is early in __log_buf and gets split
across the lossy P2A chunk boundaries. Read the early 24KB in small overlapping
0x400 chunks over several passes, merge, and grep for the VIC config line."""
import subprocess

C = "/root/culvert-g3/build/src/culvert"
BASE = 0x40cffa2c
SPAN = 0x6000       # 24KB (early boot region)
STEP = 0x300        # overlap: 0x400 reads stepped by 0x300 so no line is split
merged = bytearray()
for _pass in range(3):
    for off in range(0, SPAN, STEP):
        r = subprocess.run([C, "read", "--type", "ram", hex(BASE + off), "0x400", "via", "p2a", "vga"],
                           capture_output=True)
        merged += r.stdout
open("/root/vic_lb.bin", "wb").write(merged)
s = subprocess.run(["strings", "-n", "8", "/root/vic_lb.bin"], capture_output=True, text=True)
seen = set()
for line in s.stdout.splitlines():
    if any(k in line for k in ("AST2050-VIC", "SENSE", "i2c controller", "NR_IRQS", "GIC", "AVIC")):
        if line not in seen:
            seen.add(line)
            print(line)

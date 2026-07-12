#!/usr/bin/env python3
"""Runs ON the host. Read __log_buf in small chunks (the P2A read window only returns
~2KB reliably per invocation) and concatenate, so we get the full early dmesg incl. the
ftgmac100 ndo_open markers past the dead console."""
import subprocess
C = "/root/culvert-g3/build/src/culvert"
BASE = 0x40cffa2c
CHUNK = 0x800          # 2KB per read (window-safe)
NCHUNKS = 40           # 80KB span (covers the 64KB __log_buf)
out = bytearray()
for i in range(NCHUNKS):
    addr = BASE + i * CHUNK
    r = subprocess.run([C, "read", "--type", "ram", hex(addr), hex(CHUNK), "via", "p2a", "vga"],
                       capture_output=True)
    out += r.stdout
open("/root/lb_full.bin", "wb").write(out)
print(f"read {len(out)} bytes")
# extract printable strings
s = subprocess.run(["strings", "-n", "5", "/root/lb_full.bin"], capture_output=True, text=True)
for line in s.stdout.splitlines():
    print(line)

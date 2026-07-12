#!/usr/bin/env python3
"""Runs ON the host. Read the ftgmac100 TX descriptor ring over P2A and decode the
OWN bit + buffer address, to see whether the MAC is consuming queued TX descriptors."""
import subprocess
C = "/root/culvert-g3/build/src/culvert"

def rd(addr):
    r = subprocess.run([C, "p2a", "vga", "read", hex(addr)], capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip()
    hexpart = out.split(":")[-1].strip() if ":" in out else out
    try:
        return int(hexpart, 16)
    except ValueError:
        return None

txr = rd(0x1e660020)   # TXR_BADR
rxr = rd(0x1e660024)   # RXR_BADR
maccr = rd(0x1e660050)
print(f"TXR_BADR={txr:#010x} RXR_BADR={rxr:#010x} MACCR={maccr:#010x}" if txr else "read failed")
if not txr:
    raise SystemExit(1)
print("\n== TX descriptor ring ==")
for i in range(8):
    base = txr + i * 16
    d0, d1, d2, d3 = rd(base), rd(base+4), rd(base+8), rd(base+12)
    if d0 is None:
        break
    own = "MAC" if (d0 & 0x80000000) else "SW"
    fts = bool(d0 & 0x20000000); lts = bool(d0 & 0x10000000); edotr = bool(d0 & 0x40000000)
    length = d0 & 0x3fff
    print(f"  txdes[{i}] @ {base:#010x}: d0={d0:#010x} OWN={own} FTS={fts} LTS={lts} EDOTR={edotr} len={length}  buf(d3)={d3:#010x}")

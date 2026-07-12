#!/usr/bin/env python3
"""Runs ON the host. Poll TXR_BADR + MACCR + MAC_MADR in a tight loop over the whole
boot, so we can see if Linux's ndo_open ever sets up its own TX ring (a TXR_BADR that
is NOT U-Boot's 0x43fe9760 and not 0)."""
import subprocess, time
C = "/root/culvert-g3/build/src/culvert"
def rd(addr):
    r = subprocess.run([C, "p2a", "vga", "read", hex(addr)], capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip()
    h = out.split(":")[-1].strip() if ":" in out else out
    try: return int(h, 16)
    except ValueError: return None
prev = None
for i in range(70):
    txr, maccr, madr = rd(0x1e660020), rd(0x1e660050), rd(0x1e660008)
    line = f"[{i:02d}] TXR_BADR={txr:#010x} MACCR={maccr:#010x} MADR={madr:#010x}" if txr is not None else f"[{i:02d}] read-fail"
    tag = ""
    if txr not in (None, 0x43fe9760, 0x0):
        tag = "  <<< NON-UBOOT RING (Linux ndo_open set it up!)"
    if line != prev or tag:
        print(line + tag, flush=True)
        prev = line
    time.sleep(1.0)

#!/usr/bin/env python3
"""Runs ON the host. Read the ftgmac100 MAC (0x1e660000) + relevant SCU (0x1e6e2000)
registers in one culvert session, for a U-Boot-vs-Linux RX diff. eth0 RX is dead
(tx>0 rx=0) with the MAC enabled + RX ring correct + link up -> physical RX path."""
import subprocess

C = ["/root/culvert-g3/build/src/culvert", "p2a", "vga"]
MAC = 0x1e660000
SCU = 0x1e6e2000
REGS = [
    ("ISR@00", MAC + 0x00), ("IER@04", MAC + 0x04), ("MADR@08", MAC + 0x08),
    ("LADR@0c", MAC + 0x0c), ("NPTXR_BADR@20", MAC + 0x20), ("RXR_BADR@24", MAC + 0x24),
    ("ITC@30", MAC + 0x30), ("APTC@34", MAC + 0x34), ("DBLAC@38", MAC + 0x38),
    ("REVR@40", MAC + 0x40), ("FEAR@44", MAC + 0x44), ("RBSR@4c", MAC + 0x4c),
    ("MACCR@50", MAC + 0x50), ("MACSR@54", MAC + 0x54), ("PHYCR@60", MAC + 0x60),
    ("FCR@68", MAC + 0x68),
    ("SCU08", SCU + 0x08), ("SCU0C", SCU + 0x0c), ("SCU48", SCU + 0x48),
    ("SCU70", SCU + 0x70), ("SCU74", SCU + 0x74), ("SCU7C", SCU + 0x7c),
    ("SCU90", SCU + 0x90), ("SCU04", SCU + 0x04), ("SCU2C", SCU + 0x2c),
]


def rd(a):
    r = subprocess.run(C + ["read", hex(a)], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    for tok in out.replace(":", " ").split():
        if tok.startswith("0x") and len(tok) == 10:
            return tok
    return out


for name, addr in REGS:
    print(f"{name:14s} {hex(addr)}: {rd(addr)}")

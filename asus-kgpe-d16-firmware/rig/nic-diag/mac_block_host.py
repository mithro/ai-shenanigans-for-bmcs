#!/usr/bin/env python3
"""Runs ON the host. Dump the ftgmac100 MAC register block + relevant SCU/clock regs
via P2A, so we can diff U-Boot's working state vs Linux's broken state."""
import subprocess
C = "/root/culvert-g3/build/src/culvert"
MAC = 0x1e660000
# ftgmac100 register offsets (from the driver header)
OFF = {
    0x00: "ISR", 0x04: "IER", 0x08: "MAC_MADR", 0x0c: "MAC_LADR",
    0x10: "MAHT0", 0x14: "MAHT1", 0x18: "TXPD", 0x1c: "RXPD",
    0x20: "TXR_BADR", 0x24: "RXR_BADR", 0x28: "HPTXPD", 0x2c: "HPTXR_BADR",
    0x30: "ITC", 0x34: "APTC", 0x38: "DBLAC", 0x3c: "DMAFIFOS",
    0x40: "REVR", 0x44: "FEAR", 0x48: "TPAFCR", 0x4c: "RBSR",
    0x50: "MACCR", 0x54: "MACSR", 0x58: "TM", 0x5c: "RESV5c",
    0x60: "PHYCR", 0x64: "PHYDATA", 0x68: "FCR", 0x6c: "BPR",
    0x70: "RESV70", 0x74: "RESV74", 0x78: "RESV78", 0x7c: "RESV7c",
    0x80: "TS", 0x84: "GISR", 0x88: "RESV88", 0x8c: "RESV8c",
    0x90: "REVR90", 0x94: "FEAR94",
}
SCU = {  # clock / reset / pinmux relevant to MAC1 + RMII
    0x1e6e2004: "SCU04_reset", 0x1e6e2008: "SCU08_clksel", 0x1e6e200c: "SCU0C_clkstop",
    0x1e6e2048: "SCU48_macdelay", 0x1e6e2070: "SCU70_strap", 0x1e6e2074: "SCU74_pinmux",
    0x1e6e2080: "SCU80_pin", 0x1e6e2088: "SCU88_pin", 0x1e6e2090: "SCU90_pin",
}

def rd(addr):
    r = subprocess.run([C, "p2a", "vga", "read", hex(addr)], capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip()
    return out.split(":")[-1].strip() if ":" in out else out

print("### MAC block ###")
for off in sorted(OFF):
    print(f"{MAC+off:#010x} +{off:#04x} {OFF[off]:12s} {rd(MAC+off)}")
print("### SCU ###")
for addr in sorted(SCU):
    print(f"{addr:#010x} {SCU[addr]:16s} {rd(addr)}")

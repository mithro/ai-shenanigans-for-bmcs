#!/usr/bin/env python3
"""Runs ON the host. Probe the AST2050 VIC + Timer1 live state over P2A, and test
whether the VIC SENSE/EVENT/DUAL registers are actually writable (the mainline
irq-aspeed-vic driver assumes firmware configured them; the P2A reset-boot never does).

VIC base 0x1e6c0080 (interleaved low/high; low word = sources 0-31):
  IRQ_STATUS +0x00  RAW_STATUS +0x10  INT_ENABLE +0x20  INT_SENSE +0x40
  INT_DUAL_EDGE +0x48  INT_EVENT +0x50  EDGE_STATUS +0x60
Timer1 (TMC30) base 0x1e782000: count +0x00 load +0x04 match1 +0x08 control +0x30
"""
import subprocess

C = ["/root/culvert-g3/build/src/culvert", "p2a", "vga"]
VIC = 0x1e6c0080
TMR = 0x1e782000

VIC_REGS = {
    "IRQ_STATUS":  0x00, "RAW_STATUS": 0x10, "INT_SELECT": 0x18,
    "INT_ENABLE":  0x20, "INT_SENSE":  0x40, "INT_DUAL":   0x48,
    "INT_EVENT":   0x50, "EDGE_STATUS": 0x60,
}
TMR_REGS = {"T1_COUNT": 0x00, "T1_LOAD": 0x04, "T1_MATCH1": 0x08, "CONTROL": 0x30}


def rd(addr):
    r = subprocess.run(C + ["read", hex(addr)], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def wr(addr, val):
    subprocess.run(C + ["write", hex(addr), hex(val)], capture_output=True, text=True)


def bit16(hexstr):
    """Extract the last 0x... token and report bit16."""
    for tok in hexstr.replace(",", " ").split():
        if tok.startswith("0x"):
            try:
                v = int(tok, 16)
                return f"{tok} bit16={'1' if v & (1 << 16) else '0'}"
            except ValueError:
                pass
    return hexstr


print("== alive check: SCU 0x1e6e207c (expect 0x...0202) ==")
print("  SCU7C:", rd(0x1e6e207c))

print("\n== live VIC state ==")
for name, off in VIC_REGS.items():
    print(f"  {name:12s} @ {hex(VIC+off):>10s}:", bit16(rd(VIC + off)))

print("\n== live Timer1 state ==")
for name, off in TMR_REGS.items():
    print(f"  {name:12s} @ {hex(TMR+off):>10s}:", rd(TMR + off))

print("\n== CONTROL: is P2A write working AT ALL right now? DRAM scratch 0x41234000 ==")
print("  before  :", rd(0x41234000))
wr(0x41234000, 0xDEADBEEF)
print("  after wr:", rd(0x41234000), "(expect 0xdeadbeef if P2A write works)")

print("\n== Can P2A reach the 0x1e6c0000 VIC region? read a 0x40-span ==")
for off in range(0, 0x80, 0x10):
    print(f"  0x1e6c00{off:02x}:", rd(0x1e6c0000 + off))

print("\n== WRITABILITY TEST on VIC INT_ENABLE (0x1e6c00a0, R/W) ==")
print("  before        :", rd(VIC + 0x20))
wr(VIC + 0x20, 0x00010000)     # try to enable source 16 (timer)
print("  after 0x00010000:", rd(VIC + 0x20))

print("\n== WRITABILITY TEST on INT_SENSE (0x1e6c00c0) ==")
print("  before        :", rd(VIC + 0x40))
wr(VIC + 0x40, 0xA5A5A5A5)
print("  after 0xA5A5A5A5:", rd(VIC + 0x40))

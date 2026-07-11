#!/usr/bin/env python3
"""HW-agent: dump the FULL ftgmac100 MAC register file (0x1e660000..0x1e6600cc)
over P2A while the board runs (U-Boot or Linux). Decodes MACCR speed/enable bits
and the MAC's own RX statistics counters (0xb0..0xc8). The RX counters are the
decisive read: if RX-total / RX-CRC-err / RX-runt are all zero after traffic the
MAC RX engine saw NOTHING on the wire (clock/RMII); if CRC-err/runt climb the MAC
IS clocking frames in but mis-sampling them (speed/RMII-timing mismatch).

Read-only (pure culvert p2a reads). Safe to run concurrently with other probing.
"""
import subprocess
import sys

PI = "asus-bmc"
HOST = "root@192.168.77.138"
C = "/root/culvert-g3/build/src/culvert p2a vga"
MAC = 0x1e660000

# name -> offset
REGS = [
    ("ISR",      0x00), ("IER",      0x04), ("MAC_MADR", 0x08), ("MAC_LADR", 0x0c),
    ("MAHT0",    0x10), ("MAHT1",    0x14), ("NPTXPD",   0x18), ("RXPD",     0x1c),
    ("NPTXR_BADR",0x20),("RXR_BADR", 0x24), ("HPTXPD",   0x28), ("HPTXR_BADR",0x2c),
    ("ITC",      0x30), ("APTC",     0x34), ("DBLAC",    0x38), ("DMAFIFOS", 0x3c),
    ("REVR",     0x40), ("FEAR",     0x44), ("TPAFCR",   0x48), ("RBSR",     0x4c),
    ("MACCR",    0x50), ("MACSR",    0x54), ("TM",       0x58), ("PHYCR",    0x60),
    ("PHYDATA",  0x64), ("FCR",      0x68), ("BPR",      0x6c),
    ("NPTXR_PTR",0x90), ("HPTXR_PTR",0x94), ("RXR_PTR",  0x98),
    ("TX_pkts",  0xa0), ("TX_MCOL_SCOL",0xa4), ("TX_ECOL_FAIL",0xa8), ("TX_LCOL_UND",0xac),
    ("RX_pkts",  0xb0), ("RX_BC",    0xb4), ("RX_MC",    0xb8), ("RX_PF_AEP",0xbc),
    ("RX_RUNT",  0xc0), ("RX_CRCER_FTL",0xc4), ("RX_COL_LOST",0xc8),
]

MACCR_BITS = [
    (0,"TXDMA_EN"),(1,"RXDMA_EN"),(2,"TXMAC_EN"),(3,"RXMAC_EN"),(4,"RM_VLAN"),
    (5,"HPTXR_EN"),(6,"LOOP_EN"),(7,"ENRX_IN_HALFTX"),(8,"FULLDUP"),(9,"GIGA_MODE"),
    (10,"CRC_APD"),(11,"PHY_LINK_LEVEL"),(12,"RX_RUNT"),(13,"JUMBO_LF"),(14,"RX_ALL"),
    (15,"HT_MULTI_EN"),(16,"RX_MULTIPKT"),(17,"RX_BROADPKT"),(18,"DISCARD_CRCERR"),
    (19,"FAST_MODE"),(31,"SW_RST"),
]


def host(script, timeout=150):
    pi_cmd = (f"sshpass -p systemrescue ssh -o StrictHostKeyChecking=no "
              f"-o ConnectTimeout=20 {HOST} bash -s")
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                           PI, pi_cmd], input=script, capture_output=True, text=True,
                          timeout=timeout)


def main() -> int:
    lines = [f'printf "%s=" "{n}"; {C} read {MAC+off:#x} 4' for n, off in REGS]
    r = host("\n".join(lines))
    if r.returncode != 0:
        print("FAILED rc=", r.returncode)
        print("STDOUT:\n" + r.stdout)
        print("STDERR:\n" + r.stderr)
        return 1
    vals = {}
    print("=== ftgmac100 MAC register file (real AST2050, P2A) ===")
    for ln in r.stdout.splitlines():
        print(ln)
        if "=0x" in ln:
            name, hx = ln.split("=0x", 1)
            try:
                vals[name.strip()] = int(hx.strip(), 16)
            except ValueError:
                pass
    if r.stderr.strip():
        print("--- stderr ---\n" + r.stderr)

    maccr = vals.get("MACCR")
    if maccr is not None:
        on = [nm for b, nm in MACCR_BITS if maccr & (1 << b)]
        print(f"\nMACCR=0x{maccr:08x} bits: {', '.join(on)}")
        print(f"  SPEED: {'100M (FAST_MODE)' if maccr&(1<<19) else ('1G (GIGA)' if maccr&(1<<9) else '10M (!! FAST_MODE clear)')}")
        print(f"  DUPLEX: {'full' if maccr&(1<<8) else 'half'}")
        print(f"  RX path: RXMAC_EN={bool(maccr&8)} RXDMA_EN={bool(maccr&2)}")
    for nm in ("RX_pkts","RX_BC","RX_RUNT","RX_CRCER_FTL","RX_COL_LOST","TX_pkts"):
        if nm in vals:
            print(f"  counter {nm:14s}= {vals[nm]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

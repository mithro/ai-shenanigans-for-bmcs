#!/usr/bin/env python3
"""N1 probe: read the ftgmac100 MAC RX state on the real AST2050 over P2A while
Linux is running, to see if the MAC ever DMAs a received frame.

Reads (via culvert p2a vga on the PXE host):
  - MACCR (0x1e660050)      : RX/TX enable state
  - RXR_BADR (0x1e660024)   : RX descriptor ring base (DRAM addr)
  - DMAFIFOS (0x1e66003c)   : DMA/FIFO state
  - MAC_MADR/LADR           : is the MAC address programmed (Linux up)?
  - the RX descriptor ring  : per-descriptor RXDES0 (OWN/RXPKT_RDY bit31)
If the board is in Linux (MACCR RX enabled) and no descriptor shows RXPKT_RDY
after traffic, the MAC is receiving nothing at the PHY/clock level."""
import subprocess
import sys

PI = "asus-bmc"
HOST = "root@192.168.77.138"
C = "/root/culvert-g3/build/src/culvert p2a vga"

REGS = {
    "MAC_MADR(0x08)": 0x1e660008,
    "MAC_LADR(0x0c)": 0x1e66000c,
    "RXR_BADR(0x24)": 0x1e660024,
    "DMAFIFOS(0x3c)": 0x1e66003c,
    "MACCR(0x50)":    0x1e660050,
    "MACSR(0x54)":    0x1e660054,
    "PHYCR(0x60)":    0x1e660060,
    "PHYDATA(0x64)":  0x1e660064,
    "FEAR(0x44)":     0x1e660044,
}


def host(script, timeout=120):
    pi_cmd = (f"sshpass -p systemrescue ssh -o StrictHostKeyChecking=no "
              f"-o ConnectTimeout=20 {HOST} bash -s")
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                           PI, pi_cmd], input=script, capture_output=True, text=True,
                          timeout=timeout)


def main() -> int:
    # 1. read the MAC control/RX registers
    lines = [f'echo "{name} =$({C} read {addr:#x} 4)"' for name, addr in REGS.items()]
    r = host("\n".join(lines))
    print("=== MAC RX-relevant registers (real AST2050, via P2A) ===")
    print(r.stdout)
    if r.stderr.strip():
        print("--- stderr ---\n" + r.stderr)
    # 2. parse RXR_BADR, dump the ring (8 descriptors x 16 bytes) if it looks valid
    ring = None
    for ln in r.stdout.splitlines():
        if ln.startswith("RXR_BADR"):
            hexval = ln.split("0x")[-1].strip()
            try:
                ring = int(hexval, 16)
            except ValueError:
                ring = None
    if ring and 0x40000000 <= ring < 0x44000000:
        print(f"\n=== RX descriptor ring @ {ring:#x} (8 descriptors) ===")
        r2 = host(f"{C} read {ring:#x} 128")
        print(r2.stdout)
        if r2.stderr.strip():
            print("--- stderr ---\n" + r2.stderr)
    else:
        print(f"\n[RXR_BADR = {ring!r} not a valid DRAM ring address -> "
              f"MAC likely NOT configured by Linux / board not in Linux]")
    return 0


if __name__ == "__main__":
    sys.exit(main())

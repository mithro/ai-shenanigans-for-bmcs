#!/usr/bin/env python3
"""Read Linux's RX descriptor buffers + RBSR over P2A to see if the RX ring has
valid buffers (RXDES3 bufaddr, RBSR size). If buffers are set but the MAC still
receives nothing -> RX engine/clock; if buffers are 0 -> driver ring/coherency."""
import subprocess
import sys

PI = "asus-bmc"
HOST = "root@192.168.77.138"
C = "/root/culvert-g3/build/src/culvert p2a vga"
READS = {
    "RXDES0(desc0)":        0x41b2c000,
    "RXDES1(desc0)":        0x41b2c004,
    "RXDES2(desc0)":        0x41b2c008,
    "RXDES3=bufaddr(desc0)": 0x41b2c00c,
    "RXDES3(desc1)":        0x41b2c01c,
    "RXDES3(desc2)":        0x41b2c02c,
    "RBSR(0x4c)=rxbufsz":   0x1e66004c,
    "MAHT0(0x10)":          0x1e660010,
    "MAHT1(0x14)":          0x1e660014,
    "ITC(0x30)":            0x1e660030,
    "APTC(0x34)":           0x1e660034,
    "TPAFCR(0x48)":         0x1e660048,
    "FCR(0x68)":            0x1e660068,
    "MACCR(0x50)":          0x1e660050,
}


def host(script, timeout=90):
    pi_cmd = (f"sshpass -p systemrescue ssh -o StrictHostKeyChecking=no "
              f"-o ConnectTimeout=20 {HOST} bash -s")
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                           PI, pi_cmd], input=script, capture_output=True, text=True,
                          timeout=timeout)


def main() -> int:
    lines = [f'echo "{n} =$({C} read {a:#x} 4)"' for n, a in READS.items()]
    r = host("\n".join(lines))
    print(r.stdout)
    if r.stderr.strip():
        print("--- stderr ---\n" + r.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

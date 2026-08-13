#!/usr/bin/env python3
"""N1 decisive test: inject frames at the BMC and see if the ftgmac100 MAC ever
DMAs a received frame into its RX ring (RXDES0 bit31 RXPKT_RDY) or advances.

The Pi can't ARP-resolve the BMC (RX dead -> no ARP reply), so we install a
static ARP entry, then flood ICMP at the BMC MAC. Frames go on the wire; if the
MAC receives, a descriptor fills. Read the ring + MACSR over P2A before/after."""
import subprocess
import sys

PI = "asus-bmc"
HOST = "root@192.168.77.138"
C = "/root/culvert-g3/build/src/culvert p2a vga"
BMC_IP = "192.168.66.2"
BMC_MAC = "96:0e:ce:b9:5d:8d"
RING = 0x41b2c000


def host(script, timeout=150):
    pi_cmd = (f"sshpass -p systemrescue ssh -o StrictHostKeyChecking=no "
              f"-o ConnectTimeout=20 {HOST} bash -s")
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                           PI, pi_cmd], input=script, capture_output=True, text=True,
                          timeout=timeout)


def pi(cmd, timeout=60):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                           PI, cmd], capture_output=True, text=True, timeout=timeout)


def read_ring(tag):
    # read RXDES0 of 8 descriptors (16 bytes each) + MACSR + DMAFIFOS + RXR_BADR
    lines = [f'echo "RXDES0[{i}]=$({C} read {RING + i*16:#x} 4)"' for i in range(8)]
    lines.append(f'echo "MACSR(0x54)=$({C} read 0x1e660054 4)"')
    lines.append(f'echo "DMAFIFOS(0x3c)=$({C} read 0x1e66003c 4)"')
    lines.append(f'echo "RXR_BADR(0x24)=$({C} read 0x1e660024 4)"')
    r = host("\n".join(lines))
    print(f"=== RX ring / status [{tag}] ===")
    print(r.stdout)
    if r.stderr.strip():
        print("--- stderr ---\n" + r.stderr)


def main() -> int:
    read_ring("BEFORE traffic")
    print(">>> install static ARP for the BMC + flood 800 frames at it")
    r = pi(f"sudo ip neigh replace {BMC_IP} lladdr {BMC_MAC} dev eth-bmc && "
           f"sudo ping -f -c 800 -W1 {BMC_IP}; echo '--- ping done (loss expected) ---'; "
           f"ip -s link show eth-bmc | tail -4")
    print(r.stdout[-800:])
    if r.stderr.strip():
        print("--- pi stderr ---\n" + r.stderr[-400:])
    read_ring("AFTER 800 frames")
    print("\n[interpretation] If every RXDES0 stayed 0x00000000 and RXR_BADR "
          "unchanged after 800 frames -> the MAC received NOTHING (RX dead at "
          "PHY/clock level). If any RXDES0 bit31 set or ring advanced -> MAC does "
          "receive (bug is downstream: driver/coherency).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

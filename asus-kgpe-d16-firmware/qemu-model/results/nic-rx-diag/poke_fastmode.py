#!/usr/bin/env python3
"""HW-agent poke-and-observe: test whether MACCR FAST_MODE (bit19, 100M timing)
is the eth0-RX fix. The live MAC shows RX_pkts climbing but ~every frame counted
as CRC/FTL error while FAST_MODE is CLEAR (MAC at 10M) though the link is 100M.

Experiment: baseline the MAC RX stat counters, flood; then SET FAST_MODE via P2A,
flood again; compare the delta of good frames (RX_pkts) vs error frames
(RX_CRCER_FTL). If, with FAST_MODE set, RX_pkts climbs but CRC/FTL errors do NOT,
the frames are now sampled correctly -> the speed bit is the mechanism.

STATE-MUTATING: one MACCR write (MAC-only, non-destructive to flash). Coordinated.
"""
import subprocess
import sys
import time

PI = "asus-bmc"
HOST = "root@192.168.77.138"
C = "/root/culvert-g3/build/src/culvert p2a vga"
MAC = 0x1e660000
MACCR = MAC + 0x50
BMC_IP = "192.168.66.2"
BMC_MAC = "96:0e:ce:b9:5d:8d"
FAST_MODE = 1 << 19

CNT = {  # name: offset
    "RX_pkts": 0xb0, "RX_CRCER_FTL": 0xc4, "RX_RUNT": 0xc0, "RX_BC": 0xb4,
    "RXR_PTR": 0x98, "MACCR": 0x50, "MACSR": 0x54,
}


def host(script, timeout=180):
    pi_cmd = (f"sshpass -p systemrescue ssh -o StrictHostKeyChecking=no "
              f"-o ConnectTimeout=20 {HOST} bash -s")
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                           PI, pi_cmd], input=script, capture_output=True, text=True,
                          timeout=timeout)


def pi(cmd, timeout=90):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                           PI, cmd], capture_output=True, text=True, timeout=timeout)


def read_counters(tag):
    lines = [f'printf "%s=" "{n}"; {C} read {MAC+off:#x} 4' for n, off in CNT.items()]
    r = host("\n".join(lines))
    vals = {}
    for ln in r.stdout.splitlines():
        # line format: "NAME=0xADDR: 0xVALUE"
        if "=" in ln and ": 0x" in ln:
            nm = ln.split("=", 1)[0].strip()
            val = ln.rsplit(": ", 1)[-1].strip()
            try:
                vals[nm] = int(val, 16)
            except ValueError:
                pass
    print(f"--- counters [{tag}] ---")
    for n in CNT:
        if n in vals:
            v = vals[n]
            extra = ""
            if n == "RX_CRCER_FTL":
                extra = f"  (CRCerr_lo={v & 0xffff}, FTL_hi={(v >> 16) & 0xffff})"
            print(f"  {n:14s}= 0x{v:08x} ({v}){extra}")
    if r.stderr.strip():
        print("  stderr:", r.stderr.strip()[:200])
    return vals


def flood(n=600):
    r = pi(f"sudo ip neigh replace {BMC_IP} lladdr {BMC_MAC} dev eth-bmc && "
           f"sudo ping -f -c {n} -W1 {BMC_IP} | tail -3; echo done")
    print(f"  [flood {n}] {r.stdout.strip()[-200:]}")


def main() -> int:
    b0 = read_counters("BEFORE, FAST_MODE as-is")
    print(">>> flood #1 (FAST_MODE unchanged)")
    flood()
    b1 = read_counters("AFTER flood #1")

    maccr = b1.get("MACCR", b0.get("MACCR"))
    if maccr is None:
        print("could not read MACCR; abort")
        return 1
    new = maccr | FAST_MODE
    print(f"\n>>> SET FAST_MODE: MACCR 0x{maccr:08x} -> 0x{new:08x}")
    host(f"{C} write {MACCR:#x} {new:#x}")
    time.sleep(0.5)
    chk = read_counters("AFTER setting FAST_MODE")
    print(">>> flood #2 (FAST_MODE now set)")
    flood()
    b2 = read_counters("AFTER flood #2")

    def d(a, b, k):
        return b.get(k, 0) - a.get(k, 0)

    print("\n=== DELTAS ===")
    print(f"flood#1 (10M): RX_pkts +{d(b0,b1,'RX_pkts')}, "
          f"CRCer_lo +{(b1.get('RX_CRCER_FTL',0)&0xffff)-(b0.get('RX_CRCER_FTL',0)&0xffff)}, "
          f"FTL_hi +{((b1.get('RX_CRCER_FTL',0)>>16)&0xffff)-((b0.get('RX_CRCER_FTL',0)>>16)&0xffff)}")
    print(f"flood#2 (FAST_MODE set): RX_pkts +{d(chk,b2,'RX_pkts')}, "
          f"CRCer_lo +{(b2.get('RX_CRCER_FTL',0)&0xffff)-(chk.get('RX_CRCER_FTL',0)&0xffff)}, "
          f"FTL_hi +{((b2.get('RX_CRCER_FTL',0)>>16)&0xffff)-((chk.get('RX_CRCER_FTL',0)>>16)&0xffff)}")
    print("\n[interpretation] If flood#2 RX_pkts climbs but CRCer/FTL stay ~flat, "
          "FAST_MODE (100M timing) is the fix. Also check if the BMC now answers ping:")
    r = pi(f"ping -c3 -W1 {BMC_IP} | tail -3")
    print(r.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

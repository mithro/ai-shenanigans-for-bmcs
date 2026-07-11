#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""F-HWPASS real-hardware capture.

Two capture halves, both READ-ONLY:

* **board** — IPMI-over-LAN against the live AST2050 BMC (192.168.66.2) from the
  Pi bridge (asus-bmc): the F5 command suite + power-STATUS + SOL front-end +
  sensors. Warms up the socket-activated netipmid first (F5's race).
* **host** — the KGPE-D16 x86 host (SystemRescue, 192.168.77.138) reached through
  the Pi: proves it is powered ON (so the W83795 rails are live and there is a
  live host-side KCS peer) and probes the host-side IPMI/KCS hardware readiness
  (SuperIO KCS @ 0xca2, /dev/ipmi*, ipmitool -I open).

  uv run hwpass-realhw-capture.py --which both --evidence-dir evidence/real-hw-hwpass
"""
import argparse
import os
import subprocess
import sys
import time

PI = "asus-bmc"
BOARD = "192.168.66.2"
HOST = "192.168.77.138"
HOST_PW = "systemrescue"

BOARD_SUITE = [
    ("mc-info", ["mc", "info"]),
    ("lan-print", ["lan", "print", "1"]),
    ("chassis-status", ["chassis", "status"]),
    ("chassis-power-status", ["chassis", "power", "status"]),
    ("sdr-elist", ["sdr", "elist"]),
    ("sel-info", ["sel", "info"]),
    ("sel-list", ["sel", "list"]),
    ("user-list", ["user", "list", "1"]),
    ("fru-print0", ["fru", "print", "0"]),
    ("sol-info", ["sol", "info", "1"]),
    ("sol-payload-status", ["sol", "payload", "status", "1", "1"]),
]


def pi_sh(cmd, timeout=40):
    r = subprocess.run(
        ["ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", PI, cmd],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", "replace")


def ipmi(args, user, pw, timeout=25, retries=4):
    cmd = (f"timeout {timeout} ipmitool -I lanplus -H {BOARD} -U {user} "
           f"-P {pw} -C 17 " + " ".join(args))
    rc, out = 124, ""
    for a in range(retries):
        try:
            rc, out = pi_sh(cmd, timeout=timeout + 15)
        except subprocess.TimeoutExpired:
            rc, out = 124, "[ssh/ipmitool timeout]"
        if rc == 0:
            return rc, out
        time.sleep(2.0 * (a + 1))
    return rc, out


def host_sh(remote, timeout=45):
    inner = (f"timeout -s KILL 25 sshpass -p {HOST_PW} ssh -n -T "
             f"-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
             f"-o ConnectTimeout=8 -o ServerAliveInterval=3 "
             f"-o ServerAliveCountMax=2 -o PreferredAuthentications=password "
             f"-o PubkeyAuthentication=no root@{HOST} " + repr(remote))
    r = subprocess.run(
        ["ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=12", PI, inner],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", "replace")


def save(evidence_dir, slug, header, text, rc):
    os.makedirs(evidence_dir, exist_ok=True)
    p = os.path.join(evidence_dir, f"{slug}.txt")
    with open(p, "w") as f:
        f.write(f"$ {header}\n# exit code: {rc}\n\n{text}\n")
    first = next((l.strip() for l in text.splitlines()
                  if l.strip() and not l.startswith("$")), "")
    print(f"[{'ok ' if rc == 0 else f'rc{rc}'}] {slug:<22} {first[:66]}")
    return p


def capture_board(evidence_dir, user, pw):
    print(f"[board] warm up netipmid on {BOARD} ...")
    for i in range(8):
        rc, _ = ipmi(["mc", "info"], user, pw, retries=1)
        if rc == 0:
            print(f"[board] netipmid warm after {i + 1} probe(s)")
            break
        time.sleep(3)
    for slug, args in BOARD_SUITE:
        rc, out = ipmi(args, user, pw)
        save(evidence_dir, f"board-{slug}",
             "ipmitool -I lanplus -H %s -U %s -P <pw> -C 17 %s"
             % (BOARD, user, " ".join(args)), out, rc)


def capture_host(evidence_dir):
    print(f"[host] probe KGPE-D16 x86 host {HOST} (SystemRescue) ...")
    probes = [
        ("host-uname", "uname -a; cat /proc/uptime; echo '--- powered ON (culvert P2A peer) ---'"),
        ("host-ipmi-devs", "ls -la /dev/ipmi* 2>&1; lsmod | grep -iE 'ipmi|kcs' 2>&1; echo rc=$?"),
        ("host-ipmi-si", "dmesg 2>/dev/null | grep -iE 'ipmi|kcs|IPMI System Interface' | tail -20; echo '--- /proc/ioports 0xca ---'; grep -iE 'ca[0-9]|ipmi' /proc/ioports 2>&1"),
        ("host-dmidecode-ipmi", "dmidecode -t 38 2>&1 | head -30"),
        ("host-ipmitool-open", "which ipmitool && timeout 15 ipmitool -I open mc info 2>&1 | head -25 || echo 'ipmitool/-I open unavailable'"),
        ("host-w83795-smbus", "which sensors 2>&1; timeout 10 sensors 2>&1 | head -30; echo '--- i2c ---'; ls /dev/i2c* 2>&1"),
    ]
    for slug, cmd in probes:
        try:
            rc, out = host_sh(cmd)
        except subprocess.TimeoutExpired:
            rc, out = 124, "[host ssh timeout]"
        save(evidence_dir, slug, f"(host {HOST}) {cmd}", out, rc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", choices=["board", "host", "both"], default="both")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="0penBmc")
    ap.add_argument("--evidence-dir", default="evidence/real-hw-hwpass")
    args = ap.parse_args()
    if args.which in ("board", "both"):
        capture_board(args.evidence_dir, args.user, args.password)
    if args.which in ("host", "both"):
        capture_host(args.evidence_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

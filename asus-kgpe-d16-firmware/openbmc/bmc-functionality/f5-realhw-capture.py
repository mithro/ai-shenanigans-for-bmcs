#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""F5 real-hardware evidence capture — IPMI-over-LAN off the live AST2050.

Runs ``ipmitool -I lanplus`` **on the Pi bridge** (``asus-bmc``, 192.168.66.1)
against the real board's ``netipmid`` (default 192.168.66.2), issues the same
IPMI command suite the QEMU harness (``f5-ipmi-test.py``) runs, saves each raw
output under ``--evidence-dir``, and reports which commands answered over RMCP+.

The Pi is the only host with a route to the board's 192.168.66.0/24 BMC network
*and* it has ``ipmitool`` installed, so all IPMI is issued there and the text is
streamed back over SSH.  This is **read-only** except for the optional
``--power-cycle`` demo (guarded, off by default): it does not reset or reflash
the board by default — it queries a board already booted on the lean IPMI
daemon set (F5 ``lan`` mask profile: bmcweb masked, the IPMI stack kept).

  uv run f5-realhw-capture.py --pi asus-bmc --board 192.168.66.2 \
      --user root --password 0penBmc --evidence-dir evidence/real-hw
"""
import argparse
import os
import subprocess
import sys
import time

# (slug, ipmitool args, required-to-pass). Only `mc info` gates PASS.
SUITE = [
    ("mc-info", ["mc", "info"], True),
    ("chassis-status", ["chassis", "status"], False),
    ("chassis-power-status", ["chassis", "power", "status"], False),
    ("lan-print", ["lan", "print", "1"], False),
    ("sel-info", ["sel", "info"], False),
    ("sel-list", ["sel", "list"], False),
    ("sdr-list", ["sdr", "list"], False),
    ("fru-print", ["fru", "print"], False),
    ("user-list", ["user", "list", "1"], False),
]


def _pi_ipmi_once(pi, board, user, password, args, timeout=25):
    remote = (f"timeout {timeout} ipmitool -I lanplus -H {board} -U {user} "
              f"-P {password} -C 17 " + " ".join(args))
    try:
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", pi, remote],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout + 20)
        return r.returncode, r.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace")
        return 124, out + f"\n[ssh/ipmitool timeout after {timeout}s]"


def pi_ipmi(pi, board, user, password, args, timeout=25, retries=4):
    """Run one ipmitool lanplus command with retry.

    netipmid on the board is socket-activated: the first RMCP+ packet after an
    idle period pays a cold-start (RAKP timeout / 'no response'), so retry a few
    times before accepting a failure.  An rc==0 is authoritative and returned
    immediately.
    """
    rc, text = 124, ""
    for attempt in range(retries):
        rc, text = _pi_ipmi_once(pi, board, user, password, args, timeout)
        if rc == 0:
            return rc, text
        time.sleep(2.0 * (attempt + 1))
    return rc, text


def capture(pi, board, user, password, evidence_dir):
    os.makedirs(evidence_dir, exist_ok=True)
    results = {}
    for slug, args, required in SUITE:
        rc, text = pi_ipmi(pi, board, user, password, args)
        results[slug] = (rc, text, required)
        out = os.path.join(evidence_dir, f"{slug}.txt")
        with open(out, "w") as f:
            f.write(f"$ ipmitool -I lanplus -H {board} -U {user} -P <pw> "
                    + " ".join(args) + "\n")
            f.write(f"# exit code: {rc}\n\n")
            f.write(text)
        tag = "rc=0" if rc == 0 else f"rc={rc}"
        print(f"[capture] ipmitool {' '.join(args):<22} -> {tag:<6} -> {out}")
    return results


def report(results):
    lines, ok = [], True
    for slug, (rc, text, required) in results.items():
        executed = rc == 0
        mark = "PASS" if executed else ("FAIL" if required else "warn")
        if required and not executed:
            ok = False
        first = ""
        for ln in text.splitlines():
            if ln.strip() and not ln.startswith("$") and not ln.startswith("#"):
                first = ln.strip()
                break
        lines.append(f"  [{mark}] {slug:<22} rc={rc}  {first[:70]}")
    return ok, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pi", default="asus-bmc")
    ap.add_argument("--board", default="192.168.66.2")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="0penBmc")
    ap.add_argument("--evidence-dir", default="evidence/real-hw")
    args = ap.parse_args()

    print(f"[real-hw] ipmitool -I lanplus on {args.pi} -> board {args.board}")
    print("[warmup] waking socket-activated netipmid (mc info until rc=0) ...")
    for i in range(8):
        rc, _ = pi_ipmi(args.pi, args.board, args.user, args.password,
                        ["mc", "info"], retries=1)
        if rc == 0:
            print(f"[warmup] netipmid warm after {i + 1} probe(s)")
            break
        time.sleep(3)
    results = capture(args.pi, args.board, args.user, args.password,
                      args.evidence_dir)
    ok, lines = report(results)
    print("\n=== F5 real-HW IPMI-over-LAN command suite ===")
    print("\n".join(lines))
    print("\nF5 REAL-HW RESULT:", "PASS — IPMI backbone over LAN (RMCP+) on the "
          "real AST2050 in 64 MB" if ok else
          "INCOMPLETE — `mc info` did not answer over RMCP+ (see .txt)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Run a diagnostic (or arbitrary) command on the live AST2050 BMC over SSH.

Reaches the board the same way the P2A boot scripts reach the x86 host: a nested
SSH through the Pi bridge (``asus-bmc``) into the board's dropbear
(``root@192.168.66.2``, password ``0penBmc``), via ``sshpass``.  Used to inspect
the IPMI daemon state on the real board (``systemctl`` / ``ss`` / ``free`` /
``journalctl``) when ``ipmitool`` from the Pi can't establish an RMCP+ session.

  uv run f5-board-diag.py                     # default IPMI-state diagnostic bundle
  uv run f5-board-diag.py --cmd "free -m"     # arbitrary command on the board
"""
import argparse
import subprocess
import sys

DEFAULT_DIAG = r"""
echo '== free -m =='; free -m
echo '== IPMI unit states =='
systemctl is-active phosphor-ipmi-host.service phosphor-ipmi-net@eth0.service \
    phosphor-ipmi-net@eth0.socket xyz.openbmc_project.Logging.IPMI.service \
    xyz.openbmc_project.State.Chassis@0.service xyz.openbmc_project.User.Manager.service \
    xyz.openbmc_project.Network.service 2>&1
echo '== udp/623 listener =='; ss -ulnp | grep -E ':623|netipmid' || echo 'NO 623 listener'
echo '== netipmid recent journal =='; journalctl -u 'phosphor-ipmi-net@eth0.service' -n 15 --no-pager 2>&1 | tail -15
echo '== ipmid recent journal =='; journalctl -u phosphor-ipmi-host.service -n 10 --no-pager 2>&1 | tail -10
echo '== OOM/killed in dmesg =='; dmesg 2>&1 | grep -iE 'oom|killed process|out of memory' | tail -5 || echo 'no OOM'
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pi", default="asus-bmc")
    ap.add_argument("--board", default="192.168.66.2")
    ap.add_argument("--password", default="0penBmc")
    ap.add_argument("--cmd", default=None, help="command to run (default: diag bundle)")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    script = args.cmd if args.cmd else DEFAULT_DIAG
    # nested: desktop -> Pi -> board (sshpass), same pattern as ddr2-init-p2a.py
    inner = ("sshpass -p " + args.password +
             " ssh -o StrictHostKeyChecking=no -o ConnectTimeout=12 root@" +
             args.board + " bash -s")
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", args.pi, inner],
        input=script, capture_output=True, text=True, timeout=args.timeout + 20)
    sys.stdout.write(r.stdout)
    if r.stderr.strip():
        sys.stderr.write("[stderr] " + r.stderr)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())

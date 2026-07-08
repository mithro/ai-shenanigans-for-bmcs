#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Staged, careful test of the AST2050 DRAM->0x0 remap over culvert P2A.

Resolves the pivotal question in P2A-DRAM-BOOT-SEQUENCE.md sec.3: does the remap
register 0x1e60008c[0] make 0x0 read as DRAM (stage1, NO reset), and does it
survive a watchdog HRST_N (stage2, needs the ported wdt reset -- not here yet).

HARD SAFETY (host-crash lesson): NEVER write 0x0 or 0x14000000 over P2A while the
remap is not confirmed live. This script only ever READS 0x0; all writes go to
DRAM (0x40000000) or backed AHB regs (0x1e6000xx). Before flipping the remap we
fill the 0x0-mapped DRAM with `b .` (0xEAFFFFFE) so a live ARM fetching 0x0 spins
harmlessly rather than executing garbage.

Runs culvert on the PXE host via the Pi bridge (asus-bmc -> host), read-only by
default. Subcommands:
  check    read-only: SCU7C, SCU70, remap reg, DRAM markers  (no writes)
  stage1   fill DRAM vectors with b., AHB-unlock, set remap, READ 0x0  (no reset)
"""
import argparse, subprocess, sys

PI = "asus-bmc"
HOST = "root@192.168.77.138"
C = "/root/culvert-g3/build/src/culvert p2a vga"

SCU7C   = 0x1e6e207c          # silicon rev (0x00000202 = AST2050)
SCU70   = 0x1e6e2070          # hw strap
DRAM    = 0x40000000          # DDR2 base (maps to 0x0 when remap set)
AHB_KEY = 0x1e600000          # AHB protection key reg
AHB_KEY_VAL = 0xaeed1a03      # unlock value
REMAP   = 0x1e60008c          # AHB_ADDR_REMAP_REG; bit0 = DRAM->0x0
BOOT0   = 0x00000000          # ARM reset vector (READ-ONLY here)
BRANCH_SELF = 0xeafffffe      # ARM `b .` -- safe infinite loop / distinctive marker


def pi(script, timeout=180):
    """Run a bash script on the PXE host, reached through the Pi."""
    host_cmd = (f"sshpass -p systemrescue ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout=20 {HOST} bash -s")
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", PI, host_cmd],
        text=True, capture_output=True, input=script, timeout=timeout)


def rd(addr):
    return f'echo -n "R {addr:#010x} = "; {C} read {addr:#x}'


def wr(addr, val):
    return f'echo "W {addr:#010x} <- {val:#010x}"; {C} write {addr:#x} {val:#x}'


def run(lines, timeout=180):
    script = "set -u\n" + "\n".join(lines) + "\n"
    r = pi(script, timeout=timeout)
    sys.stdout.write(r.stdout)
    if r.stderr.strip():
        sys.stdout.write("\n[stderr]\n" + r.stderr)
    print(f"\n[exit {r.returncode}]")
    return r.returncode


def cmd_check(_):
    print("== READ-ONLY check: rev, strap, remap reg, DRAM markers ==")
    return run([
        rd(SCU7C), rd(SCU70), rd(REMAP),
        rd(DRAM), rd(DRAM + 4),
        # NOTE: deliberately NOT reading 0x0 here -- keep this purely benign.
    ])


def cmd_stage1(_):
    print("== STAGE 1: prove DRAM->0x0 remap live (NO reset) ==")
    lines = [
        'echo "--- 1. seed the 0x0-mapped DRAM vector region with b. (safe loop) ---"',
    ]
    for i in range(8):                       # 8 ARM exception vectors 0x00..0x1c
        lines.append(wr(DRAM + i * 4, BRANCH_SELF))
    lines += [
        'echo "--- 2. read the seed back from DRAM (sanity: DDR2 alive) ---"',
        rd(DRAM), rd(DRAM + 4), rd(DRAM + 0x1c),
        'echo "--- 3. AHB unlock ---"',
        wr(AHB_KEY, AHB_KEY_VAL),
        'echo "--- 4. read remap reg before ---"',
        rd(REMAP),
        'echo "--- 5. set remap bit0 (read-modify-write) ---"',
        f'CUR=$({C} read {REMAP:#x} | grep -oE "0x[0-9a-fA-F]+" | tail -1)',
        'echo "  current REMAP=$CUR"',
        f'NEW=$(printf "0x%08x" $(( CUR | 0x1 )))',
        'echo "  writing REMAP=$NEW"',
        f'{C} write {REMAP:#x} "$NEW"',
        'echo "--- 6. read remap reg after (bit0 must be 1) ---"',
        rd(REMAP),
        'echo "--- 7. THE TEST: read 0x0 over P2A (expect 0xeafffffe = DRAM) ---"',
        rd(BOOT0), rd(BOOT0 + 4), rd(BOOT0 + 0x1c),
        'echo "--- interpretation ---"',
        'echo "  0x0 == 0xeafffffe  -> remap LIVE, 0x0 is DRAM (0x0 now safe to write)"',
        'echo "  0x0 == 0x0/0xffff.. -> remap did NOT take; 0x0 still flash. STOP."',
    ]
    return run(lines)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("stage1")
    args = ap.parse_args()
    return {"check": cmd_check, "stage1": cmd_stage1}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

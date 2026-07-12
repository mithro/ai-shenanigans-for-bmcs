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
SCU3C   = 0x1e6e203c          # System Reset Control: bit1 = watchdog-reset flag (set by wdt reset)
DRAM    = 0x40000000          # DDR2 base (maps to 0x0 when remap set)
AHB_KEY = 0x1e600000          # AHB protection key reg
AHB_KEY_VAL = 0xaeed1a03      # unlock value
REMAP   = 0x1e60008c          # AHB_ADDR_REMAP_REG (AHBC8C); bit0 = Boot Area Remap (0=flash,1=SDRAM)
BOOT0   = 0x00000000          # ARM reset vector (READ-ONLY unless remap confirms it's DRAM)
BRANCH_SELF = 0xeafffffe      # ARM `b .` -- safe infinite loop / distinctive marker

# Watchdog (WDT1 @ 0x1e785000), AST2050 datasheet sec.27.3. WDT0C[4]=1MHz clk,
# [1]=reset-system, [0]=enable. wdt_rst -> HRST_N is UNCONDITIONAL (SCU3C[3] only
# gates the external EXTRST# pin, not wdt_rst). HRST_N resets ARM + AHB controller
# (the remap) + A2P bridge, but NOT the VGA/PCI endpoint (PCI_RST_N) -> host keeps
# the PCIe device and P2A recovers. DDR2 (MMC_RST_N) also survives.
WDT_RELOAD  = 0x1e785004
WDT_RESTART = 0x1e785008
WDT_CTRL    = 0x1e78500c
WDT_MAGIC   = 0x4755
WDT_CTRL_GO = 0x13            # enable(0) | reset-system(1) | 1MHz-clock(4)
RELOAD_2S   = 2_000_000       # counter ticks; at 1MHz = 2 s (never-stopped 24MHz/24 osc)


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


def cmd_stage2(_):
    """THE pivotal test: does the remap survive a watchdog HRST_N reset?

    Assumes DDR2 is up (run ddr2-init-p2a.py first). Re-seeds + re-sets the remap,
    confirms 0x0==DRAM, then arms WDT1 for a ~2 s reset. No culvert process holds
    the bridge across the reset (each write/read is its own invocation), so there
    is no in-flight AHB transaction to stall the host; the readback invocations
    re-init the P2A bridge (== ahb_reinit_bridge). The x86 host is NOT reset by the
    BMC watchdog, so this single SSH/bash session survives to do the readback.
    """
    print("== STAGE 2: does the DRAM->0x0 remap survive a watchdog HRST_N reset? ==")
    lines = [
        'echo "--- pre: verify DDR2 alive (re-seed vectors) ---"',
    ]
    for i in range(8):
        lines.append(wr(DRAM + i * 4, BRANCH_SELF))
    lines += [
        f'SEED=$({C} read {DRAM:#x} | grep -oE "0x[0-9a-fA-F]+" | tail -1)',
        'echo "  DRAM[0]=$SEED (expect 0xeafffffe; if 0x00101000-ish, run ddr2-init-p2a.py first)"',
        f'case "$SEED" in 0x[eE][aA][fF][fF][fF][fF][fF][eE]) ;; *) echo "ABORT: DDR2 not up"; exit 2;; esac',
        'echo "--- pre: AHB unlock + set remap bit0 ---"',
        wr(AHB_KEY, AHB_KEY_VAL),
        f'{C} write {REMAP:#x} 0x1',
        rd(REMAP),
        'echo "--- pre: confirm 0x0 == DRAM (must, or we abort before resetting) ---"',
        f'B0=$({C} read {BOOT0:#x} | grep -oE "0x[0-9a-fA-F]+" | tail -1)',
        'echo "  0x0=$B0"',
        f'case "$B0" in 0x[eE][aA][fF][fF][fF][fF][fF][eE]) ;; *) echo "ABORT: remap not live"; exit 3;; esac',
        'echo "--- pre: SCU3C (bit0=power-on flag, bit1=wdt-reset flag) BEFORE reset ---"',
        rd(SCU3C),
        'echo "--- ARM the watchdog: disable, reload(2s@1MHz), restart magic, enable ---"',
        wr(WDT_CTRL, 0x0),
        wr(WDT_RELOAD, RELOAD_2S),
        wr(WDT_RESTART, WDT_MAGIC),
        wr(WDT_CTRL, WDT_CTRL_GO),
        'echo "--- watchdog armed; BMC will HRST_N in ~2 s. Sleeping 6 s (no P2A) ---"',
        'sleep 6',
        'echo "--- POST-RESET readback (fresh culvert = re-inits the P2A bridge) ---"',
        rd(SCU7C),          # chip alive + P2A survived?  expect 0x00000202
        rd(SCU3C),          # bit1 should now be 1 == watchdog reset fired
        rd(REMAP),          # 0 = cleared by HRST_N (blocked) | 1 = survived (viable!)
        rd(BOOT0),          # 0/flash = remap cleared | 0xeafffffe = remap survived
        rd(DRAM),           # should still be 0xeafffffe (DDR2 survives wdt reset)
        'echo "--- interpretation ---"',
        'echo "  SCU7C=0x202 + SCU3C bit1=1  -> watchdog fired, P2A survived (host safe)"',
        'echo "  REMAP=1 & 0x0=0xeafffffe    -> remap SURVIVED HRST_N: P2A-only boot VIABLE"',
        'echo "  REMAP=0 & 0x0=0/flash       -> remap CLEARED by HRST_N: P2A-only boot BLOCKED"',
    ]
    return run(lines, timeout=120)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("stage1")
    sub.add_parser("stage2")
    args = ap.parse_args()
    return {"check": cmd_check, "stage1": cmd_stage1, "stage2": cmd_stage2}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

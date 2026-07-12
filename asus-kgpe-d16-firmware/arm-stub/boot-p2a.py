#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Seed the ARM UART stub into AST2050 DRAM over culvert P2A, flip the DRAM->0x0
remap, and watch the BMC debug UART (/dev/serial-bmc-console) for the stub's
signature -- the P2A-independent proof the ARM ran our code.

Modes:
  live      seed stub + set remap, then WAIT. No reset, no SCU write. A firmware-
            dead ARM NOP-slides through flash(=0) and, on a prefetch abort, its PC
            returns to the low exception vectors (~1 s cycle); those are now
            DRAM-backed `b _start`, so it falls into the stub. Lowest risk.
  (clock-gate / reset modes are deferred -- need SCU70 semantics verified, see
   P2A-DRAM-BOOT-SEQUENCE.md §6a.)

Prereq: DDR2 up (run ddr2-init-p2a.py). Runs culvert on the PXE host via the Pi.
Assumes `make` has produced uart-hello.bin (auto-builds if missing).
"""
import argparse, os, struct, subprocess, sys, time

PI = "asus-bmc"
HOST = "root@192.168.77.138"
C = "/root/culvert-g3/build/src/culvert p2a vga"
BMC_TTY = "/dev/serial-bmc-console"

DRAM  = 0x40000000
AHBK  = 0x1e600000
AHBKV = 0xaeed1a03
REMAP = 0x1e60008c
BOOT0 = 0x00000000
# SCU: unlock key + the ARM-restart register.
SCU00 = 0x1e6e2000            # protection key: 0x1688a8a8 unlock, other = lock
SCU00_KEY = 0x1688a8a8
SCU70 = 0x1e6e2070            # HW trap; [1:0] = ARM boot-code sel: 10=boot SPI, 11=DISABLE ARM
# Watchdog (WDT1) for the HRST_N pulse that resets the ARM's PC to 0x0.
WDT_RELOAD, WDT_RESTART, WDT_CTRL = 0x1e785004, 0x1e785008, 0x1e78500c
WDT_MAGIC, WDT_GO, RELOAD_2S = 0x4755, 0x13, 2_000_000
SCU7C, SCU3C = 0x1e6e207c, 0x1e6e203c
HERE  = os.path.dirname(os.path.abspath(__file__))
BIN   = os.path.join(HERE, "uart-hello.bin")


def words_from_bin():
    if not os.path.exists(BIN):
        subprocess.run(["make", "-C", HERE], check=True)
    data = open(BIN, "rb").read()
    data += b"\x00" * ((-len(data)) % 4)
    return [w for (w,) in struct.iter_unpack("<I", data)]


def pi(script, timeout=180):
    host_cmd = (f"sshpass -p systemrescue ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout=20 {HOST} bash -s")
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", PI, host_cmd],
        text=True, capture_output=True, input=script, timeout=timeout)


def seed_and_remap_lines(words):
    """Shared prologue: seed the stub into DRAM and flip the DRAM->0x0 remap."""
    lines = ["set -u", 'echo "--- pre: DDR2 alive? ---"',
             f'PRE=$({C} read {DRAM:#x} | grep -oE "0x[0-9a-fA-F]+" | tail -1)',
             'echo "  DRAM[0]=$PRE"',
             'echo "--- seed stub words to DRAM 0x40000000 ---"']
    for i, w in enumerate(words):
        lines.append(f"{C} write {DRAM + i*4:#x} {w:#x}")
    lines += [
        'echo "--- read back stub[0] (expect 0xea000006) ---"',
        f'{C} read {DRAM:#x}',
        'echo "--- AHB unlock + set DRAM->0x0 remap ---"',
        f"{C} write {AHBK:#x} {AHBKV:#x}",
        f"{C} write {REMAP:#x} 0x1",
        'echo "--- confirm 0x0 == stub[0] (remap live, stub at reset vector) ---"',
        f'{C} read {BOOT0:#x}',
    ]
    return lines


def arm_restart_lines():
    """Toggle SCU70[1:0] 10->11->10: disable the ARM, then re-enable it so it
    re-boots by fetching 0x0 -- which the remap now points at DRAM. No HRST_N,
    so the remap is NOT cleared (unlike a watchdog reset). RMW preserves straps."""
    return [
        'echo "--- SCU unlock ---"',
        f"{C} write {SCU00:#x} {SCU00_KEY:#x}",
        'echo "--- SCU70 before (expect ...82, [1:0]=10 boot-SPI) ---"',
        f'{C} read {SCU70:#x}',
        f'S=$({C} read {SCU70:#x} | grep -oE "0x[0-9a-fA-F]+" | tail -1)',
        'echo "--- DISABLE ARM: SCU70[1:0]=11 (S | 0x1) ---"',
        f'DIS=$(printf "0x%08x" $(( S | 0x1 )))',
        f'{C} write {SCU70:#x} "$DIS"',
        f'{C} read {SCU70:#x}',
        'sleep 1',
        'echo "--- ENABLE/BOOT ARM: SCU70[1:0]=10 (S & ~0x1) -> fetch 0x0 = DRAM ---"',
        f'EN=$(printf "0x%08x" $(( S & ~0x1 )))',
        f'{C} write {SCU70:#x} "$EN"',
        f'{C} read {SCU70:#x}',
        'echo "--- SCU lock ---"',
        f"{C} write {SCU00:#x} 0x0",
        'echo "--- ARM re-enabled; should fetch 0x0=DRAM=stub now ---"',
    ]


def reset_boot_lines():
    """The full trick: disable the ARM (SCU70[1:0]=11, survives HRST_N) -> watchdog
    HRST_N (ARM PC->0x0 but held disabled; remap cleared; DDR2+SCU survive) ->
    re-set the remap -> enable the ARM (SCU70[1:0]=10) so it fetches 0x0=DRAM.
    The freeze holds the ARM at the reset vector while we re-establish the remap."""
    return [
        'echo "--- DISABLE ARM before reset (SCU70[1:0]=11; survives HRST_N) ---"',
        f"{C} write {SCU00:#x} {SCU00_KEY:#x}",
        f'S=$({C} read {SCU70:#x} | grep -oE "0x[0-9a-fA-F]+" | tail -1)',
        f'{C} write {SCU70:#x} $(printf "0x%08x" $(( S | 0x1 )))',
        f'{C} read {SCU70:#x}',
        f"{C} write {SCU00:#x} 0x0",
        'echo "--- arm WDT1 (2s@1MHz) for the HRST_N pulse ---"',
        f"{C} write {WDT_CTRL:#x} 0x0",
        f"{C} write {WDT_RELOAD:#x} {RELOAD_2S:#x}",
        f"{C} write {WDT_RESTART:#x} {WDT_MAGIC:#x}",
        f"{C} write {WDT_CTRL:#x} {WDT_GO:#x}",
        'echo "--- HRST_N in ~2s; sleeping 6s (no P2A) ---"',
        'sleep 6',
        'echo "--- post-reset: chip alive? wdt fired? ARM still disabled? ---"',
        f'{C} read {SCU7C:#x}',       # 0x202 = alive
        f'{C} read {SCU3C:#x}',       # bit1 = wdt fired
        f'{C} read {SCU70:#x}',       # ...83 = ARM still disabled (SCU survived)
        f'{C} read {BOOT0:#x}',       # flash(0) now (remap cleared by HRST_N)
        'echo "--- re-set the remap (0x0 -> DRAM=stub) ---"',
        f"{C} write {AHBK:#x} {AHBKV:#x}",
        f"{C} write {REMAP:#x} 0x1",
        f'{C} read {BOOT0:#x}',       # 0xea000006 = stub back at 0x0
        f'{C} read {DRAM:#x}',        # stub survived in DRAM (DDR2 kept)
        'echo "--- ENABLE ARM (SCU70[1:0]=10) -> boot 0x0=DRAM=stub ---"',
        f"{C} write {SCU00:#x} {SCU00_KEY:#x}",
        f'S2=$({C} read {SCU70:#x} | grep -oE "0x[0-9a-fA-F]+" | tail -1)',
        f'{C} write {SCU70:#x} $(printf "0x%08x" $(( S2 & ~0x1 )))',
        f'{C} read {SCU70:#x}',
        f"{C} write {SCU00:#x} 0x0",
        'echo "--- ARM enabled at PC=0x0=DRAM; watch UART ---"',
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["live", "arm-restart", "reset-boot"],
                    default="reset-boot")
    ap.add_argument("--watch", type=int, default=20, help="seconds to watch the UART")
    args = ap.parse_args()

    words = words_from_bin()
    print(f"[*] mode={args.mode}; stub = {len(words)} words ({len(words)*4} bytes); "
          f"first={words[0]:#010x} (expect 0xea000006)")

    # start the UART capture in parallel (held-open ssh so it isn't SIGHUP'd)
    subprocess.run(["ssh", "-o", "BatchMode=yes", PI,
                    f"sudo stty -F {BMC_TTY} 1200 raw -echo -crtscts cs8 -parenb -cstopb"],
                   text=True, capture_output=True)
    cap = subprocess.Popen(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", PI,
         f"sudo timeout {args.watch} cat {BMC_TTY}"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(2)

    lines = seed_and_remap_lines(words)
    if args.mode == "arm-restart":
        lines += arm_restart_lines()
    elif args.mode == "reset-boot":
        lines += reset_boot_lines()
    else:  # live: no ARM action, just wait for a slide-cycle to hit the vectors
        lines.append('echo "--- remap set; waiting for the ARM to reach a vector ---"')
    r = pi("\n".join(lines) + "\n", timeout=120)
    sys.stdout.write(r.stdout)
    if r.stderr.strip():
        sys.stdout.write("\n[stderr]\n" + r.stderr[-400:])

    print(f"\n[*] watching {BMC_TTY} for the stub signature ({args.watch}s total)...")
    try:
        out, err = cap.communicate(timeout=args.watch + 10)
    except subprocess.TimeoutExpired:
        cap.kill(); out, err = cap.communicate()
    print("=== BMC UART capture ===")
    print(out.strip() or "(nothing seen)")
    if "AST2050-ARM-ALIVE" in out:
        print("\n*** SUCCESS: the ARM ran our stub from DRAM (P2A-only boot)! ***")
    else:
        print("\n(no signature -- ARM not fetching our stub this way; see §6a clock-gate path)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

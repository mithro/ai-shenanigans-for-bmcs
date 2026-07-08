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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["live"], default="live")
    ap.add_argument("--watch", type=int, default=20, help="seconds to watch the UART")
    args = ap.parse_args()

    words = words_from_bin()
    print(f"[*] stub = {len(words)} words ({len(words)*4} bytes); first={words[0]:#010x} (expect 0xea000006)")

    # start the UART capture in parallel (held-open ssh so it isn't SIGHUP'd)
    subprocess.run(["ssh", "-o", "BatchMode=yes", PI,
                    f"sudo stty -F {BMC_TTY} 1200 raw -echo -crtscts cs8 -parenb -cstopb"],
                   text=True, capture_output=True)
    cap = subprocess.Popen(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", PI,
         f"sudo timeout {args.watch} cat {BMC_TTY}"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(2)

    # build the host seeding script
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
        'echo "--- remap set; ARM should fall into the stub within ~1-2 s ---"',
    ]
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

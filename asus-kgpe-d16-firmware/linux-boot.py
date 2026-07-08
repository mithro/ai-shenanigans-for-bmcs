#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""One-shot: bring the AST2050 BMC from cold to a Linux shell over P2A alone.

  1. ddr2-init-p2a.py        -- DDR2 up (4-bank/64MB/DLL), SCU40[6] set
  2. p2a-image-boot.py       -- load u-boot.bin into DRAM + reset-boot to `boot#`
  3. drive U-Boot over the BMC UART: static IP, initrd_high (no ramdisk reloc!),
     tftp kernel+initrd, set bootargs, bootm -> Linux

Prereq on the Pi: eth-bmc up at 192.168.66.1 + dnsmasq TFTP on it serving
/srv/tftp-bmc (see LINUX-TFTP-BOOT.md). U-Boot = tmp/raptor-uboot.bin.

  uv run linux-boot.py --watch 160
  uv run linux-boot.py --bootargs "console=ttyS1,1200n8 rdinit=/init" --watch 200
"""
import argparse, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # worktree root
PI = "asus-bmc"
BMC = "/dev/serial-bmc-console"
UBOOT = os.path.join(ROOT, "tmp", "raptor-uboot.bin")
KERNEL, INITRD = "uImage-raptor", "uInitrd-kgpe-d16"
KADDR, RADDR = 0x41000000, 0x42000000


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=isinstance(cmd, str), **kw)


def send(cmd):
    line = (cmd + "\r").replace("'", "'\\''")
    sh(["ssh", "-o", "BatchMode=yes", PI,
        f"printf '{line}' | sudo dd of={BMC} status=none"], capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootargs", default="console=ttyS1,1200n8")
    ap.add_argument("--watch", type=int, default=160)
    ap.add_argument("--gap", type=float, default=4.0)
    ap.add_argument("--skip-load", action="store_true",
                    help="skip DDR2+U-Boot load (U-Boot already at prompt)")
    args = ap.parse_args()

    if not args.skip_load:
        print("[1] DDR2 init (M1)...")
        sh(["uv", "run", os.path.join(HERE, "ddr2-init-p2a.py")],
           capture_output=True, text=True)
        print("[2] load U-Boot + reset-boot...")
        r = sh(["uv", "run", os.path.join(HERE, "p2a-image-boot.py"),
                "--image", UBOOT, "--baud", "1200", "--watch", "8"],
               capture_output=True, text=True)
        if "boot#" not in r.stdout and "U-Boot" not in r.stdout:
            print("[!] U-Boot did not reach prompt:\n", r.stdout[-500:]); return 1
        print("    U-Boot up.")

    print("[3] drive U-Boot -> tftp + bootm...")
    # start the serial capture for the whole Linux boot
    sh(["ssh", "-o", "BatchMode=yes", PI,
        f"sudo stty -F {BMC} 1200 raw -echo -crtscts cs8 -parenb -cstopb"],
       capture_output=True, text=True)
    cap = subprocess.Popen(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", PI,
                            f"sudo timeout {args.watch} cat {BMC}"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(1.5)
    seq = [
        "setenv ipaddr 192.168.66.2",
        "setenv serverip 192.168.66.1",
        "setenv initrd_high 0xffffffff",          # <-- do NOT relocate the ramdisk
        f"tftp {KADDR:#x} {KERNEL}",
        f"tftp {RADDR:#x} {INITRD}",
        f"setenv bootargs {args.bootargs}",
        f"bootm {KADDR:#x} {RADDR:#x}",
    ]
    # tftp needs longer settle; give big gaps before/after the transfers
    gaps = {3: 12.0, 4: 10.0}   # after kernel tftp, after initrd tftp
    send("")  # wake
    time.sleep(args.gap)
    for i, c in enumerate(seq):
        send(c)
        time.sleep(gaps.get(i, args.gap))
    try:
        out, _ = cap.communicate(timeout=args.watch + 8)
    except subprocess.TimeoutExpired:
        cap.kill(); out, _ = cap.communicate()
    print(out)
    for marker in ("BMC-READY", "Kernel panic", "Cannot open root", "/ #", "# "):
        if marker in out:
            print(f"\n[*] saw: {marker!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

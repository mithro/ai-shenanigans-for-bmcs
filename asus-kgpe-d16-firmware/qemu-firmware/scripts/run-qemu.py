#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Run / smoke-test the custom kgpe-d16-bmc (AST2050) QEMU machine.

Modes:
  smoke  -- instantiate `-M kgpe-d16-bmc` (CPU stopped with -S) and confirm
            QEMU creates the machine without error. Proves the machine builds
            and registers. No firmware needed.
  boot   -- boot a kernel (+optional initrd/dtb) or a flash image, capture the
            serial console, and succeed when --expect regex appears before
            --timeout. Used by the P3-P6 boot tests.

Examples:
  run-qemu.py smoke --qemu .../qemu-system-arm
  run-qemu.py boot  --qemu .../qemu-system-arm \\
      --kernel uImage --initrd uInitrd --expect 'kgpe-d16 login:' --timeout 120
"""
import argparse
import os
import selectors
import subprocess
import sys
import time

MACHINE = "kgpe-d16-bmc"


def base_cmd(args):
    cmd = [args.qemu, "-M", MACHINE, "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", "stdio"]
    if args.netdev:
        # user-net NIC with an SSH host-forward for the C2 ssh-login test
        cmd += ["-netdev", f"user,id=net0,hostfwd=tcp::{args.ssh_port}-:22",
                "-device", "ftgmac100,netdev=net0"]
    return cmd


def run_smoke(args):
    # -S keeps the CPU stopped; we just confirm the machine instantiates.
    cmd = [args.qemu, "-M", MACHINE, "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", "null", "-S", "-no-reboot"]
    # quit almost immediately via QMP-less approach: run with a tiny timeout.
    print("smoke:", " ".join(cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out, _ = p.communicate(timeout=args.timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        # Still running with -S == machine instantiated OK; that's success.
        p.terminate()
        try:
            out, _ = p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            out = b""
        print("smoke: machine instantiated and ran (stopped) OK")
        return 0
    text = (out or b"").decode("utf-8", "replace")
    if text.strip():
        print(text)
    # If QEMU exited non-zero quickly, the machine failed to create.
    if rc not in (0,):
        print(f"smoke: FAILED (qemu exited {rc})")
        return 1
    print("smoke: OK")
    return 0


def run_boot(args):
    cmd = base_cmd(args)
    if args.flash:
        cmd += ["-drive", f"file={args.flash},format=raw,if=mtd"]
    if args.kernel:
        cmd += ["-kernel", args.kernel]
    if args.initrd:
        cmd += ["-initrd", args.initrd]
    if args.dtb:
        cmd += ["-dtb", args.dtb]
    if args.append:
        cmd += ["-append", args.append]
    print("boot:", " ".join(cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         bufsize=0)
    sel = selectors.DefaultSelector()
    sel.register(p.stdout, selectors.EVENT_READ)
    deadline = time.time() + args.timeout
    captured = []
    found = False
    while time.time() < deadline:
        for _ in sel.select(timeout=1.0):
            chunk = os.read(p.stdout.fileno(), 4096)
            if not chunk:
                deadline = 0
                break
            sys.stdout.write(chunk.decode("utf-8", "replace"))
            sys.stdout.flush()
            captured.append(chunk)
            if args.expect and args.expect.encode() in b"".join(captured)[-8192:]:
                found = True
                break
        if found or p.poll() is not None:
            break
    p.terminate()
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()
    if args.expect and not found:
        print(f"\nboot: FAILED — did not see {args.expect!r} within "
              f"{args.timeout}s")
        return 1
    print(f"\nboot: OK — saw {args.expect!r}" if args.expect else "boot: ran")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["smoke", "boot"])
    ap.add_argument("--qemu", default="qemu-system-arm",
                    help="path to qemu-system-arm (the custom build)")
    ap.add_argument("--mem", default=128, type=int, help="RAM in MiB")
    ap.add_argument("--kernel")
    ap.add_argument("--initrd")
    ap.add_argument("--dtb")
    ap.add_argument("--flash", help="raw SPI flash image (if/mtd)")
    ap.add_argument("--append", help="kernel cmdline")
    ap.add_argument("--expect", help="success regex/substring on the console")
    ap.add_argument("--timeout", default=120, type=int)
    ap.add_argument("--netdev", action="store_true",
                    help="add user-net ftgmac100 NIC with SSH hostfwd")
    ap.add_argument("--ssh-port", default=2222, type=int)
    args = ap.parse_args()

    if args.mode == "smoke":
        return run_smoke(args)
    return run_boot(args)


if __name__ == "__main__":
    raise SystemExit(main())

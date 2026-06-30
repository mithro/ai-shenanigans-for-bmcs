#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""C2 test: boot the new kernel+initramfs on the kgpe-d16-bmc QEMU machine and
log in over SSH.

Boots qemu-system-arm with an FTGMAC100 NIC on QEMU user-net (hostfwd
tcp::PORT-:22), waits for dropbear to come up on the serial console, then runs
`ssh -i <test-key>` and asserts a command executes inside the guest.
"""
import argparse
import os
import selectors
import subprocess
import sys
import time


def wait_for(proc, marker, timeout):
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        if proc.poll() is not None:
            return False, buf
        for _ in sel.select(timeout=1.0):
            chunk = os.read(proc.stdout.fileno(), 4096)
            if chunk:
                sys.stdout.write(chunk.decode("utf-8", "replace"))
                sys.stdout.flush()
                buf += chunk
                if marker.encode() in buf:
                    return True, buf
    return False, buf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--initrd", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--key", required=True, help="SSH private key for root")
    ap.add_argument("--port", type=int, default=2222)
    ap.add_argument("--mem", type=int, default=128)
    ap.add_argument("--boot-timeout", type=int, default=180)
    ap.add_argument("--append",
                    default="console=ttyS4,115200n8 earlyprintk")
    args = ap.parse_args()

    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", "stdio",
           "-kernel", args.kernel, "-initrd", args.initrd, "-dtb", args.dtb,
           "-append", args.append,
           "-netdev", f"user,id=net0,hostfwd=tcp::{args.port}-:22",
           "-device", "ftgmac100,netdev=net0"]
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    try:
        up, _ = wait_for(qemu, "dropbear: listening", args.boot_timeout)
        if not up:
            print("\nFAIL: dropbear did not come up within "
                  f"{args.boot_timeout}s")
            return 1
        # Give dropbear a moment to bind.
        time.sleep(3)
        ssh = ["ssh", "-i", args.key, "-p", str(args.port),
               "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=/dev/null",
               "-o", "ConnectTimeout=10",
               "root@127.0.0.1", "echo SSH_OK; hostname; uname -sm"]
        print("\nssh:", " ".join(ssh))
        r = subprocess.run(ssh, capture_output=True, text=True, timeout=60)
        print("--- ssh stdout ---\n" + r.stdout)
        if r.stderr.strip():
            print("--- ssh stderr ---\n" + r.stderr)
        ok = r.returncode == 0 and "SSH_OK" in r.stdout and \
            "kgpe-d16-bmc" in r.stdout
        print("\nC2 RESULT:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

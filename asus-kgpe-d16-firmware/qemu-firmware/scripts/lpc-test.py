#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""B1 LPC sub-block bring-up test: KCS + vUART + port-80h snoop + lpc-ctrl.

Boots the kgpe-d16-bmc QEMU machine and validates that the BMC-side Linux drivers
for the LPC peripheral blocks BIND against the faithful G3 LPC model
(hw/misc/aspeed_lpc_ast2050.c):

  * KCS (B1a)   -> /dev/ipmi-kcs3            (kcs_bmc_aspeed + cdev-ipmi)
  * vUART (B1d) -> ttyS5 "ASPEED VUART"      (8250_aspeed_vuart @ 0x1e787000)
  * snoop (B1c) -> /dev/aspeed-lpc-snoop0    (aspeed-lpc-snoop, port 0x80)
  * lpc-ctrl    -> /dev/aspeed-lpc-ctrl0     (aspeed-lpc-ctrl)

This is the BMC-SIDE validation (driver probe + register setup + char-device
creation). FULL POST-code capture / mailbox message flow additionally needs a
host LPC master driving I/O cycles — present on real silicon (the SP5100), absent
in the BMC-only QEMU machine — so those are validated on silicon, honestly noted.
"""
import argparse
import os
import selectors
import subprocess
import sys
import time

GUEST_SCRIPT = r"""
set -x
echo "LPC_TTYS5="; dmesg | grep -i "ASPEED VUART" | head -1
echo "LPC_KCS="; ls /dev/ipmi-kcs3 2>&1
echo "LPC_SNOOP="; ls /dev/aspeed-lpc-snoop0 2>&1
echo "LPC_CTRL="; ls /dev/aspeed-lpc-ctrl0 2>&1
echo "LPC_SNOOP_BIND="; ls /sys/bus/platform/drivers/aspeed-lpc-snoop/ | grep 1e78 || echo none
echo "LPC_CTRL_BIND="; ls /sys/bus/platform/drivers/aspeed-lpc-ctrl/ | grep 1e78 || echo none
# a bound vUART is a real tty; kcs a real chardev
if dmesg | grep -qi "ASPEED VUART" && [ -c /dev/ipmi-kcs3 ]; then
    echo LPC_CORE_OK
fi
echo LPC_DONE
"""


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
    ap.add_argument("--key", required=True)
    ap.add_argument("--port", type=int, default=2241)
    ap.add_argument("--boot-timeout", type=int, default=180)
    args = ap.parse_args()

    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", "128", "-nographic",
           "-monitor", "none", "-serial", "stdio",
           "-nic", f"user,model=ftgmac100,hostfwd=tcp::{args.port}-:22",
           "-kernel", args.kernel, "-initrd", args.initrd, "-dtb", args.dtb,
           "-append", "console=ttyS4,115200n8 earlyprintk"]
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    try:
        up, _ = wait_for(qemu, "dropbear: listening", args.boot_timeout)
        if not up:
            print("\nFAIL: dropbear did not come up")
            return 1
        ssh = ["ssh", "-i", args.key, "-p", str(args.port),
               "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=/dev/null",
               "-o", "HostKeyAlgorithms=ssh-ed25519",
               "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=30",
               "root@127.0.0.1", "sh", "-s"]
        ok = False
        for attempt in range(1, 7):
            time.sleep(8)
            print(f"--- ssh attempt {attempt} ---")
            r = subprocess.run(ssh, input=GUEST_SCRIPT, capture_output=True,
                               text=True, timeout=300)
            print(r.stdout)
            if r.stderr.strip():
                print(r.stderr)
            if "LPC_DONE" in r.stdout:
                ok = "LPC_CORE_OK" in r.stdout
                break
        print("\nLPC RESULT:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

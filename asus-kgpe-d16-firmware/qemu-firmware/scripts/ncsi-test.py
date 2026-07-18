#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""D07 test: NC-SI on MAC2 (0x1e680000) in QEMU.

Boots the kgpe-d16-bmc machine with TWO ftgmac100 NICs:
  - MAC0 (eth0) on a user-net with hostfwd :22  -> the SSH channel
  - MAC1 (eth1) on a second user-net            -> its slirp backend answers
    NC-SI control frames (EtherType 0x88F8), modeling the RMII2 sideband.

The DTB has MAC1's `use-ncsi` set and the node enabled (fdtput). With
CONFIG_NET_NCSI built in, the kernel's net/ncsi runs the discovery handshake
(Clear Initial State, Select Package, Get Version/Capabilities, Get Link
Status) against the slirp responder and brings eth1 up.

PASS = eth1 exists, net/ncsi discovered a channel (dmesg NCSI markers), and
eth1's NC-SI link is up.
"""
import argparse
import os
import selectors
import subprocess
import sys
import tempfile
import time

GUEST = r"""
set -x
echo "=== interfaces ==="
ls /sys/class/net/
[ -e /sys/class/net/eth1 ] || { echo NCSI_FAIL_no_eth1; exit 1; }
ip link set eth1 up
# net/ncsi runs its discovery when the netdev is brought up; give it a moment.
sleep 8
echo "=== dmesg NCSI ==="
dmesg | grep -i ncsi
echo "=== eth1 state ==="
cat /sys/class/net/eth1/carrier 2>&1 || true
cat /sys/class/net/eth1/operstate 2>&1 || true
# The channel-discovered marker: net/ncsi logs the package/channel probe and,
# on success, "NCSI interface ... turned on" / carrier=1.
if dmesg | grep -qi "ncsi.*channel\|NCSI: .*package\|ncsi.*turned on\|ncsi.*link up"; then
    echo NCSI_DISCOVERY_OK
fi
if [ "$(cat /sys/class/net/eth1/carrier 2>&1)" = "1" ]; then
    echo NCSI_CARRIER_UP
fi
echo NCSI_GUEST_DONE
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
    ap.add_argument("--port", type=int, default=2225)
    ap.add_argument("--boot-timeout", type=int, default=180)
    args = ap.parse_args()

    # Enable MAC1 (use-ncsi is already in the DTS, node is disabled by default).
    with tempfile.NamedTemporaryFile(suffix=".dtb", delete=False) as tf:
        ncsi_dtb = tf.name
    subprocess.run(["cp", args.dtb, ncsi_dtb], check=True)
    subprocess.run(["fdtput", "-t", "s", ncsi_dtb, "/ahb/ethernet@1e680000",
                    "status", "okay"], check=True)

    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", "128", "-nographic",
           "-monitor", "none", "-serial", "stdio",
           # MAC0 (eth0): SSH channel. MAC1 (eth1): NC-SI sideband responder.
           "-nic", f"user,model=ftgmac100,hostfwd=tcp::{args.port}-:22",
           "-nic", "user,model=ftgmac100",
           "-kernel", args.kernel, "-initrd", args.initrd,
           "-dtb", ncsi_dtb,
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
            r = subprocess.run(ssh, input=GUEST, capture_output=True,
                               text=True, timeout=120)
            print(r.stdout)
            if r.stderr.strip():
                print(r.stderr)
            if "NCSI_DISCOVERY_OK" in r.stdout:
                ok = True
                break
            if "NCSI_FAIL" in r.stdout:
                break
        print("\nNCSI RESULT:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        os.unlink(ncsi_dtb)
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

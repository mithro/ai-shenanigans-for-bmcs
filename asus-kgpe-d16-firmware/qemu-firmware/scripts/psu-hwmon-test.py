#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Reproduce #198: dump the PSU (pmbus @ i2c0/0x58) hwmon on a real Linux boot to
see whether phantom in2/temp2/temp3 sensors appear (and what they read)."""
import argparse, os, selectors, subprocess, sys, time

GUEST = r"""
set +e
echo "=== i2c devices ==="
ls /sys/bus/i2c/devices/ 2>/dev/null | tr '\n' ' '; echo
echo "=== find the pmbus/psu hwmon (0x58 on i2c-0) ==="
for h in /sys/class/hwmon/hwmon*; do
    nm=$(cat "$h/name" 2>/dev/null)
    dev=$(readlink -f "$h/device" 2>/dev/null)
    echo "--- $h name=$nm device=$dev ---"
    case "$dev" in
      *0-0058*|*pmbus*|*psu*)
        echo "  [PSU HWMON]"
        for f in "$h"/in*_input "$h"/temp*_input "$h"/curr*_input "$h"/power*_input "$h"/fan*_input; do
            [ -e "$f" ] || continue
            lbl=""
            b=$(basename "$f" _input)
            [ -e "$h/${b}_label" ] && lbl=$(cat "$h/${b}_label")
            echo "  $(basename $f) = $(cat $f 2>&1)   label=$lbl"
        done
        ;;
    esac
done
echo "=== PSU_CHECK_DONE ==="
"""

def wait_for(proc, marker, timeout):
    sel = selectors.DefaultSelector(); sel.register(proc.stdout, selectors.EVENT_READ)
    deadline = time.time() + timeout; buf = b""
    while time.time() < deadline:
        if proc.poll() is not None: return False, buf
        for _ in sel.select(timeout=1.0):
            c = os.read(proc.stdout.fileno(), 4096)
            if c:
                buf += c
                if marker.encode() in buf: return True, buf
    return False, buf

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True); ap.add_argument("--kernel", required=True)
    ap.add_argument("--initrd", required=True); ap.add_argument("--dtb", required=True)
    ap.add_argument("--key", required=True); ap.add_argument("--port", type=int, default=2239)
    a = ap.parse_args()
    cmd = [a.qemu, "-M", "kgpe-d16-bmc", "-m", "128", "-nographic", "-monitor", "none",
           "-serial", "stdio", "-nic", f"user,model=ftgmac100,hostfwd=tcp::{a.port}-:22",
           "-kernel", a.kernel, "-initrd", a.initrd, "-dtb", a.dtb,
           "-append", "console=ttyS4,115200n8 earlyprintk"]
    q = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    try:
        up, _ = wait_for(q, "dropbear: listening", 180)
        if not up:
            print("FAIL: dropbear did not come up"); return 1
        ssh = ["ssh", "-i", a.key, "-p", str(a.port), "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=/dev/null", "-o", "HostKeyAlgorithms=ssh-ed25519",
               "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=30", "root@127.0.0.1", "sh", "-s"]
        for attempt in range(1, 6):
            time.sleep(6)
            r = subprocess.run(ssh, input=GUEST, capture_output=True, text=True, timeout=120)
            print(r.stdout)
            if r.stderr.strip(): print("STDERR:", r.stderr[:500])
            if "PSU_CHECK_DONE" in r.stdout: break
        return 0
    finally:
        q.terminate()
        try: q.wait(timeout=10)
        except subprocess.TimeoutExpired: q.kill()

if __name__ == "__main__":
    raise SystemExit(main())

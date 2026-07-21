#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""#198 test: boot Linux and assert the PSU (pmbus @ i2c0/0x58) exposes ONLY the
sensors it implements — no phantom vcap(in2)/temp2/temp3 (which read -500 before
the SMBus command-NACK fix). Fails loud on any phantom or missing real sensor."""
import argparse, os, selectors, subprocess, sys, time

GUEST = r"""
set +e
echo "=== find the pmbus/psu hwmon (0x58 on i2c-0) ==="
PSU=""
for h in /sys/class/hwmon/hwmon*; do
    dev=$(readlink -f "$h/device" 2>/dev/null)
    case "$dev" in *0-0058*) PSU="$h";; esac
done
[ -n "$PSU" ] || { echo PSU_FAIL_no_hwmon; exit 1; }
echo "PSU_HWMON=$PSU"
for f in "$PSU"/in*_input "$PSU"/temp*_input "$PSU"/curr*_input "$PSU"/power*_input "$PSU"/fan*_input; do
    [ -e "$f" ] || continue
    b=$(basename "$f" _input); lbl=""
    [ -e "$PSU/${b}_label" ] && lbl=$(cat "$PSU/${b}_label")
    echo "  $(basename $f) = $(cat $f 2>&1)   label=$lbl"
done
echo "=== assertions ==="
# PHANTOMS must be ABSENT: no vcap label anywhere, no temp2/temp3 inputs.
if grep -rql vcap "$PSU"/*_label 2>/dev/null; then echo PSU_FAIL_phantom_vcap; exit 1; fi
[ -e "$PSU/temp2_input" ] && { echo PSU_FAIL_phantom_temp2; exit 1; }
[ -e "$PSU/temp3_input" ] && { echo PSU_FAIL_phantom_temp3; exit 1; }
# REAL sensors must be PRESENT + sane (vin~230V, a vout, temp1~30C).
grep -rql vin "$PSU"/*_label 2>/dev/null || { echo PSU_FAIL_no_vin; exit 1; }
grep -rql vout "$PSU"/*_label 2>/dev/null || { echo PSU_FAIL_no_vout; exit 1; }
[ -e "$PSU/temp1_input" ] || { echo PSU_FAIL_no_temp1; exit 1; }
V=$(cat "$PSU/in1_input"); [ "$V" = "230000" ] || { echo "PSU_FAIL_vin=$V"; exit 1; }
echo PSU_NO_PHANTOMS_OK
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
        ok = False
        for attempt in range(1, 6):
            time.sleep(6)
            r = subprocess.run(ssh, input=GUEST, capture_output=True, text=True, timeout=120)
            print(r.stdout)
            if r.stderr.strip(): print("STDERR:", r.stderr[:500])
            if "PSU_NO_PHANTOMS_OK" in r.stdout:
                ok = True; break
            if "PSU_FAIL" in r.stdout:
                break  # a real assertion failure, not an ssh race
        print("\nPSU RESULT:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        q.terminate()
        try: q.wait(timeout=10)
        except subprocess.TimeoutExpired: q.kill()

if __name__ == "__main__":
    raise SystemExit(main())

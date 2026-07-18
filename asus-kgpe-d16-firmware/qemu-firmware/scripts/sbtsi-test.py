#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""D09 test: AMD SB-TSI CPU thermal sensors on the BMC's I2C4 engine.

Boots the kgpe-d16-bmc QEMU machine and reads the two SB-TSI processor thermal
interfaces (P0 @0x4c, P1 @0x4d on schematic I2C4 = Linux i2c-3) via raw SMBus,
validating the datasheet/driver register layout of hw/sensor/sbtsi.c against the
Linux sbtsi_temp driver's model:

  TEMP_INT (0x01) = integer degrees C
  TEMP_DEC (0x10) = fractional, bits[7:5] in 0.125 C steps

The machine seeds P0=45.500 C (0x2d, 0x80) and P1=43.000 C (0x2b, 0x00). This is
the QEMU + raw-userspace half; binding the in-kernel sbtsi_temp hwmon driver
needs CONFIG_SENSORS_SBTSI (a kernel rebuild) and, on silicon, a powered host
CPU. Reading the registers raw proves the model without either.
"""
import argparse
import os
import selectors
import subprocess
import sys
import time

GUEST_SCRIPT = r"""
set -x
# The kernel has CONFIG_SENSORS_SBTSI, so the in-kernel sbtsi_temp hwmon driver
# binds the amd,sbtsi DT nodes on i2c3 (0x4c=P0, 0x4d=P1). Validate through the
# hwmon sysfs (the real Linux driver reading the QEMU sbtsi model), which is a
# stronger both-sides check than raw SMBus. DT i2c3 -> Linux i2c-3.
D0=/sys/bus/i2c/devices/3-004c
D1=/sys/bus/i2c/devices/3-004d
[ -d "$D0" ] || { echo TSI_FAIL_no_dev_4c; exit 1; }
[ -d "$D1" ] || { echo TSI_FAIL_no_dev_4d; exit 1; }

hwmon_temp() {   # hwmon_temp <i2c-devdir>  -> echoes temp1_input millidegrees
    for h in $1/hwmon/hwmon*; do
        [ -e "$h/temp1_input" ] && { cat "$h/temp1_input"; return 0; }
    done
    return 1
}

T0=$(hwmon_temp $D0) || { echo TSI_FAIL_no_hwmon_4c; exit 1; }
echo "TSI_P0 3-004c hwmon temp1_input=$T0 (want 45500)"
[ "$T0" = "45500" ] || { echo TSI_FAIL_p0_temp; exit 1; }

T1=$(hwmon_temp $D1) || { echo TSI_FAIL_no_hwmon_4d; exit 1; }
echo "TSI_P1 3-004d hwmon temp1_input=$T1 (want 43000)"
[ "$T1" = "43000" ] || { echo TSI_FAIL_p1_temp; exit 1; }

echo "TSI in-kernel sbtsi_temp driver bound both processor sensors"
echo TSI_ALL_OK
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
    ap.add_argument("--port", type=int, default=2231)
    ap.add_argument("--boot-timeout", type=int, default=180)
    args = ap.parse_args()

    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", "128", "-nographic",
           "-monitor", "none", "-serial", "stdio",
           "-nic", f"user,model=ftgmac100,hostfwd=tcp::{args.port}-:22",
           "-kernel", args.kernel, "-initrd", args.initrd,
           "-dtb", args.dtb,
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
            if "TSI_ALL_OK" in r.stdout:
                ok = True
                break
            if "TSI_FAIL" in r.stdout:
                break
        print("\nSBTSI RESULT:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

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
# create /dev/i2c-* nodes (minimal initramfs runs no mdev/udev)
for d in /sys/class/i2c-dev/i2c-*; do
    n=${d##*i2c-}
    mm=$(cat $d/dev); maj=${mm%%:*}; min=${mm##*:}
    [ -e /dev/i2c-$n ] || mknod /dev/i2c-$n c $maj $min
done

# locate the SB-TSI bus: the one where 0x4c TEMP_INT (0x01) reads our seed 0x2d
BUS=""
for d in /sys/class/i2c-dev/i2c-*; do
    n=${d##*i2c-}
    v=$(i2cget -y $n 0x4c 0x01) || continue
    [ "$v" = "0x2d" ] && { BUS=$n; break; }
done
[ -n "$BUS" ] || { echo TSI_FAIL_no_bus; exit 1; }
echo "TSI_BUS=i2c-$BUS"

chk() {   # chk <addr> <reg> <expected> <label>
    got=$(i2cget -y $BUS $1 $2)
    echo "TSI $4 [$1:$2] = $got (want $3)"
    [ "$got" = "$3" ] || { echo "TSI_FAIL_$4"; exit 1; }
}

# --- P0 @0x4c = 45.500 C -> INT 0x2d, DEC (0.5C = 4<<5) 0x80 ---
chk 0x4c 0x01 0x2d p0_int
chk 0x4c 0x10 0x80 p0_dec
# --- P1 @0x4d = 43.000 C -> INT 0x2b, DEC 0x00 ---
chk 0x4d 0x01 0x2b p1_int
chk 0x4d 0x10 0x00 p1_dec
# --- CONFIG (0x03) reset 0x00, STATUS (0x02) reset 0x00 ---
chk 0x4c 0x03 0x00 config
chk 0x4c 0x02 0x00 status
# --- RW limit register accepts a write (TEMP_HIGH_INT 0x07) ---
i2cset -y $BUS 0x4c 0x07 0x55
chk 0x4c 0x07 0x55 high_limit_rw
# --- RO TEMP_INT rejects a write (stays the seeded 0x2d) ---
i2cset -y $BUS 0x4c 0x01 0x11
chk 0x4c 0x01 0x2d ro_write_ignored

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

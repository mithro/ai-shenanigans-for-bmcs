#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""D08 test: DIMM SPD/TSOD through the QU9/QU5/U23 mux fabric, full Linux stack.

Boots the kgpe-d16-bmc QEMU machine and drives the REAL driver chain the
silicon procedure uses (I2C-MUX-FABRIC-ARBITRATION.md §6):

  1. With the host OFF, the fabric is electrically absent (QU9 open): the
     DT-declared at24 SPD and jc42 TSOD fail their probe reads -> no eeprom
     node, no hwmon. This is asserted, not worked around.
  2. Power the host on in-guest via the modeled sequencer (same GPIO recipe
     as kgpe-power.sh: reclaim A4, pulse B1 low).
  3. Re-probe the devices (deferred probing does not retry on power events;
     same re-bind step the silicon procedure needs), then:
       - i2c-mux-gpio child adapter for chan 2 exists (bank Y2 = DIMM A-D)
       - at24 exposes /sys/.../eeprom whose first bytes are 92 11 0b (DDR3)
       - jc42 exposes hwmon temp1_input ~ 35000 mC
  4. Power the host OFF and show a fresh SPD read fails again (gating is
     live, not cached).

PASS criteria mirror what the silicon run must produce.
"""
import argparse
import os
import selectors
import subprocess
import sys
import time

GUEST_SCRIPT = r"""
set -x
# --- resolve the aspeed gpiochip base (kgpe-power.sh recipe) ---
BASE=""
for c in /sys/class/gpio/gpiochip*; do
    if grep -q 1e780000.gpio "$c/label"; then BASE=$(cat "$c/base"); fi
done
[ -n "$BASE" ] || { echo SPD_FAIL_no_gpiochip; exit 1; }
A4=$((BASE+4)); B1=$((BASE+9)); B6=$((BASE+14)); F0=$((BASE+40))
exp() { [ -d /sys/class/gpio/gpio$1 ] || echo $1 > /sys/class/gpio/export; }
out() { echo out > /sys/class/gpio/gpio$1/direction; }
val() { echo $2 > /sys/class/gpio/gpio$1/value; }

# --- locate the mux child adapters (i2c-mux-gpio chan_id N) ---
CH2=""
for d in /sys/bus/i2c/devices/i2c-*; do
    if grep -q "chan_id 2" "$d/name" 2>/dev/null; then CH2=${d##*/i2c-}; fi
done
[ -n "$CH2" ] || { echo SPD_FAIL_no_mux_chan2; exit 1; }
echo "SPD_MUX_CH2=i2c-$CH2"

# --- host is OFF: the DT probe at boot must have FAILED (no eeprom node) ---
if [ -e /sys/bus/i2c/devices/$CH2-0051/eeprom ]; then
    echo SPD_FAIL_eeprom_present_while_host_off; exit 1
fi
echo SPD_GATED_OFF_OK

# --- power the host on (A4 reclaim + power-up pulse) ---
exp $A4; out $A4; val $A4 1
exp $B1; exp $B6; exp $F0; out $B1; out $B6; out $F0
val $B1 1; val $B6 1; val $F0 1
val $B6 0; val $B1 0; sleep 1; val $B6 1; val $B1 1
echo SPD_HOST_ON

# --- re-probe (the same re-bind the silicon procedure needs) ---
echo $CH2-0051 > /sys/bus/i2c/drivers_probe
echo $CH2-0019 > /sys/bus/i2c/drivers_probe
sleep 1
[ -e /sys/bus/i2c/devices/$CH2-0051/eeprom ] || { echo SPD_FAIL_no_eeprom_after_on; exit 1; }
HDR=$(hexdump -v -e '3/1 "%02x "' -n 3 /sys/bus/i2c/devices/$CH2-0051/eeprom)
echo "SPD_HDR=[$HDR]"
[ "$HDR" = "92 11 0b" ] || { echo SPD_FAIL_bad_header; exit 1; }
T=$(cat /sys/bus/i2c/devices/$CH2-0019/hwmon/hwmon*/temp1_input)
echo "TSOD_MC=$T"
[ "$T" -gt 30000 ] && [ "$T" -lt 40000 ] || { echo SPD_FAIL_tsod_range; exit 1; }

# --- power off: a FRESH read must fail (live gating) ---
val $F0 0; sleep 1; val $F0 1
if dd if=/sys/bus/i2c/devices/$CH2-0051/eeprom of=/dev/null bs=16 count=1 iflag=direct 2>/dev/null; then
    :
fi
# at24 caches nothing; a raw i2ctransfer-less check: re-probe must now fail
echo $CH2-0051 > /sys/bus/i2c/drivers/at24/unbind
echo $CH2-0051 > /sys/bus/i2c/drivers_probe
[ -e /sys/bus/i2c/devices/$CH2-0051/eeprom ] && { echo SPD_FAIL_still_bound_after_off; exit 1; }
echo SPD_GATED_OFF_AGAIN_OK
echo SPD_ALL_OK
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
    ap.add_argument("--port", type=int, default=2224)
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
            if "SPD_ALL_OK" in r.stdout:
                ok = True
                break
            if "SPD_FAIL" in r.stdout:
                break   # a real assertion failure, not an ssh race
        print("\nSPD RESULT:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

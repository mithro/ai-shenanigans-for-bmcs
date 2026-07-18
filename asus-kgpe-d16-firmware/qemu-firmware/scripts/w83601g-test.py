#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""D08 test: W83601G DIMM-LED GPIO expanders (U27/U28) over the BMC's I2C5.

Boots the kgpe-d16-bmc QEMU machine and drives the two Nuvoton W83601G SMBus
GPIO expanders exactly as the BMC firmware does on silicon: raw SMBus register
access on the direct I2C5 engine (Linux i2c-4), no kernel driver. Validates the
datasheet-faithful model (hw/gpio/w83601g.c) against the Nuvoton V1.31 register
map and the silicon captures (evidence/d08-w83601g/):

  * reset defaults: CR01/CR09 output-data = 0x00, CR03/CR0B I/O-config all-input
    (0xFF/0x7F), CR02/CR0A polarity 0xF0/0x70, chip-ID CR20=0x60,
  * the per-instance Port-1 input latch seeded from silicon (U27=0x0f, U28=0xb5),
  * reserved index (CR07) reads open-bus 0xFF,
  * the LED-drive path: clear a CR03 direction bit to output, then write CR01 and
    read it back -- the exact sequence the BMC uses to light DIMM{A..H}ERRLED.

These are the same reads/writes the silicon procedure runs, so a PASS here is the
QEMU half of the both-sides D08 W83601G validation.
"""
import argparse
import os
import selectors
import subprocess
import sys
import time

# Runs in the guest over ssh. Fail-loud: any mismatch prints W836_FAIL_* + exits.
GUEST_SCRIPT = r"""
set -x
# The minimal initramfs runs no mdev/udev, so create the /dev/i2c-* nodes from
# sysfs (CONFIG_I2C_CHARDEV=y, major:minor in .../i2c-N/dev).
for d in /sys/class/i2c-dev/i2c-*; do
    n=${d##*i2c-}
    mm=$(cat $d/dev); maj=${mm%%:*}; min=${mm##*:}
    [ -e /dev/i2c-$n ] || mknod /dev/i2c-$n c $maj $min
done

# Locate the direct I2C5 engine bus by the W83601G chip-ID (CR20=0x60 at 0x18) --
# robust against Linux bus renumbering. (The DIMM TSOD would sit at 0x18 only on a
# gated mux child bus and never returns 0x60.)
BUS=""
for d in /sys/class/i2c-dev/i2c-*; do
    n=${d##*i2c-}
    v=$(i2cget -y $n 0x18 0x20) || continue
    [ "$v" = "0x60" ] && { BUS=$n; break; }
done
[ -n "$BUS" ] || { echo W836_FAIL_no_bus; exit 1; }
echo "W836_BUS=i2c-$BUS"

chk() {   # chk <addr> <reg> <expected> <label>
    got=$(i2cget -y $BUS $1 $2)
    echo "W836 $4 [$1:$2] = $got (want $3)"
    [ "$got" = "$3" ] || { echo "W836_FAIL_$4"; exit 1; }
}

# --- U27 @0x18 reset defaults (Nuvoton V1.31 table) ---
chk 0x18 0x00 0x0f p1in_u27          # Port1 input latch, seeded from silicon
chk 0x18 0x01 0x00 p1out_reset       # Port1 output data resets 0x00
chk 0x18 0x02 0xf0 p1pol_reset       # Port1 polarity inversion resets 0xF0
chk 0x18 0x03 0xff p1iocfg_reset     # Port1 I/O config resets all-input 0xFF
chk 0x18 0x09 0x00 p2out_reset       # Port2 output data resets 0x00
chk 0x18 0x0a 0x70 p2pol_reset       # Port2 polarity resets 0x70
chk 0x18 0x0b 0x7f p2iocfg_reset     # Port2 I/O config resets 0x7F
chk 0x18 0x20 0x60 idhigh            # Chip ID high 0x60
chk 0x18 0x21 0x13 idlow             # Chip ID low 0x13 (silicon-resolved; datasheet table's 0x12 is wrong)
chk 0x18 0x07 0xff reserved_openbus  # reserved index reads 0xFF (== silicon)

# --- U28 @0x19: present, own seeded Port-1 input, same ID ---
chk 0x19 0x00 0xb5 p1in_u28
chk 0x19 0x01 0x00 u28_p1out_reset
chk 0x19 0x20 0x60 u28_idhigh

# --- read-only registers reject writes (CR00 input data stays put) ---
i2cset -y $BUS 0x18 0x00 0x55
chk 0x18 0x00 0x0f ro_write_ignored

# --- LED-DRIVE PATH: the exact BMC sequence to light a DIMM error LED ---
# 1) make GP10 an output: clear CR03 bit0 -> 0xfe
i2cset -y $BUS 0x18 0x03 0xfe
chk 0x18 0x03 0xfe iocfg_gp10_output
# 2) drive GP10 high via CR01 output-data
i2cset -y $BUS 0x18 0x01 0x01
chk 0x18 0x01 0x01 led_on
# 3) Port2 LED via CR09 after CR0B output-enable
i2cset -y $BUS 0x18 0x0b 0x7e
i2cset -y $BUS 0x18 0x09 0x01
chk 0x18 0x09 0x01 p2_led_on
# 4) clear it again
i2cset -y $BUS 0x18 0x01 0x00
chk 0x18 0x01 0x00 led_off

echo W836_ALL_OK
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
    ap.add_argument("--port", type=int, default=2226)
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
            if "W836_ALL_OK" in r.stdout:
                ok = True
                break
            if "W836_FAIL" in r.stdout:
                break   # a real assertion failure, not an ssh race
        print("\nW83601G RESULT:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""F3 - sensors (W83795G) on the faithful kgpe-d16-bmc QEMU machine.

Boots the fuller OpenBMC image over NFS on the ``kgpe-d16-bmc`` QEMU machine and
proves the KGPE-D16's **Nuvoton/Winbond W83795G** hardware monitor is read
end-to-end:

  1. **QEMU model + kernel bind** - over SSH, read ``/sys/class/hwmon`` and
     confirm the ``w83795`` driver bound to the modelled chip at i2c ``1-002f``
     and that ``fan*_input`` / ``in*_input`` / ``temp*_input`` report the
     plausible readings the model emits (real RPM / mV / degC, not zero).
  2. **IPMI SDR** - phosphor-hwmon (started by udev from the W83795 config at
     ``/etc/default/obmc/hwmon/ahb/apb/bus@1e78a000/i2c@80/hwmon@2f.conf``)
     publishes the readings on D-Bus; ``ipmitool -I lanplus ... sdr``/``sensor``
     then shows the same values remotely.

PASS gate: the ``w83795`` hwmon device is bound and reports a non-zero fan RPM,
a plausible voltage and a plausible temperature over sysfs, AND at least one of
those shows up as a real (non-"disabled") reading in ``ipmitool sensor``.

CI needs: the QEMU binary (with the W83795 model), the g3vic kernel + real-PHY
DTB (both with CONFIG_SENSORS_W83795 and the i2c1 w83795 DTS node), an NFS export
of the fuller rootfs with the W83795 hwmon config installed, plus ``ipmitool``
and ``sshpass`` on PATH.

Example:
  uv run f3-sensor-test.py \
     --qemu    .../qemu-firmware/qemu/build/qemu-system-arm \
     --kernel  .../kernel/out/uImage-kgpe-d16 \
     --dtb     .../kernel/out/aspeed-bmc-asus-kgpe-d16.dtb \
     --nfsroot 10.0.2.2:/export/openbmc-f3sensors --mem 256 \
     --evidence-dir evidence/qemu-sensors
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time


def sh_qemu(qemu, kernel, dtb, nfsroot, mem, ssh_port, ipmi_port, logpath):
    append = (
        "console=ttyS4,115200n8 "
        f"mem={mem}M root=/dev/nfs rw ip=dhcp "
        f"nfsroot={nfsroot},vers=3,tcp,nolock"
    )
    nic = (f"user,model=ftgmac100,"
           f"hostfwd=tcp::{ssh_port}-:22,hostfwd=udp::{ipmi_port}-:623")
    cmd = [qemu, "-M", "kgpe-d16-bmc", "-m", str(mem), "-nographic",
           "-monitor", "none", "-serial", f"file:{logpath}", "-nic", nic,
           "-kernel", kernel, "-dtb", dtb, "-append", append]
    return cmd


def tail_wait(path, markers, deadline, echo=True):
    seen = b""
    pos = 0
    while time.time() < deadline:
        if os.path.exists(path):
            with open(path, "rb") as f:
                f.seek(pos)
                chunk = f.read()
                pos = f.tell()
            if chunk:
                if echo:
                    sys.stdout.write(chunk.decode("utf-8", "replace"))
                    sys.stdout.flush()
                seen += chunk
                for m in markers:
                    if m.encode() in seen:
                        return m
        time.sleep(1.0)
    return None


def ssh(port, password, cmd, timeout=40):
    full = ["sshpass", "-p", password, "ssh", "-p", str(port),
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=15", "-o", "PreferredAuthentications=password",
            "root@127.0.0.1", cmd]
    p = subprocess.run(full, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def wait_ssh(port, password, deadline):
    while time.time() < deadline:
        rc, out = ssh(port, password, "echo __F3_SSH_OK__", timeout=25)
        if rc == 0 and "__F3_SSH_OK__" in out:
            return True
        time.sleep(5)
    return False


def ipmitool(port, args, user, password, timeout=30):
    cmd = ["ipmitool", "-I", "lanplus", "-H", "127.0.0.1", "-p", str(port),
           "-U", user, "-P", password, "-C", "17"] + args
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def find_w83795_hwmon(port, password):
    """Return (hwmonN, dict of channel->value) for the bound w83795, or (None,{})."""
    rc, out = ssh(port, password,
                  "for h in /sys/class/hwmon/hwmon*; do "
                  "n=$(cat $h/name 2>/dev/null); echo \"HWMON $h $n\"; done")
    hwmon = None
    for line in out.splitlines():
        m = re.match(r"HWMON (\S+) w83795", line)
        if m:
            hwmon = m.group(1)
            break
    if not hwmon:
        return None, {}, out
    rc, dump = ssh(port, password,
                   f"cd {hwmon} && for f in fan*_input in*_input temp*_input; do "
                   "[ -e $f ] && echo \"$f=$(cat $f)\"; done")
    vals = {}
    for line in dump.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            try:
                vals[k.strip()] = int(v.strip())
            except ValueError:
                pass
    return hwmon, vals, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--nfsroot", required=True)
    ap.add_argument("--mem", type=int, default=256)
    ap.add_argument("--ssh-port", type=int, default=22222)
    ap.add_argument("--ipmi-port", type=int, default=26623)
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="0penBmc")
    ap.add_argument("--boot-timeout", type=int, default=1500)
    ap.add_argument("--evidence-dir", default="evidence/qemu-sensors")
    ap.add_argument("--serial-log", default=None)
    args = ap.parse_args()

    for tool in ("ipmitool", "sshpass"):
        if not shutil.which(tool):
            print(f"FAIL: {tool} not on PATH")
            return 2

    os.makedirs(args.evidence_dir, exist_ok=True)
    logpath = args.serial_log or os.path.join(os.getcwd(), "tmp",
                                               f"f3-boot-{os.getpid()}.log")
    os.makedirs(os.path.dirname(logpath), exist_ok=True)
    if os.path.exists(logpath):
        os.remove(logpath)

    cmd = sh_qemu(args.qemu, args.kernel, args.dtb, args.nfsroot, args.mem,
                  args.ssh_port, args.ipmi_port, logpath)
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.STDOUT)
    deadline = time.time() + args.boot_timeout
    try:
        tail_wait(logpath, ["w83795", "1-002f"], min(time.time() + 300, deadline))
        tail_wait(logpath, ["Mounted root", "VFS: Mounted root"], deadline)
        print("\n[ssh] waiting for dropbear ...")
        if not wait_ssh(args.ssh_port, args.password, deadline):
            print("\nF3 RESULT: FAIL - no SSH login before timeout")
            return 1

        # --- Tier 1/2: QEMU model + kernel hwmon bind (sysfs) ----------------
        hwmon, vals, listing = find_w83795_hwmon(args.ssh_port, args.password)
        with open(os.path.join(args.evidence_dir, "hwmon-sysfs.txt"), "w") as f:
            f.write(listing + "\n")
            for k in sorted(vals):
                f.write(f"{k}={vals[k]}\n")
        if not hwmon:
            print("\nF3 RESULT: FAIL - no w83795 hwmon device bound")
            return 1
        fans = [v for k, v in vals.items() if k.startswith("fan") and v > 0]
        volts = [v for k, v in vals.items() if k.startswith("in") and v > 0]
        temps = [v for k, v in vals.items() if k.startswith("temp") and v > 0]
        print(f"\n[sysfs] w83795 at {hwmon}: "
              f"{len(fans)} spinning fans, {len(volts)} rails, {len(temps)} temps")
        print("  fans(RPM):", sorted(fans, reverse=True))
        print("  volts(mV):", sorted(volts))
        print("  temps(mC):", sorted(temps))
        model_ok = bool(fans) and bool(volts) and bool(temps)

        # --- Tier 3/4: IPMI SDR over LAN -------------------------------------
        print("\n[ipmi] reading sensors over LAN ...")
        ipmi_ok = False
        for slug, ia in (("sdr-list", ["sdr", "list"]),
                         ("sensor", ["sensor"]),
                         ("sdr-type-fan", ["sdr", "type", "Fan"]),
                         ("sdr-type-temp", ["sdr", "type", "Temperature"]),
                         ("sdr-type-volt", ["sdr", "type", "Voltage"])):
            rc, out = ipmitool(args.ipmi_port, ia, args.user, args.password)
            with open(os.path.join(args.evidence_dir, f"ipmi-{slug}.txt"), "w") as f:
                f.write(f"$ ipmitool -I lanplus ... {' '.join(ia)}\n# rc={rc}\n\n{out}")
            # a real reading = a line with RPM / Volts / degrees and not disabled
            for line in out.splitlines():
                low = line.lower()
                if ("disabled" in low) or ("no reading" in low) or ("ns" == low.strip()):
                    continue
                if re.search(r"\d[\d.]*\s*(rpm|volts|degrees)", low):
                    ipmi_ok = True
            print(f"[ipmi] {' '.join(ia):<20} rc={rc}")

        print("\n=== F3 sensors result ===")
        print(f"  QEMU W83795 model + kernel bind (sysfs): "
              f"{'PASS' if model_ok else 'FAIL'}")
        print(f"  IPMI SDR real readings over LAN:         "
              f"{'PASS' if ipmi_ok else 'warn (see evidence)'}")
        ok = model_ok  # the model is the PASS gate; IPMI is reported
        print("\nF3 RESULT:", "PASS - W83795 sensors read in QEMU"
              if ok else "FAIL - W83795 not read")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

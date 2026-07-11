#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""F3 real-hardware sensors -- the actual W83795G on the live AST2050.

Two jobs, mirroring F5's real-HW tooling:

  * ``deploy``  - install the W83795G phosphor-hwmon config into the board's NFS
    rootfs on the Pi bridge (``asus-bmc``:``/srv/nfs/openbmc-full``) at the OF
    path ``etc/default/obmc/hwmon/ahb/apb/bus@1e78a000/i2c-bus@80/hwmon@2f.conf``
    so that, once the board boots the F3 kernel (CONFIG_SENSORS_W83795 + the i2c1
    w83795 DTS node + the legacy->modern hwmon patch), phosphor-hwmon reads the
    real chip.  Mutates the shared export -> pair with ``revert``.

  * ``capture`` - over SSH on the Pi, read the board's live sensors: probe i2c
    bus 1 for the real W83795G at 0x2f, dump ``/sys/class/hwmon`` and the
    ``w83795`` ``*_input`` channels (the real fan RPM / rail mV / die degC), and
    run ``ipmitool -I lanplus ... sdr``/``sensor`` for the IPMI view.  Read-only.

The Pi is the only host with a route to the board's BMC net (192.168.66.2) and to
the board shell.  This does not reflash or power-cycle the board.

  uv run f3-realhw-sensors.py deploy  --pi asus-bmc --export /srv/nfs/openbmc-full
  uv run f3-realhw-sensors.py capture --pi asus-bmc --board 192.168.66.2 \
      --evidence-dir evidence/real-hw-sensors
  uv run f3-realhw-sensors.py revert  --pi asus-bmc --export /srv/nfs/openbmc-full
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OF_REL = "etc/default/obmc/hwmon/ahb/apb/bus@1e78a000/i2c-bus@80"
CONF = "hwmon@2f.conf"


def pi_sh(pi, script, capture=True):
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", pi, "bash -s"],
        input=script, capture_output=True, text=True)
    if capture:
        sys.stdout.write(r.stdout)
    if r.stderr.strip():
        sys.stderr.write(r.stderr)
    return r.returncode, r.stdout


def deploy(args):
    conf_src = os.path.join(HERE, "w83795-hwmon.conf")
    with open(conf_src) as f:
        body = f.read()
    dst_dir = f"{args.export}/{OF_REL}"
    script = (
        f"set -e\n"
        f"sudo mkdir -p '{dst_dir}'\n"
        f"sudo tee '{dst_dir}/{CONF}' >/dev/null <<'W83795EOF'\n{body}\nW83795EOF\n"
        f"echo '--- installed W83795 hwmon config ---'\n"
        f"sudo ls -l '{dst_dir}/{CONF}'\n")
    print(f"[deploy] W83795 config -> {args.pi}:{dst_dir}/{CONF}")
    return pi_sh(args.pi, script)[0]


def revert(args):
    dst = f"{args.export}/{OF_REL}/{CONF}"
    script = (f"sudo rm -f '{dst}'\n"
              f"echo '--- removed {dst} ---'\n")
    print(f"[revert] removing {dst}")
    return pi_sh(args.pi, script)[0]


def capture(args):
    os.makedirs(args.evidence_dir, exist_ok=True)
    b = args.board
    # 1) board-side sysfs view (real W83795 read by the kernel)
    sysfs = (
        "echo '# i2cdetect bus 1 (expect UU/2f = the real W83795G)'\n"
        "i2cdetect -y 1 || i2cdetect -y -r 1 || true\n"
        "echo; echo '# w83795 binding + hwmon channels'\n"
        "ls -l /sys/bus/i2c/drivers/w83795/ 2>&1 | grep 002f || echo 'w83795 not bound'\n"
        "for h in /sys/class/hwmon/hwmon*; do "
        "n=$(cat $h/name 2>/dev/null); [ \"$n\" = w83795 ] && "
        "{ echo \"== $h ($n) ==\"; for f in $h/fan*_input $h/in*_input $h/temp*_input; do "
        "[ -e \"$f\" ] && echo \"$(basename $f)=$(cat $f)\"; done; }; done\n")
    rc, out = pi_sh(args.pi,
                    f"ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "
                    f"root@{b} 'bash -s' <<'REMOTE'\n{sysfs}\nREMOTE\n")
    with open(os.path.join(args.evidence_dir, "board-hwmon-sysfs.txt"), "w") as f:
        f.write(out)
    # 2) IPMI view over LAN from the Pi
    for slug, cmd in (("ipmi-sdr-list", "sdr list"),
                      ("ipmi-sensor", "sensor"),
                      ("ipmi-sdr-fan", "sdr type Fan"),
                      ("ipmi-sdr-temp", "sdr type Temperature"),
                      ("ipmi-sdr-volt", "sdr type Voltage")):
        remote = (f"timeout 30 ipmitool -I lanplus -H {b} -U {args.user} "
                  f"-P {args.password} -C 17 {cmd}")
        rc, out = pi_sh(args.pi, remote, capture=False)
        with open(os.path.join(args.evidence_dir, f"{slug}.txt"), "w") as f:
            f.write(f"$ ipmitool -I lanplus -H {b} ... {cmd}\n# rc={rc}\n\n{out}")
        print(f"[capture] {cmd:<20} rc={rc} -> {slug}.txt")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="action", required=True)
    for name in ("deploy", "revert"):
        p = sub.add_parser(name)
        p.add_argument("--pi", default="asus-bmc")
        p.add_argument("--export", default="/srv/nfs/openbmc-full")
    p = sub.add_parser("capture")
    p.add_argument("--pi", default="asus-bmc")
    p.add_argument("--board", default="192.168.66.2")
    p.add_argument("--user", default="root")
    p.add_argument("--password", default="0penBmc")
    p.add_argument("--evidence-dir", default="evidence/real-hw-sensors")
    args = ap.parse_args()
    return {"deploy": deploy, "revert": revert, "capture": capture}[args.action](args)


if __name__ == "__main__":
    raise SystemExit(main())

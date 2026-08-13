#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Apply / revert the F5 realhw daemon mask on the shared NFS export (real HW).

On the real AST2050 the mask must live in the **rootfs** (systemd symlink ->
/dev/null under ``/etc/systemd/system``), because U-Boot's serial-driven
``setenv bootargs`` cannot reliably carry the long ``systemd.mask=`` fragment
(F1's finding).  This mutates the *shared* Pi export
``/srv/nfs/openbmc-full`` — so it is **per-run and must be reverted** (``revert``)
once the demo boot is captured, restoring the pristine F0 rootfs.

The flash-safety masks the image ships (``obmc-flash-bmc-*``) are left untouched.

  uv run f5-realhw-mask.py apply    --pi asus-bmc --export /srv/nfs/openbmc-full
  uv run f5-realhw-mask.py revert   --pi asus-bmc --export /srv/nfs/openbmc-full
  uv run f5-realhw-mask.py status   --pi asus-bmc --export /srv/nfs/openbmc-full
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f5_masked_daemons import mask_units  # noqa: E402


def pi_sh(pi, script):
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", pi,
         "bash -s"], input=script, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.stderr.strip():
        sys.stderr.write(r.stderr)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["apply", "revert", "status"])
    ap.add_argument("--pi", default="asus-bmc")
    ap.add_argument("--export", default="/srv/nfs/openbmc-full")
    ap.add_argument("--profile", default="realhw")
    args = ap.parse_args()

    units = mask_units(args.profile)
    sysd = f"{args.export}/etc/systemd/system"

    # netipmid dual-enablement fix: the q71l image enables BOTH the standalone
    # `phosphor-ipmi-net@eth0.service` (multi-user.target.wants) AND the
    # `.socket` (sockets.target.wants).  On the slow real board the standalone
    # service starts netipmid *before* the network settles, so it runs but never
    # binds UDP/623, and socket-activation then never re-triggers (the service is
    # already "active").  Removing the standalone enablement leaves pure
    # socket-activation: the first RMCP+ packet cleanly spawns a bound netipmid.
    net_wants = f"{args.export}/etc/systemd/system/multi-user.target.wants/phosphor-ipmi-net@eth0.service"
    net_tmpl = "/usr/lib/systemd/system/phosphor-ipmi-net@.service"

    if args.action == "apply":
        cmds = "\n".join(
            f"sudo ln -sf /dev/null {sysd}/{u}" for u in units)
        script = (f"set -e\n{cmds}\n"
                  f"sudo rm -f {net_wants}   # netipmid = socket-activation only\n"
                  f"echo '--- applied {len(units)} F5 {args.profile} masks "
                  f"+ netipmid socket-only ---'\n"
                  f"ls -l {sysd} | grep -c ' -> /dev/null'\n")
        print(f"[apply] {len(units)} masks -> {sysd} (+ netipmid socket-only)")
        return pi_sh(args.pi, script)

    if args.action == "revert":
        # remove only OUR mask symlinks (leave the shipped obmc-flash-bmc-* ones)
        # and restore the standalone netipmid enablement to pristine.
        rms = "\n".join(f"sudo rm -f {sysd}/{u}" for u in units)
        script = (f"{rms}\n"
                  f"sudo ln -sf {net_tmpl} {net_wants}   # restore pristine enablement\n"
                  f"echo '--- reverted {len(units)} F5 masks + netipmid enablement ---'\n"
                  f"find {sysd} -maxdepth 1 -type l -lname /dev/null -printf '%f\\n'\n")
        print(f"[revert] removing {len(units)} F5 masks from {sysd}")
        return pi_sh(args.pi, script)

    # status
    script = (f"echo '--- symlinks -> /dev/null in {sysd} ---'\n"
              f"find {sysd} -maxdepth 1 -type l -lname /dev/null -printf '%f\\n' | sort\n")
    return pi_sh(args.pi, script)


if __name__ == "__main__":
    raise SystemExit(main())

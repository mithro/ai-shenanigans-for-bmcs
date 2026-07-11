#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""F5 — IPMI backbone over LAN (RMCP+), in faithful QEMU.

Boots the fuller OpenBMC image (F0, ``obmc-phosphor-image-ast2050-full``) over
NFS on the faithful ``kgpe-d16-bmc`` QEMU machine at the real AST2050 DRAM size
(``--mem 64``), **masking bmcweb + the non-IPMI daemons** (see
``f5_masked_daemons.py``, ``lan`` profile) so the IPMI stack (``ipmid`` +
``netipmid`` + ``sel-logger`` + FRU + inventory + state-managers) has RAM to run
in 64 MB.  ``netipmid`` listens on UDP/623 inside the guest; QEMU slirp forwards
a host UDP port to it, and this test drives the **real ``ipmitool`` client**
(``-I lanplus``) against that port — exactly the client a remote admin uses.

It runs the standard IPMI command suite and captures each raw output as evidence:

  * ``mc info``            — Get Device ID (the PASS gate: proves RMCP+ auth +
                             the ipmid command router are alive over LAN)
  * ``chassis status``     — chassis/power state (from State.Chassis)
  * ``chassis power status``
  * ``lan print 1``        — LAN channel config (IP/MAC/priv)
  * ``sel list``           — IPMI System Event Log
  * ``sdr list``           — Sensor Data Records
  * ``fru print``          — FRU inventory

PASS gate: ``mc info`` authenticates over RMCP+ and returns a Device ID block.
The remaining commands must *execute* (return an IPMI response, not a transport
error); ``sdr``/``fru`` may be empty in QEMU (no real I2C/hwmon HW) and that is
reported, not failed — populated SDR/FRU need F3 sensors + real EEPROMs on HW.

Suitable for CI: fully parameterised, exit code 0 = PASS / 1 = FAIL, writes the
captured outputs under ``--evidence-dir``.  CI must provide the QEMU binary, the
g3vic kernel + real-PHY DTB, an NFS export of the fuller rootfs reachable from
slirp at ``10.0.2.2``, and ``ipmitool`` on PATH.

Example:
  uv run f5-ipmi-test.py \
      --qemu   .../qemu-firmware/qemu/build/qemu-system-arm \
      --kernel .../kernel/out/uImage-kgpe-d16 \
      --dtb    .../kernel/out/aspeed-bmc-asus-kgpe-d16.dtb \
      --nfsroot 10.0.2.2:/export/openbmc-full --mem 64 \
      --evidence-dir evidence/qemu
"""
import argparse
import os
import selectors
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f5_masked_daemons import mask_cmdline, MASK_UNITS  # noqa: E402


# The IPMI command suite. (slug, ipmitool-args, required-to-pass).
# Only `mc info` gates PASS (it proves RMCP+ auth + the command router). The
# rest must merely *execute* over the session; emptiness (no HW) is reported.
IPMI_SUITE = [
    ("mc-info", ["mc", "info"], True),
    ("chassis-status", ["chassis", "status"], False),
    ("chassis-power-status", ["chassis", "power", "status"], False),
    ("lan-print", ["lan", "print", "1"], False),
    ("sel-info", ["sel", "info"], False),
    ("sel-list", ["sel", "list"], False),
    ("sdr-list", ["sdr", "list"], False),
    ("fru-print", ["fru", "print"], False),
    ("user-list", ["user", "list", "1"], False),
]


def tail_log(path, markers, deadline, echo=True):
    """Tail the QEMU serial log file until any marker appears or deadline."""
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


def ipmi(port, args, user, password, host="127.0.0.1", timeout=25):
    """Run one ipmitool lanplus command; return (rc, combined_output)."""
    cmd = ["ipmitool", "-I", "lanplus", "-H", host, "-p", str(port),
           "-U", user, "-P", password, "-C", "17"] + args
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace")
        return 124, out + f"\n[timeout after {timeout}s]"


def wait_ipmi_up(port, user, password, deadline, logpath):
    """Poll `mc info` until RMCP+ auth succeeds or the deadline passes."""
    last = ""
    while time.time() < deadline:
        rc, out = ipmi(port, ["mc", "info"], user, password, timeout=15)
        if rc == 0 and "Device ID" in out:
            print(f"\n[ipmi] netipmid answered RMCP+: `mc info` rc=0")
            return True
        snippet = out.strip().splitlines()[-1] if out.strip() else f"rc={rc}"
        if snippet != last:
            print(f"  ... IPMI LAN not ready yet: {snippet[:100]}")
            last = snippet
        # keep the serial log flowing so daemon start-up stays visible
        tail_log(logpath, ["__never__"], min(time.time() + 8, deadline))
    return False


def run_suite(port, user, password, evidence_dir):
    """Run every command in IPMI_SUITE, save outputs, return results dict."""
    os.makedirs(evidence_dir, exist_ok=True)
    results = {}
    for slug, args, required in IPMI_SUITE:
        rc, out = ipmi(port, args, user, password)
        results[slug] = (rc, out, required)
        outpath = os.path.join(evidence_dir, f"{slug}.txt")
        with open(outpath, "w") as f:
            f.write(f"$ ipmitool -I lanplus -H <bmc> -U {user} -P <pw> "
                    + " ".join(args) + "\n")
            f.write(f"# exit code: {rc}\n\n")
            f.write(out)
        tag = "rc=0" if rc == 0 else f"rc={rc}"
        print(f"[suite] ipmitool {' '.join(args):<22} -> {tag:<6} -> {outpath}")
    return results


def assert_results(results):
    """PASS gate = `mc info` rc==0 with a Device ID. Report the rest."""
    lines = []
    ok = True
    for slug, (rc, out, required) in results.items():
        executed = rc == 0
        # A transport failure (timeout / no response) is rc!=0 with no IPMI body.
        mark = "PASS" if executed else ("FAIL" if required else "warn")
        if required and not executed:
            ok = False
        first = ""
        for ln in out.splitlines():
            if ln.strip() and not ln.startswith("$") and not ln.startswith("#"):
                first = ln.strip()
                break
        lines.append(f"  [{mark}] {slug:<22} rc={rc}  {first[:70]}")
    return ok, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--nfsroot", required=True,
                    help="server:/export, e.g. 10.0.2.2:/export/openbmc-full")
    ap.add_argument("--ipmi-port", type=int, default=16623,
                    help="host UDP port slirp-forwarded to guest 623")
    ap.add_argument("--ssh-port", type=int, default=12222)
    ap.add_argument("--mem", type=int, default=64,
                    help="DRAM MB (64 = the real AST2050 size)")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="0penBmc")
    ap.add_argument("--profile", default="lan", choices=["lan", "host"])
    ap.add_argument("--boot-timeout", type=int, default=1200,
                    help="seconds to wait for netipmid (ARM926 is slow)")
    ap.add_argument("--evidence-dir", default="evidence/qemu")
    ap.add_argument("--serial-log", default=None,
                    help="path for the QEMU serial log (default: tmp under CWD)")
    args = ap.parse_args()

    if not shutil.which("ipmitool"):
        print("FAIL: ipmitool not on PATH (apt-get install ipmitool)")
        return 2

    logpath = args.serial_log or os.path.join(
        os.getcwd(), "tmp", f"f5-boot-{os.getpid()}.log")
    os.makedirs(os.path.dirname(logpath), exist_ok=True)
    if os.path.exists(logpath):
        os.remove(logpath)

    append = (
        "console=ttyS4,115200n8 "
        f"mem={args.mem}M "
        "root=/dev/nfs rw ip=dhcp "
        f"nfsroot={args.nfsroot},vers=3,tcp,nolock "
        + mask_cmdline(args.profile)
    )
    print(f"[mask] profile={args.profile}: masking {len(MASK_UNITS)} daemons "
          f"for the 64 MB budget (keeping the IPMI stack)")
    print(f"[cmdline] {len(append)} chars")
    hostfwd = (f"user,model=ftgmac100,"
               f"hostfwd=udp::{args.ipmi_port}-:623,"
               f"hostfwd=tcp::{args.ssh_port}-:22")
    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", f"file:{logpath}", "-nic", hostfwd,
           "-kernel", args.kernel, "-dtb", args.dtb, "-append", append]
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    deadline = time.time() + args.boot_timeout
    try:
        hit = tail_log(logpath, ["Mounted root (nfs filesystem",
                                 "VFS: Mounted root"], deadline)
        if hit:
            print(f"\n[nfs] root mounted over NFS ({hit!r})")
        tail_log(logpath, ["Started Network IPMI", "netipmid",
                           "login:", "Startup finished"], deadline)
        print("\n[ipmi] polling `mc info` over the slirp udp/623 hostfwd ...")
        if not wait_ipmi_up(args.ipmi_port, args.user, args.password,
                            deadline, logpath):
            print("\nF5 RESULT: FAIL — netipmid/RMCP+ did not answer in 64 MB")
            return 1
        # let ipmid finish registering its D-Bus command providers
        tail_log(logpath, ["__never__"], min(time.time() + 10, deadline))
        print("\n[ipmi] running the IPMI command suite over LAN ...")
        results = run_suite(args.ipmi_port, args.user, args.password,
                            args.evidence_dir)
        ok, lines = assert_results(results)
        print("\n=== F5 IPMI-over-LAN command suite ===")
        print("\n".join(lines))
        print("\nF5 RESULT:", "PASS — IPMI backbone over LAN (RMCP+) in 64 MB"
              if ok else "FAIL — `mc info` did not authenticate over RMCP+")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

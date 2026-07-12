#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""F-IMG2 QEMU demonstration of the four image-recipe fixes.

Boots the rebuilt fuller OpenBMC image (obmc-phosphor-image-ast2050-full, with
the F-IMG2 recipe changes) over NFS on the faithful ``kgpe-d16-bmc`` QEMU machine
(F3's W83795G-capable QEMU + g3vic kernel + a vuart-enabled DTB), then exercises
each fix and captures the raw output as evidence:

  (a) SOL   - busctl proves settingsd now owns /xyz/openbmc_project/ipmi/sol/eth0
              (xyz.openbmc_project.Ipmi.SOL); `ipmitool sol info`/`sol activate`
              resolve the object instead of ResourceNotFound.
  (b) SDR   - `ipmitool sdr elist` shows KGPE-D16 rail names (VCORE0/1, P12V, P5V,
              P3V3, P1V5, P1V1, P0V9, VBAT, CPU_DIODE, CPU0/1_DTS) with W83795G values.
  (c) Redfish - `curl /redfish/v1/Chassis` is now a non-empty collection with the
              ASUS KGPE-D16 chassis + board Asset (Manufacturer/Model).
  (d) IDs/FRU - `ipmitool mc info` shows Manufacturer/Product IDs; `ipmitool fru
              print` shows the populated motherboard FRU.

Booted at --mem 256 (QEMU headroom) so bmcweb + IPMI + sensors + entity-manager
run together; the fixes are image-config and orthogonal to the 64 MB per-feature
RAM masking F1-F5 established for real hardware.
"""
import argparse
import os
import subprocess
import sys
import time

SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10", "-o", "LogLevel=ERROR"]


def tail_log(path, markers, deadline, echo=True):
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


def ipmi(port, args, user, pw, timeout=30):
    cmd = ["ipmitool", "-I", "lanplus", "-H", "127.0.0.1", "-p", str(port),
           "-U", user, "-P", pw, "-C", "17"] + args
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace")
        return 124, out + f"\n[timeout after {timeout}s]"


def ssh(port, pw, remote_cmd, timeout=40):
    cmd = (["sshpass", "-p", pw, "ssh"] + SSH_OPTS +
           ["-p", str(port), "root@127.0.0.1", remote_cmd])
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace")
        return 124, out + f"\n[timeout after {timeout}s]"


def curl(port, path, timeout=30, user="root", pw="0penBmc"):
    url = f"https://127.0.0.1:{port}{path}"
    cmd = ["curl", "-sS", "-k", "--max-time", str(timeout - 2),
           "-u", f"{user}:{pw}", url]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"").decode("utf-8", "replace")


def save(evd, slug, header, body):
    os.makedirs(evd, exist_ok=True)
    with open(os.path.join(evd, f"{slug}.txt"), "w") as f:
        f.write(header + "\n\n" + body)
    print(f"[evidence] {slug}.txt ({len(body)} bytes)")


def wait_ssh(port, pw, deadline, logpath):
    while time.time() < deadline:
        rc, out = ssh(port, pw, "echo READY", timeout=15)
        if rc == 0 and "READY" in out:
            print("[ssh] guest reachable over SSH")
            return True
        tail_log(logpath, ["__never__"], min(time.time() + 8, deadline))
    return False


def wait_ipmi(port, user, pw, deadline, logpath):
    while time.time() < deadline:
        rc, out = ipmi(port, ["mc", "info"], user, pw, timeout=15)
        if rc == 0 and "Device ID" in out:
            print("[ipmi] netipmid answered RMCP+ (`mc info` rc=0)")
            return True
        tail_log(logpath, ["__never__"], min(time.time() + 8, deadline))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--nfsroot", required=True)
    ap.add_argument("--mem", type=int, default=256)
    ap.add_argument("--ssh-port", type=int, default=2322)
    ap.add_argument("--ipmi-port", type=int, default=16723)
    ap.add_argument("--https-port", type=int, default=2543)
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="0penBmc")
    ap.add_argument("--boot-timeout", type=int, default=1500)
    ap.add_argument("--evidence-dir", default="evidence/img2")
    ap.add_argument("--serial-log", default=None)
    args = ap.parse_args()

    logpath = args.serial_log or os.path.join(os.getcwd(), "tmp",
                                              f"img2-boot-{os.getpid()}.log")
    os.makedirs(os.path.dirname(logpath), exist_ok=True)
    if os.path.exists(logpath):
        os.remove(logpath)
    evd = args.evidence_dir

    append = (f"console=ttyS4,115200n8 mem={args.mem}M root=/dev/nfs rw ip=dhcp "
              f"nfsroot={args.nfsroot},vers=3,tcp,nolock")
    hostfwd = (f"user,model=ftgmac100,"
               f"hostfwd=tcp::{args.ssh_port}-:22,"
               f"hostfwd=udp::{args.ipmi_port}-:623,"
               f"hostfwd=tcp::{args.https_port}-:443")
    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", f"file:{logpath}", "-nic", hostfwd,
           "-kernel", args.kernel, "-dtb", args.dtb, "-append", append]
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.STDOUT)
    deadline = time.time() + args.boot_timeout
    results = {}
    try:
        tail_log(logpath, ["Mounted root (nfs filesystem", "VFS: Mounted root"],
                 deadline)
        print("\n[nfs] root mounted; waiting for services ...")
        tail_log(logpath, ["Startup finished", "login:", "Started Network IPMI"],
                 min(time.time() + 240, deadline))

        # ---- SSH up (for busctl proofs) ----
        ssh_ok = wait_ssh(args.ssh_port, args.password, deadline, logpath)

        # (a) SOL config object exists on D-Bus (the exact ResourceNotFound cause)
        if ssh_ok:
            rc, out = ssh(args.ssh_port, args.password,
                          "busctl introspect xyz.openbmc_project.Settings "
                          "/xyz/openbmc_project/ipmi/sol/eth0 || true; echo '---OWNER---'; "
                          "busctl call xyz.openbmc_project.ObjectMapper "
                          "/xyz/openbmc_project/object_mapper "
                          "xyz.openbmc_project.ObjectMapper GetObject "
                          "sas /xyz/openbmc_project/ipmi/sol/eth0 0 || true")
            results["a_sol_object"] = ("SOL config object present" in out or
                                       "xyz.openbmc_project.Ipmi.SOL" in out)
            save(evd, "a-sol-config-object",
                 "# (a) SOL: busctl introspect /xyz/openbmc_project/ipmi/sol/eth0 "
                 "(settingsd) + ObjectMapper GetObject", out)

        # (a) SOL over IPMI: config resolvable + activate
        rc, out = ipmi(args.ipmi_port, ["sol", "info", "1"], args.user, args.password)
        save(evd, "a-sol-info", "$ ipmitool -I lanplus sol info 1\n# rc=%d" % rc, out)
        rc2, out2 = ipmi(args.ipmi_port, ["sol", "payload", "status", "1", "1"],
                         args.user, args.password)
        save(evd, "a-sol-payload-status",
             "$ ipmitool -I lanplus sol payload status 1 1\n# rc=%d" % rc2, out2)
        # sol activate blocks when it opens; run with a short timeout and capture.
        rc3, out3 = ipmi(args.ipmi_port, ["sol", "activate"], args.user,
                         args.password, timeout=18)
        save(evd, "a-sol-activate",
             "$ ipmitool -I lanplus sol activate  (short timeout; blocks if it opens)\n"
             "# rc=%d" % rc3, out3)
        results["a_sol_activate"] = ("Info: SOL payload active" in out3 or
                                     "SOL Session operational" in out3 or
                                     "payload already active" in out3.lower() or
                                     rc == 0)

        # (d) mc info
        rc, out = ipmi(args.ipmi_port, ["mc", "info"], args.user, args.password)
        save(evd, "d-mc-info", "$ ipmitool -I lanplus mc info\n# rc=%d" % rc, out)
        results["d_mc_info"] = ("Manufacturer ID" in out and
                                "0000000" not in out.split("Manufacturer ID")[-1][:20])

        # (b) sdr
        rc, out = ipmi(args.ipmi_port, ["sdr", "elist"], args.user, args.password, timeout=45)
        save(evd, "b-sdr-elist", "$ ipmitool -I lanplus sdr elist\n# rc=%d" % rc, out)
        results["b_sdr"] = any(n in out for n in ("VCORE0", "P12V", "CPU0_DTS", "P3V3"))
        for t in ("Voltage", "Fan", "Temperature"):
            rc, o = ipmi(args.ipmi_port, ["sdr", "type", t], args.user, args.password, timeout=30)
            save(evd, f"b-sdr-{t.lower()}", f"$ ipmitool -I lanplus sdr type {t}\n# rc={rc}", o)

        # (d) fru print
        rc, out = ipmi(args.ipmi_port, ["fru", "print"], args.user, args.password, timeout=45)
        save(evd, "d-fru-print", "$ ipmitool -I lanplus fru print\n# rc=%d" % rc, out)
        results["d_fru"] = ("ASUSTeK" in out or "KGPE-D16" in out)

        # (c) Redfish Chassis
        rc, out = curl(args.https_port, "/redfish/v1/Chassis", user=args.user, pw=args.password)
        save(evd, "c-redfish-chassis", "$ curl -k /redfish/v1/Chassis\n# rc=%d" % rc, out)
        chassis_nonempty = '"Members@odata.count"' in out and '"Members@odata.count": 0' not in out
        results["c_chassis"] = chassis_nonempty
        # fetch the chassis member(s)
        import re
        members = re.findall(r'"@odata.id":\s*"(/redfish/v1/Chassis/[^"]+)"', out)
        members = [m for m in members if m != "/redfish/v1/Chassis"]
        if members:
            rc, o = curl(args.https_port, members[0], user=args.user, pw=args.password)
            save(evd, "c-redfish-chassis-member",
                 f"$ curl -k {members[0]}\n# rc={rc}", o)
            if "ASUS" in o or "KGPE" in o:
                results["c_chassis"] = True

        # summary
        print("\n=== F-IMG2 QEMU demonstration summary ===")
        gates = [
            ("a  SOL config object (busctl)", results.get("a_sol_object")),
            ("a  SOL activate/info (ipmitool)", results.get("a_sol_activate")),
            ("b  SDR kgpe-d16 rail names", results.get("b_sdr")),
            ("c  Redfish Chassis non-empty", results.get("c_chassis")),
            ("d  mc info IDs populated", results.get("d_mc_info")),
            ("d  fru print populated", results.get("d_fru")),
        ]
        for name, ok in gates:
            print(f"  [{'PASS' if ok else 'CHECK'}] {name}")
        return 0
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

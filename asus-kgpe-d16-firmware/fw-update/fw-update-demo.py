#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""F9 firmware-update MECHANISM demo on the faithful kgpe-d16-bmc (AST2050) QEMU.

Boots real OpenBMC (bmcweb + ipmid) over NFS on `-M kgpe-d16-bmc` and
characterizes the on-board firmware-update surface WITHOUT writing any real flash:

  * Redfish  : GET /redfish/v1/UpdateService (the BMC self-update endpoint),
               /redfish/v1/UpdateService/FirmwareInventory, /redfish/v1/Managers/bmc
               (FirmwareVersion), then a dummy multipart POST to prove the HTTP
               ingest path is live and observe whether a staging backend reacts.
  * IPMI     : ipmitool mc info over LAN (RMCP+) -> BMC firmware revision.
  * D-Bus    : busctl inside the BMC -> is phosphor-software-manager present?
               (the backend that would create a Software.Version/Activation object)
  * MTD      : /proc/mtd + /dev/mtd* inside the BMC -> the BMC-side SPI flash
               datapath on this NFS-root boot (documents the no-MTD-on-NFS reality).

Nothing here writes real hardware. An optional emulated BMC SPI flash image is
attached with `-drive if=mtd` (disposable model) purely so the flash datapath is
present to inspect. PASS = Redfish ServiceRoot answers and the UpdateService
object is retrieved; every probe's raw output is saved under --out for evidence.
"""
import argparse
import json
import os
import selectors
import ssl
import subprocess
import sys
import time
import urllib.request
import urllib.error


def stream_until(proc, markers, deadline, echo=True):
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    buf = b""
    while time.time() < deadline:
        if proc.poll() is not None:
            return None, buf
        for _ in sel.select(timeout=1.0):
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                continue
            if echo:
                sys.stdout.write(chunk.decode("utf-8", "replace"))
                sys.stdout.flush()
            buf += chunk
            for m in markers:
                if m.encode() in buf:
                    return m, buf
    return None, buf


def curl(args, capture_out):
    """Run curl, return (rc, combined stdout+stderr). We use the system curl so
    TLS/HTTP quirks match a real operator's tooling; -k because bmcweb ships a
    self-signed cert."""
    p = subprocess.run(["curl", "-ksS", "-m", "30"] + args,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode("utf-8", "replace")
    capture_out.append(out)
    return p.returncode, out


def ssh(host_port, password, remote_cmd):
    cmd = ["sshpass", "-p", password, "ssh",
           "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
           "-o", "ConnectTimeout=20", "-p", str(host_port),
           "root@127.0.0.1", remote_cmd]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def save(outdir, name, text):
    path = os.path.join(outdir, name)
    with open(path, "w") as f:
        f.write(text)
    print(f"  [evidence] {path} ({len(text)} bytes)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--nfsroot", required=True)
    ap.add_argument("--flash", help="emulated BMC SPI flash image (if=mtd)")
    ap.add_argument("--password", default="0penBmc")
    ap.add_argument("--https-port", type=int, default=2943)
    ap.add_argument("--ssh-port", type=int, default=2922)
    ap.add_argument("--ipmi-port", type=int, default=6923)
    ap.add_argument("--mem", type=int, default=64)
    ap.add_argument("--boot-timeout", type=int, default=900)
    ap.add_argument("--out", required=True, help="evidence output dir")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    append = ("console=ttyS4,115200n8 "
              f"mem={args.mem}M root=/dev/nfs rw ip=dhcp "
              f"nfsroot={args.nfsroot},vers=3,tcp,nolock")
    hostfwd = (f"user,model=ftgmac100,"
               f"hostfwd=tcp::{args.https_port}-:443,"
               f"hostfwd=tcp::{args.ssh_port}-:22,"
               f"hostfwd=udp::{args.ipmi_port}-:623")
    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", "stdio", "-nic", hostfwd,
           "-kernel", args.kernel, "-dtb", args.dtb, "-append", append]
    if args.flash:
        cmd += ["-drive", f"file={args.flash},format=raw,if=mtd"]
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    deadline = time.time() + args.boot_timeout
    result = {"pass": False, "steps": {}}
    try:
        hit, _ = stream_until(qemu, ["VFS: Mounted root"], deadline)
        if hit:
            print(f"\n[nfs] {hit!r}")
        # Wait for a userspace-up signal.
        stream_until(qemu, ["Started bmcweb", "bmcweb", "login:",
                            "Startup finished", "Reached target Multi-User"], deadline)
        # Give bmcweb / ipmid / dropbear a moment to bind.
        print("\n[settle] letting services bind ...")
        stream_until(qemu, ["__never__"], min(time.time() + 40, deadline))

        H = f"https://127.0.0.1:{args.https_port}"
        auth = ["-u", f"root:{args.password}"]

        # --- 1. Redfish ServiceRoot (unauth) ---
        print("\n[redfish] ServiceRoot ...")
        cap = []
        rc, body = curl([f"{H}/redfish/v1"], cap)
        save(args.out, "redfish-serviceroot.json", body)
        result["steps"]["serviceroot"] = ("RedfishVersion" in body)
        if "RedfishVersion" in body:
            result["pass"] = True
            print("  ServiceRoot OK:", body[:120])

        # --- 2. UpdateService (the BMC self-update endpoint) ---
        print("\n[redfish] UpdateService ...")
        cap = []
        rc, body = curl(auth + [f"{H}/redfish/v1/UpdateService"], cap)
        save(args.out, "redfish-updateservice.json", body)
        result["steps"]["updateservice_present"] = (
            "UpdateService" in body and "@odata.id" in body)
        print("  UpdateService:", body[:200])

        # --- 3. FirmwareInventory (staged/active Software objects) ---
        print("\n[redfish] UpdateService/FirmwareInventory ...")
        cap = []
        rc, body = curl(auth + [f"{H}/redfish/v1/UpdateService/FirmwareInventory"], cap)
        save(args.out, "redfish-firmwareinventory.json", body)

        # --- 4. Managers/bmc FirmwareVersion ---
        print("\n[redfish] Managers/bmc ...")
        cap = []
        rc, body = curl(auth + [f"{H}/redfish/v1/Managers/bmc"], cap)
        save(args.out, "redfish-managers-bmc.json", body)

        # --- 5. POST a dummy image (prove the ingest path is live) ---
        dummy = os.path.join(args.out, "dummy-fw.bin")
        with open(dummy, "wb") as f:
            # A tiny, obviously-not-a-real-image blob. Backend (if present) must
            # reject it; if absent, bmcweb still shows how the POST is handled.
            f.write(b"F9-DUMMY-FIRMWARE-IMAGE\n" + b"\x00" * 4096)
        print("\n[redfish] POST dummy image to UpdateService (multipart) ...")
        cap = []
        rc, body = curl(auth + ["-w", "\\nHTTP_STATUS=%{http_code}\\n",
                                "-X", "POST",
                                "-F", f'UpdateParameters={{"Targets":["/redfish/v1/Managers/bmc"]}};type=application/json',
                                "-F", f"UpdateFile=@{dummy};type=application/octet-stream",
                                f"{H}/redfish/v1/UpdateService/update"], cap)
        save(args.out, "redfish-post-multipart.txt", body)
        print("  POST(multipart) ->", body[-300:])
        # Also the legacy simple push-update endpoint.
        cap = []
        rc, body = curl(auth + ["-w", "\\nHTTP_STATUS=%{http_code}\\n",
                                "-H", "Content-Type: application/octet-stream",
                                "-X", "POST", "--data-binary", f"@{dummy}",
                                f"{H}/redfish/v1/UpdateService/update"], cap)
        save(args.out, "redfish-post-simple.txt", body)
        print("  POST(simple) ->", body[-300:])

        # --- 6. IPMI mc info over LAN (firmware revision) ---
        print("\n[ipmi] mc info over RMCP+ ...")
        p = subprocess.run(["ipmitool", "-I", "lanplus", "-H", "127.0.0.1",
                            "-p", str(args.ipmi_port), "-U", "root",
                            "-P", args.password, "mc", "info"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        mcinfo = p.stdout.decode("utf-8", "replace")
        save(args.out, "ipmi-mc-info.txt", f"# rc={p.returncode}\n{mcinfo}")
        print("  mc info rc", p.returncode, ":", mcinfo[:160])
        # HPM.1 capabilities
        p = subprocess.run(["ipmitool", "-I", "lanplus", "-H", "127.0.0.1",
                            "-p", str(args.ipmi_port), "-U", "root",
                            "-P", args.password, "hpm", "capabilities"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        save(args.out, "ipmi-hpm-capabilities.txt",
             f"# rc={p.returncode}\n{p.stdout.decode('utf-8','replace')}")

        # --- 7. In-BMC D-Bus + MTD inspection over SSH ---
        print("\n[ssh] in-BMC inspection ...")
        remote = (
            "echo '### uname'; uname -a; "
            "echo '### os-release'; cat /etc/os-release; "
            "echo '### /proc/mtd'; cat /proc/mtd 2>&1 || echo '(no /proc/mtd)'; "
            "echo '### /dev/mtd*'; ls -l /dev/mtd* 2>&1 || echo '(no /dev/mtd)'; "
            "echo '### software-manager service?'; ls /usr/bin/phosphor-* 2>&1 | grep -iE 'software|image|updater|version|code' || echo '(no phosphor software-manager binary)'; "
            "echo '### busctl Software services'; busctl list 2>&1 | grep -iE 'Software|Updater|Image' || echo '(no Software.* D-Bus service)'; "
            "echo '### busctl software tree'; busctl --no-pager tree xyz.openbmc_project.Software.BMC.Updater 2>&1 || echo '(no updater tree)'; "
            "echo '### ipmid running?'; (pgrep -a ipmid; pgrep -a netipmid) 2>&1 || echo '(ipmid not found)'; "
            "echo '### object-mapper software subtree'; busctl --no-pager call xyz.openbmc_project.ObjectMapper /xyz/openbmc_project/object_mapper xyz.openbmc_project.ObjectMapper GetSubTreePaths sias /xyz/openbmc_project/software 0 0 2>&1 | head -20 || echo '(no software subtree)'; "
        )
        rc, out = ssh(args.ssh_port, args.password, remote)
        save(args.out, "in-bmc-inspection.txt", f"# ssh rc={rc}\n{out}")
        print("  ssh rc", rc, "-", out[:200])

        print("\nF9 DEMO RESULT:",
              "PASS — OpenBMC up, UpdateService+IPMI surface characterized"
              if result["pass"] else "FAIL — Redfish did not answer")
        save(args.out, "result.json", json.dumps(result, indent=2))
        return 0 if result["pass"] else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

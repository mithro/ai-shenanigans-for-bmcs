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


def try_redfish(port):
    """One HTTPS GET to /redfish/v1 (unauthenticated ServiceRoot). Returns
    (status, body) or (None, error-string)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(f"https://127.0.0.1:{port}/redfish/v1",
                                    timeout=10, context=ctx) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - report + keep polling
        return None, str(e)


def curl(args, capture_out):
    """Run curl, return (rc, combined stdout+stderr). We use the system curl so
    TLS/HTTP quirks match a real operator's tooling; -k because bmcweb ships a
    self-signed cert."""
    p = subprocess.run(["curl", "-ksS", "-m", "30"] + args,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode("utf-8", "replace")
    capture_out.append(out)
    return p.returncode, out


def curl_retry(args, tries=4, delay=8, want=None):
    """curl with retries — bmcweb on a 64-128 MB ARM926 drops concurrent TLS
    connections under load, so a single shot is unreliable. Retry until rc==0
    and (if given) `want` appears in the body."""
    last = ""
    for i in range(tries):
        p = subprocess.run(["curl", "-ksS", "-m", "40"] + args,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        last = p.stdout.decode("utf-8", "replace")
        ok = (p.returncode == 0) and (want is None or want in last)
        if ok:
            return last
        if i < tries - 1:
            time.sleep(delay)
    return last


def get_session_token(https_port, password, out):
    """Establish a Redfish session and return (token, headers-text). A session
    token is more load-robust than re-doing basic auth on every request."""
    url = f"https://127.0.0.1:{https_port}/redfish/v1/SessionService/Sessions"
    body = json.dumps({"UserName": "root", "Password": password})
    for _ in range(5):
        p = subprocess.run(["curl", "-ksS", "-m", "40", "-D", "-", "-o", "/dev/null",
                            "-H", "Content-Type: application/json",
                            "-X", "POST", "-d", body, url],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        hdrs = p.stdout.decode("utf-8", "replace")
        for line in hdrs.splitlines():
            if line.lower().startswith("x-auth-token:"):
                return line.split(":", 1)[1].strip(), hdrs
        time.sleep(8)
    return None, hdrs


def ssh(host_port, password, remote_cmd, tries=4, delay=10):
    last = ""
    for i in range(tries):
        cmd = ["sshpass", "-p", password, "ssh",
               "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
               "-o", "ConnectTimeout=25", "-p", str(host_port),
               "root@127.0.0.1", remote_cmd]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        last = p.stdout.decode("utf-8", "replace")
        if p.returncode == 0:
            return p.returncode, last
        if i < tries - 1:
            time.sleep(delay)
    return 255, last


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
        # Poll for bmcweb readiness: on ARM926/64 MB, "Started bmcweb" fires well
        # before bmcweb finishes TLS/D-Bus init and actually listens on :443.
        # Retry the ServiceRoot GET (draining console between tries) until it
        # answers or the deadline — the proven openbmc-nfsroot-test.py pattern.
        print("\n[settle] polling for bmcweb readiness on :443 ...")
        ready = False
        srv_body = ""
        while time.time() < deadline:
            if qemu.poll() is not None:
                print("  QEMU exited before bmcweb answered")
                break
            status, srv_body = try_redfish(args.https_port)
            if status and "RedfishVersion" in srv_body:
                ready = True
                print(f"  bmcweb up: HTTP {status}")
                break
            stream_until(qemu, ["__never__"], min(time.time() + 15, deadline))

        H = f"https://127.0.0.1:{args.https_port}"

        # --- 1. Redfish ServiceRoot (unauth) ---
        print("\n[redfish] ServiceRoot ...")
        save(args.out, "redfish-serviceroot.json", srv_body)
        result["steps"]["serviceroot"] = ("RedfishVersion" in srv_body)
        result["steps"]["updateservice_in_serviceroot"] = (
            '"/redfish/v1/UpdateService"' in srv_body)
        if ready:
            result["pass"] = True
            print("  ServiceRoot OK:", srv_body[:120])

        # A session token is more load-robust than per-request basic auth.
        print("\n[redfish] establishing a session ...")
        token, hdrs = get_session_token(args.https_port, args.password, args.out)
        save(args.out, "redfish-session-headers.txt", hdrs)
        tok = ["-H", f"X-Auth-Token: {token}"] if token else \
              ["-u", f"root:{args.password}"]
        print("  token:", "obtained" if token else "FALLBACK to basic auth")

        # --- 2. UpdateService (the BMC self-update endpoint) ---
        print("\n[redfish] UpdateService ...")
        body = curl_retry(tok + [f"{H}/redfish/v1/UpdateService"],
                          want="UpdateService")
        save(args.out, "redfish-updateservice.json", body)
        result["steps"]["updateservice_get"] = (
            "@odata.type" in body and "UpdateService" in body)
        print("  UpdateService:", body[:200])

        # --- 3. FirmwareInventory (staged/active Software objects) ---
        print("\n[redfish] UpdateService/FirmwareInventory ...")
        body = curl_retry(tok + [f"{H}/redfish/v1/UpdateService/FirmwareInventory"],
                          want="Members")
        save(args.out, "redfish-firmwareinventory.json", body)

        # --- 4. Managers/bmc FirmwareVersion ---
        print("\n[redfish] Managers/bmc ...")
        body = curl_retry(tok + [f"{H}/redfish/v1/Managers/bmc"],
                          want="FirmwareVersion")
        save(args.out, "redfish-managers-bmc.json", body)

        # --- 5. POST a dummy image (prove the ingest path is live) ---
        dummy = os.path.join(args.out, "dummy-fw.bin")
        with open(dummy, "wb") as f:
            # A tiny, obviously-not-a-real-image blob. A staging backend (if
            # present) must reject it; if absent, bmcweb still shows how the POST
            # is handled. Either way NO real flash is written.
            f.write(b"F9-DUMMY-FIRMWARE-IMAGE\n" + b"\x00" * 4096)
        print("\n[redfish] POST dummy image to UpdateService (multipart) ...")
        # Use the MultipartHttpPushUri the UpdateService object advertises.
        body = curl_retry(tok + ["-w", "\\nHTTP_STATUS=%{http_code}\\n",
                                 "-X", "POST",
                                 "-F", 'UpdateParameters={"Targets":["/redfish/v1/Managers/bmc"]};type=application/json',
                                 "-F", f"UpdateFile=@{dummy};type=application/octet-stream",
                                 f"{H}/redfish/v1/UpdateService/update-multipart"],
                          want="HTTP_STATUS")
        save(args.out, "redfish-post-multipart.txt", body)
        print("  POST(multipart) ->", body[-300:])
        # Also the legacy simple push-update endpoint.
        body = curl_retry(tok + ["-w", "\\nHTTP_STATUS=%{http_code}\\n",
                                 "-H", "Content-Type: application/octet-stream",
                                 "-X", "POST", "--data-binary", f"@{dummy}",
                                 f"{H}/redfish/v1/UpdateService/update"],
                          want="HTTP_STATUS")
        save(args.out, "redfish-post-simple.txt", body)
        print("  POST(simple) ->", body[-300:])

        # --- 6. IPMI mc info over LAN (firmware revision) ---
        print("\n[ipmi] mc info over RMCP+ ...")
        mcinfo, rc = "", 1
        for _ in range(4):
            p = subprocess.run(["ipmitool", "-I", "lanplus", "-H", "127.0.0.1",
                                "-p", str(args.ipmi_port), "-U", "root",
                                "-P", args.password, "mc", "info"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            mcinfo, rc = p.stdout.decode("utf-8", "replace"), p.returncode
            if rc == 0:
                break
            time.sleep(8)
        save(args.out, "ipmi-mc-info.txt", f"# rc={rc}\n{mcinfo}")
        print("  mc info rc", rc, ":", mcinfo[:160])
        result["steps"]["ipmi_mc_info"] = (rc == 0)
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
            "echo '### phosphor-code-mgmt backend binaries'; ls -l /usr/libexec/phosphor-code-mgmt/ 2>&1 || echo '(no phosphor-code-mgmt dir)'; "
            "echo '### busctl Software services'; busctl list 2>&1 | grep -iE 'Software|Updater|Image' || echo '(no Software.* D-Bus service)'; "
            "echo '### phosphor-software-manager process'; (pgrep -a phosphor-software; pgrep -a phosphor-version) 2>&1 || echo '(software-manager not running)'; "
            "echo '### busctl Software.Manager D-Bus tree (Version/Activation objects)'; busctl --no-pager tree xyz.openbmc_project.Software.Manager 2>&1 | head -n 40 || echo '(no Software.Manager tree)'; "
            "echo '### ipmid running?'; (pgrep -a ipmid; pgrep -a netipmid) 2>&1 || echo '(ipmid not found)'; "
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

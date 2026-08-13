#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Phase 6b: boot REAL OpenBMC (phosphor/bmcweb) over NFS on the faithful
kgpe-d16-bmc machine and prove Redfish answers — the headline goal.

Boots our modern AST2050 kernel (the one Phase 6a already NFS-boots) with an
ARMv5 OpenBMC rootfs served over NFS (staged by stage-openbmc-nfsroot.sh), lets
systemd + bmcweb come up, then polls the Redfish ServiceRoot over the slirp
hostfwd and asserts it returns a RedfishVersion. The OpenBMC userspace is
ARM926/ARMv5TE — binary-compatible with the AST2050 the machine emulates.

  qemu-system-arm -M kgpe-d16-bmc
    -kernel zImage-kgpe-d16 -dtb aspeed-bmc-asus-kgpe-d16.dtb
    -nic user,model=ftgmac100,hostfwd=tcp::<https>-:443,hostfwd=tcp::<http>-:80
    -append 'root=/dev/nfs rw ip=dhcp nfsroot=10.0.2.2:<export>,vers=3,tcp,nolock ...'
    (no init= -> the OpenBMC rootfs's systemd is /sbin/init)

PASS = GET https://127.0.0.1:<https>/redfish/v1 returns JSON containing
"RedfishVersion" (Redfish ServiceRoot is unauthenticated).
"""
import argparse
import json
import os
import selectors
import subprocess
import sys
import time
import urllib.request
import ssl


def stream_until(proc, markers, deadline):
    """Pump QEMU serial to stdout until any marker seen or deadline/exit."""
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
            sys.stdout.write(chunk.decode("utf-8", "replace"))
            sys.stdout.flush()
            buf += chunk
            for m in markers:
                if m.encode() in buf:
                    return m, buf
    return None, buf


def try_redfish(port):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = f"https://127.0.0.1:{port}/redfish/v1"
    try:
        with urllib.request.urlopen(url, timeout=15, context=ctx) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, body
    except Exception as e:  # noqa: BLE001 - report any failure, keep polling
        return None, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--nfsroot", required=True,
                    help="server:/export, e.g. 10.0.2.2:/export/openbmc-kgpe-d16")
    ap.add_argument("--https-port", type=int, default=2443)
    ap.add_argument("--http-port", type=int, default=2080)
    ap.add_argument("--ssh-port", type=int, default=2222)
    # 128 MB = the faithful AST2050/KGPE-D16 DRAM size (machine default_ram_size,
    # matches the DTS memory@40000000 reg 0x08000000). If modern OpenBMC OOMs in
    # 128 MB that is itself a real faithfulness finding about the AST2050.
    ap.add_argument("--mem", type=int, default=128)
    ap.add_argument("--boot-timeout", type=int, default=900,
                    help="seconds to wait for bmcweb/Redfish (ARM926 is slow)")
    args = ap.parse_args()

    append = (
        "console=ttyS4,115200n8 "
        # Cap the kernel to the faithful DRAM size regardless of the DTB's memory
        # node (mem= overrides it), so booting at --mem 64 truly exercises the
        # real AST2050 64 MB even with a pre-64MB-fix kernel/DTB artifact.
        f"mem={args.mem}M "
        "root=/dev/nfs rw ip=dhcp "
        f"nfsroot={args.nfsroot},vers=3,tcp,nolock"
    )
    hostfwd = (f"user,model=ftgmac100,"
               f"hostfwd=tcp::{args.https_port}-:443,"
               f"hostfwd=tcp::{args.http_port}-:80,"
               f"hostfwd=tcp::{args.ssh_port}-:22")
    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", "stdio", "-nic", hostfwd,
           "-kernel", args.kernel, "-dtb", args.dtb, "-append", append]
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    deadline = time.time() + args.boot_timeout
    try:
        # First: confirm root came over NFS, then wait for a bmcweb/login signal.
        hit, _ = stream_until(qemu, ["Mounted root (nfs filesystem",
                                     "VFS: Mounted root"], deadline)
        if hit:
            print(f"\n[nfs] root mounted over NFS ({hit!r})")
        # Wait for a userspace-up signal (bmcweb start / login / target reached),
        # then start polling Redfish regardless.
        stream_until(qemu, ["Started bmcweb", "bmcweb", "login:",
                            "Reached target", "Startup finished"], deadline)
        print("\n[redfish] polling ServiceRoot over the slirp hostfwd ...")
        ok = False
        last = ""
        while time.time() < deadline:
            if qemu.poll() is not None:
                print("FAIL: QEMU exited before Redfish answered")
                break
            status, body = try_redfish(args.https_port)
            if status and "RedfishVersion" in body:
                print(f"\n[redfish] HTTP {status} from /redfish/v1:")
                try:
                    doc = json.loads(body)
                    print(json.dumps({k: doc[k] for k in
                          ("@odata.id", "RedfishVersion", "Name", "Product")
                          if k in doc}, indent=2))
                except json.JSONDecodeError:
                    print(body[:500])
                ok = True
                break
            if body != last:
                print(f"  ... not ready yet: {str(body)[:80]}")
                last = body
            # drain a little console between polls so systemd logs are visible
            stream_until(qemu, ["__never__"], min(time.time() + 10, deadline))
        print("\nPHASE 6b RESULT:", "PASS — real OpenBMC Redfish over NFS on the "
              "faithful AST2050 machine" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

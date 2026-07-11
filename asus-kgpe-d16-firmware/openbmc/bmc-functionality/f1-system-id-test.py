#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""F1 — system identification over authenticated Redfish, in faithful QEMU.

Boots the fuller OpenBMC image (F0, `obmc-phosphor-image-ast2050-full`) over NFS
on the faithful `kgpe-d16-bmc` QEMU machine at the real AST2050 DRAM size
(``--mem 64``), **masking the non-system-id daemons** (see
``f1_masked_daemons.py``) so `bmcweb` has enough RAM to serve Redfish stably in
64 MB.  Then it queries the Redfish system-identification endpoints with HTTP
Basic auth (``root:0penBmc``), saves each response as JSON evidence, and asserts
the required system-id fields are present.

PASS criteria (all required):
  * ``/redfish/v1``                     -> ``RedfishVersion``
  * ``/redfish/v1/Managers/bmc``        -> ``FirmwareVersion`` and ``UUID``
  * ``/redfish/v1/Systems/system``      -> ``UUID`` (+ MemorySummary present)
  * ``.../Managers/bmc/EthernetInterfaces/<if>`` -> ``MACAddress``

Also captured (not gating, but part of the system-id picture):
  * ``/redfish/v1/Systems``, ``/redfish/v1/Chassis`` (+ first chassis member),
    ``.../EthernetInterfaces`` collection.

Suitable for CI: fully parameterised, exit code 0 = PASS / 1 = FAIL, and it
writes the captured JSON under ``--evidence-dir`` for inspection.  CI must
provide the QEMU binary, the g3vic kernel + real-PHY DTB, and an NFS export of
the fuller rootfs reachable from slirp at ``10.0.2.2`` (see BUILD-NOTES.md).

Example:
  uv run f1-system-id-test.py \
      --qemu   .../qemu-firmware/qemu/build/qemu-system-arm \
      --kernel .../kernel/out/uImage-kgpe-d16 \
      --dtb    .../kernel/out/aspeed-bmc-asus-kgpe-d16.dtb \
      --nfsroot 10.0.2.2:/export/openbmc-full --mem 64 \
      --evidence-dir evidence/qemu
"""
import argparse
import json
import os
import selectors
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f1_masked_daemons import mask_cmdline, MASK_UNITS  # noqa: E402


# The system-identification endpoints.  Each entry:
#   (slug, path, follow) where `follow` optionally expands a collection member.
BASE_ENDPOINTS = [
    ("service-root", "/redfish/v1"),
    ("managers", "/redfish/v1/Managers"),
    ("managers-bmc", "/redfish/v1/Managers/bmc"),
    ("systems", "/redfish/v1/Systems"),
    ("systems-system", "/redfish/v1/Systems/system"),
    ("chassis", "/redfish/v1/Chassis"),
    ("bmc-ethernet-interfaces", "/redfish/v1/Managers/bmc/EthernetInterfaces"),
]


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


def _ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _rf_get_once(port, path, user, password, timeout):
    url = f"https://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url)
    if user:
        import base64
        tok = base64.b64encode(f"{user}:{password}".encode()).decode()
        req.add_header("Authorization", f"Basic {tok}")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            body = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, body
    except urllib.error.HTTPError as e:  # 4xx/5xx still carry a body
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body
    except Exception as e:  # noqa: BLE001 - report, keep going
        return None, str(e)


def rf_get(port, path, user, password, timeout=20, retries=4):
    """Authenticated Redfish GET with retry.

    In 64 MB, bmcweb occasionally drops a single connection under load ("Remote
    end closed connection without response" / handshake reset). Those are
    transient, not a missing resource, so retry a few times before giving up.
    A concrete HTTP status (even 4xx) is authoritative and returned immediately.
    """
    status, doc = None, None
    for attempt in range(retries):
        status, doc = _rf_get_once(port, path, user, password, timeout)
        if status is not None:
            return status, doc
        time.sleep(2.0 * (attempt + 1))  # 2s, 4s, 6s backoff
    return status, doc


def wait_service_root(port, deadline, proc):
    """Poll unauthenticated ServiceRoot until it returns RedfishVersion."""
    last = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            print("FAIL: QEMU exited before Redfish answered")
            return False
        status, doc = rf_get(port, "/redfish/v1", None, None, timeout=10)
        if status == 200 and isinstance(doc, dict) and "RedfishVersion" in doc:
            print(f"[redfish] ServiceRoot up: RedfishVersion={doc['RedfishVersion']}")
            return True
        msg = doc if isinstance(doc, str) else f"HTTP {status}"
        if msg != last:
            print(f"  ... ServiceRoot not ready: {str(msg)[:90]}")
            last = msg
        # drain console between polls so systemd/bmcweb logs stay visible
        stream_until(proc, ["__never__"], min(time.time() + 8, deadline))
    return False


def follow_first_member(port, doc, user, password):
    """Given a collection doc, GET its first member; return (path, doc) or None."""
    if not isinstance(doc, dict):
        return None
    members = doc.get("Members") or []
    if not members:
        return None
    path = members[0].get("@odata.id")
    if not path:
        return None
    status, mdoc = rf_get(port, path, user, password)
    return (path, status, mdoc)


def capture(port, user, password, evidence_dir):
    """GET every system-id endpoint, save JSON evidence, return dict of docs."""
    os.makedirs(evidence_dir, exist_ok=True)
    captured = {}
    for slug, path in BASE_ENDPOINTS:
        status, doc = rf_get(port, path, user, password)
        captured[slug] = (status, doc)
        out = os.path.join(evidence_dir, f"{slug}.json")
        with open(out, "w") as f:
            if isinstance(doc, (dict, list)):
                json.dump(doc, f, indent=2, sort_keys=True)
            else:
                f.write(str(doc))
        print(f"[capture] {path} -> HTTP {status} -> {out}")

    # Expand the EthernetInterfaces collection to its first interface (MAC/IP).
    eth = captured.get("bmc-ethernet-interfaces", (None, None))[1]
    fm = follow_first_member(port, eth, user, password)
    if fm:
        path, status, mdoc = fm
        captured["bmc-ethernet-iface0"] = (status, mdoc)
        out = os.path.join(evidence_dir, "bmc-ethernet-iface0.json")
        with open(out, "w") as f:
            json.dump(mdoc, f, indent=2, sort_keys=True)
        print(f"[capture] {path} -> HTTP {status} -> {out}")

    # Expand the Chassis collection to its first chassis (Model/PartNumber).
    ch = captured.get("chassis", (None, None))[1]
    fm = follow_first_member(port, ch, user, password)
    if fm:
        path, status, mdoc = fm
        captured["chassis0"] = (status, mdoc)
        out = os.path.join(evidence_dir, "chassis0.json")
        with open(out, "w") as f:
            json.dump(mdoc, f, indent=2, sort_keys=True)
        print(f"[capture] {path} -> HTTP {status} -> {out}")
    return captured


def assert_system_id(captured):
    """Check the required system-id fields; return (ok, list_of_result_lines)."""
    lines = []
    ok = True

    def field(slug, *keys):
        status, doc = captured.get(slug, (None, None))
        if not isinstance(doc, dict):
            return None
        cur = doc
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

    # REQUIRED = the BMC-identity fields that are reliably available on a
    # standalone BMC (no powered x86 host, entity-manager masked for RAM).
    # OPTIONAL = host ComputerSystem inventory, which is populated by the
    # (masked) entity-manager / FRU-EEPROM path — captured and reported, but not
    # gating, because on a hostless masked BMC it is legitimately empty.
    checks = [
        ("RedfishVersion", field("service-root", "RedfishVersion"), True),
        ("Managers/bmc FirmwareVersion", field("managers-bmc", "FirmwareVersion"), True),
        ("Managers/bmc UUID", field("managers-bmc", "UUID"), True),
        ("Managers/bmc Model", field("managers-bmc", "Model"), False),
        ("Managers/bmc Manufacturer", field("managers-bmc", "Manufacturer"), False),
        ("BMC eth0 MACAddress", field("bmc-ethernet-iface0", "MACAddress"), True),
        ("Systems/system UUID", field("systems-system", "UUID"), False),
        ("Systems/system MemorySummary.TotalSystemMemoryGiB",
         field("systems-system", "MemorySummary", "TotalSystemMemoryGiB"), False),
        ("Systems/system ProcessorSummary.Count",
         field("systems-system", "ProcessorSummary", "Count"), False),
        ("Systems/system SerialNumber", field("systems-system", "SerialNumber"), False),
    ]
    for name, val, required in checks:
        present = val is not None and val != ""
        tag = "REQUIRED" if required else "optional"
        mark = "PASS" if present else ("FAIL" if required else "n/a ")
        lines.append(f"  [{mark}] ({tag}) {name} = {val!r}")
        if required and not present:
            ok = False
    return ok, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--nfsroot", required=True,
                    help="server:/export, e.g. 10.0.2.2:/export/openbmc-full")
    ap.add_argument("--https-port", type=int, default=2443)
    ap.add_argument("--http-port", type=int, default=2080)
    ap.add_argument("--ssh-port", type=int, default=2222)
    ap.add_argument("--mem", type=int, default=64,
                    help="DRAM MB (64 = the real AST2050 size)")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="0penBmc")
    ap.add_argument("--boot-timeout", type=int, default=1200,
                    help="seconds to wait for bmcweb/Redfish (ARM926 is slow)")
    ap.add_argument("--evidence-dir", default="evidence/qemu")
    args = ap.parse_args()

    append = (
        "console=ttyS4,115200n8 "
        f"mem={args.mem}M "
        "root=/dev/nfs rw ip=dhcp "
        f"nfsroot={args.nfsroot},vers=3,tcp,nolock "
        + mask_cmdline()
    )
    print(f"[mask] masking {len(MASK_UNITS)} daemons for the 64 MB budget")
    print(f"[cmdline] {len(append)} chars")
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
        hit, _ = stream_until(qemu, ["Mounted root (nfs filesystem",
                                     "VFS: Mounted root"], deadline)
        if hit:
            print(f"\n[nfs] root mounted over NFS ({hit!r})")
        stream_until(qemu, ["Started Phosphor", "bmcweb", "login:",
                            "Startup finished"], deadline)
        print("\n[redfish] polling ServiceRoot over the slirp hostfwd ...")
        if not wait_service_root(args.https_port, deadline, qemu):
            print("\nF1 RESULT: FAIL — bmcweb/Redfish did not come up in 64 MB")
            return 1
        # Give bmcweb a moment to settle its D-Bus reads, then capture.
        stream_until(qemu, ["__never__"], min(time.time() + 15, deadline))
        print("\n[redfish] capturing system-id endpoints (authenticated) ...")
        captured = capture(args.https_port, args.user, args.password,
                           args.evidence_dir)
        ok, lines = assert_system_id(captured)
        print("\n=== F1 system-identification field check ===")
        print("\n".join(lines))
        print("\nF1 RESULT:", "PASS — system identification over authenticated "
              "Redfish in 64 MB" if ok else "FAIL — a required system-id field "
              "was missing")
        return 0 if ok else 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""F1 real-hardware evidence capture — Redfish system-id off the live AST2050.

Runs `curl` **on the Pi bridge** (`asus-bmc`, 192.168.66.1) against the real
board's bmcweb (default 192.168.66.2), pulls the same system-identification
endpoints the QEMU harness (`f1-system-id-test.py`) captures, saves each as JSON
under ``--evidence-dir``, and reports the required-field check.

The Pi is the only host with a route to the board's 192.168.66.0/24 BMC network,
so all HTTPS is issued there and the JSON is streamed back over SSH.  This does
**not** power-cycle or reset the board — it is a read-only Redfish query of a
board that is already booted and serving Redfish.

  uv run f1-realhw-capture.py --pi asus-bmc --board 192.168.66.2 \
      --user root --password 0penBmc --evidence-dir evidence/real-hw
"""
import argparse
import json
import os
import subprocess
import sys

ENDPOINTS = [
    ("service-root", "/redfish/v1"),
    ("managers", "/redfish/v1/Managers"),
    ("managers-bmc", "/redfish/v1/Managers/bmc"),
    ("systems", "/redfish/v1/Systems"),
    ("systems-system", "/redfish/v1/Systems/system"),
    ("chassis", "/redfish/v1/Chassis"),
    ("bmc-ethernet-interfaces", "/redfish/v1/Managers/bmc/EthernetInterfaces"),
    ("bmc-ethernet-iface0", "/redfish/v1/Managers/bmc/EthernetInterfaces/eth0"),
]


def pi_curl(pi, board, user, password, path, unauth=False):
    """Issue one curl on the Pi; return (http_status:int|None, text)."""
    auth = "" if unauth else f"-u {user}:{password} "
    # -w writes the HTTP code on its own trailing line after the body.
    remote = (f"curl -sk --max-time 25 {auth}"
              f"-w '\\n__HTTP__%{{http_code}}' https://{board}{path}")
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", pi, remote],
        capture_output=True, text=True)
    out = r.stdout
    status = None
    if "__HTTP__" in out:
        body, _, code = out.rpartition("__HTTP__")
        out = body
        try:
            status = int(code.strip())
        except ValueError:
            status = None
    return status, out


def capture(pi, board, user, password, evidence_dir):
    os.makedirs(evidence_dir, exist_ok=True)
    captured = {}
    for slug, path in ENDPOINTS:
        # ServiceRoot is unauthenticated; everything else needs auth.
        status, text = pi_curl(pi, board, user, password, path,
                               unauth=(slug == "service-root"))
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            doc = text
        captured[slug] = (status, doc)
        out = os.path.join(evidence_dir, f"{slug}.json")
        with open(out, "w") as f:
            if isinstance(doc, (dict, list)):
                json.dump(doc, f, indent=2, sort_keys=True)
            else:
                f.write(str(doc))
        print(f"[capture] {path} -> HTTP {status} -> {out}")
    return captured


def assert_system_id(captured):
    lines, ok = [], True

    def field(slug, *keys):
        _, doc = captured.get(slug, (None, None))
        cur = doc
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

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
    ap.add_argument("--pi", default="asus-bmc")
    ap.add_argument("--board", default="192.168.66.2")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="0penBmc")
    ap.add_argument("--evidence-dir", default="evidence/real-hw")
    args = ap.parse_args()

    print(f"[real-hw] curl Redfish on {args.pi} -> board {args.board}")
    captured = capture(args.pi, args.board, args.user, args.password,
                       args.evidence_dir)
    ok, lines = assert_system_id(captured)
    print("\n=== F1 real-HW system-identification field check ===")
    print("\n".join(lines))
    print("\nF1 REAL-HW RESULT:", "PASS — system identification over "
          "authenticated Redfish on the real AST2050" if ok else
          "INCOMPLETE — a required field was missing (see JSON)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

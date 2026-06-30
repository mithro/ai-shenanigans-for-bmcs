#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Boot the Dell C410X proprietary firmware on kgpe-d16-bmc and verify its BMC
web service (appweb) responds — the C4 acceptance check.

Boots QEMU with the assembled flash and a slirp hostfwd (host port -> guest :80),
then polls the forwarded port until appweb answers (the firmware DHCPs to slirp's
10.0.2.15, so the forward reaches it). Succeeds when an HTTP response arrives.
"""
import argparse
import socket
import subprocess
import time
import urllib.request


def http_probe(port):
    """Return (status, body_snippet) if the BMC web server answers, else None."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=6) as r:
            return r.status, r.read(800)
    except urllib.error.HTTPError as e:          # a 401/403/302 still proves it serves
        return e.code, (e.read(400) if e.fp else b"")
    except (urllib.error.URLError, ConnectionError, socket.timeout, OSError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--flash", required=True)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--boot-timeout", type=int, default=600)
    args = ap.parse_args()

    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", "128", "-display", "none",
           "-monitor", "none", "-serial", "file:c410x-serial.log",
           "-nic", f"user,model=ftgmac100,hostfwd=tcp::{args.port}-:80",
           "-drive", f"file={args.flash},format=raw,if=mtd", "-no-reboot"]
    print("+", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + args.boot_timeout
        while time.monotonic() < deadline:
            if qemu.poll() is not None:
                print(f"C4 RESULT: FAIL — qemu exited early (rc={qemu.returncode})")
                return 1
            probe = http_probe(args.port)
            if probe:
                status, body = probe
                print(f"\n=== BMC web responded: HTTP {status} ===")
                print(body.decode("latin1", "replace")[:800])
                print("\nC4 RESULT: PASS — proprietary firmware booted to a "
                      "running BMC web service")
                return 0
            time.sleep(5)
        print("C4 RESULT: FAIL — no web response within "
              f"{args.boot_timeout}s (see c410x-serial.log)")
        return 1
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    raise SystemExit(main())

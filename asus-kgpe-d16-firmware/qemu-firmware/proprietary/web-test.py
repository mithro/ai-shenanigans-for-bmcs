#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Boot the Dell C410X proprietary firmware on kgpe-d16-bmc and verify its BMC
web service (appweb) responds — the C4 acceptance check.

Boots QEMU with the assembled flash and a slirp hostfwd (host port -> guest :80),
then polls the forwarded port until appweb answers. The wrapper initramfs brings
eth0 up with slirp's guest IP (10.0.2.15), so the forward reaches the BMC web
server. Succeeds when any HTTP response arrives (appweb 301-redirects to the HTTPS
login page — a redirect still proves it serves).
"""
import argparse
import socket
import subprocess
import time


def http_probe(port):
    """Return (status_line, snippet) if the BMC web server answers, else None.

    Raw HTTP/1.0 GET over a socket so a 3xx redirect counts as "serving" (urllib
    would follow appweb's 301 to https:// and fail).
    """
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=6) as s:
            s.sendall(b"GET / HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
            s.settimeout(6)
            data = b""
            while len(data) < 800:
                chunk = s.recv(800 - len(data))
                if not chunk:
                    break
                data += chunk
    except (ConnectionError, socket.timeout, OSError):
        return None
    if not data.startswith(b"HTTP/"):
        return None
    status_line = data.split(b"\r\n", 1)[0].decode("latin1", "replace")
    return status_line, data


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
                status_line, body = probe
                print(f"\n=== BMC web responded: {status_line} ===")
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

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Push tmp/poll_ring_host.py to the host and run it (streams TXR_BADR/MACCR poll)."""
import subprocess, base64, sys, os
PI, HOST = "asus-bmc", "192.168.77.138"
SOPT = "-o StrictHostKeyChecking=" + "no"
HERE = os.path.dirname(os.path.abspath(__file__))
b64 = base64.b64encode(open(os.path.join(HERE, "poll_ring_host.py"), "rb").read()).decode()
def hostrun(inner, t=200):
    full = f"sshpass -p systemrescue ssh {SOPT} -o ConnectTimeout=10 root@{HOST} {inner!r}"
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", PI, full],
                          text=True, capture_output=True, timeout=t)
hostrun(f"echo {b64} | base64 -d > /root/poll_ring_host.py")
r = hostrun("python3 /root/poll_ring_host.py")
sys.stdout.write(r.stdout)
if r.stderr.strip():
    sys.stderr.write(r.stderr[-800:])

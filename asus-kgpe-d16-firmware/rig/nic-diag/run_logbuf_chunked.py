#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Push logbuf_chunked_host.py to the host, run it (chunked __log_buf read over P2A,
the only reliable way — the P2A window returns ~2KB/read), and print the diagnostic
lines: the VIC pr_warn, the FTTMR010 clockevent-fires verdict, and the ftgmac markers."""
import subprocess, base64, sys, os, re
PI, HOST = "asus-bmc", "192.168.77.138"
SOPT = "-o StrictHostKeyChecking=" + "no"
HERE = os.path.dirname(os.path.abspath(__file__))
b64 = base64.b64encode(open(os.path.join(HERE, "logbuf_chunked_host.py"), "rb").read()).decode()

PATTERNS = re.compile(
    r"AST2050-VIC|FTTMR010-CHECK|clockevent|AST2050-OPEN|Link is|IP-Config|"
    r"nfs|VFS:|Kernel panic|Booting Linux|Switched to clocksource|ftgmac",
    re.IGNORECASE)


def hostrun(inner, t=180):
    full = f"sshpass -p systemrescue ssh {SOPT} -o ConnectTimeout=10 root@{HOST} {inner!r}"
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", PI, full],
                          text=True, capture_output=True, timeout=t)


hostrun(f"echo {b64} | base64 -d > /root/logbuf_chunked_host.py")
r = hostrun("python3 /root/logbuf_chunked_host.py")
matched = [ln for ln in r.stdout.splitlines() if PATTERNS.search(ln)]
print("\n".join(matched) if matched else "[no diagnostic markers found in __log_buf]")
if r.stderr.strip():
    sys.stderr.write(r.stderr[-500:])

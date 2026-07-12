#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Drive the live U-Boot on the AST2050 BMC over /dev/serial-bmc-console (via the
Pi). U-Boot must already be running at its prompt (loaded by p2a-image-boot.py).

Sends a sequence of commands (one per --cmd, in order), each followed by CR, with a
per-command settle delay, and captures the whole session. Because the mini-UART is
1200 8N1, keep commands short and allow generous delays for slow output (e.g. tftp).

  uv run uboot-console.py --cmd "printenv" --cmd "ping 192.168.66.1"
  uv run uboot-console.py --watch 40 --cmd "setenv ipaddr 192.168.66.2" --cmd "..."
"""
import argparse, subprocess, sys, time

PI = "asus-bmc"
BMC = "/dev/serial-bmc-console"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", action="append", default=[], help="a U-Boot command (repeatable)")
    ap.add_argument("--watch", type=int, default=25, help="total capture seconds")
    ap.add_argument("--gap", type=float, default=2.0, help="seconds between commands")
    ap.add_argument("--baud", type=int, default=1200)
    args = ap.parse_args()

    subprocess.run(["ssh", "-o", "BatchMode=yes", PI,
                    f"sudo stty -F {BMC} {args.baud} raw -echo -crtscts cs8 -parenb -cstopb"],
                   capture_output=True, text=True)
    cap = subprocess.Popen(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", PI,
                            f"sudo timeout {args.watch} cat {BMC}"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(1.5)
    # wake the prompt
    subprocess.run(["ssh", "-o", "BatchMode=yes", PI,
                    f"printf '\\r' | sudo dd of={BMC} status=none"], capture_output=True, text=True)
    time.sleep(args.gap)
    for c in args.cmd:
        line = (c + "\r").replace("'", "'\\''")
        subprocess.run(["ssh", "-o", "BatchMode=yes", PI,
                        f"printf '{line}' | sudo dd of={BMC} status=none"],
                       capture_output=True, text=True)
        time.sleep(args.gap)
    try:
        out, _ = cap.communicate(timeout=args.watch + 8)
    except subprocess.TimeoutExpired:
        cap.kill(); out, _ = cap.communicate()
    print(out)


if __name__ == "__main__":
    sys.exit(main())

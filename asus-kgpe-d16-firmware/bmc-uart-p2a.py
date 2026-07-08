#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Drive the AST2050 BMC debug UART (UART2 @ 0x1e784000) over culvert P2A and read
it back on the Pi's /dev/serial-bmc-console — proves/exercises the BMC<->Pi serial
channel with the ARM dead. See P2A-DRAM-BOOT-SEQUENCE.md §0.

Runs culvert on the PXE host (reached via the ASUS bridge Pi). Baud default 1200 8N1
(reliable on the Pi mini-UART; UARTCLK=24MHz so divisor = 24e6/(16*baud)).

  uv run bmc-uart-p2a.py                    # config UART2 @1200, send a test string
  uv run bmc-uart-p2a.py --baud 1200 --msg "HELLO"
  uv run bmc-uart-p2a.py --config-only      # just configure (e.g. before the ARM drives it)
"""
import argparse, subprocess, sys, time

PI = "asus-bmc"
HOST = "192.168.77.138"
CULVERT = "/root/culvert-g3/build/src/culvert p2a vga"
UART2 = 0x1e784000        # AST2050 debug UART (Raptor .Done target); UART1=0x1e783000 is unwired
BMC_TTY = "/dev/serial-bmc-console"


def pi(cmd, t=60, stdin=None):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", PI, cmd],
                          text=True, capture_output=True, input=stdin, timeout=t)


def divisor(baud):
    d = round(24_000_000 / (16 * baud))       # UARTCLK = 24 MHz, SCU2C[12]=0
    return d & 0xff, (d >> 8) & 0xff           # DLL, DLH


def config_cmds(base, baud):
    dll, dlh = divisor(baud)
    return [f"{CULVERT} write {base+0x0c:#x} 0x83",      # LCR: DLAB=1, 8N1
            f"{CULVERT} write {base+0x00:#x} {dll:#x}",  # DLL
            f"{CULVERT} write {base+0x04:#x} {dlh:#x}",  # DLH
            f"{CULVERT} write {base+0x0c:#x} 0x03",      # LCR: DLAB=0, 8N1
            f"{CULVERT} write {base+0x08:#x} 0x07"]      # FCR: enable + clear FIFOs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baud", type=int, default=1200)
    ap.add_argument("--msg", default="BMC-UART2-P2A-OK")
    ap.add_argument("--config-only", action="store_true")
    args = ap.parse_args()

    cmds = ["cd /root/culvert-g3"] + config_cmds(UART2, args.baud)
    if not args.config_only:
        for ch in args.msg + "\r\n":
            cmds.append(f"{CULVERT} write {UART2:#x} {ord(ch):#x}")
    cmds.append("echo done")
    host_script = "\n".join(cmds) + "\n"

    cap = None
    if not args.config_only:
        # capture the Pi serial console in parallel (held-open ssh so it isn't SIGHUP'd)
        pi(f"sudo stty -F {BMC_TTY} {args.baud} raw -echo -crtscts cs8 -parenb -cstopb")
        cap = subprocess.Popen(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", PI,
             f"sudo timeout 12 cat {BMC_TTY} | od -An -c"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(2)

    hostcmd = (f"sshpass -p systemrescue ssh -o StrictHostKeyChecking=accept-new "
               f"-o ConnectTimeout=12 root@{HOST} bash -s")
    r = pi(hostcmd, t=80, stdin=host_script)
    print(f"[*] configured UART2 @ {args.baud} 8N1 (DLL/DLH = {divisor(args.baud)})")
    if r.stderr.strip():
        print("[stderr]", r.stderr[-200:])

    if cap:
        try:
            out, _ = cap.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            cap.kill(); out, _ = cap.communicate()
        print(f"=== read back on {BMC_TTY} ===\n{out.strip() or '(nothing — check wiring/baud)'}")


if __name__ == "__main__":
    sys.exit(main())

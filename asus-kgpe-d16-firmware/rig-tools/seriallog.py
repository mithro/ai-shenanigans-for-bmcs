#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Continuously log a serial port to a file with timestamps (stdlib only).

Runs ON rpi4-asus-aspeed2050-dev as a daemon.  It *owns* the serial port and
appends everything it reads to a logfile (with a timestamp marker whenever data
resumes after a >1s gap).  View live with:  tail -f ~/hw-capture/com1.log

    seriallog.py --port /dev/serial-com1 --baud 115200 --out ~/hw-capture/com1.log

Only one reader may own a tty at a time — run exactly one instance per port and
tail its logfile rather than opening the port again.
"""
import argparse
import os
import select
import termios
import time

BAUDS = {
    110: termios.B110, 300: termios.B300, 600: termios.B600, 1200: termios.B1200,
    2400: termios.B2400, 4800: termios.B4800, 9600: termios.B9600,
    19200: termios.B19200, 38400: termios.B38400, 57600: termios.B57600,
    115200: termios.B115200, 230400: termios.B230400,
}


def configure(fd, baud):
    """Put the tty in raw 8N1 at the requested baud."""
    if baud not in BAUDS:
        raise SystemExit(f"unsupported baud {baud}; choose from {sorted(BAUDS)}")
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(fd)
    iflag = 0
    oflag = 0
    lflag = 0
    cflag |= (termios.CLOCAL | termios.CREAD)
    cflag &= ~termios.PARENB           # no parity
    cflag &= ~termios.CSTOPB           # 1 stop bit
    cflag &= ~termios.CSIZE
    cflag |= termios.CS8               # 8 data bits
    ispeed = ospeed = BAUDS[baud]
    cc[termios.VMIN] = 0
    cc[termios.VTIME] = 1
    termios.tcsetattr(fd, termios.TCSANOW,
                      [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/serial-com1")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--out", default=os.path.expanduser("~/hw-capture/com1.log"))
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    fd = os.open(a.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    configure(fd, a.baud)
    with open(a.out, "ab", buffering=0) as log:
        start = time.strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"\n===== seriallog start {start} port={a.port} baud={a.baud} =====\n".encode())
        last = 0.0
        while True:
            r, _, _ = select.select([fd], [], [], 1.0)
            if fd not in r:
                continue
            try:
                data = os.read(fd, 4096)
            except OSError:
                continue
            if not data:
                continue
            now = time.time()
            if now - last > 1.0:
                log.write(f"\n[{time.strftime('%H:%M:%S')}] ".encode())
            last = now
            log.write(data)


if __name__ == "__main__":
    main()

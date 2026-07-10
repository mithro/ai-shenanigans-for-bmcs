#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Serial-console daemon — the *single owner* of a serial port.

Running exactly one of these per port is what prevents multi-reader / multi-writer
races on the tty:
  * RX  (port -> file): everything read from the port is appended to a log file
    with timestamps.  Any number of clients may read that file concurrently
    (`tail -f`, `serialscreen.py`) — they never open the tty.
  * TX  (FIFO -> port): bytes written to the control FIFO are forwarded to the
    port.  Clients (serialkey.py) write to the FIFO instead of opening the tty,
    so there is only ever one writer of the device.

    seriald.py --port /dev/serial-com1 --baud 115200 \
               --log ~/hw-capture/com1.log --tx ~/hw-capture/com1.tx

Start it once (e.g. via systemd or setsid nohup).  Stdlib only.
"""
import argparse
import os
import select
import termios
import time

BAUDS = {9600: termios.B9600, 19200: termios.B19200, 38400: termios.B38400,
         57600: termios.B57600, 115200: termios.B115200, 230400: termios.B230400}


def configure(fd, baud):
    if baud not in BAUDS:
        raise SystemExit(f"unsupported baud {baud}; choose {sorted(BAUDS)}")
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(fd)
    iflag = oflag = lflag = 0
    cflag |= (termios.CLOCAL | termios.CREAD)
    cflag &= ~termios.PARENB
    cflag &= ~termios.CSTOPB
    cflag &= ~termios.CSIZE
    cflag |= termios.CS8
    ispeed = ospeed = BAUDS[baud]
    cc[termios.VMIN] = 0
    cc[termios.VTIME] = 1
    termios.tcsetattr(fd, termios.TCSANOW,
                      [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/serial-com1")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--log", default="~/hw-capture/com1.log")
    ap.add_argument("--tx", default="~/hw-capture/com1.tx")
    a = ap.parse_args()

    log_path = os.path.expanduser(a.log)
    tx_path = os.path.expanduser(a.tx)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    port_fd = os.open(a.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    configure(port_fd, a.baud)

    if not os.path.exists(tx_path):
        os.mkfifo(tx_path, 0o600)
    # O_RDONLY nonblock so we can select() on it; keep a writer fd open so the
    # FIFO never signals EOF when a client closes its end.
    tx_fd = os.open(tx_path, os.O_RDONLY | os.O_NONBLOCK)
    os.open(tx_path, os.O_WRONLY | os.O_NONBLOCK)  # keepalive writer (leaked on purpose)

    log = open(log_path, "ab", buffering=0)
    log.write(f"\n===== seriald start {time.strftime('%Y-%m-%d %H:%M:%S')} "
              f"port={a.port} baud={a.baud} =====\n".encode())
    last = 0.0
    while True:
        r, _, _ = select.select([port_fd, tx_fd], [], [], 1.0)
        if port_fd in r:
            try:
                data = os.read(port_fd, 4096)
            except OSError:
                data = b""
            if data:
                now = time.time()
                if now - last > 1.0:
                    log.write(f"\n[{time.strftime('%H:%M:%S')}] ".encode())
                last = now
                log.write(data)
        if tx_fd in r:
            try:
                cmd = os.read(tx_fd, 4096)
            except OSError:
                cmd = b""
            if cmd:
                os.write(port_fd, cmd)


if __name__ == "__main__":
    main()

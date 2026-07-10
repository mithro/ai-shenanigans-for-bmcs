#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Send keystrokes to the ASUS BIOS over the serial console (COM1 redirection).

Runs ON rpi4-asus-aspeed2050-dev, writing to /dev/serial-com1.  This is the
serial twin of keysend.py: it lets us drive AMIBIOS Setup over the comm port
(no USB keyboard / Magewell).  The read-only serial logger can keep running —
this only writes; the logger captures the BIOS's responses, which you then
render with serialscreen.py.

Key encodings target AMIBIOS Terminal Type = VT100:
  arrows  ESC[A/B/C/D      Enter CR    ESC 0x1b    Tab \\t    Space
  DEL 0x7f (Delete / common Setup-entry key)   BACKSPACE 0x08
  F1..F10 = ESC 1..0, F11 = ESC !, F12 = ESC @   (AMI terminal combo keys)

Usage:
    serialkey.py type "115200"
    serialkey.py press DEL
    serialkey.py press DOWN DOWN ENTER
    serialkey.py raw 1b 5b 41            # raw hex bytes (ESC [ A)
    serialkey.py script 'press:DEL|sleep:200|press:DOWN'
Options: --port, --baud (default 115200), --delay MS between keys (default 60),
         --app (use ESC O x application-mode arrows instead of ESC [ x).
"""
import argparse
import os
import sys
import termios
import time

BAUDS = {9600: termios.B9600, 19200: termios.B19200, 38400: termios.B38400,
         57600: termios.B57600, 115200: termios.B115200}

NAMED = {
    "ENTER": b"\r", "RETURN": b"\r", "CR": b"\r", "LF": b"\n",
    "ESC": b"\x1b", "ESCAPE": b"\x1b", "TAB": b"\t", "SPACE": b" ",
    "BACKSPACE": b"\x08", "BKSP": b"\x08", "BS": b"\x08",
    "DEL": b"\x7f", "DELETE": b"\x7f",
    "UP": b"\x1b[A", "DOWN": b"\x1b[B", "RIGHT": b"\x1b[C", "LEFT": b"\x1b[D",
    "HOME": b"\x1b[H", "END": b"\x1b[K", "INS": b"\x1b[@",
    "PGUP": b"\x1b[V", "PGDN": b"\x1b[U",
    "F1": b"\x1b1", "F2": b"\x1b2", "F3": b"\x1b3", "F4": b"\x1b4",
    "F5": b"\x1b5", "F6": b"\x1b6", "F7": b"\x1b7", "F8": b"\x1b8",
    "F9": b"\x1b9", "F10": b"\x1b0", "F11": b"\x1b!", "F12": b"\x1b@",
    "PLUS": b"+", "MINUS": b"-",
}
APP_ARROWS = {"UP": b"\x1bOA", "DOWN": b"\x1bOB", "RIGHT": b"\x1bOC", "LEFT": b"\x1bOD"}


def configure(fd, baud):
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(fd)
    iflag = oflag = lflag = 0
    cflag |= (termios.CLOCAL | termios.CREAD)
    cflag &= ~termios.PARENB
    cflag &= ~termios.CSTOPB
    cflag &= ~termios.CSIZE
    cflag |= termios.CS8
    ispeed = ospeed = BAUDS[baud]
    termios.tcsetattr(fd, termios.TCSANOW,
                      [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])


class Sender:
    def __init__(self, port, baud, delay_ms, app=False):
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
        configure(self.fd, baud)
        self.delay = delay_ms / 1000.0
        self.app = app

    def send(self, data):
        os.write(self.fd, data)

    def key(self, name):
        u = name.upper()
        seq = (APP_ARROWS.get(u) if self.app else None) or NAMED.get(u)
        if seq is None:
            if len(name) == 1:
                seq = name.encode()
            else:
                sys.exit(f"serialkey: unknown key {name!r}")
        self.send(seq)
        time.sleep(self.delay)

    def type_text(self, text):
        for ch in text:
            self.send(ch.encode())
            time.sleep(self.delay)

    def script(self, text):
        for step in text.replace("\n", "|").split("|"):
            step = step.strip()
            if not step:
                continue
            op, _, arg = step.partition(":")
            op = op.strip().lower()
            if op == "type":
                self.type_text(arg)
            elif op == "press":
                for k in arg.split():
                    self.key(k)
            elif op == "raw":
                self.send(bytes(int(x, 16) for x in arg.split()))
            elif op == "sleep":
                time.sleep(float(arg) / 1000.0)
            else:
                sys.exit(f"serialkey: unknown script op {op!r}")

    def close(self):
        os.close(self.fd)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/serial-com1")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--delay", type=int, default=60)
    ap.add_argument("--app", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("type"); p.add_argument("text")
    p = sub.add_parser("press"); p.add_argument("keys", nargs="+")
    p = sub.add_parser("raw"); p.add_argument("hex", nargs="+")
    p = sub.add_parser("script"); p.add_argument("src")
    a = ap.parse_args()

    s = Sender(a.port, a.baud, a.delay, a.app)
    try:
        if a.cmd == "type":
            s.type_text(a.text)
        elif a.cmd == "press":
            for k in a.keys:
                s.key(k)
        elif a.cmd == "raw":
            s.send(bytes(int(x, 16) for x in a.hex))
        elif a.cmd == "script":
            s.script(a.src)
    finally:
        s.close()


if __name__ == "__main__":
    main()

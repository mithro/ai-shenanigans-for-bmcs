#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Send keystrokes to a USB HID *boot-protocol* keyboard gadget.

Runs ON opi1pc-a (the USB-gadget board), writing 8-byte HID boot-keyboard
reports to /dev/hidg0 — so the ASUS host (and its BIOS) sees a real keyboard.

Report format (USB HID Boot Keyboard, 8 bytes):
    [modifiers][reserved=0][keycode1..keycode6]
A keypress = one report with the key set, then an all-zero report (release).

Usage (run as root, e.g. via sudo):
    keysend.py type "ls -la"            # type literal text
    keysend.py press ENTER              # one named key
    keysend.py press DOWN DOWN ENTER    # a sequence of named keys
    keysend.py combo CTRL ALT DEL       # modifiers + final key, chorded
    keysend.py hold 2000 F2             # hold a key for N ms (spam-free single press held)
    echo 'type:root|press:ENTER' | keysend.py script -   # mini-script via stdin

Tunables: --delay MS (gap between keys, default 24), --hold MS (press duration,
default 12), --dev PATH (default /dev/hidg0). BIOS menus can need slower timing;
bump --delay/--hold if keys are missed.  Never assume the hardware dropped a key
before ruling out too-fast timing.
"""
import argparse
import sys
import time

DEV_DEFAULT = "/dev/hidg0"

MOD = {"CTRL": 0x01, "LCTRL": 0x01, "SHIFT": 0x02, "LSHIFT": 0x02,
       "ALT": 0x04, "LALT": 0x04, "GUI": 0x08, "WIN": 0x08, "META": 0x08,
       "RCTRL": 0x10, "RSHIFT": 0x20, "RALT": 0x40, "ALTGR": 0x40, "RGUI": 0x80}

# Named non-character keys -> HID usage id
NAMED = {
    "ENTER": 0x28, "RETURN": 0x28, "ESC": 0x29, "ESCAPE": 0x29,
    "BACKSPACE": 0x2A, "BKSP": 0x2A, "BS": 0x2A, "TAB": 0x2B, "SPACE": 0x2C,
    "CAPS": 0x39, "CAPSLOCK": 0x39,
    "F1": 0x3A, "F2": 0x3B, "F3": 0x3C, "F4": 0x3D, "F5": 0x3E, "F6": 0x3F,
    "F7": 0x40, "F8": 0x41, "F9": 0x42, "F10": 0x43, "F11": 0x44, "F12": 0x45,
    "PRTSC": 0x46, "SCROLLLOCK": 0x47, "PAUSE": 0x48,
    "INS": 0x49, "INSERT": 0x49, "HOME": 0x4A, "PGUP": 0x4B, "PAGEUP": 0x4B,
    "DEL": 0x4C, "DELETE": 0x4C, "END": 0x4D, "PGDN": 0x4E, "PAGEDOWN": 0x4E,
    "RIGHT": 0x4F, "LEFT": 0x50, "DOWN": 0x51, "UP": 0x52,
    "NUMLOCK": 0x53, "MENU": 0x65, "APP": 0x65,
}

# Characters typeable without shift -> HID usage id
_UNSHIFTED = {
    "\n": 0x28, "\t": 0x2B, " ": 0x2C,
    "-": 0x2D, "=": 0x2E, "[": 0x2F, "]": 0x30, "\\": 0x31, ";": 0x33,
    "'": 0x34, "`": 0x35, ",": 0x36, ".": 0x37, "/": 0x38,
}
for _i, _c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _UNSHIFTED[_c] = 0x04 + _i
for _i, _c in enumerate("1234567890"):
    _UNSHIFTED[_c] = 0x1E + _i

# Characters needing Shift -> HID usage id (of the base key)
_SHIFTED = {
    "!": 0x1E, "@": 0x1F, "#": 0x20, "$": 0x21, "%": 0x22, "^": 0x23,
    "&": 0x24, "*": 0x25, "(": 0x26, ")": 0x27,
    "_": 0x2D, "+": 0x2E, "{": 0x2F, "}": 0x30, "|": 0x31, ":": 0x33,
    '"': 0x34, "~": 0x35, "<": 0x36, ">": 0x37, "?": 0x38,
}
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    _SHIFTED[_c] = 0x04 + (ord(_c) - ord("A"))


def char_to_report(ch):
    """Return (modifier, usage) for a single character, or None if unsupported."""
    if ch in _UNSHIFTED:
        return (0, _UNSHIFTED[ch])
    if ch in _SHIFTED:
        return (MOD["SHIFT"], _SHIFTED[ch])
    return None


class Keyboard:
    def __init__(self, dev=DEV_DEFAULT, hold_ms=12, delay_ms=24):
        self.dev = dev
        self.hold = hold_ms / 1000.0
        self.delay = delay_ms / 1000.0
        # Open unbuffered binary; keep fd for the whole run.
        self.fd = open(dev, "wb", buffering=0)

    def _write(self, mod, usages):
        report = bytes([mod & 0xFF, 0x00] + (list(usages) + [0] * 6)[:6])
        self.fd.write(report)
        self.fd.flush()

    def tap(self, mod, usage, hold=None):
        self._write(mod, [usage])
        time.sleep(self.hold if hold is None else hold)
        self._write(0, [])          # release
        time.sleep(self.delay)

    def type_text(self, text):
        for ch in text:
            r = char_to_report(ch)
            if r is None:
                sys.stderr.write(f"keysend: skipping unsupported char {ch!r}\n")
                continue
            self.tap(r[0], r[1])

    def press_named(self, name):
        key = name.upper()
        if key in NAMED:
            self.tap(0, NAMED[key])
        elif key in MOD:
            # a lone modifier tap (rarely useful, but supported)
            self._write(MOD[key], [])
            time.sleep(self.hold)
            self._write(0, [])
            time.sleep(self.delay)
        elif len(name) == 1:
            r = char_to_report(name)
            if r:
                self.tap(r[0], r[1])
            else:
                sys.exit(f"keysend: unknown key {name!r}")
        else:
            sys.exit(f"keysend: unknown key name {name!r}")

    def combo(self, tokens):
        mod = 0
        key_usage = None
        for t in tokens:
            u = t.upper()
            if u in MOD:
                mod |= MOD[u]
            elif u in NAMED:
                key_usage = NAMED[u]
            elif len(t) == 1:
                r = char_to_report(t)
                if r is None:
                    sys.exit(f"keysend: unknown combo key {t!r}")
                mod |= r[0]
                key_usage = r[1]
            else:
                sys.exit(f"keysend: unknown combo token {t!r}")
        if key_usage is None:
            sys.exit("keysend: combo needs one non-modifier key")
        self.tap(mod, key_usage)

    def close(self):
        # Ensure keys are released even if something above failed.
        try:
            self._write(0, [])
        finally:
            self.fd.close()


def run_script(kb, text):
    """Mini-script: 'type:hello|press:ENTER|combo:CTRL+c|sleep:500'."""
    for step in text.replace("\n", "|").split("|"):
        step = step.strip()
        if not step:
            continue
        op, _, arg = step.partition(":")
        op = op.strip().lower()
        if op == "type":
            kb.type_text(arg)
        elif op == "press":
            for k in arg.split():
                kb.press_named(k)
        elif op == "combo":
            kb.combo(arg.replace("+", " ").split())
        elif op == "sleep":
            time.sleep(float(arg) / 1000.0)
        else:
            sys.exit(f"keysend: unknown script op {op!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dev", default=DEV_DEFAULT)
    ap.add_argument("--hold", type=int, default=12, help="press duration ms")
    ap.add_argument("--delay", type=int, default=24, help="gap between keys ms")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("type"); p.add_argument("text")
    p = sub.add_parser("press"); p.add_argument("keys", nargs="+")
    p = sub.add_parser("combo"); p.add_argument("tokens", nargs="+")
    p = sub.add_parser("hold"); p.add_argument("ms", type=int); p.add_argument("key")
    p = sub.add_parser("script"); p.add_argument("src", help="text or '-' for stdin")
    args = ap.parse_args()

    kb = Keyboard(args.dev, args.hold, args.delay)
    try:
        if args.cmd == "type":
            kb.type_text(args.text)
        elif args.cmd == "press":
            for k in args.keys:
                kb.press_named(k)
        elif args.cmd == "combo":
            kb.combo(args.tokens)
        elif args.cmd == "hold":
            key = args.key.upper()
            usage = NAMED.get(key)
            mod = 0
            if usage is None:
                r = char_to_report(args.key)
                if r is None:
                    sys.exit(f"keysend: unknown key {args.key!r}")
                mod, usage = r
            kb.tap(mod, usage, hold=args.ms / 1000.0)
        elif args.cmd == "script":
            text = sys.stdin.read() if args.src == "-" else args.src
            run_script(kb, text)
    finally:
        kb.close()


if __name__ == "__main__":
    main()

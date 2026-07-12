#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Reconstruct the 80x25 text screen from a VT100/ANSI serial capture.

AMIBIOS console redirection paints the Setup menu at absolute cursor positions
(ESC[row;colH) with clears (ESC[2J) — so a linear escape-strip is unreadable.
This is a minimal VT100 grid emulator: feed it the raw serial log and it prints
the resulting screen, i.e. what a terminal would be showing.  This is how we
"see the BIOS on the comm port" without the Magewell.

    serialscreen.py ~/hw-capture/com1.log            # render current screen
    serialscreen.py ~/hw-capture/com1.log --rows 25  # force size
    serialscreen.py --from-last-clear LOG            # start at last ESC[2J

Stdlib only.
"""
import argparse
import re

CSI_RE = re.compile(rb"\x1b\[([0-9;?]*)([@-~])")


class Screen:
    def __init__(self, cols=80, rows=25):
        self.cols, self.rows = cols, rows
        self.grid = [[" "] * cols for _ in range(rows)]
        self.r = self.c = 0

    def _clamp(self):
        self.r = max(0, min(self.rows - 1, self.r))
        self.c = max(0, min(self.cols - 1, self.c))

    def _scroll(self):
        while self.r >= self.rows:
            self.grid.pop(0)
            self.grid.append([" "] * self.cols)
            self.r -= 1

    def put(self, ch):
        if self.c >= self.cols:
            self.c = 0
            self.r += 1
            self._scroll()
        self.grid[self.r][self.c] = ch
        self.c += 1

    def feed(self, data):
        i, n = 0, len(data)
        while i < n:
            b = data[i]
            if b == 0x1B:  # ESC
                m = CSI_RE.match(data, i)
                if m:
                    self._csi(m.group(1), m.group(2))
                    i = m.end()
                    continue
                # non-CSI escape (charset select, keypad mode): skip ESC + 1 byte
                i += 2
                continue
            if b == 0x0D:      # CR
                self.c = 0
            elif b == 0x0A:    # LF
                self.r += 1
                self._scroll()
            elif b == 0x08:    # BS
                self.c = max(0, self.c - 1)
            elif b == 0x09:    # TAB
                self.c = min(self.cols - 1, (self.c // 8 + 1) * 8)
            elif 0x20 <= b <= 0x7E:
                self.put(chr(b))
            # else: ignore other control bytes
            i += 1

    def _csi(self, params, final):
        f = chr(final[0])
        nums = [int(x) for x in params.split(b";") if x.isdigit()]
        if f in "Hf":                       # cursor position (1-based)
            self.r = (nums[0] - 1) if len(nums) >= 1 and nums[0] else 0
            self.c = (nums[1] - 1) if len(nums) >= 2 and nums[1] else 0
            self._clamp()
        elif f == "A":
            self.r -= nums[0] if nums else 1; self._clamp()
        elif f == "B":
            self.r += nums[0] if nums else 1; self._clamp()
        elif f == "C":
            self.c += nums[0] if nums else 1; self._clamp()
        elif f == "D":
            self.c -= nums[0] if nums else 1; self._clamp()
        elif f == "J":                      # erase display
            mode = nums[0] if nums else 0
            if mode == 2:
                self.grid = [[" "] * self.cols for _ in range(self.rows)]
                self.r = self.c = 0
        elif f == "K":                      # erase line
            mode = nums[0] if nums else 0
            if mode == 0:
                for x in range(self.c, self.cols): self.grid[self.r][x] = " "
            elif mode == 1:
                for x in range(0, self.c + 1): self.grid[self.r][x] = " "
            elif mode == 2:
                self.grid[self.r] = [" "] * self.cols
        # 'm' (SGR/colours) and others: ignored

    def render(self):
        return "\n".join("".join(row).rstrip() for row in self.grid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--cols", type=int, default=80)
    ap.add_argument("--rows", type=int, default=25)
    ap.add_argument("--from-last-clear", action="store_true",
                    help="start rendering at the last ESC[2J clear")
    a = ap.parse_args()
    data = open(a.path, "rb").read()
    if a.from_last_clear:
        idx = data.rfind(b"\x1b[2J")
        if idx >= 0:
            data = data[idx:]
    scr = Screen(a.cols, a.rows)
    scr.feed(data)
    print(scr.render())


if __name__ == "__main__":
    main()

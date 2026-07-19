#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Regenerate the DEVICE-MATRIX.md coverage snapshot tally.

Parses every device row (leading cell is an integer id) and counts the status
glyph in each of the 8 per-stack columns (QE/UQ/US/LQ/LS/LU/ZQ/ZS). Prints a
Markdown table matching the snapshot, plus the row count, so the numbers can be
pasted back into the "Coverage snapshot" section. Stdlib only; run with uv.
"""
import re
import sys
from pathlib import Path

MATRIX = Path(__file__).with_name("DEVICE-MATRIX.md")
COLS = ["QE", "UQ", "US", "LQ", "LS", "LU", "ZQ", "ZS"]
GLYPHS = ["✅", "🔶", "🔷", "⬜", "Ⓝ"]
LABELS = {
    "QE": "QEMU emulation", "UQ": "U-Boot @ QEMU", "US": "U-Boot @ silicon",
    "LQ": "Linux @ QEMU", "LS": "Linux @ silicon", "LU": "Linux userspace",
    "ZQ": "Zephyr @ QEMU", "ZS": "Zephyr @ silicon",
}


def main() -> int:
    counts = {c: {g: 0 for g in GLYPHS} for c in COLS}
    rows = 0
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # A device row: >=11 cells and the first cell is a numeric id (e.g. "26b").
        if len(cells) < 11 or not re.fullmatch(r"\d+[a-z]?", cells[0]):
            continue
        rows += 1
        status = cells[3:11]  # the 8 per-stack columns follow id/device/soc
        for col, cell in zip(COLS, status):
            for g in GLYPHS:
                if g in cell:
                    counts[col][g] += 1
                    break
            else:
                print(f"WARN row {cells[0]} col {col}: no glyph in {cell!r}",
                      file=sys.stderr)

    print(f"Rows counted: {rows}  ({rows} x 8 = {rows * 8} per-stack tasks)\n")
    print("| Stack × env | ✅ done | 🔶 partial | 🔷 blocked | ⬜ todo | Ⓝ n/a (justified) |")
    print("|---|---|---|---|---|---|")
    for c in COLS:
        n = counts[c]
        print(f"| {LABELS[c]} | {n['✅']} | {n['🔶']} | {n['🔷']} | {n['⬜']} | {n['Ⓝ']} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

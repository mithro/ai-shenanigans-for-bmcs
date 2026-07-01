"""Parsers for on-target command output.

Pure functions over text so they are trivially unit-testable and reused by every
backend. Kept deliberately strict -- malformed input raises rather than silently
returning a wrong-but-plausible result (fail loud, per project convention).
"""

from __future__ import annotations

import re


def parse_i2cdetect(text: str) -> set[int]:
    """Parse ``i2cdetect -y <bus>`` output into the set of responding 7-bit addresses.

    Accepts the standard grid where each cell is a two-hex-digit address, ``--``
    (no device), or ``UU`` (device present but bound to a kernel driver -- which
    still counts as *present*). The row label ``NN:`` gives the high nibble.

    >>> sorted(hex(a) for a in parse_i2cdetect(
    ...     "     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f\\n"
    ...     "00:                         -- -- -- -- -- -- -- --\\n"
    ...     "40: 40 -- -- -- -- -- -- -- UU -- -- -- -- -- -- --\\n"))
    ['0x40', '0x48']
    """
    present: set[int] = set()
    for raw in text.splitlines():
        line = raw.rstrip()
        m = re.match(r"^\s*([0-9a-fA-F]{2}):\s*(.*)$", line)
        if not m:
            continue  # header row / blank
        high = int(m.group(1), 16)
        cells = m.group(2).split()
        for col, cell in enumerate(cells):
            if cell == "--":
                continue
            if cell == "UU":
                # Device present but bound to a kernel driver; address is row|col.
                present.add(high | col)
            elif re.fullmatch(r"[0-9a-fA-F]{2}", cell):
                addr = int(cell, 16)
                # Sanity: the printed address must match row<<4 | col.
                if addr != (high | col):
                    raise ValueError(
                        f"i2cdetect cell {cell!r} at row {high:#04x} col {col} "
                        f"is inconsistent (expected {high | col:#04x})"
                    )
                present.add(addr)
            else:
                raise ValueError(f"unrecognised i2cdetect cell: {cell!r}")
    return present


def parse_sysfs_int(text: str) -> int:
    """Parse a single integer from a sysfs read (e.g. a hwmon ``*_input``)."""
    s = text.strip()
    if not re.fullmatch(r"-?\d+", s):
        raise ValueError(f"not an integer sysfs value: {s!r}")
    return int(s)


def parse_kv_lines(text: str, sep: str = "=") -> dict[str, str]:
    """Parse ``key=value`` lines (blank lines ignored) into a dict."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if sep not in line:
            raise ValueError(f"line missing {sep!r} separator: {line!r}")
        k, v = line.split(sep, 1)
        out[k.strip()] = v.strip()
    return out

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
    still counts as *present*). The row label ``NN:`` gives the high nibble, and
    each column is a fixed three-character field.

    >>> row = "40: 40 -- -- -- -- -- -- -- UU -- -- -- -- -- -- --"
    >>> sorted(hex(a) for a in parse_i2cdetect(row))
    ['0x40', '0x48']
    """
    present: set[int] = set()
    for raw in text.splitlines():
        m = re.match(r"^\s*([0-9a-fA-F]{2}):(.*)$", raw)
        if not m:
            continue  # header row / blank
        high = int(m.group(1), 16)
        region = m.group(2)
        # i2cdetect prints a FIXED 3-char field per column (" XX" / " --" / " UU"
        # / "   "). Parse by fixed width: splitting on whitespace would drop the
        # blank reserved-address cells the 0x00 row prints for 0x00-0x07 and
        # mis-shift every column after them.
        for col in range(16):
            field = region[col * 3 : col * 3 + 3]
            if len(field) < 3:
                break  # short final row (e.g. only 0x70-0x77 was scanned)
            cell = field.strip()
            if cell in ("", "--"):
                continue
            addr = high | col
            if cell == "UU":
                present.add(addr)  # present but bound to a kernel driver
            elif re.fullmatch(r"[0-9a-fA-F]{2}", cell):
                if int(cell, 16) != addr:
                    raise ValueError(
                        f"i2cdetect cell {cell!r} at row {high:#04x} col {col} "
                        f"is inconsistent (expected {addr:#04x})"
                    )
                present.add(addr)
            else:
                raise ValueError(f"unrecognised i2cdetect cell: {cell!r}")
        # Fail loud on a row wider than the 16 columns i2cdetect can print.
        if region[16 * 3:].strip():
            raise ValueError(
                f"i2cdetect row {high:#04x} has content beyond 16 columns: "
                f"{region[16 * 3:]!r}"
            )
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

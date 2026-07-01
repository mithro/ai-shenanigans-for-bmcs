"""Unit tests for the on-target output parsers."""

import pytest

from firmware_testbench.parsers import (
    parse_i2cdetect,
    parse_kv_lines,
    parse_sysfs_int,
)

def render_i2cdetect(present, first=0x08, last=0x77):
    """Render an ``i2cdetect -y`` grid byte-exactly, as the tool does.

    Each column is a fixed 3-char field (" XX" / " --" / "   "); addresses
    outside [first, last] are reserved and printed blank. This guarantees the
    fixtures match real tool output so the fixed-width parser is tested honestly.
    """
    lines = ["     " + "  ".join(f"{c:x}" for c in range(16))]
    for row in range(0x00, 0x80, 0x10):
        cells = []
        for col in range(16):
            addr = row + col
            if addr < first or addr > last:
                cells.append("   ")
            elif addr in present:
                cells.append(f" {addr:02x}")
            else:
                cells.append(" --")
        lines.append(f"{row:02x}:" + "".join(cells).rstrip())
    return "\n".join(lines) + "\n"


def test_parse_i2cdetect_full_row():
    got = parse_i2cdetect(render_i2cdetect(set(range(0x40, 0x50))))
    assert got == set(range(0x40, 0x50))


def test_parse_i2cdetect_low_addresses_in_00_row():
    # Devices in the 0x00 row must not be mis-shifted by the leading blank
    # reserved cells (0x00-0x02). Regression for the split()-based parser.
    got = parse_i2cdetect(render_i2cdetect({0x08, 0x0c}, first=0x03))
    assert got == {0x08, 0x0C}


def test_parse_i2cdetect_uu_counts_as_present():
    # Byte-exact short row: " 70"" --"" UU".
    assert parse_i2cdetect("70: 70 -- UU\n") == {0x70, 0x72}


def test_parse_i2cdetect_rejects_inconsistent_cell():
    # Address printed in the wrong column must fail loud.
    with pytest.raises(ValueError):
        parse_i2cdetect("40: 41\n")


def test_parse_i2cdetect_rejects_row_wider_than_16_columns():
    # A malformed row with a 17th column must fail loud, not silently truncate.
    with pytest.raises(ValueError):
        parse_i2cdetect("00:" + " --" * 17 + "\n")


def test_parse_sysfs_int():
    assert parse_sysfs_int(" 12500\n") == 12500
    assert parse_sysfs_int("-3") == -3
    with pytest.raises(ValueError):
        parse_sysfs_int("12.5")


def test_parse_kv_lines():
    assert parse_kv_lines("a=1\n\nb = two \n") == {"a": "1", "b": "two"}
    with pytest.raises(ValueError):
        parse_kv_lines("no-separator")

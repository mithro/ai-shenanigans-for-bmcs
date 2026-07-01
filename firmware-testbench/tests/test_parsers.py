"""Unit tests for the on-target output parsers."""

import pytest

from firmware_testbench.parsers import (
    parse_i2cdetect,
    parse_kv_lines,
    parse_sysfs_int,
)

I2CDETECT_F0 = """\
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: 40 41 42 43 44 45 46 47 48 49 4a 4b 4c 4d 4e 4f
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
"""


def test_parse_i2cdetect_full_row():
    got = parse_i2cdetect(I2CDETECT_F0)
    assert got == set(range(0x40, 0x50))


def test_parse_i2cdetect_uu_counts_as_present():
    text = (
        "     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f\n"
        "70: 70 -- UU -- -- -- -- --\n"
    )
    assert parse_i2cdetect(text) == {0x70, 0x72}


def test_parse_i2cdetect_rejects_inconsistent_cell():
    # Address printed in the wrong column must fail loud.
    text = "40: 41 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --\n"
    with pytest.raises(ValueError):
        parse_i2cdetect(text)


def test_parse_sysfs_int():
    assert parse_sysfs_int(" 12500\n") == 12500
    assert parse_sysfs_int("-3") == -3
    with pytest.raises(ValueError):
        parse_sysfs_int("12.5")


def test_parse_kv_lines():
    assert parse_kv_lines("a=1\n\nb = two \n") == {"a": "1", "b": "two"}
    with pytest.raises(ValueError):
        parse_kv_lines("no-separator")

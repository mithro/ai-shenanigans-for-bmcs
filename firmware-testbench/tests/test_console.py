"""Unit tests for the console expect engine (fake streams, fake clock)."""

import re

import pytest

from firmware_testbench.console import Console, ExpectTimeout


def make_console(chunks, *, tick=0.02):
    """Console fed from a list of byte chunks with a deterministic clock."""
    incoming = list(chunks)
    written = bytearray()
    t = {"now": 0.0}

    def read():
        return incoming.pop(0) if incoming else b""

    def write(data):
        written.extend(data)

    def clock():
        return t["now"]

    def sleep(dt):
        t["now"] += dt

    c = Console(read, write, clock=clock, sleep=sleep, poll_interval=tick)
    return c, written, t


def test_expect_simple_match():
    c, _, _ = make_console([b"boot\n", b"kgpe-d16 login: "])
    m = c.expect(r"login: ")
    assert m.after == "login: "
    assert "kgpe-d16 " in m.before


def test_expect_consumes_buffer_up_to_match():
    c, _, _ = make_console([b"aaLOGINbbLOGINcc"])
    first = c.expect("LOGIN")
    assert first.before == "aa"
    second = c.expect("LOGIN")
    assert second.before == "bb"
    assert c.buffer == "cc"


def test_expect_first_pattern_by_position_then_order():
    c, _, _ = make_console([b"...PASS...FAIL..."])
    m = c.expect([r"FAIL", r"PASS"])   # PASS occurs earlier in the stream
    assert m.index == 1
    assert m.after == "PASS"


def test_expect_precompiled_pattern():
    c, _, _ = make_console([b"x=42\n"])
    m = c.expect([re.compile(r"x=(\d+)")])
    assert m.match.group(1) == "42"


def test_expect_timeout_raises_with_buffer():
    c, _, t = make_console([b"partial output "])
    with pytest.raises(ExpectTimeout) as ei:
        c.expect("never", timeout=1.0)
    assert "partial output" in ei.value.buffer
    assert t["now"] >= 1.0     # the fake clock advanced to the deadline


def test_send_line_writes_bytes():
    c, written, _ = make_console([])
    c.send_line("root")
    assert bytes(written) == b"root\n"


def test_expect_handles_multibyte_char_split_across_reads():
    # 'é' is 0xC3 0xA9 in UTF-8; split it across two reads. A per-chunk decode
    # would corrupt it into replacement chars; the incremental decoder must not.
    c, _, _ = make_console([b"caf\xc3", b"\xa9 login: "])
    m = c.expect("café")
    assert m.after == "café"
    assert "�" not in m.after

"""Integration test: SCU faithfulness on the QEMU model vs AST2050 golden values.

Boots `peripherals/scu/fwtest.c` under `-M kgpe-d16-bmc` and asserts each SCU
reset value matches real AST2050 silicon (A3 datasheet V1.05 §18, corroborated by
Raptor platform.S + the culvert HW capture; see peripherals/scu/DOC.md).

Rows the current AST2400-based model still gets wrong are marked xfail with the
datasheet cite; the `aspeed.scu-ast2050` model change flips them to xpass, at
which point the xfail marker is removed. Nothing here touches hardware.

Run:  uv run --with pytest python -m pytest integration/test_scu.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

# Datasheet §18 golden reset values (label -> (expected, xfail_reason_or_None)).
# label is the fwtest `reg` label. xfail reason set for gaps the ast2050-scu
# model does not yet close.
WIP = "ast2050-scu G3 reset table/post-divider WIP (datasheet §18)"
GOLDEN = {
    "revid":     (0x00000202, None),          # §18.2 p220 — FIXED
    "resetflag": (0x00000001, None),          # SCU3C §11 p215
    "sysreset":  (0x000FFE5C, WIP),           # SCU04 §2 p205
    "clksel":    (0xE3F00070, WIP),           # SCU08 §3 p207
    "clkstop":   (0x000C3E8B, WIP),           # SCU0C §4 p209
    "mpll":      (0x00004291, WIP),           # SCU20 §7 p212
    "hpll":      (0x00004291, WIP),           # SCU24 §8 p212
    "pinmux1":   (0x40048000, WIP),           # SCU74 §15 p219
    "protect":   (0x00000000, WIP),           # SCU00 §1 p205 (locked read-back)
}


@pytest.fixture(scope="module")
def scu():
    return runner.run_fwtest("scu")


def test_reaches_halt(scu):
    assert scu.halted, f"scu fwtest did not reach the halt sentinel:\n{scu.raw}"


@pytest.mark.parametrize(
    "label",
    [
        pytest.param(
            k,
            marks=(pytest.mark.xfail(reason=v[1], strict=False) if v[1] else ()),
        )
        for k, v in GOLDEN.items()
    ],
)
def test_reset_value_faithful(scu, label):
    want = GOLDEN[label][0]
    got = scu.regs.get(label)
    assert got is not None, f"SCU reg '{label}' missing from transcript:\n{scu.raw}"
    assert got == want, f"SCU {label}: got {got:#010x}, want {want:#010x}"

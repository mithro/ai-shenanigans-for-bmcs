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
# The rev-id is faithful (set from silicon_rev). The full G3 reset TABLE is not
# applied by default: CI showed it breaks the legacy boots tuned for the AST2400
# machine (the OpenBMC AST2400 U-Boot + the RE-patched Dell vendor firmware read
# AST2400 SCU values the G3 map zeroes). It is the opt-in `ast2050_a3_resets` table
# pending a G3-aware U-Boot/firmware -- see peripherals/scu/DOC.md §4 + the
# co-evolution task. (SCU00 lock-state is not asserted: QEMU pre-unlocks on a
# `-kernel` boot.)
CO_EVO = ("G3 reset table breaks the AST2400-U-Boot + vendor-firmware boots; "
          "applied opt-in pending G3-aware firmware (DOC.md §4)")
GOLDEN = {
    "revid":     (0x00000202, None),          # SCU7C §18.2 p220 — faithful
    "resetflag": (0x00000001, None),          # SCU3C §11 p215 (matches AST2400 too)
    "sysreset":  (0x000FFE5C, CO_EVO),        # SCU04 §2 p205
    "clksel":    (0xE3F00070, CO_EVO),        # SCU08 §3 p207
    "clkstop":   (0x000C3E8B, CO_EVO),        # SCU0C §4 p209
    "mpll":      (0x00004291, None),          # SCU20 §7 p212 — G3 reset (HW-JTAG)
    "hpll":      (0x00004291, None),          # SCU24 §8 p212 — G3 reset (HW-JTAG)
    "pinmux1":   (0x40048000, CO_EVO),        # SCU74 §15 p219
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

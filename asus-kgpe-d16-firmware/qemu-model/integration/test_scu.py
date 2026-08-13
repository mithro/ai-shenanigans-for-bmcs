"""Integration test: SCU faithfulness on the QEMU model vs AST2050 golden values.

Boots `peripherals/scu/fwtest.c` under `-M kgpe-d16-bmc` and asserts each SCU
reset value matches real AST2050 silicon (A3 datasheet V1.05 §18, corroborated by
Raptor platform.S + the culvert HW capture; see peripherals/scu/DOC.md).

The SCU reset-table faithfulness is proven in the *faithful G3 mode*: the model
carries the datasheet-faithful G3 reset table (aspeed_scu.c ast2050_a3_resets),
opt-in via `-global driver=aspeed.scu-ast2050,property=g3-resets,value=on`. The
default `kgpe-d16-bmc` machine keeps the AST2400-compat table so the AST2400-tuned
legacy oracles (C2/C3/C4) are byte-for-byte unaffected; a genuinely G3-aware
firmware (Raptor's AST2050 U-Boot, which runs the real DDR2 init) boots with the
same flag ON. This test asserts the faithful G3 reset state, so it boots with
g3-resets=on and all eight golden values match (the four that used to xfail against
the AST2400 table -- sysreset/clksel/clkstop/pinmux1 -- now pass). Nothing here
touches hardware. See peripherals/scu/DOC.md §4 (co-evolution, now resolved).

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
# Booted in the faithful G3 mode (G3_RESETS below), so the full ast2050_a3_resets
# table is applied and every golden value matches -- including the four
# (sysreset/clksel/clkstop/pinmux1) that used to xfail against the AST2400-compat
# default table. The co-evolution blocker is resolved: the default machine keeps
# the AST2400 table for the legacy oracles (C2/C3/C4), while this test and the
# G3-aware Raptor U-Boot opt into the faithful G3 reset state. See DOC.md §4.
# (SCU00 lock-state is not asserted: QEMU pre-unlocks on a `-kernel` boot.)
GOLDEN = {
    "revid":     (0x00000202, None),          # SCU7C §18.2 p220 — faithful
    "resetflag": (0x00000001, None),          # SCU3C §11 p215 (matches AST2400 too)
    "sysreset":  (0x000FFE5C, None),          # SCU04 §2 p205 — G3 reset table
    "clksel":    (0xE3F00070, None),          # SCU08 §3 p207 — G3 reset table
    "clkstop":   (0x000C3E8B, None),          # SCU0C §4 p209 — G3 reset table
    "mpll":      (0x00004291, None),          # SCU20 §7 p212 — G3 reset (HW-JTAG)
    "hpll":      (0x00004291, None),          # SCU24 §8 p212 — G3 reset (HW-JTAG)
    "pinmux1":   (0x40048000, None),          # SCU74 §15 p219 — G3 reset table
}

# Faithful G3 reset state (see module docstring). The dotted `-global TYPE.PROP=`
# shorthand mis-splits because the type name itself contains a dot, so use the
# explicit driver=/property=/value= form.
G3_RESETS = ["-global", "driver=aspeed.scu-ast2050,property=g3-resets,value=on"]


@pytest.fixture(scope="module")
def scu():
    return runner.run_fwtest("scu", qemu_args=G3_RESETS)


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

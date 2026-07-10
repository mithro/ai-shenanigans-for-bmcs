"""Integration test: LPC host-interface faithfulness on the QEMU model.

The G3 KCS/BT/iLPC2AHB register block lives at 0x24-0x8C — NOT the AST2400 0x140
that mainline aspeed_lpc uses. Fixed 2026-07-10 by aspeed.lpc-ast2050 (a G3-only
register-accurate model that replaces aspeed_lpc for the AST2050): config
registers (HICR) are RW at the G3 offsets and KCS status (STR) is read-only,
reset 0. See peripherals/lpc/DOC.md. No hardware here.
"""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402
skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def lpc():
    return runner.run_fwtest("lpc")


def test_reaches_halt(lpc):
    assert lpc.halted, f"lpc fwtest did not reach the halt sentinel:\n{lpc.raw}"


@pytest.mark.parametrize("label", ["str1.reset", "hicr0.rw", "hicr5.rw"])
def test_g3_lpc_layout(lpc, label):
    """The G3 LPC registers are addressable at the G3 offsets: HICR0 (0x00) and
    the iLPC2AHB HICR5 (0x80) are RW config registers, and KCS STR1 (0x3C) is a
    read-only status register that resets to 0 — proving the model uses the G3
    layout, not the AST2400 0x140."""
    c = next((c for c in lpc.checks if c[0] == label), None)
    assert c is not None and c[1], f"LPC G3-layout check {label} failed"

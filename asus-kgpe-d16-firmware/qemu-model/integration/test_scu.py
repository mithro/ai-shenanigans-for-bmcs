"""Integration test: SCU faithfulness on the QEMU model vs AST2050 golden values.

Boots `peripherals/scu/fwtest.c` under `-M kgpe-d16-bmc` and asserts the register
transcript matches real AST2050 hardware. Golden values are from the A3 datasheet
V1.05 and the culvert real-silicon capture (see peripherals/scu/DOC.md). Nothing
here touches hardware; the HIL half (same test on silicon) is added at the gated
HW-validation step.

Run:  uv run --with pytest python -m pytest integration/test_scu.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

# Real AST2050-A3 SCU7C silicon revision id (datasheet §18.2 p220 + HW capture).
AST2050_A3_REVID = 0x00000202


@pytest.fixture(scope="module")
def scu():
    return runner.run_fwtest("scu")


def test_reaches_halt(scu):
    assert scu.halted, f"scu fwtest did not reach the halt sentinel:\n{scu.raw}"


def test_revid_faithful(scu):
    got = scu.regs.get("revid")
    assert got == AST2050_A3_REVID, (
        f"SCU7C rev-id not faithful to AST2050-A3: got {got:#010x}, "
        f"want {AST2050_A3_REVID:#010x}"
    )


def test_no_failed_checks(scu):
    failed = [c for c in scu.checks if not c[1]]
    assert scu.fails == 0, f"SCU faithfulness checks failed: {failed}\n{scu.raw}"


def test_clkin_reference_is_24mhz(scu):
    # The KGPE-D16 straps a 24 MHz reference clock; the SCU strap register must be
    # present. (Exact clock-select bit assertion lands once DATASHEET-SCU.md pins
    # the AST2050 strap bit positions.)
    assert "strap" in scu.regs, f"no SCU strap register in transcript:\n{scu.raw}"

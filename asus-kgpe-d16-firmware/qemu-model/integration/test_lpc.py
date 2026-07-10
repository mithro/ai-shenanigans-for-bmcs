"""Integration test: LPC host-interface faithfulness on the QEMU model.

The G3 KCS/BT/iLPC2AHB layout (0x24-0x8C) is not modelled — QEMU's aspeed_lpc puts
KCS/iBT at the AST2400 0x140 offsets. So the G3 offsets read 0 (observed); a faithful
G3 aspeed.lpc-ast2050 is oracle-gated (see peripherals/lpc/DOC.md). No hardware here.
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


@pytest.mark.xfail(reason="G3 KCS/BT/iLPC2AHB at 0x24-0x8C not modelled; aspeed_lpc uses "
                          "the AST2400 0x140 layout (DOC.md §2)", strict=False)
def test_g3_kcs_present(lpc):
    # A G3 KCS status register at 0x3C would not read 0 once modelled.
    assert lpc.regs.get("kcs.str1", 0) != 0

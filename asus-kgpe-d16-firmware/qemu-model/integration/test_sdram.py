"""Integration test: SDRAM controller (DDR2) faithfulness on the QEMU model.

Boots `peripherals/sdram/fwtest.c` under `-M kgpe-d16-bmc`. The faithful
`aspeed.sdmc-ast2050` DDR2 model is now wired into the G3 SoC (gated on the
AST2050 silicon rev), so all checks PASS: MCR04 resets to 0 and stores writes
verbatim, MCR100 reads 0xA8, and reading MCR04 back after firmware programs the
real KGPE-D16 value (0x585) reports 4-bank / 64 MB / 16-bit. The three checks
that were xfail against the old DDR3 model (config.reset, config.rw, compat100)
now pass. No hardware here (see peripherals/sdram/DOC.md).

Run:  uv run --with pytest python -m pytest integration/test_sdram.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

# fwtest check label -> xfail reason (None = must pass). The faithful DDR2 model
# closes the three DDR2-vs-DDR3 gaps that were previously xfail.
CHECKS = {
    "protect.reset": None,   # MCR00 locked at reset -> reads 0
    "refresh.reset": None,   # MCR0C Init=0
    "unlock":        None,   # 0xFC600309 -> reads 1
    "config.reset":  None,   # MCR04 Init=0 (DDR2 model no longer synthesises it)
    "config.rw":     None,   # MCR04 stores verbatim (no DDR3 recompute)
    "compat100":     None,   # MCR100 = 0xA8 (AST2000-compat shadow modelled)
    "geom.cap64":    None,   # MCR04[3:2]=01 -> reports 64 MB total
    "geom.w16":      None,   # MCR04[9:8]=01 -> reports 16-bit bus
    "geom.bank4":    None,   # MCR04[11]=0  -> reports 4-bank
}


@pytest.fixture(scope="module")
def sdram():
    return runner.run_fwtest("sdram")


def test_reaches_halt(sdram):
    assert sdram.halted, f"sdram fwtest did not reach the halt sentinel:\n{sdram.raw}"


@pytest.mark.parametrize(
    "label",
    [
        pytest.param(k, marks=(pytest.mark.xfail(reason=v, strict=False) if v else ()))
        for k, v in CHECKS.items()
    ],
)
def test_check(sdram, label):
    c = next((c for c in sdram.checks if c[0] == label), None)
    assert c is not None, f"no '{label}' check in transcript:\n{sdram.raw}"
    assert c[1], f"SDRAM {label}: got {c[2]:#010x}, want {c[3]:#010x}"

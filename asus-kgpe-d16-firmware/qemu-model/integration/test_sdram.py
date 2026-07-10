"""Integration test: SDRAM controller (DDR2) faithfulness on the QEMU model.

Boots `peripherals/sdram/fwtest.c` under `-M kgpe-d16-bmc`. The protection
lock-latch (unlock 0xFC600309) and refresh reset are already faithful; three
DDR2-vs-DDR3 gaps remain and are xfail until the boot-gated `aspeed.sdmc-ast2050`
model lands (see peripherals/sdram/DOC.md §4). No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_sdram.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

# DDR2 model change is gated on the C1-C4 boot check (MCR04 drives DRAM sizing).
GATED = "aspeed.sdmc-ast2050 DDR2 model gated on the C1-C4 boot check (DOC.md §4)"

# fwtest check label -> xfail reason (None = must pass now).
CHECKS = {
    "protect.reset": None,   # MCR00 locked at reset -> reads 0
    "refresh.reset": None,   # MCR0C Init=0
    "unlock":        None,   # 0xFC600309 -> reads 1
    "config.reset":  GATED,  # MCR04 Init=0 (QEMU synthesises DDR3 0x41)
    "config.rw":     GATED,  # MCR04 stores verbatim (QEMU recomputes)
    "compat100":     GATED,  # MCR100 = 0xA8 (unmodelled)
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

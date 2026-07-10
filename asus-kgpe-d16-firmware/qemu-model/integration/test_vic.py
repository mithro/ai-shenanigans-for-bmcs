"""Integration test: VIC (interrupt controller) faithfulness on the QEMU model.

Boots `peripherals/vic/fwtest.c` under `-M kgpe-d16-bmc`. The faithful compact G3
VIC (`aspeed.vic-ast2050`: status/enable/select reset 0 + the G3 trigger-config
sensitivity/both-edge/event reset 0 and fully writable) is now **wired to the
machine end-to-end** (2026-07-10): the AST2050 SoC uses TYPE_ASPEED_2050_VIC, our
kernel binds it via the `irq-aspeed-g3-vic` driver (which programs SENSE/DUAL/
EVENT) with the `aspeed,ast2050-vic` DTS node. All C2/C2-full/C5 boots verified —
the timer IRQ works. All 13 checks now PASS. See peripherals/vic/DOC.md §5.
No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_vic.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

# fwtest check label -> xfail reason (None = must pass). All pass now that the G3
# VIC is wired with its matching kernel driver.
CHECKS = {
    "irqstat.reset": None, "fiqstat.reset": None, "rawstat.reset": None,
    "select.reset": None, "enable.reset": None, "softint.reset": None,
    "protect.reset": None,
    "sense.reset": None, "dual.reset": None, "event.reset": None,
    "sense.rw": None, "dual.rw": None, "event.rw": None,
}


@pytest.fixture(scope="module")
def vic():
    return runner.run_fwtest("vic")


def test_reaches_halt(vic):
    assert vic.halted, f"vic fwtest did not reach the halt sentinel:\n{vic.raw}"


@pytest.mark.parametrize(
    "label",
    [
        pytest.param(k, marks=(pytest.mark.xfail(reason=v, strict=False) if v else ()))
        for k, v in CHECKS.items()
    ],
)
def test_check(vic, label):
    c = next((c for c in vic.checks if c[0] == label), None)
    assert c is not None, f"no '{label}' check in transcript:\n{vic.raw}"
    assert c[1], f"VIC {label}: got {c[2]:#010x}, want {c[3]:#010x}"

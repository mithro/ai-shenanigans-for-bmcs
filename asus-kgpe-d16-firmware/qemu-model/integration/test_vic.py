"""Integration test: VIC (interrupt controller) faithfulness on the QEMU model.

Boots `peripherals/vic/fwtest.c` under `-M kgpe-d16-bmc`. The faithful compact G3
VIC (`aspeed.vic-ast2050`, TYPE_ASPEED_2050_VIC — trigger config sensitivity/
both-edge/event reset 0 + fully writable, JTAG-confirmed) is **wired to the machine
end-to-end**: the AST2050 SoC uses TYPE_ASPEED_2050_VIC and our modern kernel binds
it via the `irq-aspeed-g3-vic` driver (which programs SENSE/DUAL/EVENT) with the
`aspeed,ast2050-vic` DTS node. Both our kernel (C2/C2-full/C5) AND the proprietary
C410X vendor firmware (C4 oracle) boot on it — the latter once the faithful timer
emits one rising-edge PULSE per expiry instead of toggling (the toggle only
delivered on every other expiry under the G3's single rising-edge timer config,
halving the guest clock and tripping the vendor watchdog at ~17s). All 13 checks
now PASS. See peripherals/vic/DOC.md and results/vic-hardware-crosscheck.md §5-6.
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
# VIC (TYPE_ASPEED_2050_VIC) is wired with its matching kernel driver and the
# faithful one-pulse-per-expiry timer unblocks the C4 vendor oracle.
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

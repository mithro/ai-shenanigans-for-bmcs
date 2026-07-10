"""Integration test: VIC (interrupt controller) faithfulness on the QEMU model.

Boots `peripherals/vic/fwtest.c` under `-M kgpe-d16-bmc`. The status/enable/select
registers already reset to 0 on the current machine. The G3-specific trigger-config
behaviour (sensitivity/both-edge/event reset 0 + fully writable) is implemented in
the `aspeed.vic-ast2050` model but that VIC is **not yet wired to the machine**:
wiring it needs a matching G3 kernel driver (`irq-aspeed-g3-vic` + `aspeed,ast2050-vic`
DTS), else the mainline `aspeed,ast2400-vic` driver can't program the trigger config
and the timer IRQ dies (Linux hangs). Until that end-to-end bring-up lands, the six
G3 checks are xfail. See peripherals/vic/DOC.md §5. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_vic.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

# fwtest check label -> xfail reason (None = must pass now).
E2E = ("G3 VIC not wired to the machine yet — needs the irq-aspeed-g3-vic kernel "
       "driver + aspeed,ast2050-vic DTS (else the mainline ast2400 VIC driver hangs "
       "the timer). See DOC.md §5 / the G3-VIC-end-to-end task.")
CHECKS = {
    "irqstat.reset": None, "fiqstat.reset": None, "rawstat.reset": None,
    "select.reset": None, "enable.reset": None, "softint.reset": None,
    "protect.reset": None,
    "sense.reset": E2E, "dual.reset": E2E, "event.reset": E2E,
    "sense.rw": E2E, "dual.rw": E2E, "event.rw": E2E,
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

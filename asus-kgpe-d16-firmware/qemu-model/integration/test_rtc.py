"""Integration test: RTC faithfulness on the QEMU model.

Boots `peripherals/rtc/fwtest.c` under `-M kgpe-d16-bmc`. The G3 RTC is counter-style
(reload + restart-magic), but the machine instantiates the AST2400 aspeed_rtc (a
different layout), so the G3-layout checks xfail — a faithful counter-style RTC + a
matching G3 kernel driver is oracle-gated (see peripherals/rtc/DOC.md §2). No hardware.

Run:  uv run --with pytest python -m pytest integration/test_rtc.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

GATE = ("G3 counter-style RTC layout differs from the AST2400 aspeed_rtc the machine "
        "uses; faithful model + G3 kernel RTC driver is oracle-gated (DOC.md §2)")


@pytest.fixture(scope="module")
def rtc():
    return runner.run_fwtest("rtc")


def test_reaches_halt(rtc):
    assert rtc.halted, f"rtc fwtest did not reach the halt sentinel:\n{rtc.raw}"


@pytest.mark.parametrize("label", ["control.rw", "counter.loaded_sec"])
@pytest.mark.xfail(reason=GATE, strict=False)
def test_g3_layout(rtc, label):
    c = next((c for c in rtc.checks if c[0] == label), None)
    assert c is not None and c[1], f"RTC {label}: got {c[2] if c else '?'}"

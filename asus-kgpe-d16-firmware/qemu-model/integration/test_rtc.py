"""Integration test: RTC faithfulness on the QEMU model.

Boots `peripherals/rtc/fwtest.c` under `-M kgpe-d16-bmc`. The G3 counter-style RTC is
now modelled by `aspeed.rtc-ast2050` (counter at 0x00, reload 0x08, control 0x0C,
restart-magic 0x5A at 0x10), replacing the AST2400 aspeed_rtc for the G3. See
peripherals/rtc/DOC.md. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_rtc.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def rtc():
    return runner.run_fwtest("rtc")


def test_reaches_halt(rtc):
    assert rtc.halted, f"rtc fwtest did not reach the halt sentinel:\n{rtc.raw}"


@pytest.mark.parametrize("label", ["control.rw", "counter.loaded_sec"])
def test_g3_layout(rtc, label):
    c = next((c for c in rtc.checks if c[0] == label), None)
    assert c is not None and c[1], f"RTC {label}: got {c[2] if c else '?'}"

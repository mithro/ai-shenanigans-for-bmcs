"""Integration test: Watchdog Timer (WDT) faithfulness on the QEMU model.

Boots `peripherals/wdt/fwtest.c` under `-M kgpe-d16-bmc`: reload + control reset
values match the datasheet, and the 0x4755 restart magic reloads the counter. The
model is register-faithful for the G3 (no change needed); the absolute PCLK timeout
rate is deferred to the SCU post-divider work (task #55). See peripherals/wdt/DOC.md.
No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_wdt.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def wdt():
    return runner.run_fwtest("wdt")


def test_reaches_halt(wdt):
    assert wdt.halted, f"wdt fwtest did not reach the halt sentinel:\n{wdt.raw}"


def test_all_checks_pass(wdt):
    failed = [c for c in wdt.checks if not c[1]]
    assert wdt.fails == 0, f"WDT checks failed: {failed}\n{wdt.raw}"


def test_reload_reset_value(wdt):
    # Datasheet reload reset = 0x03EF1480 (1s @66MHz).
    assert wdt.regs.get("reload") == 0x03EF1480

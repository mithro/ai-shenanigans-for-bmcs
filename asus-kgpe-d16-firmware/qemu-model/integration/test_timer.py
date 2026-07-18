"""Integration test: Timer (FTTMR010) faithfulness on the QEMU model.

Boots `peripherals/timer/fwtest.c` under `-M kgpe-d16-bmc`: control + count reset
to 0, and enabling timer1 from PCLK loads from reload and counts down. The absolute
PCLK rate is deferred to the SCU post-divider work (task #55); here we assert
correct reset + functional counting. See peripherals/timer/DOC.md. No hardware here.

Task #55 scope note (gate-b review 2026-07-18): the G3 SCU currently reuses the
AST2400 clkin/calc_hpll, which mis-decode the G3 strap -- get_clkin returns 25 MHz
because the G3 strap's bit23 (LPC-reset-pin) collides with SCU_HW_STRAP_CLK_25M_IN,
and calc_hpll reads H-PLL from bits[9:8] not the G3's [11:9]. So the rate this test
defers is not merely un-asserted, it is currently wrong; #55 must add a G3-specific
calc_hpll/clkin (bit23=LPC-reset, CLKIN fixed 24 MHz, H-PLL bits[11:9] + G3 freq
table) AND a rate-validation assertion. See device-driver-program/LOG.md 2026-07-18.

Run:  uv run --with pytest python -m pytest integration/test_timer.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def timer():
    return runner.run_fwtest("timer")


def test_reaches_halt(timer):
    assert timer.halted, f"timer fwtest did not reach the halt sentinel:\n{timer.raw}"


def test_all_checks_pass(timer):
    failed = [c for c in timer.checks if not c[1]]
    assert timer.fails == 0, f"timer checks failed: {failed}\n{timer.raw}"


def test_counts_down(timer):
    # The functional check must have passed (timer decrements when enabled).
    c = next((c for c in timer.checks if c[0] == "counts_down"), None)
    assert c is not None and c[1], f"timer did not count down:\n{timer.raw}"

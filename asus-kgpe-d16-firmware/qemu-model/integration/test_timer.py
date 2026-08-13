"""Integration test: Timer (FTTMR010) faithfulness on the QEMU model.

Boots `peripherals/timer/fwtest.c` under `-M kgpe-d16-bmc`: control + count reset
to 0, and enabling timer1 from PCLK loads from reload and counts down. The absolute
PCLK rate is deferred to the SCU post-divider work (task #55); here we assert
correct reset + functional counting. See peripherals/timer/DOC.md. No hardware here.

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

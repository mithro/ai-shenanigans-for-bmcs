"""Integration test: GPIO faithfulness on the QEMU model.

Boots `peripherals/gpio/fwtest.c` under `-M kgpe-d16-bmc`: direction/data/int-enable
reset to 0, the direction register is RW, and an output pin latches the written value
(banks A-D and E-H). Datapath faithful; the model exposing more banks than the G3's
A-H is a documented cosmetic gap. See peripherals/gpio/DOC.md. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_gpio.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def gpio():
    return runner.run_fwtest("gpio")


def test_reaches_halt(gpio):
    assert gpio.halted, f"gpio fwtest did not reach the halt sentinel:\n{gpio.raw}"


def test_all_checks_pass(gpio):
    failed = [c for c in gpio.checks if not c[1]]
    assert gpio.fails == 0, f"GPIO checks failed: {failed}\n{gpio.raw}"


def test_output_latch(gpio):
    c = next((c for c in gpio.checks if c[0] == "data_ad.output_latch"), None)
    assert c is not None and c[1], f"GPIO output latch failed:\n{gpio.raw}"

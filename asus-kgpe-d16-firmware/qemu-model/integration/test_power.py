"""Integration test: KGPE-D16 (AST2050) host power-sequencer on the QEMU model.

Boots `peripherals/power/fwtest.c` under `-M kgpe-d16-bmc` and asserts the
board power glue modeled in the Aspeed GPIO device (aspeed_gpio_kgpe_d16_pwrseq):
driving the active-low request lines per Raptor's asus_power.sh sequences moves
a host-power latch that is reflected on the GPIOH2 power-state input —

  * off out of reset,
  * a GPIOB1 POWERUP_N pulse is IGNORED while GPIOA4 (ASUS_BMC_CTL_LOCKOUT_N)
    is not driven high (stock image can't power on — HW-verified 2026-07-13),
  * on after the SAME POWERUP_N pulse once GPIOA4 is reclaimed high,
  * still on across a GPIOB6 RESET_N pulse (warm reset keeps power),
  * off after the GPIOF0 POWERDOWN_N pulse,
  * on again after a fresh POWERUP_N pulse (A4 still held high).

This is the QEMU half of the OpenBMC "Redfish -> state-manager -> GPIO ->
power-state" loop (feature F2). See peripherals/power/DOC.md. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_power.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def power():
    return runner.run_fwtest("power")


def test_reaches_halt(power):
    assert power.halted, f"power fwtest did not reach the halt sentinel:\n{power.raw}"


def test_all_checks_pass(power):
    failed = [c for c in power.checks if not c[1]]
    assert power.fails == 0, f"power checks failed: {failed}\n{power.raw}"


@pytest.mark.parametrize(
    "label",
    [
        "power.off_at_reset",
        "power.on_blocked_without_a4",
        "power.on_after_a4_reclaim",
        "power.on_after_powerup",
        "power.on_after_reset",
        "power.off_after_powerdown",
    ],
)
def test_power_loop_step(power, label):
    c = next((c for c in power.checks if c[0] == label), None)
    assert c is not None, f"missing check {label!r}:\n{power.raw}"
    assert c[1], f"power check {label!r} failed (got={c[2]:#x} want={c[3]:#x}):\n{power.raw}"

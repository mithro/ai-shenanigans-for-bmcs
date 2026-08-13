"""Integration test: PWM/tach faithfulness on the QEMU model.

Boots `peripherals/pwm/fwtest.c` under `-M kgpe-d16-bmc`. The AST2050 PWM/tach block
(fan control/monitor) is now modelled by the `aspeed.pwm-ast2050` device (4 PWM + 16
tach, register window 0x00-0x3C), so PTCR00 enables + duty are RW. See
peripherals/pwm/DOC.md. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_pwm.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def pwm():
    return runner.run_fwtest("pwm")


def test_reaches_halt(pwm):
    assert pwm.halted, f"pwm fwtest did not reach the halt sentinel:\n{pwm.raw}"


def test_all_checks_pass(pwm):
    failed = [c for c in pwm.checks if not c[1]]
    assert pwm.fails == 0, f"PWM checks failed: {failed}\n{pwm.raw}"


@pytest.mark.parametrize("label", ["ptcr00.master_en", "ptcr00.pwmA_en", "duty.rw"])
def test_pwm_modelled(pwm, label):
    c = next((c for c in pwm.checks if c[0] == label), None)
    assert c is not None and c[1], f"PWM {label} not modelled:\n{pwm.raw}"

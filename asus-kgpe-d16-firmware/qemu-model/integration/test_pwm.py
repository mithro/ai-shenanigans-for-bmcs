"""Integration test: PWM/tach faithfulness on the QEMU model.

Boots `peripherals/pwm/fwtest.c` under `-M kgpe-d16-bmc`. The AST2050 PWM/tach block
(fan control/monitor) is NOT modelled on this machine — all checks xfail until a
faithful `aspeed.pwm-ast2050` device is added (see peripherals/pwm/DOC.md §3). This
blocks OpenBMC hwmon fan verification. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_pwm.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

UNMODELLED = "PWM/tach block unmodelled; needs aspeed.pwm-ast2050 (DOC.md §3)"


@pytest.fixture(scope="module")
def pwm():
    return runner.run_fwtest("pwm")


def test_reaches_halt(pwm):
    assert pwm.halted, f"pwm fwtest did not reach the halt sentinel:\n{pwm.raw}"


@pytest.mark.parametrize("label", ["ptcr00.master_en", "ptcr00.pwmA_en", "duty.rw"])
@pytest.mark.xfail(reason=UNMODELLED, strict=False)
def test_pwm_modelled(pwm, label):
    c = next((c for c in pwm.checks if c[0] == label), None)
    assert c is not None and c[1]

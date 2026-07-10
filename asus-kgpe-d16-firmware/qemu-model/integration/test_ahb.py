"""Integration test: AHB controller probe on the QEMU model.

Boots `peripherals/ahb/fwtest.c` under `-M kgpe-d16-bmc`. The AHB controller
(0x1E600000) is not modelled (reads 0), but QEMU maps DRAM at 0x0 directly so the boot
address space is correct without the AHBC remap — the legacy boots are unaffected. This
test just confirms the probe runs; behaviour is recorded as observations. See
peripherals/ahb/DOC.md. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_ahb.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def ahb():
    return runner.run_fwtest("ahb")


def test_reaches_halt(ahb):
    assert ahb.halted, f"ahb fwtest did not reach the halt sentinel:\n{ahb.raw}"


def test_probe_recorded(ahb):
    # The remap register observation is present (0 = unmodelled, recorded for the diff).
    assert "remap" in ahb.regs, f"no AHBC remap observation:\n{ahb.raw}"

"""Integration test: SMC (legacy SPI flash controller) faithfulness on the model.

Boots `peripherals/smc/fwtest.c` under `-M kgpe-d16-bmc`. The AST2050 legacy SMC
(0x16000000, flash data 0x10000000) is NOT modelled — mainline QEMU models only the
FMC (0x1E620000). All checks xfail until a faithful `aspeed.smc-ast2050` device + flash
mapping is added (see peripherals/smc/DOC.md §3). The current boots use the FMC path, so
this gap doesn't affect them. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_smc.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

UNMODELLED = "legacy SMC unmodelled (mainline models the FMC); needs aspeed.smc-ast2050 (DOC.md §3)"


@pytest.fixture(scope="module")
def smc():
    return runner.run_fwtest("smc")


def test_reaches_halt(smc):
    assert smc.halted, f"smc fwtest did not reach the halt sentinel:\n{smc.raw}"


@pytest.mark.parametrize("label", ["smc00.reset", "smc04.rw"])
@pytest.mark.xfail(reason=UNMODELLED, strict=False)
def test_smc_modelled(smc, label):
    c = next((c for c in smc.checks if c[0] == label), None)
    assert c is not None and c[1]

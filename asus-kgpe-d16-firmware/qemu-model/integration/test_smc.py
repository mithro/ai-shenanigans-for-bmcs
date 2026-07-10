"""Integration test: SMC (legacy SPI flash controller) faithfulness on the model.

Boots `peripherals/smc/fwtest.c` under `-M kgpe-d16-bmc`. The AST2050 legacy SMC
(control @ 0x16000000, flash data @ 0x10000000) is modelled by the G3-only
`aspeed.smc-ast2050` device: the SMC00 config reset, writable CE control regs, AND
the UMA (user-mode) SPI path — byte-banging the flash window drives an m25p80
(mx25l12805d) so the vendor's JEDEC-ID read returns 0xC22018. This is the exact
path the C410X firmware (C4) uses; modelling it removed the non-fatal div0 in
aess_write_spi_nor_flash. Our modern kernel uses the FMC (0x1E620000), unaffected.
No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_smc.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

@pytest.fixture(scope="module")
def smc():
    return runner.run_fwtest("smc")


def test_reaches_halt(smc):
    assert smc.halted, f"smc fwtest did not reach the halt sentinel:\n{smc.raw}"


@pytest.mark.parametrize("label",
                         ["smc00.reset", "smc04.rw", "smc.jedec.mx25l128"])
def test_smc_modelled(smc, label):
    """The legacy SMC (0x16000000) is modelled by the G3-only aspeed.smc-ast2050
    device: SMC00 config reads its 0x240 reset value, SMC04 CE0-control is writable,
    and the UMA JEDEC-ID read (cs_low -> 0x9F -> 3 reads -> cs_high) returns
    0xC22018 from the modelled mx25l12805d. Fixed 2026-07-11 (DOC.md §3)."""
    c = next((c for c in smc.checks if c[0] == label), None)
    assert c is not None and c[1]

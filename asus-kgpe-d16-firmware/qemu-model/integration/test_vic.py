"""Integration test: VIC (interrupt controller) faithfulness on the QEMU model.

Boots `peripherals/vic/fwtest.c` under `-M kgpe-d16-bmc` and asserts the AST2050
single-bank VIC behaviour: every register resets to 0, and the trigger-config
registers (sensitivity/both-edge/event, 0x24/0x28/0x2C) are fully writable and
read back the firmware-programmed words that match real silicon (culvert capture
== datasheet §10 Table 36). See peripherals/vic/DOC.md. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_vic.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

# Firmware-programmed trigger words (real silicon == datasheet Table 36).
FW = {"sense": 0x903897FE, "dual": 0x07C00000, "event": 0x983F97FE}


@pytest.fixture(scope="module")
def vic():
    return runner.run_fwtest("vic")


def test_reaches_halt(vic):
    assert vic.halted, f"vic fwtest did not reach the halt sentinel:\n{vic.raw}"


def test_all_checks_pass(vic):
    failed = [c for c in vic.checks if not c[1]]
    assert vic.fails == 0, f"VIC faithfulness checks failed: {failed}\n{vic.raw}"


@pytest.mark.parametrize("reg", ["sense", "dual", "event"])
def test_trigger_config_resets_zero(vic, reg):
    # Datasheet §16: the trigger-config registers reset to 0 (G4 hardwires them).
    got = vic.regs.get(reg)
    assert got == 0, f"VIC {reg} reset not 0 (G4 value?): {got:#010x}"


@pytest.mark.parametrize("reg,word", FW.items())
def test_trigger_config_writable(vic, reg, word):
    # The fwtest wrote the firmware word then checked read-back; confirm that
    # specific check passed (registers are RW on G3, masked on G4).
    check = next((c for c in vic.checks if c[0] == f"{reg}.rw"), None)
    assert check is not None, f"no {reg}.rw check in transcript:\n{vic.raw}"
    assert check[1], f"VIC {reg} not writable: got {check[2]:#010x}, want {word:#010x}"

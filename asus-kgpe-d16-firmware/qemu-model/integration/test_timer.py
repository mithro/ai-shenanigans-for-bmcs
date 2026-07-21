"""Integration test: Timer (FTTMR010) faithfulness on the QEMU model.

Boots `peripherals/timer/fwtest.c` under `-M kgpe-d16-bmc`: control + count reset
to 0, and enabling timer1 from PCLK loads from reload and counts down. Here we
assert correct reset + functional counting. See peripherals/timer/DOC.md.

H-PLL/CLKIN RATE (#142, FIXED 2026-07-22): the G3 SCU no longer reuses the AST2400
clkin/calc_hpll (which mis-decoded the G3 strap -- CLKIN as 25 MHz because bit23 is
the LPC-reset pin not SCU_HW_STRAP_CLK_25M_IN, and H-PLL from bits[9:8] not the G3's
[11:9]). aspeed_2050_scu_calc_hpll now uses a fixed 24 MHz CLKIN + the SCU70[11:9]
strap table {266,233,200,166,133,100,300,24} MHz -- the G3 strap 0x00819582 ->
[11:9]=011=166 MHz. The corrected rate is validated by all three legacy oracles
booting (C2 Linux, C-UBOOT Raptor U-Boot->boot#, C4 vendor->appweb) plus the
functional counts-down check below. A DETERMINISTIC absolute-rate assertion (count
timer ticks over an independent reference interval) remains a small follow-on --
the bare-metal fwtest has no independent time reference to divide against yet.

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


def test_pclk_rate(timer):
    """#142: PCLK-timer vs 1 MHz-external-timer ratio == PCLK/1MHz.

    timer1 runs off PCLK, timer2 off the 1 MHz external clock; both advance with
    virtual time so d1/d2 is exactly PCLK/1MHz, independent of the spin length.
    Expect ~10.375 (166 MHz H-PLL / (PCLK_DIV=7 + 1) / apb_divider=2 = 10.375 MHz).
    The old mis-decoded 25 MHz-CLKIN / bits[9:8] H-PLL (~375 MHz) would give ~23,
    so this pins the G3 clkin/calc_hpll fix (#142) against regression.
    """
    d1 = timer.kvs.get("rate.d1_pclk")
    d2 = timer.kvs.get("rate.d2_1mhz")
    assert d1 is not None and d2 is not None, f"rate deltas missing:\n{timer.raw}"
    assert d2 > 0, f"1 MHz reference timer did not advance (d2={d2}):\n{timer.raw}"
    ratio = d1 / d2
    assert 8.0 <= ratio <= 13.0, (
        f"PCLK/1MHz ratio {ratio:.2f} (d1={d1} d2={d2}) is not ~10.375 — the G3 "
        f"H-PLL rate is wrong (would be ~23 with the old 25MHz/[9:8] decode):\n{timer.raw}"
    )

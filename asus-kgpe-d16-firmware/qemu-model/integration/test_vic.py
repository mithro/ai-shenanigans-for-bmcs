"""Integration test: VIC (interrupt controller) faithfulness on the QEMU model.

Boots `peripherals/vic/fwtest.c` under `-M kgpe-d16-bmc`. The status/enable/select
registers already reset to 0. The faithful compact G3 VIC (`aspeed.vic-ast2050`,
TYPE_ASPEED_2050_VIC — trigger config sensitivity/both-edge/event reset 0 + fully
writable) plus its kernel driver (`irq-aspeed-g3-vic` + `aspeed,ast2050-vic` DTS)
DO boot our modern kernel (C2/C2-full/C5 all verified — the timer IRQ works). BUT
wiring the G3 VIC breaks the proprietary C410X firmware boot (C4): the vendor
kernel oops's (div0 in aess_write_spi_nor_flash during ftgmac100_open) and reboots
(confirmed locally + in CI run 29099450053). C4 is an UNPATCHABLE legacy-boot
oracle, so per qemu-must-model-real-hardware the machine keeps the AST2400 VIC and
the six G3 checks stay xfail — the G3 VIC model + driver remain in-tree, ready to
re-wire once validated against the KGPE-D16's own firmware (Raptor/C3).
See peripherals/vic/DOC.md. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_vic.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

# fwtest check label -> xfail reason (None = must pass). The six G3 trigger-config
# checks need the G3 VIC wired. Its REGISTER model is hardware-confirmed faithful
# (JTAG: sense/dual/event reset 0 + fully writable — results/vic-hardware-crosscheck.md),
# but wiring it alone breaks the C4 vendor boot via IRQ *routing*, not the register
# model: this SoC uses the AST2400 irqmap (UART2-4/TIMER4-8 on lines 32-39, above the
# G3's single 32-bit bank) so the vendor firmware hangs and the WDT resets it (~16s).
# The earlier "div0 in the vendor SPI-NOR path" is the UNMODELLED legacy SMC and fires
# on the AST2400 VIC too (non-fatal) — it was never the VIC. Completing the G3 VIC
# needs a Table-36 irqmap (+DTS) and the legacy SMC model; until then keep AST2400 VIC.
C4 = ("the G3 VIC register model is hardware-confirmed faithful, but wiring "
      "TYPE_ASPEED_2050_VIC needs a G3 Table-36 irqmap (+DTS) and the legacy SMC "
      "model before the C410X vendor firmware (C4) boots — the AST2400 irqmap "
      "routes UART2-4/TIMER4-8 above the G3's 32-bit bank, hanging the vendor "
      "firmware (WDT reset). Machine keeps the AST2400 VIC. See DOC.md + "
      "results/vic-hardware-crosscheck.md.")
CHECKS = {
    "irqstat.reset": None, "fiqstat.reset": None, "rawstat.reset": None,
    "select.reset": None, "enable.reset": None, "softint.reset": None,
    "protect.reset": None,
    "sense.reset": C4, "dual.reset": C4, "event.reset": C4,
    "sense.rw": C4, "dual.rw": C4, "event.rw": C4,
}


@pytest.fixture(scope="module")
def vic():
    return runner.run_fwtest("vic")


def test_reaches_halt(vic):
    assert vic.halted, f"vic fwtest did not reach the halt sentinel:\n{vic.raw}"


@pytest.mark.parametrize(
    "label",
    [
        pytest.param(k, marks=(pytest.mark.xfail(reason=v, strict=False) if v else ()))
        for k, v in CHECKS.items()
    ],
)
def test_check(vic, label):
    c = next((c for c in vic.checks if c[0] == label), None)
    assert c is not None, f"no '{label}' check in transcript:\n{vic.raw}"
    assert c[1], f"VIC {label}: got {c[2]:#010x}, want {c[3]:#010x}"

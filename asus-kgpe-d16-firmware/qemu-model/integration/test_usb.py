"""Integration test: USB device/vhub faithfulness on the QEMU model.

The AST2050 USB2.0 device/vhub (0x1E6A0000, virtual media) is not modelled, and QEMU
exposes a phantom EHCI host at 0x1E6A1000 the AST2050 lacks — xfail until an
aspeed.usb-vhub-ast2050 is added + the EHCI removed (peripherals/usb/DOC.md §3). No hardware.
"""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402
skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def usb():
    return runner.run_fwtest("usb")


def test_reaches_halt(usb):
    assert usb.halted, f"usb fwtest did not reach the halt sentinel:\n{usb.raw}"


def test_udc_modelled(usb):
    """The G3 USB device/vhub controller (0x1E6A0000) is modelled by the G3-only
    aspeed.udc-ast2050 register block: HUB00 root control is RW. Fixed 2026-07-10
    (DOC.md §3). Full USB device semantics (enumeration, EP DMA, media transport)
    are refinements."""
    c = next((c for c in usb.checks if c[0] == "hub00.rw"), None)
    assert c is not None and c[1], "UDC HUB00 not RW at 0x1E6A0000"


def test_no_phantom_ehci(usb):
    """The AST2050 (G3) has no EHCI host controller — the faithful SoC gates it
    off (aspeed_ast2400.c), so 0x1E6A1000 no longer reads the EHCI cap word
    0x01000020. Fixed 2026-07-10 (DOC.md §3)."""
    assert usb.regs.get("ehci1000", 0) == 0, \
        f"phantom EHCI still present: 0x1E6A1000 = {usb.regs.get('ehci1000'):#x}"

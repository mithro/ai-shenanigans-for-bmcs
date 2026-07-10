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


@pytest.mark.xfail(reason="USB device/vhub unmodelled + phantom EHCI present (DOC.md §3)",
                   strict=False)
def test_udc_modelled(usb):
    c = next((c for c in usb.checks if c[0] == "hub00.rw"), None)
    assert c is not None and c[1]


@pytest.mark.xfail(reason="AST2050 has no EHCI at 0x1E6A1000; QEMU exposes one (DOC.md §3)",
                   strict=False)
def test_no_phantom_ehci(usb):
    assert usb.regs.get("ehci1000", 0) == 0

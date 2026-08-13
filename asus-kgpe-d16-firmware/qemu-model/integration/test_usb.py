"""Integration test: USB device/vhub faithfulness on the QEMU model.

The AST2050's ONLY USB block is the USB2.0 *device / virtual-hub* controller at
0x1E6A0000 (VIC INT#5) — the BMC virtual-media / virtual-HID (KVM) datapath. The
AST2050 has NO USB *host* controller (no EHCI at 0x1E6A1000 — that is AST2400+).
QEMU models it as aspeed.udc-ast2050 (register block) and gates the phantom EHCI
off. This walks the datasheet §15.4 init/register map (HUB/DEV/EPP) to confirm the
register file is present + RW and no phantom EHCI exists. Full device semantics
(enumeration, EP DMA, media transport) are F8-KVM refinements. No hardware.

See peripherals/usb/{DOC.md,DATASHEET-USB.md} and
openbmc/bmc-functionality/F6-USB.md.
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


@pytest.mark.parametrize("label", [
    "hub08.irq_en.rw",   # HUB08 interrupt enables (bus-reset / EP0 int enables)
    "hub20.reset.rw",    # HUB20 device-controller soft-reset enable
    "dev00.enable.rw",   # Device #1 function enable (downstream addr + port enable)
    "epp00.hid_cfg.rw",  # EPP #0 config (Interrupt-In HID endpoint — vKVM kbd/mouse)
    "hub3c.plug.rw",     # HUB3C hub status-change bitmap (host-polled "plugged" byte)
])
def test_register_file_modelled(usb, label):
    """The full datasheet HUB/DEV/EPP register file (§15.3) is present and RW, so the
    aspeed-vhub driver + the vendor firmware's §15.4 init sequence can drive it. The
    Linux aspeed-vhub driver probes this block cleanly in QEMU ('Initialized virtual
    hub in USB2 mode') — see openbmc/bmc-functionality/evidence/f6-usb/ (F6)."""
    c = next((c for c in usb.checks if c[0] == label), None)
    assert c is not None and c[1], f"UDC register {label} not RW"


def test_no_phantom_ehci(usb):
    """The AST2050 (G3) has no EHCI host controller — the faithful SoC gates it
    off (aspeed_ast2400.c), so 0x1E6A1000 no longer reads the EHCI cap word
    0x01000020. Fixed 2026-07-10 (DOC.md §3)."""
    assert usb.regs.get("ehci1000", 0) == 0, \
        f"phantom EHCI still present: 0x1E6A1000 = {usb.regs.get('ehci1000'):#x}"

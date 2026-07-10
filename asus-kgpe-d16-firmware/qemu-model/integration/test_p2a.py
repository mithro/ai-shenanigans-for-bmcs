"""Integration test: P2A / PCI-to-AHB bridge faithfulness on the QEMU model.

From the BMC/AHB side: the PCI identity (vendor 0x1A03 ASPEED) is faithful and SCU2C[8]
enable is observed. The host-side P2A backdoor (PCI-slave BAR window) is not modelled in
QEMU (no host PCI endpoint) — that half is xfail, validated on silicon via culvert. See
peripherals/p2a/DOC.md. No hardware here.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def p2a():
    return runner.run_fwtest("p2a")


def test_reaches_halt(p2a):
    assert p2a.halted, f"p2a fwtest did not reach the halt sentinel:\n{p2a.raw}"


def test_pci_identity_aspeed(p2a):
    c = next((c for c in p2a.checks if c[0] == "pci.vendor_aspeed"), None)
    assert c is not None and c[1], f"PCI vendor id not ASPEED 0x1A03:\n{p2a.raw}"


@pytest.mark.xfail(reason="host-side P2A BAR window not modelled (no host PCI endpoint); "
                          "culvert backdoor validated on silicon (DOC.md §2-3)", strict=False)
def test_a2p_bridge_modelled(p2a):
    assert p2a.regs.get("a2p.bridge", 0) != 0

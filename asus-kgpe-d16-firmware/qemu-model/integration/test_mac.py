"""Integration test: MAC (ftgmac100) faithfulness on the QEMU model.

Boots `peripherals/mac/fwtest.c` under `-M kgpe-d16-bmc`: MACCR is RW and holds the
real captured value, and the descriptor-ring base registers store the full [31:4]
address. The PHY *identity* is unfaithful for the D16 (QEMU models RTL8211E gigabit;
the board has RTL8201CP 10/100) — xfail, oracle-gated (see peripherals/mac/DOC.md §4).
Full TX/RX DMA is exercised by the boot tests. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_mac.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

RTL8211E_ID3 = 0x0000C915   # gigabit PHY id (reg 3) currently modelled


@pytest.fixture(scope="module")
def mac():
    return runner.run_fwtest("mac")


def test_reaches_halt(mac):
    assert mac.halted, f"mac fwtest did not reach the halt sentinel:\n{mac.raw}"


def test_register_checks_pass(mac):
    # MACCR RW + ring-base [31:4] storage.
    failed = [c for c in mac.checks if not c[1]]
    assert mac.fails == 0, f"MAC register checks failed: {failed}\n{mac.raw}"


def test_maccr_writable(mac):
    c = next((c for c in mac.checks if c[0] == "maccr.rw"), None)
    assert c is not None and c[1], f"MACCR not writable:\n{mac.raw}"


@pytest.mark.xfail(reason="D16 PHY should be RTL8201CP (10/100); QEMU models RTL8211E "
                          "(gigabit) — board-specific PHY, oracle-gated (DOC.md §4)",
                   strict=False)
def test_phy_is_10_100(mac):
    # The D16's RTL8201CP is a 10/100 PHY; it must not report the RTL8211E gigabit id.
    assert mac.kvs.get("phy0.id3") != RTL8211E_ID3, (
        f"PHY modelled as RTL8211E (gigabit); D16 has RTL8201CP: "
        f"id3={mac.kvs.get('phy0.id3'):#06x}"
    )

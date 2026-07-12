"""Integration test: MAC (ftgmac100) faithfulness on the QEMU model.

Boots `peripherals/mac/fwtest.c` under `-M kgpe-d16-bmc`: MACCR is RW and holds the
real captured value, and the descriptor-ring base registers store the full [31:4]
address. The G3/KGPE-D16 MDIO PHY is the board's dedicated **Realtek RTL8201CP**
10/100 transceiver (PHYID1=0x0000, PHYID2=0x8201; RTL8201CP datasheet §MII reg 2/3;
mainline drivers/net/phy/realtek.c PHY_ID_MATCH_EXACT(0x00008201); DOC.md §4,
F7-NCSI.md §1). Task #61 gave the kgpe-d16-bmc MAC that identity + a 10/100-only
capability set (no gigabit BMSR/CTRL1000 bits) — the previously-xfailed PHY check now
PASSES. Full TX/RX DMA is exercised by the boot tests. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_mac.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

RTL8201CP_ID2 = 0x00000000  # PHYID1 (MII reg 2) — RTL8201CP datasheet default 0x0000
RTL8201CP_ID3 = 0x00008201  # PHYID2 (MII reg 3) — RTL8201CP datasheet default 0x8201
RTL8211E_ID3 = 0x0000C915   # gigabit PHY id (reg 3) — the AST2400+/C410X default


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


def test_phy_is_rtl8201cp_10_100(mac):
    # The D16's dedicated PHY is the RTL8201CP (10/100). Its MDIO identity must be
    # PHYID1=0x0000 / PHYID2=0x8201, NOT the RTL8211E gigabit id (0xC915) that the
    # AST2400+/C410X path keeps. (Was xfail before task #61; now expected-pass.)
    id2 = mac.kvs.get("phy0.id2")
    id3 = mac.kvs.get("phy0.id3")
    assert id3 == RTL8201CP_ID3 and id2 == RTL8201CP_ID2, (
        f"D16 MDIO PHY should be RTL8201CP (id2=0x0000, id3=0x8201); got "
        f"id2={id2:#06x}, id3={id3:#06x}"
    )
    assert id3 != RTL8211E_ID3, "PHY still modelled as RTL8211E gigabit"


def test_phy_bmsr_no_gigabit(mac):
    # RTL8201CP BMSR must not set the extended-status bit (reg 15 / gigabit); a
    # faithful 10/100 BMSR is 0x786D-class (100/10 FD+HD, MFPS, AN, link, extcap).
    bmsr = mac.kvs.get("phy0.bmsr")
    assert bmsr is not None, f"no BMSR captured:\n{mac.raw}"
    assert not (bmsr & (1 << 8)), (
        f"BMSR advertises gigabit extended status (bit8) — not 10/100-faithful: "
        f"bmsr={bmsr:#06x}"
    )

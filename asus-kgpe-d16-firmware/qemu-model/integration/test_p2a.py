"""Integration test: P2A / PCI-to-AHB back-door faithfulness on the QEMU model.

Two layers:

1. BMC/AHB side (bare-metal fwtest): the PCI identity (vendor 0x1A03 ASPEED) is
   faithful and the SCU2C[8] slave->AHB enable is observed.

2. Host side (the culvert `p2a` back door), driven the KCS-M2 way: since the
   kgpe-d16-bmc machine has no host PCI root complex, the faithful G3 P2A model
   (hw/misc/aspeed_p2a_ast2050.c) exposes the HOST half of the back door — the
   PCI-slave BAR1 window — as QOM properties (host-p2a00-key / host-p2a04-remap /
   host-p2a-offset / host-p2a-data). Those properties replace ONLY the physical
   PCI bus wires + the host-BIOS BAR1 placement they subsume; the P2A00 unlock,
   the P2A04 remap equation, the live SCU2C[8] gate and the AHB access itself are
   the modelled silicon behaviour. TestP2AHostBackdoor drives the host side over
   QMP qom-set/qom-get and the BMC side over qtest MMIO, and reads SCU7C = 0x202
   through the window — the exact value culvert reads over P2A on real silicon —
   plus a write round-trip into AHB/DRAM. See peripherals/p2a/DOC.md. No hardware.
"""
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")

# AHB addresses (AST2050 §9 memory map, p.97).
SCU = 0x1E6E2000
SCU00 = SCU + 0x00        # protection key (0x1688A8A8 unlocks)
SCU2C = SCU + 0x2C        # misc ctrl; bit8 = disable PCI-slave->AHB bridge
SCU7C = SCU + 0x7C        # silicon revision ID = 0x00000202 on the AST2050
SCU_PROT_KEY = 0x1688A8A8
SCU2C_PCI_SLAVE_AHB_DIS = 1 << 8
SILICON_REV_AST2050 = 0x00000202   # culvert reads this over P2A on real silicon
DRAM = 0x40000000

P2A_G3_QOM_PATH = "/machine/soc/p2a-g3"


@pytest.fixture(scope="module")
def p2a():
    return runner.run_fwtest("p2a")


def test_reaches_halt(p2a):
    assert p2a.halted, f"p2a fwtest did not reach the halt sentinel:\n{p2a.raw}"


def test_pci_identity_aspeed(p2a):
    c = next((c for c in p2a.checks if c[0] == "pci.vendor_aspeed"), None)
    assert c is not None and c[1], f"PCI vendor id not ASPEED 0x1A03:\n{p2a.raw}"


qemu_skip = runner.qemu_preconditions()


class QtestMachine:
    """A kgpe-d16-bmc instance under `-accel qtest`: no guest code runs; the
    test does BMC-side AHB MMIO over the qtest protocol and drives the host P2A
    back door (the PCI-slave BAR1 window) over QMP qom-set/qom-get — the model's
    honest stand-in for the PCI bus wires this BMC-only machine cannot have."""

    def __init__(self, qemu: Path, tmpdir: Path):
        qtest_sock = tmpdir / "qtest.sock"
        qmp_sock = tmpdir / "qmp.sock"
        self._qtest_srv = socket.socket(socket.AF_UNIX)
        self._qtest_srv.bind(str(qtest_sock))
        self._qtest_srv.listen(1)
        self._qmp_srv = socket.socket(socket.AF_UNIX)
        self._qmp_srv.bind(str(qmp_sock))
        self._qmp_srv.listen(1)
        self.proc = subprocess.Popen(
            [str(qemu), "-M", "kgpe-d16-bmc", "-m", "64",
             "-display", "none", "-serial", "none", "-monitor", "none",
             "-accel", "qtest",
             "-qtest", f"unix:{qtest_sock}",
             "-qmp", f"unix:{qmp_sock}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._qtest_srv.settimeout(10)
        self._qmp_srv.settimeout(10)
        self.qtest, _ = self._qtest_srv.accept()
        self.qmp, _ = self._qmp_srv.accept()
        self._qtest_f = self.qtest.makefile("rw")
        self._qmp_f = self.qmp.makefile("rw")
        greeting = json.loads(self._qmp_f.readline())
        assert "QMP" in greeting, f"no QMP greeting: {greeting}"
        assert "return" in self._qmp_cmd("qmp_capabilities")

    def _qmp_cmd(self, execute: str, arguments: dict | None = None) -> dict:
        msg = {"execute": execute}
        if arguments is not None:
            msg["arguments"] = arguments
        self._qmp_f.write(json.dumps(msg) + "\n")
        self._qmp_f.flush()
        while True:
            resp = json.loads(self._qmp_f.readline())
            if "return" in resp or "error" in resp:
                return resp
            # skip async events

    def _qtest_cmd(self, line: str) -> str:
        self._qtest_f.write(line + "\n")
        self._qtest_f.flush()
        while True:
            resp = self._qtest_f.readline().strip()
            if resp.startswith("OK"):
                return resp
            if resp.startswith("FAIL"):
                raise AssertionError(f"qtest {line!r} -> {resp}")
            # skip IRQ intercept events etc.

    # -- BMC (AHB/APB) side: real 32-bit MMIO like the ARM core would issue --
    def readl(self, addr: int) -> int:
        return int(self._qtest_cmd(f"readl 0x{addr:x}").split()[1], 16)

    def writel(self, addr: int, val: int) -> None:
        self._qtest_cmd(f"writel 0x{addr:x} 0x{val:x}")

    # -- host (PCI-slave BAR1) side: the P2A QOM back-channel --
    def host_set(self, prop: str, val: int) -> dict:
        return self._qmp_cmd("qom-set", {"path": P2A_G3_QOM_PATH,
                                         "property": prop, "value": val})

    def host_get_raw(self, prop: str) -> dict:
        return self._qmp_cmd("qom-get",
                             {"path": P2A_G3_QOM_PATH, "property": prop})

    def host_get(self, prop: str) -> int:
        resp = self.host_get_raw(prop)
        assert "return" in resp, f"qom-get {prop} failed: {resp}"
        return resp["return"]

    def p2a_window_read(self, ahb: int) -> int:
        """Host READ cycle through the P2A window at an arbitrary AHB address:
        program P2A04[31:16] + the aperture offset, then IN from host-p2a-data."""
        assert "return" in self.host_set("host-p2a04-remap", ahb & 0xFFFF0000)
        assert "return" in self.host_set("host-p2a-offset", ahb & 0xFFFF)
        return self.host_get("host-p2a-data")

    def p2a_window_write(self, ahb: int, val: int) -> dict:
        assert "return" in self.host_set("host-p2a04-remap", ahb & 0xFFFF0000)
        assert "return" in self.host_set("host-p2a-offset", ahb & 0xFFFF)
        return self.host_set("host-p2a-data", val)

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        for s in (self.qtest, self.qmp, self._qtest_srv, self._qmp_srv):
            s.close()


@pytest.fixture(scope="class")
def m(tmp_path_factory):
    machine = QtestMachine(runner.qemu_path(), tmp_path_factory.mktemp("p2a"))
    yield machine
    machine.close()


@pytest.mark.skipif(qemu_skip is not None, reason=qemu_skip or "")
class TestP2AHostBackdoor:
    """The culvert `p2a` back door, exercised end to end against the faithful G3
    model: unlock (P2A00), set the remap window (P2A04), and read/write an
    arbitrary AHB address through the aperture — gated by P2A00[0]=1 and the live
    SCU2C[8]=0. Tests are sequential steps of one bring-up (shared machine)."""

    def test_scu7c_ground_truth_bmc_side(self, m):
        """The BMC/AHB-side value of SCU7C is the AST2050 silicon revision ID
        (0x202) and the PCI-slave->AHB bridge is enabled at the SCU (SCU2C[8]=0),
        so the back door's SCU-level gate is open by default."""
        assert m.readl(SCU7C) == SILICON_REV_AST2050
        assert m.readl(SCU2C) & SCU2C_PCI_SLAVE_AHB_DIS == 0, "SCU2C[8] must be 0"

    def test_locked_backdoor_refuses(self, m):
        """Out of reset P2A00[0]=0: the back door ignores all P-Bus commands
        (datasheet §36.2 p.400), so a host aperture cycle must fail loudly rather
        than fake a value."""
        assert m.host_get("host-p2a00-key") == 0, "key must reset to 0 (locked)"
        assert "return" in m.host_set("host-p2a04-remap", SCU7C & 0xFFFF0000)
        assert "return" in m.host_set("host-p2a-offset", SCU7C & 0xFFFF)
        resp = m.host_get_raw("host-p2a-data")
        assert "error" in resp, f"locked back door must refuse the read: {resp}"

    def test_unlock_and_read_scu7c_through_window(self, m):
        """THE genuine translated access: unlock P2A00, aim the window at SCU7C,
        and read 0x202 back through the aperture — the exact value culvert reads
        over P2A on the real AST2050 (SCU7C=0x00000202)."""
        assert "return" in m.host_set("host-p2a00-key", 1)
        assert m.host_get("host-p2a00-key") == 1, "back door must be unlocked"
        got = m.p2a_window_read(SCU7C)
        assert got == SILICON_REV_AST2050, \
            f"P2A window read of SCU7C = {got:#x}, expected {SILICON_REV_AST2050:#x}"

    def test_window_read_matches_bmc_side(self, m):
        """The host-side P2A read and the BMC-side AHB read of the same register
        agree — the bridge is a faithful address translation, not a fake."""
        assert m.p2a_window_read(SCU7C) == m.readl(SCU7C)

    def test_write_roundtrip_into_ahb_dram(self, m):
        """A host WRITE cycle through the aperture lands in real AHB address
        space: write a pattern to a DRAM scratch word and read it back both via
        the BMC-side MMIO and via the window itself."""
        scratch = DRAM + 0x100
        pattern = 0xDEADBEEF
        assert "return" in m.p2a_window_write(scratch, pattern)
        assert m.readl(scratch) == pattern, "BMC side must see the P2A write"
        assert m.p2a_window_read(scratch) == pattern, "window read-back must match"

    def test_remap_equation_low16_passthrough(self, m):
        """AHB = (P2A04[31:16]<<16) | offset[15:0]: two scratch words in the same
        64KB window are reached by moving only the aperture offset."""
        a0, a1 = DRAM + 0x200, DRAM + 0x2A4
        assert "return" in m.p2a_window_write(a0, 0x11112222)
        assert "return" in m.p2a_window_write(a1, 0x33334444)
        # Remap fixed at the DRAM window; reach both words by only moving offset.
        assert "return" in m.host_set("host-p2a04-remap", DRAM & 0xFFFF0000)
        assert "return" in m.host_set("host-p2a-offset", a0 & 0xFFFF)
        assert m.host_get("host-p2a-data") == 0x11112222
        assert "return" in m.host_set("host-p2a-offset", a1 & 0xFFFF)
        assert m.host_get("host-p2a-data") == 0x33334444

    def test_scu2c_gate_closes_the_backdoor(self, m):
        """The SCU2C[8] gate is genuine and live: with the back door still
        unlocked, disabling the PCI-slave->AHB bridge at the SCU (SCU2C[8]=1)
        makes the window refuse; re-enabling it restores access."""
        assert m.host_get("host-p2a00-key") == 1, "precondition: still unlocked"
        m.writel(SCU00, SCU_PROT_KEY)                 # unlock the SCU
        misc = m.readl(SCU2C)
        m.writel(SCU2C, misc | SCU2C_PCI_SLAVE_AHB_DIS)   # disable slave->AHB
        assert m.readl(SCU2C) & SCU2C_PCI_SLAVE_AHB_DIS, "SCU2C[8] must be set"
        m.host_set("host-p2a04-remap", SCU7C & 0xFFFF0000)
        m.host_set("host-p2a-offset", SCU7C & 0xFFFF)
        resp = m.host_get_raw("host-p2a-data")
        assert "error" in resp, f"SCU-disabled bridge must refuse: {resp}"
        m.writel(SCU2C, misc & ~SCU2C_PCI_SLAVE_AHB_DIS)  # re-enable
        assert m.p2a_window_read(SCU7C) == SILICON_REV_AST2050, "restored access"

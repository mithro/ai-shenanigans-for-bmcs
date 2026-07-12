"""Integration test: LPC host-interface faithfulness on the QEMU model.

The G3 KCS/BT/iLPC2AHB register block lives at 0x24-0x8C — NOT the AST2400 0x140
that mainline aspeed_lpc uses. Fixed 2026-07-10 by aspeed.lpc-ast2050 (a G3-only
register-accurate model that replaces aspeed_lpc for the AST2050): config
registers (HICR) are RW at the G3 offsets, KCS status (STR) resets to 0.

Since 2026-07-12 (KCS M2) the model also implements the faithful H8S/2168-style
KCS OBF/IBF/C-D handshake (datasheet p.315-316) with the IBF interrupt to VIC #8,
and exposes the HOST half of each channel (the LPC I/O ports at LADRn) as QOM
properties `host-kcs<N>-{data,cmdsts}` — the machine has no host CPU, so the
properties replace the LPC bus wires (and only the wires; the handshake itself is
the modelled silicon behaviour). The TestKCS3HostHandshake class below drives the
BMC side over qtest MMIO and the host side over QMP qom-set/qom-get and asserts
every datasheet transition, including the VIC #8 line via the G3 VIC raw-status
register. See peripherals/lpc/DOC.md. No hardware here.
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

LPC = 0x1E789000
HICR0, HICR2, HICR4 = LPC + 0x00, LPC + 0x08, LPC + 0x10
LADR3H, LADR3L = LPC + 0x14, LPC + 0x18
IDR3, ODR3, STR3 = LPC + 0x2C, LPC + 0x38, LPC + 0x44

STR_OBF, STR_IBF, STR_CMD_DAT = 0x01, 0x02, 0x08

VIC = 0x1E6C0000
VIC_RAWSTS = VIC + 0x08   # raw pending, pre-mask (DOC.md; HW-confirmed)
VIC_SENSE = VIC + 0x24    # 1 = level-sensitive (combinational raw bit)
VIC_EVENT = VIC + 0x2C    # 1 = high-level/rising (resets 0 = active-low!)
LPC_IRQ = 8               # LPC -> VIC INT#8 (datasheet §10 Table 36 p.99)

LPC_G3_QOM_PATH = "/machine/soc/lpc-g3"


@pytest.fixture(scope="module")
def lpc():
    return runner.run_fwtest("lpc")


def test_reaches_halt(lpc):
    assert lpc.halted, f"lpc fwtest did not reach the halt sentinel:\n{lpc.raw}"


@pytest.mark.parametrize("label", ["str1.reset", "hicr0.rw", "hicr5.rw"])
def test_g3_lpc_layout(lpc, label):
    """The G3 LPC registers are addressable at the G3 offsets: HICR0 (0x00) and
    the iLPC2AHB HICR5 (0x80) are RW config registers, and KCS STR1 (0x3C) is a
    status register that resets to 0 — proving the model uses the G3 layout,
    not the AST2400 0x140."""
    c = next((c for c in lpc.checks if c[0] == label), None)
    assert c is not None and c[1], f"LPC G3-layout check {label} failed"


class QtestMachine:
    """A kgpe-d16-bmc instance under `-accel qtest`: no guest code runs; the
    test does BMC-side MMIO over the qtest protocol and host-side KCS port
    access over QMP qom-set/qom-get (the model's honest LPC-wire stand-in)."""

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

    # -- BMC (slave/APB) side: real 32-bit MMIO like the kernel's regmap --
    def readl(self, addr: int) -> int:
        return int(self._qtest_cmd(f"readl 0x{addr:x}").split()[1], 16)

    def writel(self, addr: int, val: int) -> None:
        self._qtest_cmd(f"writel 0x{addr:x} 0x{val:x}")

    # -- host (LPC I/O port) side: the QOM back-channel --
    def host_get(self, prop: str) -> int:
        resp = self._qmp_cmd("qom-get",
                             {"path": LPC_G3_QOM_PATH, "property": prop})
        assert "return" in resp, f"qom-get {prop} failed: {resp}"
        return resp["return"]

    def host_set(self, prop: str, val: int) -> dict:
        return self._qmp_cmd("qom-set", {"path": LPC_G3_QOM_PATH,
                                         "property": prop, "value": val})

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
    machine = QtestMachine(runner.qemu_path(), tmp_path_factory.mktemp("kcs"))
    yield machine
    machine.close()


class TestKCS3HostHandshake:
    """The datasheet KCS handshake on channel 3 (IDR3/ODR3/STR3 =
    0x2C/0x38/0x44, host port pair 0xca2/0xca3), asserted transition by
    transition, including the IBF interrupt on VIC #8. Tests in this class are
    sequential steps of one bring-up + transaction; they run in order."""

    def test_host_ports_refused_while_channel_disabled(self, m):
        """Before the BMC enables ch3, the LPC cycle is not claimed: the host
        back-channel fails loudly instead of faking a latched byte."""
        assert m.readl(STR3) == 0, "STR3 must reset to 0"
        resp = m.host_set("host-kcs3-data", 0xAA)
        assert "error" in resp, f"expected error on disabled channel: {resp}"
        assert m.readl(STR3) == 0, "refused host write must not touch STR3"

    def test_bmc_enables_channel3_like_the_kernel_driver(self, m):
        """The exact register writes kcs_bmc_aspeed does at probe: LADR3=0xca2,
        HICR0.LPC3E, HICR4.KCSENBL, HICR2.IBFIE3 (called IBFIF3 on the G3)."""
        m.writel(LADR3H, 0x0C)
        m.writel(LADR3L, 0xA2)
        m.writel(HICR0, m.readl(HICR0) | 0x80)   # LPC3E
        m.writel(HICR4, m.readl(HICR4) | 0x04)   # KCSENBL
        m.writel(HICR2, m.readl(HICR2) | 0x08)   # IBFIF3
        # VIC: make INT#8 high-level-sensitive so rawsts follows the line
        # combinationally (the G3 kernel VIC driver programs SENSE+EVENT the
        # same way; EVENT resets to 0 = active-low, which would invert this).
        m.writel(VIC_EVENT, m.readl(VIC_EVENT) | (1 << LPC_IRQ))
        m.writel(VIC_SENSE, m.readl(VIC_SENSE) | (1 << LPC_IRQ))
        assert m.readl(HICR0) & 0x80
        assert m.readl(VIC_RAWSTS) & (1 << LPC_IRQ) == 0, "IRQ must be quiet"

    def test_host_command_write_sets_ibf_cd_and_irq(self, m):
        """Host OUT 0xca3, WRITE_START: IDR3 latches, IBF=1, C/D=1 (command
        port), and the LPC line to VIC #8 asserts (IBFIF3 is enabled)."""
        resp = m.host_set("host-kcs3-cmdsts", 0x61)   # KCS WRITE_START
        assert "return" in resp, f"host command write failed: {resp}"
        str3 = m.readl(STR3)
        assert str3 & STR_IBF, f"IBF must set on host write: STR3={str3:#x}"
        assert str3 & STR_CMD_DAT, f"C/D must be 1 for command port: {str3:#x}"
        assert m.readl(VIC_RAWSTS) & (1 << LPC_IRQ), "VIC #8 must assert on IBF"

    def test_bmc_idr_read_clears_ibf_and_irq(self, m):
        """BMC read of IDR3 is the receive completion: IBF (and the VIC line)
        clear; C/D keeps reporting the last host port."""
        assert m.readl(IDR3) == 0x61, "IDR3 must hold the host byte"
        str3 = m.readl(STR3)
        assert not (str3 & STR_IBF), f"IBF must clear on IDR read: {str3:#x}"
        assert str3 & STR_CMD_DAT, "C/D unaffected by the BMC IDR read"
        assert m.readl(VIC_RAWSTS) & (1 << LPC_IRQ) == 0, "VIC #8 must deassert"

    def test_host_data_write_clears_cd(self, m):
        """Host OUT 0xca2 (data port): IBF sets again, C/D=0."""
        assert "return" in m.host_set("host-kcs3-data", 0x18)  # netfn 0x06<<2
        str3 = m.readl(STR3)
        assert str3 & STR_IBF and not (str3 & STR_CMD_DAT), f"STR3={str3:#x}"
        assert m.readl(IDR3) == 0x18

    def test_bmc_odr_write_sets_obf_host_read_clears(self, m):
        """BMC posts a response byte: ODR3 write sets OBF; the host sees it via
        IN 0xca3 (status) and consumes it via IN 0xca2 (data), clearing OBF."""
        m.writel(ODR3, 0xAA)
        assert m.readl(STR3) & STR_OBF, "OBF must set on BMC ODR3 write"
        assert m.host_get("host-kcs3-cmdsts") & STR_OBF, "host must see OBF"
        assert m.host_get("host-kcs3-data") == 0xAA, "host must read the byte"
        assert m.readl(STR3) & STR_OBF == 0, "OBF must clear on host data read"

    def test_str3_slave_dbu_rw_and_obf_rw0c(self, m):
        """STR3 slave access (p.316): bits 7:4,2 'defined by user' are RW (the
        kernel keeps the IPMI KCS state bits in 7:6), OBF is RW0C, IBF/C-D are
        read-only for the BMC."""
        m.writel(ODR3, 0x00)                       # set OBF again
        before = m.readl(STR3)
        assert before & STR_OBF
        m.writel(STR3, (before & ~0xC0) | 0x80 | STR_OBF)  # state=WRITE, OBF=1
        got = m.readl(STR3)
        assert got & 0xC0 == 0x80, f"DBU state bits must be slave-RW: {got:#x}"
        assert got & STR_OBF, "writing OBF=1 must NOT clear it (RW0C)"
        m.writel(STR3, got & ~STR_OBF & 0xFF)
        assert m.readl(STR3) & STR_OBF == 0, "writing OBF=0 must clear it"

    def test_idr3_is_host_owned(self, m):
        """IDR3 is Slave R / Host W (p.315): a BMC write must be dropped."""
        m.writel(IDR3, 0x77)
        assert m.readl(IDR3) == 0x18, "BMC write to IDR3 must be ignored"

"""Integration test: I2C/SMBus faithfulness on the QEMU model.

Boots `peripherals/i2c/fwtest.c` under `-M kgpe-d16-bmc`: function-control resets
to 0 and MASTER_EN is RW, the engine is held in reset by SCU04[2] until de-asserted,
and the master engine runs a START (auto-clears it + advances the CMD state field).
With the ACK/NAK interrupts enabled (I2CD0C) as the datasheet's master-transmit
sequence and real firmware require, the AST2050 master's address-probe ACK/NAK is
faithful (datasheet §31.5): a bare addr+W START of a present device latches TX_ACK
into I2CD10, an absent address latches TX_NAK.

The one device at 0x50 on this shared machine is the Dell C410X MAC/config EEPROM
(seeded for the C4 vendor oracle), NOT a KGPE-D16 board device — the KGPE-D16 has no
attested probe-able BMC I2C EEPROM (its FRU is software-populated). So this asserts
the shared *master-engine* probe behaviour, not a fictional KGPE-D16 EEPROM.
See peripherals/i2c/DOC.md §2.1. No hardware here.

Run:  uv run --with pytest python -m pytest integration/test_i2c.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def i2c():
    return runner.run_fwtest("i2c")


def test_reaches_halt(i2c):
    assert i2c.halted, f"i2c fwtest did not reach the halt sentinel:\n{i2c.raw}"


def test_register_and_engine(i2c):
    # function-control RW + master engine executes (START auto-clears).
    failed = [c for c in i2c.checks if not c[1]]
    assert i2c.fails == 0, f"I2C register/engine checks failed: {failed}\n{i2c.raw}"


def test_eeprom_probe_acks(i2c):
    # The shared machine carries one device at 0x50 (an smbus_eeprom on bus 0 —
    # the C410X MAC store for the C4 oracle; DOC.md §2.1). A bare addr+W probe
    # with the ACK/NAK interrupts enabled (as the datasheet + firmware require)
    # sets TX_ACK, so bit0 of ack50.mask is set. Buses 1-6 have no device at 0x50
    # → mask is exactly 0x01. This proves the AST2050 master-engine probe-ACK
    # path, formerly xfail (task #63).
    mask = i2c.kvs.get("ack50.mask")
    assert mask is not None and (mask & 1), f"no EEPROM ACK observed:\n{i2c.raw}"
    assert mask == 1, f"unexpected extra ACK (only bus 0 has 0x50):\n{i2c.raw}"


def test_psu_pmbus_probe(i2c):
    # The kgpe-d16-bmc machine wires a generic pmbus-psu (hw/sensor/pmbus_psu.c)
    # at 0x58 on bus 0 = DT i2c0 = schematic I2C1 (connector PSUSMB1). A bare
    # addr+W probe must ACK on bus 0 (the PSU is present + addressable) and NAK
    # on buses 1-6, so ack58.mask is exactly 0x01 — the schematic-faithful engine.
    mask = i2c.kvs.get("ack58.mask")
    assert mask is not None and (mask & 1), f"PSU 0x58 did not ACK on bus 0:\n{i2c.raw}"
    assert mask == 1, f"PSU 0x58 ACKed on an unexpected bus (want only bus 0):\n{i2c.raw}"

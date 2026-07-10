"""Integration test: I2C/SMBus faithfulness on the QEMU model.

Boots `peripherals/i2c/fwtest.c` under `-M kgpe-d16-bmc`: function-control resets
to 0 and MASTER_EN is RW, and the master engine executes a START command (auto-clears
it + advances the CMD status field). A full device readback of the seeded EEPROM is
deferred (the model reports status in the CMD state field and the smbus_eeprom needs
the SMBus command protocol) — xfail. See peripherals/i2c/DOC.md. No hardware here.

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


@pytest.mark.xfail(reason="full I2C transaction ACK/NAK + smbus_eeprom device readback "
                          "needs the exact status-field + SMBus command protocol "
                          "(DOC.md §2)", strict=False)
def test_eeprom_readback(i2c):
    # The machine seeds an EEPROM at 0x50; a bus should ACK it (bit0 of the kv).
    acks = [v for v in [i2c.kvs.get("ack50.bus")] if v is not None]
    assert acks and (acks[0] & 1), f"no EEPROM ACK observed:\n{i2c.raw}"

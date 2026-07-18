"""Integration test: KGPE-D16 QU9/QU5/U23 I2C mux fabric (DIMM SPD/TSOD).

Boots `peripherals/i2cmux/fwtest.c` under `-M kgpe-d16-bmc` and proves the
netlist-decoded board fabric (schematic-wiring/I2C-MUX-FABRIC-ARBITRATION.md):

- QU9's bridge is gated on host SYS_PWRGD (no BMC enable GPIO exists): with
  the host off, DIMM SPD probes NAK while the W83795G — directly on I2C2,
  before the fabric — still ACKs.
- The QU5 selects idle at S1:S0=11 (pull-ups) = the empty E-H bank; driving
  GPIOF4 low routes to bank Y2 where the rig's DIMM A2 answers: SPD 0x51 ACKs,
  the unpopulated 0x50 NAKs, and 0x19 (TSOD) NAKs — the real A2 UDIMM has no
  thermal sensor (SPD byte32=0), matching silicon.
- The SPD data path works end-to-end against the REAL silicon-read SPD:
  byte0=0x92 (DDR3 header), byte2=0x0B (DDR3), byte3=0x02 (UDIMM).
- Routing is live, not cached: re-selecting Y3 makes 0x51 vanish; forcing
  host power off makes the whole fabric vanish mid-session.

Run:  uv run --with pytest python -m pytest integration/test_i2cmux.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def mux():
    return runner.run_fwtest("i2cmux", timeout=30.0)


def test_reaches_halt(mux):
    assert mux.halted, f"i2cmux fwtest did not reach the halt sentinel:\n{mux.raw}"


def test_all_checks_pass(mux):
    failed = [c for c in mux.checks if not c[1]]
    assert mux.fails == 0, f"fabric checks failed: {failed}\n{mux.raw}"


def test_host_power_gates_fabric(mux):
    by = {c[0]: c for c in mux.checks}
    assert by["hostoff.spd_naks"][1] and by["hostoff2.spd_naks"][1]
    assert by["hostoff.hwmon_acks"][1], "W83795G must not be fabric-gated"


def test_spd_content(mux):
    assert mux.kvs.get("spd.b0") == 0x92    # DDR3 SPD header
    assert mux.kvs.get("spd.b2") == 0x0B    # memory type = DDR3
    assert mux.kvs.get("spd.b3") == 0x02    # module type = UDIMM (real rig DIMM)

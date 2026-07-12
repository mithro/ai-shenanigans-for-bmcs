"""Unit tests for the C410X board bench I2C-map check."""

from firmware_testbench.benches.board_c410x import EXPECTED_DIRECT, check_i2c_map


def test_perfect_map_has_no_discrepancies():
    # A detected map that exactly matches expectation on the enumerated buses.
    detected = {bus: set(addrs) for bus, addrs in EXPECTED_DIRECT.items()}
    assert check_i2c_map(detected) == []


def test_missing_ina219_reported():
    detected = {bus: set(addrs) for bus, addrs in EXPECTED_DIRECT.items()}
    detected[0xF0].discard(0x4F)          # slot-16 power monitor absent
    disc = check_i2c_map(detected)
    assert len(disc) == 1
    assert disc[0].bus == 0xF0
    assert disc[0].missing == {0x4F}
    assert "missing 0x4f" in str(disc[0])


def test_unexpected_device_reported():
    detected = {bus: set(addrs) for bus, addrs in EXPECTED_DIRECT.items()}
    detected[0xF2].add(0x51)              # stray device on the EEPROM bus
    disc = check_i2c_map(detected)
    assert any(d.bus == 0xF2 and d.unexpected == {0x51} for d in disc)


def test_variable_bus_not_checked_for_completeness():
    # PMBus PSU bus (0xF5) has an empty expectation: emptiness is not an error.
    detected = {bus: set(addrs) for bus, addrs in EXPECTED_DIRECT.items()}
    detected[0xF5] = set()
    assert all(d.bus != 0xF5 for d in check_i2c_map(detected))

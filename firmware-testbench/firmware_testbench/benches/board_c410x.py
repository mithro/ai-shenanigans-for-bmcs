"""Dell C410X board-level bench: the expected I2C device map and its check.

The expected map is the reverse-engineered ground truth (see the project's
dell-c410x-firmware/datasheets/README.md I2C topology and the docs site
``hardware/i2c-topology``). ``check_i2c_map`` compares a detected map (from
``parse_i2cdetect`` over each bus) to this expectation and returns a list of
human-readable discrepancies -- empty means the board emulation matches silicon.

Bus numbers here are the *logical* AST2050 I2C controller indices used by the
firmware (0xF0-0xF6). On a Linux target they appear as adapters 0..6; the bench
takes a mapping from logical bus to the detected address set.
"""

from __future__ import annotations

from dataclasses import dataclass

# Logical bus -> set of expected 7-bit addresses directly on that bus.
# Muxed devices (behind PCA954x) are listed under their downstream channel in
# EXPECTED_MUXED and are only visible once the channel is selected.
EXPECTED_DIRECT: dict[int, set[int]] = {
    0xF0: set(range(0x40, 0x50)),          # 16x INA219 (per-slot power)
    0xF1: {0x70, 0x20},                     # PCA9544 mux + PCA9555 #5
    0xF2: {0x50},                           # AT24C256 EEPROM (FRU)
    # PEX switches, as 7-bit addresses (i2cdetect reports 7-bit). The GBT 8-bit
    # forms are PEX8696 0x30/0x32/0x34/0x36 and PEX8647 0xD0/0xD4 (= 7-bit << 1).
    0xF3: {0x30 >> 1, 0x32 >> 1, 0x34 >> 1, 0x36 >> 1, 0xD0 >> 1, 0xD4 >> 1},
    0xF4: {0x70, 0x71},                     # 2x PCA9548 mux
    0xF5: set(),                            # PMBus PSUs (addresses vary by PSU)
    0xF6: {0x20, 0x21, 0x22, 0x23, 0x4F},   # 4x PCA9555 + LM75 ambient
}

# Downstream of a mux: (parent_bus, mux_addr, channel) -> expected addresses.
EXPECTED_MUXED: dict[tuple[int, int, int], set[int]] = {
    (0xF1, 0x70, 0): {0x58},                # ADT7462 #1 (fans 1-4)
    (0xF1, 0x70, 1): {0x5C},                # ADT7462 #2 (fans 5-8)
    **{(0xF4, 0x70, ch): {0x5C} for ch in range(8)},   # TMP75 slots 1-8
    **{(0xF4, 0x71, ch): {0x5C} for ch in range(8)},   # TMP75 slots 9-16
}


@dataclass
class I2CDiscrepancy:
    bus: int
    missing: set[int]
    unexpected: set[int]

    def __str__(self) -> str:
        parts = [f"bus {self.bus:#04x}:"]
        if self.missing:
            parts.append("missing " + ",".join(f"{a:#04x}" for a in sorted(self.missing)))
        if self.unexpected:
            parts.append("unexpected " + ",".join(f"{a:#04x}" for a in sorted(self.unexpected)))
        return " ".join(parts)


def check_i2c_map(detected: dict[int, set[int]]) -> list[I2CDiscrepancy]:
    """Compare a detected direct-bus map to :data:`EXPECTED_DIRECT`.

    ``detected`` maps logical bus -> set of addresses seen by ``i2cdetect`` on
    that bus (no mux channel selected). Buses with an empty expectation
    (variable addressing, e.g. PMBus PSUs) are only checked for *unexpected*
    devices, not for completeness.
    """
    out: list[I2CDiscrepancy] = []
    for bus, expected in EXPECTED_DIRECT.items():
        seen = detected.get(bus, set())
        missing = expected - seen
        unexpected = seen - expected
        # Don't flag "missing" on buses we don't fully enumerate.
        if not expected:
            missing = set()
        if missing or unexpected:
            out.append(I2CDiscrepancy(bus, missing, unexpected))
    return out

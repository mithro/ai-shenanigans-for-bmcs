#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["smbus2>=0.4"]
# ///
"""Dell C410X PEX PCIe switch I2C control library.

Implements the PLX 4-byte I2C command protocol for communicating with
PEX8696 (96-lane downstream) and PEX8647 (48-lane upstream) PCIe switches
on the Dell C410X GPU expansion chassis.

Protocol reference: Reverse engineered from Avocent MergePoint firmware v1.35.
See PEX-I2C-COMMANDS.md for the complete register-level documentation.

Usage:
    from c410x_pex import C410X

    chassis = C410X(i2c_bus=3)
    chassis.slot_power_on(4)           # Power on slot 4
    chassis.startup_all()              # Full 16-slot staggered power-on
    chassis.shutdown_all()             # Power off all 16 slots
    chassis.set_multihost_mode("4:1")  # Configure 4:1 fan-out
"""

from __future__ import annotations

import logging
import struct
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Sequence

try:
    from smbus2 import SMBus, i2c_msg
except ImportError:
    SMBus = None  # type: ignore[misc, assignment]
    i2c_msg = None  # type: ignore[misc, assignment]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PLX I2C command constants
# ---------------------------------------------------------------------------

class PlxCmd(IntEnum):
    """PLX I2C command type bytes."""
    WRITE = 0x03
    READ = 0x04


# Default byte-enables mask: all 4 bytes enabled, reg_hi=0, port_lo=0
BYTE_ENABLES_ALL = 0x3C


# ---------------------------------------------------------------------------
# PLX register DWORD indices (byte_addr / 4)
# ---------------------------------------------------------------------------

class PlxReg(IntEnum):
    """PLX register DWORD indices used by the C410X firmware."""
    # PCIe standard registers (relative to PCIe Capability base 0x068)
    SLOT_CAP = 0x1F          # 0x07C: Slot Capabilities / Write Protect
    SLOT_CTRL_STATUS = 0x20  # 0x080: Slot Control / Slot Status

    # PLX proprietary registers
    PORT_CTRL_MASK = 0x81    # 0x204: Port control mask
    HP_LED_MRL = 0x8A        # 0x228: Hot-plug LED / MRL control
    HP_POWER_CTRL = 0x8D     # 0x234: Hot-plug power controller control
    PORT_MERGE = 0x77        # 0x1DC: Port merging / aggregation (PEX8647)
    LANE_CFG_LO = 0xE0       # 0x380: Port/lane configuration lower
    LANE_CFG_HI = 0xE1       # 0x384: Port/lane configuration upper
    NT_BRIDGE = 0xEB         # 0x3AC: NT bridge setup
    SERDES_EQ1 = 0x2E4       # 0xB90: SerDes equalization coeff 1
    SERDES_EQ2 = 0x2E7       # 0xB9C: SerDes equalization coeff 2
    SERDES_DEEMPH1 = 0x2E9   # 0xBA4: SerDes de-emphasis 1
    SERDES_DEEMPH2 = 0x2EA   # 0xBA8: SerDes de-emphasis 2


# ---------------------------------------------------------------------------
# Bit-field constants for slot control
# ---------------------------------------------------------------------------

# Register 0x07C (SLOT_CAP) bit 18 = write-protect enable
WRITE_PROTECT_BIT = 1 << 18

# Register 0x080 (SLOT_CTRL_STATUS) fields
SLOT_CTRL_PIC_MASK = 0x0300      # Power Indicator Control [9:8]
SLOT_CTRL_PIC_ON = 0x0100        # PIC = 01 (ON)
SLOT_CTRL_PIC_OFF = 0x0300       # PIC = 11 (OFF)
SLOT_CTRL_AIC_MASK = 0x00C0      # Attention Indicator Control [7:6]
SLOT_CTRL_PCC = 0x0400           # Power Controller Control bit [10]
SLOT_CTRL_POWER_OFF_BITS = 0x0700  # PIC=OFF + PCC=1 (attention ON)

# Register 0x234 (HP_POWER_CTRL) bit 0 = pulse trigger
HP_POWER_PULSE_BIT = 0x01

# Register 0x228 (HP_LED_MRL) bit 21 = MRL/LED enable
HP_LED_ENABLE_BIT = 1 << 21


# ---------------------------------------------------------------------------
# Dell C410X hardware topology
# ---------------------------------------------------------------------------

# PEX8696 downstream switch 8-bit I2C addresses (GBT format)
PEX8696_ADDRS = [0x30, 0x34, 0x32, 0x36]

# PEX8647 upstream switch 8-bit I2C addresses (GBT format)
PEX8647_ADDRS = [0xD4, 0xD0]


@dataclass(frozen=True)
class SlotInfo:
    """Mapping from a GPU slot to its PEX8696 switch port."""
    slot_num: int       # 1-based slot number (1-16)
    i2c_addr: int       # 8-bit GBT I2C address of the PEX8696
    port_byte: int      # Pre-encoded station/port byte for PLX I2C cmd

    @property
    def switch_index(self) -> int:
        """Which PEX8696 switch (0-3) this slot belongs to."""
        return PEX8696_ADDRS.index(self.i2c_addr)

    @property
    def station(self) -> int:
        """PLX station number decoded from port_byte."""
        return self.port_byte >> 1

    def __str__(self) -> str:
        return (
            f"Slot {self.slot_num}: switch #{self.switch_index} "
            f"(0x{self.i2c_addr:02X}), station {self.station}"
        )


# Slot mapping table extracted from firmware ROM at 0xF7B06/0xF7B16.
# Index = slot_index (0-15), value = (i2c_8bit_addr, port_byte)
_SLOT_MAP_RAW: list[tuple[int, int]] = [
    (0x30, 0x04),  # Slot 1:  Switch #0, station 2
    (0x30, 0x0A),  # Slot 2:  Switch #0, station 5
    (0x34, 0x04),  # Slot 3:  Switch #1, station 2
    (0x34, 0x0A),  # Slot 4:  Switch #1, station 5
    (0x32, 0x04),  # Slot 5:  Switch #2, station 2
    (0x32, 0x0A),  # Slot 6:  Switch #2, station 5
    (0x36, 0x02),  # Slot 7:  Switch #3, station 1
    (0x36, 0x08),  # Slot 8:  Switch #3, station 4
    (0x36, 0x04),  # Slot 9:  Switch #3, station 2
    (0x36, 0x0A),  # Slot 10: Switch #3, station 5
    (0x32, 0x02),  # Slot 11: Switch #2, station 1
    (0x32, 0x08),  # Slot 12: Switch #2, station 4
    (0x34, 0x02),  # Slot 13: Switch #1, station 1
    (0x34, 0x08),  # Slot 14: Switch #1, station 4
    (0x30, 0x02),  # Slot 15: Switch #0, station 1
    (0x30, 0x08),  # Slot 16: Switch #0, station 4
]

SLOT_MAP: list[SlotInfo] = [
    SlotInfo(slot_num=i + 1, i2c_addr=addr, port_byte=port)
    for i, (addr, port) in enumerate(_SLOT_MAP_RAW)
]

# Staggered power-on phases (firmware powers in reverse numerical order)
# Each phase activates one slot per PEX8696 switch to distribute inrush
POWER_ON_PHASES: list[list[int]] = [
    [3, 7, 11, 15],   # Phase 1: slots 4, 8, 12, 16
    [2, 6, 10, 14],   # Phase 2: slots 3, 7, 11, 15
    [1, 5, 9, 13],    # Phase 3: slots 2, 6, 10, 14
    [0, 4, 8, 12],    # Phase 4: slots 1, 5, 9, 13
]


# ---------------------------------------------------------------------------
# PLX I2C transport
# ---------------------------------------------------------------------------

class PlxI2C:
    """Low-level PLX 4-byte I2C command protocol implementation.

    This handles the wire-level encoding/decoding for communicating with
    PEX8696 and PEX8647 switches. Each transaction sends a 4-byte command
    header that encodes the target station/port, byte enables, and register
    DWORD index.

    Write: 8 bytes on wire (4-byte cmd + 4-byte LE value)
    Read:  write 4-byte cmd, then read back 4 bytes (LE value)
    """

    def __init__(self, bus: int, *, dry_run: bool = False) -> None:
        """Open an I2C bus for PLX switch communication.

        Args:
            bus: Linux I2C bus number (e.g. 3 for /dev/i2c-3).
            dry_run: If True, log transactions but don't touch hardware.
        """
        self.bus_number = bus
        self.dry_run = dry_run
        self._smbus: SMBus | None = None

        if not dry_run:
            if SMBus is None:
                raise ImportError(
                    "smbus2 is required for I2C access. "
                    "Install with: pip install smbus2"
                )
            self._smbus = SMBus(bus)

    def close(self) -> None:
        """Release the I2C bus."""
        if self._smbus is not None:
            self._smbus.close()
            self._smbus = None

    def __enter__(self) -> PlxI2C:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _build_cmd(
        cmd_type: PlxCmd,
        port_byte: int,
        dword_idx: int,
        *,
        enables: int = BYTE_ENABLES_ALL,
    ) -> bytes:
        """Build a 4-byte PLX I2C command header.

        Args:
            cmd_type: PlxCmd.WRITE (0x03) or PlxCmd.READ (0x04).
            port_byte: Station/port encoding byte.
            dword_idx: Register DWORD index (byte_addr / 4).
            enables: Byte-enable mask (default 0x3C = all 4 bytes).

        Returns:
            4-byte command: [cmd, port_byte, enables|reg_hi, reg_lo]
        """
        reg_hi = (dword_idx >> 8) & 0x03
        reg_lo = dword_idx & 0xFF
        return bytes([cmd_type, port_byte, enables | reg_hi, reg_lo])

    def write_register(
        self,
        i2c_addr: int,
        port_byte: int,
        dword_idx: int,
        value: int,
    ) -> None:
        """Write a 32-bit value to a PLX register via I2C.

        Sends 8 bytes: 4-byte command + 4-byte little-endian value.

        Args:
            i2c_addr: 7-bit I2C address of the PLX switch.
            port_byte: Station/port encoding for the target port.
            dword_idx: Register DWORD index.
            value: 32-bit value to write.
        """
        cmd = self._build_cmd(PlxCmd.WRITE, port_byte, dword_idx)
        val_bytes = struct.pack("<I", value & 0xFFFFFFFF)
        data = cmd + val_bytes

        log.debug(
            "PLX WRITE  0x%02X port=0x%02X reg=0x%03X (dw 0x%02X) "
            "val=0x%08X  wire=[%s]",
            i2c_addr, port_byte, dword_idx * 4, dword_idx, value,
            " ".join(f"{b:02X}" for b in data),
        )

        if self.dry_run:
            return

        assert self._smbus is not None
        msg_w = i2c_msg.write(i2c_addr, data)
        self._smbus.i2c_rdwr(msg_w)

    def read_register(
        self,
        i2c_addr: int,
        port_byte: int,
        dword_idx: int,
    ) -> int:
        """Read a 32-bit value from a PLX register via I2C.

        Sends 4-byte command, then reads back 4 bytes (little-endian).

        Args:
            i2c_addr: 7-bit I2C address of the PLX switch.
            port_byte: Station/port encoding for the target port.
            dword_idx: Register DWORD index.

        Returns:
            32-bit register value.
        """
        cmd = self._build_cmd(PlxCmd.READ, port_byte, dword_idx)

        log.debug(
            "PLX READ   0x%02X port=0x%02X reg=0x%03X (dw 0x%02X)  "
            "cmd=[%s]",
            i2c_addr, port_byte, dword_idx * 4, dword_idx,
            " ".join(f"{b:02X}" for b in cmd),
        )

        if self.dry_run:
            # In dry-run mode, return 0 so read-modify-write still works
            return 0x00000000

        assert self._smbus is not None
        msg_w = i2c_msg.write(i2c_addr, cmd)
        msg_r = i2c_msg.read(i2c_addr, 4)
        self._smbus.i2c_rdwr(msg_w, msg_r)

        raw = bytes(msg_r)
        value = struct.unpack("<I", raw)[0]

        log.debug(
            "PLX READ   0x%02X -> 0x%08X  raw=[%s]",
            i2c_addr, value,
            " ".join(f"{b:02X}" for b in raw),
        )
        return value

    def read_modify_write(
        self,
        i2c_addr: int,
        port_byte: int,
        dword_idx: int,
        *,
        set_bits: int = 0,
        clear_bits: int = 0,
    ) -> int:
        """Atomic read-modify-write on a PLX register.

        Args:
            i2c_addr: 7-bit I2C address.
            port_byte: Station/port encoding.
            dword_idx: Register DWORD index.
            set_bits: Bits to set (OR mask).
            clear_bits: Bits to clear (inverted AND mask).

        Returns:
            The new register value after modification.
        """
        val = self.read_register(i2c_addr, port_byte, dword_idx)
        val = (val | set_bits) & ~clear_bits
        self.write_register(i2c_addr, port_byte, dword_idx, val)
        return val


# ---------------------------------------------------------------------------
# Slot power control
# ---------------------------------------------------------------------------

class SlotPowerController:
    """Controls GPU slot power via PEX8696 I2C register writes.

    Implements the exact power-on/off sequences reverse engineered from
    the Dell C410X Avocent firmware.
    """

    # Delay between asserting and de-asserting the power controller pulse
    POWER_PULSE_DELAY_S = 0.1  # 100ms, matches firmware

    def __init__(self, plx: PlxI2C) -> None:
        self.plx = plx

    def _unprotect(self, slot: SlotInfo) -> None:
        """Remove write protection for a slot's PEX8696 port.

        Read-modify-write on register 0x07C: clear bit 18.
        """
        log.info("Unprotect %s", slot)
        self.plx.read_modify_write(
            slot.i2c_addr, slot.port_byte, PlxReg.SLOT_CAP,
            clear_bits=WRITE_PROTECT_BIT,
        )

    def power_on(self, slot: SlotInfo) -> None:
        """Power on a single GPU slot.

        Executes the 4-step sequence (9 I2C transactions + 100ms delay):
          1. Remove write protection (reg 0x07C)
          2. Set slot control indicators (reg 0x080)
          3. Pulse hardware power controller (reg 0x234)
          4. Enable hot-plug LED (reg 0x228)
        """
        log.info("Power ON %s", slot)

        # Step 1: Remove write protection
        self._unprotect(slot)

        # Step 2: Set power indicator = ON, clear PCC (power on)
        val = self.plx.read_register(
            slot.i2c_addr, slot.port_byte, PlxReg.SLOT_CTRL_STATUS
        )
        val = (val & ~SLOT_CTRL_PIC_MASK) | SLOT_CTRL_PIC_ON
        val &= ~SLOT_CTRL_PCC  # clear PCC = power on
        self.plx.write_register(
            slot.i2c_addr, slot.port_byte, PlxReg.SLOT_CTRL_STATUS, val
        )

        # Step 3: Pulse the hardware power controller
        val = self.plx.read_register(
            slot.i2c_addr, slot.port_byte, PlxReg.HP_POWER_CTRL
        )
        # Assert bit 0
        self.plx.write_register(
            slot.i2c_addr, slot.port_byte, PlxReg.HP_POWER_CTRL,
            val | HP_POWER_PULSE_BIT,
        )
        time.sleep(self.POWER_PULSE_DELAY_S)
        # De-assert bit 0
        self.plx.write_register(
            slot.i2c_addr, slot.port_byte, PlxReg.HP_POWER_CTRL,
            val & ~HP_POWER_PULSE_BIT,
        )

        # Step 4: Enable hot-plug LED / MRL
        self.plx.read_modify_write(
            slot.i2c_addr, slot.port_byte, PlxReg.HP_LED_MRL,
            set_bits=HP_LED_ENABLE_BIT,
        )

        log.info("Power ON %s complete", slot)

    def power_off(self, slot: SlotInfo) -> None:
        """Power off a single GPU slot.

        Sets power indicator = OFF and attention = ON in register 0x080.
        No power controller pulse, no delays.
        """
        log.info("Power OFF %s", slot)
        self.plx.read_modify_write(
            slot.i2c_addr, slot.port_byte, PlxReg.SLOT_CTRL_STATUS,
            set_bits=SLOT_CTRL_POWER_OFF_BITS,
        )

    def power_off_all(self) -> None:
        """Power off all 16 GPU slots (not staggered).

        Uses the read-modify-write approach (32 I2C transactions).
        """
        log.info("Power OFF all 16 slots")
        for slot in SLOT_MAP:
            self.power_off(slot)

    def startup_all(
        self,
        present_mask: int = 0xFFFF,
    ) -> None:
        """Execute the full 16-slot staggered power-on sequence.

        Powers on slots in 4 phases, activating one slot per PEX8696
        switch per phase to distribute inrush current.

        Args:
            present_mask: 16-bit mask of physically present GPUs.
                          Bit 0 = slot 1, bit 15 = slot 16.
                          Default 0xFFFF = all present.
        """
        log.info(
            "Starting 16-slot power sequence (present=0x%04X)", present_mask
        )

        for phase_num, slot_indices in enumerate(POWER_ON_PHASES, 1):
            log.info("Phase %d: slots %s", phase_num, [
                SLOT_MAP[i].slot_num for i in slot_indices
            ])
            for slot_idx in slot_indices:
                if present_mask & (1 << slot_idx):
                    self.power_on(SLOT_MAP[slot_idx])
                else:
                    log.info(
                        "Skipping slot %d (not present)", slot_idx + 1
                    )

        log.info("16-slot power sequence complete")

    def shutdown_all(self) -> None:
        """Power off all 16 GPU slots (not staggered)."""
        self.power_off_all()


# ---------------------------------------------------------------------------
# Multi-host mode configuration
# ---------------------------------------------------------------------------

class MultiHostMode(IntEnum):
    """Supported host-to-GPU fan-out ratios."""
    MODE_2_1 = 2   # 2:1 — each iPass serves 2 GPU slots
    MODE_4_1 = 4   # 4:1 — each iPass serves 4 GPU slots (default)
    MODE_8_1 = 8   # 8:1 — each iPass serves 8 GPU slots


# PEX8647 station/port bytes for multi-host configuration
_PEX8647_STN0_PORT0 = 0x00  # Station 0, port 0
_PEX8647_STN2_PORT0 = 0x04  # Station 2, port 0

# PEX8696 station/port bytes for configuration port and NT bridge
_PEX8696_CFG_PORT = 0x00        # Station 0, port 0 (upstream/config)
_PEX8696_NT_BRIDGE = 0x07       # Station 3, port 1 (NT bridge, port 15)
_PEX8696_NT_ENABLES = 0xBC      # byte enables with port_lo=1 for odd port


class MultiHostController:
    """Configures PEX8696/PEX8647 lane topology for multi-host modes.

    The Dell C410X supports three fan-out modes:
      2:1 — 8 hosts, each with 2 GPU slots
      4:1 — 4 hosts, each with 4 GPU slots (default)
      8:1 — 2 hosts, each with 8 GPU slots

    Mode switching reconfigures both the downstream PEX8696 switches
    (lane partitioning) and upstream PEX8647 switches (port merging).
    """

    # Delays match firmware: 200ms (20 ticks at 10ms/tick)
    MODE_SWITCH_DELAY_S = 0.2

    def __init__(self, plx: PlxI2C) -> None:
        self.plx = plx

    def _configure_pex8696_lanes(self, mode: MultiHostMode) -> None:
        """Write lane configuration registers to all 4 PEX8696 switches."""
        if mode == MultiHostMode.MODE_2_1:
            reg_384_val = 0x00101100  # bits 8, 12 set in upper
            reg_380_val = 0x11010000  # bits 8, 12 clear in lower
        else:
            # 4:1 and 8:1 share the same PEX8696 configuration
            reg_384_val = 0x00100000  # bits 8, 12 clear in upper
            reg_380_val = 0x11011100  # bits 8, 12 set in lower

        for addr in PEX8696_ADDRS:
            log.info(
                "PEX8696 0x%02X: lane config for %s mode", addr, mode.name
            )
            self.plx.write_register(
                addr, _PEX8696_CFG_PORT, PlxReg.LANE_CFG_HI, reg_384_val
            )
            self.plx.write_register(
                addr, _PEX8696_CFG_PORT, PlxReg.LANE_CFG_LO, reg_380_val
            )

    def _configure_pex8696_nt_bridge(self) -> None:
        """Configure NT bridge port (global port 15) on all PEX8696 switches.

        Uses byte[2] = 0xBC (port_lo=1 for odd port, enables=0xF).
        """
        for addr in PEX8696_ADDRS:
            log.info("PEX8696 0x%02X: NT bridge setup", addr)
            # These writes target station 3, port 3 (global port 15)
            # byte[2] = 0xBC = enables(0xF) | port_lo(1)
            cmd_base = bytes([0x03, _PEX8696_NT_BRIDGE, _PEX8696_NT_ENABLES])

            # Register 0x3AC = NT bridge setup
            self.plx.write_register(
                addr, _PEX8696_NT_BRIDGE, PlxReg.NT_BRIDGE, 0x01000000
            )
            # Register 0x384 = lane config upper (NT port)
            self.plx.write_register(
                addr, _PEX8696_NT_BRIDGE, PlxReg.LANE_CFG_HI, 0x00000000
            )
            # Register 0x380 = lane config lower (NT port)
            self.plx.write_register(
                addr, _PEX8696_NT_BRIDGE, PlxReg.LANE_CFG_LO, 0x10011100
            )

    def _configure_pex8647(self, mode: MultiHostMode) -> None:
        """Configure upstream PEX8647 switches for the given mode."""
        if mode == MultiHostMode.MODE_8_1:
            # 8:1 mode: swap primary/secondary host port, enable port merge
            stn2_reg234 = 0x9C040000  # bit 8 = 0 (secondary)
            stn0_reg234 = 0x9C040100  # bit 8 = 1 (primary)
            reg1dc = 0x0F882010       # bit 19 = 1 (port merge enabled)
        else:
            # 2:1 and 4:1 mode
            stn2_reg234 = 0x9C040100  # bit 8 = 1 (secondary)
            stn0_reg234 = 0x9C040000  # bit 8 = 0 (primary)
            reg1dc = 0x0F802010       # bit 19 = 0 (port merge disabled)

        for addr in PEX8647_ADDRS:
            log.info("PEX8647 0x%02X: mode %s", addr, mode.name)

            # Step 1: Station 2, port 0 — host port select
            self.plx.write_register(
                addr, _PEX8647_STN2_PORT0, PlxReg.HP_POWER_CTRL,
                stn2_reg234,
            )

            # Step 2: Station 0, port 0 — host port select + delay
            self.plx.write_register(
                addr, _PEX8647_STN0_PORT0, PlxReg.HP_POWER_CTRL,
                stn0_reg234,
            )
            time.sleep(self.MODE_SWITCH_DELAY_S)

            # Step 3: Station 0, port 0 — port merge control + delay
            self.plx.write_register(
                addr, _PEX8647_STN0_PORT0, PlxReg.PORT_MERGE,
                reg1dc,
            )
            time.sleep(self.MODE_SWITCH_DELAY_S)

    def set_mode(self, mode: MultiHostMode | int | str) -> None:
        """Switch the chassis to a new multi-host mode.

        Args:
            mode: Target mode — MultiHostMode enum, int (2/4/8),
                  or string ("2:1", "4:1", "8:1").
        """
        if isinstance(mode, str):
            ratio = int(mode.split(":")[0])
            mode = MultiHostMode(ratio)
        elif isinstance(mode, int) and not isinstance(mode, MultiHostMode):
            mode = MultiHostMode(mode)

        log.info("Switching to %s multi-host mode", mode.name)

        # Order of operations from firmware:
        # 1. Configure PEX8696 downstream lane partitioning
        self._configure_pex8696_lanes(mode)

        # 2. Configure PEX8696 NT bridge ports
        self._configure_pex8696_nt_bridge()

        # 3. Configure PEX8647 upstream switches
        self._configure_pex8647(mode)

        log.info("Multi-host mode switch to %s complete", mode.name)


# ---------------------------------------------------------------------------
# Top-level chassis controller
# ---------------------------------------------------------------------------

class C410X:
    """Top-level controller for the Dell C410X GPU expansion chassis.

    Combines slot power control and multi-host mode configuration
    into a single interface.
    """

    def __init__(
        self,
        i2c_bus: int = 3,
        *,
        dry_run: bool = False,
    ) -> None:
        """Open I2C bus and initialise controllers.

        Args:
            i2c_bus: Linux I2C bus number (default 3 for AST2050 engine 3).
            dry_run: If True, log all transactions but don't touch hardware.
        """
        self.plx = PlxI2C(i2c_bus, dry_run=dry_run)
        self.slots = SlotPowerController(self.plx)
        self.multihost = MultiHostController(self.plx)

    def close(self) -> None:
        self.plx.close()

    def __enter__(self) -> C410X:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- Convenience methods delegating to sub-controllers --

    def slot_power_on(self, slot_num: int) -> None:
        """Power on a single GPU slot (1-based)."""
        self.slots.power_on(SLOT_MAP[slot_num - 1])

    def slot_power_off(self, slot_num: int) -> None:
        """Power off a single GPU slot (1-based)."""
        self.slots.power_off(SLOT_MAP[slot_num - 1])

    def startup_all(self, present_mask: int = 0xFFFF) -> None:
        """Full 16-slot staggered power-on sequence."""
        self.slots.startup_all(present_mask)

    def shutdown_all(self) -> None:
        """Power off all 16 slots (not staggered)."""
        self.slots.shutdown_all()

    def set_multihost_mode(self, mode: MultiHostMode | int | str) -> None:
        """Switch multi-host fan-out mode (2:1, 4:1, or 8:1)."""
        self.multihost.set_mode(mode)

    def read_slot_status(self, slot_num: int) -> dict[str, object]:
        """Read current power/link status for a slot.

        Returns a dict with decoded register fields.
        """
        slot = SLOT_MAP[slot_num - 1]
        slot_ctrl = self.plx.read_register(
            slot.i2c_addr, slot.port_byte, PlxReg.SLOT_CTRL_STATUS
        )

        pic = (slot_ctrl >> 8) & 0x03
        pcc = bool(slot_ctrl & SLOT_CTRL_PCC)
        power_indicator = {0: "reserved", 1: "ON", 2: "blink", 3: "OFF"}
        return {
            "slot": slot_num,
            "switch": f"PEX8696 #{slot.switch_index} (0x{slot.i2c_addr:02X})",
            "station": slot.station,
            "raw_slot_ctrl": f"0x{slot_ctrl:08X}",
            "power_indicator": power_indicator.get(pic, "unknown"),
            "power_controller": "off" if pcc else "on",
        }

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["smbus2>=0.4"]
# ///
"""Dell C410X PEX PCIe switch I2C control library.

Implements the PLX 4-byte I2C command protocol for communicating with
PEX8696 (96-lane downstream) and PEX8647 (48-lane upstream) PCIe switches
on the Dell C410X GPU expansion chassis.

==========================================================================
 Source & References
==========================================================================

All register addresses, bit fields, I2C sequences, and timing values in
this file were reverse engineered from the Dell C410X BMC firmware:

  Firmware:    Avocent MergePoint embedded firmware v1.35
  Binary:      /sbin/fullfw (ARM 32-bit LE ELF, not stripped, 3983 symbols)
  Extracted:   backup/c410xbmc135.zip -> SquashFS -> /sbin/fullfw
  Decompiler:  Ghidra 11.3.1

The following analysis documents in this repository provide the detailed
reverse engineering evidence for every value used here:

  PEX-I2C-COMMANDS.md
    The master reference document. Contains the complete I2C protocol,
    register map, wire-level transaction traces, slot mapping tables,
    and pseudocode for all operations.

  analysis/i2c-transport.md
    Details of the PLX 4-byte I2C command encoding, the PI2CWriteRead()
    firmware function, ioctl structure, and bus/mux addressing.

  analysis/pex8696-hotplug.md
    Per-register analysis of the slot power on/off sequences, including
    the write-protect removal, slot control indicators, power controller
    pulse, and LED enable. Documents the firmware functions
    pex8696_un_protect_reg (0x2FC74), pex8696_slot_power_on_reg (0x2F7C4),
    pex8696_slot_power_ctrl (0x332AC), and all_slot_power_off_reg (0x2F188).

  analysis/pex-multihost.md
    Analysis of multi-host mode switching: PEX8696 lane partitioning
    (registers 0x380/0x384), PEX8647 host port selection (register 0x234),
    port merging (register 0x1DC), and NT bridge setup (register 0x3AC).

  analysis/power-sequencing.md
    The 4-phase staggered GPU power-on sequence, phase ordering, inrush
    current distribution strategy, and timing analysis.

  research/plxtools-register-map.md
    Cross-reference of discovered registers against plxtools PEX8696
    definitions and the PLX SDK RegDefs.c register database.

  research/pcie-hotplug-registers.md
    Mapping of firmware register accesses to PCIe Base Specification
    Chapter 6.7 (Hot-Plug) standard register definitions.

External references:
  https://github.com/mithro/plxtools
    PLX switch control tools with I2C backend and PEX8696 register YAML.
    The plxtools I2C backend uses a simpler 2-byte address protocol;
    the PEX8696/PEX8647 require the extended 4-byte command protocol
    implemented here (see PEX-I2C-COMMANDS.md section 3.5 for comparison).

  https://patchwork.kernel.org/patch/5000551/
    Linux kernel patch for PEX8xxx I2C slave driver that documents the
    same 4-byte command encoding used by the Dell firmware.

==========================================================================
 Usage
==========================================================================

    from c410x_pex import C410X

    chassis = C410X(i2c_bus=3)
    chassis.slot_power_on(4)           # Power on GPU slot 4
    chassis.startup_all()              # Full 16-slot staggered power-on
    chassis.shutdown_all()             # Power off all 16 GPU slots
    chassis.set_multihost_mode("4:1")  # Configure 4:1 fan-out mode

==========================================================================
 Hardware Overview
==========================================================================

The Dell C410X is a 3U 16-slot PCIe GPU expansion chassis with:
  - AST2050 BMC (ARM926EJ-S) running Avocent MergePoint firmware
  - 4x PEX8696 downstream switches (96-lane, 24-port, PCIe Gen2)
  - 2x PEX8647 upstream switches (48-lane, 3-port, PCIe Gen2)
  - 16 x16 PCIe GPU slots, 4 per PEX8696 switch
  - 8 iPass host connections via PEX8647 switches

All PEX switches are on I2C bus 3 of the AST2050, with no I2C mux.
The BMC controls slot power, hot-plug, and lane topology entirely
through I2C register writes to the PLX switches.

See: PEX-I2C-COMMANDS.md sections 1-2 for full hardware topology.
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


# ===========================================================================
# PLX I2C Command Protocol Constants
# ===========================================================================
#
# The PEX8696 and PEX8647 use the "PLX PEX8xxx I2C slave protocol" — a
# 4-byte command header that encodes the target station/port, byte enables,
# and register DWORD index.
#
# This is DIFFERENT from the simpler 2-byte address protocol used by smaller
# PLX switches (e.g. PEX8619) and by the plxtools I2C backend. The 4-byte
# protocol is necessary because the PEX8696 has 24 ports across 6 stations,
# requiring per-port addressing within a single I2C slave.
#
# Command format (PEX-I2C-COMMANDS.md section 3.1):
#
#   Byte [0]: Command type
#             0x03 = PLX_CMD_I2C_WRITE  (write 4 data bytes to register)
#             0x04 = PLX_CMD_I2C_READ   (read 4 data bytes from register)
#
#   Byte [1]: Station/Port selection
#             bits [7:1] = (station << 1) | (port >> 1)
#             bit  [0]   = 0 (always, for even ports)
#
#   Byte [2]: Byte enables + register address high + port low bit
#             bit  [7]   = port & 1  (low bit of port number)
#             bits [5:2] = byte enable mask (0xF = all 4 bytes)
#             bits [1:0] = register DWORD index bits [9:8]
#
#   Byte [3]: Register DWORD index bits [7:0]
#
# The register DWORD index = (byte[2] & 0x03) << 8 | byte[3].
# The register byte address = DWORD_index * 4.
#
# In the Dell C410X firmware, byte[2] is almost always 0x3C (byte enables =
# all 4 bytes, reg_hi = 0, port_low = 0), so the DWORD index is simply
# byte[3].
#
# Write transaction (PEX-I2C-COMMANDS.md section 3.2):
#   I2C bus: [START] [slave_addr+W] [cmd] [stn_port] [enables] [reg_lo]
#                                   [val0] [val1] [val2] [val3] [STOP]
#   Total: 8 bytes written (4-byte command + 4-byte LE value)
#
# Read transaction (PEX-I2C-COMMANDS.md section 3.3):
#   Phase 1: [START] [slave_addr+W] [cmd=0x04] [stn_port] [enables] [reg_lo]
#   Phase 2: [REPEATED START] [slave_addr+R] [val0] [val1] [val2] [val3] [STOP]
#   Total: write 4 bytes, read 4 bytes (little-endian value)
#
# Confirmed by Linux kernel PEX8xxx I2C driver patch:
#   https://patchwork.kernel.org/patch/5000551/
#
# See also: analysis/i2c-transport.md for decompilation of PI2CWriteRead()
# (firmware address 0x253C4) and PI2CMuxWriteRead() (0x256C4).

class PlxCmd(IntEnum):
    """PLX I2C command type bytes.

    Source: PEX-I2C-COMMANDS.md section 3.1
    Firmware: write_pex8696_register (0x2EAD4) uses 0x03,
              read_pex8696_register  (0x2EBF0) uses 0x04.
    """
    WRITE = 0x03  # PLX_CMD_I2C_WRITE
    READ = 0x04   # PLX_CMD_I2C_READ


# Default byte-enables mask: all 4 bytes enabled, reg_hi=0, port_lo=0.
# This is 0x3C = (0xF << 2) | 0x00, meaning byte enables = 1111 (all 4
# bytes) and the upper 2 bits of the register DWORD index are 0.
#
# The firmware almost always uses this value. The only exception is
# NT bridge port writes where port_lo=1 (odd port), giving 0xBC.
# Source: PEX-I2C-COMMANDS.md section 3.1
BYTE_ENABLES_ALL = 0x3C


# ===========================================================================
# PLX Register Definitions
# ===========================================================================
#
# All register addresses were extracted from the decompiled firmware
# functions. Each register entry below documents:
#   - The DWORD index (used in the PLX I2C command byte[3])
#   - The byte address (DWORD index * 4)
#   - The firmware function(s) that access it
#   - The PLX SDK name (from RegDefs.c Pci8500[] array) where known
#   - Whether it's a PCIe standard or PLX proprietary register
#
# Full register reference: PEX-I2C-COMMANDS.md section 4
# Cross-reference: research/plxtools-register-map.md
# PCIe spec mapping: research/pcie-hotplug-registers.md

class PlxReg(IntEnum):
    """PLX register DWORD indices used by the C410X firmware.

    Each value is a register DWORD index (byte_address / 4). The PLX I2C
    command encodes this in bytes [2:3] of the 4-byte command header.

    Source: PEX-I2C-COMMANDS.md section 4.1 (Complete Register Table)
    """

    # --- PCIe Standard Registers ---
    # These are defined by the PCIe Base Specification, located relative
    # to the PCIe Capability base (0x068 for PEX8696, confirmed by PLX
    # SDK RegDefs.c). See: research/pcie-hotplug-registers.md

    SLOT_CAP = 0x1F
    """Slot Capabilities register (byte addr 0x07C).

    PCIe Capability + 0x14.  PLX SDK name: "PCIe Cap: Slot Capabilities".

    Standard PCIe fields include ABP, PCP, MRLSP, AIP, PIP, HPS, HPC,
    SPLV, SPLS, EIP, PSN. However, PLX repurposes bit 18 (normally NCCS
    "No Command Completed Support", read-only per spec) as a **writable
    write-protect control** when accessed via I2C.

    Firmware function: pex8696_un_protect_reg (0x2FC74)
      - Reads this register, clears bit 18, writes it back
      - Must be done before modifying any VS1 registers (0x200+)

    Source: PEX-I2C-COMMANDS.md section 4.2, section 6.2
    Source: analysis/pex8696-hotplug.md "Register Unprotect Sequence"
    """

    SLOT_CTRL_STATUS = 0x20
    """Slot Control / Slot Status register (byte addr 0x080).

    PCIe Capability + 0x18.  PLX SDK name: "PCIe Cap: Slot Status | Slot Control".

    Key bit fields used by the firmware:
      bits [7:6]  AIC  - Attention Indicator Control
      bits [9:8]  PIC  - Power Indicator Control
                         00=reserved, 01=ON, 10=blink, 11=OFF
      bit  [10]   PCC  - Power Controller Control (0=on, 1=off)

    Firmware functions:
      pex8696_slot_power_on_reg  (0x2F7C4) - sets PIC=ON, clears PCC
      pex8696_slot_power_ctrl    (0x332AC) - sets PIC=OFF, sets PCC for power-off
      all_slot_power_off_reg     (0x2F188) - sets bits [10:8] = 0x7 (PIC=OFF, PCC=1)

    Source: PEX-I2C-COMMANDS.md sections 4.2, 6.3 Phase 1, 7.1
    Source: analysis/pex8696-hotplug.md "Slot Control Register Analysis"
    """

    # --- PLX Proprietary Registers ---
    # These are in the Vendor-Specific (VS1) configuration space, starting
    # at offset 0x200. They require write-protection removal (clearing
    # bit 18 of SLOT_CAP) before modification.
    # See: research/plxtools-register-map.md

    PORT_CTRL_MASK = 0x81
    """Port Control Mask register (byte addr 0x204).

    PLX VS1 area. Written during multi-host mode configuration.
    Firmware function: pex8696_multi_host_mode_reg_set (0x37420)

    Source: PEX-I2C-COMMANDS.md section 4.3
    """

    HP_LED_MRL = 0x8A
    """Hot-Plug LED / MRL Control register (byte addr 0x228).

    PLX proprietary hot-plug extension.

    Key bit field:
      bit [21]  MRL/LED enable - set during power-on, enables the
                hot-plug LED indicator for the slot.

    Firmware function: pex8696_slot_power_on_reg (0x2F7C4), Phase 3
      - Read-modify-write: sets bit 21

    Source: PEX-I2C-COMMANDS.md sections 4.3, 6.3 Phase 3
    Source: analysis/pex8696-hotplug.md "Phase 3: Enable Hot-Plug LED"
    """

    HP_POWER_CTRL = 0x8D
    """Hot-Plug Power Controller Control register (byte addr 0x234).

    PLX proprietary. This register controls the hardware power controller
    that actually switches power to the PCIe slot.

    Key bit field:
      bit [0]  Power controller pulse trigger. The firmware asserts this
               bit, waits 100ms, then de-asserts it. This triggers the
               PLX hardware to physically enable slot power.

    The 100ms pulse width is hardcoded in the firmware (10 ticks at
    10ms/tick in the Avocent RTOS scheduler).

    Firmware function: pex8696_slot_power_on_reg (0x2F7C4), Phase 2
      - Read, set bit 0, write (assert)
      - Sleep 100ms
      - Write with bit 0 cleared (de-assert)

    Also used by PEX8647 for host port selection in multi-host mode
    (register 0x234 on PEX8647, but with different bit meanings).

    Source: PEX-I2C-COMMANDS.md sections 4.3, 6.3 Phase 2
    Source: analysis/pex8696-hotplug.md "Phase 2: Pulse Power Controller"
    """

    PORT_MERGE = 0x77
    """Port Merging / Aggregation Control register (byte addr 0x1DC).

    PEX8647 only. Controls whether ports are merged for 8:1 multi-host mode.

    Key bit field:
      bit [19]  Port aggregation enable. When set, merges two 4-port
                groups into a single 8-port group, allowing one host
                to access 8 GPU slots.

    Firmware functions:
      pex8647_cfg_multi_host_8   (0x36DBC) - sets bit 19
      pex8647_cfg_multi_host_2_4 (0x36EF0) - clears bit 19

    Source: PEX-I2C-COMMANDS.md sections 4.3, 9.4, 9.7
    Source: analysis/pex-multihost.md "PEX8647 Port Merging"
    """

    LANE_CFG_LO = 0xE0
    """Port/Lane Configuration Lower register (byte addr 0x380).

    Controls lane partitioning in the PEX8696. Together with LANE_CFG_HI,
    determines how the 96 lanes are distributed among ports.

    Values per mode (PEX-I2C-COMMANDS.md section 9.7):
      2:1 mode: 0x11010000 (bits 8,12 clear)
      4:1 mode: 0x11011100 (bits 8,12 set)
      8:1 mode: 0x11011100 (same as 4:1; PEX8647 differs)

    Written to station 0, port 0 (upstream/config port).

    Firmware functions:
      pex8696_cfg_multi_host_2 (0x36BEC)
      pex8696_cfg_multi_host_4 (0x36CD4)

    Source: PEX-I2C-COMMANDS.md sections 4.3, 9.3
    Source: analysis/pex-multihost.md "PEX8696 Lane Configuration"
    """

    LANE_CFG_HI = 0xE1
    """Port/Lane Configuration Upper register (byte addr 0x384).

    Complementary to LANE_CFG_LO. The mode-differentiating bits (8 and 12)
    are set in the opposite register compared to LANE_CFG_LO.

    Values per mode (PEX-I2C-COMMANDS.md section 9.7):
      2:1 mode: 0x00101100 (bits 8,12 set)
      4:1 mode: 0x00100000 (bits 8,12 clear)
      8:1 mode: 0x00100000 (same as 4:1)

    Source: PEX-I2C-COMMANDS.md sections 4.3, 9.3
    """

    NT_BRIDGE = 0xEB
    """NT Bridge Setup register (byte addr 0x3AC).

    Configures the Non-Transparent Bridge port (global port 15) on
    the PEX8696. Written during multi-host mode switching.

    Written to station 3, port 3 (the NT bridge port), which requires
    byte[2] = 0xBC (port_lo=1 for odd port number).

    Firmware function: pex8696_multi_host_mode_reg_set (0x37420)

    Source: PEX-I2C-COMMANDS.md section 9.5
    Source: analysis/pex-multihost.md "NT Bridge Setup"
    """

    SERDES_EQ1 = 0x2E4
    """SerDes Equalization Coefficient 1 register (byte addr 0xB90).

    PLX SerDes PHY configuration. Written per-port during multi-host
    mode setup to re-equalize the high-speed serial links after
    changing the lane configuration.

    Firmware function: pex8696_multi_host_mode_reg_set (0x37420)

    Source: PEX-I2C-COMMANDS.md section 9.6
    """

    SERDES_EQ2 = 0x2E7
    """SerDes Equalization Coefficient 2 register (byte addr 0xB9C).
    See SERDES_EQ1 for context. Source: PEX-I2C-COMMANDS.md section 9.6
    """

    SERDES_DEEMPH1 = 0x2E9
    """SerDes De-emphasis 1 register (byte addr 0xBA4).
    See SERDES_EQ1 for context. Source: PEX-I2C-COMMANDS.md section 9.6
    """

    SERDES_DEEMPH2 = 0x2EA
    """SerDes De-emphasis 2 register (byte addr 0xBA8).
    See SERDES_EQ1 for context. Source: PEX-I2C-COMMANDS.md section 9.6
    """


# ===========================================================================
# Bit-Field Constants
# ===========================================================================
#
# These constants define the specific bits manipulated by the firmware
# in each register. Values were extracted from the Ghidra decompilation
# of the firmware functions listed below.
#
# Source: analysis/pex8696-hotplug.md, analysis/decompiled/*.c

# --- Register 0x07C (SLOT_CAP) ---
# Firmware: pex8696_un_protect_reg (0x2FC74)
# The firmware reads the register, clears bit 18, and writes it back.
# Decompiled code: val = plx_read(..., 0x1F); val &= ~(1<<18); plx_write(..., 0x1F, val)
# Source: PEX-I2C-COMMANDS.md section 6.2
WRITE_PROTECT_BIT = 1 << 18

# --- Register 0x080 (SLOT_CTRL_STATUS) ---
# Firmware: pex8696_slot_power_on_reg (0x2F7C4), pex8696_slot_power_ctrl (0x332AC)
#
# Power Indicator Control (PIC) field, bits [9:8]:
#   00 = reserved
#   01 = ON   (green LED, slot powered)
#   10 = blink (attention)
#   11 = OFF  (slot unpowered)
# Source: PCIe Base Spec Chapter 6.7, PEX-I2C-COMMANDS.md section 4.2
SLOT_CTRL_PIC_MASK = 0x0300
SLOT_CTRL_PIC_ON = 0x0100    # PIC = 01 (ON)
SLOT_CTRL_PIC_OFF = 0x0300   # PIC = 11 (OFF)

# Attention Indicator Control (AIC) field, bits [7:6]:
SLOT_CTRL_AIC_MASK = 0x00C0

# Power Controller Control (PCC), bit [10]:
#   0 = power on
#   1 = power off
# Source: PCIe Base Spec Table 7-21
SLOT_CTRL_PCC = 0x0400

# Combined power-off bits: PIC=OFF (0x0300) | PCC=off (0x0400)
# The firmware ORs these into the register value to power off a slot.
# Firmware: all_slot_power_off_reg (0x2F188) does: val |= 0x0700
# Source: PEX-I2C-COMMANDS.md section 7.1
SLOT_CTRL_POWER_OFF_BITS = 0x0700

# --- Register 0x234 (HP_POWER_CTRL) ---
# Firmware: pex8696_slot_power_on_reg (0x2F7C4), Phase 2
# The firmware asserts bit 0, sleeps 100ms, then de-asserts bit 0.
# Source: PEX-I2C-COMMANDS.md section 6.3 Phase 2
HP_POWER_PULSE_BIT = 0x01

# --- Register 0x228 (HP_LED_MRL) ---
# Firmware: pex8696_slot_power_on_reg (0x2F7C4), Phase 3
# Read-modify-write: sets bit 21 to enable the hot-plug LED.
# Source: PEX-I2C-COMMANDS.md section 6.3 Phase 3
HP_LED_ENABLE_BIT = 1 << 21


# ===========================================================================
# Dell C410X Hardware Topology
# ===========================================================================
#
# I2C Bus Configuration (PEX-I2C-COMMANDS.md section 2.1):
#   All PEX switches are on I2C bus 3 (AST2050 engine 3).
#   No I2C mux is used on this bus.
#   The firmware encodes bus+mux as 0xF3: lower nibble 0x3 = bus 3,
#   upper nibble 0xF = mux channel 15 (bypass/no mux).
#   Kernel driver: /dev/aess_i2cdrv, ioctl 0xC010B702
#   Source: analysis/i2c-transport.md "I2C Bus Architecture"
#
# I2C Address Map (PEX-I2C-COMMANDS.md section 2.2):
#   All addresses are in GBT (General Bus Target) 8-bit format,
#   which is the 7-bit address left-shifted by 1. The Linux kernel's
#   I2C subsystem expects 7-bit addresses, so we pass i2c_addr >> 1
#   to smbus2's i2c_msg. However, when using i2c_msg directly (as we
#   do), the library handles this internally — we pass the 7-bit address.
#
#   Note: The firmware uses 8-bit GBT addresses (0x30 = 7-bit 0x18),
#   but smbus2.i2c_msg expects 7-bit addresses. We store 7-bit here
#   and document both forms.
#
# Physical topology (PEX-I2C-COMMANDS.md section 2.3):
#
#                     iPass Cables (to hosts)
#                      |   |   |   |
#               +------+---+---+------+
#               | PEX8647 #0 (0x6A)   |  Upstream switches
#               | PEX8647 #1 (0x68)   |  (host-side links)
#               +------+---+---+------+
#                      |   |   |
#               +------+---+---+------+
#               | PEX8696 #0 (0x18)   |  Downstream switches
#               | PEX8696 #1 (0x1A)   |  (GPU-side links)
#               | PEX8696 #2 (0x19)   |  4 GPU slots per switch
#               | PEX8696 #3 (0x1B)   |
#               +------+---+---+------+
#                 |  |  |  |  |  |  |
#                GPU slots 1-16

# PEX8696 downstream switch I2C addresses.
# Index 0-3 = switch #0-#3.
# 7-bit addresses used by smbus2.i2c_msg.
#
# Source: PEX-I2C-COMMANDS.md section 2.2
# Firmware: resources.md section 4.3 "PEX 8696 I2C Addresses"
#
# | Switch | 8-bit GBT | 7-bit  | GPU Slots          |
# |--------|-----------|--------|--------------------|
# | #0     | 0x30      | 0x18   | 1, 2, 15, 16       |
# | #1     | 0x34      | 0x1A   | 3, 4, 13, 14       |
# | #2     | 0x32      | 0x19   | 5, 6, 11, 12       |
# | #3     | 0x36      | 0x1B   | 7, 8, 9, 10        |
PEX8696_ADDRS = [0x18, 0x1A, 0x19, 0x1B]

# PEX8647 upstream switch I2C addresses.
# 7-bit addresses.
#
# Source: PEX-I2C-COMMANDS.md section 2.2
# Firmware: discovered from pex8647_cfg_multi_host_8 (0x36DBC) and
#           pex8647_cfg_multi_host_2_4 (0x36EF0) decompilations.
#
# | Switch | 8-bit GBT | 7-bit  | Function           |
# |--------|-----------|--------|--------------------|
# | #0     | 0xD4      | 0x6A   | Hosts 0-1          |
# | #1     | 0xD0      | 0x68   | Hosts 2-3          |
PEX8647_ADDRS = [0x6A, 0x68]


@dataclass(frozen=True)
class SlotInfo:
    """Mapping from a GPU slot number to its PEX8696 switch port.

    Each of the 16 GPU slots is connected to a specific port on one of
    four PEX8696 switches. The slot-to-switch mapping was extracted from
    two 16-byte lookup tables in the firmware ROM:

      I2C address table at ROM 0xF7B06: [30 30 34 34 32 32 36 36 36 36 32 32 34 34 30 30]
      Port byte table at ROM 0xF7B16:   [04 0A 04 0A 04 0A 02 08 04 0A 02 08 02 08 02 08]

    These tables are referenced by three copies of get_PEX8696_addr_port()
    at firmware addresses 0x2E66C, 0x317E4, 0x37F7C.

    The port_byte is the pre-encoded PLX I2C command byte[1] value:
      port_byte = (station << 1) | (port >> 1)

    Since all slots use even port numbers (port_lo = 0), the port_byte
    directly encodes just the station number shifted left by 1.

    Source: PEX-I2C-COMMANDS.md section 5.1 (Lookup Tables)
    Source: analysis/i2c-transport.md "Slot-to-I2C-Address Mapping"
    """
    slot_num: int       # 1-based slot number (1-16)
    i2c_addr: int       # 7-bit I2C address of the PEX8696 switch
    port_byte: int      # Pre-encoded station/port byte for PLX I2C command

    @property
    def switch_index(self) -> int:
        """Which PEX8696 switch (0-3) this slot belongs to."""
        return PEX8696_ADDRS.index(self.i2c_addr)

    @property
    def station(self) -> int:
        """PLX station number decoded from port_byte.

        The PEX8696 has 6 stations of 4 ports each (24 ports total).
        The station number is encoded in port_byte bits [7:1].
        """
        return self.port_byte >> 1

    def __str__(self) -> str:
        return (
            f"Slot {self.slot_num}: switch #{self.switch_index} "
            f"(0x{self.i2c_addr:02X}), station {self.station}"
        )


# Slot mapping table: firmware ROM addresses 0xF7B06 (I2C addrs) and
# 0xF7B16 (port bytes). Three copies of get_PEX8696_addr_port() at
# 0x2E66C, 0x317E4, 0x37F7C all reference identical table data.
#
# Index = slot_index (0-15), value = (7-bit i2c_addr, port_byte).
#
# The firmware ROM stores 8-bit GBT addresses (0x30, 0x32, etc.) but
# we convert to 7-bit here for smbus2 compatibility.
#
# Source: PEX-I2C-COMMANDS.md section 5.2 (Complete Slot Mapping)
# Source: Appendix A.5 (Slot Mapping Table)
_SLOT_MAP_RAW: list[tuple[int, int]] = [
    (0x18, 0x04),  # Slot 1:  Switch #0, station 2, port 0
    (0x18, 0x0A),  # Slot 2:  Switch #0, station 5, port 0
    (0x1A, 0x04),  # Slot 3:  Switch #1, station 2, port 0
    (0x1A, 0x0A),  # Slot 4:  Switch #1, station 5, port 0
    (0x19, 0x04),  # Slot 5:  Switch #2, station 2, port 0
    (0x19, 0x0A),  # Slot 6:  Switch #2, station 5, port 0
    (0x1B, 0x02),  # Slot 7:  Switch #3, station 1, port 0
    (0x1B, 0x08),  # Slot 8:  Switch #3, station 4, port 0
    (0x1B, 0x04),  # Slot 9:  Switch #3, station 2, port 0
    (0x1B, 0x0A),  # Slot 10: Switch #3, station 5, port 0
    (0x19, 0x02),  # Slot 11: Switch #2, station 1, port 0
    (0x19, 0x08),  # Slot 12: Switch #2, station 4, port 0
    (0x1A, 0x02),  # Slot 13: Switch #1, station 1, port 0
    (0x1A, 0x08),  # Slot 14: Switch #1, station 4, port 0
    (0x18, 0x02),  # Slot 15: Switch #0, station 1, port 0
    (0x18, 0x08),  # Slot 16: Switch #0, station 4, port 0
]

SLOT_MAP: list[SlotInfo] = [
    SlotInfo(slot_num=i + 1, i2c_addr=addr, port_byte=port)
    for i, (addr, port) in enumerate(_SLOT_MAP_RAW)
]

# Staggered power-on phases.
#
# The firmware powers slots in reverse numerical order to distribute
# inrush current: phase 1 = slots 4,8,12,16; phase 4 = slots 1,5,9,13.
# Each phase activates exactly one slot per PEX8696 switch (one per
# I2C address), preventing any single switch from handling simultaneous
# inrush on multiple ports.
#
# Firmware: Start_GPU_Power_Sequence (0x33AE8)
#   calls gpu_power_on_4_8_12_16, gpu_power_on_3_7_11_15,
#         gpu_power_on_2_6_10_14, gpu_power_on_1_5_9_13
#
# Source: PEX-I2C-COMMANDS.md section 8.1 (Phase Ordering)
# Source: analysis/power-sequencing.md
POWER_ON_PHASES: list[list[int]] = [
    [3, 7, 11, 15],   # Phase 1: slots 4, 8, 12, 16 (one per switch)
    [2, 6, 10, 14],   # Phase 2: slots 3, 7, 11, 15
    [1, 5, 9, 13],    # Phase 3: slots 2, 6, 10, 14
    [0, 4, 8, 12],    # Phase 4: slots 1, 5, 9, 13
]


# ===========================================================================
# PLX I2C Transport Layer
# ===========================================================================

class PlxI2C:
    """Low-level PLX 4-byte I2C command protocol implementation.

    This class handles the wire-level encoding/decoding for communicating
    with PEX8696 and PEX8647 switches over Linux I2C (/dev/i2c-N).

    It uses smbus2's i2c_rdwr() method for raw I2C message transfer,
    rather than SMBus read/write_block_data, because the PLX protocol
    doesn't follow the SMBus register-address convention. The entire
    4-byte (read) or 8-byte (write) payload is sent as a single I2C
    WRITE message, and reads use a combined WRITE+READ (repeated start).

    The original firmware uses the Avocent aess_i2cdrv kernel module
    (ioctl 0xC010B702) on /dev/aess_i2cdrv. On a modern Linux system
    (e.g. OpenBMC), the standard I2C character device (/dev/i2c-N)
    provides equivalent functionality via the I2C_RDWR ioctl, which
    smbus2.i2c_rdwr wraps.

    Source: analysis/i2c-transport.md
    Firmware: PI2CWriteRead (0x253C4), PI2CMuxWriteRead (0x256C4)
    """

    def __init__(self, bus: int, *, dry_run: bool = False) -> None:
        """Open an I2C bus for PLX switch communication.

        Args:
            bus: Linux I2C bus number (e.g. 3 for /dev/i2c-3).
                 On the Dell C410X AST2050, the PEX switches are on bus 3.
                 Source: PEX-I2C-COMMANDS.md section 2.1
            dry_run: If True, log all transactions but don't touch hardware.
                     Read operations return 0x00000000 so read-modify-write
                     sequences still execute correctly for testing.
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

        Encodes the command type, target station/port, byte enables,
        and register DWORD index into the PLX wire format.

        See module-level documentation for the full byte layout, or
        PEX-I2C-COMMANDS.md section 3.1 for the specification.

        Args:
            cmd_type: PlxCmd.WRITE (0x03) or PlxCmd.READ (0x04).
            port_byte: Station/port encoding byte. This is the pre-encoded
                       value from the slot mapping table (SLOT_MAP), where
                       port_byte = (station << 1) | (port >> 1).
            dword_idx: Register DWORD index (register_byte_address / 4).
                       For the C410X firmware, this is always <= 0xFF
                       (10-bit index with upper 2 bits = 0).
            enables: Combined byte-enable and register-high bits.
                     Default 0x3C = all 4 bytes enabled, reg_hi=0, port_lo=0.
                     Use 0xBC for odd-numbered ports (NT bridge).

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

        Sends 8 bytes as a single I2C WRITE message:
          bytes [0-3] = PLX command header (cmd=0x03, port, enables, reg)
          bytes [4-7] = 32-bit register value in little-endian byte order

        Wire format (PEX-I2C-COMMANDS.md section 3.2):
          [START] [addr+W] [03] [port] [3C] [reg] [v0] [v1] [v2] [v3] [STOP]

        Firmware equivalent: write_pex8696_register (0x2EAD4)
          calls PI2CWriteRead(bus_mux, slave_addr, 8, &buffer, 0, 0, 0)

        Args:
            i2c_addr: 7-bit I2C address of the PLX switch.
            port_byte: Station/port encoding for the target port.
            dword_idx: Register DWORD index (PlxReg enum value).
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

        Uses a combined write-then-read (I2C repeated start):
          Phase 1: write 4-byte command (cmd=0x04, port, enables, reg)
          Phase 2: read 4 bytes (32-bit value, little-endian)

        Wire format (PEX-I2C-COMMANDS.md section 3.3):
          [START] [addr+W] [04] [port] [3C] [reg]
          [RS]    [addr+R] [v0] [v1] [v2] [v3] [STOP]

        Firmware equivalent: read_pex8696_register (0x2EBF0)
          calls PI2CWriteRead(bus_mux, slave_addr, 4, &cmd, 4, &result, 0)

        Args:
            i2c_addr: 7-bit I2C address of the PLX switch.
            port_byte: Station/port encoding for the target port.
            dword_idx: Register DWORD index (PlxReg enum value).

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

        This is the most common firmware pattern: read the current value,
        modify specific bits, write it back. Used for write-protect removal,
        slot control indicator updates, and LED enable.

        Note: "atomic" here means no other I2C master should interleave
        between the read and write. On the C410X, the BMC is the only
        I2C master on bus 3, so this is safe. The firmware protects
        concurrent access with a semaphore (_lx_SemaphoreGet with 20-tick
        timeout). See: analysis/i2c-transport.md "Semaphore Protection".

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


# ===========================================================================
# Slot Power Control
# ===========================================================================

class SlotPowerController:
    """Controls GPU slot power via PEX8696 I2C register writes.

    Implements the exact power-on/off sequences reverse engineered from
    the Dell C410X Avocent MergePoint firmware v1.35.

    Power-on sequence per slot (9 I2C transactions + 100ms delay):
      1. Unprotect: R/W register 0x07C (clear bit 18)           [2 txns]
      2. Indicators: R/W register 0x080 (PIC=ON, PCC=0)         [2 txns]
      3. Power pulse: R/W/W register 0x234 (assert, wait, deassert) [3 txns]
      4. LED enable: R/W register 0x228 (set bit 21)             [2 txns]

    Power-off per slot (2 I2C transactions, no delays):
      1. R/W register 0x080 (PIC=OFF, PCC=1)                    [2 txns]

    Full documentation: PEX-I2C-COMMANDS.md sections 6-8
    Detailed analysis: analysis/pex8696-hotplug.md
    Timing analysis: analysis/power-sequencing.md
    """

    # Delay between asserting and de-asserting the power controller pulse.
    # The firmware uses 10 ticks at 10ms/tick = 100ms.
    # Firmware: pex8696_slot_power_on_reg (0x2F7C4), _lx_TaskDelay(10)
    # Source: PEX-I2C-COMMANDS.md section 6.3 Phase 2
    POWER_PULSE_DELAY_S = 0.1

    def __init__(self, plx: PlxI2C) -> None:
        self.plx = plx

    def _unprotect(self, slot: SlotInfo) -> None:
        """Remove write protection for a slot's PEX8696 port.

        Read-modify-write on register 0x07C (Slot Capabilities):
        clear bit 18 (PLX write-protect enable).

        This must be done before writing any VS1 registers (0x200+)
        including the hot-plug and lane configuration registers.

        Firmware: pex8696_un_protect_reg at 0x2FC74
        Source: PEX-I2C-COMMANDS.md section 6.2
        """
        log.info("Unprotect %s", slot)
        self.plx.read_modify_write(
            slot.i2c_addr, slot.port_byte, PlxReg.SLOT_CAP,
            clear_bits=WRITE_PROTECT_BIT,
        )

    def power_on(self, slot: SlotInfo) -> None:
        """Power on a single GPU slot.

        Executes the complete 4-step power-on sequence:

        Step 1 — Write-protect removal (register 0x07C, DWORD 0x1F):
          Read register, clear bit 18, write back.
          Firmware: pex8696_un_protect_reg (0x2FC74)
          Source: PEX-I2C-COMMANDS.md section 6.2

        Step 2 — Set slot control indicators (register 0x080, DWORD 0x20):
          Read register, set PIC=ON (bits [9:8] = 01), clear PCC (bit 10 = 0).
          This tells the PCIe subsystem the slot is powered.
          Firmware: pex8696_slot_power_on_reg (0x2F7C4)
          Source: PEX-I2C-COMMANDS.md section 6.3 Phase 1

        Step 3 — Pulse hardware power controller (register 0x234, DWORD 0x8D):
          Read register, set bit 0 (assert), write.
          Sleep 100ms.
          Clear bit 0 (de-assert), write.
          This triggers the PLX hardware to physically enable slot power.
          Firmware: pex8696_slot_power_on_reg (0x2F7C4)
          Source: PEX-I2C-COMMANDS.md section 6.3 Phase 2

        Step 4 — Enable hot-plug LED (register 0x228, DWORD 0x8A):
          Read register, set bit 21, write back.
          Enables the hot-plug LED indicator for the slot.
          Firmware: pex8696_slot_power_on_reg (0x2F7C4)
          Source: PEX-I2C-COMMANDS.md section 6.3 Phase 3

        Wire-level example for slot 4:
          See PEX-I2C-COMMANDS.md section 6.4

        Total: 9 I2C transactions (4 reads + 5 writes) + 100ms delay.
        Source: PEX-I2C-COMMANDS.md section 6.5
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
        self.plx.write_register(
            slot.i2c_addr, slot.port_byte, PlxReg.HP_POWER_CTRL,
            val | HP_POWER_PULSE_BIT,
        )
        time.sleep(self.POWER_PULSE_DELAY_S)
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

        Sets power indicator = OFF and PCC = 1 (attention ON) in
        register 0x080 (Slot Control). This is the only register
        modified during power-off — no power controller pulse,
        no LED changes, no write-protect removal needed.

        Firmware: pex8696_slot_power_ctrl (0x332AC) power-off path
          Read reg 0x080, OR in 0x0700 (PIC=OFF + PCC=1), write back.

        Source: PEX-I2C-COMMANDS.md section 7.1
        Source: analysis/pex8696-hotplug.md "Power-Off Sequence"

        Total: 2 I2C transactions (1 read + 1 write), no delays.
        """
        log.info("Power OFF %s", slot)
        self.plx.read_modify_write(
            slot.i2c_addr, slot.port_byte, PlxReg.SLOT_CTRL_STATUS,
            set_bits=SLOT_CTRL_POWER_OFF_BITS,
        )

    def power_off_all(self) -> None:
        """Power off all 16 GPU slots (not staggered).

        Uses the read-modify-write approach: for each of 16 slots, reads
        register 0x080 and ORs in PIC=OFF + PCC=1.

        Firmware: all_slot_power_off_reg (0x2F188)
        Source: PEX-I2C-COMMANDS.md section 7.2

        Total: 32 I2C transactions (16 reads + 16 writes), no delays.

        Note: The firmware also has a more efficient bulk-write method
        (pex8696_all_slot_off at 0x375B8) that uses 16 write-only
        transactions with pre-built values. This implementation uses the
        read-modify-write approach for safety, as it preserves other
        register bits that may have been set by the hardware.
        See: PEX-I2C-COMMANDS.md section 7.3 for the bulk method.
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
        switch per phase to distribute inrush current across the chassis
        power system.

        Phase ordering (reverse numerical, from firmware):
          Phase 1: slots 4, 8, 12, 16  (indices 3, 7, 11, 15)
          Phase 2: slots 3, 7, 11, 15  (indices 2, 6, 10, 14)
          Phase 3: slots 2, 6, 10, 14  (indices 1, 5, 9, 13)
          Phase 4: slots 1, 5, 9, 13   (indices 0, 4, 8, 12)

        Each phase hits exactly one slot per PEX8696 switch (one per I2C
        address: 0x18, 0x19, 0x1A, 0x1B), ensuring no switch handles
        simultaneous inrush from multiple slots.

        Firmware: Start_GPU_Power_Sequence (0x33AE8)
          calls gpu_power_on_4_8_12_16, gpu_power_on_3_7_11_15,
                gpu_power_on_2_6_10_14, gpu_power_on_1_5_9_13

        Source: PEX-I2C-COMMANDS.md section 8.1 (Phase Ordering)
        Source: analysis/power-sequencing.md

        Total for 16 slots: 144 I2C transactions (64 reads + 80 writes)
                           + 16 x 100ms delays = ~2.0 seconds
        Source: PEX-I2C-COMMANDS.md section 8.5

        Args:
            present_mask: 16-bit mask of physically present GPUs.
                          Bit 0 = slot 1, bit 15 = slot 16.
                          Default 0xFFFF = all present.
                          The firmware reads presence from PCA9555 GPIO
                          expanders (I2C bus 6, address 0x20).
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
        """Power off all 16 GPU slots (not staggered).

        Power-off does not need staggering because there is no inrush
        current concern when removing power.

        Source: PEX-I2C-COMMANDS.md section 8.8
        """
        self.power_off_all()


# ===========================================================================
# Multi-Host Mode Configuration
# ===========================================================================

class MultiHostMode(IntEnum):
    """Supported host-to-GPU fan-out ratios.

    The Dell C410X connects up to 8 host servers to 16 GPU slots via
    iPass cables. The fan-out ratio determines how many GPU slots each
    host can access:

      2:1 — 8 hosts, 2 GPU slots each
      4:1 — 4 hosts, 4 GPU slots each (factory default)
      8:1 — 2 hosts, 8 GPU slots each

    Mode switching is performed via IPMI OEM command (NetFn 0x34, Cmd 0xC8)
    which triggers the multi-host configuration functions.

    Source: PEX-I2C-COMMANDS.md section 9.1
    Source: dell-c410x-firmware/ANALYSIS.md "Port Mapping"
    """
    MODE_2_1 = 2
    MODE_4_1 = 4
    MODE_8_1 = 8


# PEX8647 station/port bytes for multi-host configuration.
# These target the upstream configuration ports on the PEX8647.
# Source: analysis/pex-multihost.md, decompiled pex8647_cfg_multi_host_* functions
_PEX8647_STN0_PORT0 = 0x00  # Station 0, port 0
_PEX8647_STN2_PORT0 = 0x04  # Station 2, port 0

# PEX8696 station/port bytes for configuration port and NT bridge.
# Station 0, port 0 is the upstream/configuration port.
# Station 3, port 3 (global port 15) is the NT bridge port.
# Source: PEX-I2C-COMMANDS.md section 9.5
_PEX8696_CFG_PORT = 0x00    # Station 0, port 0 (upstream/config)
_PEX8696_NT_BRIDGE = 0x07   # Station 3, port 1 (port_byte encoding)

# For the NT bridge port (global port 15 = station 3, port 3), the
# port number is odd (3), so bit 7 of byte[2] must be set:
#   byte[2] = (port_lo << 7) | (enables << 2) | reg_hi
#           = (1 << 7) | (0xF << 2) | 0
#           = 0x80 | 0x3C | 0x00 = 0xBC
# Source: PEX-I2C-COMMANDS.md section 9.5 (note about byte[2] = 0xBC)
_PEX8696_NT_ENABLES = 0xBC


class MultiHostController:
    """Configures PEX8696/PEX8647 lane topology for multi-host modes.

    Mode switching involves three stages:
      1. PEX8696 lane partitioning (registers 0x380/0x384 on all 4 switches)
      2. PEX8696 NT bridge setup (registers 0x3AC/0x384/0x380 on port 15)
      3. PEX8647 host port selection and port merging (registers 0x234/0x1DC)

    Key insight from the reverse engineering: 4:1 and 8:1 modes share
    identical PEX8696 configuration — they differ ONLY in the PEX8647
    upstream switches. Specifically, 8:1 mode sets bit 19 of register
    0x1DC (port merge/aggregation enable) on the PEX8647, which merges
    two 4-port groups into a single 8-port group.

    Mode-differentiating bits summary (PEX-I2C-COMMANDS.md section 9.7):

      | Switch  | Register | Bit | 2:1 | 4:1 | 8:1 | Description           |
      |---------|----------|-----|-----|-----|-----|-----------------------|
      | PEX8696 | 0x384    | 8   | 1   | 0   | 0   | Port partition ctrl   |
      | PEX8696 | 0x384    | 12  | 1   | 0   | 0   | Lane assignment ctrl  |
      | PEX8696 | 0x380    | 8   | 0   | 1   | 1   | Port partition (comp) |
      | PEX8696 | 0x380    | 12  | 0   | 1   | 1   | Lane assignment (comp)|
      | PEX8647 | 0x234/s0 | 8   | 0   | 0   | 1   | Primary host port     |
      | PEX8647 | 0x234/s2 | 8   | 1   | 1   | 0   | Secondary host port   |
      | PEX8647 | 0x1DC    | 19  | 0   | 0   | 1   | Port merge enable     |

    Firmware functions:
      multi_host_mode_set           (0x380BC) — orchestrator
      pex8696_cfg_multi_host_2      (0x36BEC) — PEX8696 2:1 lane config
      pex8696_cfg_multi_host_4      (0x36CD4) — PEX8696 4:1/8:1 lane config
      pex8696_multi_host_mode_reg_set (0x37420) — NT bridge + SerDes setup
      pex8647_cfg_multi_host_8      (0x36DBC) — PEX8647 8:1 config
      pex8647_cfg_multi_host_2_4    (0x36EF0) — PEX8647 2:1/4:1 config

    Source: PEX-I2C-COMMANDS.md section 9
    Source: analysis/pex-multihost.md
    """

    # Delays between PEX8647 register writes.
    # Firmware uses 20 ticks at 10ms/tick = 200ms.
    # Source: PEX-I2C-COMMANDS.md section 9.8
    MODE_SWITCH_DELAY_S = 0.2

    def __init__(self, plx: PlxI2C) -> None:
        self.plx = plx

    def _configure_pex8696_lanes(self, mode: MultiHostMode) -> None:
        """Write lane configuration registers to all 4 PEX8696 switches.

        Registers 0x380 (LANE_CFG_LO) and 0x384 (LANE_CFG_HI) control
        the PEX8696's internal crossbar routing between upstream and
        downstream ports. The mode-differentiating bits (8 and 12) are
        complementary between the two registers.

        Written to station 0, port 0 (the upstream/configuration port)
        on each switch.

        Wire-level transactions (PEX-I2C-COMMANDS.md section 9.3):

        2:1 mode:
          WRITE 0x384: [03] [00] [3C] [E1] [00] [11] [10] [00]  val=0x00101100
          WRITE 0x380: [03] [00] [3C] [E0] [00] [00] [01] [11]  val=0x11010000

        4:1 / 8:1 mode:
          WRITE 0x384: [03] [00] [3C] [E1] [00] [00] [10] [00]  val=0x00100000
          WRITE 0x380: [03] [00] [3C] [E0] [00] [11] [01] [11]  val=0x11011100

        Firmware: pex8696_cfg_multi_host_2 (0x36BEC) for 2:1 mode,
                  pex8696_cfg_multi_host_4 (0x36CD4) for 4:1/8:1 mode.
        """
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

        The NT bridge is at station 3, port 3 (an odd-numbered port).
        Because port 3 has port_lo = 1, byte[2] of the PLX command must
        include the port_lo bit: byte[2] = 0xBC instead of 0x3C.

        Three registers are written to the NT bridge port:
          1. Register 0x3AC (NT_BRIDGE):    value 0x01000000
          2. Register 0x384 (LANE_CFG_HI):  value 0x00000000
          3. Register 0x380 (LANE_CFG_LO):  value 0x10011100

        Wire-level transactions (PEX-I2C-COMMANDS.md section 9.5):
          WRITE 0x3AC: [03] [07] [BC] [EB] [00] [00] [00] [01]
          WRITE 0x384: [03] [07] [BC] [E1] [00] [00] [00] [00]
          WRITE 0x380: [03] [07] [BC] [E0] [00] [11] [01] [10]

        Note byte[2] = 0xBC confirming odd port (port_lo=1, bit 7 set).

        Firmware: pex8696_multi_host_mode_reg_set (0x37420)
        """
        for addr in PEX8696_ADDRS:
            log.info("PEX8696 0x%02X: NT bridge setup", addr)
            self.plx.write_register(
                addr, _PEX8696_NT_BRIDGE, PlxReg.NT_BRIDGE, 0x01000000
            )
            self.plx.write_register(
                addr, _PEX8696_NT_BRIDGE, PlxReg.LANE_CFG_HI, 0x00000000
            )
            self.plx.write_register(
                addr, _PEX8696_NT_BRIDGE, PlxReg.LANE_CFG_LO, 0x10011100
            )

    def _configure_pex8647(self, mode: MultiHostMode) -> None:
        """Configure upstream PEX8647 switches for the given mode.

        Three registers are written to each PEX8647, with 200ms delays:

        Step 1: Register 0x234 on station 2 — secondary host port select
        Step 2: Register 0x234 on station 0 — primary host port select [+200ms]
        Step 3: Register 0x1DC on station 0 — port merge control [+200ms]

        For 8:1 mode, bit 8 of reg 0x234 is swapped between stations
        (primary gets bit 8 = 1, secondary gets bit 8 = 0), and bit 19
        of reg 0x1DC is set to enable port merging.

        Wire-level transactions for 2:1/4:1 (PEX-I2C-COMMANDS.md section 9.4):
          WRITE 0x234/stn2: [03] [04] [3C] [8D] [00] [01] [04] [9C]  val=0x9C040100
          WRITE 0x234/stn0: [03] [00] [3C] [8D] [00] [00] [04] [9C]  val=0x9C040000
          DELAY 200ms
          WRITE 0x1DC/stn0: [03] [00] [3C] [77] [10] [20] [80] [0F]  val=0x0F802010
          DELAY 200ms

        Wire-level transactions for 8:1:
          WRITE 0x234/stn2: [03] [04] [3C] [8D] [00] [00] [04] [9C]  val=0x9C040000
          WRITE 0x234/stn0: [03] [00] [3C] [8D] [00] [01] [04] [9C]  val=0x9C040100
          DELAY 200ms
          WRITE 0x1DC/stn0: [03] [00] [3C] [77] [10] [20] [88] [0F]  val=0x0F882010
          DELAY 200ms

        These writes are repeated for both PEX8647 switches (0x6A and 0x68).

        Firmware: pex8647_cfg_multi_host_8   (0x36DBC)
                  pex8647_cfg_multi_host_2_4 (0x36EF0)
        """
        if mode == MultiHostMode.MODE_8_1:
            stn2_reg234 = 0x9C040000  # bit 8 = 0 (secondary)
            stn0_reg234 = 0x9C040100  # bit 8 = 1 (primary)
            reg1dc = 0x0F882010       # bit 19 = 1 (port merge enabled)
        else:
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

        Order of operations (from firmware multi_host_mode_set at 0x380BC):
          1. Configure PEX8696 downstream lane partitioning (all 4 switches)
          2. Configure PEX8696 NT bridge ports (station 3, port 3)
          3. Configure PEX8647 upstream switches (both switches)

        Source: PEX-I2C-COMMANDS.md section 9.2

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

        # Order matches firmware (multi_host_mode_set at 0x380BC):
        self._configure_pex8696_lanes(mode)
        self._configure_pex8696_nt_bridge()
        self._configure_pex8647(mode)

        log.info("Multi-host mode switch to %s complete", mode.name)


# ===========================================================================
# Top-Level Chassis Controller
# ===========================================================================

class C410X:
    """Top-level controller for the Dell C410X GPU expansion chassis.

    Combines slot power control and multi-host mode configuration
    into a single interface. Opens an I2C bus connection and provides
    convenience methods for all chassis operations.

    Example usage:
        with C410X(i2c_bus=3) as chassis:
            chassis.startup_all()              # Power on all 16 GPU slots
            chassis.set_multihost_mode("4:1")  # Set 4:1 fan-out
            print(chassis.read_slot_status(4)) # Check slot 4 status
            chassis.shutdown_all()             # Power off all slots

    For dry-run testing (logs I2C transactions without hardware):
        with C410X(i2c_bus=3, dry_run=True) as chassis:
            chassis.startup_all()  # Logs transactions, no hardware access
    """

    def __init__(
        self,
        i2c_bus: int = 3,
        *,
        dry_run: bool = False,
    ) -> None:
        """Open I2C bus and initialise controllers.

        Args:
            i2c_bus: Linux I2C bus number. Default 3 for the AST2050
                     I2C engine 3 on the Dell C410X.
                     Source: PEX-I2C-COMMANDS.md section 2.1
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
        """Power on a single GPU slot (1-based). See SlotPowerController.power_on."""
        self.slots.power_on(SLOT_MAP[slot_num - 1])

    def slot_power_off(self, slot_num: int) -> None:
        """Power off a single GPU slot (1-based). See SlotPowerController.power_off."""
        self.slots.power_off(SLOT_MAP[slot_num - 1])

    def startup_all(self, present_mask: int = 0xFFFF) -> None:
        """Full 16-slot staggered power-on. See SlotPowerController.startup_all."""
        self.slots.startup_all(present_mask)

    def shutdown_all(self) -> None:
        """Power off all 16 slots. See SlotPowerController.shutdown_all."""
        self.slots.shutdown_all()

    def set_multihost_mode(self, mode: MultiHostMode | int | str) -> None:
        """Switch multi-host fan-out mode. See MultiHostController.set_mode."""
        self.multihost.set_mode(mode)

    def read_slot_status(self, slot_num: int) -> dict[str, object]:
        """Read current power/link status for a slot.

        Reads register 0x080 (Slot Control / Slot Status) and decodes
        the Power Indicator Control (PIC) and Power Controller Control
        (PCC) fields.

        Source: PEX-I2C-COMMANDS.md section 4.2

        Returns a dict with:
          slot: slot number (1-16)
          switch: PEX8696 switch identifier
          station: PLX station number
          raw_slot_ctrl: raw 32-bit register value (hex string)
          power_indicator: "ON", "OFF", "blink", or "reserved"
          power_controller: "on" or "off"
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

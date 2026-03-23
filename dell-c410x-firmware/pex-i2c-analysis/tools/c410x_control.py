#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["smbus2>=0.4"]
# ///
"""Dell C410X PEX switch control CLI.

Command-line interface for controlling GPU slot power and multi-host
mode on the Dell C410X expansion chassis via I2C to PLX PEX switches.

This tool implements the operations documented in PEX-I2C-COMMANDS.md,
using the c410x_pex library for the PLX 4-byte I2C command protocol.
All I2C sequences were reverse engineered from the Dell C410X Avocent
MergePoint firmware v1.35 (/sbin/fullfw ARM ELF binary).

==========================================================================
 Usage
==========================================================================

    # Show slot power status (reads register 0x080 per slot)
    uv run c410x_control.py status

    # Power on a single slot (9 I2C txns + 100ms delay per slot)
    uv run c410x_control.py power-on 4

    # Power off a single slot (2 I2C txns per slot, no delay)
    uv run c410x_control.py power-off 4

    # Full 16-slot staggered startup (144 I2C txns, ~2s total)
    # Phases: slots 4,8,12,16 -> 3,7,11,15 -> 2,6,10,14 -> 1,5,9,13
    # Source: PEX-I2C-COMMANDS.md section 8
    uv run c410x_control.py startup

    # Shutdown all 16 slots (32 I2C txns, not staggered)
    uv run c410x_control.py shutdown

    # Switch multi-host fan-out mode
    # Reconfigures PEX8696 lane partitioning + PEX8647 port merging
    # Source: PEX-I2C-COMMANDS.md section 9
    uv run c410x_control.py multihost 4:1

    # Show slot-to-switch mapping (no I2C, just prints the lookup table)
    uv run c410x_control.py topology

    # Dry-run mode: log all I2C transactions without touching hardware
    # Shows exact wire-level bytes that would be sent
    uv run c410x_control.py --dry-run -vv startup

    # Verbose output: -v for INFO, -vv for DEBUG (shows wire bytes)
    uv run c410x_control.py -vv power-on 4

==========================================================================
 References
==========================================================================

    PEX-I2C-COMMANDS.md       - Master I2C command reference
    c410x_pex.py              - Library implementing the PLX I2C protocol
    analysis/i2c-transport.md - I2C bus and protocol details
    analysis/pex8696-hotplug.md - Slot power register analysis
    analysis/pex-multihost.md - Multi-host mode register analysis
    analysis/power-sequencing.md - 16-slot startup sequence analysis
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow importing c410x_pex from the same directory
sys.path.insert(0, str(Path(__file__).parent))

from c410x_pex import (
    C410X,
    MultiHostMode,
    SLOT_MAP,
    POWER_ON_PHASES,
    PEX8696_ADDRS,
    PEX8647_ADDRS,
)


def cmd_status(chassis: C410X, args: argparse.Namespace) -> None:
    """Show current slot power status."""
    slots = range(1, 17) if args.slot is None else [args.slot]

    print(f"{'Slot':>4}  {'Switch':>22}  {'Stn':>3}  {'Power':>6}  {'PCC':>4}  {'Raw':>12}")
    print("-" * 60)

    for slot_num in slots:
        status = chassis.read_slot_status(slot_num)
        print(
            f"{status['slot']:>4}  {status['switch']:>22}  "
            f"{status['station']:>3}  {status['power_indicator']:>6}  "
            f"{status['power_controller']:>4}  {status['raw_slot_ctrl']}"
        )


def cmd_power_on(chassis: C410X, args: argparse.Namespace) -> None:
    """Power on one or more slots."""
    for slot_num in args.slots:
        if slot_num < 1 or slot_num > 16:
            print(f"Error: slot {slot_num} out of range (1-16)", file=sys.stderr)
            sys.exit(1)
        chassis.slot_power_on(slot_num)
        print(f"Slot {slot_num}: powered ON")


def cmd_power_off(chassis: C410X, args: argparse.Namespace) -> None:
    """Power off one or more slots."""
    for slot_num in args.slots:
        if slot_num < 1 or slot_num > 16:
            print(f"Error: slot {slot_num} out of range (1-16)", file=sys.stderr)
            sys.exit(1)
        chassis.slot_power_off(slot_num)
        print(f"Slot {slot_num}: powered OFF")


def cmd_startup(chassis: C410X, args: argparse.Namespace) -> None:
    """Execute full 16-slot staggered power-on sequence."""
    present_mask = args.present_mask

    print("Dell C410X 16-Slot GPU Power-On Sequence")
    print("=" * 50)
    print(f"Present mask: 0x{present_mask:04X} ({bin(present_mask).count('1')} slots)")
    print()

    for phase_num, slot_indices in enumerate(POWER_ON_PHASES, 1):
        phase_slots = [SLOT_MAP[i].slot_num for i in slot_indices]
        active = [
            SLOT_MAP[i].slot_num
            for i in slot_indices
            if present_mask & (1 << i)
        ]
        print(f"Phase {phase_num}: slots {phase_slots} (active: {active})")

    print()

    if not args.yes:
        answer = input("Proceed with power-on? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    chassis.startup_all(present_mask)
    print("\nAll slots powered on.")


def cmd_shutdown(chassis: C410X, args: argparse.Namespace) -> None:
    """Power off all 16 GPU slots."""
    print("Dell C410X 16-Slot GPU Shutdown")
    print("=" * 50)

    if not args.yes:
        answer = input("Power off all 16 GPU slots? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    chassis.shutdown_all()
    print("All slots powered off.")


def cmd_multihost(chassis: C410X, args: argparse.Namespace) -> None:
    """Switch multi-host fan-out mode.

    WARNING: All GPU slots must be powered off before switching modes.
    The firmware orchestrator (multi_host_mode_set at 0x380BC) powers off
    all slots first. Changing lane registers while PCIe links are active
    causes bus errors. See PEX-I2C-COMMANDS.md section 9.2.

    Note: SerDes re-equalisation (section 9.6) is not yet implemented.
    Gen2 links may require manual re-training after mode switch.
    """
    mode_str = args.mode
    valid_modes = {"2:1": 2, "4:1": 4, "8:1": 8}

    if mode_str not in valid_modes:
        print(f"Error: invalid mode '{mode_str}'. Use 2:1, 4:1, or 8:1", file=sys.stderr)
        sys.exit(1)

    print(f"Switching to {mode_str} multi-host mode")
    print()
    print("  WARNING: All GPU slots must be powered off before mode switching!")
    print("  Run 'c410x_control.py shutdown' first if slots are powered.")
    print("  (Firmware does this automatically — see PEX-I2C-COMMANDS.md section 9.2)")
    print()
    print(f"  PEX8696 switches (7-bit): {[f'0x{a:02X}' for a in PEX8696_ADDRS]}")
    print(f"  PEX8647 switches (7-bit): {[f'0x{a:02X}' for a in PEX8647_ADDRS]}")

    mode_descriptions = {
        "2:1": "8 hosts, 2 GPU slots each",
        "4:1": "4 hosts, 4 GPU slots each (default)",
        "8:1": "2 hosts, 8 GPU slots each",
    }
    print(f"  Configuration: {mode_descriptions[mode_str]}")
    print()

    if not args.yes:
        answer = input("Proceed with mode switch? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    chassis.set_multihost_mode(mode_str)
    print(f"\nMulti-host mode switched to {mode_str}.")


def cmd_topology(chassis: C410X, args: argparse.Namespace) -> None:
    """Display the slot-to-switch mapping topology.

    Shows the firmware lookup tables extracted from ROM addresses 0xF7B06
    and 0xF7B16, with both 7-bit (smbus2) and 8-bit GBT (firmware) I2C
    address formats.

    Source: PEX-I2C-COMMANDS.md section 5 (Slot-to-Switch Mapping)
    Source: analysis/i2c-transport.md "Slot-to-I2C-Address Mapping"
    """
    print("Dell C410X Slot-to-Switch Mapping")
    print("(Source: firmware ROM at 0xF7B06/0xF7B16, see PEX-I2C-COMMANDS.md section 5)")
    print("=" * 72)
    # i2c_addr is stored as 7-bit for smbus2; GBT 8-bit = 7-bit << 1
    print(f"{'Slot':>4}  {'7-bit':>6}  {'8-bit GBT':>9}  {'Switch':>8}  {'Station':>7}  {'Port Byte':>9}")
    print("-" * 72)

    for slot in SLOT_MAP:
        gbt_addr = slot.i2c_addr << 1  # 8-bit GBT format (as in firmware)
        print(
            f"{slot.slot_num:>4}  "
            f"0x{slot.i2c_addr:02X}    "
            f"0x{gbt_addr:02X}        "
            f"#{slot.switch_index:<7d} "
            f"{slot.station:>7}  "
            f"0x{slot.port_byte:02X}"
        )

    print()
    print("PEX8696 downstream switches (4 slots each):")
    for i, addr in enumerate(PEX8696_ADDRS):
        gbt = addr << 1
        slots = [s.slot_num for s in SLOT_MAP if s.i2c_addr == addr]
        print(f"  #{i}: 7-bit 0x{addr:02X} / GBT 0x{gbt:02X} -> slots {slots}")

    print()
    print("PEX8647 upstream switches (host-side):")
    for i, addr in enumerate(PEX8647_ADDRS):
        gbt = addr << 1
        print(f"  #{i}: 7-bit 0x{addr:02X} / GBT 0x{gbt:02X}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dell C410X PEX switch control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s status              Show all slot power status
  %(prog)s status --slot 4     Show status for slot 4 only
  %(prog)s power-on 1 2 3      Power on slots 1, 2, 3
  %(prog)s power-off 4         Power off slot 4
  %(prog)s startup             Full 16-slot staggered power-on
  %(prog)s shutdown             Power off all 16 slots
  %(prog)s multihost 4:1       Switch to 4:1 fan-out mode
  %(prog)s topology            Show slot-to-switch mapping
  %(prog)s --dry-run startup   Log transactions without touching HW
""",
    )

    parser.add_argument(
        "--bus", type=int, default=3,
        help="I2C bus number (default: 3)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Log all I2C transactions but don't touch hardware",
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Skip confirmation prompts",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Show slot power status")
    p_status.add_argument("--slot", type=int, help="Show specific slot (1-16)")

    # power-on
    p_on = subparsers.add_parser("power-on", help="Power on slot(s)")
    p_on.add_argument("slots", type=int, nargs="+", help="Slot numbers (1-16)")

    # power-off
    p_off = subparsers.add_parser("power-off", help="Power off slot(s)")
    p_off.add_argument("slots", type=int, nargs="+", help="Slot numbers (1-16)")

    # startup
    p_startup = subparsers.add_parser(
        "startup", help="Full 16-slot staggered power-on"
    )
    p_startup.add_argument(
        "--present-mask", type=lambda x: int(x, 0), default=0xFFFF,
        help="16-bit mask of present GPUs (default: 0xFFFF = all)",
    )

    # shutdown
    subparsers.add_parser("shutdown", help="Power off all 16 slots")

    # multihost
    p_multi = subparsers.add_parser("multihost", help="Switch multi-host mode")
    p_multi.add_argument("mode", choices=["2:1", "4:1", "8:1"],
                         help="Fan-out ratio")

    # topology
    subparsers.add_parser("topology", help="Show slot-to-switch mapping")

    args = parser.parse_args()

    # Configure logging
    if args.verbose >= 2:
        log_level = logging.DEBUG
    elif args.verbose >= 1:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Topology command doesn't need I2C
    if args.command == "topology":
        cmd_topology(None, args)  # type: ignore[arg-type]
        return

    # Open chassis connection
    with C410X(i2c_bus=args.bus, dry_run=args.dry_run) as chassis:
        commands = {
            "status": cmd_status,
            "power-on": cmd_power_on,
            "power-off": cmd_power_off,
            "startup": cmd_startup,
            "shutdown": cmd_shutdown,
            "multihost": cmd_multihost,
        }
        commands[args.command](chassis, args)


if __name__ == "__main__":
    main()

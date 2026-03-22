#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["smbus2>=0.4"]
# ///
"""Dell C410X PEX switch control CLI.

Command-line interface for controlling GPU slot power and multi-host
mode on the Dell C410X expansion chassis via I2C to PLX PEX switches.

Usage:
    # Show slot status
    uv run c410x_control.py status

    # Power on a single slot
    uv run c410x_control.py power-on 4

    # Power off a single slot
    uv run c410x_control.py power-off 4

    # Full 16-slot startup sequence (staggered)
    uv run c410x_control.py startup

    # Shutdown all 16 slots
    uv run c410x_control.py shutdown

    # Switch multi-host mode
    uv run c410x_control.py multihost 4:1

    # Dry-run mode (log transactions without touching hardware)
    uv run c410x_control.py --dry-run startup
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
    """Switch multi-host fan-out mode."""
    mode_str = args.mode
    valid_modes = {"2:1": 2, "4:1": 4, "8:1": 8}

    if mode_str not in valid_modes:
        print(f"Error: invalid mode '{mode_str}'. Use 2:1, 4:1, or 8:1", file=sys.stderr)
        sys.exit(1)

    print(f"Switching to {mode_str} multi-host mode")
    print(f"  PEX8696 switches: {[f'0x{a:02X}' for a in PEX8696_ADDRS]}")
    print(f"  PEX8647 switches: {[f'0x{a:02X}' for a in PEX8647_ADDRS]}")

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
    """Display the slot-to-switch mapping topology."""
    print("Dell C410X Slot-to-Switch Mapping")
    print("=" * 65)
    print(f"{'Slot':>4}  {'I2C Addr':>9}  {'7-bit':>5}  {'Switch':>8}  {'Station':>7}  {'Port Byte':>9}")
    print("-" * 65)

    for slot in SLOT_MAP:
        print(
            f"{slot.slot_num:>4}  "
            f"0x{slot.i2c_addr:02X}       "
            f"0x{slot.i2c_addr >> 1:02X}   "
            f"#{slot.switch_index:<7d} "
            f"{slot.station:>7}  "
            f"0x{slot.port_byte:02X}"
        )

    print()
    print("PEX8696 downstream switches:")
    for i, addr in enumerate(PEX8696_ADDRS):
        slots = [s.slot_num for s in SLOT_MAP if s.i2c_addr == addr]
        print(f"  #{i}: 0x{addr:02X} (7-bit 0x{addr >> 1:02X}) -> slots {slots}")

    print()
    print("PEX8647 upstream switches:")
    for i, addr in enumerate(PEX8647_ADDRS):
        print(f"  #{i}: 0x{addr:02X} (7-bit 0x{addr >> 1:02X})")


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

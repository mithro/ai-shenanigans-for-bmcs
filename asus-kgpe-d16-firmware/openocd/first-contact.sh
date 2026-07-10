#!/bin/sh
# first-contact.sh — first JTAG contact with the AST2050 BMC (SoC-only stack).
# Prints the TAP IDCODE; expect 0x07926f0f (ARM926EJ-S). A scan of "all ones"
# with "IR capture error; saw 0x0f" means the harness is not connected or the
# board is unpowered — the normal result with nothing wired.
#
# Runs from wherever the OpenOCD configs live (this script's own directory), so
# it works both from the repo checkout and from ~/openocd-bmc/ on the bridge Pi.
# See JTAG-USAGE-GUIDE.md §5.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec openocd -f "$here/rpi4-jtag.cfg" -f "$here/ast2050.cfg" \
             -c "init; scan_chain; shutdown"

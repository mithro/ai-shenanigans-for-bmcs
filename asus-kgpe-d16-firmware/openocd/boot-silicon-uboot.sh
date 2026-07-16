#!/bin/sh
# boot-silicon-uboot.sh — bring the real AST2050 BMC from ANY state to a U-Boot
# `boot#` prompt over JTAG. Run on the bridge Pi (rpi4-asus-aspeed2050-dev).
#
# Why three OpenOCD invocations:
#  1. `reset halt` — a previously-booted Linux leaves the MMU+caches ON; JTAG then
#     translates virtually and physical AHB writes fail ("Address translation
#     failure"). Poking SCTLR via CP15 mid-session isn't enough (OpenOCD keeps a
#     stale MMU view), so reset the core for a clean MMU-off state.
#  2. ddr2-init.tcl — MEASURED: that core reset ALSO resets the SDMC (DRAM
#     read-back returned 0x00054000, not the 0xdeadbeef we wrote), so DDR2 must be
#     re-trained after every reset. Also re-sets SCU40[6] (U-Boot skips DDR2 init).
#  3. boot-uboot.tcl — load u-boot.bin into the native 0x40000000 window, AHB
#     unlock + DRAM->0x0 remap, PC=0, resume. (JTAG sets PC, so no P2A watchdog
#     reset-boot trick needed.)
set -eu
cd "$(dirname "$0")"
CFG="-f rpi4-jtag.cfg -f kgpe-d16-bmc.cfg"

echo "### [1/3] reset halt (clean core, MMU off)"
timeout 60 openocd $CFG -c init -c "reset halt" -c shutdown 2>&1 | grep -iE "halted in|Error" | head -3

echo "### [2/3] re-train DDR2 (a core reset clears the SDMC)"
timeout 90 openocd $CFG -f ddr2-init.tcl 2>&1 | grep -iE "TRAINED|NOT up|MCR04|straps|Error" | head -6

echo "### [3/3] load U-Boot + remap + PC=0 + resume"
timeout 90 openocd $CFG -f boot-uboot.tcl 2>&1 | grep -iE "SCTLR|read-back|remap|resumed|Error" | head -8

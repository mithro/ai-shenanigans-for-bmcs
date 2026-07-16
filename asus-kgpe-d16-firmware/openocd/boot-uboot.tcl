# boot-uboot.tcl — load the Raptor AST2050 U-Boot into trained DRAM and run it.
#
# Prereq: ddr2-init.tcl has run (DDR2 trained + SCU40[6] set so U-Boot's
# lowlevel_init SKIPS DDR2 re-init -- re-initing the DRAM it executes from crashes).
#
# U-Boot links at -Ttext 0x0, so it must execute at 0x0. We load it into the NATIVE
# DRAM window (0x40000000) -- never writing 0x0 pre-remap (the crash rule) -- then
# enable the DRAM->0x0 remap (AHB_ADDR_REMAP_REG 0x1E60008C bit 0, after the AHB
# unlock 0xAEED1A03 -> 0x1E600000) so 0x0 aliases to DRAM, and set PC=0 directly.
# JTAG lets us set PC, so we do NOT need the P2A watchdog reset-boot trick.
proc rd {a} { return [lindex [read_memory $a 32 1] 0] }

# -f scripts run at CONFIG stage; bring the target up before any run-control.
init

# Run me LAST in this 3-step chain (see boot-silicon-uboot.sh):
#   1. openocd -c init -c "reset halt" -c shutdown   -> clean core, MMU/caches OFF
#      (a previously-booted Linux leaves the MMU ON; JTAG then virtually translates
#      and physical AHB writes fail with "Address translation failure". Clearing
#      SCTLR via CP15 mid-session is NOT enough -- OpenOCD keeps a stale MMU view.)
#   2. openocd -f ddr2-init.tcl                      -> re-train DDR2 + set SCU40[6]
#      (MEASURED: a core `reset halt` DOES reset the SDMC -- DRAM read-back came back
#      0x00054000 instead of 0xdeadbeef -- so the training must be redone after it.)
#   3. this script                                   -> load U-Boot + remap + PC=0
halt
set sctlr [arm mrc 15 0 1 0 0]
echo [format "SCTLR = 0x%08x (MMU=%d -- must be 0)" $sctlr [expr {$sctlr & 1}]]

echo "=== DRAM trained? (expect the ddr2-init pattern to stick) ==="
mww 0x40000000 0xdeadbeef
echo [format "0x40000000 read-back = 0x%08x (expect 0xdeadbeef)" [rd 0x40000000]]

echo "=== loading U-Boot into native DRAM window 0x40000000 ==="
load_image /home/tim/openocd-bmc/raptor-uboot.bin 0x40000000 bin
echo "image head @0x40000000:"
mdw 0x40000000 4

echo "=== AHB unlock + DRAM->0x0 remap ==="
mww 0x1E600000 0xAEED1A03
set remap [rd 0x1E60008C]
echo [format "remap before = 0x%08x" $remap]
mww 0x1E60008C [expr {$remap | 1}]
set remap2 [rd 0x1E60008C]
echo [format "remap after  = 0x%08x" $remap2]

echo "=== 0x0 should now alias DRAM (== image head above) ==="
mdw 0x0 4

echo "=== boot: PC=0x0, SVC mode, IRQ/FIQ off ==="
reg cpsr 0x000000d3
reg pc 0x00000000
resume
echo "=== resumed -- watch the BMC console @1200 for the U-Boot banner ==="
shutdown

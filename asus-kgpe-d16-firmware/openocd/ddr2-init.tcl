# ddr2-init.tcl — initialise the AST2050 DDR2 controller over JTAG.
# ----------------------------------------------------------------------------
# Faithful, register-for-register translation of Raptor's DDR2 bring-up in
# platform.S — the same sequence as ddr2-init-p2a.py, but executed by the
# ARM926 core's own AHB (via EmbeddedICE) instead of the P2A PCIe back door.
# This is MORE faithful than P2A: the CPU issues the writes, exactly as a
# booting U-Boot would.
#
# On a firmware-dead AST2050, power-on leaves DDR2 UNTRAINED — the native DRAM
# window (0x40000000, 64 MB) reads a stuck constant and writes don't stick.
# After this script, a DRAM write/read-back round-trips.
#
# Run (board powered, harness wired):
#   openocd -f rpi4-jtag.cfg -f kgpe-d16-bmc.cfg -f ddr2-init.tcl
#
# STATE-MUTATING: SCU + SDMC register writes (0x1e6e2000 / 0x1e6e0000) and DRAM
# verify writes to the 0x40000000 native window. It NEVER writes 0x0 or the SMC
# flash window 0x14000000 (the AHB-stall hazard). Coordinate on the shared rig.
#
# Values: see ddr2-init-p2a.py for the per-line provenance (4-bank/64 MB MCR04,
# the critical final DLL value 0x002d3000, etc.) and
# DDR2-INIT-REVERSE-ENGINEERING.md for the platform.S mapping.
# ----------------------------------------------------------------------------
init
halt

set M     0x1e6e0000   ;# SDMC (MCRxx) base
set SCU00 0x1e6e2000
set SCU0C 0x1e6e200c
set SCU20 0x1e6e2020
set SCU40 0x1e6e2040
set SCU70 0x1e6e2070

proc w {a v} { mww $a $v }
proc rd {a}  { return [lindex [read_memory $a 32 1] 0] }

echo "=== AST2050 DDR2 init over JTAG (faithful platform.S) ==="
set scu70 [rd $SCU70]
set scu40 [rd $SCU40]
echo [format "straps: SCU70=0x%08x SCU40=0x%08x" $scu70 $scu40]

# --- SCU: unlock, restore clock-stop default, program M-PLL ---
w $SCU00 0x1688a8a8
w $SCU0C 0x000c3e8b
w $SCU20 0x000041f0
sleep 50                             ;# ~400 us

# --- SDMC: unlock + early DLL ---
w [expr {$M + 0x00}] 0xfc600309
w [expr {$M + 0x6c}] 0x00909090
w [expr {$M + 0x64}] 0x00050000

# MCR04 = base 0x585 (4-bank + 64 MB) OR the SCU70 strap bits [3:2]<<2
set mcr04 [expr {0x00000585 | (($scu70 & 0xc) << 2)}]
echo [format "MCR04 = 0x%08x (from SCU70 strap)" $mcr04]
w [expr {$M + 0x04}] $mcr04

# --- SDMC: protection, AC timing (NSPEED then LSPEED), delay ctrl ---
w [expr {$M + 0x08}] 0x0011030f
w [expr {$M + 0x10}] 0x22201725
w [expr {$M + 0x18}] 0x1e29011a
w [expr {$M + 0x20}] 0x00c82222
w [expr {$M + 0x14}] 0x22201725
w [expr {$M + 0x1c}] 0x1e29011a
w [expr {$M + 0x24}] 0x00c82222
w [expr {$M + 0x38}] 0xffffff82
w [expr {$M + 0x3c}] 0x00000000
w [expr {$M + 0x40}] 0x00000000
w [expr {$M + 0x44}] 0x00000000
w [expr {$M + 0x48}] 0x00000000
w [expr {$M + 0x4c}] 0x00000000
w [expr {$M + 0x50}] 0x00000000
w [expr {$M + 0x54}] 0x00000000
w [expr {$M + 0x58}] 0x00000000
w [expr {$M + 0x5c}] 0x00000000
w [expr {$M + 0x60}] 0x032aa02a

# --- FINAL DLL block (platform.S 451-469) — CRITICAL: MCR64 written a 2nd
#     time with the real DQS/DLL delay; omitting it caused ~0.29% data errors ---
w [expr {$M + 0x64}] 0x002d3000
w [expr {$M + 0x68}] 0x02020202
w [expr {$M + 0x70}] 0x00000000
w [expr {$M + 0x74}] 0x00000000
w [expr {$M + 0x78}] 0x00000000
w [expr {$M + 0x7c}] 0x00000000

# --- power ctrl start, then MRS/EMRS mode-set sequence ---
w [expr {$M + 0x34}] 0x00000001
sleep 50                             ;# ~400 us
w [expr {$M + 0x2c}] 0x00000732
w [expr {$M + 0x30}] 0x00000040
w [expr {$M + 0x28}] 0x00000005
w [expr {$M + 0x28}] 0x00000007
w [expr {$M + 0x28}] 0x00000003
w [expr {$M + 0x28}] 0x00000001
w [expr {$M + 0x0c}] 0x00005a08
w [expr {$M + 0x2c}] 0x00000632
w [expr {$M + 0x28}] 0x00000001
w [expr {$M + 0x30}] 0x000003c0
w [expr {$M + 0x28}] 0x00000003
w [expr {$M + 0x30}] 0x00000040
w [expr {$M + 0x28}] 0x00000003
w [expr {$M + 0x0c}] 0x00005a21       ;# refresh timing (final)
w [expr {$M + 0x34}] 0x00007c03       ;# power ctrl (final)
w [expr {$M + 0x120}] 0x00004c41      ;# AST2000-compat SCU MPLL param

# --- set DDR-init-done scratch flag, relock SCU + SDRAM regs ---
w $SCU40 [expr {$scu40 | 0x40}]
w $SCU00 0x00000000
w [expr {$M + 0x00}] 0x00000000

# --- verify: DRAM write/read-back on the native 0x40000000 window ---
echo "=== DRAM write/read-back verify (0x40000000 native window) ==="
set fails 0
proc vtest {a v} {
    mww $a $v
    set r [rd $a]
    set ok [expr {$r == $v}]
    echo [format "  0x%08x <- 0x%08x  read=0x%08x  %s" $a $v $r [expr {$ok ? "OK" : "FAIL"}]]
    return $ok
}
if {![vtest 0x40000000 0xdeadbeef]} { incr fails }
if {![vtest 0x40000004 0x12345678]} { incr fails }
if {![vtest 0x40100000 0xa5a5a5a5]} { incr fails }
if {![vtest 0x43f00000 0x5a5a5a5a]} { incr fails }
if {$fails == 0} {
    echo ">>> DDR2 TRAINED: all read-backs match. DRAM is usable."
} else {
    echo ">>> DDR2 NOT up: $fails/4 failed (stuck constant = still uninitialised)."
}

shutdown

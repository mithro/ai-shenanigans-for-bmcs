# mic-test.tcl — silicon cross-validation of the AST2050 MIC engine (row 44).
#
# Prereq: run as the LAST openocd step, AFTER `reset halt` + ddr2-init.tcl
# (DDR2 trained, core halted, MMU off). Mirrors the QEMU `mictest` gate but on the
# REAL chip via JTAG: unlock AHBC + remap DRAM->0x0, lay out a zeroed 4KB page +
# control buffer (only that page = MIC-mode) + checksum buffer, enable the MIC, and
# read back the checksum. The bit-exact Fletcher-32 of an all-zero 4KB page is
# 0xFFFFFFFF (== what the QEMU aspeed_mic_ast2050 model produces).
proc rd {a} { return [lindex [read_memory $a 32 1] 0] }

init
halt

# --- AHB unlock (0xAEED1A03 key) + DRAM->0x0 remap so the MIC's 0x0-based scan
#     reaches DRAM (same sequence boot-uboot.tcl uses). ---
mww 0x1E600000 0xAEED1A03
set remap [rd 0x1E60008C]
mww 0x1E60008C [expr {$remap | 1}]
echo [format "REMAP: 0x1E60008C = 0x%08x" [rd 0x1E60008C]]

# remap sanity: write via native 0x4000_0000, read via low alias 0x0000_0000
mww 0x40000000 0xcafebabe
echo [format "REMAPCHK: low 0x00000000 = 0x%08x (expect 0xcafebabe)" [rd 0x00000000]]

# --- vInitSCU (from the Raptor SLT mictest.c): unlock the SCU and RELEASE THE MIC
#     FROM RESET (SCU04 &= 0xbffff clears bit 18). Without this the MIC stays held
#     in reset by SCU04 and never scans. ---
mww 0x1E6E2000 0x1688A8A8
set scu04 [rd 0x1E6E2004]
mww 0x1E6E2004 [expr {$scu04 & 0xbffff}]
echo [format "SCU04: 0x%08x -> 0x%08x (MIC released from reset)" $scu04 [rd 0x1E6E2004]]

# --- MIC test layout (post-remap low addresses == DRAM) ---
# scanned page = page 15 (0x0000F000); control buf @0x03000000; checksum @0x03400000.
echo "zeroing scanned page 15 (0x0000F000, 4KB)..."
mww 0x0000F000 0x00000000 1024
# control buffer: page 15 = CHK3 (MIC mode, bits[7:6] of byte3), pages 0-14 = SKIP.
mww 0x03000000 0xC0000000
# checksum-buffer entry for page 15 = 0 (initiative value).
mww 0x0340003C 0x00000000

# --- program + enable the MIC ---
mww 0x1E640000 0x03000000
mww 0x1E640004 0x03400000
mww 0x1E640008 0x00000000
mww 0x1E640018 0x10000000
mww 0x1E64000C 0x1000F000

# let the continuous scanner complete a pass (SLT polls up to ~100ms).
sleep 700

echo [format "MIC-CHKSUM: checksum-buf-page15 (0x0340003C) = 0x%08x  (expect 0xFFFFFFFF)" [rd 0x0340003C]]
echo [format "MIC-PROG:   MIC14 = 0x%08x  MIC18 = 0x%08x" [rd 0x1E640014] [rd 0x1E640018]]

# --- corrupt page 15 (word0=0xBEEF), re-scan -> mismatch -> MIC18 first-page-error ---
mww 0x0000F000 0x0000BEEF
mww 0x1E640018 0x10000000
mww 0x1E64000C 0x1000F000
sleep 700
echo [format "MIC-ERR:    after corrupt: MIC18 = 0x%08x  (expect bit28 + page 0x000F)" [rd 0x1E640018]]

shutdown

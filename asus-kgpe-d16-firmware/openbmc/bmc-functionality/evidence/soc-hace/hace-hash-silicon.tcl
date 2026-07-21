# hace-hash.tcl — silicon validation of the AST2050 HACE hash engine (row 43).
# Prereq: run AFTER `reset halt` + ddr2-init.tcl (DRAM trained). The HACE SRC is a
# full 32-bit AHB address, so it reads native DRAM (0x40000000) directly — no AHBC
# remap needed. Hash 64 zero bytes with SHA-256 and compare the digest to the known
# value f5a5fd42... (JTAG reads it back as LE u32 words: 42fda5f5 30206ad1 ...).
proc rd {a} { return [lindex [read_memory $a 32 1] 0] }
init
halt
mww 0x1E6E2000 0x1688A8A8   ;# SCU unlock
# Enable the HAC engine: clear SCU0C[13] "Stop YCLK (For HAC)" (datasheet §18
# l.16040 — YCLK is the hash/crypto compute clock) and release AES_RST_N =
# SCU04[4] (datasheet Fig.43 Crypto Engine Reset). Both are held at power-on, so
# the register file responds but the compute engine is clock-dead + in reset.
set scu0c [rd 0x1E6E200C]
mww 0x1E6E200C [expr {$scu0c & ~0x2000}]
set scu04 [rd 0x1E6E2004]
mww 0x1E6E2004 [expr {$scu04 & ~0x10}]
echo [format "SCU0C 0x%08x->0x%08x (YCLK on) ; SCU04 0x%08x->0x%08x (AES_RST_N off)" \
  $scu0c [rd 0x1E6E200C] $scu04 [rd 0x1E6E2004]]

# source buffer: 64 zero bytes @ 0x40001000 (native DRAM); digest buf @ 0x40002000
mww 0x40001000 0x00000000 16
mww 0x40002000 0xEEEEEEEE 8
echo [format "PRE: src0=0x%08x digest0=0x%08x (0xEEEEEEEE sentinel)" [rd 0x40001000] [rd 0x40002000]]

# program the HACE hash: SHA-256 (CMD 0x50 = BIT4|BIT6), single buffer (no SG/ACCUM)
mww 0x1E6E3020 0x40001000   ;# R_HASH_SRC
mww 0x1E6E3024 0x40002000   ;# R_HASH_DEST
mww 0x1E6E302C 0x00000040   ;# R_HASH_SRC_LEN = 64
mww 0x1E6E3030 0x00000050   ;# R_HASH_CMD = SHA256 -> fires
sleep 400
echo [format "STATUS 0x1E6E301C = 0x%08x" [rd 0x1E6E301C]]
echo [format "DIGEST = %08x %08x %08x %08x %08x %08x %08x %08x" \
  [rd 0x40002000] [rd 0x40002004] [rd 0x40002008] [rd 0x4000200c] \
  [rd 0x40002010] [rd 0x40002014] [rd 0x40002018] [rd 0x4000201c]]
echo "EXPECT   = 42fda5f5 30206ad1 6eef9827 9b9709d3 233d0043 e8f0d920 a93198ea 4bfb5927"
shutdown

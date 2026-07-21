# mdma-test.tcl — silicon cross-validation of the AST2050 MDMA engine (row 45).
# Prereq: run as the LAST openocd step, AFTER `reset halt` + ddr2-init.tcl.
# Mirrors the QEMU mdmacopy gate on the REAL chip: AHBC unlock + DRAM->0x0 remap
# (the 28-bit MDMA only reaches 0x0..0x0FFFFFFF, so DRAM must be remapped low),
# lay out a source pattern + zeroed dest, program MDMA (base 0x1E740000:
# SRC@00 DST@04 CMD@0C where a CMD write FIRES: [31]UPDATE|[30:28]ID|[25:24]TYPE|
# [23:0]LEN, TYPE 0=COPY 2=FILL), then verify dest == source.
proc rd {a} { return [lindex [read_memory $a 32 1] 0] }

init
halt

# --- AHBC unlock (0xAEED1A03) + DRAM->0x0 remap ---
mww 0x1E600000 0xAEED1A03
set remap [rd 0x1E60008C]
mww 0x1E60008C [expr {$remap | 1}]
mww 0x40000000 0xcafebabe
echo [format "REMAPCHK: low 0x0 = 0x%08x (expect 0xcafebabe)" [rd 0x00000000]]

# --- vInitSCU: unlock SCU + release the MDMA from reset. Datasheet Fig.54:
#     SCU04[16] = DMA_RST_N (MDMA Engine Reset), default 1 = held in reset at
#     power-on. Clear bit 16 (and 18=MIC) so the MDMA register block responds. ---
mww 0x1E6E2000 0x1688A8A8
set scu04 [rd 0x1E6E2004]
mww 0x1E6E2004 [expr {$scu04 & ~0x50000}]
echo [format "SCU04: 0x%08x -> 0x%08x (cleared DMA_RST_N bit16)" $scu04 [rd 0x1E6E2004]]

# --- lay out source (0x00010000) + zeroed dest (0x00020000) via the low alias ---
mww 0x00010000 0xdeadbeef
mww 0x00010004 0x12345678
mww 0x00010008 0xa5a5a5a5
mww 0x0001000c 0x5a5a5a5a
mww 0x00020000 0x00000000
mww 0x00020004 0x00000000
mww 0x00020008 0x00000000
mww 0x0002000c 0x00000000
echo [format "PRE : src=%08x %08x %08x %08x  dst=%08x %08x %08x %08x" \
  [rd 0x00010000] [rd 0x00010004] [rd 0x00010008] [rd 0x0001000c] \
  [rd 0x00020000] [rd 0x00020004] [rd 0x00020008] [rd 0x0002000c]]

# --- program + fire the MDMA copy (16 bytes) ---
mww 0x1E740000 0x00010000
mww 0x1E740004 0x00020000
mww 0x1E74000C 0x80000010
sleep 300
echo [format "MDMA-STS 0x1E740014 = 0x%08x" [rd 0x1E740014]]
echo [format "POST: dst=%08x %08x %08x %08x (expect deadbeef 12345678 a5a5a5a5 5a5a5a5a)" \
  [rd 0x00020000] [rd 0x00020004] [rd 0x00020008] [rd 0x0002000c]]

# --- MDMA fill test: fill 0x00030000..0F with 0xF00DF00D ---
mww 0x00030000 0x00000000
mww 0x1E740004 0x00030000
mww 0x1E740008 0xF00DF00D
mww 0x1E74000C 0x82000010
sleep 300
echo [format "FILL: dst=%08x %08x (expect f00df00d f00df00d)" [rd 0x00030000] [rd 0x00030004]]

shutdown

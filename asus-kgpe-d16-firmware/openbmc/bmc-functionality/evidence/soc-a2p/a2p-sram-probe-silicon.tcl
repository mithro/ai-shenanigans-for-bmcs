# sram-probe.tcl — ground-truth: is 0x1E720000 real on-chip SRAM on the AST2050,
# or the A2P (AHB->PCI) window? Decides whether QEMU #176 (SRAM removed on G3) is
# faithful. 0x1E7xxxxx is fixed SoC space, unaffected by the DRAM boot-remap, so a
# bare `reset halt` (no DDR2 init needed) suffices.
proc rd {a} { return [lindex [read_memory $a 32 1] 0] }

init
reset halt

echo "=== CONTROL: JTAG AHB read sanity ==="
echo [format "SCU7C (silicon rev) = 0x%08x  (expect ~0x0202)" [rd 0x1E6E207C]]

echo "=== PROBE 0x1E720000 : write-read (RAM?) ==="
set orig [rd 0x1E720000]
echo [format "ORIG            0x1E720000 = 0x%08x" $orig]
mww 0x1E720000 0xA5A5F00D
echo [format "WROTE 0xA5A5F00D -> reads   0x%08x" [rd 0x1E720000]]
mww 0x1E720000 0x5A5A0FF0
echo [format "WROTE 0x5A5A0FF0 -> reads   0x%08x" [rd 0x1E720000]]

echo "=== PROBE offset 0x1E724000 (mid-window) ==="
mww 0x1E724000 0xDEADBEEF
echo [format "WROTE 0xDEADBEEF -> reads   0x%08x" [rd 0x1E724000]]
mww 0x1E727FFC 0xCAFEBABE
echo [format "WROTE 0xCAFEBABE @0x1E727FFC -> reads 0x%08x" [rd 0x1E727FFC]]

echo "=== CONTROL: a KNOWN on-chip register block (SCU00) should NOT be RAM ==="
echo [format "SCU00 = 0x%08x (protection key reg, reads 0/lock state)" [rd 0x1E6E2000]]

shutdown

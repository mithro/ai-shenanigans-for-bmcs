# a2p-sweep.tcl — characterize the AST2050 A2P window (0x1E720000) readback.
# Is 0x04000008 a fixed constant across the whole 0x20000 window, or is there
# word-level structure? Read-only (no writes). Also probe just past the window.
proc rd {a} { return [lindex [read_memory $a 32 1] 0] }
init
reset halt
echo "=== word-level structure at the base ==="
foreach off {0x0 0x4 0x8 0xC 0x10 0x14 0x18 0x1C} {
    echo [format "0x1E72%04x = 0x%08x" $off [rd [expr {0x1E720000 + $off}]]]
}
echo "=== across the 0x20000 window ==="
foreach off {0x0 0x1000 0x4000 0x8000 0xF000 0x10000 0x14000 0x18000 0x1FFF0 0x1FFFC} {
    echo [format "0x1E72%05x = 0x%08x" $off [rd [expr {0x1E720000 + $off}]]]
}
echo "=== just past the window (0x1E728000..0x1E73FFFC) ==="
foreach a {0x1E728000 0x1E730000 0x1E738000 0x1E73FFFC} {
    echo [format "0x%08x = 0x%08x" $a [rd $a]]
}
echo "=== control: adjacent known blocks ==="
echo [format "0x1E740000 (SDHCI/MDMA region) = 0x%08x" [rd 0x1E740000]]
echo [format "0x1E6E2000 (SCU00)             = 0x%08x" [rd 0x1E6E2000]]
shutdown

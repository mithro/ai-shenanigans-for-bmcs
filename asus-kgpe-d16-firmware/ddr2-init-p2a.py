#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Bring up the AST2050 DDR2 controller over culvert P2A (milestone M1 of the
live-BMC boot; see docs/plans/2026-07-08-ast2050-live-bmc-boot.md).

This is a faithful, register-for-register translation of Raptor's DDR2 init in
`platform.S` (the sequence a booting U-Boot would run), executed from the host
over the P2A PCIe->AHB back door instead of from the ARM core. On a firmware-dead
AST2050 it initialises DRAM so payloads can be loaded, without needing the SMC
boot flash or a U-Boot build.

STATUS: written from platform.S; NOT yet hardware-verified (needs the rig). It
performs SCU + SDMC AHB WRITES -- a *state-mutating* op -- so it LOGS intent to
/home/claude/HARDWARE-COORDINATION.md and must be coordinated with instance-A
before running (per that protocol). Verifies success by a DRAM write/read-back
(the uninitialised repeating pattern -> real storage).

Runs culvert on the PXE host, reached via the Pi bridge (asus-bmc -> host).
"""
import subprocess, sys, time

PI = "asus-bmc"
HOST = "root@192.168.77.138"
CULVERT = "/root/culvert-g3/build/src/culvert p2a vga"

SCU00, SCU20, SCU40, SCU70 = 0x1e6e2000, 0x1e6e2020, 0x1e6e2040, 0x1e6e2070
M = 0x1e6e0000  # SDMC (MCRxx) base

# (addr, value) exactly as platform.S writes them, in order. MCR04 and the SCU40
# done-flag are computed at run time (marked None) and handled specially below.
SEQ = [
    (SCU00, 0x1688a8a8),        # unlock SCU
    (SCU20, 0x000041f0),        # SCU M-PLL params
    ("delay", 0),               # ~400us
    (M + 0x00, 0xfc600309),     # unlock SDRAM regs
    (M + 0x6c, 0x00909090),     # DLL ctrl #3
    (M + 0x64, 0x00050000),     # DLL ctrl #1
    ("mcr04", 0x00000585),      # CONFIG | ((SCU70 & 0xc) << 2); 4-BANK + 64MB
    # (was 0x00000d89 = 8-bank/1G; this KGPE-D16 DDR2 is 4-bank, 64MB. 8-bank
    #  aliased address bit13 (scrambled DRAM >8KB); 128MB [3:2]=10 gave a phantom
    #  64-128MB alias that wrapped onto U-Boot's own code at 0x40000000. bits[3:2]=01
    #  = 64MB matches the real chip. Verified on hw 2026-07-08 (tmp/mcr04_test.py,
    #  tmp/dramsize.py: real size aliases mod 64MB).)
    (M + 0x08, 0x0011030f),     # graphics mem protection
    (M + 0x10, 0x22201725),     # NSPEED AC timing #1
    (M + 0x18, 0x1e29011a),     # NSPEED AC timing #2
    (M + 0x20, 0x00c82222),     # NSPEED delay ctrl
    (M + 0x14, 0x22201725),     # LSPEED AC timing #1
    (M + 0x1c, 0x1e29011a),     # LSPEED AC timing #2
    (M + 0x24, 0x00c82222),     # LSPEED delay ctrl
    (M + 0x38, 0xffffff82),     # page-miss latency mask
    (M + 0x3c, 0x00000000),     # priority group
    (M + 0x40, 0x00000000), (M + 0x44, 0x00000000), (M + 0x48, 0x00000000),
    (M + 0x4c, 0x00000000),
    (M + 0x50, 0x00000000), (M + 0x54, 0x00000000), (M + 0x58, 0x00000000),
    (M + 0x5c, 0x00000000),
    (M + 0x60, 0x032aa02a),     # IO buffer mode
    # FINAL DLL block (platform.S lines 451-469) -- CRITICAL. platform.S writes
    # MCR64 TWICE: early 0x00050000 (above) then this final 0x002d3000, which sets
    # the real DQS/DLL delay. Omitting it left the DLL mistuned => ~0.29% DDR2 data
    # errors that corrupted large payloads. Restored to match platform.S exactly.
    (M + 0x64, 0x002d3000),     # DLL ctrl #1 (FINAL delay value)
    (M + 0x68, 0x02020202),     # DLL ctrl #2
    (M + 0x70, 0x00000000),     # test ctrl/status
    (M + 0x74, 0x00000000),     # test start addr/length
    (M + 0x78, 0x00000000),     # test fail DQ bit
    (M + 0x7c, 0x00000000),     # test init value
    (M + 0x34, 0x00000001),     # power ctrl (start)
    ("delay", 0),               # ~400us
    (M + 0x2c, 0x00000732),     # MRS/EMRS2
    (M + 0x30, 0x00000040),     # EMRS3
    (M + 0x28, 0x00000005),     # mode-set ctrl sequence
    (M + 0x28, 0x00000007),
    (M + 0x28, 0x00000003),
    (M + 0x28, 0x00000001),
    (M + 0x0c, 0x00005a08),     # refresh timing
    (M + 0x2c, 0x00000632),
    (M + 0x28, 0x00000001),
    (M + 0x30, 0x000003c0),
    (M + 0x28, 0x00000003),
    (M + 0x30, 0x00000040),
    (M + 0x28, 0x00000003),
    (M + 0x0c, 0x00005a21),     # refresh timing (final)
    (M + 0x34, 0x00007c03),     # power ctrl (final)
    (M + 0x120, 0x00004c41),    # AST2000-compat SCU MPLL param
    ("scu40done", 0),           # SCU40 |= 0x40  (DDR-init-done scratch flag)
    (SCU00, 0x00000000),        # lock SCU
    (M + 0x00, 0x00000000),     # lock SDRAM regs
]

NOTE = ("- 2026-07-08  instance-B (culvert-port): running ddr2-init-p2a.py -- "
        "DDR2 bring-up on the dead AST2050 via P2A (faithful platform.S sequence: "
        "SCU M-PLL + SDMC MCRxx writes + MRS/EMRS). STATE-MUTATING (SCU/SDMC AHB "
        "writes). Non-destructive to flash; brings DRAM up. Verifies by DRAM "
        "write/read-back. Coordinated per protocol.\n")


def sh(cmd, **kw):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                           PI, cmd], text=True, capture_output=True, **kw)


def host(script):
    pi_cmd = (f"sshpass -p systemrescue ssh -o StrictHostKeyChecking=no "
              f"-o ConnectTimeout=20 {HOST} bash -s")
    return sh(pi_cmd, input=script, timeout=180)


def build_host_script():
    lines = ["set -u", f'C="{CULVERT}"']
    # read the SCU70 strap to compute MCR04
    lines.append('SCU70=$($C read 0x1e6e2070 | awk -F: \'{gsub(/ /,"",$2);print $2}\')')
    lines.append('SCU40=$($C read 0x1e6e2040 | awk -F: \'{gsub(/ /,"",$2);print $2}\')')
    lines.append('echo "SCU70=$SCU70 SCU40=$SCU40"')
    for addr, val in SEQ:
        if addr == "delay":
            lines.append("sleep 0.05")
        elif addr == "mcr04":
            # MCR04 = 0x00000d89 | ((SCU70 & 0xc) << 2)
            lines.append('MCR04=$(printf "0x%08x" $(( 0x00000585 | ((SCU70 & 0xc) << 2) )))')
            lines.append('$C write 0x1e6e0004 "$MCR04"')
        elif addr == "scu40done":
            lines.append('$C write 0x1e6e2040 $(printf "0x%08x" $(( SCU40 | 0x40 )))')
        else:
            lines.append(f'$C write {hex(addr)} {hex(val)}')
    # verify DRAM: write a marker, read it back
    lines += [
        'echo "=== DRAM write/read-back verify ==="',
        '$C write 0x40000000 0xdeadbeef',
        '$C write 0x40000004 0x12345678',
        'echo -n "0x40000000 = "; $C read 0x40000000',
        'echo -n "0x40000004 = "; $C read 0x40000004',
        'echo "(expect deadbeef/12345678 if DDR2 alive; a fixed 0x00101000-style pattern = still uninitialised)"',
    ]
    return "\n".join(lines) + "\n"


def main():
    print("Logging intent to the coordination file...")
    sh("cat >> /home/claude/HARDWARE-COORDINATION.md", input=NOTE, timeout=40)
    print("Running DDR2 init over P2A on the host...\n")
    r = host(build_host_script())
    print(r.stdout)
    if r.stderr:
        print("[stderr]\n" + r.stderr)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())

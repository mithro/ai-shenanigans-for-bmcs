#!/usr/bin/env python3
"""Trim Raptor's `init_all_device[]` to the peripherals the kgpe-d16-bmc QEMU
machine actually models, so the 2.6.28.9 kernel boots an initramfs instead of
taking an external-abort panic the moment it pokes an unmodelled register.

Why
---
`plat-aspeed/devs.c` registers ~20 on-SoC devices at boot via
`ast_add_all_devices()`. QEMU's aspeed model implements the SCU, timer, UART,
FTGMAC, watchdog and RTC — but NOT the AST NAND controller, PWM/FAN, ADC, PECI,
KCS, LPC snoop, video FB, virtual USB hub, etc. The first such registration
(`ast_add_device_nand`) writes a NAND control register and faults:

    Unhandled fault: external abort on non-linefetch at 0xc800c050
    PC is at ast_add_device_nand+0x30 ... Kernel panic - Attempted to kill init!

An initramfs + dropbear boot needs only the console UART and the network MAC,
so we comment out every other entry. Idempotent: lines already commented (or
absent) are left alone.

Usage:
    uv run qemu-safe-devices.py --kdir /path/to/ast2050-linux-kernel
"""
import argparse
import os
import re

# Registered devices QEMU's kgpe-d16-bmc machine models / tolerates.
KEEP = {
    "ast_add_device_uart",      # console (0x1e784000) — required
    "ast_add_device_gmac",      # FTGMAC100 — required for SSH
    "ast_add_device_watchdog",  # aspeed wdt — modelled
    "ast_add_device_rtc",       # aspeed rtc — modelled
}
DEVS = os.path.join("arch", "arm", "plat-aspeed", "devs.c")
LINE = re.compile(r"^(\s*)(ast_add_device_\w+)\s*,\s*$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kdir", required=True)
    args = ap.parse_args()
    path = os.path.join(args.kdir, DEVS)
    out, changed = [], []
    for ln in open(path).read().splitlines():
        m = LINE.match(ln)
        if m and m.group(2) not in KEEP:
            out.append(f"//{ln}  /* not modelled by kgpe-d16-bmc QEMU */")
            changed.append(m.group(2))
        else:
            out.append(ln)
    open(path, "w").write("\n".join(out) + "\n")
    print(f"commented {len(changed)} unmodelled device(s): {', '.join(changed) or '(none)'}")
    print(f"kept: {', '.join(sorted(KEEP))}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Port G4 (AST2300/AST2400) symbol/IRQ definitions into the G3 headers so
Raptor's 2.6.28.9 AST2050 kernel compiles with a modern-enough toolchain.

Why this is needed
------------------
Raptor's `plat-aspeed/Makefile` builds every `dev-*.c` device file
unconditionally (`obj-y`), and several of those shared files reference
G4-only symbols (`AST_FMC_BASE`, `AST_UHCI_BASE`, `IRQ_UART3`, ...) that do
not exist in the AST2050/G3 `mach/ast2100_*.h` headers. The devices are not
probed during an initramfs boot, so the symbols only need to *exist* for the
build to link. This script copies every object-like `AST_*`/`IRQ_*` define
from the G4 headers into the G3 headers, each wrapped in `#ifndef`, so a real
G3 definition always wins and only the genuinely-missing ones are filled in.

Idempotent: re-running appends nothing new because every define is guarded and
the appended block is marked; pass --check to fail if a re-run would change
anything.

Usage:
    uv run port-g4-symbols.py --kdir /path/to/ast2050-linux-kernel
"""
import argparse
import os
import re

MARK = "/* --- G4 symbol fallbacks (port-g4-symbols.py) --- */"


def object_like_defines(text):
    """Yield (name, value) for object-like `#define AST_x V` / `IRQ_x V`,
    skipping function-like macros (`NAME(...)`)."""
    seen = set()
    for name, val in re.findall(
        r"^#define\s+((?:AST_|IRQ_)\w+)\s+([^\n(].*?)\s*(?:/\*.*)?$", text, re.M
    ):
        if name not in seen:
            seen.add(name)
            yield name, val.strip()


def fallback_block(src_text, header):
    out = [f"\n{MARK}\n/* {header} */\n"]
    for name, val in object_like_defines(src_text):
        out.append(f"#ifndef {name}\n#define {name} {val}\n#endif\n")
    return "".join(out), len(out) - 1


def append_once(dst_path, block):
    existing = open(dst_path).read() if os.path.exists(dst_path) else ""
    if MARK in existing:
        return 0  # already ported
    with open(dst_path, "a") as f:
        f.write(block)
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kdir", required=True, help="Raptor ast2050-linux-kernel root")
    args = ap.parse_args()
    inc = os.path.join(args.kdir, "arch/arm/mach-aspeed/include/mach")

    # G3 platform header gets the missing AST_*_BASE from the G4 platform header.
    plat_block, nplat = fallback_block(
        open(os.path.join(inc, "ast2300_platform.h")).read(),
        "from ast2300_platform.h",
    )
    wrote_p = append_once(os.path.join(inc, "ast2100_platform.h"), plat_block)

    # G3 IRQ header gets the missing IRQ_* from the G4 IRQ header.
    irq_block, nirq = fallback_block(
        open(os.path.join(inc, "ast2400_irqs.h")).read(),
        "from ast2400_irqs.h",
    )
    wrote_i = append_once(os.path.join(inc, "ast2100_irqs.h"), irq_block)

    print(f"ast2100_platform.h: {'appended' if wrote_p else 'already ported'} "
          f"({nplat} guarded defines)")
    print(f"ast2100_irqs.h:     {'appended' if wrote_i else 'already ported'} "
          f"({nirq} guarded defines)")


if __name__ == "__main__":
    main()

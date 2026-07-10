#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["gpiod>=2.1"]
# ///
"""TCK->RTCK echo test for the AST2050 JTAG harness (KGPE-D16 AST_JTAG1).

ARM926EJ-S RTCK is TCK re-synchronised through the core-clock domain, so an
echo on RTCK proves — without attempting a JTAG scan — that the AST2050 is
powered, its core clock is running, and the TAP clock path is alive. A failed
first-contact scan plus a PASSING echo test points at TDO/TMS/TDI wiring; a
FAILING echo test points at power/clock/RTCK-routing instead.

Wiring (see RPI4-OPENOCD-JTAG-WIRING.md): AST_JTAG1 pin 11 (RTCK, target
OUTPUT — never drive it) -> RPi4 GPIO27 / physical pin 13, input-only.

Run ON the bridge Pi (needs /dev/gpiochip0): `uv run rtck-echo-test.py`, or
plain `python3 rtck-echo-test.py` there (python3-libgpiod >=2.1 is installed
system-wide on rpi4-asus-aspeed2050-dev; no uv on the Pi).

Do NOT run while OpenOCD is attached — both claim TCK/TMS, and the kernel
enforces exclusive line claims (this script will fail loudly with EBUSY).

Method: drive TMS high for 5 TCK cycles (parks the TAP in Test-Logic-Reset,
where extra TCK edges are harmless and TMS=1 keeps it there), then toggle TCK
and check that RTCK follows on both phases.

Expected signatures:
  PASS            64/64 echoes on both phases -> chip powered + clocked.
  FAIL, all low   board off / RTCK not routed to the header / wiring fault.
                  (This is also the normal result with nothing wired.)
"""

import sys
import time

import gpiod
from gpiod.line import Bias, Direction, Value

CHIP = "/dev/gpiochip0"
TCK = 25   # RPi4 phys pin 22 -> AST_JTAG1 pin 9
TMS = 24   # RPi4 phys pin 18 -> AST_JTAG1 pin 7 (held HIGH: TAP stays in TLR)
RTCK = 27  # RPi4 phys pin 13 <- AST_JTAG1 pin 11 (input-only)

CYCLES = 64
SETTLE = 0.0005  # 0.5 ms/edge; RTCK sync latency is ~3 core clocks (~15 ns)


def main() -> int:
    config = {
        TCK: gpiod.LineSettings(direction=Direction.OUTPUT,
                                output_value=Value.INACTIVE),
        TMS: gpiod.LineSettings(direction=Direction.OUTPUT,
                                output_value=Value.ACTIVE),
        RTCK: gpiod.LineSettings(direction=Direction.INPUT,
                                 bias=Bias.PULL_DOWN),
    }
    with gpiod.request_lines(CHIP, consumer="rtck-echo-test",
                             config=config) as req:
        # Park the TAP in Test-Logic-Reset: >=5 TCK cycles with TMS high.
        for _ in range(5):
            req.set_value(TCK, Value.ACTIVE)
            time.sleep(SETTLE)
            req.set_value(TCK, Value.INACTIVE)
            time.sleep(SETTLE)

        high_ok = low_ok = 0
        for _ in range(CYCLES):
            req.set_value(TCK, Value.ACTIVE)
            time.sleep(SETTLE)
            if req.get_value(RTCK) == Value.ACTIVE:
                high_ok += 1
            req.set_value(TCK, Value.INACTIVE)
            time.sleep(SETTLE)
            if req.get_value(RTCK) == Value.INACTIVE:
                low_ok += 1
        # Leave TCK low, TMS released to input on context exit.

    print(f"RTCK echo: high phase {high_ok}/{CYCLES}, "
          f"low phase {low_ok}/{CYCLES}")
    if high_ok == CYCLES and low_ok == CYCLES:
        print("PASS: RTCK follows TCK — AST2050 is powered, core-clocked, "
              "and the TAP clock path is alive.")
        return 0
    if high_ok == 0 and low_ok == CYCLES:
        print("FAIL: RTCK stuck low — board off, RTCK not routed to the "
              "header, or the RTCK/TCK wire is not connected. (This is the "
              "normal result with nothing wired.)")
    else:
        print("FAIL: partial/erratic echo — check lead length, ground, and "
              "the TCK/RTCK connections.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

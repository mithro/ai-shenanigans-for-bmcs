"""Run a qemu-model bare-metal firmware test and parse its `[FWT]` transcript.

Used by the per-peripheral integration tests (pytest). Shells out to
`fwtest/build.py` so there is a single source of truth for how a test is built
and booted under `-M kgpe-d16-bmc`. Nothing here touches real hardware.

The same transcript grammar is emitted by the SAME .elf on real silicon (via the
RPi rig), so a future HIL runner can produce a `Transcript` the identical way and
the two can be asserted equal — that is the "u-boot & linux behave identically on
QEMU and hardware" proof, at the register level.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MODEL = Path(__file__).resolve().parent.parent          # .../qemu-model
BUILD_PY = MODEL / "fwtest" / "build.py"
LOCAL_QEMU = MODEL.parent / "qemu-firmware/qemu/build/qemu-system-arm"
SIBLING_QEMU = MODEL.parents[2] / "d16-qemu/tmp/qemu-dev/build/qemu-system-arm"
CC = "arm-none-eabi-gcc"


@dataclass
class Transcript:
    regs: dict[str, int]        # label -> value
    kvs: dict[str, int]         # key -> value
    checks: list[tuple]         # (label, ok, got, want)
    fails: int
    halted: bool
    raw: str

    def reg(self, label: str) -> int:
        return self.regs[label]


def preconditions() -> str | None:
    """Return a human skip-reason if this environment can't run fwtests, else None."""
    if shutil.which(CC) is None:
        return f"{CC} not installed (gcc-arm-none-eabi)"
    if not (LOCAL_QEMU.exists() or SIBLING_QEMU.exists()):
        return "no qemu-system-arm with kgpe-d16-bmc built (run scripts/build-qemu.sh)"
    return None


def qemu_preconditions() -> str | None:
    """Skip-reason for tests that only need the built QEMU (no cross-compiler)."""
    if not (LOCAL_QEMU.exists() or SIBLING_QEMU.exists()):
        return "no qemu-system-arm with kgpe-d16-bmc built (run scripts/build-qemu.sh)"
    return None


def qemu_path() -> Path:
    """The qemu-system-arm carrying the kgpe-d16-bmc machine (see preconditions)."""
    return LOCAL_QEMU if LOCAL_QEMU.exists() else SIBLING_QEMU


def parse(text: str) -> Transcript:
    regs: dict[str, int] = {}
    kvs: dict[str, int] = {}
    checks: list[tuple] = []
    fails = 0
    halted = False
    for ln in text.splitlines():
        if not ln.startswith("[FWT]"):
            continue
        p = ln.split()
        kind = p[1] if len(p) > 1 else ""
        if kind == "reg":                      # [FWT] reg <label> <addr> = <val>
            regs[p[2]] = int(p[-1], 16)
        elif kind == "kv":                     # [FWT] kv <key> = <val>
            kvs[p[2]] = int(p[-1], 16)
        elif kind == "check":                  # [FWT] check <label> P/F got= want=
            checks.append((p[2], p[3] == "PASS",
                           int(p[4].split("=")[1], 16),
                           int(p[5].split("=")[1], 16)))
        elif kind == "end":                    # [FWT] end <name> checks= fails=
            for tok in p:
                if tok.startswith("fails="):
                    fails = int(tok.split("=")[1], 16)
        elif kind == "halt":
            halted = True
    return Transcript(regs, kvs, checks, fails, halted, text)


def run_fwtest(name: str, qemu: str | None = None, timeout: float = 20.0) -> Transcript:
    cmd = [sys.executable, str(BUILD_PY), name, "--run", "--timeout", str(timeout)]
    if qemu:
        cmd += ["--qemu", qemu]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return parse(r.stdout + r.stderr)

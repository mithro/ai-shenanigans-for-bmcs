#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Build and (optionally) run one AST2050 bare-metal firmware test under QEMU.

Each test is `peripherals/<name>/fwtest.c`; it is linked with the shared harness
(crt0.S + console.c + main.c) at the DRAM base and booted with
`qemu-system-arm -M kgpe-d16-bmc -kernel <elf>`. The test prints a deterministic
`[FWT]` transcript over the console UART and then spins; we capture the serial
log up to the `[FWT] halt` sentinel and report pass/fail.

The SAME .elf is intended to run on real silicon (via the RPi rig) later, so the
transcripts can be diffed byte-for-byte. Nothing here touches hardware.

Examples:
    uv run fwtest/build.py smoke --run
    uv run fwtest/build.py scu --run --qemu /path/to/qemu-system-arm
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent           # .../qemu-model/fwtest
MODEL = HERE.parent                              # .../qemu-model
MACHINE = "kgpe-d16-bmc"
HALT_SENTINEL = "[FWT] halt"

# Prebuilt custom QEMU with the kgpe-d16-bmc machine (from the d16-qemu stack).
# Override with --qemu or $QEMU_AST2050. The reproducible build is the fork's
# scripts/build-qemu.sh; this default just enables fast local iteration.
# Where to find a qemu-system-arm carrying the kgpe-d16-bmc machine, in order:
#  1. this worktree's own build (the one we edit + rebuild) -- preferred;
#  2. the sibling d16-qemu worktree's prebuilt (fast bootstrap before we build).
LOCAL_QEMU = MODEL.parent / "qemu-firmware/qemu/build/qemu-system-arm"
SIBLING_QEMU = MODEL.parents[2] / "d16-qemu/tmp/qemu-dev/build/qemu-system-arm"
PREBUILT_QEMU = LOCAL_QEMU if LOCAL_QEMU.exists() else SIBLING_QEMU

CC = "arm-none-eabi-gcc"
OBJCOPY = "arm-none-eabi-objcopy"
CFLAGS = [
    "-mcpu=arm926ej-s", "-marm", "-mfloat-abi=soft",
    "-ffreestanding", "-fno-pic", "-fno-pie", "-fno-builtin",
    "-Wall", "-Wextra", "-Werror", "-O2", "-g",
]


def die(msg: str) -> "None":
    sys.stderr.write(f"build.py: error: {msg}\n")
    raise SystemExit(2)


def resolve_qemu(arg: str | None) -> Path:
    cand = arg or os.environ.get("QEMU_AST2050")
    if cand:
        p = Path(cand)
        if not p.exists():
            die(f"--qemu {p} does not exist")
        return p
    if PREBUILT_QEMU.exists():
        return PREBUILT_QEMU
    onpath = shutil.which("qemu-system-arm")
    if onpath:
        return Path(onpath)
    die("no qemu-system-arm found; pass --qemu or set $QEMU_AST2050")


def check_machine(qemu: Path) -> None:
    out = subprocess.run([str(qemu), "-M", "help"], capture_output=True,
                         text=True, check=True).stdout
    if MACHINE not in out:
        die(f"{qemu} has no '{MACHINE}' machine (build the mithro/qemu fork)")


def build(name: str, outdir: Path) -> Path:
    test_c = MODEL / "peripherals" / name / "fwtest.c"
    if not test_c.exists():
        die(f"no such test: {test_c}")
    if shutil.which(CC) is None:
        die(f"{CC} not found (install gcc-arm-none-eabi)")
    outdir.mkdir(parents=True, exist_ok=True)
    elf = outdir / f"{name}.elf"
    sources = [HERE / "crt0.S", HERE / "console.c", HERE / "main.c", test_c]
    cmd = [CC, *CFLAGS, f"-I{HERE}", "-T", str(HERE / "fwtest.ld"),
           *[str(s) for s in sources], "-o", str(elf),
           "-Wl,--build-id=none", "-nostdlib"]
    print("[build]", " ".join(cmd))
    subprocess.run(cmd, check=True)
    subprocess.run([OBJCOPY, "-O", "binary", str(elf), str(elf.with_suffix(".bin"))],
                   check=True)
    print(f"[build] {elf}  ({elf.stat().st_size} bytes elf)")
    return elf


def run(qemu: Path, elf: Path, outdir: Path, timeout: float) -> str:
    check_machine(qemu)
    serial = outdir / f"{elf.stem}.serial.log"
    if serial.exists():
        serial.unlink()
    argv = [str(qemu), "-M", MACHINE, "-m", "128", "-display", "none",
            "-serial", f"file:{serial}", "-kernel", str(elf), "-no-reboot"]
    print("[run]", " ".join(argv))
    proc = subprocess.Popen(argv)
    deadline = time.monotonic() + timeout
    transcript = ""
    try:
        while time.monotonic() < deadline:
            if serial.exists():
                transcript = serial.read_text(errors="replace")
                if HALT_SENTINEL in transcript:
                    break
            if proc.poll() is not None:
                break
            time.sleep(0.1)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    if serial.exists():
        transcript = serial.read_text(errors="replace")
    return transcript


def summarize(transcript: str) -> int:
    fwt = [ln for ln in transcript.splitlines() if ln.startswith("[FWT]")]
    print("\n--- transcript ---")
    print("\n".join(fwt) if fwt else "(no [FWT] output captured)")
    print("--- end ---")
    if not fwt:
        print("RESULT: NO OUTPUT (console UART / -kernel boot path?)")
        return 3
    if HALT_SENTINEL not in transcript:
        print("RESULT: INCOMPLETE (no halt sentinel; timed out?)")
        return 3
    end = [ln for ln in fwt if ln.startswith("[FWT] end")]
    fails = 0
    for ln in end:
        for tok in ln.split():
            if tok.startswith("fails="):
                fails = int(tok.split("=")[1], 16)
    print(f"RESULT: {'PASS' if fails == 0 else 'FAIL'} ({fails} failed check(s))")
    return 0 if fails == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("name", nargs="?", default="smoke",
                    help="peripheral test name (dir under peripherals/)")
    ap.add_argument("--run", action="store_true", help="boot the test under QEMU")
    ap.add_argument("--qemu", help="path to qemu-system-arm with kgpe-d16-bmc")
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--out", default=str(MODEL / "tmp" / "fwtest"))
    args = ap.parse_args()

    outdir = Path(args.out)
    elf = build(args.name, outdir)
    if not args.run:
        return 0
    qemu = resolve_qemu(args.qemu)
    print(f"[run] qemu = {qemu}")
    transcript = run(qemu, elf, outdir, args.timeout)
    return summarize(transcript)


if __name__ == "__main__":
    raise SystemExit(main())

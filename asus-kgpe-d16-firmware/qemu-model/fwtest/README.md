# fwtest — bare-metal firmware-test harness (AST2050)

A tiny freestanding ARM926EJ-S program that pokes one peripheral and prints a
**deterministic, greppable** `[FWT]` transcript over the console UART, then spins.
The **same binary** is meant to run on QEMU (`-M kgpe-d16-bmc -kernel test.elf`)
and, later, on real silicon via the RPi rig — so the two transcripts can be
diffed byte-for-byte. That diff is how we prove "emulation ≡ hardware" per device.

## Files

| File | Role |
|---|---|
| `crt0.S` | reset entry: stack + zero BSS + call `fwtest_main` (linked at DRAM 0x40000000) |
| `fwtest.ld` | linker script (loads via `-kernel`) |
| `ast2050.h` | MMIO base addresses + `readl`/`writel` |
| `console.c/.h` | console UART (0x1E784000) + the `[FWT]` report protocol |
| `main.c` | init console → `fwt_begin` → `fwtest_run` → `fwt_end` |
| `harness.h` | the contract a test implements (`fwtest_name`, `fwtest_run`) |
| `build.py` | compile + (optionally) boot under QEMU, capture serial, report |

A test is `../peripherals/<name>/fwtest.c` defining `fwtest_name` and
`fwtest_run()`.

## Report grammar (deterministic — no timestamps/addresses that vary)

```
[FWT] begin <name>
[FWT] reg  <label> <addr:08x> = <val:08x>
[FWT] kv   <key> = <val:08x>
[FWT] check <label> <PASS|FAIL> got=<08x> want=<08x>
[FWT] end  <name> checks=<n> fails=<n>
[FWT] halt
```

`check` encodes the **golden (real-silicon)** expectation, so a test may FAIL
against an unfaithful model on purpose until that model is fixed.

## Usage

```sh
# build only
uv run fwtest/build.py smoke
# build + boot under the custom QEMU, print transcript, exit non-zero on FAIL
uv run fwtest/build.py smoke --run
# point at a specific qemu-system-arm (else $QEMU_AST2050, else the sibling
# d16-qemu prebuilt, else PATH)
uv run fwtest/build.py scu --run --qemu /path/to/qemu-system-arm
```

Requires `gcc-arm-none-eabi` and a `qemu-system-arm` carrying the `kgpe-d16-bmc`
machine (the `mithro/qemu` fork; build via `../qemu-firmware/scripts/build-qemu.sh`).
Build artifacts land in `../tmp/fwtest/` (gitignored).

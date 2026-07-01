# firmware-testbench

One test bench, two backends. The same board-level assertions run against **QEMU**
in CI and against **real hardware** on the RPi OpenOCD/UART rig — so a firmware
image proven in emulation can be re-verified on silicon by changing one flag.

```python
from firmware_testbench import make_target, TargetConfig

cfg = TargetConfig(board="c410x", kernel="uImage-c410x",
                   dtb="aspeed-bmc-dell-c410x.dtb", initrd="uInitrd-c410x")
with make_target("qemu", cfg) as t:          # or "hil"
    t.console().expect(r"c410x-bmc login:", timeout=240)
```

## Layout

```
firmware_testbench/
  console.py            transport-agnostic expect engine (fake-stream testable)
  parsers.py            i2cdetect / sysfs / key=value parsers
  target.py             Target ABC + TargetConfig + backend registry/factory
  backends/qemu.py      build_qemu_argv() + QEMUTarget (serial + ssh hostfwd)
  backends/hil.py       build_openocd_flash_cmd() + HILTarget (rig wiring TBD)
  benches/board_c410x.py  expected I2C device map + check_i2c_map()
tests/                  unit tests (no QEMU / no hardware needed)
```

## Design

- **Pure where it counts.** The expect loop, the parsers, and the QEMU/OpenOCD
  command builders are pure functions of their inputs, so they are unit-tested
  with fake streams and a fake clock — no real IO, no wall-clock sleeps, fully
  deterministic. The process/socket wiring is a thin shell exercised by
  integration CI once the QEMU fork is built.
- **Fail loud.** Parsers raise on malformed input rather than returning a
  wrong-but-plausible result; `expect` raises `ExpectTimeout` carrying the
  console buffer.
- **Backend registry.** Backends self-register; `make_target("qemu"|"hil", cfg)`
  is the only entry point a bench needs.

## Running the tests

```sh
uv run --with pytest python -m pytest -q      # 21 unit tests, ~0.03s
```

## Roadmap

- Refactor `asus-kgpe-d16-firmware/qemu-firmware/scripts/{run-qemu,ssh-test}.py`
  and `hpe-ipdu-firmware/uboot-port/test/qemu_smoke_test.py` onto this module so
  the existing `boot-ssh` / `boot-raptor` jobs run through it unchanged.
- Add SSH to `QEMUTarget` (paramiko or subprocess `ssh`), hwmon/GPIO ops, and
  the `board_kgpe_d16` / `board_ipdu` benches.
- Wire the `hil` backend to the physical rig when the rpi4-pmod boards arrive.

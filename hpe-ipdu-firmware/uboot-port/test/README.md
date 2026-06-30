# NS9360 U-Boot QEMU smoke test

Boots the HPE iPDU U-Boot port on the QEMU `ns9360` machine and checks basic
functionality (prompt, `version`, `bdinfo`, SDRAM/flash reads, memory
write-readback, `gpio`, `i2c`, `printenv`).

## Reproduce from a fresh clone

```sh
# 1. Check out the u-boot and qemu submodules
git submodule update --init --recursive \
    ../u-boot ../qemu/qemu-10.0.7

# 2. Build qemu-system-arm (with the ns9360 machine)
( cd ../qemu/qemu-10.0.7 && ./configure --target-list=arm-softmmu && make -j"$(nproc)" )

# 3. Build U-Boot and assemble the 8 MiB NOR flash image (flash0.img)
uv run python3 mkflash.py            # CROSS_COMPILE defaults to arm-none-eabi-

# 4. Run the smoke test
uv run python3 qemu_smoke_test.py
```

Expected: `Results: 10 passed, 0 failed of 10`.

## Files

| File | Purpose |
|------|---------|
| `qemu_smoke_test.py` | Boots U-Boot under `qemu-system-arm -M ns9360` and runs the checks |
| `mkflash.py` | Builds U-Boot (if needed) and pads `u-boot.bin` into `flash0.img` |
| `flash0.img` | Built 8 MiB NOR image (gitignored — produced by `mkflash.py`) |

## Flash layout

`flash0.img` is NOR flash **bank 0**, mapped at `0x40000000` (= `CONFIG_TEXT_BASE`):

```
0x000000  u-boot.bin     reset vector runs in place
   ...    0xFF           erased NOR, padded to 8 MiB
```

The U-Boot environment lives in flash **bank 1** (`CONFIG_ENV_ADDR = 0x507F0000`),
which the smoke test does not back with a drive, so U-Boot boots with its
compiled-in default environment (the `bad CRC, using default environment`
notice at boot is expected).

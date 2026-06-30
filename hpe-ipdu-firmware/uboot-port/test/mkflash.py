#!/usr/bin/env python3
"""Build flash0.img -- the NOR flash image booted by the QEMU ns9360 smoke test.

The image is flash bank 0 of the Digi NS9360 (mapped at 0x40000000 by the
qemu `ns9360` machine and by CONFIG_TEXT_BASE in hpe_ipdu_defconfig):

    offset 0x000000  u-boot.bin            (reset vector runs in place at 0x40000000)
    ...              0xFF                   (erased NOR) up to 8 MiB

The U-Boot environment lives in flash *bank 1* (CONFIG_ENV_ADDR = 0x507F0000),
which the smoke test does not back with a drive, so U-Boot boots with its
built-in default environment. This image therefore contains only U-Boot.

Usage (from anywhere -- paths resolve relative to this file):

    uv run python3 mkflash.py             # build U-Boot (if needed), then assemble
    uv run python3 mkflash.py --no-build  # assemble from an existing u-boot/u-boot.bin
    uv run python3 mkflash.py -o /tmp/x.img   # write somewhere other than ./flash0.img

CROSS_COMPILE defaults to arm-none-eabi- and can be overridden via the
environment, e.g. `CROSS_COMPILE=arm-linux-gnueabi- uv run python3 mkflash.py`.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UBOOT = os.path.normpath(os.path.join(HERE, "..", "u-boot"))
UBOOT_BIN = os.path.join(UBOOT, "u-boot.bin")
DEFAULT_OUT = os.path.join(HERE, "flash0.img")

DEFCONFIG = "hpe_ipdu_defconfig"
FLASH_SIZE = 8 * 1024 * 1024  # 8 MiB NOR bank 0 (qemu ns9360 @ 0x40000000)
PAD_BYTE = 0xFF               # erased NOR state
CROSS_COMPILE = os.environ.get("CROSS_COMPILE", "arm-none-eabi-")


def build_uboot():
    """Build U-Boot in-tree in the submodule (incremental if already built)."""
    if not os.path.exists(os.path.join(UBOOT, "Makefile")):
        sys.exit(
            f"U-Boot source not found at {UBOOT}\n"
            f"Initialise the submodule first:\n"
            f"    git submodule update --init {UBOOT}"
        )
    env = dict(os.environ, CROSS_COMPILE=CROSS_COMPILE)
    if not os.path.exists(os.path.join(UBOOT, ".config")):
        print(f"==> Configuring {DEFCONFIG}")
        subprocess.run(["make", DEFCONFIG], cwd=UBOOT, env=env, check=True)
    print(f"==> Building U-Boot (CROSS_COMPILE={CROSS_COMPILE})")
    subprocess.run(["make", f"-j{os.cpu_count() or 1}"], cwd=UBOOT, env=env, check=True)


def assemble(out_path):
    """Pad u-boot.bin to FLASH_SIZE with PAD_BYTE and write the flash image."""
    if not os.path.exists(UBOOT_BIN):
        sys.exit(
            f"{UBOOT_BIN} not found.\n"
            f"Build U-Boot first (run without --no-build), or:\n"
            f"    make -C {UBOOT} {DEFCONFIG} && make -C {UBOOT} CROSS_COMPILE={CROSS_COMPILE}"
        )
    data = open(UBOOT_BIN, "rb").read()
    if len(data) > FLASH_SIZE:
        sys.exit(f"u-boot.bin is {len(data)} bytes, larger than the {FLASH_SIZE}-byte flash")
    image = data + bytes([PAD_BYTE]) * (FLASH_SIZE - len(data))
    with open(out_path, "wb") as f:
        f.write(image)
    print(
        f"==> Wrote {out_path}\n"
        f"    {FLASH_SIZE} bytes ({FLASH_SIZE // (1024 * 1024)} MiB); "
        f"u-boot.bin = {len(data)} bytes at offset 0x0, padded with 0x{PAD_BYTE:02X}"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-build", action="store_true",
                    help="skip the U-Boot build; assemble from an existing u-boot.bin")
    ap.add_argument("-o", "--output", default=DEFAULT_OUT,
                    help=f"output image path (default: {DEFAULT_OUT})")
    args = ap.parse_args()
    if not args.no_build:
        build_uboot()
    assemble(args.output)


if __name__ == "__main__":
    main()

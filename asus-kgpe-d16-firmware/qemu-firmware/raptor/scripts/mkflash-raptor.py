#!/usr/bin/env python3
"""Assemble an 8 MB SPI-flash image that boots the Raptor AST2050 kernel via
ATAGS on the kgpe-d16-bmc QEMU machine.

Boot path (no device tree):
  OpenBMC U-Boot  ->  setenv machid 8888 (MACH_TYPE_ASPEED)  ->  bootm K I
  with only two args (kernel, initrd) so U-Boot passes an ATAG list + machine
  id instead of a flattened device tree — which is what the 2.6.28.9 kernel
  (MACHINE_START(ASPEED, ...)) expects.

Layout:  uboot@0  env@0xF0000  kernel@0x100000  initrd@0x500000

Usage:
    uv run mkflash-raptor.py --uboot u-boot.bin --kernel uImage-raptor \\
        --initrd uInitrd-kgpe-d16 --out flash-raptor.img
"""
import argparse
import subprocess

ENV = (
    "bootdelay=0\n"
    "machid=8888\n"
    # Raptor kernel UART2 == 0x1e784000 (the UART QEMU's -serial is wired to);
    # offer every plausible ttyS index since the G3 kernel's numbering differs
    # from the modern aspeed-g4 kernel's ttyS4.
    "bootargs=console=ttyS0,115200n8 console=ttyS1,115200n8 "
    "console=ttyS2,115200n8 console=ttyS4,115200n8 earlyprintk\n"
    "bootcmd=cp.b 0x20100000 0x41000000 0x200000; "
    "cp.b 0x20500000 0x45000000 0x200000; bootm 0x41000000 0x45000000\n"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uboot", required=True)
    ap.add_argument("--kernel", required=True, help="uImage-raptor")
    ap.add_argument("--initrd", required=True, help="uInitrd (BusyBox+dropbear)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="0x800000")
    args = ap.parse_args()

    env_txt, env_img = args.out + ".env.txt", args.out + ".env.img"
    open(env_txt, "w").write(ENV)
    subprocess.run(["mkenvimage", "-s", "0x10000", "-o", env_img, env_txt],
                   check=True)

    flash = bytearray(b"\x00" * int(args.size, 0))

    def place(path, off):
        data = open(path, "rb").read()
        flash[off:off + len(data)] = data
        print(f"  {hex(off):>9} {len(data):>9} {path}")

    place(args.uboot, 0x000000)
    place(env_img, 0x0F0000)
    place(args.kernel, 0x100000)
    place(args.initrd, 0x500000)
    open(args.out, "wb").write(flash)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Assemble the 8 MB SPI boot flash for the kgpe-d16-bmc machine: U-Boot + a
U-Boot env (bootcmd) + the kernel uImage + initramfs uInitrd + the dtb, at the
offsets the env's bootcmd expects.

Layout (FMC CS0 is XIP-mapped at 0x20000000):
  0x000000  u-boot.bin
  0x080000  dtb            -> 0x20080000
  0x0F0000  u-boot env     (CONFIG_ENV_OFFSET for evb-ast2400)
  0x100000  kernel uImage  -> 0x20100000
  0x500000  initrd uInitrd -> 0x20500000

bootcmd copies kernel/initrd/dtb from flash into DRAM (booting bootm straight
from the XIP flash leaves the kernel silent), then `bootm`.
"""
import argparse
import subprocess
from pathlib import Path

# The kernel copy must span the whole 4 MB kernel slot (0x100000..0x500000):
# the NFS-root kernel config (NFS v3/v4 + IP_PNP + SUNRPC + LOCKD + DEVTMPFS,
# built-in) grew the uImage past 3 MB, so a 0x300000 (3 MB) copy truncated it and
# bootm got a corrupt kernel (C2-full-chain regression). Copying 0x400000 reads
# exactly the kernel slot; the tail padding past the uImage is harmless (bootm
# uses the uImage header length). Direct -kernel boots (C2/C5) never hit this.
ENV_TEXT = (
    "bootdelay=0\n"
    "bootargs=console=ttyS4,115200n8 earlyprintk\n"
    "bootcmd=cp.b 0x20100000 0x41000000 0x400000; "
    "cp.b 0x20500000 0x45000000 0x200000; "
    "cp.b 0x20080000 0x44000000 0x10000; "
    "bootm 0x41000000 0x45000000 0x44000000\n"
)
LAYOUT = [("uboot", 0x000000), ("dtb", 0x080000), ("env", 0x0F0000),
          ("kernel", 0x100000), ("initrd", 0x500000)]
SIZE = 0x1000000  # 16 MB (matches the kgpe-d16-bmc FMC chip, mx25l12805d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uboot", required=True)
    ap.add_argument("--kernel", required=True, help="kernel uImage")
    ap.add_argument("--initrd", required=True, help="initramfs uInitrd")
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--out", required=True, help="output flash image")
    args = ap.parse_args()

    out = Path(args.out)
    env_img = out.parent / "uboot-env.img"
    out.parent.mkdir(parents=True, exist_ok=True)
    (out.parent / "env.txt").write_text(ENV_TEXT)
    subprocess.run(["mkenvimage", "-s", "0x10000", "-o", str(env_img),
                    str(out.parent / "env.txt")], check=True)

    parts = {"uboot": args.uboot, "dtb": args.dtb, "env": str(env_img),
             "kernel": args.kernel, "initrd": args.initrd}
    flash = bytearray(b"\x00" * SIZE)
    for name, off in LAYOUT:
        data = Path(parts[name]).read_bytes()
        if off + len(data) > SIZE:
            raise SystemExit(f"{name} ({len(data)}) overflows flash at {off:#x}")
        flash[off:off + len(data)] = data
        print(f"  {off:#08x}  {len(data):>8}  {name}")
    out.write_bytes(flash)
    print(f"flash image -> {out} ({SIZE // (1024 * 1024)} MB)")


if __name__ == "__main__":
    main()

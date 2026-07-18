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

# Each region is copied from its XIP-flash address into DRAM before bootm, and the
# copy size MUST cover the whole file or bootm gets a truncated, bad-CRC image.
# Two regressions came from hardcoding these sizes too small:
#   * the NFS-root kernel grew past 3 MB -> a 0x300000 copy truncated the uImage
#     -> "corrupt kernel" (C2-full-chain);
#   * the usbip initramfs grew past 2 MB -> a 0x200000 copy truncated the uInitrd
#     -> "Verifying Checksum ... Bad Data CRC" -> bootm aborts (C2-full-chain).
# So DON'T hardcode copy sizes: compute each from the actual file (rounded up to a
# 64 KB erase block) and fail loud if it overflows its flash slot. Tail padding
# past the image is harmless (bootm uses the image header length). Direct -kernel
# boots (C2/C5) bypass U-Boot and never hit this.
ENV_TEMPLATE = (
    "bootdelay=0\n"
    "bootargs=console=ttyS4,115200n8 earlyprintk\n"
    "bootcmd=cp.b 0x20100000 0x41000000 {kernel_cp:#x}; "
    "cp.b 0x20500000 0x45000000 {initrd_cp:#x}; "
    "cp.b 0x20080000 0x44000000 0x10000; "
    "bootm 0x41000000 0x45000000 0x44000000\n"
)
LAYOUT = [("uboot", 0x000000), ("dtb", 0x080000), ("env", 0x0F0000),
          ("kernel", 0x100000), ("initrd", 0x500000)]
SIZE = 0x1000000  # 16 MB (matches the kgpe-d16-bmc FMC chip, mx25l12805d)
ERASE = 0x10000   # 64 KB erase block — round copy sizes up to this
KERNEL_SLOT = 0x500000 - 0x100000   # 0x400000 (4 MB): kernel .. initrd
INITRD_SLOT = SIZE - 0x500000       # 0xB00000 (11 MB): initrd .. end of flash


def roundup(n, align):
    return (n + align - 1) // align * align


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

    # Size the DRAM copies from the actual images so a grown kernel/initramfs can
    # never be silently truncated (bad-CRC bootm). Fail loud if either overflows
    # its flash slot rather than corrupting the neighbouring region.
    kernel_cp = roundup(Path(args.kernel).stat().st_size, ERASE)
    initrd_cp = roundup(Path(args.initrd).stat().st_size, ERASE)
    if kernel_cp > KERNEL_SLOT:
        raise SystemExit(
            f"kernel uImage copy {kernel_cp:#x} exceeds the {KERNEL_SLOT:#x} flash "
            f"slot (0x100000..0x500000) — grow the kernel slot / move initrd offset")
    if initrd_cp > INITRD_SLOT:
        raise SystemExit(
            f"initrd uInitrd copy {initrd_cp:#x} exceeds the {INITRD_SLOT:#x} flash "
            f"slot (0x500000..{SIZE:#x}) — shrink the initramfs or grow the flash")
    env_text = ENV_TEMPLATE.format(kernel_cp=kernel_cp, initrd_cp=initrd_cp)
    print(f"  copy sizes: kernel={kernel_cp:#x} initrd={initrd_cp:#x}")
    (out.parent / "env.txt").write_text(env_text)
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

# Building the Raptor AST2050 U-Boot for P2A boot

The canonical U-Boot for this SoC is Raptor Engineering's AST2050 port (board
`asus`, `board/aspeed/ast2050/`). It links at `-Ttext 0x00000000` and boots from
`0x0`, which is exactly where the DRAM→`0x0` remap points our loaded image — so
it drops straight into the P2A boot mechanism (`P2A-DRAM-BOOT-SEQUENCE.md §6a`,
`p2a-image-boot.py`). We only need `u-boot.bin` (the raw ARM binary), **not** the
host tools (`mkimage` etc.), which lets us sidestep the vintage-vs-modern build
quagmire.

## Source & toolchain

- Source: Raptor's U-Boot tree (`board/aspeed/ast2050`, `include/configs/asus.h`,
  `include/configs/ast2050.h`). Configured with `make asus_config`.
- Cross toolchain: `gcc-4.9.4-nolibc/arm-linux-gnueabi-` (the same one used for the
  C3/QEMU builds). Its `cc1` needs `libmpfr.so.4`; shim it to the system `.so.6`.

## Patches for real hardware

1. **Console baud → 1200** (`include/configs/asus.h`: `CONFIG_BAUDRATE 1200`). The
   Pi mini-UART capture on `/dev/serial-bmc-console` is byte-reliable at 1200 but
   flaky at the stock 38400/115200. (Switch the Pi to PL011 to keep 115200.)
2. **MCR04 → 4-bank, 64 MB** (`board/aspeed/ast2050/platform.S`: the
   `CONFIG_1G_DDRII` value `0x00000d89` → `0x00000585`). This KGPE-D16's DDR2 is
   **4-bank, 64 MB**; 8-bank aliased address bit 13, and the 128 MB capacity setting
   left a phantom 64–128 MB region that aliases onto U-Boot's own code (see
   `ddr2-init-p2a.py`, `tmp/dramsize.py`). *Mostly moot* because of the DDR2 skip
   below, but the matching value is set by M1.
3. **Init stack above the image** (`include/configs/asus.h`: `CONFIG_SYS_INIT_SP_ADDR`
   `SDRAM_BASE + 0x1000` → `+ 0x1000000`). The stock `+0x1000` puts the pre-relocation
   stack at `0x40000F00` — fine when code is in flash, but **it collides with our
   U-Boot image loaded at `0x40000000`** and corrupts the relocation code. Moving it
   16 MB up clears the ~164 KB image.

## The DDR2-init skip (why run-from-DRAM works)

`lowlevel_init` (`platform.S`) checks **`SCU40[6]`** early and, if set, branches
straight to `reg_lock` and returns — **skipping all SCU/DDR2 init**. Our
`ddr2-init-p2a.py` (M1) sets `SCU40 |= 0x40` after bringing DDR2 up, and SCU is
`PWRSTNin`-only reset so the flag survives the watchdog reset in the boot trick.
So when the ARM runs U-Boot from DRAM, `lowlevel_init` sees DDR2 is already up and
does **not** re-init it (which would crash, since `MCR34=1` makes DRAM inaccessible
mid-sequence while U-Boot is executing from it).

## Build recipe (produces u-boot.bin without the host tools)

```sh
cd raptor-uboot
XPREFIX=.../gcc-4.9.4-nolibc/arm-linux-gnueabi/bin/arm-linux-gnueabi-
mkdir -p xlibs && ln -sf /usr/lib/x86_64-linux-gnu/libmpfr.so.6 xlibs/libmpfr.so.4
make ARCH=arm CROSS_COMPILE=$XPREFIX asus_config
# libfdt clash fix in tools/Makefile HOSTCPPFLAGS: -idirafter $(SRCTREE)/include ->
#   -I $(SRCTREE)/include  AND add  -DLIBFDT_H   (only needed if building tools)
# SUBDIR_TOOLS= drops the u-boot ELF's build-order dep on the (unbuildable) host
#   tools, so u-boot.bin links without them:
LD_LIBRARY_PATH=$PWD/xlibs make ARCH=arm CROSS_COMPILE=$XPREFIX SUBDIR_TOOLS= u-boot.bin
# -> u-boot.bin (~164 KB, entry 0x0, board ast2050, baud 1200)
```

## Boot it over P2A

```sh
uv run asus-kgpe-d16-firmware/ddr2-init-p2a.py            # M1: DDR2 up (4-bank) + SCU40[6]
uv run asus-kgpe-d16-firmware/p2a-image-boot.py \
    --image u-boot.bin --baud 1200 --watch 30            # load + reset-boot trick + watch UART
```

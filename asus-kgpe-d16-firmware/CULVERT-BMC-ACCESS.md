# Reaching the AST2050 BMC in-band with culvert (P2A / AHB backdoor)

The AST2050 BMC on this board has **no functional firmware running** (no network,
no serial, no IPMI-over-LAN, no in-band KCS response — see
[`hardware-inventory/README.md`](hardware-inventory/README.md)). But its silicon
is still reachable: [**culvert**](https://github.com/amboar/culvert) can read and
write the BMC's **AHB** directly over the ASPEED **P2A (PCIe→AHB) bridge**, from
the host, **with the BMC CPU/firmware dead**. Verified **2026-07-08**.

## Result — P2A works
Running `culvert probe` (verbose) on the host walks the bridge drivers:

```
p2a        -> reads real AHB data:  0x1e6e207c = 0x00000202 (SCU silicon rev)
              probe then fails "-19": culvert doesn't know this SoC (AST2050
              predates its device table, which targets AST2400/2500/2600)
l2a        -> -95 (EOPNOTSUPP)
ilpc       -> reads 0xffffffff (that backdoor isn't enabled on this board)
devmem     -> -1 (only usable when running ON the BMC)
debug-uart -> skipped (no interface given)
```

So **P2A is the working path.** Raw AHB reads via `culvert p2a vga read <addr>`
return real data even though the high-level SoC-aware commands refuse the
unrecognised AST2050:

| Register | Value | Meaning |
|---|---|---|
| SCU7C `0x1e6e207c` | `0x00000202` | silicon revision (AST2050/AST1100 G3) |
| SCU00 `0x1e6e2000` | `0x00000000` | protection key — **SCU locked** (write `0x1688A8A8` to unlock writes) |
| SCU04 `0x1e6e2004` | `0x000ffe5c` | system reset control |
| SCU08 `0x1e6e2008` | `0xe3f00070` | clock selection |
| SCU70 `0x1e6e2070` | `0x00819582` | hardware strapping |
| SCU74 `0x1e6e2074` | `0x40048000` | hardware strapping 2 |

Register meanings are in [`ast2050.h`](ast2050.h) / [`hwreg.h`](hwreg.h).

## Why this matters
P2A is a **hardware backdoor** independent of the BMC firmware, so it's the
in-band route for the open-firmware bring-up: from the host we can read/write
BMC registers, unlock and drive the **SPI-flash controller** to dump/reflash the
BMC boot flash, load code into BMC SRAM, hold/release the ARM core via SCU
reset, etc. — the same operations the spispy/ULX3S path would do, but over PCIe.
culvert's SoC table would need an AST2050 entry for its high-level `sfc`/`read`/
`console` commands to work; until then, use raw `p2a`/`debug` with the AST2050
register map.

## Reproducing (culvert on the PXE-booted SystemRescue host)
SystemRescue has no toolchain and strips dev files from its live image, so:
```
# host needs internet (NAT on the Pi) + a correct clock (dead CMOS battery):
date -u -s "<current UTC>"                 # else TLS fails: "cert not yet valid"
printf 'nameserver 1.1.1.1\n' > /etc/resolv.conf
pacman -Sy --noconfirm base-devel meson ninja git dtc
pacman -S  --noconfirm glibc linux-api-headers   # force (NOT --needed): restore stripped static libs + headers
git clone https://github.com/amboar/culvert && cd culvert
CC=gcc meson setup build && ninja -C build
./build/src/culvert -v probe                 # p2a reads AHB
./build/src/culvert p2a vga read 0x1e6e207c  # raw AHB read
```
See [`HOST-NETBOOT.md`](HOST-NETBOOT.md) for the PXE boot + NAT setup.

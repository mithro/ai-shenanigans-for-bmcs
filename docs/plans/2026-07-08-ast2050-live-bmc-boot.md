# Booting a live AST2050 BMC on the real KGPE-D16

**Date:** 2026-07-08
**Why now:** [@mithro] chose "prioritize booting a live BMC" — it's the project's
end goal **and** it's the only way to finish verifying culvert's `sfc` / `console`
/ on-BMC `devmem`, which are provably un-verifiable on the current dead-BMC bench
(see [`../asus-kgpe-d16-firmware/CULVERT-G3-HARDWARE-RESULTS.md`](../asus-kgpe-d16-firmware/CULVERT-G3-HARDWARE-RESULTS.md)).

## Current hardware state (verified 2026-07-08)

The AST2050 is **cold**: ARM core held in reset, no firmware. Over P2A the DRAM
window (`0x40000000`) reads a fixed repeating pattern (`0x00101000 …`) → **DDR2
not initialised**; the SMC flash window reads `0`. P2A read/write of SoC
registers + DRAM works (that's how culvert reaches it).

## Assets we already have

- **Real DDR2 init**: `asus-kgpe-d16-firmware/platform.S` (Raptor's AST2050 DDR2
  bring-up asm) + `DDR2-INIT-REVERSE-ENGINEERING.md`. This is the piece QEMU
  never needed.
- **QEMU-verified firmware** (PR #16, `.worktrees/d16-qemu`): a U-Boot + Linux
  that boots on the `kgpe-d16-bmc` QEMU machine, plus the Raptor 2.6.28.9 and
  proprietary C410X stacks. **Caveat:** QEMU models DRAM, so its U-Boot does not
  necessarily do real DDR2 training — the real-HW boot needs U-Boot that runs
  `platform.S`-equivalent init.
- **Bridge/rig** (`rpi4-asus-aspeed2050-dev`): ULX3S on `/dev/ttyUSB0` = **UART to
  the AST2050 + spispy SPI-flash emulation of the BMC boot flash**; a physical
  `AST_JTAG1` header + Pi-GPIO OpenOCD; board power via Tasmota `au-plug-10`.
- **culvert G3 port** (`mithro/culvert @ ast2050-support`): P2A read/write of any
  AHB address — usable to drive SoC bring-up from the host.

## Boot paths (pick per what's ready)

1. **spispy (preferred if a real-HW image exists).** Build a U-Boot that does real
   AST2050 DDR2 init (integrate `platform.S`), assemble `U-Boot [+ kernel]` into a
   CE2 boot image, load it into the ULX3S spispy emulation, **reset the AST2050**
   → it fetches boot code from CE2 (0x0 / 0x14000000) → U-Boot inits DDR2 → boots.
   Observe on `/dev/ttyUSB0` (UART = console UART2, 115200 8N1).
   - *Unknowns to close:* the spispy image-load command/format on this ULX3S
     gateware (no `spispy`/`flashrom` tool found in `claude`'s PATH on the Pi);
     whether the AST2050 boot-strap selects CE2 SPI on this board.

2. **P2A SoC bring-up (culvert-native, no spispy).** From the host over P2A:
   (a) unlock SCU, run the `platform.S` DDR2 init sequence as P2A register writes;
   verify DRAM by write/read-back (pattern should stick, unlike now); (b) load a
   payload (U-Boot/Linux) into DRAM via P2A; (c) point the ARM boot vector / release
   the ARM core from reset via SCU. This proves each bring-up step independently and
   needs no spispy, but DDR2 training over P2A is delicate.

3. **JTAG (physical header + OpenOCD).** Halt the ARM at reset, load + run a payload
   via the `AST_JTAG1` header (already wired to the Pi GPIO — `RPI4-OPENOCD-JTAG-WIRING.md`).

## Milestones (each independently verifiable)

- [ ] **M1 — DDR2 alive.** Initialise the DDR2 controller (path 1's U-Boot, or path
      2's P2A sequence) and prove DRAM with a write/read-back over P2A (the
      repeating-pattern → real storage). This alone unblocks loading payloads.
- [ ] **M2 — U-Boot prompt** on `/dev/ttyUSB0` (serial console). Press a key within
      the boot delay; confirm `AST2050`/DRAM banner.
- [ ] **M3 — Linux boots** (our kernel + initramfs) to a shell/SSH.
- [ ] **M4 — culvert in-band:** run culvert on the BMC via `devmem`; `sfc` dump the
      real flash; `console` — closing the culvert-port verification.

## Coordination (mandatory — shared rig)

Booting the BMC **resets the AST2050 and reprograms the boot flash** — a major
state-mutating operation on a rig **instance-A** is actively using for host
BIOS/CMOS RE (battery going in "tomorrow", host PXE sessions). Per
`/home/claude/HARDWARE-COORDINATION.md`: **log + agree before any reset / spispy
write / DDR2 bring-up.** Sequence the BMC-boot work so it doesn't clobber
instance-A's host sessions (e.g. take a window, or after the battery/CMOS work).

## M-prep progress (2026-07-08): Raptor U-Boot build (offline, no rig)

Advanced PR #16's "one remaining task" (building Raptor's *own* AST2050 U-Boot,
the one with real DDR2 init). Reproducible recipe, verified working through
cross-compilation:

```sh
# toolchain (already on disk from the C3 build):
XPREFIX=.../.worktrees/d16-qemu/tmp/gcc-4.9.4-nolibc/arm-linux-gnueabi/bin/arm-linux-gnueabi-
# gcc-4.9.4's cc1 needs libmpfr.so.4 -> shim it to the system so.6:
mkdir -p xlibs && ln -sf /usr/lib/x86_64-linux-gnu/libmpfr.so.6 xlibs/libmpfr.so.4
# source: .worktrees/d16-qemu/tmp/raptor-uboot  (board config include/configs/ast2050.h; CONFIG_DDRII1G_200)
make ARCH=arm CROSS_COMPILE=$XPREFIX asus_config          # ✓ "Configuring for asus board..." (ast2050)
LD_LIBRARY_PATH=$PWD/xlibs make ARCH=arm CROSS_COMPILE=$XPREFIX u-boot.bin   # cross-compile ✓
```

**Verified working:** toolchain runs, the `asus`/ast2050 board config applies, and
the ARM target cross-compiles (mpfr shim fixed it). **Remaining build blocker:**
the documented vintage **libfdt host-tools clash** — U-Boot 2013.07's `tools/`
(`mkimage`/`image-sig`/`aisimage`) pull the modern system `/usr/include/libfdt.h`
alongside the bundled `include/libfdt.h` (different include guards → inline-fn
redefinitions). The AST2050 board uses **no FIT/FDT** (`ast2050.h` has no
`CONFIG_FIT`), so the fix is to stop the host image tools pulling libfdt (drop the
non-Aspeed `NOPED` image tools + neutralise `image-sig`'s libfdt include, or build
the `u-boot` ELF and `objcopy` it directly, bypassing `tools/`). A few more
iterations; **does not** need the rig.

> Note: even a finished `u-boot.bin` cannot *run* without the rig — loading it
> (spispy/JTAG) + resetting the AST2050 are the coordinated steps below.

## Immediate next steps

1. Confirm with instance-A the spispy image-load mechanism on this ULX3S (or that
   path 2/3 is preferred), and a coordination window.
2. Build a real-HW U-Boot with `platform.S` DDR2 init (from PR #16's U-Boot +
   Raptor's init), or script the P2A DDR2 sequence.
3. Execute **M1** first (DDR2), the highest-leverage, most-isolable step.

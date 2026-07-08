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

## Rig is now FULLY remote-controllable (established 2026-07-08)

Four independent channels (see the memory `hardware-rig-capabilities`):
- **Power** — Tasmota `au-plug-10` (`cmnd=Power on/off`; `cmnd=Status 8` power meter:
  ~3 W standby vs ~80–150 W running = host off/on). BIOS now **Restore-on-AC = Power On**
  (CMOS battery replaced, boot order = PXE) → plug-on auto-boots the host. Remote power-cycle
  for the M2 reset testing now works without a physical button.
- **PXE host** — boots SystemRescue → `root@192.168.77.138` (via the Pi). **Per-boot repair
  recipe** (host is diskless/tmpfs, SystemRescue strips dev files):
  `ssh-keygen -R 192.168.77.138` (host key regenerates); `printf 'nameserver 1.1.1.1\n' >/etc/resolv.conf`
  (dnsmasq gives no DNS); rebuild culvert with `pacman -S --noconfirm glibc linux-api-headers`
  **force-reinstall** (restores `libc_nonshared.a` + `linux/falloc.h`) then
  `git clone -b ast2050-support https://github.com/mithro/culvert && meson setup build && ninja -C build`.
  *TODO: bake the PXE/dnsmasq/http + NAT + DNS + culvert-build into a persistent Pi service.*
- **P2A** — `culvert p2a vga read/write` on the host (`/root/culvert-g3`). `SCU7C=0x00000202`.
- **BMC serial console — VALIDATED** — UART2 `0x1e784000` → **`/dev/serial-bmc-console`** on
  the Pi (1200 8N1 proven; wiring swap fixed). An **independent witness** to P2A for the ARM stub.
- **Video** — Magewell `/dev/video0`: `ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 out.png`
  captures the VGA (host POST/BIOS; works even with dead BMC firmware).

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

- [x] **M1 — DDR2 alive. DONE + hardware-verified (2026-07-08).** `ddr2-init-p2a.py`
      (path 2, the faithful `platform.S` sequence over P2A) initialised the DDR2
      controller on the real AST2050; DRAM `0x40000000`/`0x100`/`0x40100000`/
      `0x41000000` now store & read back `deadbeef`/`a5a5a5a5`/`cafebabe`/`0badf00d`
      (was a fixed uninitialised pattern). The hardest low-level bring-up is proven
      — payloads can now be loaded into BMC DRAM over P2A. Non-destructive; SCU/SDMC
      relocked after.
- [ ] **M2 — U-Boot prompt** on `/dev/ttyUSB0`. The **ARM-start mechanism is the
      blocker**, and it's now pinned down on hardware:
      - **JTAG path is DEAD (physical).** OpenOCD 0.12 is on the Pi and the
        Raptor-verified configs load, but the TAP scan returns **all-ones**
        (`IDCODE 0xffffffff`, "unknown EmbeddedICE 0xffffffff") — the `AST_JTAG1`
        header is not electrically connected (it's an unpopulated footprint per
        `HEADER-PINOUTS.md`; needs soldering/wiring — physical access, not remote).
      - **So the path is spispy.** `SCU70[1:0]=10` (read live: `SCU70=0x00819582`)
        → the ARM **boots from SPI flash (CE2)** on reset. Therefore: **load a
        U-Boot into the ULX3S spispy CE2 boot-flash emulation, then reset the
        ARM** → it boots our U-Boot; DRAM is already up (M1) so lowlevel DDR init
        is moot. **Two external blockers remain:** (1) the **spispy image-load
        mechanism** on the ULX3S — asked instance-A (twice) in the coordination
        log; (2) a **U-Boot binary** (vintage build is a quagmire — see above; or
        a modern build). Reset is coordinated with instance-A.
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
the ARM target cross-compiles (mpfr shim fixed it). Changing tools' `HOSTCPPFLAGS`
`-idirafter $(SRCTREE)/include` → `-I $(SRCTREE)/include` lets the non-libfdt host
tools build. **Remaining blocker (vintage quagmire, offline):** `tools/mkimage`
(always built) **links** `aisimage.o`/`kwbimage.o`/… (`tools/Makefile:214`), so the
image-format objects can't simply be dropped, and the 2013 vs modern **libfdt**
header clash on those needs a cleaner resolution than the `-I` tweak.

**libfdt clash — SOLVED** (reusable): in `tools/Makefile` `HOSTCPPFLAGS`, change
`-idirafter $(SRCTREE)/include` → `-I $(SRCTREE)/include` **and** add `-DLIBFDT_H`
(the modern system `/usr/include/libfdt.h` guard is `LIBFDT_H`; the bundled one is
`_LIBFDT_H`, so predefining `LIBFDT_H` makes the system header self-skip, leaving
only the bundled libfdt the tools need). This clears the redefinitions.

**But it's a multi-issue quagmire:** the next vintage-vs-modern break is
`include/compiler.h:66` (a `##sfx` bswap macro the modern host cpp rejects) — and
there will be more. This confirms PR #16's "hard-to-build" call.

**Recommended path (avoids the vintage quagmire entirely):** port `platform.S`'s
AST2050 **DDR2 init into the modern OpenBMC U-Boot** that PR #16 already builds
green (`uboot/build-uboot.sh`, v2019.04) — a real-HW `u-boot.bin` from a clean
modern build. **Alternatively** (culvert-native, no U-Boot build at all): script
`platform.S`'s SDMC register sequence over **P2A** to bring DDR2 up directly
(milestone M1), then load a payload — needs the rig + coordination but no vintage
build. Either path is the concrete next step.

> Note: even a finished `u-boot.bin` cannot *run* without the rig — loading it
> (spispy/JTAG) + resetting the AST2050 are the coordinated steps below.

## Immediate next steps

1. Confirm with instance-A the spispy image-load mechanism on this ULX3S (or that
   path 2/3 is preferred), and a coordination window.
2. Build a real-HW U-Boot with `platform.S` DDR2 init (from PR #16's U-Boot +
   Raptor's init), or script the P2A DDR2 sequence.
3. Execute **M1** first (DDR2), the highest-leverage, most-isolable step.

# ASUS KGPE-D16 BMC: custom-QEMU firmware stack

Goal: a custom QEMU that emulates the KGPE-D16's **ASPEED AST2050** BMC well
enough to (1) build a new U-Boot + Linux + initramfs **from source** and boot it
to an **SSH login**, (2) boot **Raptor Engineering's** AST2050 U-Boot/Linux, and
(3) boot the **proprietary** BMC firmware to a running **web service** — all
verified on CI.

Everything D16-specific lives under `asus-kgpe-d16-firmware/`. We reuse the Dell
C410X AST2050 build infrastructure and the HP iPDU "QEMU fork as submodule"
pattern (both in this repo).

## Why a *custom* QEMU

QEMU upstream models AST2400/2500/2600 but **not the AST2050** (the G3 part).
The AST2050 and AST2400 share the **ARM926EJ-S** core (QEMU's `palmetto-bmc` is
AST2400/ARM926EJ-S), but differ in SCU clocking (H-PLL post-divider, strap bit
positions) and the SDRAM/static-memory controllers. So:

- **Deliverable (primary):** a brand-new **`ast2050` SoC type** + a
  **`kgpe-d16-bmc` machine** built **specifically for this hardware**, developed
  as commits on a branch of the `mithro/qemu` fork (`d16-ast2050-machine`) and
  pulled in as a **git submodule** at `qemu/qemu`, built from source in CI —
  mirroring the iPDU's `mithro/qemu` `ns9360-machine` submodule pattern.
- **Smoke-test only:** stock `palmetto-bmc` (AST2400, same ARM926EJ-S core) may
  be used for throwaway early kernel sanity checks — it is **not** the target.
  The AST2050 machine is the deliverable.

Register map for the machine model comes from `../ast2050.h`, `../hwreg.h`,
`../platform.S` (Raptor DDR2 init) and `../RAPTOR-UBOOT-ANALYSIS.md`:
UART2 console `0x1E784000`, SCU `0x1E6E2000` (key `0x1688A8A8`), SDRAM ctrl
`0x1E6E0000` (key `0xFC600309`), DRAM `0x40000000`, SPI flash `0x14000000`.

## Tracks (one per CI acceptance criterion)

### Track 1 — Everything builds from source on CI
- **QEMU** — submodule `mithro/qemu@d16-ast2050-machine`; CI builds
  `qemu-system-arm` (`--target-list=arm-softmmu`) with the `kgpe-d16-bmc` machine.
- **Linux** — mainline stable + `kernel/patches/0001-clk-aspeed-add-ast2050-support.patch`
  (reused from C410X) + `dts/aspeed-bmc-asus-kgpe-d16.dts`;
  `aspeed_g4_defconfig` merged with `kernel/kgpe-d16.config`; build `uImage`+dtb.
- **Initramfs** — `initramfs/build.py` (BusyBox, static) **+ dropbear** for SSH;
  packaged as `uInitrd`.
- **U-Boot (new)** — mainline U-Boot, AST2400 aspeed base, adapted to AST2050
  (DRAM init ported from `../platform.S`). Interim: Raptor 2013.07 also builds.

### Track 2 — New U-Boot/Linux boots in QEMU, SSH login works (CI)
Boot `uImage`+`uInitrd` under the `kgpe-d16-bmc` (or interim `palmetto-bmc`)
machine with an `ftgmac100` NIC on QEMU user-net (`hostfwd tcp::2222-:22`).
`scripts/run-qemu.py` drives boot; `scripts/ssh-test.py` logs in over the
forwarded port and runs a command. Dropbear host key + `root` login baked into
the initramfs.

### Track 3 — Raptor U-Boot/Linux boots in QEMU (CI)
Fetch + build Raptor `ast2050-uboot` (U-Boot 2013.07) and `ast2050-linux-kernel`
(2.6.28.9) from source; boot under `kgpe-d16-bmc`. Console-only pass criterion
(reaching a Raptor login/shell banner over serial).

### Track 4 — Proprietary firmware boots to web service (CI)
**Blocked on firmware availability** (see STATUS.md). No proprietary *KGPE-D16*
BMC image is in the repo or known-public. Plan:
1. Attempt to source ASUS ASMB4/ASMB5 (AST2050) BMC firmware.
2. **Fallback emulation proof:** boot the **Dell C410X** proprietary firmware
   (also AST2050, already in `dell-c410x-firmware/backup/`, web UI present) under
   `kgpe-d16-bmc` and assert its web service (`curl` the login page) — proving
   the AST2050 emulation is complete enough, which is the criterion's intent.

## Phasing (incremental, each lands green CI before the next)

1. **P1 custom `kgpe-d16-bmc` (AST2050) machine** — new `ast2050` SoC + machine
   committed on the `mithro/qemu` submodule branch; CI inits the submodule, builds
   `qemu-system-arm` from source, and `-M kgpe-d16-bmc` starts (runs U-Boot /
   reaches console). *(Track 1: QEMU.)*
2. **P2 build-from-source CI** — kernel (D16 DTS + AST2050 clock patch) + initramfs
   (BusyBox + dropbear) + U-Boot build green. *(Track 1 complete → C1.)*
3. **P3 new stack boots to serial shell** on `kgpe-d16-bmc`.
4. **P4 SSH** — networking + dropbear + `ssh-test.py` green. *(→ C2.)*
5. **P5 Raptor stack** (U-Boot 2013.07 + Linux 2.6.28.9) boots on `kgpe-d16-bmc`. *(→ C3.)*
6. **P6 proprietary** firmware (ASUS, or C410X AST2050 fallback) → web service. *(→ C4.)*

CI is the source of truth — each phase adds/extends `.github/workflows/d16-qemu-stack.yml`.

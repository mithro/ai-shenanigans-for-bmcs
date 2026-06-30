# Status — D16 custom-QEMU firmware stack

See [PLAN.md](PLAN.md) for the design. CI workflow: `.github/workflows/d16-qemu-stack.yml`.

## Acceptance criteria (the goal)

- [ ] **C1** Everything builds from source on CI (QEMU, U-Boot, Linux, initramfs)
- [ ] **C2** New U-Boot/Linux boots in QEMU and is logged into via SSH on CI
- [ ] **C3** Raptor U-Boot/Linux boots in QEMU on CI
- [ ] **C4** Proprietary firmware boots in QEMU to a running BMC web service on CI

## Phase progress

- [ ] P1 — custom `kgpe-d16-bmc` (AST2050) QEMU machine; builds from source + starts
- [ ] P2 — kernel + initramfs(+dropbear) + U-Boot build from source → **C1**
- [ ] P3 — new stack boots to serial shell on `kgpe-d16-bmc`
- [ ] P4 — SSH login green (networking + dropbear + ssh-test) → **C2**
- [ ] P5 — Raptor stack boots → **C3**
- [ ] P6 — proprietary firmware → web service → **C4**

## Blockers / risks (honest assessment)

1. **C4 firmware availability (BLOCKER).** No proprietary *KGPE-D16* BMC image is
   in this repo or known to be publicly downloadable. Options, in order:
   (a) source ASUS ASMB4/ASMB5 AST2050 firmware; (b) **fallback**: boot the Dell
   C410X proprietary firmware (also AST2050, in `dell-c410x-firmware/backup/`,
   has a web UI) under the same `kgpe-d16-bmc` machine as the emulation proof.
   Until one is wired up, C4 cannot pass.
2. **AST2050 ≠ upstream QEMU.** A real `kgpe-d16-bmc` machine requires modelling
   AST2050 SCU clocking + SDRAM controller deltas vs AST2400. High effort; P4.
   Interim boots use `palmetto-bmc` (AST2400, same ARM926EJ-S core).
3. **Raptor stack age (C3).** U-Boot 2013.07 + Linux 2.6.28.9 build with old
   toolchains; may need a pinned cross-gcc in CI.
4. **Local toolchain.** Dev box has only `arm-none-eabi` + native gcc; the Linux
   cross-compiler (`gcc-arm-linux-gnueabi`) is installed in CI. Fast local
   iteration of boots uses the host's `qemu-system-arm` 10.0.8 (`palmetto-bmc`).

## Now

**Done — P1 machine exists.** A custom `kgpe-d16-bmc` AST2050 machine:
`ast2050-a1` SoC (reuses the register-compatible AST2400 peripheral models via a
new `qom_socname` override; provisional AST2050 SCU7C rev `0x01000303`) + the
`kgpe-d16-bmc` machine (128 MB DDR2, FTGMAC100 NIC, 8 MB SPI NOR, 24 MHz clock).
Developed on `mithro/qemu` branch `d16-ast2050-machine` (off QEMU v10.0.7),
vendored as a submodule at `qemu/qemu`. `qemu-system-arm` builds from it and
`-M kgpe-d16-bmc` instantiates the SoC cleanly — smoke test green via
`scripts/run-qemu.py smoke`.

**Next:** P1 CI job (build `qemu-system-arm` from the submodule + smoke-start on
CI), then P2 (kernel `uImage` + initramfs with dropbear) → boot on the machine.

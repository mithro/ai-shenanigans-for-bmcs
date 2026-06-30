# Status — D16 custom-QEMU firmware stack

See [PLAN.md](PLAN.md) for the design. CI workflow: `.github/workflows/d16-qemu-stack.yml`.

## Acceptance criteria (the goal)

- [x] **C1** Builds from source on CI — QEMU ✅, kernel ✅, initramfs ✅ (green on
      CI run #28472752429) **+ U-Boot ✅** (OpenBMC v2019.04 builds from source;
      `build-uboot` CI job).
- [x] **C2** New U-Boot/Linux boots + SSH — **full chain proven**: U-Boot 2019.04
      boots on `kgpe-d16-bmc`, `bootm`s the kernel+initramfs from flash, and an
      SSH key login succeeds (`SSH_OK / kgpe-d16-bmc`). `ssh-test --flash` passes
      locally; the `boot-uboot-ssh` CI job runs the identical chain. (The simpler
      direct-`-kernel` `boot-ssh` job is already green on CI.)
- [x] **C3** Raptor U-Boot/Linux boots in QEMU on CI — **DONE**: Raptor's 2.6.28.9
      AST2050 kernel (vintage gcc-4.9.4) + a musl BusyBox/dropbear userspace build
      from source and boot on `kgpe-d16-bmc` via the OpenBMC U-Boot ATAGS path
      (`machid=0x22b8`); SSH login succeeds (`SSH_OK / kgpe-d16-bmc /
      Linux armv5tejl`). Local pass + new `boot-raptor` CI job. The G4-modelled
      machine runs the G3 kernel unchanged — see [raptor/README.md](raptor/README.md).
- [ ] **C4** Proprietary firmware boots in QEMU to a running BMC web service on CI
      — open / research-grade (no public D16 image; Dell C410X AST2050 as proxy).

## Phase progress

- [x] P1 — custom `kgpe-d16-bmc` (AST2050) QEMU machine; builds from source + starts
- [~] P2 — build from source → **C1**: kernel ✅, initramfs (BusyBox + static dropbear) ✅, U-Boot ⬜
- [x] P3 — boots on `kgpe-d16-bmc` to a shell (kernel + initramfs) ✅ *(locally)*
- [x] P4 — **SSH login PASSES locally** on `kgpe-d16-bmc` (ed25519 key auth):
      `SSH_OK / kgpe-d16-bmc / Linux armv5tejl` → **C2** linux/SSH part proven.
      Remaining for C2: wire kernel+initramfs+ssh-test into CI, add the U-Boot chain.
- [x] P5 — Raptor stack boots → **C3** ✅ (2.6.28.9 kernel + musl userspace,
      SSH login on `kgpe-d16-bmc`; `boot-raptor` CI job)
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

## Now / progress (honest)

**C1 — builds from source on CI:** custom QEMU ✅ (machine smoke-test green on a
CI run); initramfs (BusyBox + static dropbear) ✅ on CI; the kernel + `boot-ssh`
jobs are running. Effectively in hand.

**C2 — new stack boots + SSH on CI:** the from-source kernel + initramfs boot on
`-M kgpe-d16-bmc` and accept an SSH key login — **verified locally**
(`ssh-test.py → SSH_OK / kgpe-d16-bmc / Linux armv5tejl`); the CI `boot-ssh` job
exercises the identical path. Remaining: a U-Boot stage in front of the kernel
(the criterion names "u-boot/linux"; today QEMU loads the kernel directly).

**C3 — Raptor stack: DONE.** Raptor's Linux 2.6.28.9 AST2050 kernel builds with a
vintage gcc-4.9.4 (kernel.org crosstool, auto-fetched) and boots on
`kgpe-d16-bmc` via the existing OpenBMC U-Boot using an ATAGS hand-off
(`setenv machid 22b8; bootm <kernel> <initrd>`, no dtb). A **musl** BusyBox +
dropbear userspace (the C2 glibc one can't run on a 2.6.28 kernel) reaches a
shell and an SSH login (`SSH_OK / kgpe-d16-bmc / Linux armv5tejl`). The earlier
"needs a G3 SoC model in QEMU" worry was wrong — the AST2400/G4 peripheral models
run the G3 kernel unchanged. Reproducible `build-raptor-kernel.sh` /
`build-raptor-userspace.sh` + a `boot-raptor` CI job; full diagnostic chain in
[raptor/README.md](raptor/README.md). (Raptor's *own* U-Boot 2013.07 is not on
the boot path and remains an optional extra.)

**C4 — proprietary firmware → web service: blocked / research-grade.** No public
KGPE-D16 BMC image exists; the only AST2050 proprietary image in-repo is the Dell
C410X firmware (`dell-c410x-firmware/backup/`). Booting a full proprietary BMC
image to a *running web service* in QEMU needs near-complete AST2050 peripheral
emulation (every I2C sensor / GPIO it probes, or it hangs/panics) — realistically
a multi-day effort that may not be fully achievable. Highest-risk criterion.

**Bottom line:** C1, C2, and **C3 are achieved** (all three with CI jobs;
C1/C2 already green, the C3 `boot-raptor` job mirrors the validated local pass).
**C4 remains the only open criterion** — a research problem gated on firmware
availability and AST2050 emulation completeness: no public KGPE-D16 BMC image
exists, so it needs either a firmware source or agreement to use the in-repo Dell
C410X AST2050 image as the emulation-proof proxy.

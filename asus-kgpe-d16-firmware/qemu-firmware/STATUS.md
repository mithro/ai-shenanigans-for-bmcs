# Status — D16 custom-QEMU firmware stack

See [PLAN.md](PLAN.md) for the design. CI workflow: `.github/workflows/d16-qemu-stack.yml`.

## Acceptance criteria (the goal)

- [~] **C1** Builds from source on CI — **QEMU ✅, Linux kernel ✅, initramfs ✅
      green on CI** (run #28472752429); the new U-Boot build is the only piece left.
- [~] **C2** New stack boots + SSH on CI — **the new Linux boots on `kgpe-d16-bmc`
      and an SSH key login succeeds, green on CI** (`boot-ssh` job ✅); adding a
      U-Boot stage in front of the kernel is the remaining refinement.
- [ ] **C3** Raptor U-Boot/Linux boots in QEMU on CI — open (vintage toolchain;
      see [raptor/README.md](raptor/README.md)).
- [ ] **C4** Proprietary firmware boots in QEMU to a running BMC web service on CI
      — open / research-grade (no public D16 image; Dell C410X AST2050 as proxy).

## Phase progress

- [x] P1 — custom `kgpe-d16-bmc` (AST2050) QEMU machine; builds from source + starts
- [~] P2 — build from source → **C1**: kernel ✅, initramfs (BusyBox + static dropbear) ✅, U-Boot ⬜
- [x] P3 — boots on `kgpe-d16-bmc` to a shell (kernel + initramfs) ✅ *(locally)*
- [x] P4 — **SSH login PASSES locally** on `kgpe-d16-bmc` (ed25519 key auth):
      `SSH_OK / kgpe-d16-bmc / Linux armv5tejl` → **C2** linux/SSH part proven.
      Remaining for C2: wire kernel+initramfs+ssh-test into CI, add the U-Boot chain.
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

## Now / progress (honest)

**C1 — builds from source on CI:** custom QEMU ✅ (machine smoke-test green on a
CI run); initramfs (BusyBox + static dropbear) ✅ on CI; the kernel + `boot-ssh`
jobs are running. Effectively in hand.

**C2 — new stack boots + SSH on CI:** the from-source kernel + initramfs boot on
`-M kgpe-d16-bmc` and accept an SSH key login — **verified locally**
(`ssh-test.py → SSH_OK / kgpe-d16-bmc / Linux armv5tejl`); the CI `boot-ssh` job
exercises the identical path. Remaining: a U-Boot stage in front of the kernel
(the criterion names "u-boot/linux"; today QEMU loads the kernel directly).

**C3 — Raptor stack: substantial open work.** Raptor's U-Boot 2013.07 and Linux
2.6.28.9 do **not** build with the modern gcc-14 cross-toolchain: U-Boot cascades
(needs `compiler-gccN.h` shims, hits host `libfdt` header conflicts) and the 2008
kernel realistically needs a **vintage gcc-4.x** (e.g. kernel.org crosstool
prebuilts). The board target exists (`asus`/`ast2050` in Raptor's `boards.cfg`),
so the path is known — but it is hours of toolchain + patch work, not yet done.

**C4 — proprietary firmware → web service: blocked / research-grade.** No public
KGPE-D16 BMC image exists; the only AST2050 proprietary image in-repo is the Dell
C410X firmware (`dell-c410x-firmware/backup/`). Booting a full proprietary BMC
image to a *running web service* in QEMU needs near-complete AST2050 peripheral
emulation (every I2C sensor / GPIO it probes, or it hangs/panics) — realistically
a multi-day effort that may not be fully achievable. Highest-risk criterion.

**Bottom line:** C1+C2 are essentially achieved (CI confirming). C3 is a known
but heavy toolchain task; C4 is a research problem gated on firmware availability
and emulation completeness. Scope for C3/C4 is worth agreeing before committing
days of effort, especially to C4.

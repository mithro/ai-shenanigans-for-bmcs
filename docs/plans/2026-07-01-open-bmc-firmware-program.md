<!--
Provenance: this is the approved output of a cloud /ultraplan session.
Session : https://claude.ai/code/session_018sFmMwzLVFc6Xp5DQxLj7h
Original: /root/.claude/plans/check-on-all-the-unified-shell.md (cloud sandbox)
Approved 2026-07-01; recovered verbatim from the session transcript on 2026-07-02.
-->

# Open BMC/Firmware Program — QEMU, Kernel, U-Boot, OpenBMC, WallaBMC, Docs

## Context

`mithro/ai-shenanigans-for-bmcs` (private) is a reverse-engineering + open-firmware
program for **three pieces of hardware**, two of which share a SoC:

| Board | SoC | Core | Role | Dir |
|---|---|---|---|---|
| **ASUS KGPE-D16** | Aspeed **AST2050** | ARM926EJ-S (ARMv5TE) | server BMC | `asus-kgpe-d16-firmware/` |
| **Dell C410X** | Aspeed **AST2050** | ARM926EJ-S | 16-slot PCIe GPU chassis BMC | `dell-c410x-firmware/` |
| **HPE iPDU AF531A** | Digi **NS9360** | ARM926EJ-S | intelligent PDU | `hpe-ipdu-firmware/` |

The goal is to turn the existing RE work into a full, CI-verified open-firmware stack
(QEMU emulation → test benches → Linux/U-Boot on latest upstream → OpenBMC + WallaBMC),
plus ReadTheDocs documentation, while maintaining **clean, small, rebasable upstream
patch series** (never auto-PR'd upstream) separate from the private narrative history.

> **Note on the working copy:** the seed at `/home/user/repo` contains only `README.md`.
> The real repo (8216 files, `origin/main` + `origin/claude/d16-qemu-firmware-stack` +
> PRs 1–16) is cloned read-only at
> `…/scratchpad/realrepo`. First execution step is to wire `origin` in the working repo.

## What already exists (leverage, don't rebuild)

- **AST2050 QEMU vertical is far along** (branch `claude/d16-qemu-firmware-stack`, PR #16).
  Custom `kgpe-d16-bmc` machine + new `ast2050` SoC live in fork **`mithro/qemu@d16-ast2050-machine`**
  (submodule `asus-kgpe-d16-firmware/qemu-firmware/qemu/qemu`). CI `.github/workflows/d16-qemu-stack.yml`
  builds QEMU+kernel+initramfs+U-Boot from source and is green on **C1** (builds), **C2**
  (mainline U-Boot→kernel→BusyBox/dropbear→SSH), **C3** (Raptor 2.6.28.9 + musl → SSH).
- **C4 blocker is mis-stated in `STATUS.md`.** Per
  `asus-kgpe-d16-firmware/qemu-firmware/AST2050-PERIPHERAL-MODELING.md`, runtime gdb tracing
  **disproved NCSI** as the blocker. Real gate: the MAC-info **enable byte `cfg[0x225]`** sourced
  from an **I2C EEPROM** read, plus **ftgmac100 DMA-ring/stats completeness** (register_netdevice
  oops). NCSI responder is optional faithfulness only. Correct `STATUS.md` to match.
- **QEMU models the AST2050 as ~AST2400/G4 peripherals**; **no board-level I2C device models exist yet**
  (INA219, ADT7462, TMP75/LM75, PCA9555, PCA9548/9544, PEX8696/8647). This is the core (a)/(b) gap.
- **C410X**: fully RE'd `aspeed-bmc-dell-c410x.dts` (on `aspeed-g4.dtsi`), `kernel/patches/0001-clk-aspeed-add-ast2050-support.patch`, `c410x.config`, `tftp_boot.py`, CI `build-bmc-firmware.yml`.
  192 devices / 72 sensors / 118 GPIO decoded (`io-tables/`), PEX I2C protocol in `pex-i2c-analysis/PEX-I2C-COMMANDS.md`, datasheets in `datasheets/`. `REUSING-KGPE-D16-WORK.md` is the reuse map.
- **HPE iPDU**: `mithro/u-boot@hpe-ipdu-port` + `mithro/qemu@ns9360-machine` boot U-Boot in QEMU
  (`uboot-port/test/qemu_smoke_test.py`). Vendored `linux-mach-ns9xxx/linux-v2.6.39` reference. No mainline Linux for NS9360.
- **Harness patterns to unify**: `scripts/run-qemu.py`, `scripts/ssh-test.py`, `uboot-port/test/qemu_smoke_test.py`.
- **HIL**: `RPI4-OPENOCD-JTAG-WIRING.md` + `openocd/*.cfg` (RPi4 as JTAG/UART/SPI). Real
  `rpi4-pmod`/`rpi5-pmod`/`rpi4-gwifi` boards arrive "in the near future."
- **No** OpenBMC / WallaBMC / Zephyr / Sphinx work exists yet.

## Locked decisions (from user)

1. **Sequencing**: (1) ReadTheDocs/Sphinx foundation **first**, (2) scaffolding for all tracks,
   (3) then **in parallel**: OpenBMC track + AST2050 emulation deepening.
2. **WallaBMC** = Tenstorrent's **Zephyr-based** BMC (`tenstorrent-riscv-software/wallabmc`;
   Redfish/web/power/console; Apache-2.0; West/CMake). Architecture split is firm:
   **OpenBMC = the Linux-based BMC track; WallaBMC = the Zephyr-based BMC track**, both for all 3 boards.
3. **Zephyr on ARM926EJ-S/ARMv5**: Zephyr has no ARMv5 support today → **do the full ARM926EJ-S/ARMv5
   architecture port to Zephyr now** as a first-class deliverable, then bring up WallaBMC on it.
4. **iPDU gets the full treatment**: U-Boot port → add both Zephyr and Linux support → OpenBMC (on Linux)
   and WallaBMC (on Zephyr).
5. **Upstream tracking**: maintain **two variants of every patch stack** — one on the **latest stable
   release tag**, one on **mainline `master` HEAD** — for kernel, U-Boot, QEMU, and Zephyr.
6. **Create the public repos now** under `mithro`, wired into the private repo as submodules.
7. **Never open upstream PRs** (user handles). Private `main` advances only via reviewed `--no-ff`
   merges after green CI, and is the full narrative (dead ends included).

## Repository & branch / patch-stack strategy

**Public forks (clean, upstreamable — one topic branch per subsystem, `git format-patch`
series rebased onto upstream; kept strictly separate from private history):**

- `mithro/qemu` (exists): `d16-ast2050-machine`, `ns9360-machine` (exist) + new `c410x-bmc-machine`,
  `i2c-device-models`, `pex-i2c-models`.
- `mithro/u-boot` (exists): `hpe-ipdu-port` (exists) + new `ast2050-port`.
- **`mithro/linux`** (create fork): `aspeed-g3-soc` (clk + `aspeed-g3.dtsi` + `aspeed,ast2050-*` compatibles),
  `aspeed-bmc-boards` (the 2 board DTS), `ns9xxx-revive` (stretch).
- **`mithro/openbmc`** (create fork): `meta-asus-kgpe-d16`, `meta-dell-c410x`, `meta-hpe-ipdu`.
- **`mithro/zephyr`** (create fork): `arch-arm926ejs` (ARMv5 arch), `soc-ast2050`, `soc-ns9360`, board defs.
- **`mithro/wallabmc`** (create fork): board/SoC ports on top of the Zephyr fork.
- **`mithro/bmc-open-firmware-docs`** (create public repo): Sphinx/MyST site on ReadTheDocs
  (docs must be public; the program repo is private).

Each fork subsystem branch is maintained in **both** a `…-stable` and a `…-master` variant (decision 5).
The **applied** patches are *generated* into the private repo (`*/kernel/patches/*.patch`, etc.) by a
script from the fork branches — never hand-edited — so clean series and messy history never mix.

**Private repo (`ai-shenanigans-for-bmcs`):** long-running tracks each get a git **worktree**
(`wt/docs`, `wt/qemu-c410x`, `wt/openbmc`, `wt/zephyr`, `wt/kernel-rebase`) so tracks don't serialize.
Small logical commits; merge to `origin/main` via `--no-ff` PRs after CI is green and reviewed
(cross-checked by sub-agents). All the new forks are added to `.gitmodules`.

## Dependency ordering

Register docs **(i)** → QEMU device model **(a)** → test bench **(b)** are done as **one triplet per
device**, and are the prerequisite for verifying drivers **(c)**, U-Boot **(e)**, and BMC firmware
**(f/g)** that touch that device. `(d)` rebase automation is built early (cheap CI plumbing that every
later phase depends on). `(h)` is one two-backend harness (QEMU now, HIL later) consumed by all
firmware phases. Honoring the user's priority, docs `(i)` + scaffolding come first, then OpenBMC `(f)`
and emulation `(a/b)` proceed in parallel.

## Phased roadmap (each phase lands green CI before merge)

### Phase 0 — Consolidate & scaffold (foundation)
- Wire `origin` in the working repo; confirm `d16-qemu-stack.yml` green; **merge PR #16
  (`claude/d16-qemu-firmware-stack`) into `main` via `--no-ff`**. Correct the C4/NCSI claim in
  `asus-kgpe-d16-firmware/qemu-firmware/STATUS.md` to match `AST2050-PERIPHERAL-MODELING.md`.
- Create the six new public repos/forks above; add as submodules.
- **(i) ReadTheDocs foundation FIRST**: `mithro/bmc-open-firmware-docs` — Sphinx + MyST + `.readthedocs.yaml`,
  import existing Markdown, RTD builds on push (link-check CI job). Structure: per-board hardware/register
  reference (from `datasheets/`, `ast2050.h`, `hwreg.h`, `pex-i2c-analysis/`), driver docs
  (Linux/Zephyr/U-Boot), OpenBMC/WallaBMC interfaces, references.
- **Scaffolding**: the unified `firmware-testbench/` Python module with a pluggable `Target`
  backend (`qemu`|`hil`) exposing serial/SSH/i2c-scan/sensor/GPIO; refactor `run-qemu.py`,
  `ssh-test.py`, `qemu_smoke_test.py` onto it (existing `boot-ssh`/`boot-raptor` jobs pass unchanged).
  Stub directories/branches for every downstream track.
- **(d) rebase automation, dual-variant**: `.github/workflows/rebase-{kernel,uboot,qemu,zephyr}.yml`
  (scheduled + dispatch) that rebase both the `…-stable` and `…-master` variants onto latest upstream,
  regenerate the in-repo patch series, run the boot/bench suite, and **open a PR** (advisory) on
  conflict/failure. Never touches upstream.

### Phase 1 (parallel A) — Board-complete AST2050 emulation + benches (a/b/i)
Per-device triplets in `mithro/qemu` (`i2c-device-models`, then `pex-i2c-models`), shared by D16 & C410X:
- Device models + qtest benches (`tests/qtest/*-test.c`): **INA219 + PCA9548 first** (most-used), then
  ADT7462, TMP75/LM75, PCA9555, PCA9544; then the hardest, **PEX8696/PEX8647** I2C management model from
  `PEX-I2C-COMMANDS.md`. New CI job `qemu-qtest` (`meson test --suite qtest`); benches fail if a register
  returns the unimplemented-default.
- New **`c410x-bmc` machine** wiring the models onto the 7 I2C buses + GPIO/PCA9555 lines per
  `aspeed-bmc-dell-c410x.dts`. Jobs `qemu-c410x-smoke`, `c410x-board-bench` (i2cdetect map + hwmon reads
  match the expected map in `REUSING-KGPE-D16-WORK.md`).
- **Close C4 faithfully (a6)**: seed I2C EEPROM MAC-info blob (MAC + `cfg[0x225]` enable byte) + complete
  ftgmac100 DMA-ring/stats. Job `qemu-c410x-vendor-web`: vendor firmware boots, `eth0` registers,
  `curl :8080` serves appweb.
- **NS9360 board-complete (a7)**: extend `ns9360-machine` (MAXQ3180 SPI, TMP89 display MCU, CFI flash,
  ICS1893 PHY) enough to netboot U-Boot; keep `qemu_smoke_test.py` green.

### Phase 1 (parallel B) — OpenBMC (Linux) track (f) — starts on SoC-complete emulation, deepens as devices land
- **`mithro/openbmc`** `meta-asus-kgpe-d16` + `meta-dell-c410x` referencing `aspeed-g3.dtsi`/board DTBs;
  workflow `openbmc-build.yml` bitbakes an image, **verified in QEMU** via `firmware-testbench`
  (boot → SSH → `GET /redfish/v1`).
- entity-manager JSON for the 72 C410X sensors (`io-tables/IS_fl.bin.md`); dbus-sensors for
  INA219/ADT7462/TMP75/LM75; phosphor fan control (ADT7462 curves); phosphor power for the 12-step
  GPIO/PCA9555 sequence (`io-tables/gpio-pin-mapping.md`). Job `openbmc-c410x-bench`: Redfish enumerates
  all sensors; power-on drives the modeled GPIOs in order.
- **PCIe switch daemon**: phosphor-style userspace implementing the PEX8696/8647 protocol, verified vs the
  `pex-i2c-models` qtest. SoL (obmc-console over modeled UART), ssh/https via slirp hostfwd.
- **XIP + stripping (f5)**, only after a non-XIP image boots: XIP the RO rootfs from modeled SPI flash;
  strip authentication and unneeded features to fit the AST2050 flash-partition/RAM budget (from the DTS).
  Job `openbmc-c410x-xip`: image fits budget AND boots to Redfish with `-m` at real RAM size.

### Phase 2 — Kernel (c) & U-Boot (e) on latest upstream, dual-variant
- **(c) `aspeed-g3.dtsi` series** in `mithro/linux` (promote the clock patch + SCU overrides to a proper
  G3 dtsi + `aspeed,ast2050-*` compatibles); switch both board DTS to include it (per
  `REUSING-KGPE-D16-WORK.md` Step 1). `build-kernel` matrix builds **stable + master** variants; both
  boards boot to SSH on QEMU. Confirm all mainline drivers bind (`ina2xx`, `adt7462`, `lm75`, `pca953x`,
  `pca954x`, `ftgmac100`, `spi-aspeed-smc`, `gpio/i2c-aspeed`, `aspeed-wdt`). PEX has no mainline driver →
  userspace tool (in f/g) or out-of-tree patch.
- **(e) `ast2050-port`** in `mithro/u-boot` on latest (replacing OpenBMC v2019.04); `boot-uboot-ssh` stays
  green. **Full TFTP netboot** verified in QEMU (slirp TFTP → `tftpboot; bootm` → Linux; job
  `c410x-tftp-netboot`) and mirrored to HIL via `tftp_boot.py`. Rebase `hpe-ipdu-port` onto latest.
- **iPDU Linux (c4)**: forward-port a minimal `mach-ns9xxx` from the vendored `linux-v2.6.39` reference
  toward latest (device-tree-ify). High-risk; boots to console on `ns9360` QEMU as the acceptance target.

### Phase 3 — WallaBMC (Zephyr) track (g) + full ARMv5 Zephyr port
- **`mithro/zephyr` `arch-arm926ejs`**: add ARM926EJ-S/ARMv5TE architecture support (exceptions, MMU/cache,
  timer, GIC/VIC, boot) — the biggest single deliverable. Validate first on a Zephyr `qemu`-friendly
  ARM926 target, then `soc-ast2050` and `soc-ns9360` + board defs.
- **`mithro/wallabmc`** board ports on the Zephyr fork; bring up Redfish/web/power/console. Because upstream
  WallaBMC lacks sensors/fans/PCIe, extend it (or document the gap) to cover the BMC sensor/fan/PCIe needs.
  Verified in QEMU via the same `firmware-testbench` Redfish/power/console benches; differentiator vs
  OpenBMC is footprint (smaller flash/RAM).

### Phase 4 — HIL verification (h2) — when `rpi*-pmod`/`gwifi` boards arrive
- Implement `Target(backend=hil)` driving the RPi4/5 OpenOCD/UART/SPI rig (`RPI4-OPENOCD-JTAG-WIRING.md`,
  `openocd/*.cfg`). The **same** board-bench code runs on real hardware via a self-hosted-runner workflow
  (`hil-*.yml`), proving QEMU and silicon behave identically. Build the HIL backend stubbed now.

## Test-bench approach (deliverables b + h)
- **Layer 1 — qtest (C, in `mithro/qemu/tests/qtest/`)**: register-level device-model correctness; fast,
  headless, native (`meson test`), CI job `qemu-qtest`.
- **Layer 2 — `firmware-testbench/` (Python)**: full boot/SSH/curl/i2cdetect/hwmon/GPIO assertions over a
  pluggable `Target` backend. **One bench, two backends** (`qemu` in CI now, `hil` on real boards later).
  Reuses existing bespoke harnesses — no new framework (Avocado) needed.

## Hard problems / risks (tracked honestly)
- **Full ARMv5 Zephyr port** (decision 3) is the largest, highest-uncertainty deliverable — de-risk with a
  QEMU ARM926 spike before SoC/board work.
- **OpenBMC on AST2050** may not fit even with XIP/stripping — boot non-XIP first, then squeeze; WallaBMC is
  the lighter fallback.
- **NS9360 mainline Linux** doesn't exist — forward-porting `mach-ns9xxx` is a long pole.
- **Dual-variant (stable + master) patch stacks** ×4 projects is real maintenance load — the rebase-bots
  (Phase 0) exist precisely to carry it.
- **CI/compute budget**: OpenBMC Yocto + QEMU-from-source + dual kernel matrices are heavy and may hit
  quota; expect to pause/resume (user pre-authorized). Use ccache and artifact caching aggressively.

## First concrete work items (highest leverage)
1. Wire `origin`; verify `d16-qemu-stack.yml` green; **merge PR #16 into `main` (`--no-ff`)**; fix the C4/NCSI
   claim in `STATUS.md`.
2. Create the six public repos/forks; add as submodules; stand up the **RTD/Sphinx docs site (i)** and the
   **dual-variant rebase-bots (d)**.
3. Build the **`firmware-testbench/` two-backend harness** by refactoring the three existing harnesses.
4. Land the **INA219 + PCA9548 device-model triplet** (doc → QEMU model → qtest) + `qemu-qtest` job — proves
   the a/b/i pattern; unblocks the `c410x-bmc` machine, sensor drivers, and OpenBMC sensors.
5. **Close C4 faithfully** (I2C MAC-info EEPROM + ftgmac100 completeness) with a `qemu-c410x-vendor-web` job.

Items 1–4 run in parallel worktrees; item 5 builds on item 4's I2C EEPROM plumbing.

## Verification
- **Per QEMU device model**: `meson test --suite qtest` in the `mithro/qemu` fork (job `qemu-qtest`) — each
  bench asserts reset values + R/W + I2C addressing/mux gating.
- **Board-complete emulation**: `firmware-testbench --backend qemu --bench board_c410x` (i2cdetect map,
  hwmon reads, GPIO presence, power sequence) green in CI.
- **C4**: `qemu-c410x-vendor-web` boots vendor firmware and `curl :8080` returns appweb.
- **Kernel/U-Boot**: `d16-qemu-stack.yml` + matrix (stable + master) boot both boards to SSH; TFTP netboot
  job reaches Linux.
- **OpenBMC/WallaBMC**: image boots in QEMU via `firmware-testbench` → SSH + `GET /redfish/v1` + sensor
  enumeration + power sequencing; XIP image fits the DTS flash/RAM budget.
- **Docs**: ReadTheDocs build + link-check green.
- **HIL (later)**: the identical board-bench passes on real hardware via `hil-*.yml`.
- **Every merge to private `main`**: green CI + sub-agent review, integrated with a `--no-ff` merge commit.

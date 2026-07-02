<!--
Provenance: originally the approved output of a cloud /ultraplan session.
Session : https://claude.ai/code/session_018sFmMwzLVFc6Xp5DQxLj7h
Original: /root/.claude/plans/check-on-all-the-unified-shell.md (cloud sandbox)
Approved 2026-07-01; recovered verbatim from the session transcript on 2026-07-02.
Revised  2026-07-02: restructured around Claude Code Workflow orchestration and
per-task model tiering (session https://claude.ai/code/session_0142b4TWwFm4ZTyhzcGEn7Xj).
All engineering content, locked decisions, and acceptance gates from the approved
plan are preserved; the revision adds HOW the work is executed, not WHAT is built.
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

This revision restructures the plan around its execution model: the program is driven
by **Claude Code multi-agent Workflows** with a **best-fit Claude model per task tier**.
Two new cross-cutting sections (§ Execution model, § Model tiering) define the machinery
once; each phase then carries an **Orchestration** note mapping its work onto that
machinery. No `.claude/` directory, `.mcp.json`, or agent configuration exists in the
repo today — standing that up is not required by this plan; the orchestration described
here is invoked from Claude Code sessions directly.

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

## Execution model — Claude Code Workflows

All multi-item or multi-stage work in this program is orchestrated through the Claude Code
**Workflow** tool rather than worked serially by a single agent. The rules:

- **`pipeline()` is the default** for per-device, per-board, and per-patch-stack work. Each
  item (a device model, a patch-stack variant, a doc page) flows through its stages
  independently — no barrier between stages, so a fast item's verification runs while a slow
  item is still being built. Wall-clock cost is the slowest single-item chain, not the sum
  of the slowest stage across items.
- **`parallel()` only where a stage genuinely needs all prior results together** — deduping
  findings across finders, merging a full sensor map before comparison, or early-exit when a
  count is zero. "The stages are conceptually separate" is not a reason for a barrier.
- **Adversarial verification** gates every correctness-critical claim (see § RE-verification
  pattern below): N independent skeptic agents prompted to *refute* the claim, majority-refute
  kill, before the claim lands in a device model, DTS, or published doc.
- **Worktree isolation.** Long-running tracks each get a git worktree (`wt/docs`,
  `wt/qemu-c410x`, `wt/openbmc`, `wt/zephyr`, `wt/kernel-rebase`) — locked decision, restated
  here because it maps 1:1 onto orchestration: any Workflow agent that *mutates files* runs
  with `isolation: 'worktree'` so parallel agents never conflict; read-only agents (doc
  extraction, verification, log analysis) run without it.
- **One orchestrator, delegated tiers.** The main session loop stays on a single model;
  work belonging to a different tier is delegated to sub-agents/workflow stages with a
  per-agent `model` override (never swap the main loop's model mid-session — it destroys
  the prompt cache).
- **Existing skills are part of the machinery**: `code-review` before every merge to `main`,
  `verify` after nontrivial code changes, and the in-repo `uv run` cross-checkers
  (`cross_check_dts.py`, `parse_io_tables.py`) run *inside* workflow verify stages as
  ground truth.

## Model tiering

Every task in this plan is assigned one of four tiers. Model IDs are exact; effort is the
per-agent reasoning-effort setting.

| Tier | Model ID | Cost (in/out per MTok) | Use for | Effort |
|---|---|---|---|---|
| **Frontier reasoning** | `claude-fable-5` | $10 / $50 (1M ctx) | ARMv5/ARM926EJ-S Zephyr arch-port design; PEX8696/8647 I2C protocol modeling from decompilation; ambiguous RE (DDR2 init, MAC-info `cfg[0x225]` gating); architectural decisions; **all adversarial verification** | `xhigh`–`max` |
| **Heavy implementation** | `claude-opus-4-8` | $5 / $25 (1M ctx) | Well-scoped builds: QEMU device models + qtest benches, kernel/U-Boot patch series, OpenBMC recipes / entity-manager JSON, the `firmware-testbench` harness | `high`–`xhigh` |
| **Routine implementation** | `claude-sonnet-5` | $3 / $15 (intro $2 / $10 through 2026-08-31; 1M ctx) | CI YAML, scaffolding, Sphinx/MyST doc conversion, test-bench plumbing, straightforward refactors | `medium`–`high` |
| **Mechanical fan-out** | `claude-haiku-4-5` | $1 / $5 (200K ctx) | File/enum sweeps, link-checking, log grepping, table/format transforms | `low` |

Guidance:

- **Effort defaults**: `xhigh` for coding/agentic stages on the top two tiers; `high` minimum
  for anything intelligence-sensitive (verification, protocol interpretation); `low` for
  mechanical fan-out — never spend frontier effort on enumeration.
- **When unsure between tiers, pick the higher one for design and the lower one for
  execution**: e.g. Fable 5 designs the PEX device-model register map, Opus implements it.
- `claude-mythos-5` is the same underlying model as Fable 5 but available only through
  Project Glasswing; use `claude-fable-5` unless the org has Glasswing access.
- **Budget**: the plan already flags CI/compute quota pressure (OpenBMC Yocto + QEMU-from-source
  + dual kernel matrices). The same discipline applies to model spend — Haiku + `low` effort is
  the lever for the high-volume mechanical stages; frontier spend is reserved for the items in
  the Fable 5 row and for verification, where being wrong is expensive.

## RE-verification pattern (cross-cutting)

Reverse-engineered claims — decoded registers, GPIO maps, device-model reset values,
decompiled PEX commands — are exactly the "plausible-but-wrong" hazard adversarial
verification exists for. The rule, stated once and applied everywhere:

> Any RE claim that will drive a QEMU device model, a DTS entry, or a datasheet-cited doc
> is verified by **≥3 independent `claude-fable-5` skeptics**, each prompted to *refute*
> the claim (default to refuted when uncertain), before it lands. A claim survives only if
> a majority fail to refute it. The verify stage also runs the in-repo ground-truth
> cross-checkers (`uv run cross_check_dts.py`, `uv run parse_io_tables.py`) and treats a
> checker mismatch as an automatic refutation.

This gate sits between "extraction/implementation" and "merge" in every pipeline below.

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
(the review pass is a `claude-fable-5` adversarial code-review sub-agent — see Verification).
All the new forks are added to `.gitmodules`.

## Dependency ordering

Register docs **(i)** → QEMU device model **(a)** → test bench **(b)** are done as **one triplet per
device**, and are the prerequisite for verifying drivers **(c)**, U-Boot **(e)**, and BMC firmware
**(f/g)** that touch that device. `(d)` rebase automation is built early (cheap CI plumbing that every
later phase depends on). `(h)` is one two-backend harness (QEMU now, HIL later) consumed by all
firmware phases. Honoring the user's priority, docs `(i)` + scaffolding come first, then OpenBMC `(f)`
and emulation `(a/b)` proceed in parallel.

The triplet structure is why `pipeline()` is the program's default shape: each device is an
independent item flowing through doc → model → bench → verify, and devices never need to wait
on each other.

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

**Orchestration.** The RTD/Sphinx import is a `pipeline()` over the repo's existing Markdown:
Haiku (`low`) enumerates and classifies files → Sonnet converts each to MyST + fixes intra-doc
links → Sonnet wires the link-check CI job. Rebase-bot YAML and stub scaffolding: Sonnet.
The `firmware-testbench/` harness refactor (three bespoke harnesses onto one `Target`
abstraction, existing CI jobs must pass unchanged): Opus at `xhigh`, isolation `worktree`
(`wt/docs` and the harness work run concurrently). The C4/NCSI `STATUS.md` correction is a
single Fable-5 task — the claim is subtle (runtime gdb tracing disproved NCSI; the real gate
is `cfg[0x225]` + ftgmac100 completeness) and the correction must survive an adversarial
re-read of `AST2050-PERIPHERAL-MODELING.md`.

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

**Orchestration — the anchor pattern for the whole program.** One `pipeline()` over the device
list `[INA219, PCA9548, ADT7462, TMP75/LM75, PCA9555, PCA9544, PEX8696/8647]`, three stages
per device:

1. **Register-doc extraction** from `datasheets/` + `pex-i2c-analysis/PEX-I2C-COMMANDS.md`
   into the RTD register reference — Opus for the straightforward sensor/mux parts; **Fable 5**
   for PEX8696/8647 (protocol reconstructed from decompilation, the plan's hardest RE).
2. **QEMU model + qtest bench** in the `mithro/qemu` fork — Opus at `xhigh`, isolation
   `worktree` (each device gets its own worktree so models land independently).
3. **Adversarial verify** of the register semantics — 3× Fable-5 skeptics + the ground-truth
   checkers, per § RE-verification — before the `qemu-qtest` gate counts.

Because it's a pipeline, INA219 can be in verify while PEX is still in extraction. The
`c410x-bmc` machine wiring and the C4 EEPROM/ftgmac100 work are Opus builds, with a
dedicated Fable-5 verify on the MAC-info `cfg[0x225]` gating (a mis-modeled enable byte
silently breaks the C4 acceptance test). NS9360 board-completion (a7): Opus.

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

**Orchestration.** Recipes, entity-manager JSON, and dbus-sensors config fan out as a
`parallel()` over the sensor/subsystem groups (Opus per group) — a barrier is correct here
because the final Redfish-enumeration bench compares the *complete* merged sensor map against
`io-tables/` + `REUSING-KGPE-D16-WORK.md`, which needs all groups reconciled together first.
The PCIe switch daemon implements the decompiled PEX protocol → **Fable 5** for the protocol
logic, Opus for the phosphor scaffolding around it, verified against the `pex-i2c-models`
qtest from Phase 1A. XIP/stripping (f5): Opus, gated on the non-XIP boot.

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

**Orchestration.** The stable + master ×{kernel, U-Boot, QEMU, Zephyr} matrix is a
`parallel()` fan-out — one Opus agent per (project, variant) cell, each in its own worktree,
since the cells are fully independent and the matrix gate needs all of them green. Two
high-uncertainty long poles get **Fable 5**: the `aspeed-g3.dtsi` promotion (deciding what is
G3-generic vs board-specific vs SCU-override is a judgment call that shapes every later DTS)
and the NS9360 `mach-ns9xxx` forward-port (2.6.39 → latest, device-tree-ification of a dead
platform). Driver-bind confirmation across the matrix is a Haiku sweep over boot logs.

### Phase 3 — WallaBMC (Zephyr) track (g) + full ARMv5 Zephyr port
- **`mithro/zephyr` `arch-arm926ejs`**: add ARM926EJ-S/ARMv5TE architecture support (exceptions, MMU/cache,
  timer, GIC/VIC, boot) — the biggest single deliverable. Validate first on a Zephyr `qemu`-friendly
  ARM926 target, then `soc-ast2050` and `soc-ns9360` + board defs.
- **`mithro/wallabmc`** board ports on the Zephyr fork; bring up Redfish/web/power/console. Because upstream
  WallaBMC lacks sensors/fans/PCIe, extend it (or document the gap) to cover the BMC sensor/fan/PCIe needs.
  Verified in QEMU via the same `firmware-testbench` Redfish/power/console benches; differentiator vs
  OpenBMC is footprint (smaller flash/RAM).

**Orchestration.** The ARMv5 arch port is the program's single biggest, highest-uncertainty
deliverable and is **Fable-5-led at `max` effort**: a design pass (exception model, MMU/cache
strategy, VIC vs GIC, boot flow) de-risked by the QEMU-ARM926 spike *before* any SoC/board
work, with the design adversarially verified against the ARM926EJ-S TRM. Implementation of
the designed subsystems then pipelines to Opus agents (one per subsystem, worktree-isolated).
`soc-ast2050` / `soc-ns9360` + board defs and WallaBMC bring-up: Opus. The
sensors/fans/PCIe gap analysis vs upstream WallaBMC: Sonnet (documentation-shaped), with
Fable 5 deciding extend-vs-document per gap.

### Phase 4 — HIL verification (h2) — when `rpi*-pmod`/`gwifi` boards arrive
- Implement `Target(backend=hil)` driving the RPi4/5 OpenOCD/UART/SPI rig (`RPI4-OPENOCD-JTAG-WIRING.md`,
  `openocd/*.cfg`). The **same** board-bench code runs on real hardware via a self-hosted-runner workflow
  (`hil-*.yml`), proving QEMU and silicon behave identically. Build the HIL backend stubbed now.

**Orchestration.** `Target(backend=hil)` implementation: Opus (well-scoped — the bench code
already exists from Phase 0; only the backend is new). Verification is definitionally reuse:
the same benches run on silicon. QEMU-vs-silicon divergences, when they appear, are RE
findings and route through the § RE-verification pattern (Fable-5 skeptics decide whether
the model or the doc is wrong).

## Test-bench approach (deliverables b + h)
- **Layer 1 — qtest (C, in `mithro/qemu/tests/qtest/`)**: register-level device-model correctness; fast,
  headless, native (`meson test`), CI job `qemu-qtest`.
- **Layer 2 — `firmware-testbench/` (Python)**: full boot/SSH/curl/i2cdetect/hwmon/GPIO assertions over a
  pluggable `Target` backend. **One bench, two backends** (`qemu` in CI now, `hil` on real boards later).
  Reuses existing bespoke harnesses — no new framework (Avocado) needed.

## Hard problems / risks (tracked honestly)
- **Full ARMv5 Zephyr port** (decision 3) is the largest, highest-uncertainty deliverable — de-risk with a
  QEMU ARM926 spike before SoC/board work (Fable-5-led; see Phase 3 Orchestration).
- **OpenBMC on AST2050** may not fit even with XIP/stripping — boot non-XIP first, then squeeze; WallaBMC is
  the lighter fallback.
- **NS9360 mainline Linux** doesn't exist — forward-porting `mach-ns9xxx` is a long pole (Fable-5 tier).
- **Dual-variant (stable + master) patch stacks** ×4 projects is real maintenance load — the rebase-bots
  (Phase 0) exist precisely to carry it.
- **CI/compute budget**: OpenBMC Yocto + QEMU-from-source + dual kernel matrices are heavy and may hit
  quota; expect to pause/resume (user pre-authorized). Use ccache and artifact caching aggressively.
  The same applies to model spend — see § Model tiering (Haiku/`low` for volume; Fable 5 reserved for
  the frontier-reasoning row and verification).

## First concrete work items (highest leverage)
1. Wire `origin`; verify `d16-qemu-stack.yml` green; **merge PR #16 into `main` (`--no-ff`)**; fix the C4/NCSI
   claim in `STATUS.md` (single Fable-5 verify task).
2. Create the six public repos/forks; add as submodules; stand up the **RTD/Sphinx docs site (i)**
   (Haiku→Sonnet pipeline) and the **dual-variant rebase-bots (d)** (Sonnet).
3. Build the **`firmware-testbench/` two-backend harness** by refactoring the three existing harnesses
   (Opus, `xhigh`, worktree).
4. Land the **INA219 + PCA9548 device-model triplet** (doc → QEMU model → qtest, with the 3-skeptic
   Fable-5 verify stage) + `qemu-qtest` job — proves the a/b/i pattern *and* the orchestration
   pattern; unblocks the `c410x-bmc` machine, sensor drivers, and OpenBMC sensors.
5. **Close C4 faithfully** (I2C MAC-info EEPROM + ftgmac100 completeness) with a `qemu-c410x-vendor-web`
   job (Opus build, Fable-5 verify on the `cfg[0x225]` gating).

Items 1–4 run in parallel worktrees; item 5 builds on item 4's I2C EEPROM plumbing.

## Verification
- **Per QEMU device model**: `meson test --suite qtest` in the `mithro/qemu` fork (job `qemu-qtest`) — each
  bench asserts reset values + R/W + I2C addressing/mux gating. Register semantics behind each bench have
  passed the § RE-verification skeptic gate before the job counts.
- **Board-complete emulation**: `firmware-testbench --backend qemu --bench board_c410x` (i2cdetect map,
  hwmon reads, GPIO presence, power sequence) green in CI.
- **C4**: `qemu-c410x-vendor-web` boots vendor firmware and `curl :8080` returns appweb.
- **Kernel/U-Boot**: `d16-qemu-stack.yml` + matrix (stable + master) boot both boards to SSH; TFTP netboot
  job reaches Linux.
- **OpenBMC/WallaBMC**: image boots in QEMU via `firmware-testbench` → SSH + `GET /redfish/v1` + sensor
  enumeration + power sequencing; XIP image fits the DTS flash/RAM budget.
- **Docs**: ReadTheDocs build + link-check green.
- **HIL (later)**: the identical board-bench passes on real hardware via `hil-*.yml`.
- **Every merge to private `main`**: green CI + an adversarial code-review pass by a
  `claude-fable-5` sub-agent (the `code-review` skill at high effort; findings verified, not
  just listed), integrated with a `--no-ff` merge commit.

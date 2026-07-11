# Upstream-bump status log (branch `claude/bmc-upstream`)

Goal (standing directive): track the LATEST UPSTREAM of kernel + QEMU + OpenBMC,
**incrementally and conservatively**. Overriding rule: the proven faithful boot
MUST keep working — a bump that regresses any of the 9 BMC features is a failure;
a partial, well-documented bump is a success.

Base: `claude/bmc-functionality` @ 38d9e8d, QEMU submodule @ a010d69, kernel v6.6.70.

## Version landscape (checked 2026-07-12)

| Component | Current | Latest LTS | Latest stable | Project also uses |
|-----------|---------|-----------|---------------|-------------------|
| Linux     | v6.6.70 | v6.12.95  | v6.19.14      | v6.18.38 (modern OpenBMC) |
| QEMU fork | mithro/qemu ast2050-faithful @ a010d69 (base = upstream 561f025 = v10.0.7 stable) | — | v10.x | — |

## Plan

1. Baseline: build current QEMU + kernel v6.6.70 + initramfs, run the regression
   subset (C2 ssh, C4 web (QEMU oracle), F7 ncsi, boot-usb, boot-nfsroot,
   host-kcs, power fwtest, smoke). Record PASS before changing anything.
2. Kernel → v6.12.95 (LTS): re-apply clk/ftgmac100/w83795 patches + g3-vic driver
   + DTS + config fragments. Rebuild, re-run regression. Commit only if green.
3. Kernel → v6.19.14 (latest): port irq_domain_add_simple→create_simple in
   g3-vic (removed ~6.16) + any other API deltas. Verify. Commit if green, else
   document blocker and keep 6.12 as the branch's kernel.
4. QEMU: assess rebase of the ~30-commit AST2050 stack (2225 LoC over 29 files;
   conflict-prone: aspeed_ast2400.c +357, aspeed.c +101, aspeed_scu.c +89,
   aspeed_gpio.c +89, aspeed_vic.c +73, ftgmac100.c +52, aspeed_timer.c +48)
   onto latest QEMU. Bump if tractable + non-regressing; else document + defer.

## Progress

### Baseline (current stack: QEMU 10.0.7 @ a010d69 + kernel v6.6.70) — GREEN (2026-07-12)

Local host: 12 cores, ~25 GB free RAM; builds at `nice -n 15 -j4`, one at a time.

| Check | Result |
|-------|--------|
| QEMU build (qemu-system-arm 10.0.7) | PASS — `-M kgpe-d16-bmc` registered |
| QEMU machine smoke (`run-qemu.py smoke`) | PASS |
| Kernel v6.6.70 build (uImage+zImage+dtb) | PASS — all 3 patches applied clean, 0 dropped Kconfig symbols |
| Initramfs (BusyBox 1.37 + dropbear 2024.86) | PASS |
| Full bare-metal QEMU-model suite (`qemu-model/integration/`) | PASS — 76 passed, 10 xfailed |
| F2 power fwtest (`test_power.py`) | PASS — 6/6 |
| C2 boot + SSH (`ssh-test.py`) | PASS — `SSH_OK / kgpe-d16-bmc / Linux armv5tejl` |
| F6 boot-usb (`usb-test.py`) | PASS — aspeed_vhub probe + gadget enum |
| F5b host-kcs (`f5b-host-kcs-test.py`, 64 MB) | PASS — /dev/ipmi-kcs3 + ast-kcs-bmc + LPC poke |
| C5 boot-nfsroot (`nfsboot-test.py`) | PASS — root over NFSv3 + SSH |
| F7 ncsi dedicated-PHY (`f7-ncsi-evidence.py`) | boot invariants 5/5 PASS + committed fragments clean (see note) |

**F7 note (local-only artifact, NOT a regression):** the `CONFIG_NET_NCSI` static
check `rglob`s `qemu-firmware/kernel/` and, when the kernel *build tree*
`kernel/linux/` is present locally, finds `CONFIG_NET_NCSI=y` in the built
`.config` + upstream `aspeed_g4/g5_defconfig` → exit 1. In CI `kernel/linux/` is
never checked out (only the kernel artifact is downloaded), so the scan sees only
the committed fragments (none set NCSI) → pass. The real faithfulness signal — the
5 runtime boot-log invariants (dedicated PHY, eth0 DHCP, ZERO NC-SI at runtime) —
PASSES. I therefore track F7 by the boot invariants + committed-fragment scan, both
green, before and after every bump.

| U-Boot v2019.04-aspeed (`build-uboot.sh`) | PASS |
| C4 proprietary Dell firmware → BMC web (`web-test.py`) | PASS — Mbedthis-Appweb/2.4.2, HTTP 301 → login.html |

C4 is the QEMU faithfulness oracle (boots the *vendor* kernel, so it is
kernel-independent — it validates QEMU changes, not kernel changes).

- [DONE] Baseline established: **GREEN** across QEMU + kernel + all boots/oracles.

### Kernel bump v6.6.70 → v6.12.95 (LTS) — port + build

Rationale for v6.12.95: the current LTS, a genuine +6-minor forward step from the
6.6 LTS, lowest-risk modern target (the `irq_domain_add_simple` legacy API the
g3-vic driver uses still exists here; it is removed by 6.19 — see below). This is
the conservative committed step; v6.19.14 (latest) is attempted afterward.

Patch porting onto a pristine v6.12.95 clone:
- `0001-clk-aspeed-add-ast2050-support.patch` — applies clean (no change).
- `0002-ftgmac100-set-mac-speed-from-cur_speed-g3.patch` — applies clean (no change).
- `0003-hwmon-w83795-modern-hwmon-registration.patch` — **needed porting**.
  `git apply` failed at hunk 3 (`w83795.c:2134`). Cause: upstream migrated the
  probe from `i2c_match_id(w83795_id, client)->driver_data` to
  `(uintptr_t)i2c_get_match_data(client)` (the tree-wide `i2c_get_match_data()`
  cleanup, ~6.7), which also **removed the forward declaration**
  `static const struct i2c_device_id w83795_id[];` — the exact context line hunk 3
  keyed on. The patch's five changes are all still semantically valid (verified:
  fuzzy apply = git-apply of the regenerated patch, byte-identical result).
  Ported by regenerating the patch against v6.12.95 context (144→144 lines, same
  semantics); it now `git apply`s cleanly to a pristine v6.12.95 tree.
- g3-vic driver + DTS + config fragments: unchanged; build clean, 0 dropped
  Kconfig symbols (only benign merge_config `-m` "redefined by fragment" notes).

**6.12.95 build:** EXIT 0 — uImage+zImage+dtb, `irq-aspeed-g3-vic.o` compiled.

**6.12.95 regression (new kernel on the unchanged QEMU 10.0.7) — GREEN:**

| Check | Result |
|-------|--------|
| C2 boot + SSH | PASS — `Linux armv5tejl` |
| F6 boot-usb | PASS — vhub probe + gadget enum |
| F5b host-kcs (64 MB) | PASS — `6.12.95-dirty` booted, /dev/ipmi-kcs3, HICR0=0x80, ODR3=0x5a |
| C5 boot-nfsroot | PASS — NFSv3 root + SSH |
| F7 ncsi dedicated-PHY | boot invariants 5/5 PASS (same local CONFIG_NET_NCSI artifact as baseline) |

QEMU-model integration suite (76p/10xf), F2 power fwtest (6/6) and C4 web oracle
are kernel-independent (QEMU unchanged) → still green from baseline; not re-run.

**Committed:** `build-kernel.sh` default `KERNEL_VERSION` v6.6.70 → **v6.12.95**
+ regenerated patch 0003. This is the safe LTS checkpoint on the branch.

### Kernel bump v6.12.95 → v6.19.14 (latest) — attempt

Known blocker to port: g3-vic uses `irq_domain_add_simple(node, …)`, removed
~6.16 in favour of `irq_domain_create_simple(of_fwnode_handle(node), …)`.

Port work onto a pristine v6.19.14 clone:
- All 3 patches (0001 clk, 0002 ftgmac100, 0003 w83795-regenerated) `git apply`
  **clean** — the 6.12 regeneration of 0003 also fits 6.19 (i2c_get_match_data
  was already in place by 6.12 and unchanged since).
- g3-vic driver: confirmed `irq_domain_add_simple` is **gone** from
  `include/linux/irqdomain.h` in 6.19.14 (`irq_domain_create_simple` + the
  `of_fwnode_handle()` macro are present, and also in 6.12 → bi-compatible).
  Ported the one call to `irq_domain_create_simple(of_fwnode_handle(node), …)`.
  Other driver touchpoints verified still present in 6.19.14: `irq_domain_ops`
  `.map`/`.xlate`, `irq_domain->host_data`, `irq_domain_xlate_onetwocell`,
  `generic_handle_domain_irq`.

**6.19.14 build:** EXIT 0 — uImage+zImage+dtb, ported `irq-aspeed-g3-vic.o`
compiled clean, 0 dropped Kconfig symbols.

**6.19.14 regression (latest kernel on the unchanged QEMU 10.0.7) — GREEN:**

| Check | Result |
|-------|--------|
| C2 boot + SSH | PASS — `Linux armv5tejl` |
| F6 boot-usb | PASS |
| F5b host-kcs (64 MB) | PASS — `6.19.14-dirty` booted, /dev/ipmi-kcs3, LPC serviced |
| C5 boot-nfsroot | PASS |
| F7 ncsi dedicated-PHY | boot invariants 5/5 PASS (same local artifact) |

**Committed:** `build-kernel.sh` default → **v6.19.14** (latest upstream stable),
g3-vic ported to `irq_domain_create_simple()`. The v6.12.95 LTS build stays
supported via `KERNEL_VERSION=v6.12.95` (patches + ported driver are
bi-compatible) and remains a proven checkpoint in this branch's history (commit
"kernel: bump ... v6.6.70 -> v6.12.95").

### Kernel outcome

**v6.6.70 → v6.19.14 (latest upstream stable): DONE, non-regressing.** The whole
kernel-facing regression subset (C2/F6/F5b/C5/F7) passes on the latest kernel over
the unchanged faithful QEMU; the QEMU-model oracles (integration suite, power
fwtest, C4 vendor web) are kernel-independent and unaffected.

### QEMU bump assessment — DEFERRED (documented, gitlink stays at a010d69)

Fork `mithro/qemu` `ast2050-faithful` @ a010d69 = 30 AST2050 commits (2225 LoC /
29 files) on top of upstream `561f025` (v10.0.7 stable, which branched from master
at v10.0.0). Latest upstream is **v11.0.2** (gap: 10.1, 10.2, 11.0).

Empirical rebase-conflict surface — `git merge-tree --merge-base=561f025 a010d69 <tag>`
(the exact "rebase the AST2050 stack onto upstream" 3-way merge):

| Onto | Textual conflicts | Files |
|------|------------------:|-------|
| v10.1.0 | 3 | aspeed.c, aspeed_gpio.c, aspeed_scu.c |
| v10.2.4 | 4 | + aspeed_ast2400.c |
| **v11.0.2** | **6** | + include/hw/arm/aspeed_soc.h, include/hw/misc/aspeed_scu.h |

**What upstream changed (the blockers), by evidence:**
- `12d1a768bd "qom: Have class_init() take a const data argument"` — a **tree-wide
  signature change** (`class_init(ObjectClass*, void*)` → `const void*`) that hits
  *every* class the AST2050 stack adds: the SoC class + w83795 + lpc/pwm/rtc/smc/
  udc/video device models. Present already at v10.1.0.
- aspeed SoC base-class API refactor in `aspeed_ast2400.c` (v10.2+): `21b3898a69`
  removes the `get_irq` hook; `448c4502a5`/`68f915b91c`/`15f26071bf`/`bb3219345a`
  drop the `AspeedSoCState`/`AspeedSoCClass` dependency from `aspeed_mmio_map()`,
  `aspeed_mmio_map_unimplemented()`, `aspeed_soc_uart_realize()`,
  `aspeed_soc_cpu_type()` — the exact helpers the AST2050's +310-line interleaved
  `soc_init`/`soc_realize` calls.
- `aspeed.c` (52 commits, v11.0): the "split each machine into its own source file"
  campaign + `aspeed_connect_serial_hds_to_uarts()` rename — the `kgpe-d16-bmc`
  machine registration must move/adapt.

**Why defer, not force:** the textual conflict count *understates* the work —
`merge-tree` reports only text conflicts, but the auto-merged new
`aspeed_*_ast2050.c` model files would still **fail to compile** against the changed
upstream APIs (const `class_init`, the removed SoC-helper deps). A real bump means
resolving 6 conflicts **plus** adapting ~15 AST2050 model/SoC files to the new APIs
**plus** the machine-file-split restructure, then rebuilding and re-validating the
*entire* faithful stack (C4 vendor-boot oracle + the 76-test integration suite +
every F-feature boot). That is precisely a "large conflict surface that risks the
proven models" — forcing it risks regressing the faithfulness oracle. Per the
overriding rule, deferring with this documentation is the correct outcome. Gitlink
left at **a010d69**; the kernel now tracks latest over this unchanged, proven QEMU.

**Recommended incremental path (future work):** bump one minor at a time, not
straight to v11. v10.0.7 → **v10.1.0** is the tractable first step (3 textual
conflicts, `aspeed_ast2400.c` still auto-merges) and its main real change is the
mechanical `class_init` const-data adaptation across the AST2050 models. Then
v10.2 (adapt to the SoC-helper API refactor), then v11.0 (adapt to the machine
split). Validate C4 + the integration suite + the boots after each step. Prefer
refactoring the AST2050 SoC additions in `aspeed_ast2400.c` toward *self-contained*
`aspeed_ast2050.c` functions (fewer interleaved edits) to shrink future conflict
surface.

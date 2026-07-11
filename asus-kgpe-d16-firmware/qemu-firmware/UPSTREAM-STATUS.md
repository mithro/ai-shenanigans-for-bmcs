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

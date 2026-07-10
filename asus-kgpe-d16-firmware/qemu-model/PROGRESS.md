# Progress log — AST2050 faithful QEMU model

Newest entries at the bottom of each day. Committed after every change (repo rule).
Dates are ISO 8601 (YYYY-MM-DD).

## 2026-07-10 — Phase 0: program setup

- **Pivot recorded.** New goal: OpenBMC booting via TFTP + NFS root inside a QEMU
  that faithfully emulates the AST2050 (G3) hardware, with a comprehensive
  per-peripheral test suite proving emulation ≡ silicon. See `README.md`.
- **Reconnaissance done.** Audited existing QEMU work: the `kgpe-d16-bmc` machine
  (PR #16) boots U-Boot/kernel/Raptor/vendor firmware but is **G4/AST2400-based**,
  not faithful to the G3. Modern OpenBMC+Redfish (PR #22) runs only on
  `romulus`/AST2500. Neither is a faithful AST2050 nor TFTP+NFS. → this program is
  genuinely new work. The `firmware-testbench` module (PR #17, two backends:
  qemu + hil) is the integration-test substrate.
- **Workspace.** New isolated worktree `.worktrees/ast2050-qemu` on branch
  `claude/ast2050-qemu-faithful`, branched off `main` (has firmware-testbench,
  datasheets, culvert submodule), then `git merge --no-ff` of
  `claude/d16-qemu-firmware-stack` to pull in the QEMU fork + machine + build
  scripts. Only conflict was `.gitmodules` (resolved: union of both submodules).
  A prebuilt `qemu-system-arm` with the custom machine exists in the d16-qemu
  worktree — fast local iteration is possible without a full rebuild.
- **Authoritative register base addresses** taken from Raptor `hwreg.h`: VIC
  `0x1E6C0000` (compact G3 bank), SCU `0x1E6E2000`, SDRAM `0x1E6E0000`, MAC1
  `0x1E660000`, timer `0x1E782000`, UART2 `0x1E784000`, WDT `0x1E785000`, GPIO
  `0x1E780000`, AHB `0x1E600000`, SMC `0x16000000`.
- **Plan + matrix written** (`README.md`): 20-row peripheral inventory, the
  4-deliverable definition of done, golden-reference validation methodology, and a
  6-phase incremental roadmap (Phase 1 SoC identity/boot → Phase 6 OpenBMC over
  TFTP/NFS).
- **Dispatched** a subagent to extract the datasheet-cited authoritative memory map
  into `AST2050-MEMORY-MAP.md` (confirms/corrects the matrix's TBD rows).

### Datasheet map returned — authoritative corrections (fold into matrix)
From `AST2050-MEMORY-MAP.md` (datasheet A3 V1.05 §9, pp.97–98):
- **SCU7C rev-id = `0x00000202`** for AST2050-A3 (§18.2 p220), matching the culvert
  HW read. QEMU returns `0x01000303` → confirmed unfaithful.
- **VIC** is a single 32-bit bank (0x00–0x38), 32 sources; **no** G4 second bank.
- **Flash** = legacy **SMC regs @`0x16000000`, flash data @`0x10000000`** (not G4 FMC).
- **Conventional PCI**: A2P bridge `0x1E720000`, arbiter `0x1E78C000`; culvert P2A
  rides the PCI-slave BAR (not PCIe/XDMA).
- **ABSENT on AST2050** but present in the reused G4 memmap: **ADC**, SD/eMMC, eSPI,
  UARTs 3–5, graphics-display controller, USB1.1 host. 16-bit DRAM, ≤128 MB, no ECC.
  → the faithful machine must *remove/abort* these, not return 0.

### Harness built + first finding (DONE)
- `fwtest/` harness complete: crt0 + linker (DRAM 0x40000000), console UART
  `0x1E784000`, deterministic `[FWT]` report protocol, `build.py` (compile + boot
  under `-M kgpe-d16-bmc`, capture serial). Builds with `arm-none-eabi-gcc` 14.2.
- **Smoke test ran end-to-end on QEMU.** Console works; identity registers read:
  `scu.protect=1688a8a8`, `scu.revid=01000303`, `scu.strap=0a08e416`,
  `scu.clksel=f3f40000`, `scu.hpll=00000291`, `scu.mpll=00030291`,
  `sdmc.config=00000041`, `vic.irqstat/rawstat=0`.
- **Finding #1 (rev-id):** `scu.revid.is_ast2050_a3` FAIL got=`01000303`
  want=`00000202`. The harness mechanically reproduced the datasheet+HW-backed gap.

### Phase 1 — SCU: rev-id made faithful (model + test + integration all green)
- QEMU fork submodule initialised in this worktree and **built from source**
  (`scripts/build-qemu.sh` → `qemu/build/qemu-system-arm`, `-M kgpe-d16-bmc` OK).
- To avoid disturbing PR #16, the model change is on a **new submodule branch
  `ast2050-faithful`** (branched from `d16-ast2050-machine` tip); `.gitmodules`
  repointed to it.
- **Fix:** `AST2050_A1_SILICON_REV` `0x01000303`→`0x00000202` in `aspeed_scu.h`.
  Justified: only 3 uses (property, valid-revs table by name, definition); the sole
  classifier `ASPEED_IS_AST2500` (bits[31:24]==0x04) is unaffected. Datasheet §18.2
  p220 + culvert HW both give `0x00000202`.
- **Deliverables done for the rev-id aspect:** `peripherals/scu/fwtest.c` (1),
  submodule model change (3), `integration/test_scu.py` — 4 pytest cases (4).
  Verified: `scu` + `smoke` fwtests FAIL→PASS; `pytest integration/test_scu.py` →
  4 passed. Remaining SCU aspects (strap bit decode, H-PLL/M-PLL clock tree,
  clock-select/PCLK divider faithfulness, and `DOC.md`) pending `DATASHEET-SCU.md`
  (subagent extracting SCU §18 in progress).

### Phase 1 — SCU: full register chapter + G3 reset table (8/8 checks green)
- Subagent extracted the full SCU §18 chapter → `peripherals/scu/DATASHEET-SCU.md`
  (every offset/reset value/bitfield cited) and `DOC.md` (driver-grade view). It
  surfaced **4 more gaps** beyond rev-id: PLL post-divider [14:12], G4 strap layout,
  whole AST2400 reset table reused, SCU00 read-back.
- `fwtest.c` expanded to dump+decode the whole SCU file and assert 9 golden values.
  Baseline: 7 fail (AST2400 reset table).
- **Fix (model):** new `aspeed.scu-ast2050` SCU variant with the datasheet §18 reset
  table (only the registers the G3 has), selected by the AST2050 SoC (keyed on
  silicon-rev; AST2400/2500 untouched). Committed on `ast2050-faithful`, pushed to
  mithro/qemu (`d74eeb79`).
- Result: **8/8 fwtest checks PASS** (SCU04/08/0C/20/24/3C/74 + rev-id), **9 pytest
  passed, 0 xfail**. Insight: SCU00 lock-state is **not** testable via `-kernel`
  (QEMU pre-unlocks when there's no U-Boot) — a documented harness limitation, not a
  model gap; needs a flash-boot harness.
- **Deferred (documented):** PLL post-divider [14:12] (timer clock-rate fidelity —
  tested with the timer peripheral; reset path unaffected since SCU24[18]=0) and the
  G3 strap-bit layout for SCU70.

### Regression watch
- The G3 reset table zeroes G4-only convenience values (e.g. SOC_SCRATCH1 was
  `0xC0` "DRAM ready"). Faithful per datasheet (Init=0), low-risk for -kernel/U-Boot
  boots (they don't depend on it), but the C1–C4 full-boot CI jobs should confirm.

### Phase 1 — VIC: compact G3 interrupt controller (13/13 checks green)
- Subagent extracted §16 + source Table 36 → `peripherals/vic/DATASHEET-VIC.md`:
  single 32-bit bank, 13 regs (0x00–0x38), all reset 0; IRQ map (timers 16/17/18
  rising-edge, UART1/2 9/10 level, MAC1=2, I2C=12, WDT=27, RTC 22–26 both-edge).
  The firmware trigger words reconstruct bit-for-bit from Table 36 and match the
  culvert HW capture: sense=0x903897FE, dual=0x07C00000, event=0x983F97FE.
- `fwtest.c`: dumps the file + checks reset (all 0) + writes the firmware words and
  checks read-back. Baseline: 6 fail — the AST2400 model hardwires
  sense/dual/event (0xfff8ffff etc.) and treats 0x24/0x28/0x2C as read-only.
- **Fix (model):** `aspeed.vic-ast2050` variant (`bool ast2050`): trigger-config
  regs reset 0 + fully writable; IRQ-raise logic and 32 source lines reused
  unchanged (boot IRQ path undisturbed). Selected by the AST2050 SoC. Pushed to
  mithro/qemu.
- Result: **13/13 fwtest checks PASS; integration suite 17 passed** (SCU 9 + VIC 8).
  Deferred refinement (documented): stop decoding the AST2400 0x80+ aliases (G3
  firmware never touches them — cosmetic only).

### Phase 1 — SDRAM (DDR2): test + doc done; model gated on the boot check
- Subagent extracted §17 (pp.183-203) → `peripherals/sdram/DATASHEET-SDRAM.md`:
  MCR00 lock-latch (unlock 0xFC600309, reads 0/1), MCR04 config `Init=0` with DDR2
  geometry ([3:2]=cap, [9:8]=width, [11]=bank), **no DRAM-size auto-detect** (firmware
  writes MCR04 from a constant), MCR100=0xA8, no ECC block.
- `fwtest.c` (6 checks) baseline: protect/unlock/refresh already faithful; **3 gaps**
  — MCR04 resets to a DDR3-synthesised `0x41` (want 0), writes get *recomputed* to
  `0x5c1` (want verbatim `0xD89`), MCR100 reads 0 (want 0xA8).
- **Model deferred + gated:** the `aspeed.sdmc-ast2050` DDR2 variant changes MCR04
  reset/encoding, which feeds U-Boot DRAM sizing — so it lands only after the CI
  C1–C4 boots confirm the SCU+VIC changes are green. The 3 gaps are xfail meanwhile.
- Integration suite: **21 passed, 3 xfailed**. Committed locally; **push held** so the
  in-flight CI boot run (validating SCU+VIC) isn't cancelled by the concurrency group.

### CI boot check (in flight)
- Run on the VIC commit: U-Boot/D16-kernel/Raptor-kernel/initramfs builds all green;
  custom-QEMU build + C2/C4 boot jobs still running. Pre-existing unrelated failure:
  the C3 Raptor *musl userspace* build (toolchain), not the SoC model — its boot skips.

### Next
- Confirm C1–C4 boots green → push the SDRAM work → implement the boot-gated DDR2
  SDMC model → timer (with SCU PLL post-divider clock-rate check) → UART → WDT.

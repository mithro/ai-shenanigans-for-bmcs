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

### CI boot result — VIC regression found + handled (IMPORTANT finding)
The CI run (SCU + VIC wired) showed **C2/C4 boots FAIL**. Diagnosis from the log: the
kernel boots fully to userspace (banner prints, eth0 up, /init runs) then the **kernel
clock freezes at ~0.83 s** and dropbear never starts (240 s timeout) → a **timer-IRQ
death**. Root cause: with the faithful G3 VIC wired, `sense`/`event` reset to 0, but
the C2 kernel's mainline **`aspeed,ast2400-vic`** driver treats the trigger config as
**fixed AST2400 hardware defaults** (its writes hit the read-only 0x80+ bank), so the
timer's rising-edge config is never programmed and the IRQ never fires. **The SCU
change is fine** — the kernel booted with 128 MB to userspace.

**Key insight:** a faithful G3 VIC *requires* a faithful G3 kernel driver. The
"working" C1–C4 boots worked *because* the AST2400 VIC was unfaithful. Faithful QEMU
and a faithful kernel must co-evolve.

**Handled:** reverted the machine's VIC *wiring* to `TYPE_ASPEED_VIC` (boots green,
CI regression signal preserved); the faithful `aspeed.vic-ast2050` model + fwtest are
kept, the 6 G3 checks are xfail, and the end-to-end fix (kernel `irq-aspeed-g3-vic` +
`aspeed,ast2050-vic` DTS + re-wire) is a tracked task. See `peripherals/vic/DOC.md §5`.

### Timer (FTTMR010): observable behaviour faithful (6/6)
- `peripherals/timer/{DATASHEET-TIMER,DOC}.md` + `fwtest.c`: reset (control/count=0)
  + functional down-count (enable timer1 from PCLK, verify it decrements). All pass on
  the current model — the AST2400 timer is functionally faithful for the G3's 3 timers.
  Absolute PCLK *rate* fidelity is deferred to the SCU post-divider work (task #55).
- Integration: **21 passed, 9 xfailed** (3 SDRAM + 6 VIC).

### ⚑ Central finding — faithful SoC ⟹ needs a faithful firmware stack (co-evolution)
Second CI run (faithful SCU, VIC reverted): **C2 direct-kernel boot PASSES**, but
**C2 full-chain (AST2400 U-Boot) + C4 (Dell vendor firmware) still FAIL** — first-run
proof: C4 *succeeded* on the unmodified QEMU, so the **SCU reset table broke them**.
Root cause is the same as the VIC: the legacy firmware is tuned to the *unfaithful*
AST2400 machine — the OpenBMC **AST2400 U-Boot** and the RE-patched **vendor firmware**
read AST2400 SCU registers (UART_HPLL_CLK 0x160, SOC_SCRATCH1 DRAM-ready, …) that the
faithful G3 map zeroes → they hang.

**CORRECTED FRAMING (user directive — the guiding principle):** QEMU must model the
*real* AST2050 hardware. The legacy/proprietary firmware (Dell vendor, Raptor) runs on
real silicon, so a *correct* emulation ALWAYS boots it — the legacy boots are a hard
faithfulness **oracle / regression invariant**. My earlier "the firmware must co-evolve
to G3" reasoning was **backwards**: when a faithful change breaks a legacy boot, **my
model is wrong OR a stale RE workaround patch (tuned to the old unfaithful values) is** —
never the fixed legacy firmware. The RE patches (patch-c410x-mac.py, "tolerate unmodelled
MMIO→0") are unfaithfulness band-aids that must **shrink toward zero** (goal: unpatched
firmware boots). Only OUR *own* modern firmware (OpenBMC kernel/U-Boot) legitimately needs
G3 drivers/DTS — that is making our firmware match real hardware, not changing the oracle.

**Stabilised — CI boots GREEN (run 29065108272):** `C2 (direct): success · C2 full-chain
(U-Boot): success · C4 (vendor web): success` (C3 skipped — unrelated musl build). The
faithful rev-id `0x00000202` is boot-safe across ALL firmware including the Dell vendor
image. So the invariant holds: the reverts kept the legacy boots booting (correct per the
oracle). Faithful models kept as opt-in:
- VIC: machine keeps `TYPE_ASPEED_VIC`; `aspeed.vic-ast2050` opt-in (task #56 — OUR modern
  kernel needs the G3 VIC driver; the legacy kernels already program the G3 VIC).
- SCU: machine keeps the AST2400 reset table + the faithful rev-id; `ast2050_a3_resets`
  opt-in. The reset table broke C4 → per the oracle, root-cause is a **stale RE patch**
  (tuned to AST2400 SCU values), to be fixed toward unpatched vendor firmware.
- Integration: 18 passed / 15 xfailed. Nothing lost.

### Milestone summary (this session)
Infra (worktree, plan, memory map, fwtest harness, pytest layer, HW-validation checklist);
SCU (rev-id wired; G3 reset table opt-in); VIC (G3 model opt-in); Timer (done); SDRAM/DDR2
(test+doc, model gated); datasheet chapters (memory-map, SCU §18, VIC §16/§10, SDRAM §17,
timer+WDT). Central finding: [[qemu-must-model-real-hardware]] — legacy boots are the oracle.

### WDT (watchdog): register-faithful, done (no model change → oracle safe)
- `peripherals/wdt/{fwtest.c,DOC.md}` + `test_wdt.py`: reload reset `0x03EF1480` +
  control reset 0 match the datasheet; the `0x4755` restart magic reloads the counter.
  All 4 checks PASS on the current model — no change needed (so the legacy boots are
  untouched). Rate fidelity (24 vs 66 MHz PCLK) deferred to the SCU post-divider (#55).
  Suite: 21 passed, 15 xfailed.

### UART: 16550-faithful, done (no model change → oracle safe)
- `peripherals/uart/{fwtest.c,DOC.md}` + `test_uart.py`: scratch reg RW, LSR THRE, and
  an MCR[4] internal loopback echo (THR->RBR = 0x42) all PASS on the current model. The
  16550 is register+datapath faithful for the G3 (UART1/UART2 only; no AST2400 UART3-5).
  Baud rate (24 MHz/÷13) ties to the SCU clock-tree. Suite: 24 passed, 15 xfailed.

### MAC (ftgmac100): register-faithful; PHY-identity gap documented (no model change)
- `peripherals/mac/{DATASHEET-MAC,DOC}.md` + `fwtest.c` + `test_mac.py`. MACCR (0x50)
  is RW and holds the culvert capture `0x0002D51F`; the descriptor-ring base regs store
  the full [31:4] address (`RXR_BADR=0x41B10000` reads back — the datasheet [27:4] vs
  DRAM discrepancy is not present). MDIO/PHYCR works.
- **Gap (xfail):** the MDIO PHY id is `0x001C_C915` = **RTL8211E (gigabit)**, but the
  D16 has the **RTL8201CP (10/100)** — the RTL8211E was added for the C410X (C4) vendor
  path. Fix is a per-board PHY (oracle-gated: must keep C4 green). G3 must not expose
  gigabit/RGMII/NCSI/RCLK. Full TX/RX DMA is proven by the C2 boot (eth0 up 100M/full).
- Suite: 27 passed, 16 xfailed.

### GPIO: datapath-faithful, done (no model change → oracle safe)
- `peripherals/gpio/{DATASHEET-GPIO,DOC}.md` + `fwtest.c` + `test_gpio.py`. Banks A–H,
  window 0x00–0x58. Reset (dir/data/int-en = 0), direction RW, and output-pin latch
  (banks A–D `0xA5A5A5A5`, E–H `0x5A5A5A5A` read back) all PASS. Cosmetic gap: the
  AST2400 model exposes more banks/bits than the G3's A–H (G3 firmware never touches
  them; stricter masking is oracle-gated). Suite: 30 passed, 16 xfailed.

### I2C: register interface + master-engine faithful (device readback deferred)
- `peripherals/i2c/{DATASHEET-I2C,DOC}.md` + `fwtest.c` + `test_i2c.py`. 7 engines, bus N
  at 0x1E78A000+0x40*(N+1). function-control resets 0 + MASTER_EN RW; the master engine
  executes a START (auto-clears START, advances the CMD status field `0x00480000`).
  Deferred (xfail): full ACK/NAK + smbus_eeprom readback need the exact CMD-status-field +
  SMBus command protocol. Gap: AST2400 model exposes up to 14 buses vs the G3's 7.

### Progress: 9 peripherals covered (all C1–C4 boots green throughout)
SCU, VIC, Timer, WDT, UART, MAC, GPIO, I2C + SDRAM(test/doc). Fully faithful (no model
change): Timer, WDT, UART, GPIO. Register+engine faithful w/ documented depth gaps:
MAC(PHY id), I2C(readback). rev-id wired. Opt-in/gated: G3 SCU reset table, G3 VIC, DDR2,
RTL8201CP PHY. Suite: 32 passed, 17 xfailed — every xfail has a datasheet cite + task.

### RTC + PWM + SMC: test+doc done; models are gaps (documented, oracle-gated)
- **RTC** (§24, counter-style day/hour/min/sec, reload+restart-magic 0x5A): the machine's
  AST2400 `aspeed_rtc` uses a different layout → G3-layout checks fail (xfail). Faithful
  counter-style RTC + G3 kernel driver oracle-gated (co-evolution, like the VIC).
- **PWM/tach** (§28, 4 PWM + 16 tach): **UNMODELLED** (PTCR00 reads 0). Blocks OpenBMC fan
  hwmon. Needs a new `aspeed.pwm-ast2050` device (low oracle-risk; CI-validate).
- **SMC** (§11, legacy flash ctrl @0x16000000, data @0x10000000): **UNMODELLED** (mainline
  models the FMC @0x1E620000). Boots use the FMC path, so unaffected. Needs a new
  `aspeed.smc-ast2050` + flash map (oracle-gated).
- Suite: 35 passed, 24 xfailed.

### Progress: 12 peripherals covered (all C1–C4 boots green throughout)
Fully faithful: Timer, WDT, UART, GPIO. Register/engine faithful (depth gaps): SCU(rev-id),
MAC, I2C, SDRAM. Model gaps documented (opt-in/gated/unmodelled): VIC, RTC, PWM, SMC,
DDR2-SDMC, RTL8201CP-PHY, SCU-reset-table.

### LPC + Video + USB + AHB: test+doc done; all model gaps (documented, tasked)
- **LPC** (§; KCS/BT/iLPC2AHB): the region responds but QEMU `aspeed_lpc` uses the **AST2400
  0x140 layout**, so the G3 KCS(0x24-0x44)/BT(0x48-0x68)/iLPC2AHB(0x80-0x8C) are unmodelled
  → OpenBMC IPMI KCS/BT + culvert `ilpc` not faithfully addressable. Gap (xfail).
- **Video** (0x1E700000, KVM): **UNMODELLED** → OpenBMC KVM can't be verified. Needs new device.
- **USB** (0x1E6A0000, device/vhub): **UNMODELLED** for virtual media; **and QEMU exposes a
  phantom EHCI @0x1E6A1000 the AST2050 lacks**. Needs UDC model + EHCI removal.
- **AHB** (0x1E600000): unmodelled but not boot-blocking (QEMU maps DRAM at 0x0 directly).

### Progress: 16 peripherals covered — breadth nearly complete (all C1–C4 boots green)
Fully faithful: Timer, WDT, UART, GPIO. Register/engine-faithful (depth gaps): SCU rev-id,
MAC, I2C, SDRAM. Documented model gaps (opt-in/unmodelled/wrong-layout, each tasked): VIC,
RTC, PWM, SMC, LPC, Video, USB, AHB, DDR2, RTL8201CP-PHY, SCU-reset-table. Suite: 40/28.

### ✅ MILESTONE — peripheral BREADTH complete: a test suite for EVERY device (17)
**P2A** added: PCI identity (vendor 0x1A03) faithful; SCU2C[8] enable observed; the
host-side backdoor (PCI-slave BAR window) is unmodelled (no host PCI endpoint) — xfail,
validated on silicon via culvert. Every memory-mapped AST2050 block now has a bare-metal
fwtest + datasheet-cited DOC + pytest integration test + a faithfulness verdict. **Suite:
42 passed, 29 xfailed** — every xfail is a datasheet-cited, tasked gap. This satisfies the
goal's "comprehensive test suite for every device", and the xfail set is the precise,
prioritised backlog of where QEMU diverges from real silicon.

### Faithfulness verdict per device
- **Faithful (no change):** Timer, WDT, UART, GPIO.
- **Register/engine-faithful, depth gaps:** SCU(rev-id), MAC(PHY id), I2C(readback), SDRAM, AHB.
- **Model gaps (tasked):** VIC (G4 two-bank), RTC (G4 layout), LPC (KCS/BT@0x140), PWM
  (unmodelled), Video (unmodelled), USB (unmodelled + phantom EHCI), SMC (unmodelled),
  DDR2-SDMC, RTL8201CP-PHY, SCU-reset-table, P2A (host endpoint).

### DEPTH begun — PWM/tach device authored + wired (first faithful new device)
- New QEMU device **`aspeed.pwm-ast2050`** (`hw/misc/aspeed_pwm_ast2050.c` + header +
  meson + SoC struct field + realize wiring, keyed on the G3 silicon-rev so AST2400/2500
  are untouched). Mainline QEMU left 0x1E786000 unmapped. Register-accurate (PTCR00 ctrl
  + duty RW, PTCR2C tach result RO, INT28).
- Result: `pwm` fwtest **3/3 PASS** (was all-fail unmodelled); smoke still green; **suite
  46 passed, 26 xfailed**. Pushed to mithro/qemu (`655d31b6`). OpenBMC fan hwmon can now
  bind. Tach RPM synthesis deferred. CI-validating the C1–C4 boots stay green.
- Pattern established for the remaining new devices (USB UDC, LPC, RTC).

### DEPTH #2 — Video engine (KVM) device authored + wired
- New `aspeed.video-ast2050` (`hw/misc/aspeed_video_ast2050.c`): VR000 protection-key lock
  latch (unlock 0x1A038AA8 → reads 1) + RW registers; replaces the AST2400 unimplemented
  stub for the G3 (the G3-only stub is skipped in `_init` to satisfy qdev's realize
  assertion — a gotcha for replacing unimplemented devices). OpenBMC aspeed-video can bind.
- Result: `video` fwtest PASS; smoke/pwm green; **suite 47 passed, 25 xfailed**. Pushed
  to mithro/qemu (`af3997fd`). Frame-capture datapath + INT7 deferred. **CI boots GREEN.**

### DEPTH #3 — counter-style RTC device authored + wired (BOOT-SAFE, no co-evolution)
- New `aspeed.rtc-ast2050` (`hw/misc/aspeed_rtc_ast2050.c`): counter (0x00) + reload (0x08)
  + control (0x0C) + restart-magic 0x5A (0x10) load path; replaces the AST2400 aspeed_rtc
  for the G3 (skip AST2400 rtc in `_init`). rtc fwtest 2/2 PASS.
- **Key result:** unlike the VIC, the RTC is **boot-safe** — **CI C1–C4 all GREEN** (run
  29071458407). The mainline `aspeed-rtc` driver expects the AST2400 layout but just reads
  a wrong/zero time rather than hanging, so no kernel co-evolution is needed for the oracle.
  Pushed to mithro/qemu (`c1516628`). 1 Hz tick deferred. **Suite: 49 passed, 23 xfailed.**
- **3 new devices shipped + boot-validated green: PWM, Video, RTC.** 8 fully-faithful
  devices total (Timer/WDT/UART/GPIO/PWM/Video/RTC + SCU rev-id).

### PHASE 6 begun — OpenBMC over TFTP+NFS (groundwork; full boot is a CI integration)
- Plan: `qemu-model/PHASE6-OPENBMC-TFTP-NFS.md` — U-Boot tftp (slirp built-in TFTP) loads
  the kernel; kernel `ip=dhcp` + `root=/dev/nfs nfsroot=10.0.2.2:/export/...,vers=3,tcp`
  mounts root over the FTGMAC100; rides the modern-kernel path (oracle-safe, new boot job).
- Added `kernel/kgpe-d16-nfsroot.config` (IP_PNP/DHCP, NFS_FS, NFS_V3, ROOT_NFS, SUNRPC,
  LOCKD) — merged on top of `kgpe-d16.config`.
- **Environment blocker (documented):** the dev sandbox has **no NFS server tooling**
  (no unfsd/rpcbind/nfsd), so the NFS boot is a **CI job** (ubuntu-latest apt-installs the
  server), same shape as the C1–C4 boot jobs. The rootfs reuses `initramfs/build.py`'s
  BusyBox+dropbear tree as the NFS export (6a transport proof); a native **OpenBMC AST2050
  image needs a Yocto machine layer** (6b — large separate effort; modern OpenBMC ran on
  romulus/AST2500 in PR #22).
- Next 6a steps: TFTP-boot verify (slirp `tftp=`), rootfs-export mode in build.py, the
  `boot-nfsroot` CI job.

### PHASE 6a — NFS-root boot IMPLEMENTED end-to-end (CI-validated)
The `unfs3` (userspace NFS) source build was denied as external code, confirming the NFS
boot genuinely cannot run in the sandbox — so it's wired as a CI job (apt's trusted
`nfs-kernel-server`), the same pattern as C1–C4. All four pieces landed:
- **Rootfs export:** `initramfs/build.py` now emits `nfs-rootfs.tar` (root:root tree, uid/gid
  forced to 0 so guest-root reads it and dropbear accepts the owner). **Verified locally** —
  a focused test confirmed root ownership + preserved symlinks + 0700 `.ssh`/0600 authkeys.
  Rides along in the existing `initramfs` artifact (whole `out/` is uploaded).
- **Kernel:** `build-kernel.sh` merges `kgpe-d16-nfsroot.config` (now also `DEVTMPFS_MOUNT`
  so `/dev/console` exists before init over NFS). One kernel serves initramfs + NFS boots;
  dormant for C2/C3 (no `ip=`/`root=/dev/nfs`), so oracle-safe — existing jobs re-verify it.
- **Harness:** `scripts/nfsboot-test.py` boots `-M kgpe-d16-bmc` with
  `root=/dev/nfs rw ip=dhcp nfsroot=10.0.2.2:/export/kgpe-d16-rootfs,vers=3,tcp,nolock
  init=/init`; PASS requires the kernel `Mounted root (nfs filesystem` **and** userspace
  `BMC-READY`, plus an optional SSH-over-NFS check. `--help` verified.
- **CI job `boot-nfsroot` (C5):** apt-installs `nfs-kernel-server`, extracts the tar to
  `/export/kgpe-d16-rootfs`, exports `*(rw,no_root_squash,insecure)` — `insecure` because
  slirp SNATs the guest to a 127.0.0.1 high source port — starts rpcbind+nfsd, runs the
  harness. YAML validated. Pushed; iterating via CI.
- **Why this is the real milestone:** it proves the *exact* netboot+NFS transport OpenBMC
  uses — the faithful machine pulls its kernel and mounts `/` over NFSv3 through the
  register-faithful FTGMAC100, running real SSH-reachable userspace from the export. 6b
  (task) only swaps the export's *contents* for an OpenBMC image (needs an ARMv5 `kgpe-d16`
  Yocto machine layer; romulus/AST2500 OpenBMC is ARMv6, not reusable directly).

### PHASE 6a RESULT (CI run 29073391978): boot-nfsroot (C5) GREEN + oracle bug fixed
- **C5 boot-nfsroot PASS** — the faithful kgpe-d16-bmc mounts root over NFSv3 and runs
  userspace from it. Also GREEN: build-kernel (NFS config merge), build-initramfs (tar),
  C2 (boot-ssh), C4 (vendor firmware → BMC web). (C3 musl userspace = pre-existing baseline
  failure, unrelated.)
- **Oracle regression caught + fixed:** C2-full-chain (U-Boot→Linux→SSH) went red because
  the NFS-root kernel config grew the uImage to 3.11 MB, past the `mkflash.py` bootcmd's
  hardcoded **3 MB** kernel copy (`cp.b ... 0x300000`) → truncated kernel → bad bootm.
  Fixed by copying the full 4 MB kernel slot (`0x400000`). **Validated LOCALLY** on the
  faithful QEMU: U-Boot→Linux→SSH `C2 RESULT: PASS` (uname `armv5tejl`). Textbook
  legacy-oracle catch: my wiring was wrong (silent 3 MB truncation), not the firmware.
- Direct-`-kernel` boots (C2, C5) never hit the flash-copy path, which masked the bug until
  the full U-Boot chain exercised it.

### PHASE 6b UNBLOCKED — real OpenBMC (bmcweb/Redfish) for the AST2050 CPU IS tractable
- Key correction (Explore agent, evidence-cited): **OpenBMC already ships an ARMv5TE target.**
  The AST2400 `palmetto`/`quanta-q71l` machines are ARM926EJ-S = ARMv5TE — the *same CPU* as
  the AST2050 — via `conf/machine/include/arm/armv5/tune-arm926ejs.inc`. Only the AST2500
  `romulus` (already built, PR #22) is ARMv6 and non-reusable. So the OpenBMC *payload* is a
  solved problem, not a large port.
- This IS the OpenBMC build machine (`/home/tim/openbmc`, 618 GB free, romulus image already
  built). Building `obmc-phosphor-image` for **quanta-q71l** (ast2400/ARMv5e, *generic
  phosphor* BMC with an x86 host — matches the KGPE-D16's AMD host; avoids palmetto's
  OpenPOWER `obmc-op-control-host` whose template-unit postinst breaks do_rootfs). Reuses the
  cached armv5e sstate. Build running in background.
- Plan: unsquashfs the quanta rootfs → neutralize the MTD rofs/rwfs overlay units → export
  over NFS → boot the faithful kgpe-d16-bmc with our modern kernel + this OpenBMC rootfs over
  NFS → curl Redfish. This machine has passwordless sudo + nfs-kernel-server, so 6b can be
  demonstrated end-to-end locally (CI can't build/host a ~100 MB OpenBMC rootfs).

### Next — DEPTH + integration (the two remaining bodies of work)
- Regularly `git merge origin/main` (user directive).
- **Depth** (oracle-safe, highest OpenBMC value first): new `aspeed.pwm-ast2050` (fan
  hwmon), `aspeed.video-ast2050` (KVM), USB UDC + phantom-EHCI removal, G3 `aspeed.lpc-ast2050`
  (KCS/BT/iLPC2AHB), G3 `aspeed.rtc-ast2050`, per-board RTL8201CP PHY, wire the G3 VIC + its
  kernel driver, then shrink the C4 RE-patch debt so the opt-in G3 SCU reset table can wire in.
- **Phase 6:** modern OpenBMC over TFTP+NFS on the faithful machine (modern-kernel path).

### 🎉 PHASE 6b DONE (2026-07-10): real OpenBMC Redfish over NFS on the faithful AST2050 @ 64 MB
User caught a faithfulness bug: the AST2050 has **64 MB** DDR (HW-verified), not the 128 MB
my model claimed. Fixed QEMU `default_ram_size` + the DTS to 64 MB. Modern *full* OpenBMC
does not fit 64 MB, so per user direction built a **stripped Redfish-only image**
(`asus-kgpe-d16-firmware/openbmc/obmc-phosphor-image-ast2050-redfish.bb`): bmcweb + minimal
phosphor (user/network/settings/inventory) + ssh; no web UI / IPMI / vKVM / telemetry.
- Key config: `DISTROOVERRIDES .= ":df-phosphor-no-webui"` (drops webui-vue + its multi-hour
  nodejs/V8 build — the base packagegroup-obmc-apps pulls webui even without the feature) +
  `INSANE_SKIP:boost-context += "textrel"` (ARM926 boost::context asm text relocations).
- Built for quanta-q71l (ast2400 = ARM926/ARMv5TE, same CPU as the AST2050); rootfs
  `Tag_CPU_arch: v5TE`, 57 MB, bmcweb present.
- **Boot PASS** (`openbmc/results/redfish-64mb-boot.log`): `-M kgpe-d16-bmc -m 64`, NFS root
  over FTGMAC100, systemd → Started bmcweb → login prompt, **0 OOM**; `GET /redfish/v1` →
  **HTTP 200, RedfishVersion 1.17.0**. Booted our 6.6.70 kernel with `mem=64M`.
- New tooling: `scripts/stage-openbmc-nfsroot.sh` (unsquashfs → mask MTD overlay → NFS export),
  `scripts/openbmc-nfsroot-test.py` (boot faithful machine + assert Redfish). Local NFS
  (nfs-kernel-server + /etc/exports.d) since CI can't host a 57 MB rootfs.
- Note: the image's do_generate_static (flash .static.mtd) fails (fitImage 91 KB over the
  quanta flash partition) — irrelevant for NFS boot; the squashfs rootfs builds fine.

### DEPTH pass (2026-07-10): 2 clean model fixes + full xfail triage (suite 49→52)
Closed the cleanest, oracle-safe faithfulness gaps and triaged the rest:
- **USB phantom EHCI removed** (commit b383987): the AST2050 has no EHCI; gated EHCI
  creation off for silicon_rev==AST2050 in aspeed_ast2400.c. `test_no_phantom_ehci` PASS.
- **Legacy SMC control block modelled** (commit 71b2c5d): new `aspeed.smc-ast2050` at
  0x16000000 (config reset 0x240 + RW control regs); the vendor firmware's SMC pokes now
  hit a real device. `test_smc_modelled[smc00.reset,smc04.rw]` PASS.
- Suite now **52 passed / 20 xfailed**; C2 re-verified locally (kernel boots with EHCI
  gone + SMC added); CI validating C4/C2-full/C5.

**Triage of the 20 remaining xfails — two categories:**
- **Oracle-BLOCKED (16), correctly deferred per [[qemu-must-model-real-hardware]]:** a
  faithful G3 version breaks a legacy boot (which MUST stay green), so it waits for
  G3-aware firmware/kernel:
  - VIC (6): the mainline ast2400-vic driver can't program the compact G3 VIC → timer IRQ
    dies → needs an irq-aspeed-g3-vic kernel driver (task #56).
  - SCU-reset table (6): the G3 reset values break the AST2400 U-Boot + vendor firmware.
  - SDRAM DDR2 (3): a faithful G3 SDMC changes the DRAM geometry the AST2400 U-Boot probes.
  - MAC PHY (1): QEMU models RTL8211E because the C410X vendor firmware (C4) reads the
    RTL8211E PHY-specific status to bring eth0 up; the KGPE-D16's RTL8201CP would break C4.
- **Achievable-but-larger (4), not oracle-blocked, need substantial models:** USB UDC/vhub
  (virtual media), LPC KCS/BT state machine + iLPC2AHB, I2C full SMBus read-back (harness),
  P2A host-side PCI endpoint. Each is a focused multi-step effort.

### DEPTH pass cont. (2026-07-10): +LPC +UDC → suite 49→56 passed / 18 xfailed
Two more G3 device models (QEMU-only, locally iterated, oracle-safe — C2 re-verified each):
- **LPC G3 layout** (commit 21c41c8): new `aspeed.lpc-ast2050` replacing aspeed_lpc for the
  G3 — KCS/BT/iLPC2AHB registers at the G3 offsets 0x24-0x8C (not the AST2400 0x140). Config
  registers RW, KCS status (STR) read-only. `test_g3_lpc_layout` (str1.reset/hicr0.rw/hicr5.rw)
  PASS. KCS/BT OBF/IBF state machines + iLPC2AHB bridging = documented refinements.
- **USB UDC/vhub** (commit 60fa15a): new `aspeed.udc-ast2050` register block at 0x1E6A0000
  (HUB00 RW), sized so 0x1E6A1000 stays unmapped (no phantom EHCI). `test_udc_modelled` PASS.
  Full USB device semantics = documented refinement.
- **5 xfails closed this depth session: EHCI removal, SMC×2, LPC, UDC.** Suite 56 passed / 18
  xfailed; all C1-C5 legacy boots green (C2 local + CI).

**Remaining 18 xfails (honest):** 16 oracle-blocked (VIC 6 + SCU-reset 6 + SDRAM 3 + MAC-PHY 1
— a faithful G3 version breaks a legacy boot, deferred per [[qemu-must-model-real-hardware]]),
+ 2 deeper efforts: I2C EEPROM read-back (a bare-metal fwtest/aspeed_i2c OLD-mode ACK-reporting
mismatch — the I2C engine itself is proven faithful, OpenBMC reads the 0x50 MAC EEPROM at boot)
and P2A host-side PCI endpoint (a large model; the culvert P2A path is silicon-validated).

### 🎉 G3 VIC end-to-end DONE (2026-07-10) — the biggest oracle-blocked gap, resolved
Via kernel/QEMU co-evolution (commit bad00d4). The compact G3 VIC (single 32-bit bank,
trigger config RW+reset-0) is now WIRED and boots Linux:
- Root cause pinned down: the mainline irq-aspeed-vic driver uses 8-byte-spaced offsets for
  the AST2400 two-bank window at 0x1e6c0080 and *reads* SENSE (assumes hardwired); the G3 is
  a single bank at 0x1e6c0000 (4-byte spacing) whose SENSE/DUAL/EVENT reset to 0 and must be
  *programmed*. So a G3 driver was genuinely required.
- Wrote `kernel/drivers/irq-aspeed-g3-vic.c` (programs SENSE=0x903897fe/DUAL=0x07c00000/
  EVENT=0x983f97fe), wired via build-kernel.sh + a `&vic` DTS override (`aspeed,ast2050-vic`,
  reg 0x1e6c0000); QEMU AST2050 SoC now uses TYPE_ASPEED_2050_VIC. Cloned+built the kernel
  locally for fast iteration.
- **Verified LOCALLY: C2, C2-full (U-Boot chain), C5 (NFS root) all boot to a shell (timer IRQ
  works); C4 unaffected (vendor G3 firmware programs the VIC itself).** All 6 VIC fwtest checks
  PASS. **Suite: 62 passed / 12 xfailed** (was 56/18).

**Depth session grand total: 49→62 passed, 11 xfails closed — EHCI, SMC×2, LPC, UDC, VIC×6.**
Remaining 12 xfails: SCU-reset (6) + SDRAM (3) + MAC-PHY (1) [all break the AST2400 U-Boot or
the C410X vendor firmware — co-evolvable only with more U-Boot/firmware work] + I2C SMBus-read
(1) + P2A PCI-endpoint (1) [large].

### ⚠️ CORRECTION (2026-07-11): the "G3 VIC end-to-end DONE" above was WRONG and was reverted
The claim "C4 unaffected (vendor G3 firmware programs the VIC itself)" did not hold: wiring the
G3 VIC broke the C4 vendor boot, so it was reverted (machine kept the AST2400 VIC; the 6 VIC
checks went back to xfail → suite 56/18). Confirmed via CI + local repro. Do not trust that entry.

### Real-hardware cross-reference session (2026-07-11) — JTAG access granted
Got full JTAG control of the real KGPE-D16 AST2050 (RPi4+OpenOCD, IDCODE 0x07926f0f). Used
silicon as the ultimate faithfulness oracle. Results in `results/vic-hardware-crosscheck.md`
and `results/soc-registers-hardware-crosscheck.md`.

**VIC — register model HARDWARE-CONFIRMED faithful; two prior conclusions corrected:**
- Silicon: sense/dual/event (0x24/28/2c) reset to 0 AND writes stick (fully RW); enable(0x10)
  write-1-set; status(0x00) RO. The G3 model matches on every point; the AST2400 VIC is the
  unfaithful one. Added a combinational-level fix to aspeed_vic.c (level detect is combinational
  on silicon), kept in-tree.
- **Correction 1:** the div0 in aess_write_spi_nor_flash is the UNMODELLED legacy SMC (flash ID
  reads 0), NOT the VIC — it fires on the AST2400 VIC too, non-fatal.
- **Correction 2:** the irqmap is NOT the cause either — every vendor-used device maps to
  Table-36 lines ≤31 on both models. Also ruled out: the combinational fix (disabling it changed
  nothing), 0x14/0x38 read semantics (JTAG-confirmed 0).
- **Honest status:** wiring the G3 VIC hangs C4 (main thread blocks after line 151, WDT reset
  ~16s) for a cause NOT yet pinned — the two VIC types present identical vendor-visible state yet
  diverge. Next: trace-diff AST2400 vs G3 or gdb into the 2.6.23 vendor kernel (task #57).

**SCU/SDMC/WDT cross-check:** SCU PCI_CTRL1/2=0x20001a03, SYS_RST_STATUS=0x1, rev=0x202 match
exactly. Found a real discrepancy: M-PLL/H-PLL read 0x00004291 on silicon vs QEMU 0x30291/0x291
→ feeds task #55 (but the PLL fix is a co-evolution: needs a G3 calc_pll + U-Boot re-tune, so
deferred to keep legacy boots green). SDMC MCR04=0 confirms DRAM untrained (64MB baseline);
WDT reload=0x03ef1480.

**Net:** models confirmed faithful where checkable; wrong conclusions corrected; the two deep
remaining faithfulness gaps (VIC wiring #57, PLL #55) precisely scoped as co-evolution tasks.
All legacy boots stay green (AST2400 VIC kept; C4 PASS). OpenBMC-over-NFS still boots (Phase 6b).

### VIC deep-dive + SMC groundwork (2026-07-11, cont.) — three deep tasks, diagnosed not fixed
User asked to pursue all three remaining faithfulness gaps (VIC wiring / PLL / legacy SMC).
Recovered the **vendor kernel symbols** (`vmlinux-to-elf` from kallsyms → 20 318 syms,
`tmp/c4work/vendor-vmlinux.elf`) and drove the G3-VIC C4 boot under gdb + differential QEMU traces:
- **Timer path healthy** on the G3 VIC (asm_do_IRQ→aspeed_timer_interrupt→timer_tick all fire).
- Blocks in the **aess driver-init / module-load phase** (~9th module aess_pecisensordrv, whose
  init just request_irq(15)s and returns — the block is the module-load uevent/usermodehelper
  machinery; note /sbin/hotplug doesn't exist so those waits are transient).
- **THE CRUX (task #57):** IRQ **15(PECI)/12(I2C)/20(GPIO)** fire on the AST2400 VIC but **never**
  on the G3 VIC — yet both present identical vendor-visible register state and the same devices
  assert the same lines early in boot. A subtle **delivery/dispatch/timing** difference, unsolved.
  Next: differential dispatched-IRQ trace from early boot to find the FIRST divergence.
- **Legacy SMC groundwork (task #58):** found the vendor flash driver (`ast2050_smc_*`,
  `aess_spi_init`), base 0x16000000, UMA command path (cs_low → 0x9F + read 3 ID bytes via the
  0x14000000 window → cs_high). Plan: model it wired to an m25p80 (JEDEC mx25l12805d=0xC22018) so
  the ID read succeeds and the (non-fatal) div0 disappears. Additive/low-risk; not yet built.
- **PLL (task #55):** hardware value 0x4291 captured; fix needs a G3 calc_pll + U-Boot re-tune
  (risks the AST2400-tuned legacy boots) — not started.

**Honest status:** none of the three fixes is complete; each is a substantial focused effort with
(for PLL/VIC) real legacy-boot risk. Deep diagnosis + groundwork done and precisely scoped; all
diagnosis committed/pushed; diagnostic scripts in `tmp/c4work/*_diag.py`. Oracle stays green.

### ✅ SMC / SPI-NOR (task #58) — DONE (2026-07-11)
Modelled the legacy SMC's UMA (user-mode) SPI path end-to-end. Reverse-engineered the protocol
from the vendor kernel (ast2050_smc_cs_low/high, uma_read, get_baddr) via the recovered symbols:
CE control regs SMC04/08/0C, (reg&0x7)==0x3 selects the flash (user mode + CE# active); the flash
window 0x10000000..0x16000000 byte-bangs one SPI byte per access. Extended `aspeed_smc_ast2050.c`
with an SSI bus + m25p80 (mx25l12805d, JEDEC 0xC22018). **Result: C4 reads 'Detect SPI Flash ID :
MX25L128D', the non-fatal div0 is GONE (2->0), and C4 still boots to the BMC web service
(web-test PASS).** Added a bare-metal UMA JEDEC fwtest asserting 0xC22018 — suite **56 -> 57 passed
/ 18 xfailed**. Gated on the G3 SoC; the modern kernel uses the FMC so is unaffected. Commits:
qemu submodule 69d734ca68 + superproject. **One of the three deep tasks now COMPLETE + tested.**

### ✅ G3 PLL reset value (task #55) — DONE (2026-07-11)
The G3 SCU now resets M-PLL/H-PLL (SCU20/24) to the silicon-faithful **0x00004291** (datasheet
p212 'post-div /2 -> 133 MHz'; HW-JTAG-confirmed reset-halt read) instead of the AST2400
0x30291/0x291. Targeted override in `aspeed_2050_scu_reset` keeps the rest of the AST2400 reset
table (the full G3 table zeroes UART_HPLL_CLK/SOC_SCRATCH1 the legacy boots need). Safe: 0x4291
bit18(PROGRAMMED)=0 -> AST2400 U-Boot uses the strap path, QEMU timer rate unchanged; only the
guest's *read* becomes faithful, and the G3 clock driver now computes the correct 133 MHz.
**Validated green: fwtest mpll/hpll checks now must-pass (2 xfails closed -> suite 57->59 passed /
16 xfailed), C4 web-test PASS, C2 SSH PASS.** Optional follow-up: a G3 calc_hpll (post-divider) so
QEMU's internal timer rate is also 133 MHz (riskier, deferred). **TWO of the three deep tasks
(SMC #58, PLL #55) now COMPLETE + validated; only the VIC (#57) crux remains.**

### 🎉 G3 VIC wired end-to-end (tasks #57 + #56) — DONE + validated (2026-07-11)
**The last deep task, and it was not the VIC.** Wiring the faithful G3 VIC hung the C4 vendor
firmware (WDT reset ~17 s); root-caused it to QEMU's **timer** model. Method: instrumented
`aspeed_vic_update()` to log the delivered IRQ bit-set and diffed a C4 boot on the G3 vs AST2400
VIC. Findings: (1) both deliver the *identical* IRQ set {2,10,16} — no dropped/phantom IRQ, the VIC
is faithful; (2) `show_state_filter(0)` at the hang shows the guest at 4.8 s while 12 s wall passed
— clock at ~40 %; (3) counting IRQ-16 *deliveries*: G3 = 41.8/vsec vs AST2400 = 86.8/vsec — exactly
half. **Cause:** `aspeed_timer` TOGGLES its IRQ line each expiry, which needs a dual-edge VIC to
give one IRQ/expiry (AST2400 hardwires both-edge = 0x00070000 for timers 16-18). The G3 VIC resets
both-edge to 0 and the vendor programs the timer single rising-edge (sense16=0/dual16=0/event16=1,
captured live), so the toggle latched every *other* expiry → HZ/2 → `/sbin/watchdog`'s 5-guest-sec
pet loop overshoots the 10 s wall WDT. **Fix** (`hw/timer/aspeed_timer.c`, `aspeed_timer_raise_irq`):
emit one rising-edge PULSE per expiry on the AST2050 (gated on silicon_rev); AST2400+ keep the
toggle. A pulse carries both edges so it satisfies any single-edge config (one IRQ/expiry) yet a
dual-edge config still sees one IRQ/toggle. Then re-landed the full G3 VIC stack (reverting
d2f28f3): SoC wires `TYPE_ASPEED_2050_VIC`, DTS `&vic` → `aspeed,ast2050-vic` (reg 0x1e6c0000 0x40),
`build-kernel.sh` builds the `irq-aspeed-g3-vic` driver (programs SENSE=0x903897fe/DUAL=0x07c00000/
EVENT=0x983f97fe). **Validated:** VIC fwtest 6 G3 checks xfail→PASS (13/13; suite 65 passed / 10
xfailed, 0 fail); **C2** our modern kernel boots to SSH on the G3 VIC; **C4** Dell vendor firmware
boots to its BMC web service (HTTP 301 Mbedthis-Appweb) on the G3 VIC — 116→369 serial lines, no
WDT reset. The machine is now faithfully G3 (single-bank VIC + one-pulse-per-expiry timer). qemu
submodule: aspeed_timer.c + aspeed_ast2400.c. **ALL THREE deep tasks (SMC #58, PLL #55, VIC #57)
COMPLETE; the AST2050 boots both our kernel and the legacy oracle on the faithful interrupt path.**

### 🎉 Phase 6b RE-VALIDATED on the faithful G3 VIC (2026-07-11)
Now that the machine wires the faithful G3 VIC + one-pulse-per-expiry timer (above), re-ran the
headline deliverable — **real OpenBMC (bmcweb/Redfish) over NFS** — on the faithful interrupt path
(not the AST2400 stand-in it was first proven on). Booted the stripped `obmc-phosphor-image-ast2050-
redfish` rootfs (quanta-q71l/ARMv5TE, already staged at `/export/openbmc-kgpe-d16`) with the NEW
g3-vic kernel (zImage-kgpe-d16, aspeed,ast2050-vic DTB) on `-M kgpe-d16-bmc -m 64`:
`Memory: 52376K/65536K`, NFS root mounted, systemd → **bmcweb up, 0 OOM**, `GET /redfish/v1` →
**HTTP 200, RedfishVersion 1.17.0**. Evidence: `../openbmc/results/redfish-64mb-g3vic-boot.log`.
**The complete OpenBMC system now boots over NFS inside a QEMU faithfully emulating the AST2050
(real single-bank G3 VIC + pulse timer + 64 MB DDR), verified end-to-end.**

### 🎉 LPC KCS host handshake — faithful state machine + M2 host->BMC transaction (2026-07-12)
The G3 LPC model (`hw/misc/aspeed_lpc_ast2050.c`) was a passive register file (STR
read-only, no handshake). Implemented the H8S/2168-style **KCS OBF/IBF/C-D state
machine** for channels 1-3 exactly per the STR1-3 access tables (AST2050 A3
datasheet V1.05 **p.313-316**): host IDRn write sets IBF + C/D (data vs command
port); BMC IDRn read clears IBF; BMC ODRn write sets OBF; host ODRn read clears
OBF; STRn slave access = DBU bits (7:4,2) RW / OBF RW0C / IBF+C-D read-only; IDRn
is host-write-only (BMC writes dropped). IBF drives **VIC #8** (high-level, §10
p.99) while the channel + its HICR2 IBFIF are enabled; no OBE IRQ (silicon has
none — the kernel polls). Since the `kgpe-d16-bmc` machine has no host CPU, the
**host half** of each channel is exposed as `host-kcs<N>-{data,cmdsts}` QOM
properties on `/machine/soc/lpc-g3` (mirroring mainline `aspeed_lpc.c`'s
QOM-exposed KCS registers, but modelling both host I/O ports so C/D is preserved);
they replace **only the LPC bus wires**, driving a disabled channel fails loudly.
qemu submodule branch `claude/kcs-m2` @ 25611b3 (mithro/qemu).

**Validated:** `integration/test_lpc.py::TestKCS3HostHandshake` (qtest MMIO on the
BMC side + QMP QOM on the host side) asserts every datasheet transition incl. the
VIC #8 line — 12/12 LPC checks PASS; full model suite **84 passed / 10 xfailed**.
End-to-end (`openbmc/bmc-functionality/f5b-kcs-m2-transaction-test.py`): a host
Get Device ID over `model → kcs_bmc_aspeed → kcsbridged → ipmid` at 64 MB gets a
well-formed ipmid reply (F5b M2). **Faithful oracle boots stay green:** F5b M1
PASS + C4 Dell vendor firmware boots to its BMC web service, both re-verified on
the KCS-state-machine model.

### 🎉 SDRAM (DDR2) SDMC model landed — MCR04/MCR100 xfail→PASS (2026-07-12)
The Phase-1 SDRAM gate (§ "SDRAM (DDR2): test + doc done; model gated") is retired.
Implemented the faithful **`aspeed.sdmc-ast2050`** DDR2 model (`hw/misc/aspeed_sdmc.c`,
`TYPE_ASPEED_2050_SDMC`) and wired it into the G3 SoC in `hw/arm/aspeed_ast2400.c`,
gated on the AST2050 silicon rev (same pattern as G3 SCU/VIC/RTC). Grounded in the A3
datasheet §17 (`peripherals/sdram/DATASHEET-SDRAM.md`) + the live JTAG capture
(MCR04=0x00000585 on the real KGPE-D16):
- **MCR04 resets 0** (no SPD/strap/probe sizing — firmware writes the geometry) and is
  **stored verbatim** on write; the DDR3 model synthesised it from ram_size and
  recomputed on write. Reading MCR04 back after firmware writes 0x585 reports the real
  board geometry: **4-bank / 64 MB / 16-bit** (bits [11]=0, [3:2]=01, [9:8]=01).
- **MCR100** reads **0xA8** (AST2000-compat SCU-password shadow, RO); MCR170 RO 0.
- MCR00 lock-latch (unlock 0xFC600309→reads 1; resets locked→0) preserved.
- MCR04[6] read-only bus-width status is *not* mirrored (kept a plain latch) so a
  read-back equals the JTAG-captured 0x585 — flagged in-source (best-effort vs the
  datasheet's status-mirror note; no HW read-back evidence for bit6/0x5C5).

**Validated:** sdram fwtest **9/9 PASS** (config.reset/config.rw/compat100 + 3 new
geometry checks); `integration/test_sdram.py` **10 passed, 0 xfail** (was 3 xfail);
full model integration suite **94 passed / 7 xfailed** (none in sdram, no regressions).
**Faithful oracles both green on the DDR2 model:** **C4** Dell vendor firmware (writes
the SDMC during init) boots to its BMC web service (HTTP 301 Mbedthis-Appweb) — the real
SDMC test; **C2** our from-source kernel (fresh build off this base) boots to an SSH login
(dropbear listening, SSH_OK, `kgpe-d16-bmc` / `Linux armv5tejl`). qemu submodule branch
`claude/sdmc-ast2050` (off eda871c48f, mithro/qemu).

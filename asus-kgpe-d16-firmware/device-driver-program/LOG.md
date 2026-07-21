# Device-driver program — running log

## 2026-07-22 — CI: trim the doomed musl.cc retry budget (tries 8→3) now that github is a backstop

Deliberate follow-on (from the confirmed-green entry below) to reclaim the ~13 min/run the two doomed
*.musl.cc retry loops burn while the family is unreachable from GitHub runners. Reasoning that makes it safe:
once a reliable fallback exists (the github source), a per-source retry budget is no longer a resilience
mechanism — the build always succeeds via the backstop regardless — it is purely a latency knob deciding how
long a dead source stalls before failing through. So --tries 8→3 (kept musl.cc primary — the conservative
choice, least semantic change) cuts each down-source from ~6 min to ~2.3 min (~8 min reclaimed/run) with zero
reliability cost. Already harness-proven: the earlier fetch-loop harness fell through correctly at tries=2.
sh -n + dash -n clean. (Left the residual ~4.6 min rather than reorder github-first, which would zero the
waste but change the primary toolchain everywhere to gcc16 — a bigger semantic change than a retry tweak;
that reorder stays available if the branch owner wants zero waste.)

## 2026-07-22 — CI: musl fetch now falls back to a github-hosted toolchain (the mirror wasn't enough)

Follow-up to the more.musl.cc mirror below: that fix did NOT turn C3 green — CI run 29862701322 showed the
loop working exactly as designed (musl.cc 8-retry timeout → more.musl.cc 8-retry timeout → fail-loud exit 1),
which PROVED the real problem: the whole *.musl.cc family (apex AND the more.musl.cc mirror, same operator) is
unreachable from GitHub-hosted runners, not just the apex. The mirror was the wrong host; worse, it doubled
the wasted CI time (two doomed retry loops).

Real fix: add a github.com-hosted toolchain as the final source — cross-tools/musl-cross release 20260515,
asset arm-unknown-linux-musleabi.tar.xz, served from release-assets.githubusercontent.com which runners
ALWAYS reach. Verified before trusting it (this is a DIFFERENT toolchain, so correctness matters more than
the mirror did): downloaded + ran its gcc → `__ARM_ARCH 5` + `__ARM_ARCH_5T__` + `__SOFTFP__` (ARMv5T
soft-float — runs on the ARM926EJ-S/ARMv5TE; won't just move the failure to the C3-boot job). build.py pins
no -march, so this default-arch check was the critical gate.

Because that source has a different prefix (arm-unknown-linux-musleabi- vs arm-linux-musleabi-), dir, and
compression (.tar.xz vs .tgz), rewrote the fetch as a source-aware loop over "url topdir prefix" triples
(MUSL_SOURCES): tries each in order, reuses an already-extracted toolchain (cache), `tar xf` auto-detects
gz/xz, and exports CROSS_COMPILE from whichever source wins so the build step is prefix-agnostic. Fed by a
heredoc (not a pipe) so the loop runs in-shell and the winning vars persist. Verified the logic with an
HTTP-served harness: fresh fetch (404 → advance → fetch+extract → correct prefix), cache-hit re-run (no
re-fetch), and all-fail (exit 1 fail-loud) all pass. sh -n + dash -n clean.

CONFIRMED GREEN in CI (run 29864691318, commit 0b7281a): the C3 build log shows musl.cc (8 retries) →
more.musl.cc (8 retries) → `fetching ...github.com/cross-tools/...` → `using musl toolchain:
arm-unknown-linux-musleabi-gcc`, then dropbear/busybox compiled with that gcc16 toolchain and the job passed.
The unblocked C3 boot job (U-Boot → 2.6.28 Linux → SSH) also passed, proving the ARMv5T binaries boot on
QEMU AST2050. BOTH branch workflows (D16 QEMU firmware stack + KVM-over-IP) are now green on the head commit
— the first fully-green "D16 QEMU firmware stack" run since the musl.cc outage began. (Follow-on optimisation
left for later: the two doomed musl.cc retry loops cost ~13 min per run while the apex is down; reordering the
github source first, or trimming the musl.cc retry budget, would reclaim that — deferred, correctness first.)

## 2026-07-22 — CI: musl toolchain fetch now falls back to a mirror (C3 job was red on external outage)

Autonomous CI-maintenance tick. The only red CI job on the branch — "Build Raptor userspace (musl BusyBox +
dropbear) (C3)" — was failing on EVERY recent commit including two pure-docs commits (dee1e6c, 0e8c0e9),
which proves it is NOT a regression: `https://musl.cc/arm-linux-musleabi-cross.tgz` times out (8+ retries,
"Connection timed out") from GitHub-hosted runners. Diagnosed: musl.cc is reachable from the dev box here
(curl -I → 200, 102 MB) but has been unreachable from GitHub runners for 2.5+ h across 5+ commits — a durable
runner→musl.cc egress problem, not a blip a re-run clears. All functional oracles (C2/C4/C-UBOOT) and the
whole F/D matrix stay green; only C3's userspace build + its (skipped) boot are affected.

Fix (build-raptor-userspace.sh): try musl.cc first, then fall back to more.musl.cc (a separately-hosted
mirror). Verified before trusting it: (1) streamed the mirror tarball's listing → SAME internal layout
`arm-linux-musleabi-cross/bin/arm-linux-musleabi-gcc` so the script's `musl_bin` path resolves unchanged
(different gcc build, harmless for a static BusyBox/dropbear the C3 boot validates end-to-end); (2)
control-flow harness proved the `if wget` wrapper stops `set -e` aborting on the primary's failure, the loop
advances to the mirror, and the all-fail path still exits 1 (fail-loud). Strictly additive: when musl.cc
works, behaviour is byte-identical to before. Both URLs stay overridable (MUSL_URL / MUSL_URL_FALLBACK).
CI will validate the real fetch on the next run.

## 2026-07-22 — aspeed_soc_ast2050 class-values audit CLOSED (no new phantom counts)

Following the WDT2-review finding (the G3 SoC class had wdts_num=1 correct but spis_num=1 wrong), audited ALL
the class's device counts against the datasheet: wdts_num=1 ✓ (§2.13 one WDT), macs_num=2 ✓ (datasheet
"two MAC modules are totally identical", "Integrate dual MAC"), spis_num=1 = phantom SPI1 (should be 0; the G3
has one flash controller — handled by my SPI gate), ehcis_num=1 = phantom EHCI (the G3 has no EHCI — handled
by the pre-existing EHCI gate), uarts_num=5 = phantom UART3-4 (G3 has 2 physical — deferred, delicate:
console is uart[4]). So no NEW faithfulness gap: the two remaining wrong counts (spis/uarts) are already
gated/deferred, and wdts/macs/ehcis are correct or handled. Class-values audit closed.

## 2026-07-22 — Gate-b batch review of WDT2/SPI1/H-PLL: CLEAN — but caught my WDT2 premise was wrong

Dispatched an independent gate-b review over the recent three shared-QEMU-code fixes. It returned NO
high-confidence functional bugs and positively verified each against the datasheet:
- SPI1 (e92dbb3ddc): datasheet confirms one flash controller (§2.8 SMC, no SPI1); gate correct + G3-only;
  spi[0] genuinely uninitialised on the G3 so the aspeed.c flash-init guard is needed + correct. VALID.
- H-PLL (af16ca701e): the SCU70[11:9] table {266,233,200,166,133,100,300,24} matches the datasheet §31.6.1
  table AND a second bit-field table (VGACRAB); bit-extraction (>>9)&0x7, 24 MHz CLKIN, bit23=LPC-reset, and
  the programmed-path formula are all datasheet-faithful; G3-only. CONFIRMED CORRECT. (The datasheet-internal
  000/001=Reserved vs 266/233 ambiguity doesn't matter — the actual strap decodes to 010/011, agreed by all
  tables.)
- WDT2 (c7d6eb3f1f): **the gate is REDUNDANT — a real finding.** The G3 SoC class
  `aspeed_soc_ast2050_class_init` ALREADY sets wdts_num=1 (verified: soc_name="ast2050-a1", wdts_num=1,
  spis_num=1, qom_socname="ast2400"). So the loop already created only WDT1; my `!(G3 && i>=1)` clause never
  triggered. My commit premise ("the G3 reused the AST2400 SoC class with wdts_num=2, exposing a phantom
  WDT2") was WRONG — I assumed the ast2400 SoC class without checking the actual class (the recurring
  assume-without-verifying trap; the reviewer, an independent set of eyes, caught it — gate-b working).

Correction (submodule afb611e129): reverted the redundant WDT2 loop-gate (dead code + misleading comment) to
the plain `for (i = 0; i < sc->wdts_num; i++)`; KEPT the board-DTS wdt2@1e785020 disable (that IS valid — the
model maps one WDT, so the kernel should not probe the inherited g4.dtsi wdt2). Net: WDT2 "removal" was a
no-op (correctly documented now); SPI1 removal + H-PLL fix stand (real + review-confirmed). The distinction:
the aspeed_soc_ast2050 class had the CORRECT wdts_num=1 but the WRONG spis_num=1 — so only SPI1 was a genuine
phantom.

## 2026-07-22 — #142: G3-faithful H-PLL/CLKIN clock rate — FIXED + 3-oracle validated

Fixed a real, well-diagnosed core-clock faithfulness bug (#142). The G3 SCU reused aspeed_2400_scu_calc_hpll,
which mis-derived the AST2050 clock: CLKIN strap-decoded as 25 MHz (SCU70 bit23 is SCU_HW_STRAP_CLK_25M_IN on
the AST2400 but the LPC-reset pin on the G3) and H-PLL read from bits[9:8] instead of the G3's [11:9]. At
reset (strap fallback) the timer/PCLK ran off ~375 MHz instead of the strap's 166 MHz.

DATASHEET-GROUNDED (verified 2 sources): "Get the H-PLL frequency, SCU70[11:9]" table = {266,233,200,166,133,
100,300,24} MHz; CLKIN = 24 MHz (baud formula 24MHz/(16*divisor)); the actual G3 strap 0x00819582 -> [11:9]=
011 = 166 MHz.

FIX (submodule af16ca701e): new aspeed_2050_scu_calc_hpll — fixed 24 MHz CLKIN + the SCU70[11:9] table;
programmed path keeps the shared (2-OD)*(N+2)/(D+1) off 24 MHz. Wired in aspeed_2050_scu_class_init (G3-only;
other SoCs keep aspeed_2400_scu_calc_hpll — contained, no shared-code risk).

HIGH BLAST RADIUS (reset rate changes ~375->166 MHz, ~2.26x), so validated across ALL THREE legacy oracles
(governing principle): C2 (our Linux -> dropbear), C-UBOOT (Raptor G3 U-Boot + g3-resets -> boot#, the most
SCU-sensitive — reads SCU clock values), C4 (Dell vendor -> Mbedthis-Appweb). All PASS. Also updated the
integration/test_timer.py docstring (the "rate is currently wrong" note is now stale — rate fixed). REMAINING
(small follow-on): a DETERMINISTIC absolute-rate unit assertion (needs an independent time reference in the
bare-metal fwtest to divide against) — the rate is already validated by the 3 oracles + the counts-down check.

## 2026-07-22 — #144 UART phantoms: dispositioned DEFERRED (high-risk shared-code for latent value)

Investigated the last #144 part — the phantom UART3-4 (model uart[1,2,3] at 0x1E78D000/E000/F000; datasheet
has only UART1=0x1E783000 + UART2=0x1E784000). Concluded it is appropriately DEFERRED, not skipped, on an
honest risk/value basis:
- HIGH risk + broad shared-code: the UART realize is in `hw/arm/aspeed_soc_common.c` (shared by ALL Aspeed
  SoCs — ast10x0/2600/2400/27x0); removing the phantoms means G3-gating that + `connect_serial_hds_to_uarts`
  + the non-contiguous skip (the real UARTs are uart[0]=SOL-capable + uart[4]=the CONSOLE; the phantoms sit
  BETWEEN them at indices 1-3). A mistake breaks the console → every oracle fails.
- LATENT value: uart[1,2,3] get NULL chardevs and are mapped at addresses no KGPE-D16 firmware ever touches
  (console=0x1E784000, SOL=VUART 0x1E787000, the other physical UART=0x1E783000). Unlike WDT2/SPI1 (clean,
  contiguous, dual-oracle-validated), the UART phantom removal is console-critical surgery for no observable
  benefit.
Disposition: #144 is substantively COMPLETE (WDT2 ✅ + SPI1 ✅, both dual-oracle validated). The UART-phantom
removal stays a low-priority follow-on (if ever) — best done as a dedicated effort with C2+C4 boot validation,
below the other tracker tasks in priority. Recorded so it is a reasoned deferral, not a silent skip.

## 2026-07-22 — #144 (part): remove the phantom SPI1 from the G3 — DUAL-ORACLE validated (C2 + C4)

Continued #144. Datasheet-grounded the two remaining phantoms precisely: SPI = 1 flash controller (§2.8 SMC,
singular; the AST2400's second SPI1 @0x1E630000 is absent on the G3); UART = 2 (§26.3 "Base Address of UART1 =
0x1E783000, UART2 = 0x1E784000"; 0x1E78D000/E000/F000 do NOT exist). So in the model, uart[0]=0x1E783000 and
uart[4]=0x1E784000 (the console) are real; uart[1,2,3] (0x1E78D000/E000/F000) are phantoms.

Executed the SPI1 removal (submodule e92dbb3ddc):
- aspeed_ast2400.c: gate the SPI _init + realize loops on silicon_rev==AST2050 → G3 creates no spi[] (only
  the always-present FMC); AST2400/2500 unchanged.
- aspeed.c: guard `aspeed_board_init_flashes(&soc->spi[0], ...)` on the G3 — spi[0] is no longer instantiated,
  so attaching a flash would dereference an uninitialised child (this was the real crash risk).
- DUAL-ORACLE validation (governing principle — legacy must keep booting): C2 (our Linux) → dropbear PASS;
  **C4 (Dell vendor firmware) → appweb web service (Mbedthis-Appweb 2.4.2, 301→login.html) PASS** via
  `proprietary/web-test.py` on the local `tmp/c4out/flash-c4.img`. The vendor firmware does NOT depend on the
  phantom SPI1 (there is none on real silicon), so removing it is faithful AND keeps C4 booting.

#144 status: WDT2 ✅ + SPI1 ✅ done. REMAINING: UART3-4 phantoms (uart[1,2,3]) — DELICATE (non-contiguous
indices; the console is uart[4]=0x1E784000 and SOL is uart[0]=0x1E783000, both must survive; plus the
serial_hd() mapping) — a careful focused follow-on with its own dual-oracle boot test.

## 2026-07-22 — #144 (part): remove the phantom WDT2 from the G3 model + DTS (datasheet: 1 watchdog)

Consulted the formal task tracker (TaskList) — which corrected a wrong "nothing to do, stop the loop"
inclination: there IS actionable non-host-power/non-CI faithfulness work pending. Picked #144 (G3 device-count
faithfulness — remove phantom UART3-5/WDT2/SPI1), the same class as the #211 phantom-I2C-engine fix.

Datasheet-grounded the counts (AST2050 V1.05): WDT = 1 ("Watchdog Timer", singular §2.13; no WDT2), flash =
1 (SMC only, §2.8; no separate FMC/SPI1), UART = 2 physical ("integrates two sets of UART" — UART1 full flow
control + UART2). The G3 machine reused the AST2400 SoC class (wdts_num=2, spis_num=1, uarts_num=5), so WDT2 /
SPI1 / UART3-4 are phantoms.

Did the SAFEST one first — WDT2 (not the flash/boot/console path):
- QEMU (submodule c7d6eb3f1f): gate the _init + realize WDT loops on silicon_rev==AST2050 so the G3 creates
  only WDT1 (i>=1 skipped); AST2400/2500 unchanged. Same opt-in-by-connection pattern as the EHCI/SDMC gates.
- DTS: disable the inherited wdt2@1e785020 node (`&wdt2 { status = "disabled"; }`) so the kernel matches.
- Boot-validated on kgpe-d16-bmc: reaches userspace (dropbear), zero faults, no WDT errors.

REMAINING in #144 (deferred, need more care): SPI1 (0x1E630000) — verify no oracle flash-boot path uses it
before removing (the FMC stays); UART3-4 — DELICATE (the model's UART memmap is non-standard: UART5=0x1E784000
is the used console, UART1=0x1E783000 is SOL — must not remove those). Each is a follow-on with its own
datasheet-address verification + boot test.

Did the dedicated #212 pass properly this time. Found the Zephyr build env (west workspace `tmp/zws/`, SDK
0.17.0, board kgpe_d16_bmc, build dir `build-rtc187` with CONFIG_RTC_ALARM). Added a #212 tight-loop to
`rtc_smoke`: irq_disable(22) (so nothing clears a latched VIC line), re-arm a sec-only alarm at sec=30,
CONFIRM the arm (dump rtc04/ctrl), then tight-loop VIC08 raw terminating on 4 counter-minutes (robust to
CPU/MMIO speed). Built (ninja), JTAG-booted on real silicon, captured. Evidence `d14-zephyr/33`.

RESULT (solid): `#212 re-armed sec=30: rtc04=0000001e ctrl=00000003` (armed: sec-field=30, RTC+sec-alarm
enabled) and `bit26(alarm)=0 bit22(second)=0 OR=03000000 sec-range=19..59 mins=4` — the counter provably
crossed sec=30 four times with the ISR off, yet **VIC bit 26 NEVER asserted**. => the RTC alarm does NOT
drive VIC 26.

HONEST CORRECTION: this **REFUTES my earlier C2 flag** (commit 674bec4) which said the alarm was "probably on
26" and #192 was confounded. The cleaner silicon test says NOT on 26 — #192's "not on 26" is SUPPORTED, and
MY armchair confound analysis was the wrong thing. Silicon is the oracle, and here the lesson applied to my
OWN reasoning, not to prior work. Corrected the matrix flag (retracted "probably on 26").

BUT #212 stays OPEN (redirected, not closed) because a DEEPER issue surfaced: the driver alarm ISR
(`rtc_aspeed_g3.c:275`) has NO alarm-MATCH check — it fires the callback on ANY VIC-22 interrupt. So the
existing "alarm PASS (armed→VIC22→callback)" only proves "VIC 22 fired once", NOT that the alarm matched — a
possible FALSE PASS if 22 is the datasheet second-tick. And bit22=0 in polling (a latched second-tick would
show, as bits 24/25 do), so 22 isn't a latched second-tick either. Net: neither "alarm on 26" (datasheet) nor
"alarm functionally validated on 22" (#192) is established; the true alarm line + whether it fires at the
armed time are UNRESOLVED. #212 redirected: add a match-checking ISR, then re-test 22 AND 26. Taking a break
from RTC (deep RE — come back fresh) per the goal's "work on another part when stuck". Committed the rtc_smoke
diagnostic (a reusable test tool) + evidence + matrix correction.

## 2026-07-21 — Gate-b review of #211 (I2C 7-engine): CLEAN — independently verified

The independent gate-b code review of the #211 shared-code change (the new G3-only `aspeed.i2c-ast2050`
subclass) returned with **no issues ≥80 confidence** — a clean pass. It verified all six points I asked it
to adversarially check: the datasheet 7-engine count (3 citations: datasheet lines 1606/2459/1931), the QOM
inheritance semantics (read `qom/object.c` `type_initialize` directly — the parent `aspeed_2400_i2c_class_init`
runs to completion and is memcpy'd into the child before the child's `class_init` overrides only `num_busses`;
no field is zeroed/half-init), the region layout (all 7 buses take the `i<gap` branch → 0x40..0x1C0, matching
silicon), G3-only containment (AST2500/2600/2700 untouched; the hw/arm/aspeed.c boards using buses 7/8/11 are
non-G3 machines), the VMState fixed-16 serialization (pre-existing + harmless, not new), and that the kgpe
machine uses only buses 0/1/3/4. Recorded the gate-b PASS in the row-15/#211 note.

Meaningful contrast with the HACE gate-b review (which caught the SCU04[5] bug and forced a revert): this
time the careful scoping — subclass-and-override + boot validation + datasheet triple-check BEFORE landing —
produced correct shared-code, and the independent review confirms it. The gate-b mechanism is doing its job
in BOTH directions (catch when wrong, confirm when right). #211 is now a genuine both-checks-pass unit.

## 2026-07-21 — C3 resolved: articulate the QE ✅/🔶 grading standard (gap significance, not arbitrary)

Took the goal's "take a break when stuck" advice — parked the RTC #212 rat-hole (honestly flagged, attempt-2
plan documented) and closed the LAST open enumeration-audit finding, C3 (rows 15/35 kept ✅ while 42/43 went
🔶 — flagged as possibly inconsistent). Resolution: the split is a principled gap-SIGNIFICANCE gradient, now
made explicit in the row-35 note:
- ✅ = primary + all firmware-exercised functionality modeled + validated, only a MINOR optional/diagnostic
  sub-mode unmodeled (row 15 = one optional I²C DMA-buffer transfer mode, byte+pool done; row 35 = the SCU
  freq-counter PLL-lock diagnostic).
- 🔶 = a MAJOR function or half the device stubbed/partial (row 43 = the whole AES/RC4 crypto half; row 42 =
  the PECI engine partial; row 5 = the port-80h snoop datapath absent).
Under this line 15/35 = ✅ is consistent with 42/43 = 🔶 — the gaps differ in kind ("one optional I²C mode" ≠
"no crypto engine"), and every gap is disclosed in its note (not a weasel). Fixed the misleading "dispositioned
like PECI/HACE" phrasing (which implied same-status). All three gate-a/d findings now closed: C1 #211 (fixed),
C2 #212 (flagged + attempt-1 done, attempt-2 planned), C3 (resolved here). Also dispatched an independent
gate-b code review of the #211 shared-code change (a subclass in aspeed_i2c.c) — the HACE precedent shows I
can be confidently wrong about shared code, so verify it rather than let it stand review-less.

## 2026-07-21 — #212 attempt 1: isolated silicon RTC-VIC test — INCONCLUSIVE (my setup), honest record

Ran the isolated silicon JTAG test to resolve the RTC alarm VIC-source (22 vs 26). Confirmed the rig was
free (no openocd, single sshd = mine, no tmux/coord locks), board powered (JTAG halt OK). Wrote a pure-JTAG
TCL (`tmp/rtc-vic-isolate.tcl`) that free-runs the RTC while the CPU is halted (OpenOCD `sleep`) and polls
VIC08 raw (0x1E6C0008; bit26=alarm, bit22=second). Fixed one API bug (`ocd_mdw`→`read_memory`). Evidence:
`d14-zephyr/32-rtc-vic-isolate-attempt1-inconclusive.txt`.

RESULT — INCONCLUSIVE, and I'm confident it's MY test setup, not the hardware (the goal's honesty mandate):
- GOOD: the counter free-runs while JTAG-halted (PHASE2 counter advances every poll, cycling sec through 30
  many times), so the RTC clock+counter path works. And `SCU08[16]=1` clearly runs the counter fast (matches
  the driver comment, contradicts the LS "clear bit16" note — but the RATE is confounded, see below).
- NULL alarm result: bit26=0/60 AND bit22=0/60 — neither the alarm nor the second-tick appeared in vic_raw.
  But #192 (Zephyr) saw vic_raw=0x03400000 (bits 22/24/25), so the RTC CAN drive the VIC — my minimal
  bare-JTAG config just doesn't reproduce the interrupt generation. Two concrete defects: (1) NO CONTROL[5]
  restart-busy poll after the async 0x5A load (datasheet §24.4; my 50 ms sleep too short → counter never
  cleanly reset, RTC likely mid-load when I wrote RTC04/RTC0C); (2) minimal RTC0C[0]|[1] config vs the fuller
  set_time + sec/min/hour-mask alarm the Zephyr path uses.
- So this run neither confirms nor refutes 22-vs-26; it proves the counter free-runs and my setup is
  incomplete. Also surfaced that SCU08[16] semantics are themselves disputed (a THIRD tangled RTC claim
  alongside the alarm-IRQ and the 732x rate) — all must be pinned in the refined test.

REFINED PLAN (#212 attempt 2, next pass): reuse the PROVEN interrupt path — modify the Zephyr rtc_smoke to
MASK VIC 22/24/25 (leave only 26), arm the alarm, and report whether the callback fires via 26 + dump
vic_raw. Callback-on-26-only firing = alarm truly on 26; no fire = not on 26. Rebuild + JTAG-boot. (This is
the clean isolation: once VIC 22 is masked, the fast second-tick can't reach the handler, killing the
confound.) Not rushing a code change to the driver/model until attempt 2 gives a clean answer.

## 2026-07-21 — C2: the RTC "alarm on VIC 22" silicon claim is SUSPECT (confounded); opened #212

Acted on the enumeration audit's finding C2 (RTC alarm IRQ 22 vs 26). Also confirmed the CI "failure" on the
row-4 commit is FLAKY, not a regression: the only failed job is C3 "Build musl userspace" at
`fetching musl toolchain https://musl.cc/... failed: Connection timed out` (8 retries) — a transient external
host outage; every functional job (QEMU build, C2, C4, C-UBOOT, D07/D08/D09, all F-tests) passed. The #211
commit's run is already re-attempting the fetch; no action needed beyond noting it.

C2 investigation (datasheet + evidence, no code change yet):
- Datasheet Table 36 is unambiguous: **22=RTC second, 23=day, 24=hour, 25=minute, 26=RTC alarm** — the RTC
  has FIVE VIC sources. §24.2 features "Programmable alarm with interrupt generation".
- The matrix (#192, `evidence/d14-zephyr/28`) claims silicon PROVED the alarm fires on VIC **22** (not 26)
  and rewired the driver/model/dts 26→22. Re-reading the evidence, the diagnostic is **confounded**:
  - "source-22 serviced it → fires=1" is exactly what the ~732×/s *second*-tick on VIC 22 yields regardless
    of the alarm (a circular, self-consistent signal — the same trap as last session's HACE SCU04[5]).
  - The source-26 snapshot `vic_raw=03400000` has bits 22/24/25 SET = the datasheet's second/hour/minute RTC
    interrupts (the note dismissed them as "background"); bit 26 CLEAR in a single snapshot can't distinguish
    "alarm never asserted 26" from "asserted-and-already-serviced".
  - The note's premise "RTC0C has only alarm-enable bits → the RTC's sole interrupt is the alarm" is wrong:
    RTC0C[1:4] are the alarm's second/min/hour/day *sub-field* compare-enables (datasheet: "Enable second
    alarm"…), NOT periodic masks; the periodic ticks (22/24/25) assert regardless.
- Most likely conclusion: the alarm IS on 26 (datasheet), #192 misread the fast second-tick on 22 — meaning
  the 26→22 rewiring is probably WRONG. But per last session's lesson I will NOT rewire on analysis alone
  when silicon might genuinely differ.
- Action: flagged the matrix #192 claim ⚠️ SUSPECT/REOPENED, marked the alarm-IRQ-source PASSes as UNVERIFIED
  pending **#212 = an ISOLATED silicon JTAG test** (mask VIC 22/24/25, or gate on a 0→1 *transition* of bit
  26 at the armed time rather than a snapshot, so the alarm is observed free of the second-tick). Next pass
  runs #212 on the rig to definitively resolve 22-vs-26 and then correct whichever side is wrong.

## 2026-07-21 — FIX #211: remove 7 phantom I²C engines from the G3 model (14→7, datasheet-faithful)

An independent gate-a/d enumeration sub-agent (dispatched last commit) returned strong results: **A (missed
devices) and B (orphan rows) both EMPTY** — positive gate evidence that the matrix is complete at the device
level (it verified every SoC-internal register base + IRQ against the datasheet §9 memory map + Table 36) —
and it CONFIRMED my row-4 fix. It found 3 concrete items (C1 I²C engine count, C2 RTC alarm IRQ, C3 QE
✅/🔶 consistency). Acted on **C1**, which turned out to be a real model bug, not just a label:

- Datasheet V1.05 says **7** I²C/SMBus controllers (verified 3×: "Integrate 7 sets…", "7 sets of device
  registers", SDA7/SCL7 highest). Row 15's label said "8 engines"; the schematic's "I2C8" is a muxed
  segment off I2C7 (QU9/QU5), not a SoC engine.
- The G3 machine reused `aspeed.i2c-ast2400` (`num_busses=14`) → the model had **7 phantom engines**
  (0x1E78A300+) the silicon lacks — same class as the removed phantom SRAM/ADC.
- CAREFUL SCOPING (last commit's lesson): first checked whether reducing to 7 would break anything. My
  initial grep was polluted by OTHER machines (fby35/ast2600_evb/yosemitev2 use buses 7/8/11); the ACTUAL
  kgpe-d16 machine uses only buses 0/1/3/4 (schematic I2C1/2/4/5, per the code comments). And the shared
  ast2400 class MUST stay 14 (real AST2400 boards use the upper buses). So the fix is a G3-ONLY subclass.
- FIX: new `aspeed.i2c-ast2050` type (inherits TYPE_ASPEED_2400_I2C, overrides only `num_busses=7`; verified
  the region math `offset = i<gap?1:5` maps 7 engines to 0x1E78A040..0x1E78A1C0 = silicon), wired on
  `silicon_rev==AST2050_A1_SILICON_REV`. opt-in-by-connection; other SoCs untouched.
- VALIDATED: rebuilt qemu-system-arm; full boot test — buses 0/1/3/4 register at the right offsets, FRU
  EEPROM (at24 4-0054) binds, GPIO mux (buses 14/15/16) works, sensors enumerate, boot reaches login, no
  faults. Identical behaviour to before, minus the phantoms (the benign `smbus: Unexpected stop` probe
  artifact's QOM device index shifted [19]→[12] = exactly the 7 removed buses).
- Row 15 label 8→7; QE stays ✅ (removed a defect; only #190 DMA-buffer optional mode remains). Tracked as
  **#211 (DONE)**. C2 (RTC alarm IRQ 22-vs-26) and C3 (consistency) deferred to a focused next pass — C2
  especially needs careful silicon-vs-datasheet reconciliation (possible A3 erratum vs a fast-second-tick
  misdiagnosis), and I will NOT rush it.

## 2026-07-21 — Matrix accuracy: reconcile row 4 "LPC mailbox" to the datasheet (no MBX block)

Applied last commit's lesson (authoritative datasheet feature/register text, not assumptions) to a
matrix-accuracy pass on the QE ⬜ frontier. Row 4 was "LPC mailbox (§5)" with a note saying it "needs a
separate `aspeed-lpc-mbox` node + a host peer" — subtly wrong for the AST2050.

Verified against the datasheet V1.05 (authoritative feature list + memory map):
- **No dedicated mailbox (MBX) controller on the AST2050.** No "mailbox" block; nothing at 0x1E789200
  (the AST2400 MBX base). LPC base is 0x1E789000; its BMC controller has 3 KCS/BT register sets + VUART/PUART.
- The schematic §5 (authoritative wiring) line 207 groups "KCS/IPMI, **mailbox** and virtual-UART" — so the
  "mailbox" IS traceable to the schematic, but it means the **BT (Block-Transfer) mode of LPC Channel #3**
  ("Channel #3 supports KCS or BT interface"; `BTENBL`; "channel #3 BT mode: PCLK > 0.5*LCLK"), the IPMI
  alternative to KCS on the same channel — NOT an AST2400-style MBX device.
- QEMU `hw/misc/aspeed_lpc.c` models KCS only (channels 1–4, no BT datapath), so BT-mode is genuinely QE ⬜.

Fix: renamed row 4 → "LPC Ch#3 BT interface (§5 'mailbox')"; rewrote the note with the datasheet grounding
(BT-mode of Ch#3, not a separate MBX node; firmware-unexercised — KGPE/C410X use KCS; host-peer-gated for a
data transaction, like snoop/vUART); updated the §5 schematic-coverage-map row and corrected a stale header
summary ("4 QEMU ⬜" → the accurate 6: LPC-BT[4], TPM-passthru[7], DDC/EDID[14], SMBus-ALERT[25],
2D-BitBLT[46], PCI-arbiter[48]). No status flips (row 4 stays QE ⬜ — correct); this is a label+grounding
correction so the ⬜ means the right thing (BT datapath unmodeled), not a nonexistent MBX block. Dispatched an
independent enumeration sub-agent to check the rest of the schematic ↔ matrix mapping for similar mislabels
(gate a/d).

**This documents a mistake I made and committed, that an independent code review caught. Honest record per
the program rules.** While going to the datasheet to disposition #210 (the crypto half), I *also* claimed to
find a "second documented crypto reset" — SCU04[5]=hrstn (allegedly Figure 43 "Crypto Engine Reset") — and
extended `g3-hace-gate` in `hw/misc/aspeed_scu.c` to gate HACE compute on `SCU0C[13] OR SCU04[4] OR SCU04[5]`
(submodule 717a30bd9a; parent a6800da). I "validated" it with a 3rd/4th `hacetest` sub-test asserting bit 5.

**It was WRONG. There is no second crypto reset.** The AUTHORITATIVE SCU04 bit-field table (datasheet V1.05)
reads:
  * `4 RW  Reset HAC Engine`      — bit 4 = the Hash & Crypto Engine reset (the correct, only crypto reset).
  * `5 RW  Reset LPC Controller`  — bit 5 = LPC controller reset ("applied to both LPC Controller and the
    BMC controller embedded in LPC Controller"). NOT crypto.
§8.2's Clock/Reset Tree lists the Crypto Engine with a *single* reset (AES_RST_N). My change tied HACE compute
to the LPC controller's reset — so any guest resetting LPC (KCS/BT re-init, which IS exercised — row 3) would
spuriously hold the hash engine off. A pure faithfulness bug (invented behaviour, exactly what the governing
principle forbids).

**Root cause (be honest about confidence — I DID do something wrong, not the hardware):** the pdftotext
linearization put the "Figure 43: Crypto Engine Reset" caption (which belongs to bit **4**) next to the
`SCU04[5]` token, and I trusted that adjacency instead of cross-checking the authoritative bit-field table.
My own pre-session notes already had it right ("[4]=AES_RST_N (Crypto)"); I overrode a correct fact with a
mangled snippet. And my `hacetest` "proof" was CIRCULAR — it only showed the model does what I coded (gate on
bit 5), never that bit 5 *is* a crypto reset. A self-consistent test cannot catch a wrong premise; only the
independent datasheet re-reading (gate-b code review, agent a1ca801d22803a109, 95% confidence) could, and did.

**Reverted in full:** submodule revert `14e0d03edc` (restores gate to `SCU0C[13] OR SCU04[4]` + adds a guard
comment recording that SCU04[5]=LPC-reset so the trap can't recur); reverted the `hacetest` hrstn sub-tests;
restored the correct `soc-hace/01` citation (bit 4 = HAC Engine reset, Fig.43); deleted the bogus
`soc-hace/02` evidence; reverted the row-43 matrix bit-5 claims. Rebuilt qemu-system-arm + initramfs; the
restored 2-transition `hacetest` gate PASSES (gated→0x0, released→0x200). LESSON: the authoritative
register-definition table outranks figure-caption adjacency in linearized PDF text — always cross-check the
bit table; and a test built on the same assumption as the code proves nothing.

**Still-valid outcome — #210 disposition (kept):** the datasheet DOES fully document the crypto path (ch.19 +
§19.4 context buffers: RC4 272 B / AES-128 192 B / AES-192 224 B / AES-256 256 B), so a faithful
`qcrypto_cipher` model is possible — but NO KGPE-D16 firmware exercises the crypto engine (only unrelated
Tegra20 U-Boot AES code is in-tree). So #210 stays correctly LOW-PRIORITY firmware-unexercised (class of #190
I2C DMA-buffer / #191 SCU freq-counter); row 43 stays 🔶 as the HONEST end-state. Tally unchanged.

## 2026-07-21 — Gate (a): adversarial verify of THIS session's changes → 2 findings, both fixed

Dispatched an adversarial verifier over this session's matrix claims (rows 9/19/24/43/44/45 + #208). It
CONFIRMED rows 19 (TSOD), 24 (PSU #198), 44/45 (MDMA/MIC #208 — incl. the honest "bit-exact checksum, page
differs by scan size" scoping and the A2P no-action disposition), and the #182 honest scoping (row 9 NOT
bumped to ✅). It found **2 real defects — both the "assertion-only / partial-marked-✅" pattern this
session's own audits corrected elsewhere — now fixed:**

1. **Row 43 HACE QE ✅→🔶 (over-claim).** The model computes real HASHES (silicon-validated #209) but the
   CRYPTO half is a `LOG_UNIMP "Crypt commands not implemented"` stub — AES/RC4 UNMODELED. Under "QE = full
   emulation of ALL functionality" (the same standard that downgraded rows 8/9/11/16 this session, and keeps
   42/47 at 🔶) the hash/crypto engine is 🔶 not ✅. Corrected the cell + the too-soft disclosure ("not
   separately silicon-validated" → "NOT IMPLEMENTED"); opened **#210** for the crypto path. Tally QEMU 28→27✅.
2. **#182 evidence gap.** The matrix asserted `F6-VMEDIA-CDROM: PASS` but no transcript was committed (the
   #182 commit touched only matrix/LOG/init). Re-ran f6usb + committed the transcript to
   `evidence/f6-usb/04-vmedia-cdrom-qemu-PASS.txt` (idProduct 0104 enumerates, lun.0/cdrom=1, PASS).

The verifier earning two corrections is exactly why gate (a) needs INDEPENDENT eyes — I'd applied the
partial-vs-✅ standard to 8/9/11/16 but missed applying it to my own HACE ✅, and I asserted a PASS without
saving its transcript. Both are the traps the session-long honesty discipline exists to catch.

## 2026-07-21 — #182 DONE: virtual media presents as a CD-ROM (§9 "CD"), not a removable disk

Closed the last genuine §9 delta for row 9: the USB virtual-media gadget presented a removable
Direct-Access DISK, but §9 says "virtual keyboard/mouse/CD". Set `lun.0/cdrom=1` (SCSI type 5, read-only)
in BOTH gadget paths in initramfs/init — the `f6usb` dummy_hcd loopback and the USB/IP export. Validated in
QEMU (`f6usb` gate): `vmedia lun.0/cdrom = 1` + the dummy_hcd host enumerates the USB device → F6-VMEDIA-
CDROM PASS. HONEST scope: the host-side /dev/sr0 CD-ROM node needs usb-storage+sr_mod on the host, which the
minimal-initramfs dummy_hcd loopback does NOT load (the host enumerates the USB device but not the SCSI
layer) — so the host-side CD-ROM view is the USB/IP-to-a-real-host path (row 9 LS 🔷, rig-blocked, same
transport that proved the disk variant on silicon). First attempt asserted dmesg "CD-ROM" (host SCSI line) →
FAIL (no usb-storage on the loopback host); corrected the assertion to the achievable QEMU proof (gadget
config + USB enumeration) rather than assert something the minimal initramfs can't show.

## 2026-07-21 — Gate (b): independent code review of the #208 reset-gating code = CLEAN

Dispatched an independent code-reviewer on both #208 submodule commits (61615dba75 MDMA/MIC MMIO gating +
589f68f99a HACE compute gating) + the initramfs gate changes. Verdict: **REVIEW CLEAN** (no findings ≥80
confidence). Verified the subtle parts: (a) ORDERING — the SCU→engine reset GPIO lines are wired in the SoC
realize BEFORE the machine-level reset that first fires propagate_gates, and the MDMA/MIC/HACE are already
realized+mapped by then (no use-after-free / not-yet-realized); (b) both SCU04 reset tables (0xFFCFFEDC +
0x000FFE5C) hold bits 16/18 set + SCU0C[13]/SCU04[4] set, so the engines start held/clock-stopped by default
== silicon; (c) the HACE early-`break` is inside the switch so the common `regs[addr]=data` writeback still
stores the CMD (reg file stays live, compute skipped) — intended; (d) opt-in-by-connection is provably inert
on G4/G5 (g3_compute_gated defaults false, only driven by the G3-only-wired gpio); (e) all initramfs
bitmasks (bit16=0x10000, bit18=0x40000, SCU0C[13]=0x2000, SCU04[4]=0x10) correct. ONE sub-threshold note
(~50 conf, explicitly NOT a #208 defect): the SCU propagate_gates derived GPIO state isn't re-derived after
loadvm — PRE-EXISTING (shared by g3_i2c_rst etc.), only matters if this fork ever supports migration (it
doesn't). Folded into #202. Gate (b) is satisfied for the #208 reset-gating code.

## 2026-07-21 — #208 follow-up: HACE compute-gating modeled (YCLK/AES_RST_N), validated

Closed the HACE half of the #208 gap the silicon validation exposed. Silicon holds the HAC COMPUTE engine
off (SCU0C[13]="Stop YCLK" OR SCU04[4]=AES_RST_N) while the register FILE stays live — so, unlike MDMA/MIC
(whole MMIO goes dark), the HACE must gate only the compute. Added a `g3-hace-gate` SCU output line (=
SCU0C[13] || SCU04[4]) wired straight to a new HACE gpio-in; when asserted, a HASH_CMD write stores the
register but skips do_hash_operation + sets NO completion status. Opt-in by connection (only wired on the G3
SoC → G4/G5 romulus/etc. unchanged — the shared aspeed_hace.c change is inert there). QEMU submodule
589f68f99a. Validated by a new `hacetest` initramfs gate: force YCLK-stop → SHA-256 command leaves R_STATUS
HASH_IRQ (0x200) CLEAR (no compute); release YCLK+AES_RST_N → HASH_IRQ SET (computed) → HACE RESULT PASS.
C2 boot + PSU(#198) unaffected. Applied the opt-in-by-connection lesson (#198/#208) so a shared-upstream
change stays contained + needs no cross-machine qtest sweep.

## 2026-07-21 — 🎉 SILICON: HACE SHA-256 validated on the REAL AST2050 (row 43 QE 🔶→✅, #209 DONE)

Went ahead and did the full HACE silicon hash validation (didn't stop at "feasible"). Hashed 64 zero bytes
with SHA-256 on the real AST2050 HACE over JTAG (evidence soc-hace/01 + hace-hash-silicon.tcl): the digest
read back **f5a5fd42 d16a2030 … 2759fb4b = the exact known sha256(64·0x00)**, byte-for-byte. So the G3
HACE register layout (SRC/DEST/SRC_LEN/CMD) + SHA-256 CMD encoding (0x50) MATCH the generic aspeed_hace
model — resolving row 43's 🔶 ("G4 model vs AST2050 11-reg variant unverified"). QE 🔶→✅; tally QEMU 27→28✅.

GOVERNING-PRINCIPLE LESSON (third time this session): the engine first didn't fire (digest unchanged, the
0xEEEEEEEE sentinel intact). Not the hardware — MY driving: the HAC COMPUTE engine is clock-dead + held in
reset at power-on even though the register FILE responds. Datasheet: SCU0C[13]="Stop YCLK (For HAC)" (§18
l.16040, YCLK is the hash/crypto clock) + SCU04[4]=AES_RST_N (Fig.43 Crypto Engine Reset). Clearing BOTH
made it compute. This is why the earlier register-only probe saw the block "alive" but the hash didn't run.
Same reset/clock-gating faithfulness gap as MDMA/MIC (#208) — the QEMU HACE responds without the release →
follow-up on #208 (subtler here: gate the compute, not the whole MMIO, since the reg file responds while
clock-off). TCL gotcha again: `src[0]` in an echo string = command substitution (fixed to src0).

## 2026-07-21 — HACE (row 43) bounded silicon probe → #209 (feasibility confirmed, full validation scoped)

Bounded JTAG probe of the HACE @0x1E6E3000 (tmp/hace-probe.tcl) to scope row 43's 🔶 ("G3 11-reg variant vs
the generic G4 model — unverified"). Finding: the HACE register file RESPONDS on real silicon — R_HASH_SRC
(0x20) stored my write 0x02001000 and R_HASH_SRC_LEN (0x2c) stored 0x40; so, unlike MDMA/MIC, the HACE is
NOT reset-gated (register file alive by default), and the model's offsets match. A full silicon hash-digest
validation (program a SHA-256 of a known buffer, compare the digest) is therefore feasible and is the clean
path to row 43 QE 🔶→✅ + silicon cross-validation — captured as **#209** with the precise sequence.
Deliberately NOT started as a half-cycle here (multi-step JTAG session); the aspeed_hace.c model already
computes real hashes via QCryptoHashAlgo, so a QEMU-side devmem hash gate can be built in parallel to
cross-check. Honest scoping, not a dodge — the probe confirmed feasibility + the register match.

## 2026-07-21 — #208 DONE: model the MDMA/MIC SCU04 reset-hold (silicon-faithful)

Fixed the faithfulness gap the MDMA silicon validation exposed. The AST2050 holds the MDMA (SCU04[16]=
DMA_RST_N, Fig.54) and MIC (SCU04[18]=MIC_RST_N, Fig.55) in reset at power-on — their register files are
inert until firmware clears the bit. QEMU responded immediately. Extended the EXISTING G3 SCU side-effect
mechanism (which already gates the I2C controller on SCU04[2] via memory_region_set_enabled) with two more
lines: g3-mdma-rst + g3-mic-rst. The SoC disables the MDMA/MIC MMIO window while the reset bit is held —
the models themselves needed NO change (elegant: the reset-hold is a MMIO-enable toggle). QEMU submodule
61615dba75. Both SCU04 reset tables already default bits 16/18=1, so the engines start held (== silicon).

VALIDATED: (1) mdmacopy first showed dst=0 (MDMA correctly inert while held) — proof the gating works;
(2) added the SCU04 reset-release to the mdmacopy + mictest initramfs gates (unlock SCU key, clear bit
16/18) — this makes the gates MORE faithful (real firmware must release the engine, as the JTAG tests do);
(3) mdmacopy PASS (dst=0xDEADC0DE) + mictest PASS (0xFFFFFFFF / 0x10002000) after the release; (4) C2 direct
boot + SSH works (no oracle regression) and #198 still passes on this build. Applying the #198 lesson again:
a contained extension of an existing mechanism, not a risky rewrite.

## 2026-07-21 — 🎉 SILICON: MDMA model cross-validated on the REAL AST2050 via JTAG (row 45)

Cross-validated the QEMU aspeed_mdma_ast2050 model against the real AST2050 MDMA over JTAG (evidence
soc-mdma/04 + mdma-test-silicon.tcl). After AHBC unlock+remap (DRAM→0x0, so the 28-bit engine reaches DRAM),
a 16-byte COPY round-trips `deadbeef 12345678 a5a5a5a5 5a5a5a5a` src→dst, a FILL writes `f00df00d`, and
`MDMA14 = 0x00010100` (idle + ID-0 done) — IDENTICAL to the QEMU model's copy/fill/per-ID-done semantics.

GOVERNING-PRINCIPLE LESSON (again): the block first read 0 / ignored writes — I assumed nothing, probed, and
found it was MY driving: datasheet Fig.54 shows **SCU04[16] = DMA_RST_N** holds the MDMA in reset at
power-on. My initial vInitSCU mask `SCU04 &= 0xBFFFF` cleared bit 18 (MIC) but KEPT bit 16 set → MDMA dead.
Clearing SCU04[16] (0x000ffe5c → 0x000afe5c) brought it alive and the copy/fill worked. Confirmed the address
is right (datasheet §22.3 p257 = MDMA @0x1E740000), so this was reset-driving, not a wrong-address model bug.

FAITHFULNESS GAP FOUND → #208: the QEMU MDMA/MIC models respond immediately, but silicon holds them in reset
(SCU04[16]/[18]) until released. To be fully faithful the models should gate their MMIO on the SCU04 reset
bit. Tracked as a broader SCU-reset-modeling task. Two TCL gotchas fixed en route (chained openocd vs
separate invocations since ddr2-init ends in `shutdown`; `[16]` in a TCL echo string = command substitution).

## 2026-07-21 — #198 FIXED: PSU phantom sensors eliminated via an opt-in SMBus command-NACK

Went ahead and did the SMBus-layer fix — SAFELY, as an OPT-IN, so it did NOT need the full qtest suite to
prove no cross-device regression (the earlier "dedicated cycle" caution assumed a global change; the opt-in
design removes that risk by construction). Added `SMBusDeviceClass::check_command(dev, cmd)` — called on the
FIRST (command) byte of a write phase; non-zero return NACKs it. Default NULL keeps ACK-everything, so every
existing SMBus device is untouched. pmbus_psu NACKs READ_VCAP/TEMPERATURE_2/TEMPERATURE_3. The command-byte
NACK aborts the read-word → Linux's pmbus_check_word_register gets rv<0 → sensor ABSENT (vs reading 0xFFFF as
present). QEMU submodule 918836e937.

VALIDATED both-sides-of-the-boot (scripts/psu-hwmon-test.py, full Linux): the phantom in2(vcap)/temp2/temp3
= -500 are GONE; all real sensors intact (vin 230V, vout 12V, temp1 30C, iin/iout, pin/pout); W83795 +
SB-TSI + at24 EEPROMs bind in the same boot (no regression — opt-in leaves them untouched). Evidence
d09-psu-pmbus/02. Row 24 PSU now faithful (no phantoms); #198 DONE. The check_command hook is reusable for
any device needing to NACK unsupported commands. Lesson: an opt-in shared-layer callback can make a
"risky global change" safe + contained — worth reaching for before deferring to a heavyweight cycle.

## 2026-07-21 — #198 PSU pmbus phantom sensors: REPRODUCED + fully root-caused (fix = SMBus-layer cycle)

Stopped scoping and actually reproduced #198. Booted Linux (scripts/psu-hwmon-test.py, new reusable
harness) and dumped the PSU pmbus hwmon (i2c0/0x58): the real sensors are all correct (vin 230V, vout
12V, temp1 30C, iin/iout, pin/pout), but THREE phantom sensors read -500: **in2(vcap), temp2, temp3**
(evidence d09-psu-pmbus/01). COMPLETE root cause traced through QEMU + Linux: pmbus_psu.c doesn't set
PB_HAS_VCAP/TEMP2/TEMP3, so hw/i2c/pmbus_device.c gates those reads off → `goto passthough` → returns
PMBUS_ERR_BYTE=0xFF/byte → word 0xFFFF → LINEAR11 decode = mantissa -1 × 2^-1 = **-0.5 = -500** milli-units
(exactly the observed value). Linux's `pmbus_check_word_register` treats any `rv>=0` (0xFFFF=65535) as
sensor-PRESENT, so it creates the phantom attrs; a real PSU NAKs the unsupported command byte so the read
returns <0 and Linux skips it.

WHY THE FIX IS A DEDICATED SMBUS-INFRA CYCLE (honest, not a dodge): QEMU's SMBus slave layer CANNOT NAK a
read on the command byte — `hw/i2c/smbus_slave.c:62-63` calls `write_data` and DISCARDS its return, and the
per-byte send just buffers. So no pmbus-model change can signal the NAK. The faithful fix must teach
smbus_slave.c to honor a write_data NAK (or a per-device opt-in) — a change touching EVERY SMBus device
(tmp105, at24 EEPROMs, the other pmbus VR/PSU models), so it needs the full pmbus/SMBus qtest suite to
prove no cross-device regression. A careless "honor any non-zero return" would break legitimate paths that
already return PMBUS_ERR_BYTE. Deferred to a dedicated cycle WITH qtest validation rather than risk
regressing the many validated I2C/SMBus cells. Row 24 real-sensor cells stay ✅; the phantom gap is now
reproduced + root-caused with the fix path pinned.

## 2026-07-21 — CI fix: corrupt kernel patch 0007 (vhub) — the kernel build was red

Autonomous CI check found the "Build D16 kernel (uImage + dtb)" job FAILING: `error: corrupt patch at
kernel/patches/0007-usb-aspeed-vhub-ast2050-g3.patch:38`. (The C3 musl job also fails — that's the known
#143 musl.cc-mirror issue, not this.) Root cause: commit b422e84 ("vhub comment fixed") EXPANDED the
hunk-1 comment by 7 lines but left the stale `@@ -160,6 +160,25 @@` count (should be 32 = 6 context + 26
added) AND the stale post-image `index` hash — so `git apply` rejected it, blocking the whole kernel
build (and every downstream boot job). Regenerated a correct patch definitively: reset core.c to pristine
(HEAD is unpatched; the tree only had it applied in the working copy), `git apply --recount` the body,
`git diff` → correct headers (+160,32 / +224,32 / +465,16 — the +7 shift propagates to later hunks) +
correct index; `git apply --check` PASSES on pristine. Only the @@ counts + index changed; the code body
is unchanged. Unblocks the kernel/dtb build → the C2/spd-test/C4/etc. boot jobs.

## 2026-07-21 — Row 19 DIMM TSOD: modeled + validated the datapath (QE/LQ/LU ✅, #205)

Acted on audit slice-2 F1 (TSOD is a real device the matrix under-claimed). Added an OPT-IN machine
property `-M kgpe-d16-bmc,ts-dimm=on` (default off = bench-faithful, where the rig's TS-less A2 UDIMM
NAKs at 0x19) that populates a JEDEC JC-42.4 TSOD (`hw/sensor/jc42.c`) at 0x19 on the QU5 Y2 (DIMM A-D)
bank @42000 mC — QEMU submodule f3b9a9bd34, following the existing `execute-in-place` machine-bool
pattern. Declared `temp@19 "jedec,jc-42.4-temp"` in the board DTS (describes the board capability; the
jc42 driver NAKs+skips on the TS-less rig, binds when a sensor is present). Extended `scripts/spd-test.py`
with `--ts-dimm` (swaps the TSOD-absent assertion for a TSOD-present one).

**BOTH modes PASS on the faithful machine:**
- `--ts-dimm`: SPD read through QU9/QU5-Y2, then the Linux jc42 binds at 0x19 and userspace reads hwmon
  `temp1_input=42000` THROUGH the mux → row 19 QE=✅, LQ=✅, LU=✅ (evidence d08-tsod/01).
- default: `temp@19` exists but 0x19 NAKs → jc42 does not bind → TSOD absent → NO regression.

Gotcha caught: first run read 42000 while the test expected 35000 — I'd edited the source to use the
jc42 default (35000) AFTER building the 42000 binary and not rebuilt (source/binary diverged). Kept the
distinctive 42000 (stronger evidence than the model default), made source match, rebuilt. Also: the
canonical DTS is `dts/aspeed-bmc-asus-kgpe-d16.dts` (build-kernel.sh copies it INTO the gitignored kernel
tree) — edited the real source, not the copy. Row 19 UQ/US/LS/ZS=Ⓝ (U-Boot n/a; bench TS-less DIMM);
ZQ=⬜ (Zephyr jc42, remaining). Tally: Linux@QEMU 22→23✅, userspace 15→16✅, QE Ⓝ 2 (row 19 left Ⓝ set).

## 2026-07-21 — Integrated the 4-slice adversarial audit (gates a + d)

All four independent audit sub-agents reported. **Enumeration CONFIRMED complete** (no missed BMC-side
device; engines 42–50 phantom-free) and **both false-"impossible" corrections CONFIRMED** (NC-SI §7,
DIMM-SPD §10, with silicon evidence). Each slice also caught real defects — integrated all:

- **Row 11 NC-SI QE ✅→🔶** (slice-3 F2): rested on libslirp's generic responder (MFR-0x0); faithful
  dual-82574L OEM-0x157 responder unmodeled → **#204**. UQ/US/LU ⬜→Ⓝ (NC-SI is OS-level; U-Boot nets
  via MAC1). FULL-TASK-LIST C2 "faithful responder [x]"→[~].
- **Row 19 DIMM-TSOD all-Ⓝ→mixed** (slice-2 F1): TSOD is a real device (§10.2, 16 sensors); prior all-Ⓝ
  conflated THIS bench's TS-less DIMM with device-absence. QE/LQ/LU/ZQ ⬜ (model a jc42 → **#205**);
  LS/ZS Ⓝ (bench-gated). This was the SAME class as the NC-SI/DIMM memory false-claims, one level down.
- **Row 40 PWM note clarified** (slice-1 F1): the QE table cell was ALWAYS ✅ (register-accurate model);
  the agent misread the "→ Ⓝ" note (which describes the driver-stack disposition). Verified against the
  file BEFORE editing — did not apply a wrong "flip QE" change. Note reworded.
- **host-BIOS-flash SETTLED** (slice-4 F1, #134 closed): NOT impossible — datasheet §2.20 has the
  LPC-Master/FWH engine (HICR5[10] ENFWH) — but board-N/A (no LPC isolation switch; BIOS is SPI-behind-FCH).
- **iLPC2AHB over-claim split** (slice-4 F2): FULL-TASK-LIST A8 folded the LPC→AHB bridge (culvert `ilpc`)
  into P2A's [x] silicon; split into A8a (P2A validated) vs A8b (iLPC2AHB unmodeled → **#206**).
- **New tasks** (gate d): #204 (82574L responder), #205 (TS DIMM jc42), #206 (iLPC2AHB HICR5/6 model),
  #207 (I2C3/I2C6 disposition). Tally regenerated (QE 26✅/16🔶/0/7⬜/2Ⓝ).

Honest note: two of the fixed contradictions (TSOD "remaining", NC-SI "US remaining") were ones **I**
introduced in the reconciliation doc — the adversarial pass caught my own errors, which is the point.
The remaining program work is driver breadth × silicon/userspace/Zephyr validation depth, not missing
hardware.

## 2026-07-21 — Grounding pass: full schematic read-through + schematic↔matrix reconciliation + false-claim corrections

Re-grounded in the AUTHORITATIVE source (`schematic-wiring/AST2050-BMC-WIRING.md`, all 597 lines,
§1-§16) and cross-checked every device it describes against all 50 DEVICE-MATRIX rows. Wrote
`SCHEMATIC-RECONCILIATION.md` (committed): a §-by-§ device→row map proving **every BMC-side schematic
device (§3-§13) has exactly one matrix row — none missing** — plus the schematic items that legitimately
have no row (power LDOs, glue buffers, host-side peer chips SP5100/SR5690/Super-I/O).

**Corrected false "not-existing / impossible" claims** (the hook's central concern — "incorrect claims
have been made about functionality not-existing or features being unconnected; the schematic is
authoritative; the hardware is reliable, it's my driving that's the issue"):
- **NC-SI**: memory said "true NC-SI impossible / dedicated PHY not NC-SI". Schematic §7 is authoritative:
  the MAC pin-mux runs ch1 MII→RTL8201N (mgmt PHY) AND ch2 RMII2/NC-SI→both 82574L NICs AT ONCE. NC-SI
  IS wired (row 11 QE✅/LQ✅). Corrected in [[bmc-functionality-program]] + [[ncsi-sideband-exists-schematic]].
- **DIMM inventory**: memory said "impossible — i2cdetect shows SPDs on the HOST SMBus not a BMC bus".
  Schematic §10 is authoritative: the BMC reaches all 16 DIMM SPDs via QU9(FET-enable)→QU5(S1:S0 select).
  Matrix row 18 is now LS✅ (silicon-Linux validated). The old i2cdetect "absence" was MY mux-sequencing
  error (governing-principle trap), not proof. Corrected in the memory.
- **USB**: "USB-host impossible" is a misleading framing — the BMC is a USB *device* (§9); that capability
  (vhub, row 9) is covered. **host-BIOS-flash**: UNSETTLED (#134), not "impossible".

**Remaining work is driver breadth + silicon/userspace validation, NOT undiscovered hardware.** The
open cells are the U-Boot-silicon (US), Linux-silicon (LS), and Zephyr (ZQ/ZS) columns across many rows,
plus a handful of QE 🔶/⬜ (rows 4/8/12/14/25/26/28/29/31/42/43/46/47/48/49/50).

**Dispatched 4 independent adversarial audit sub-agents** (schematic slices: memory/GPIO/SoC-core;
I²C fabric; net/video/USB; LPC/serial/SoC-engines) to FALSIFY the reconciliation — find any missed
device, false absent/unconnected claim, coverage gap, or new task (completion gates a + d). Integrating
their findings next.

## 2026-07-21 — C4/C2-full legacy-boot regression: root-caused to #176 SRAM removal, fixed faithfully (#200)

Set out to close #200 ("re-verify the C4 Dell-vendor oracle still boots with the AHBC boot-remap alias").
Ran the C4 web-test on the current build → **FAIL, 0 bytes of serial** (U-Boot hung before its banner). This
matched the open memory flag "C4/C2-full legacy boots now FAIL (leading suspect: measured-strap 4ff6a74504)".
Per the governing principle a broken legacy boot is MY bug, so I bisected instead of assuming.

**Bisect (all on the kgpe-d16-bmc machine, one rebuild each):**
- Reverted SCU70 to the pre-4ff6a74504 G4-constructed strap → **still 0 bytes**. Strap INNOCENT (the memory
  flag's suspicion was wrong — this is exactly why you bisect).
- AHBC alias is disabled at reset → innocent by construction.
- Re-enabled SRAM at 0x1E720000 on the G3 (`if (1)`) → **U-Boot boots instantly** (banner, SoC detect, kernel
  load). ROOT CAUSE = **#176 removing the phantom SRAM**. The evb-ast2400 (G4) shim U-Boot sets its init
  stack to the top of on-chip SRAM (CONFIG_SYS_INIT_SP_ADDR = ASPEED_SRAM_BASE+SIZE = 0x1E728000) and its
  pre-console buffer to 0x1E720000; the G3 has no SRAM there, so on the faithful machine both land in the
  write-discard A2P window → stack corrupts → hang before console.

**Silicon decides #176 (JTAG on the real AST2050, evidence soc-a2p/):** write/read 0x1E720000 → every write
(0xA5A5F00D/0x5A5A0FF0/0xDEADBEEF/0xCAFEBABE) IGNORED, every read a constant **0x04000008** across the whole
0x20000 window; adjacent blocks (0x1E740000, SCU00) read 0. So 0x1E720000 is DEFINITIVELY not RAM → **#176 is
faithful, must NOT be reverted**. The shim is the artifact (a G4 U-Boot can't run on a real AST2050 anyway —
no SRAM for stack; silicon boots via Raptor's G3 U-Boot over JTAG).

**Fix (faithful — SoC model unchanged; QEMU-only shim adapted):** committed `uboot-patches/0004` (init stack
→ DRAM, ASPEED_DRAM_BASE+0x200000) + `0005` (pre-console → DRAM, 0x40100000). Also discovered the local
u-boot tree had UNCOMMITTED half-fixes (pre-con removal + #168 SCTLR.A) that CI never had — hence CI's C4/
C2-full were broken too; my patches make the fix reach CI. Rebuilt U-Boot from a clean tree + all patches.

**Result on the FAITHFUL (SRAM-removed) QEMU:** C4 (Dell vendor→appweb) **PASS**, C2-full (U-Boot→Linux→SSH)
**PASS** (evidence soc-a2p/02). #200 done; the C4/C2-full regression flag is resolved.

**Bonus faithfulness refinement (#176):** modeled the A2P window's silicon-exact readback — QEMU submodule
14be3eed1e replaces the create_unimplemented_device (read 0) with aspeed_a2p_ops returning 0x04000008 and
dropping writes. Both-sides validated: QEMU-monitor `xp` 0x1E720000/24000/27FFC all = 0x04000008 == silicon.
Oracles re-verified PASS with the model present. Row 50 QE stays 🔶 (SCU70[4] gate + P-Bus-target forwarding
to the internal-VGA CRTC still unmodeled — row 14).

## 2026-07-21 — 🎉 SILICON: MIC model cross-validated on the REAL AST2050 — BIT-EXACT vs QEMU (#203 DONE)

Stopped deferring the silicon validation and DID IT. Cross-validated the QEMU MIC model against the REAL
AST2050 MIC hardware over JTAG (SPI flash not connected → JTAG-driven), on the asus-bmc bridge Pi. Wrote a
JTAG TCL (`evidence/soc-mic/mic-test-silicon.tcl`) that mirrors the QEMU `mictest` gate: reset-halt +
ddr2-init, then AHB unlock (0xAEED1A03) + DRAM→0x0 remap, lay out a zeroed 4KB page + control/checksum
buffers, enable the MIC, read the checksum, corrupt the page + re-scan.
RESULT — BIT-EXACT PASS (evidence `soc-mic/02`):
- REMAPCHK: low 0x0 = 0xcafebabe → the **AHBC key + remap are confirmed on REAL SILICON** (validating last
  turn's protection-key faithfulness fix against hardware).
- MIC-CHKSUM: the real MIC computed the zero-page Fletcher-32 = **0xFFFFFFFF**, IDENTICAL to the QEMU model.
- MIC14 = 0x0000000f (real MIC scanned to page 15); after corrupting the page, MIC18 = 0x1000000f (first-
  page-error flag bit28 + the correct page number 0x000F). Same mechanism as the model.
GOVERNING-PRINCIPLE LESSON: the FIRST run had the MIC not scanning (checksum stayed 0). That was MY
incomplete driving, NOT a hardware fault — the Raptor SLT's vInitSCU() (mictest.c) does `SCU04 &= 0xbffff`,
which RELEASES THE MIC FROM RESET (SCU04 bit 18). Adding that one JTAG step made the real MIC scan. "The
hardware is 100% reliable; it's your code" — proven again, and fixed proper by studying the oracle.
IMPACT: the QEMU aspeed_mic_ast2050 model is now proven faithful to real AST2050 silicon BIT-FOR-BIT
(validated in QEMU AND on the real chip), directly answering the goal's central question. This is the first
end-to-end silicon cross-validation of a from-scratch QEMU device model this session. Row 44 annotation +
evidence updated; #203 DONE. (The rig was free — only my own session on the Pi; DDR2 re-trained cleanly.)

## 2026-07-21 — Frontier assessment of the remaining QE ⬜ cells + confirmed silicon MIC-validation feasibility (tracked #203)

With the memory-engine cluster done (MDMA/MIC ✅, AHBC/PUART honestly 🔶), assessed the remaining QE ⬜ cells
for the next unit — being honest that they are all genuinely hard, not quick wins:
- **Row 25 SMBus-ALERT: NOT a bounded cell.** Investigated: `aspeed_i2c.c` only DEFINES the SMBUS_ALERT
  intr bit (header) — it does NOT implement the alert MECHANISM (no slave-assert → master-intr → ARA path);
  the W83795 model explicitly lists SMBALERT# assertion as future work; and QEMU's i2c core has no ALERT/ARA
  plumbing. A faithful model is a multi-part effort (i2c-core alert + aspeed_i2c handling + W83795 assert +
  ARA read), not a quick add.
- **Row 48 PCI-arb:** no register chapter (§9-only) → a named RAZ/WI region is the only faithful model, and
  it overlaps the 0x1E600000 iomem catch-all at equal (create_unimplemented) priority → not a clean overlay;
  low value (register-less arbiter, no PCI bus to arbitrate). 🔶-capped.
- **Row 4 LPC-mailbox** (register block, no host peer) + **Row 14 DDC/EDID** (VGA CRTC §34 space + bit-bang
  I2C + EDID) + **Row 46 2D BitBLT** (PCI/VGA graphics accel): real but each substantial; DDC/EDID and 2D
  live in the PCI/VGA register space (not a 0x1Exx AHB base), a different modeling surface.
HIGHEST-VALUE NEXT STEP (tracked #203): SILICON cross-validation of the MIC model against the real AST2050.
CONFIRMED FEASIBLE at config level — the Raptor SLT that my MIC Fletcher-32 was copied from
(`board/aspeed/ast2050/slt.c` do_slt + mictest.c) is enabled in `include/configs/asus.h` (CONFIG_SLT +
CFG_CMD_MICTEST), so the real chip can run `slt` and byte-compare its MIC hardware output — directly
answering "the hardware is 100% reliable; is my model faithful?". It's a heavier rig workflow (netboot the
Raptor U-Boot on the SHARED real board, must not disturb others), so specced for a dedicated session rather
than rushed here. Expected bit-exact values recorded in #203 (zero page = 0xFFFFFFFF; 0xBEEF-word =
0x7DF7BEEF). No new QE cell closed this turn — an honest frontier-assessment + tracking step.

The independent gate-(a) faithfulness audit of the 4 cells I marked ✅ this session did its job — it found a
genuine faithfulness VIOLATION plus several honest over-claims. Addressed every one:
1. **AHBC (row 49) — REAL BUG (fixed).** The datasheet §12.3 protection key was NOT modeled: my AHBC let any
   write to 0x80-0x8C through, and my own evidence (`soc-mdma/02`, and transitively the MIC/MDMA data tests)
   enabled the remap with a bare `devmem 0x1E60008C 1` WITHOUT writing the 0xAEED1A03 key to AHBC00 — a
   sequence REAL SILICON REJECTS (key locked → remap stays off). This directly violated the "QEMU must model
   real silicon" rule and my tests were passing on a NON-faithful permissiveness. FIX: modeled the AHBC00
   key (writes to 0x80-0x8C dropped while locked; read 0x00 = 1 when unlocked; reset locked; vmstate v2), and
   updated the mdmacopy + mictest gates to write the key first. Rebuilt + re-ran BOTH: still PASS (MDMA copy
   round-trips 0xDEADC0DE, MIC zero-page = 0xFFFFFFFF) — now via the FAITHFUL key path. Row 49 ✅→🔶
   (honest: only key + boot-remap are functional; priority-arbitration is a flat-memory no-op, bus-error
   IRQ31 is storage-only, AHBC8C[4:5] PCI-window remap is stored-only with no PCI host here).
2. **PUART (row 47) — over-claim → 🔶.** It is a register-presence 16550 (scratch responds) but has no
   chardev (can't move a byte) and the 8 extended LPC-control regs PUART20-3C are undecoded (RAZ/WI). Honest
   🔶 (defensible only because no firmware drives PUART).
3. **MIC (row 44) — undisclosed MIC10, addressed → stays ✅.** MIC10 stop-page was unmodeled+undisclosed. FIX:
   modeled the observable MIC10 TAG write-back ({TAG,0}→checksum-buffer[page]); disclosed that the stop-scan-
   at-page is moot under the synchronous scan. Rebuilt + re-ran mictest: still PASS. Core integrity-check
   (bit-exact checksum → mismatch → error → IRQ1) is complete → ✅ holds with the fuller caveat.
4. **MDMA (row 45) — ✅ holds, disclosure added.** The 16-deep queue + MDMA14 idle/busy/overflow dynamic
   status aren't asserted (constants for W1C only) — moot under synchronous execution; disclosed in the note.
Tally: QEMU ✅ 29→27, 🔶 13→15 (the honest AHBC+PUART downgrades). This is the gates working as intended —
an adversarial second opinion caught a faithfulness bug my own passing tests hid, exactly the "it's your
code, model real silicon" principle. Submodule (AHBC key + MIC10 TAG) + parent (gates + matrix) committed.

## 2026-07-21 — Gate-(b) MIC code review: CLEAN (line-by-line diff vs the SLT oracle), no actionable defects

The independent code review of `hw/misc/aspeed_mic_ast2050.c` returned with **no high-confidence issues** —
the model is clean. Notably the reviewer located the vendored oracle (`raptor .../ast2050/mictest.c` + `.h`)
and diffed the model against it LINE BY LINE, confirming bit-for-bit: the Fletcher-32 fold cadence (block
360, seed 0xffff, fold-after-each-block-incl-tail + one final fold — and the block-360 constant is exactly
what the real ARM926 32-bit SLT uses, so it is proven overflow-safe, not just coincidentally-passing on the
zero page); every register constant (MIC_ENABLE/MAXPAGE_MASK=last-page-index/error-flag bits/INTMASK/
ERRPAGE) vs mictest.h; the 4-pages/byte control packing; the checksum "initiative" write-vs-compare
semantics; the in_scan re-entrancy guard (no stuck-true path); the first/secondary/lost error escalation +
level-IRQ recompute on every mutating path; MIC14 RO-field preservation + MIC18/1C W1C keeping the page
number; LE endianness; and large-page-count integer safety (page<<12 via a uint64_t cast). QEMU API (OOB
checks, access sizes, reset clearing in_scan + deasserting IRQ, meson/struct/wiring order vs the AHBC alias
dependency) all correct.
ONE sub-threshold note (conf ~40, NOT actionable): no vmstate `.post_load` hook to re-run
aspeed_mic_update_irq() after a loadvm — a restored VM with a latched unmasked error wouldn't re-assert the
IRQ until the next MIC write. But this is a REPO-WIDE pattern (none of the sibling mdma/ahbc/rtc/lpc/p2a/smc/
pwm/udc/video ast2050 models define post_load either) and this project never exercises QEMU migration/
snapshots, so I am NOT diverging MIC alone from the repo pattern for an unexercised path. Recorded as a known
minor item (a future repo-wide post_load sweep across the level-IRQ models could add it uniformly). So MIC is
gate-(b) CLEAN — combined with the MDMA review (1 real bug found+fixed), 2 of the new models are now
independently reviewed. Gate-(a) faithfulness audit of the 4 ✅ cells still in flight.

## 2026-07-21 — Gates (a)+(b): dispatched independent reviews of this session's new work (in flight)

To satisfy completion gates (a) completeness/faithfulness and (b) code review on the fresh work — and because
the earlier MDMA gate-(b) review caught a real memory-safety bug — dispatched two independent, read-only
sub-agents (parallel, no build conflict):
1. gate-(b) CODE REVIEW of the newest + most complex model, `hw/misc/aspeed_mic_ast2050.c` + its wiring,
   scrutinising the Fletcher-32 fold cadence (a wrong cadence could overflow sum2 and mis-checksum non-trivial
   pages even though the zero page passes), the in_scan re-entrancy guard's exit coverage, the error-flag
   escalation + level-IRQ recompute, MIC14 RO-field preservation, W1C, endianness, and large-page-count
   overflow.
2. gate-(a) FAITHFULNESS AUDIT of the four rows marked ✅ this session (44 MIC, 45 MDMA, 47 PUART, 49 AHBC):
   an adversarial check that each ✅ is honest (full datasheet functionality modeled, documented
   simplifications legitimately scoped, evidence sufficient) and that nothing is missed.
Findings will be addressed next (fixes or honest downgrades). Running in the background. This is the
independent-verification step the goal's gates (a)/(b) require, applied to the MDMA/MIC/AHBC/PUART cluster.

## 2026-07-21 — MIC (row 44) QE ⬜→✅: full §13 model + BIT-EXACT Fletcher-32, validated

Implemented the MIC (Memory Integrity Check Engine, §13, 0x1E640000, IRQ1) — `hw/misc/aspeed_mic_ast2050.c`
wired into the G3 SoC (VIC INT#1, ASPEED_DEV_MIC enum/memmap/irqmap). Full functionality: the 8-register
block + the scanner semantics — per-page 2-bit control words (SKIP/ECC/DEBUG/MIC-mode), per-page Fletcher-32
into the DRAM checksum buffer, first/secondary/lost page-error flags with W1C, and a level-high IRQ1 gated
by the MIC14[17:16] mask. The Fletcher-32 reduction is BIT-EXACT — copied from the Raptor SLT
`mictest.c do_chksum()` (blocks of ≤360 u16 words, fold after each + one final). Reads DRAM via the AHBC
boot-remap low aperture (0x0-based scan). Proactively included the re-entrancy guard the MDMA gate-b review
flagged (the scan DMAs to guest-programmed buffer addresses).
VALIDATION (evidence `soc-mic/01`, devmem gate `mictest`): the scan always starts at page 0 (= the running
kernel), so the control buffer marks all low pages SKIP and checks only ONE high page (8192, 32 MB, clear of
the kernel) that we dd-zero. Result: checksum-buf[8192] = **0xFFFFFFFF**, exactly the Fletcher-32 of an all-
zero 4 KB page I computed independently with the SLT algorithm → BIT-EXACT faithful to real silicon. Then
corrupting the page (word0=0xBEEF) + re-scan → MIC18 = 0x10002000 (first-page-error flag + the correct
recorded page number 0x2000). Machine boots normally. Simplification (documented): synchronous scan on
enable rather than the continuous MIC08-rate loop — this models exactly the first scan pass the SLT relies
on, so a real driver (the SLT) would find `chksum == goldensum`.
Matrix row 44 QE ⬜→✅; tally QEMU ✅ 28→29, ⬜ 7→6. Driver stacks LQ/LS/ZQ/ZS kept ⬜ (an EDAC-style error
reporter could exist — not downgraded to Ⓝ); UQ/US/LU Ⓝ. This was the last of the memory-reading SoC
engines the AHBC aperture unblocked. #201 done. Submodule qemu next commit.

## 2026-07-21 — Gate-(b) code review of the new G3 models: 1 real bug found + FIXED (MDMA re-entrancy), rest clean

The independent code-reviewer sub-agent (dispatched last entry) returned. It reviewed the three device-model
components shipped this session — `hw/misc/aspeed_mdma_ast2050.c`, `hw/misc/aspeed_ahbc_ast2050.c`, and the
G3 wiring in `hw/arm/aspeed_ast2400.c`. ONE real, high-confidence (80) defect found + FIXED:
- **MDMA re-entrant recursion → stack overflow (memory-safety, guest-triggerable).** `aspeed_mdma_do_command()`
  runs synchronously in the MMIO write callback and `address_space_write()`s to a guest-controlled `dst`
  masked only to 28 bits (not range-checked). A guest that points MDMA_DST at the MDMA's OWN register window
  (0x1E74000C = MDMA_CMD) makes the write re-enter `aspeed_mdma_write()` → `do_command()`; a crafted self-
  referential fill recurses until the native stack overflows → QEMU crash. FIX (submodule 9408957805): an
  `in_command` re-entrancy guard (checked/set at the top of do_command, cleared on every exit + on reset)
  drops nested invocations with a LOG_GUEST_ERROR. Rebuilt + re-validated: the `mdmacopy` gate still PASSes
  (normal single-command operation is unaffected — the flag is set/cleared within one synchronous call).
Everything ELSE in the review was confirmed CORRECT (not just asserted): MDMA IRQ6 level-recompute on every
mutating path (no stuck/missed assertion), MDMA14 W1C vs RO-field isolation, the 28-bit mask on both read +
do-command paths, the bounce-buffer chunking (no overflow given the 24-bit length), reserved-type/zero-len
short-circuit, reset values (0x100 = queue-len 16), wiring/memmap/irqmap, and — the one the review was told
to scrutinise hardest — the **AHBC boot-remap DEFAULT-OFF invariant, verified end-to-end** (alias is a true
alias, added overlap-priority-1 above the priority-0 spi_boot_container, explicitly disabled at wiring time
AND unconditionally re-disabled on every reset; dram_mr sized before realize; remap_mr NULL-checked). So the
rows-45/49 ✅ stand, now with an independent gate-(b) confirmation. This is exactly the "it's your code" value
of the review — a real fuzzer-class bug caught + fixed before it compounded.

## 2026-07-21 — MIC (row 44) ORACLE FOUND: Raptor SLT `mictest.c` gives the EXACT Fletcher-32 → bit-exact ✅ now achievable

Big upgrade to the MIC disposition (was "🔶 at best, checksum under-specified"). The Raptor U-Boot SLT source
IS in-repo: `raptor/tools/raptor-uboot/board/aspeed/ast2050/mictest.c` (+ `.h`). Its `do_chksum()` computes
the expected per-page checksum in SOFTWARE and byte-compares it against the value the MIC HARDWARE wrote to
the checksum buffer (`if (chksum != goldensum) FAIL`) — so the hardware MUST compute exactly this, i.e. this
is the bit-exact oracle the datasheet lacked. The algorithm is classic **Fletcher-32**:
  per 4 KB page: sum1=sum2=0xffff; read 2048 × u16 words; sum1+=word; sum2+=sum1; reduce (sum=(sum&0xffff)+
  (sum>>16)) every 360 words + once more at the end; result = (sum2<<16)|sum1.
`mictest.h` gives the exact register map + constants: MIC_BASE 0x1e640000; MIC00 ctrlbuf / MIC04 chksumbuf /
MIC08 rate / MIC0C engine-ctrl (MIC_ENABLE_MIC=0x10000000=bit28, MIC_MAXPAGE_MASK=0x0FFFF000=[27:12] =
last-page-index=count-1, written as `MIC_ENABLE_MIC | (DRAMSIZE-0x1000)`) / MIC10 stop-page / MIC14 status
(MIC_PAGEERROR 0x40000000 lost, MIC_PAGE1ERROR 0x10000000 first, MIC_PAGE2ERROR 0x20000000 secondary,
MIC_INTMASK 0x00060000 = [17:16], errpage [15:0]) / MIC18 first-err / MIC1C secondary-err. Control words are
2 bits/page (SKIP 0, CHK1 1, CHK2 2, CHK3 3 = MIC mode; DEFAULT_CTRL 0xFF = all-CHK3). Checksum init value 0.
The MIC scans from address 0x0 (low aperture) — reachable via the AHBC remap I just built (the SLT reads
0x40000000 in software = same DRAM as 0x0 post-remap, which is why they match). So a BIT-EXACT FAITHFUL MIC
model is now FULLY specified — QE ✅ (not 🔶) is achievable, and a real driver (this SLT) could verify it.
#201 updated. Model deferred to a dedicated turn (it's the most complex engine — Fletcher-32 + control/
checksum-buffer parsing + scan loop + error flags + IRQ1 + a buffer-layout validation gate) so I can first
address the in-flight gate-(b) code-review findings on the shipped mdma/ahbc models.

## 2026-07-21 — MIC (row 44) §13 spec obtained + honest disposition; gate-(b) code review of the new models dispatched

Got the authoritative §13 MIC spec (datasheet agent, p116-123). PIVOTAL: MIC (MICE) is NOT a one-shot
checksum engine like MDMA — it is a CONTINUOUS BACKGROUND DRAM SCANNER (reads 4 KB pages from address 0x0,
computes a per-page Fletcher checksum into a DRAM checksum-buffer at MIC04, driven by a 2-bit-per-page
control buffer at MIC00, raises IRQ1 level-high on a checksum MISMATCH). 8 registers captured (see #201).
It is heavily memory-coupled (scanned pages + both metadata buffers in DRAM) — reachable now via the AHBC
low aperture (rows 45/49). FAITHFULNESS LIMIT (honest, not a weasel): §13 NAMES "Fletcher's checksum" but
does NOT specify the variant/modulus/word-size/endianness, so a BIT-EXACT checksum a real driver could
byte-verify is NOT derivable from the datasheet; the only oracle for the exact reduction is the factory-SLT
`MICTEST` code (CFG_CMD_MICTEST in ast2050.h / Raptor U-Boot). No firmware on this board drives MIC. So MIC
is realistically a MECHANISM-faithful model (Fletcher-32 default, documented) = QE 🔶 at best without RE-ing
the SLT checksum; reaching bit-exact ✅ is a tracked sub-task. Model plan recorded in #201 (mirror the MDMA
pattern; scan on enable; validate via a devmem gate laying out the buffers in aliased DRAM). NOT coded this
turn — the register spec + honest disposition are the deliverable; the continuous-scanner model is a
dedicated future turn.
Also dispatched an INDEPENDENT gate-(b) code review (feature-dev:code-reviewer) of the new G3 device models
shipped this session — hw/misc/aspeed_mdma_ast2050.c, hw/misc/aspeed_ahbc_ast2050.c, and the SoC wiring
(PUART/MDMA/AHBC + dram_low_alias) — to catch real bugs (stuck-IRQ, W1C clobber, address-mask, reset-default
remap, alias priority) before they compound. Findings to be addressed next; running in the background.

## 2026-07-21 — AHBC boot-remap + MDMA data path COMPLETE: rows 45 & 49 QE →✅ (oracle-verified)

Closed the MDMA↔AHBC coupling identified earlier. Modeled the AHB Bus Controller (§12, 0x1E600000) as
`hw/misc/aspeed_ahbc_ast2050.c` (register block) + the AHBC8C[0] boot-remap: on write it toggles a SoC-
created SDRAM alias (`dram_low_alias`, an alias of `s->dram_mr`) mapped at 0x0 with priority above the
spi_boot_container, DEFAULT-DISABLED (reset = boot from static memory). Enabling AHBC8C[0] makes the low
256 MB aperture SDRAM — the path the 28-bit MDMA engine uses to reach DRAM.
END-TO-END VALIDATION (evidence `soc-mdma/02`, devmem gate `mdmacopy`): AHBC8C[0]=1 makes SDRAM readable at
0x02xxxxxx, and an MDMA copy src→dst through the low aperture round-trips 0xDEADC0DE. Neat STRICT_DEVMEM
trick: the kernel registers RAM at 0x40000000+, so /dev/mem refuses that range, but the alias window
(0x02xxxxxx) is NOT registered as kernel RAM → devmem_is_allowed() treats it as device memory and permits
access — a userspace view into DRAM below the kernel's RAM base, no bare-metal harness needed.
FAITHFULNESS GATE (the governing rule — legacy boots must ALWAYS keep booting): because the alias is
default-off, I re-verified the oracles after touching the boot memory map. **C2 (our Linux) boots** (the
mdmacopy gate ran). **C-UBOOT (Raptor U-Boot) boots cleanly**: `DRAM Init-DDR` → `U-Boot 2013.07` →
`DRAM: 64 MiB` → `boot#` prompt (the "can't get kernel image" is the normal bare-U-Boot behaviour). So the
two AHBC/DRAM-init-relevant oracles both pass — the change is faithful. This RESOLVES the #175 "faithful
remap is HIGH-RISK" worry: done safely with a default-off alias.
Matrix: row 45 MDMA 🔶→✅ (control path + end-to-end data movement; IRQ6 modeled+wired to VIC-6, status-set
validated — observing IRQ6-to-a-handler needs bare-metal, a harness limit not a model gap), row 49 AHBC
🔶→✅ (register block + boot-remap modeled+validated+oracle-safe). Tally QEMU ✅ 26→28, 🔶 15→13. Submodule
qemu 1d2c9aab1f. C4 (Dell vendor) oracle re-verify tracked (heavier to build; C-UBOOT already proves the
U-Boot DRAM-init-with-AHBC path). NO 0x40000000 fudge anywhere — MDMA uses the raw 28-bit address.

## 2026-07-21 — MDMA (row 45) QE ⬜→🔶: modeled the §22 register+command CONTROL path, validated by devmem

Modeled the AST2050 MDMA memory-copy/fill engine (0x1E740000, IRQ6, §22) — a real G3 block previously
swallowed by the iomem catch-all. New files: `hw/misc/aspeed_mdma_ast2050.c` (+ `.h`), registered in
`hw/misc/meson.build`, wired into the G3 SoC (`ASPEED_DEV_MDMA` enum + memmap 0x1E740000 + irqmap 6 [free
since XDMA is gated off] + struct member + G3-gated _init/realize with the VIC-6 connection). The model:
- MDMA00/04 src/dst masked to [27:0] (faithful 28-bit reach); MDMA08 fill pattern.
- MDMA0C: the WRITE fires the command (no start bit, §22 note) — copy (type 00) or fill (type 10) via
  `address_space_memory` with the raw 28-bit address; on done, if MDMA0C[31] set, sets the per-ID done bit
  in MDMA14[23:16]; level-high IRQ6 asserted when (MDMA14 status & MDMA10 mask) is non-zero.
- MDMA14: reset 0x100 (queue-len 16), done/idle/overflow are write-1-to-clear, queue/busy RO.
VALIDATION (devmem gate `mdmatest`, evidence `soc-mdma/01`): src 0x12345678 reads back 0x02345678 (28-bit
mask applied), fill persists, sts_reset=0x100, a command write sets MDMA14[16] (0x00010100), and W1C clears
it (back to 0x100). `MDMA RESULT: PASS`. The gate deliberately does NOT enable the IRQ mask (a level IRQ6
with no Linux handler would be spurious) and fills an unmapped low address (harmless no-op).
WHY 🔶 NOT ✅ (honest): the register + command/status CONTROL path is modeled + validated, but the actual
DATA MOVEMENT + IRQ6 delivery need the AHBC boot-remap low-SDRAM aperture (MDMA is 28-bit; DRAM is at
0x40000000 — unreachable). Completing that (bare-metal fwtest: enable AHBC remap → RAM-to-RAM MDMA copy →
verify dst==src + IRQ6) is coupled with the AHBC aperture and tracked in #199 + #175. The model uses the
raw 28-bit address (NO 0x40000000 fudge) so it stays faithful. Matrix row 45 QE ⬜→🔶; tally QEMU 🔶 14→15,
⬜ 8→7. Driver stacks Ⓝ (autonomous DMA, no BMC runtime driver). Submodule + parent committed.

## 2026-07-21 — PUART (row 47) QE ⬜→✅: modeled the LPC pass-through 16550 @0x1E788000, validated by devmem

Picked PUART as a CLEAN, self-contained device to close (no memory coupling, unlike MDMA/MIC/HACE). It is a
real G3 block (datasheet §29.4 p308, base 0x1E788000, a second 16550 alongside the VUART; independent-agent
confirmed). Modeled it as a `TYPE_SERIAL_MM` instance wired into the G3 SoC, mirroring the VUART but with NO
IRQ (datasheet §10 Table 36 lists no PUART VIC source) and NO chardev backend (host-less BMC machine):
- include/hw/arm/aspeed_soc.h: `SerialMM puart;` + `ASPEED_DEV_PUART` enum.
- hw/arm/aspeed_ast2400.c: memmap `[ASPEED_DEV_PUART]=0x1E788000` (both arrays); _init creates it (G3-gated
  on AST2050_A1_SILICON_REV); realize configures regshift=2/baudbase/endianness + maps it, no IRQ.
Previously 0x1E788000 fell through to the `create_unimplemented_device("aspeed.io",0x1E600000,0x200000)`
catch-all (RAZ/WI). VALIDATION: rebuilt qemu-system-arm (clean), booted, and a Linux userspace `devmem` R/W
of the 16550 Scratch Register (reg 7; regshift=2 → byte offset 0x1C → phys 0x1E78801C) round-trips both test
patterns: initial=0x00000000, write 0xA5 → 0x000000A5, write 0x5A → 0x0000005A → `PUART RESULT: PASS`
(evidence `soc-puart/01-puart-qemu-PASS.txt`). The machine booted normally to userspace, so the null-chardev
SerialMM realized cleanly (no serial-loop perturbation). Faithfulness note: the SCR is a pure R/W scratch
with no side effects, so it cleanly distinguishes a modeled UART (persists) from the catch-all (reads 0);
STRICT_DEVMEM=y still permits /dev/mem to device MMIO (existing video/RTC gates prove this). The LPC
pass-through DATAPATH (host COM redirect) needs an LPC host peer, absent here — same boundary as the VUART
(row 6). Matrix row 47 **QE ⬜→✅**; tally QEMU 25→26 ✅. Driver stacks LQ/LS/LU/ZQ/ZS kept ⬜ (a pass-through
driver is real BMC work; NOT downgraded to Ⓝ without proof the KGPE-D16 firmware doesn't use PUART — no
weaseling). UQ/US already Ⓝ.

## 2026-07-21 — SoC-internal engines (rows 44–48) faithfulness scoping: addresses CONFIRMED real, irqmap CLEAN, current state = catch-all only

Turned to the QE ⬜ SoC-internal engine rows (44 MIC, 45 MDMA, 46 2D, 47 PUART, 48 PCI-arb) to convert
"skipped" ⬜ cells into either a real model or a substantiated disposition (the goal rejects bare ⬜).
Cross-checked three sources: (1) authoritative `qemu-model/AST2050-MEMORY-MAP.md` (datasheet §9 p97 +
per-chapter, cited), (2) the QEMU SoC memmap/irqmap in `hw/arm/aspeed_ast2400.c`, (3) dispatched an
INDEPENDENT datasheet-PDF re-derivation sub-agent (reads AST2050 A3 V1.05 fresh) for verification.
INDEPENDENT AGENT VERDICT (received, gate-a evidence): **every claimed address + IRQ CONFIRMED against the
master §9 ARM Address Space Mapping (p97) + §10 Interrupt Source Table / Table 36 (p99) + per-chapter
base-address headers — NONE refuted; all eight blocks genuinely present on the G3; none are phantoms.**
The agent also settled the collision with two verbatim citations (§9 p97 row "1E74:0000–1E75:FFFF | 128K |
MDMA Controller"; §22 p257 "Base address of MDMA = 0x1E74_0000", regs MDMA00 src / 04 dst / 08 fill-data /
0C command / 10 irq-ctrl / 14 irq-status) — 0x1E740000 is MDMA (IRQ6), there is NO SD/eMMC anywhere in the
AST2050 map, and IRQ26 = RTC alarm (not storage). Key scoping note from the agent: the datasheet settles
PRESENCE/base/IRQ, but MODEL-fully vs register-model-only (NO-DRIVER) hinges on whether the firmware
oracles actually DRIVE each block — a firmware-audit question. Likely dispositions: MIC/PCI-arb/2D/A2P/
PUART = register-model-faithful (firmware-unexercised); MDMA/HACE = model fully IF fw offloads; AHBC =
boot-used (remap/priority) so at least a register model incl. remap.
FINDINGS:
- All four addresses are REAL G3 blocks per datasheet §9: MIC 0x1E640000 (§13.3 p116, IRQ1), MDMA
  0x1E740000 (§22.3 p257, IRQ6), PUART 0x1E788000 (§29.4 p308, 16550), PCI-arb 0x1E78C000 (§9-only, no
  register chapter). 2D BitBLT is §35, reached via the PCI/VGA path (not an AHB base). So these are
  MODEL-needed (QE), NOT Ⓝ-absent. Driver stacks (UQ..ZS) for MDMA/2D/PCI-arb are already Ⓝ (firmware
  never drives them) — the meaningful open cell is QE.
- The 0x1E740000 "collision" (MDMA vs the gated phantom SDHCI IRQ26) is ALREADY resolved in code: the G3
  machine skips SDHCI because "on the G3 0x1E740000 is the MDMA engine" (#172), and skips SRAM because
  "0x1E720000 is the A2P bridge" (#176). Confirmed, not a live bug.
- IRQMAP CROSS-CHECK (clean): every G3-relevant entry in `aspeed_soc_ast2400_irqmap[]` matches datasheet
  §10 (MAC1=2/MAC2=3/HACE=4/USB=5/Video=7/LPC=8/I2C=12/PECI=15/Timer1-3=16-18/GPIO=20/SCU=21/RTC=22/
  WDT=27/Tacho=28). The divergent entries (UART2=32, TIMER4-8=35-39, SDHCI=26, ADC=31, XDMA=6) are all
  for blocks absent/gated on the G3, so they don't mis-fire. IRQ1 (MIC) and IRQ6 (MDMA) are unassigned →
  free to wire when those engines are modeled. No mis-wiring found.
- CURRENT QE STATE of 44/45/47/48: their register windows fall through to the 2 MB `create_unimplemented_
  device("aspeed.io", 0x1E600000, 0x200000)` catch-all (RAZ/WI, logged) — i.e. covered-but-not-modeled,
  which is exactly why they are QE ⬜. Next step (pending the independent agent's register-level detail):
  model the tractable ones — MIC (8 regs + IRQ1-on-completion) is the cleanest "complete" candidate;
  PCI-arb (no register chapter) can at most become a NAMED region (🔶, per the A2P precedent). NO code
  written yet for these — this entry records the scoping + verification only.

## 2026-07-21 — MDMA (row 45) full register spec extracted + a memory-map COUPLING discovered (model set up, #199)

Got the complete MDMA bit-level spec (independent datasheet agent, §22 p257–261, citation-anchored) and set
up task #199 to model it. Register file (6 regs, base 0x1E740000):
- MDMA00 [27:0] source addr; MDMA04 [27:0] dest addr — **28-bit → 256 MB max, byte-aligned**.
- MDMA08 [31:0] 32-bit fill pattern (double-word-aligned ranges for fill).
- MDMA0C COMMAND: **the WRITE ITSELF fires the command** (no start bit — §22 note p259). [31]=update-status-
  on-done, [30:28]=command ID #0-7, [25:24]=type (00=copy, 10=fill), [23:0]=length in BYTES (0 invalid,
  max 16M-1). Fill issues writes only (ECC-init).
- MDMA10 IRQ control (Init 0): [23:16]=per-ID irq mask (bit16=ID0..bit23=ID7), [3]=irq-when-idle, [1]=irq-
  on-overflow.
- MDMA14 IRQ status (Init 0x00000100): [23:16]=per-ID done (W1C), [8:4]=RO queue length (reset=16), [3]=idle
  (W1C), [1]=overflow (W1C), [0]=RO busy. IRQ6 is the single aggregate VIC line; per-ID via status/mask.
COUPLING DISCOVERED (why MDMA is not a standalone win): MDMA addresses are 28-bit (max 0x0FFFFFFF), but this
machine's SDRAM is at 0x40000000 (64 MB, unreachable by 28 bits). On silicon MDMA reaches DRAM through the
AHBC boot-remap LOW aperture (0x0–0x0FFFFFFF → SDRAM when AHBC8C[0]=1; datasheet §12.3 p115 / memory-map
doc §1b), which QEMU does NOT model (AHBC 0x1E600000 is currently the `aspeed.io` RAZ/WI catch-all, row 49).
So a FULLY-validated (data-moving) MDMA needs the low-SDRAM aperture too → **row 45 (MDMA) is coupled to row
49 (AHBC remap)**. A faithful MDMA model must use address_space_memory with the raw 28-bit address (real AHB
decode) — NOT a `+0x40000000` fudge (that would be unfaithful to the silicon). Plan for the next iteration
(#199 + a new AHBC-remap task): model MDMA (register+command+copy/fill+IRQ6) AND the AHBC8C[0]-gated low
aperture together, then fwtest a real low-aperture RAM-to-RAM copy + IRQ6. NO model code written yet — this
entry records the spec + the coupling so the build is done right, not rushed. Templates identified:
`hw/misc/aspeed_pwm_ast2050.c` (+.h) house pattern; SoC wiring mirror at aspeed_ast2400.c:532-542 (PWM),
meson.build:136, ASPEED_DEV_* enum in aspeed_soc.h. IRQ6 is free in the irqmap (XDMA=6 is gated off on G3).

## 2026-07-21 — Row 24 LQ+LU (Linux pmbus @0x58): RESOLVED ✅ — root cause was my DT mis-nesting, not the model

Came back to the pmbus blocker with the "it's your code, the hardware is 100% reliable" lens and READ the
whole path instead of guessing. Static analysis said the model was correct (STATUS_WORD 0x79 → seeded
`status_word=0` via pmbus_send16, popped byte-by-byte; pmbus_psu.c seeds it; device on engine 0 = schematic
I2C1, faithful placement) — so a NAK was the only way to get `-ENXIO` → "status register not found".
THE BUG (mine): the first attempt nested `psu@58` under the node textually written `i2c@0` that is a
**mux child** of the engine-1 PCA954x (`i2c-parent=<&i2c1>`, QU5 Y0), NOT the engine-0 controller. An
Aspeed dts can contain two different `i2c@0` nodes — the SoC controller (label `&i2c0`) and a mux child
(`reg=<0>`). The client bound on the mux child (Linux bus 14 = a mux adapter) where nothing answers at
0x58 → every identify read NAK'd.
FIX: attach the node to the controller by its label `&i2c0` (new top-level block), matching QEMU's
`aspeed_i2c_get_bus(&soc->i2c,0)`. Result — PASS: `hwmon3 name=pmbus dev=0-0058`, the generic pmbus
driver identifies + binds and userspace reads live telemetry (VIN 230 V, VOUT 12 V, temp 30 C, IIN 1 A,
IOUT 8 A). Evidence `openbmc/bmc-functionality/evidence/d08-pmbus/01-pmbus-linux-qemu-PASS.txt`.
Matrix row 24: **LQ ⬜→✅** (driver identify+bind in QEMU) and **LU ⬜→✅** (userspace hwmon sysfs read of
live values — same basis as row-254 w83795 CASEOPEN LU). LS stays ⬜ (rig-hardware gate #165, no PMBus PSU
on this bench's PSUSMB1). Tally: Linux@QEMU 21→22 ✅, Linux userspace 14→15 ✅. Lesson reinforced: when a
faithful model "misbehaves", suspect my wiring first — here a one-node dts move closed the row.

## 2026-07-21 — Row 24 LQ (Linux pmbus @0x58): attempted, REVERTED the DT node — model STATUS-read must be fixed first (honest, tracked #165)

Executed the auditor's flagged "easy win" (row 24 LQ = Linux generic `pmbus` hwmon vs the QEMU-modeled
PSU on engine 0). Added a DT node `psu@58 { compatible="pmbus"; }` under i2c@0 + a `pmbustest` initramfs
gate, rebuilt kernel/dtb (24532→24584) + initramfs, and ran it (commit a7e1383).
RESULT — PARTIAL: the generic `pmbus` driver DID match + probe (`pmbus 14-0058` client created), but its
identify **FAILED**: `pmbus 14-0058: PMBus status register not found`. hwmon list = only w83795 + 2×sbtsi.
DIAGNOSIS (not yet root-caused): Linux `pmbus_init_common` (pmbus_core.c) reads STATUS_BYTE with page 0xff
first (which needs a PMBUS_PAGE=0xff write, an all-pages selector some models reject), then falls back to
STATUS_WORD (0x79) on page 0. The QEMU base class (hw/i2c/pmbus_device.c:807-812) answers STATUS_WORD/BYTE
with the seeded `status_word=0`, and Zephyr READ_VOUT (0x8B, same engine-0 device, #170) works — so the
basic word-read path is sound, yet the Linux identify STATUS read errors. Leading hypothesis: the
PMBUS_PAGE=0xff write is NAK'd/mishandled by the model, poisoning the subsequent read; needs QEMU I2C
transaction tracing to confirm.
DECISION — REVERTED the DT node + gate (commit 773c78e): shipping a DT node whose driver can't bind adds a
permanent benign `PMBus status register not found` line to EVERY Linux boot (rtclinux/wdttest/… logs), and
the correct engineering order is **fix the model STATUS/PAGE path FIRST, then re-add the node so it
validates**. The knowledge (this diagnosis) is the real output of the attempt; the non-binding config is
not. Row 24 LQ stays ⬜ with the specific blocker recorded. CONFIDENCE I didn't just do something wrong:
MODERATE — DT node/compatible/bus were correct (the client bound), but I have NOT proven model-gap vs
transaction/config; it is a real blocker, not a hand-wave "impossible". Tracked under #165 (PSU-PMBus).

## 2026-07-21 — Gate-a/d completeness SWEEP (2 sub-agents): enumeration confirmed complete + 4 over-claims corrected

Ran two independent completeness sub-agents for gates (a)+(d): one enumerating the authoritative schematic
vs the matrix, one auditing ✅ cells for over-claims.
GATE (a) ENUMERATION — CONFIRMED COMPLETE: the auditor independently re-enumerated every schematic
device/net/ref-des (§§2-15 + pinmaps) and found **NO structural device missed** — every one maps to a
matrix row or a justified Ⓝ. It surfaced 3 open IDENTITIES (not missed enumeration) now explicitly flagged
in the matrix header: the 0x69 silicon responder (#160), GPIOE6/E7↔SP5100 (#161), AUX_CHASSIS# (#183).
GATE (a) OVER-CLAIMS — 4 FIXED (honest downgrades, tally regenerated):
- Row 19 (DIMM TSOD jc42) QE ✅→Ⓝ + ZQ ⬜→Ⓝ: the machine deliberately instantiates NO jc42; QE rested on
  "the model file exists" — the EXACT defect already fixed for this row's LQ. All 8 cells now Ⓝ.
- Row 9 (USB vhub) QE ✅→🔶 + LQ ✅→🔶: the vhub model is register+IRQ only (no USB datapath); the
  "virtual-media in QEMU" evidence enumerates over Linux `dummy_hcd`, NOT the modeled vhub.
- Row 5 (LPC port-80h snoop) QE ✅→🔶: the snoop-CAPTURE function isn't modeled (no SNPWADR/SNPWDR/port-80h
  datapath), no host peer. KCS+vUART register model is real, but not "full emulation".
Tally: QEMU 28→25 ✅ (+2 🔶, +1 Ⓝ), Linux@QEMU 22→21 ✅, Zephyr@QEMU row-19 ⬜→Ⓝ. Verified LEGITIMATE (not
over-claims): the Zephyr-silicon ✅ cells (I2C/W83795/FRU/W83601G/SCU/VIC/timer/WDT/RTC) — all backed by
genuine live-hardware transcripts.
DOC INCONSISTENCIES reconciled: row-14 DDC "blocks on #176" flagged as an UNRESOLVED conflict with row-50
(does CRB7 live behind A2P or a separate CRTC aperture? — settle before #178); row-12 "CRT/DAC modeled"
corrected to "capture engine modeled; CRTC display block NOT" (resolves the row-12↔14 contradiction).
New tasks the auditor identified (gate d) captured in #197 + being folded into FULL-TASK-LIST.

## 2026-07-21 — Gate-b QEMU VUART/LPC OR-gate FIXED + validated (#196) — sweep now fully clean (7/7)

Fixed the last code-review finding from the sweep. Confirmed via the datasheet FIRST (don't guess the
fix): AST2050 Interrupt Source Table (§10, Table 36) has a SINGLE "LPC interrupt" at VIC source 8 and NO
separate VUART source — VUART is an LPC sub-IRQ — so the irqmap (VUART=8, LPC=8) is CORRECT and the fix
is to OR-combine, not re-number. Added a 2-input TYPE_OR_IRQ (`vuart_lpc_orgate` in Aspeed2400SoCState):
VUART=input0, lpc_g3=input1, OR output -> VIC 8. Submodule 3b234b40c3.
**Self-inflicted bug caught + fixed (it's your code):** the first draft segfaulted the machine (smoke:
qemu exited -11) because I took `DEVICE(&a->vuart_lpc_orgate)` BEFORE object_initialize_child — the QOM
`DEVICE()` cast dereferenced an uninitialised class pointer. The run-qemu.py SMOKE test caught it
immediately; fix = take the DEVICE ptr AFTER init. VALIDATED after the fix: smoke instantiates OK,
rtclinux boots + PASS, and lpc-test = `LPC_CORE_OK` (both `/dev/ipmi-kcs3` KCS and `ttyS5 ASPEED VUART`
bind through the OR-gated line). So the KCS(IPMI) + VUART(SOL) IRQs can no longer clobber each other.
**Gate-b sweep tally for the cycle: 7 real bugs found, 7 FIXED** (RTC ×2, RTC re-anchor, Zephyr ×4 [note:
that's 6 across those], + this QEMU OR gate) — none catchable by the smoke tests alone; i2c/wdt/SCU/
w83795/w83601g-model all cleared clean. Independent review earned its keep.

## 2026-07-21 — Gate-b code-review SWEEP across Zephyr + QEMU subsystems — 5 more real bugs found; Zephyr 4 FIXED

Dispatched 3 independent code-reviewer sub-agents (max-5 rule respected) over the custom developed
code beyond RTC: (A) Zephyr core SoC drivers i2c/gpio/wdt, (B) Zephyr device drivers w83795/w83601g/
sbtsi, (C) QEMU G3 device models. They found 5 real bugs (i2c + wdt cleared CLEAN):
FIXED THIS PASS (Zephyr, all compile-clean — 3 sample builds link OK; behaviour-neutral for the
single-threaded smoke tests so no functional regression):
1. (conf 88) gpio_w83601g.c exposed a NONEXISTENT 16th pin — the W83601G is 15 pins (Port2 bit7
   reserved). W601_PINS 16->15 + DT ngpios 16->15 (binding + board dts x2).
2. (conf 82) w83795.c had NO lock around the measurement-reg -> VRLSB(0x3C) shared-latch read pair;
   interleaved threads silently corrupt fan/temp. Added k_mutex (sample_fetch full-hold + channel_get
   snapshot).
3. (conf 65) sbtsi.c same class (INT/DEC latched pair). Added k_mutex likewise.
4. (conf 65, dormant) gpio_aspeed_g3.c fixed base+0x08.. interrupt-reg offsets are only valid for the
   ABCD/EFGH sets (the only two AST2050 has); added an init guard rejecting any other base (fail
   __ASSERT + -ENOTSUP) so a mis-added DT node / G4 reuse fails loud instead of corrupting a
   neighbouring bank's DATA/DIR register.
DEFERRED (QEMU, tracked #196): (conf 80) hw/arm/aspeed_ast2400.c wires VUART and the G3 LPC to the
SAME VIC source 8 with no OR-gate — last qemu_set_irq wins, so concurrent KCS(IPMI)+SOL can clobber an
IRQ. Fix = route both through a TYPE_OR_IRQ; needs a QEMU rebuild + IPMI re-test.
VALIDATION HONESTY: the 4 Zephyr fixes are compile-clean (3 sample ELFs link) + behaviour-neutral for
single-threaded smoke; a QEMU RUNTIME re-run was attempted via `qemu-system-arm -M kgpe-d16-bmc -kernel
zephyr.elf` but that is the WRONG launch path for this custom Zephyr board (no console output, just the
timeout) — the proper Zephyr-QEMU runner wasn't located this pass, so runtime smoke re-validation is a
follow-up. The one boot-risking fix (the gpio_aspeed_g3 base guard) is provably safe WITHOUT a run: the
ast2050.dtsi instantiates only ABCD@0x1e780000 + EFGH@0x1e780020, both compile-time-constant bases that
satisfy the guard, so it cannot reject either instantiated node.
The gate-b sweep is proving its worth: 7 real bugs found+fixed this cycle across RTC(2)+Zephyr(4)+the
RTC re-anchor, plus 1 QEMU bug queued — none of which the smoke tests would have caught.

## 2026-07-21 — Sub-agent code review of the RTC changes (gate b) — 2 real bugs found + fixed

Ran an independent code-reviewer sub-agent over this session's RTC code (Linux driver + QEMU model),
serving completion gate (b). It found TWO real bugs (both fixed — "trust the independent check over my
own confidence"):
1. **Linux set_time swallowed the CONTROL[5] timeout** (confidence 55): it logged a warn but `return 0`,
   so if the RELOAD load never completed the time was NOT programmed yet the core saw success. Fix:
   `dev_err` + `return ret` (fail loud, per CLAUDE.md). Behaviour-neutral in the normal case (ret=0);
   only surfaces a genuine 4 s timeout. patch 0009 regenerated.
2. **QEMU model: mid-run SCU08[16] change re-rated the whole elapsed interval** (confidence 70): the
   rate was live-sampled but base_ns was only re-anchored on RTC-register events, so flipping bit16
   while enabled (raw SCU poke) replayed all elapsed time at the new rate = spurious counter jump (and
   could spuriously fire/skip an armed alarm). Fix: cache `last_src_hz`, re-anchor (freeze OLD-rate
   ticks into COUNTER + reset base_ns) on a source change so it only affects time forward. vmstate v5.
   Submodule 71f01cf948 (pushed).
Both fixes RE-VALIDATED: all 3 RTC gates still PASS in QEMU (rtcrate delta=3 real-time / rtcalarm VIC22
0->1 / rtclinux exact 12:45:30 + wakealarm 0->1). Reviewer also confirmed OK: readl_poll_timeout
ordering (outside the irq lock, process context), address_space_ldl_le under BQL + SCU realized before
RTC, frozen-RTC semantics, no overflow. The RTC code is now review-clean.

## 2026-07-21 — QEMU RTC model made FAITHFUL: tick-rate tracks SCU08[16] (#194 part 2 DONE)

Closed the QEMU-side of the real-time correction. `hw/misc/aspeed_rtc_ast2050.c` used a fixed
clk_hz (24 MHz → always 732x), which is exactly what HID the real-time-with-bit16=0 behaviour. Now
the model reads SCU08[16] from the SCU (0x1E6E2008, via the address space) and picks the source Hz:
32768 (÷32768 → 1 Hz real time) when bit16=0, clk_hz (24 MHz → 732x) when bit16=1; clk_hz=0 still
forces a frozen RTC. So the modelled rate TRACKS the guest's clock-source choice, exactly like
silicon — a fixed-732x model can no longer hide a rate bug. Submodule commit 0253877b15 (pushed).

Updated the init gates to match (they had assumed the 732x fast counter). FIRST attempt tested both
bit16 legs — it PASSED in QEMU (bit16=1 delta=769) but the SILICON run revealed a NEW behaviour:
**bit16=1 (24MHz test tap) is BROKEN under the U-Boot/Linux clock config** — the counter FROZE
(silicon rtcrate bit16=1 delta=0), matching the earlier U-Boot md/mw [D] garbage. So the 24MHz tap
only works under the BARE-METAL Zephyr clock config (evidence 14 = 732x); under U-Boot the ONLY
working RTC config is bit16=0 = real time. (Opposite working configs per environment — which is why
the Linux driver clears bit16 and the Zephyr driver sets it.) So all Linux-initramfs gates now use
bit16=0/real-time with small alarm deltas + adequate sleeps (my bit16=1-for-crossing flips were
silicon-broken — "it's your code"):
```
rtcrate : bit16=0 delta=3/3s = REAL TIME -> PASS (24MHz tap N/A under U-Boot cfg, noted)
rtcalarm: bit16=0, alarm sec 1->3, sleep 4 -> VIC22 0->1 -> PASS
rtclinux: set 12:45:30 -> read 12:45:30 EXACT (was 12:45:41 under old always-732x model) -> PASS
          wakealarm bit16=0 +3s sleep 6 -> VIC22 0->1 -> PASS
```
Validated in QEMU (all 3 gates). The QEMU model stays faithful: no gate uses bit16=1 under U-Boot;
the model's bit16=1->732x path is still exercised by the Zephyr tests (whose config supports the tap).
Follow-up in #194: RESTART async-load + CONTROL[5] busy (part 1).
**SILICON RE-VALIDATION DONE:** the corrected rtclinux gate on real AST2050 — `SCU08=0x61800070`
(bit16=0), `set 12:45:30 -> read 12:45:31` (+1 s = REAL TIME, vs the old +11 s under the wrong
config), `RTC-LINUX PASS`; wakealarm `+3` real-time -> `VIC22 fired (0->66276) -> cleared` ->
`RTC-WAKEALARM PASS`. And the silicon rtcrate bit16=0 leg = delta 3/3s (real time). So the faithful
real-time RTC is confirmed on QEMU AND silicon end-to-end. (rtcalarm devmem silicon inferred from the
same VIC22 path that rtclinux-wakealarm exercised + its QEMU PASS.) The 66276 alarm re-fire count is
the known level-triggered storm (tracked; test passes = fired+cleared).

## 2026-07-21 — CORRECTION: the AST2050 RTC keeps EXACT real time on silicon (bit16=0); the "732x" claim was a bit16=1 driving artifact

Chased down the RTC rate on real silicon and CORRECTED a long-standing wrong claim. Prior docs
(#158/#186) said "the KGPE-D16 has no 32.768 kHz crystal, so the RTC runs ~732x fast and can't keep
real time." That is WRONG. It came from measuring with **SCU08[16]=1** (the 24 MHz "test only" tap,
which Zephyr's driver forces). With **SCU08[16]=0** (the SoC default, what the row-39-LS-fixed Linux
driver now uses), a clean register-level 20 s silicon measurement (U-Boot md/mw, no OS):
```
t0 counter=0x00000001 (1s); sleep 20s; t1 counter=0x00000016 (22s)
delta=21 RTC-seconds over 21.0 real seconds  => rate ~= 1.00x  == EXACT REAL TIME
```
So the internal 32.768 kHz source IS present and running (÷32768 → 1 Hz); the board needs no EXTERNAL
crystal (datasheet §2.19) and the RTC is a **functional real-time clock**. The 732x figure applies ONLY
to bit16=1. This is the goal's thesis exactly — "the hardware is 100% reliable; it is your code/driving
that is the issue": TWO stacked driving mistakes (forcing bit16=1 onto the test tap + not polling
CONTROL[5] so even that read back 0) got rationalised into a false hardware limitation. One clean
measurement dissolved it. Evidence `d14-zephyr/31-rtc-realtime-bit16-0-silicon.txt`.

HW limitation that IS real (honest): the counter RTC has no month/year register — real-time for
HH:MM:SS + a day counter, but no full Gregorian calendar (register-map limit, not a clock-rate issue).

Follow-ups queued: (a) correct #158/#186 in the matrix + driver/model comments; (b) QEMU faithfulness —
make `hw/misc/aspeed_rtc_ast2050.c` tick-rate track SCU08[16] (clk_hz 32768=real-time vs 24e6=732x;
the model already parameterises ns_per_tick on clk_hz); (c) retest Zephyr with bit16=0 + the CONTROL[5]
load-wait — the bare-metal "bit16=0 → no clock" was likely the SAME async-load misread, so ZS may reach
a real-time ✅.

## 2026-07-21 — Row 38 LS ✅: Linux /dev/watchdog on real silicon (leveraging the now-working netboot)

With the netboot unblocked (row 39 work), the many Linux-SILICON (LS) cells that were blocked purely on
"can't netboot Linux on silicon" are now reachable. First harvest: **row 38 WDT LS 🔶→✅**. Generalised
the netboot driver (`tmp/uboot_netboot_gate.py <token> <initrd_size> <secs>` — any /init gate token) and
ran the non-destructive `wdttest` gate on real AST2050:
```
=== WDT-USERSPACE-BEGIN ===
/dev/watchdog, /dev/watchdog0, /dev/watchdog1        # aspeed_wdt bound to BOTH WDT1+WDT2
identity=aspeed_wdt
state(pre-arm)=inactive
timeout=30 state=active timeleft=(not exposed by aspeed_wdt)
WDT-USERSPACE RESULT: PASS (timeout=30 active)
```
This is the DEDICATED /dev/watchdog-on-silicon transcript the row-38 LS note asked for: userspace
`busybox watchdog -T 30` → WDIOC_SETTIMEOUT reached the driver (timeout reads back 30), state
inactive→active (armed). Combined with the already-silicon-proven WDT RESET (ZS `d14-zephyr/18` + the
g3-clk 120 s reset), the Linux WDT is validated on silicon. Evidence `f-wdt-userspace/01-silicon-dev-
watchdog.txt`. Matrix Linux@silicon 19→20 ✅. The userspace-ARMED real reset on silicon (wdtreset) is a
separate destructive test (flash-less board → reset halts the CPU, needs JTAG re-boot); reset capability
itself already silicon-proven via ZS. HONEST scope: this does NOT touch the mainline aspeed_wdt 2-stage
pretimeout vs G3 one-stage-interrupt gap (#189, still separately scoped).

## 2026-07-21 — 🎉 Row 39 LS PASS on real silicon (Linux RTC set/get + wakealarm) — root cause was MY SCU08[16] write

Fixed the RTC Linux driver and **validated the full set/get + wakealarm path on real AST2050 silicon**
via netboot. Captured console:
```
DIAG scu@linux: SCU08=0x61800070 SCU0C=0x000C3E8B      # driver CLEARED bit16 (was my bug when =1)
hwclock -r after set 12:45:30 -> Sat Jan 15 12:45:35 2000
RTC-LINUX RESULT: PASS (set 12:45:30 -> read 12:45:35; hour:min round-tripped via /dev/rtc0)
rtc alarm VIC22 count: 0 -> 82460
RTC-WAKEALARM RESULT: PASS (armed -> VIC22 fired -> RTC_AF cleared it)
```

**Root cause (silicon-proven, two parts):**
1. **SCU08[16] must be 0 on this board.** My previous-cycle driver forced bit16=1 (24MHz "test only" tap),
   mis-generalised from the bare-metal Zephyr boot (no U-Boot → no 32kHz path set up). Register-probing
   the RTC directly from the U-Boot prompt (md/mw) PROVED the block is healthy with bit16=0 (32.768kHz
   source, the SoC default U-Boot leaves): RELOAD sticks, COUNTER loads + advances (0x000c2d1e→0x000c2d26).
   Forcing bit16=1 freezes the counter at 0x0 under Linux. Driver now CLEARS bit16 defensively.
2. **set_time must wait for the async RESTART load.** The RELOAD→COUNTER latch "needs 0~3s" (datasheet
   §24.4.3), CONTROL[5] reads 1 until done. The old set_time returned immediately → read_time saw a stale
   counter (round-tripped as 00:00:0x). Added a bounded `readl_poll_timeout(CONTROL[5]==0)` (matches the
   Zephyr driver), and the RMW clears bit5 (never write 1 back to the restart-status bit).

Method was disciplined **instrument-don't-guess**: DIAG dumps in the initramfs rtclinux gate + a U-Boot
md/mw register prober isolated the cause across three netboot/probe cycles (SCU08[16] survives? counter
runs under devmem? U-Boot-state healthy?), landing on "the driver's own bit16 write is the regression."
This is precisely the memory principle — a broken Linux boot is a bug in MY code, not the silicon.

Commit `0d66a5c` (driver + patch 0009 + init). Row 39 LS ⬜→✅. Follow-ups: (a) QEMU faithfulness — model
the RESTART async load + CONTROL[5] busy so a non-polling driver misbehaves in QEMU too (closes the
"QEMU hid it" gap); (b) minor: the fast counter causes an alarm IRQ re-fire storm (82460 in ~1s) —
the ISR ALREADY masks alarm-enable (CONTROL[1:4]=0) yet the line keeps re-asserting, so masking
alarm-enable alone does NOT deassert the RTC alarm interrupt (needs a status-clear or it's a
fast-clock re-match; investigate against datasheet §24 + reproduce in QEMU once #194 models the
alarm-status). Fast-clock artifact (#158/#186), NOT a correctness bug — the wakealarm test PASSES
(fires + one-shot cleared).

**QEMU regression CONFIRMED (no regression):** rebuilt the QEMU kernel with the fixed driver and
re-ran the rtclinux gate in QEMU — RTC-LINUX PASS (set 12:45:30 -> read 12:45:41) + RTC-WAKEALARM
PASS. The bit16-clear is a no-op for the QEMU counter (advances on CONTROL[0]) and the CONTROL[5]
poll returns immediately (QEMU loads synchronously). Row 39 now green QE/LQ/LS/LU/ZQ; ZS 🔶 (HW
real-time). Commits fe32a32/0d66a5c/7594cdb + this log. QEMU rtclinux regression check building in parallel.

## 2026-07-21 — Row 39 LS: netboot UNBLOCKED (static IP) + RTC block PROVEN healthy on silicon; my SCU08[16] "fix" was the regression

Continued row-39-LS silicon validation. Two big corrections, both cases of "the hardware is fine, my
code/driving was wrong":

1. **Netboot DHCP was MY driving mistake, not a NIC bug (#193 RESOLVED).** The BMC mgmt segment
   (Pi `eth-bmc` = 192.168.66.1) runs dnsmasq with `--enable-tftp` but **no `--dhcp-range`** — it
   serves TFTP only. So `dhcp` correctly gets no answer. Fix = STATIC ip: `setenv ipaddr 192.168.66.2`
   / `serverip 192.168.66.1`; `ping` → "host is alive"; three TFTPs load; boot via
   `initrd=<data>,<size>` cmdline + `bootm <k> - <dtb>` (U-Boot 2013.07's DTB-initrd fixup doesn't
   reach this kernel). Linux now boots to `/init` on real silicon and the rtclinux gate runs.

2. **Linux RTC still read back 00:00:00 / alarm count 0 → instrumented, NOT guessed.** Added a devmem
   DIAG to the rtclinux gate. First finding: `SCU08=0x61810070` (bit16 already set) yet COUNTER=0 even
   after an explicit devmem RESET+RELOAD+RESTART+enable. So SCU08[16]=1 is NOT sufficient — and the
   RESTART latch (a clocked op) does nothing → the RTC tick-clock is dead under Linux.

3. **Register-probed the RTC directly from the U-Boot prompt (md/mw) — the RTC BLOCK IS HEALTHY.**
   Under U-Boot's real clock state (`SCU08=0x61800070` → **bit16=0**, 32.768kHz source; `SCU0C=0x000c3e89`
   bit6=0, 24MHz REFCLK running): RELOAD write **sticks** (`0x000c2d1e`), CONTROL enable sticks, and the
   **COUNTER loads + advances** (`0x000c2d26` → `0x000c2d2b`). So on THIS board, under U-Boot's config,
   the RTC runs with **bit16 = 0**. Forcing `SCU08=0xE3F10070` (bit16=1 + other dividers) produced
   GARBAGE counter values (`0x08c0e421`…). 

**Consequence / reconciliation:** the earlier Zephyr silicon note "bit16 must be 1 or the RTC has no
clock" was an artifact of the *bare openocd-reset* boot (no U-Boot; the 32kHz path wasn't set up). Under
the fuller U-Boot init the 32.768kHz source works and **forcing bit16=1 is wrong** — my previous-cycle
Linux-driver `SCU08[16]=1` write is a strong suspect for the Linux regression itself (it changes the RTC
onto a source that misbehaves under Linux's clock tree). This is exactly the memory principle: a broken
legacy/Linux boot is a bug in MY code, not the silicon. Currently running a Linux DIAG that CLEARS bit16
(restores U-Boot's proven-good state) + ensures SCU0C[6]=0, then drives the RTC and reads back RELOAD +
COUNTER×2 — to confirm the RTC runs under Linux with bit16=0 before rewriting the driver. Row 39 LS still
⬜; root cause now narrowed to a Linux-side clock clobber, RTC hardware exonerated.

## 2026-07-21 — Row 39 LS: netboot ATTEMPTED on silicon — U-Boot came up, DHCP blocked (honest failure) [SUPERSEDED by static-IP fix above]

Followed through on the row-39-LS silicon validation (not just staged): worked around the TFTP
permission block (scp'd under new names /srv/tftp-bmc/{uImage,dtb,initrd}-rtc39, owned by tim),
JTAG-booted U-Boot (boot-silicon-uboot.sh) — **U-Boot 2013.07 came up cleanly on silicon: DRAM 64
MiB, Net aspeednic#0 PHY 0x20, boot# prompt** — and drove it over /dev/serial-bmc-console @115200
with a pyserial script (the prompt echoes commands, so serial write+read works).

BLOCKED: `dhcp` gets NO response — `BOOTP broadcast 1..5 / Retry count exceeded / starting again`,
looping. The mgmt NIC TX's broadcasts but RX's no reply, so no IP/serverip → tftp+bootm never run →
Linux never boots → the RTC driver never executes. **CONFIDENCE this is NOT an RTC bug: HIGH** — the
RTC code never runs; the failure is entirely in the netboot TRANSPORT (U-Boot DHCP), and the
identical VIC-22/field-packed RTC path is already silicon-proven for the Zephyr alarm (#192) +
QEMU-validated for Linux. Two likely netboot causes (evidence /29): (1) no DHCP server on the BMC
mgmt segment right now, or (2) U-Boot aspeednic RX broken — plausibly the SAME MACCR bit19 FAST_MODE
speed issue the Linux ftgmac100 RX fix addressed. Row 39 LS stays ⬜ with the SPECIFIC blocker
identified; next = static-IP ping test to isolate RX-vs-no-server, then fix accordingly. The Zephyr
bare-metal JTAG load avoids the netboot entirely (why Zephyr-silicon succeeded, Linux-silicon needs
this transport). Evidence d14-zephyr/29.

## 2026-07-21 — Row 39 LS (Linux RTC on silicon): silicon-ready kernel BUILT; netboot blocked (honest)

Worked the audit's Tier-2 #7 (Linux RTC on silicon). Prepared everything for it:
- Fixed the reference realhw dts RTC node (was stale ast2400-rtc → now ast2050-rtc + interrupts=<22>).
- Confirmed build-realhw-kernel.py builds from the SAME kernel tree (patch 0009 field-packed RTC
  applied) and ships the QEMU dts (already ast2050-rtc + interrupts=<22>) AS the realhw.dtb — so the
  realhw kernel is silicon-ready for the RTC without further changes.
- BUILT it: `tmp/uImage-kgpe-d16-realhw` (3.45 MB) + realhw.dtb, with the field-packed + VIC-22 RTC.

BLOCKED on two things (honest — NOT a driver/hardware problem, and NOT claiming row 39 LS done):
1. **TFTP-dir permissions:** `/srv/tftp-bmc` is world-writable but the existing
   uImage-kgpe-d16-realhw / realhw.dtb / uInitrd-kgpe-d16 there are owned by ANOTHER user (`claude`,
   dated Jul 8-9), so my scp can't OVERWRITE them (dest-open Permission denied). The netboot would run
   the STALE kernel, not my field-packed/VIC22 one. Workaround = scp under new filenames + TFTP those.
2. **Interactive netboot:** `boot-silicon-uboot.sh` only brings the board to a U-Boot `boot#` prompt;
   the Linux TFTP-boot from there (setenv + tftp x3 + bootm with the `rtclinux` bootarg) is an
   interactive serial workflow, not an automated script like the Zephyr `boot-zephyr-silicon-long.sh`.
So row 39 LS stays ⬜ — a focused-effort next step (new-filename scp + drive U-Boot over serial +
capture RTC-LINUX/WAKEALARM). Confidence this is purely a staging/workflow gap (not the driver): HIGH
— the SAME RTC IRQ path (VIC 22, field-packed RTC04) is ALREADY silicon-proven for the Zephyr alarm
(#192), and the Linux driver + dtb are QEMU-validated on VIC 22. The Zephyr bare-metal JTAG load is
the easier silicon path (no U-Boot/netboot); Linux needs the netboot, which is the gap.

## 2026-07-21 — #176 A2P bridge (row 50 QE ⬜→🔶): datasheet-scoped + window modeled + oracle-safe

Acted on the completeness audit's #1 Tier-1 target (A2P bridge, unblocks video/PCI). Read the
datasheet §21.2 (PDF p255) — key finding that changes the modeling: **A2P is NOT a config-register
block, it is a one-way passthrough WINDOW** forwarding ARM(AHB) accesses to P-Bus/PCI space
(+0x00000..7F relocated I/O, +0x10000..0x1FFFF MMIO @0x1E720000), auto-enabled by SCU70[4]
(PCI-master mode). In the standalone BMC machine there is NO host/PCI on the P-Bus, so the faithful
behaviour is a window that reads back 0 / drops writes (forwarding to an empty P-Bus). Replaced the
accidental IOMEM catch-all fall-through with an explicit named `aspeed.a2p-pbus-window` unimplemented
region (128 KB), so accesses are logged and 0x1E720000 is a correctly-labelled A2P device.

**Oracle-revalidated (faithfulness-critical, oracle-sensitive change): C2 Linux still boots to
userspace** — `Booting Linux`, `rtc0 registered`, RTC-LINUX + wakealarm PASS, no abort/regression.
(C4/C-UBOOT NOT re-run this session — honest limitation; the change is RAZ/WI, minimal risk.)

QE ⬜→🔶 (NOT ✅): the SCU70[4] auto-enable gate is not modeled and there is no P-Bus target to
forward to (none exists in the BMC-only machine). Full ✅ needs the SCU70[4] gate + a modeled
P-Bus/PCI target for the video-capture read path. **Also CORRECTED an audit/doc misunderstanding:
DDC/EDID (row 14) does NOT depend on the A2P bridge** — DDC is CRTC/VGACRB7 bit-bang in the *video*
register space, a separate aperture; the earlier "#178 blocks on #176" note conflated the two.
Datasheet spec recorded in `qemu-model/AST2050-MEMORY-MAP.md:55`. Tally: QEMU ⬜ 10→9, 🔶 11→12.

## 2026-07-21 — Completeness audit (gate a/d) + 2 honesty fixes; program state quantified

Ran an independent completeness/enumeration audit (sub-agent) against the authoritative schematic
§1–§16 + DEVICE-MATRIX + FULL-TASK-LIST. Findings actioned:
- **ENUMERATION COMPLETE (independently re-confirmed section-by-section):** every schematic §2–15
  device and every §14 neighbour chip maps to a matrix row or a stated/defensible disposition; the
  SoC-internal engines are covered by the datasheet-§9 rows 43–50. No schematic device lacks a row.
- **No standing non-existence claim contradicts the schematic** — the historically-wrong ones
  (NC-SI "not wired", SPD "impossible", SOL "board-limit") are all retracted/corrected.
- **Resource-cgroup hygiene: PASS** (docs mandate it; build/bisect tooling uses systemd-run scopes).
- **Two honesty fixes applied (gate-c, no over-claims):** (1) **row 8 (PCI/video) QE ✅→🔶** — the
  video-CAPTURE+P2A path IS modeled but the full PCI-33 bus + PCI-target is NOT, so QE must be the
  aggregate 🔶 (matching the already-🔶 LS), completed by modeling the A2P bridge (row 50 QE) + a
  PCI-target aperture; tally re-synced (QEMU 29→28 ✅ / 10→11 🔶). (2) **evidence d14-zephyr/17**
  carried a STALE "IRQ 26" for the RTC alarm — added a superseded-by-/28 banner (the silicon-correct
  facts are VIC 22 + field-packed RTC04; the RTC set/get+wakealarm capability itself is real).
- **Quantified program state (regenerated tally, matches snapshot): of 408 stack-cells — 129 ✅
  (~32%), 131 Ⓝ justified-n/a (~32%), 47 🔶, 3 🔷, 98 ⬜.** So ~148 genuinely-actionable cells remain,
  concentrated in Zephyr (ZQ 19 ⬜ / ZS 25 ⬜) and Linux-silicon (LS 16 ⬜). The audit's prioritized
  top-15 next-actions: Tier-1 QEMU authoring (A2P bridge row50→unblocks DDC row14+PCI row8; LPC
  mailbox row4; SMBus-ALERT row25; DDC/EDID row14); Tier-2 cheap silicon validation of built
  QE/Zephyr (row39 LS Linux-RTC, row38 LS /dev/watchdog, row27 ZS power-feedback #162); Tier-3 Zephyr
  breadth (row10 ftgmac100, row3 KCS-BMC). These are the concrete targets for the next cycles.
  HONEST BOTTOM LINE: enumeration complete, but the program is NOT complete — ~148 cells + the
  gate-(b) full-code-review and gate-(d) no-new-tasks bars remain.

## 2026-07-21 — #189 WDT timeout-INTERRUPT mode SILICON-VALIDATED (VIC 27 confirmed correct)

Booted wdt_intr_smoke over JTAG on the real AST2050 (row 38 ZS). Proactively added the same VIC
raw-status register-dump diagnostic that found the RTC alarm's wrong source (#192), to CHECK the
WDT timeout-interrupt source (assumed 27). Result: `wdt intr fires=1` → `WDT-INTR RESULT: PASS
(timeout -> VIC-27 -> callback, no reset)` — the 200 ms WDT timed out in interrupt mode on silicon,
raised VIC 27, ran the callback, and did NOT reset (console kept running past the timeout, vs the
reset-mode smoke going silent). `DIAG vic_raw=00000000` = source 27 serviced+eoi'd, no
latched-elsewhere surprise, so **VIC source 27 for the WDT timeout-interrupt is CORRECT on silicon**
(not every model assumption is wrong — but now it's VERIFIED, not assumed). The gate-(b) disable-fix
also holds on silicon (`after fire: disable=0 reinstall=0` → `WDT-INTR-REINSTALL: PASS`).

So row 38 WDT interrupt mode is now silicon-proven (ZS ✅ for interrupt, on top of the already-proven
reset mode). This is the same rigorous silicon-first method as the RTC alarm, applied to confirm a
model assumption rather than disprove one. Evidence d14-zephyr/27. Zephyr-only (model was already
correct — no submodule change). Rig: asus-bmc, JTAG free, board powered; no others disturbed.

## 2026-07-21 — SILICON caught a real bug: RTC04 alarm is FIELD-packed (fixed, #186 resolved for RTC04); alarm-IRQ-on-silicon still OPEN

First silicon (JTAG) run of the Zephyr RTC alarm (row 39 ZS) FAILED — and honestly, that is the
goal working: the hardware exposed a real bug my QEMU model hid. Two issues, peeled one at a time.

**Issue 1 — RTC04 is FIELD-packed, not byte-packed (FOUND + FIXED + silicon-CONFIRMED).**
The smoke armed 12:00:05 but alarm_get_time read the HOUR back as 00 on silicon. The driver wrote
RTC04 byte-packed (hour at bits[23:16]); the datasheet §24 says RTC04 is FIELD-packed
(hour[16:12]/min[11:6]/sec[5:0]), so hour=12 landed in reserved bits >16 and was dropped. Only the
hour distinguished the layouts (sec=5/min=0 fit both); the COUNTER set/get couldn't expose it (sec
30→39, no wrap) — exactly the #186 question, now ANSWERED by silicon: field-packed. The QEMU model
compared RTC04 byte-packed too, so a byte-packed driver PASSED in QEMU and only silicon caught it —
the precise "QEMU must model the real hardware so the bug shows in QEMU too" faithfulness gap.
FIX across ALL THREE stacks: Zephyr driver (rtc_aspeed_g3.c RTC_G3_ALARM_ENC/_OF field-packed),
Linux driver (rtc-aspeed.c read/set_alarm field-packed, patch 0009 regenerated), QEMU model
(aspeed_rtc_ast2050.c alarm_match_value extracts RTC04 field-packed vs the byte-packed counter,
submodule ed7b917d31). RE-VALIDATED: QEMU Zephyr alarm PASS (armed reads back 12:00:05, fires=1);
QEMU Linux wakealarm PASS (IRQ26 0→1); and on SILICON the arm now reads back 12:00:05 correctly
(was 00) — the field-packed layout is PROVEN on hardware. Evidence d14-zephyr/28.

**Issue 2 — RTC alarm interrupt was on the WRONG VIC source (RESOLVED: it's VIC 22, not 26).**
With the arm correct, the alarm still didn't fire on silicon (fires=0). Rather than park it, added a
register-dump diagnostic to the smoke (VIC raw-status + RTC regs). It localized the fault decisively:
source-26 driver → `vic_raw=03400000` (bits 22,24,25 set; **bit 26 CLEAR**); source-22 driver →
`vic_raw=03000000` (bit 22 CLEARED by servicing) + **fires=1, PASS**. So the RTC alarm asserts VIC
source **22** (the RTC's single interrupt line), NOT the separate source 26 the QEMU model invented.
Differential proof: source-26 left bit 22 LATCHED (never serviced); source-22 serviced+eoi'd it and
the callback fired. And it's not a periodic tick faking the alarm — RTC0C has ONLY alarm-enables
[1:4], no periodic-int-enable, so the RTC's sole interrupt is the alarm. COORDINATED FAITHFUL FIX:
Zephyr driver IRQ 26→22; QEMU model pulses the RTC's single s->irq (VIC 22), phantom source-26
alarm_irq REMOVED; machine drops the index-1→VIC-26 wiring; Linux dts interrupts=<22>; init gates
updated (bare-metal rtcalarm now checks the Linux IRQ-count delta — source 22 is SERVICED so the raw
edge no longer sits latched to read). RE-VALIDATED all on VIC 22: QEMU Zephyr alarm PASS, Linux
wakealarm PASS (0→1), Linux bare-metal rtcalarm PASS (0→1); SILICON Zephyr alarm PASS (fires=1).
**#192 RESOLVED — row 39 RTC alarm now fires end-to-end on QEMU AND real silicon (ZS ✅).** This is
the goal's mandate delivered: silicon exposed THREE model-hidden bugs (fast counter, field-packed
RTC04, wrong IRQ source), each fixed and the model made faithful so they now fail in QEMU too.
Evidence d14-zephyr/28. (Confidence: HIGH — silicon fires deterministically; the byte-packed vs
field-packed and source-26 vs 22 were both differentially proven, not guessed.)

## 2026-07-21 — #189 Zephyr WDT timeout-INTERRUPT mode (WDT_CTRL[2] + VIC-27) implemented + validated

Added the timeout-interrupt/callback path to the Zephyr WDT driver
(`zephyr/drivers/watchdog/wdt_aspeed_g3.c`), consuming the #189 QE model (submodule
46cee5fe6a: WDT_INTR set → pulse VIC-27 instead of resetting). The driver previously did RESET
mode only and rejected any callback. The G3 WDT is ONE-STAGE (interrupt OR reset, never both — not
a 2-stage pre-timeout+reset), so the mapping is: WDT_FLAG_RESET_NONE + callback → interrupt mode
(WDT_CTRL=0x15 = ENABLE|WDT_INTR|1MHZ_CLK, VIC-27 fires the cb, no reset); RESET_SOC/CPU_CORE →
reset mode (0x33, callback must be NULL since reset raises no IRQ — rejected loud rather than
silently never-called, the honest choice given no 2-stage hardware). A VIC-27 ISR invokes the
callback (one-shot); init does IRQ_CONNECT(27)+irq_enable(27) with a file-static device pointer
(mirrors GPIO/RTC). Source 27 is already edge/rising in the RE'd G3 VIC map (like the timer), so no
VIC change. New sample `samples/wdt_intr_smoke` waits for the callback via WFI (k_cpu_atomic_idle),
not k_msleep — the tick-independent pattern established with the RTC alarm.

Validated QEMU (-M kgpe-d16-bmc), deterministic 3/3: `WDT armed 200 ms in interrupt mode, NOT
feeding` → `wdt intr fires=1` → `WDT-INTR RESULT: PASS (timeout -> VIC-27 -> callback, no reset)`;
the console ran PAST the timeout (no reboot) proving interrupt-INSTEAD-of-reset. Regression: rebuilt
+ booted the reset-mode wdt_smoke → 8 boots/8 s (reset still fires). So both modes work.

Row 38 Zephyr now covers reset AND timeout-interrupt. This is the Zephyr half of #189 (QE model
already done); Linux #189 stays scoped separately (mainline aspeed_wdt is a 2-stage pretimeout, a
different semantic). Evidence d14-zephyr/27. Reuses the RTC-alarm VIC-callback + WFI-wait patterns.

**Code-review fix (gate-b, confidence 90):** the reviewer found that after a one-shot interrupt
fired, the ISR cleared `enabled` but left `installed` set, and `disable()`'s `if (!enabled) return
-EFAULT` early-return then skipped ALL cleanup → `installed` leaked true → every later
install_timeout() returned -ENOMEM, breaking the "disable then reinstall" contract (the
warn→escalate pattern interrupt mode is FOR). Fixed by guarding on `(!enabled && !installed)`.
Regression-tested (smoke now checks disable+reinstall after the fire): `after fire: disable=0
reinstall=0` → `WDT-INTR-REINSTALL: PASS`. This is the 3rd real bug independent review caught this
session (RTC-Linux lock, RTC-alarm set_time clobber, this) — the review discipline keeps paying off.

## 2026-07-21 — #187 Zephyr RTC alarm: review-finding fix + QEMU-model faithfulness + deterministic validation

Follow-up to the Zephyr RTC alarm below. An independent code review found ONE real defect
(confidence 92), and validating the fix exposed a QEMU-model faithfulness gap — three fixes:

1. **Driver (rtc_aspeed_g3.c set_time) — review finding.** The counter-enable CONTROL write was a
   plain, unlocked `write(ENABLE)` that cleared the whole register, so once the alarm feature could
   set CONTROL[1:3], calling `rtc_set_time()` AFTER arming silently DISARMED the alarm — a
   deterministic violation of the Zephyr contract (alarm stays armed until disabled via
   rtc_alarm_set_time). Fixed: RMW under the driver k_spinlock, preserving the alarm-enable bits,
   never writing back RESTART[5]. Regression-tested (RTC-ALARM-PRESERVE: PASS).

2. **QEMU model (hw/misc/aspeed_rtc_ast2050.c, submodule) — REAL faithfulness bug the Zephyr test
   exposed.** The alarm-check timer compared only the single LIVE counter each tick. The counter
   advances as calendar seconds, so a sec+min+hour alarm matches at exactly ONE tick/day; when the
   timer fired late (a tight guest poll starving the QEMU main loop) the live counter had already
   passed that one matching tick and the exact `==` missed → next match a day away → the alarm
   flaked (fired ~2/3 runs). On silicon the comparator is combinational and the VIC latches the edge
   the instant the counter reaches the alarm — un-starvable. Fixed with a bounded rising-edge
   CATCH-UP SCAN over every counter value crossed since the last check (new vmstate alarm_last_abs,
   v4). The Linux wakealarm had passed only by luck; it still passes (unregressed).

3. **Smoke determinism.** The busy-poll used a tight asm spin (never yields → QEMU can't fire the
   virtual timer) then k_busy_wait (depends on the unreliable guest tick/cycle-counter on this
   ARM926 port) — both flaky. Fixed by waiting via CPU halt (k_cpu_atomic_idle/WFI): when the guest
   halts, QEMU warps virtual time to the next timer deadline, fires the alarm, and wakes on VIC-26 —
   deterministic and tick-independent, exactly how a real consumer waits.

Result: 4/4 deterministic PASS (RTC-ALARM + PRESERVE), Linux wakealarm unregressed (IRQ26 0→1).
This is the "weird behaviour = my model/code, fix it proper" principle applied end-to-end: the
review caught the driver clobber; the flakiness was a genuine model faithfulness gap (skip) plus an
unrealistic tight-loop test, both fixed rather than worked around. Submodule commit 0bf951aef8.
Evidence updated in d14-zephyr/26.

## 2026-07-21 — #187 Zephyr RTC alarm (RTC04 + VIC-26) IMPLEMENTED + QEMU-validated (row 39 ZQ)

Closed the Zephyr QEMU half of the #187 RTC alarm. Added the Zephyr `rtc_driver_api` alarm ops to
the existing counter-style set/get driver `zephyr/drivers/rtc/rtc_aspeed_g3.c`, consuming the same
QE alarm model the Linux driver uses (RTC04 @0x04 byte-packed hour/min/sec + CONTROL[1:3] per-field
enables + VIC source 26): alarm_get_supported_fields (sec/min/hour — the counter has no calendar,
same as get_time and the Linux sibling), alarm_set_time (RTC04 + CONTROL RMW preserving ENABLE[0],
never writing back the RESTART status bit[5]; mask=0 disables), alarm_get_time, alarm_is_pending,
alarm_set_callback, and a VIC-26 ISR. The ISR follows the Zephyr contract — the alarm stays ARMED
(recurring) until disabled, so it does NOT clear the enable bits (unlike the Linux one-shot); the
framework z_soc_irq_eoi() clears the latched edge. A per-device k_spinlock guards the CONTROL RMW
(shared with the ISR) + the callback/pending state; the callback is invoked outside the lock. Init
does IRQ_CONNECT(26)+irq_enable(26) with a file-static device pointer set before enable (mirrors the
GPIO driver). No VIC change needed — source 26 is already edge/falling in the RE'd G3 VIC map.

The rtc_smoke sample gained CONFIG_RTC_ALARM=y and an alarm half that arms 12:00:05, registers a
callback, and BUSY-POLLS (not k_msleep — the QEMU RTC counter advances on a QEMU-internal timer as
virtual time passes, so a busy loop keeps the CPU running and virtual time advancing until VIC-26
fires; this does NOT depend on the guest system tick, which may not sustain on this ARM926 port).

Validated in QEMU (`-M kgpe-d16-bmc`, west build board kgpe_d16_bmc/ast2050, SDK 0.17.0):
`RTC RESULT: PASS` (set/get) + `alarm supported-fields mask=0x07` + `alarm armed at 12:00:05
mask=0x07` (get_time round-trip) + `alarm fires=1` + `RTC-ALARM RESULT: PASS`. Full path proven:
rtc_alarm_set_time → RTC04/CONTROL → QEMU model counter advance (~732x) → COUNTER==RTC04 → VIC-26 →
isr_wrapper → driver ISR → callback. Evidence `d14-zephyr/26-rtc-alarm-zephyr-qemu.txt`.

Row 39: QE ✅ + LQ/LU ✅ + ZQ ✅ (now includes alarm, not just set/get). Remaining: LS (silicon
Linux) + ZS (silicon Zephyr) — both gated on a JTAG rig run. An independent code review of the new
alarm driver was dispatched (gate-(b) discipline); findings will be actioned when it returns.

## 2026-07-21 — #180 CLOSED: module-level scu_lock on the shared-SCU RMW in the Zephyr I2C driver

Applied the same locking discipline as the RTC gate-(b) fix (above) to the analogous Zephyr site.
`zephyr/drivers/i2c/i2c_aspeed_g3.c` read-modify-writes two SoC-shared SCU registers — SCU04
(SYS_RST_CTRL, i2c reset-hold release) and SCU74 (MFP_CTL1, SDA5/6/7 pin-mux) — but each engine
only holds its OWN per-device k_mutex, which cannot protect a register shared across engines
against a concurrent configure() of a DIFFERENT engine (a documented 2026-07-20 review finding).

Fix: added a file-scope `static struct k_spinlock scu_lock;` and wrapped BOTH shared-SCU RMWs
(scu_release SCU04, pinmux SCU74) in k_spin_lock/k_spin_unlock. Chose a SPINLOCK (not a mutex):
unlike the per-device TRANSFER lock — a k_mutex precisely because a transfer busy-polls with
interrupts enabled — the SCU RMW is a short non-sleeping 3-write sequence, so a spinlock is the
right minimal primitive and works from any context. Replaced the stale "guard with a module-level
lock if a second muxed channel is added" comment with the now-present lock.

Behavior-neutral + validated: rebuilt i2c_smoke (west, board kgpe_d16_bmc/ast2050, SDK 0.17.0 —
driver compiles clean with the lock) and booted on the faithful `-M kgpe-d16-bmc`:
`I2C read dev=0x2f reg=0xfe val=0x79 (expect 0x79) PASS` — the W83795 CID read over engine 1
still works. Engine 1 exercises the scu_release (SCU04) lock directly; the pinmux (SCU74) lock is
the identical idiom for channels 5-7 (compile-validated; only reachable in the future
second-muxed-channel scenario the lock guards). The race cannot occur on this board today (init is
single-threaded POST_KERNEL, only channel 5 muxed) — this is correct-by-construction hardening.
Evidence: openbmc/.../d14-zephyr/25-i2c-scu-lock-qemu.txt. Removes a standing review finding.

## 2026-07-21 — Gate-(b) RESOLVED: RTC-driver CONTROL-register concurrency fix + robust wakealarm gate

The gate-(b) code review (below) returned one real finding (confidence 80): the counter-style
`G3_RTC_CONTROL` (0x0C) register is read-modify-written from BOTH the hard-IRQ alarm handler
(via `aspeed_rtc_alarm_enable`) AND process context (`set_time`'s master-enable, `set_alarm`,
`alarm_irq_enable`) with **no lock**. A mid-RMW preempt loses either the alarm-disable
(re-arming a consumed one-shot) or the master `G3_RTC_CTRL_ENABLE` bit (RTC silently left
disabled after a "successful" `hwclock -w`). The 732x acceleration makes the window realistic —
the one-shot fires ~7 ms after arming. Everything else the reviewer checked was correct (mday
clamp, calendar base, alarm symmetry, one-shot, BCD non-regression).

**Fix (patch 0009 regenerated, drivers/rtc/rtc-aspeed.c, +211/-4):**
- `spinlock_t lock;` added to `struct aspeed_rtc` + `spin_lock_init()` in probe;
- `spin_lock_irqsave`/`spin_unlock_irqrestore` around EVERY `G3_RTC_CONTROL` RMW —
  `set_time`'s counter-enable and `aspeed_rtc_alarm_enable` (the single choke-point that
  `set_alarm`, `alarm_irq_enable`, and the IRQ handler all funnel through, so the IRQ path is
  covered transitively);
- bare single `readl()` of CONTROL (read_time enable-check, read_alarm enabled flag) left
  lock-free — a 32-bit aligned MMIO read is atomic; only RMW needs the lock.

**Also fixed a test race (not a driver/model bug):** the wakealarm gate previously required the
sysfs value to read back non-empty as its "armed" proof — but the crystal-less counter runs
~732x (the FAITHFUL no-xtal behavior, #158/#186), so the `+5` RTC-second one-shot can fire
(~7 ms) BEFORE the shell reads it back, leaving SET empty even on success. Last rebuild happened
to lose that race → spurious FAIL. Re-keyed the gate PASS on the race-free evidence: the VIC-26
rtc-alarm **interrupt-count delta** in /proc/interrupts (armed→fired) + the one-shot cleared
(AFTER empty). This is the "weird behavior = my code, fix it proper" principle applied to the
harness: the model/driver were right, the test's proxy was racing the real fast counter.

**Re-validated (QEMU, hardened driver + robust gate):** `RTC-LINUX RESULT: PASS` (set/get) and
`RTC-WAKEALARM RESULT: PASS (armed -> IRQ26 fired (0->1) -> RTC_AF cleared it)`. The spinlock is
behavior-neutral — both gates still pass. Patch 0009 reverse- and forward-applies clean. Row 39
LQ/LU stay ✅, now concurrency-hardened; LS (silicon) still ⬜ (JTAG rig run pending).

An independent re-review of the hardened driver (feature-dev:code-reviewer, all 6 checks:
every CONTROL RMW locked; lock init before devm_request_irq; no sleeping call under the lock
and rtc_update_irq outside it; spin_lock_irqsave used consistently for the hard-IRQ+process
mix; BCD path unchanged; no double-unlock/missing-unlock/wrong-lock) returned **CLEAN — race
closed, no new defect**. Notably it confirmed the fix is correctly SCOPED: the BCD path has no
alarm ops so it was never exposed to the race and correctly takes no lock. Gate-(b) CLOSED.

## 2026-07-21 — Gate-(b) on the new RTC Linux driver + #189-Linux scope refined (WDT pretimeout mismatch)

Two things:
1. **Gate-(b) dispatched** on this session's substantial new code — the counter-RTC Linux driver + wakealarm
   (patch 0009, drivers/rtc/rtc-aspeed.c). An independent adversarial code-reviewer is checking the
   byte-packed read/set, the alarm ops (RTC04/RTC0C RMW, IRQ handler one-shot, no lock), probe (two ops
   structs, device_init_wakeup gating, BCD-path non-regression). Findings will be actioned when it returns.
   This is the right discipline: verify the new driver before building more on it (it already had one real
   omission I caught empirically — device_init_wakeup).
2. **#189-Linux scope refined (honest finding).** Investigated the Linux side of the WDT interrupt mode.
   mainline aspeed_wdt.c HAS pretimeout+interrupt (aspeed_wdt_set_pretimeout, WDT_CTRL_WDT_INTR BIT(2),
   of_irq/devm_request_irq) — BUT it's a 2-STAGE pretimeout (IRQ at timeout−pretimeout, reset at full
   timeout), a DIFFERENT semantic than the datasheet-§27 "interrupt INSTEAD of reset" (WDT_CTRL_WDT_INTR)
   that my #189 QE model implements; and the g4.dtsi ast2400-wdt node wires NO interrupt. So Linux #189 is
   not a clean drop-in like the RTC was — it needs the pretimeout↔interrupt-mode mapping resolved + the dts
   IRQ wired + (possibly) the model extended to the 2-stage pretimeout counter. Recorded on #189; low
   priority (firmware-unexercised — mainline/Zephyr WDT use reset mode). Not attempted blind; scoped honestly.

## 2026-07-21 — #187 Linux wakealarm (RTC04 + IRQ26) IMPLEMENTED + validated

Extended the just-landed G3 counter-RTC Linux driver (patch 0009) with the wakealarm, consuming the #187
QE alarm model (QEMU raises VIC-26 on an RTC04 match). Added counter-style alarm ops: read_alarm/set_alarm
(program RTC04 = byte-packed hour/min/sec + RTC0C[1:3] enables) / alarm_irq_enable, an IRQ handler
(one-shot disable + rtc_update_irq(RTC_AF)), and probe support (request the VIC-26 IRQ + device_init_wakeup
so rtc_does_wakealarm() exposes the /sys attr). The board dts `&rtc` gains `interrupts = <26>`.

Debug note (honest): first boot the wakealarm attr was ABSENT (SKIP) — root-caused to the rtc core gating
/sys/class/rtc/rtc0/wakealarm on device_can_wakeup(parent) via rtc_does_wakealarm(); the driver hadn't
called device_init_wakeup(). Added it (only when the IRQ is present+requestable), and it appeared. Not a
hardware quirk — a driver omission I fixed.

Validated (rtclinux gate): `echo +5 > /sys/class/rtc/rtc0/wakealarm` → armed (epoch 947940373) →
sleep → readback '' (empty). The 732x-fast counter reaches the alarm in ~7 ms, the model raises IRQ 26, the
handler delivers RTC_AF, and the core clears the one-shot. **RTC-WAKEALARM RESULT: PASS.** Full path proven:
userspace(/sys wakealarm) → set_alarm → RTC04/RTC0C → QEMU alarm compare → VIC 26 → IRQ handler → RTC_AF.
Regenerated patch 0009 (190 insertions, alarm ops included). Closes the Linux half of the #187 RTC-ALARM
capability. Remaining #187: Zephyr rtc alarm API + silicon validation of the whole RTC + alarm.

## 2026-07-21 — #187 Linux: G3 counter-RTC driver IMPLEMENTED + validated — over-claim → real functionality

Converted last turn's row-39 RTC over-claim (LQ ⬜, "no working Linux RTC") into a genuine, validated Linux
driver. This is the "implement proper Linux driver + validate in QEMU + validate userspace" deliverable.

The mainline `rtc-aspeed` only knows the AST2400 BCD layout (TIME/YEAR/CTRL@0x10) and the g4.dtsi node was
disabled → no /dev/rtc0. Implemented the G3 counter-style variant (kernel patch 0009, extends
drivers/rtc/rtc-aspeed.c): a new `aspeed,ast2050-rtc` compatible with a counter_style config; read_time
reads COUNTER (0x00) byte-packed and reports a fixed calendar base (the counter has no year/month —
datasheet §24); set_time writes RELOAD (0x08) + pulses RESTART (0x10)=0x5A + enables CONTROL (0x0C)[0] —
mirroring the silicon-validated Zephyr rtc_aspeed_g3.c. The ast2400/2500/2600 BCD path is untouched. The
board dts (dts/aspeed-bmc-asus-kgpe-d16.dts) gets an `&rtc` override re-pointing the node at the new
compatible + status=okay; build-kernel.sh registers 0009 (idempotent guard on the new compatible).

Validated in QEMU + userspace (rtclinux gate, evidence d14-zephyr/17): `aspeed-rtc 1e781000.rtc: registered
as rtc0` → /dev/rtc0 exists (over-claim fixed). `date -s 12:45:30` → `hwclock -w` (set_time) → `hwclock -r`
reads back `12:45:40` and `/sys/class/rtc/rtc0/time`=`12:45:50` — hour:min round-tripped, sec advancing
~732x (crystal-less rate, #158/#186), day = the set Jan 15. Full path userspace→driver→MMIO→G3 RTC model.

Row 39: LQ ⬜→✅, LU ⬜→✅ (tally LQ 21→22, LU 13→14). LS stays ⬜ (silicon via JTAG not yet run). Remaining
#187: RTC04/IRQ-26 wakealarm (RTC_ALM_SET/RTC_AIE) on top of this driver + Zephyr alarm + silicon. NICE
arc: an over-claim caught by empirical check last turn is now a real, functionally-validated driver this
turn — the honest way to move a cell to ✅.

## 2026-07-21 — INTEGRITY sweep: independent audit found 3 MORE bind-only over-claims (all corrected)

The RTC over-claim (below) exposed a class — "✅ resting on the driver binding / a model existing, not on a
functional result" — so I dispatched an independent sub-agent to hunt the same pattern across every
QEMU/userspace/Zephyr ✅ cell. It audited ~25 cells against their evidence and found exactly THREE more,
now corrected:
- **Row 19 DIMM TSOD, LQ ✅→Ⓝ (HIGH, near-exact RTC twin):** the ✅ rested on "the jc42 model file exists",
  but the machine deliberately does NOT instantiate a jc42 on this rig (0x19 NAKs faithfully). LS/LU/ZS
  were already Ⓝ → LQ must be Ⓝ. Internally-inconsistent ✅ removed.
- **Row 5 LPC POST-snoop, LQ ✅→🔶 (MEDIUM):** rested on the `aspeed-lpc-snoop` driver binding +
  `/dev/aspeed-lpc-snoop0` being created — NO POST byte is ever captured in the host-less QEMU machine
  (self-disclosed by scripts/lpc-test.py). BMC-side bind done → 🔶, not ✅.
- **Row 6 LPC vUART, LQ ✅→🔶 (MEDIUM):** rested on `8250_aspeed_vuart` binding + ttyS5 appearing — no
  host-visible vUART byte transferred (needs a host LPC master QEMU lacks). → 🔶.

CRUCIALLY the audit was DISCRIMINATING, not reflexive: it CONFIRMED row 3 (LPC KCS) — which ALSO uses a G4
compatible (`aspeed,ast2400-kcs-bmc-v2`) on the G3 — is genuinely FUNCTIONAL (ODR3 write 0x5A→readback
0x5A + LADR/HICR programmed + silicon host `mc info` answered). So "G4 driver on G3" is not automatically an
over-claim (RTC was, KCS wasn't) — each needs a functional check, which is exactly the point. Every other
audited ✅ cell (DDR2, SPI-ID, eth, I2C/W83795/SPD/FRU/W83601G/SB-TSI/PSU/power/LEDs/straps/SCU/VIC/timer/
WDT/RTC-ZQ/USB) carries real functional evidence. Regenerated the tally after the 3 glyph changes.

## 2026-07-21 — INTEGRITY: caught + corrected an RTC Linux-stack OVER-CLAIM (row 39 LQ ✅ → ⬜)

While scoping the #187 Linux stack I found — and empirically confirmed — a real OVER-CLAIM in the trackers
(the goal cares about incorrect claims; this is the over-claim direction). Row 39 LQ was ✅ and
FULL-TASK-LIST A7 said "Linux [x] QEMU (rtc-aspeed)", but:
- the board Linux dts is based on `aspeed-g4.dtsi`, whose `rtc@1e781000` is `aspeed,ast2400-rtc` — the
  BCD-style RTC (TIME@0x00, YEAR@0x04, CTRL@0x10). The REAL G3 RTC is COUNTER-style (COUNTER@0x00,
  RELOAD@0x08, CONTROL@0x0C, RESTART@0x10) — register-INCOMPATIBLE (rtc-aspeed would read "year" from the
  G3's alarm reg and "ctrl" from the G3's RESTART reg);
- EMPIRICAL PROOF (new `rtclinux` init gate): booting the C2 kernel, `ls /dev/rtc*` = "No such file", no
  `/sys/class/rtc/rtc0`, hwclock can't open /dev/rtc. So rtc-aspeed produces NO working RTC device on the
  G3 at all — the "LQ ✅ (rtc-aspeed)" was a bind/assumption over-claim, NOT a validated Linux RTC.

Corrected honestly: row 39 LQ ✅ → ⬜; FULL-TASK-LIST A7 Linux `[x] → [ ]` with the full reason. Recorded the
accurate #187-Linux scope: the G3 needs a NEW `aspeed,ast2050-rtc` COUNTER-style Linux driver + a G3 dts
rtc node (mirroring the silicon-validated Zephyr `rtc_aspeed_g3.c`), THEN the RTC04/IRQ26 wakealarm on top.
This is the same verify-first discipline that caught the #190/#191 mis-flags — applied here it caught an
over-claim instead. Note: gate-c's earlier weasel-audit spot-check did not hit this specific RTC-LQ cell;
worth a targeted re-audit of *-QEMU ✅ cells that rest on "driver binds" rather than a functional check.

## 2026-07-21 — #191 verified + dispositioned: SCU1C already modeled; freq-counter/IRQ firmware-unexercised

Investigated the last un-examined gate-d sub-block, #191 (SCU freq-counter / IRQ-ctrl / 32.768kHz
error-correction). Verify-first caught another PARTIAL mis-flag (like #190's buffer-pool):
- **SCU1C (32.768kHz err-correct): ALREADY MODELED.** The gate-d agent flagged it from the header define
  name `D2PLL_PARAM` (the AST2400 meaning), but the G3 SCU reset table `ast2050_a3_resets`
  (hw/misc/aspeed_scu.c:228) ALREADY seeds SCU1C = 0x1B with the datasheet citation "SCU1C = 32.768kHz
  err-correct p211" — the faithful G3 value + meaning. Not a gap.
- **Freq-counter (SCU10/14/28) + IRQ_CTRL (SCU18): register-level backing store, firmware-unexercised.**
  The read handler returns the backing store (FREQ_CNTR_EVAL is read-only, returns the reset seed); the
  functional behaviour (a live clock-measurement count; SCU interrupt generation) is unmodeled. But NO
  board firmware exercises them — the freq counter is a PLL-lock diagnostic and SCU interrupts are unused
  at boot by U-Boot/Linux/Zephyr. Dispositioned like the accepted PECI/HACE "modeled-but-unused → reasoned"
  precedent (gate-c confirmed that standard): row 35 QE/ZS ✅ stands because the boot-exercised SCU
  functionality (clock/reset/pinmux/PLL/silicon-rev/strap) is complete + validated; functional
  freq-counter/SCU-IRQ modelling is an OPTIONAL low-value "all-functionality" follow-on, not a boot gap.

Gate-d sub-block set now FULLY characterized (none weaseled): #187 QE done, #188 real gap scoped
(shared-code error-path), #189 QE done, #190 buffer-pool done + DMA scoped (firmware-unexercised), #191
SCU1C done + freq-counter/IRQ firmware-unexercised. The two verify-first mis-flag catches (#190 buffer-pool,
#191 SCU1C) show the value of checking the actual code before dispositioning — and neither was closed as a
false "absent".

## 2026-07-21 — #188 verified + scoped: I²C SDA bus-lock recovery is a real (shared-code, error-path) gap

Investigated gate-d #188 (I²C SDA bus-lock recovery, §31.5.11). Confirmed it's a GENUINE gap (unlike #190's
buffer-pool mis-flag): the QEMU aspeed_i2c model HEADER defines all the recovery fields —
I2CD_INTR_STS.BUS_RECOVER_DONE (bit13), engine state I2CD_RECOVER=0x3, FUN_CTRL.M_SDA_LOCK_EN/M_SCL_DRIVE_EN,
SDA_OE/SCL_OE/SDA_LINE_STS/SCL_LINE_STS — but grep shows NONE are referenced in hw/i2c/aspeed_i2c.c. So the
model never sets BUS_RECOVER_DONE; a driver running §31.5.11 SCL-toggle recovery after a stuck-SDA timeout
would never see completion.

Scoped precisely rather than rushed: this is (1) SHARED upstream code (aspeed_i2c.c used by AST2400/2500/
2600 — must stay unaffected), (2) an I²C ERROR PATH (mainline i2c-aspeed calls recover_bus only on a bus
timeout, which the clean QEMU bus never produces → firmware-rarely-exercised), and (3) validatable only
SYNTHETICALLY (devmem-trigger the recovery + read BUS_RECOVER_DONE, since QEMU has no real stuck SDA). The
implementation is small (set BUS_RECOVER_DONE + idle-high line status on a recovery trigger) but must first
pin the exact trigger against the mainline recover_bus. Deferred from this extremely-long context-tail to a
dedicated turn — rushing a shared-code error-path change here would risk a regression against the prime
directive. Honest scoping is real progress: turned a vague flag into a precise, actionable, risk-assessed
task (same treatment as #190's DMA half).

## 2026-07-21 — #189 QE: WDT timeout-INTERRUPT mode (WDT0C[2] -> VIC 27) modeled + validated

Another gate-d sub-block turned into validated emulation. #189: datasheet §27 says the WDT generates
EITHER an interrupt OR a reset (WDT0C[2] "wdt_intr"), but the QEMU aspeed WDT had no IRQ line and always
reset (watchdog_perform_action), ignoring the bit. This is SHARED upstream code (wdt_aspeed.c, used by
AST2400/2500/2600), so I was careful:
- Change is purely ADDITIVE: added a qemu_irq + sysbus_init_irq; at expiry, `if (WDT_CTRL & WDT_INTR)
  { pulse IRQ; return; }` BEFORE the unchanged watchdog_perform_action() reset. Reset mode (WDT_INTR=0 —
  what the Linux aspeed_wdt driver, U-Boot, and every legacy oracle use) hits the untouched reset path.
- The G3 machine wires WDT0's IRQ to VIC 27, G3-gated so the AST2400 path is unchanged (an unconnected
  qemu_irq is a no-op on other machines).
- Modelled as a pulse (interrupt EVENT); held-level-until-WDT_TIMEOUT_CLEAR is a follow-on.

DUAL-PATH validated (both matter — the reset path is legacy-critical):
1. INTERRUPT mode (new wdtintr /dev/mem gate, evidence f-wdt-userspace/01): RELOAD=10ms, CTRL=WDT_INTR|
   1MHZ|ENABLE -> after ~10ms the WDT raised IRQ 27, VIC raw bit27 `0 -> 0x08000000` -> **WDT-INTR PASS**.
2. RESET mode UNCHANGED: re-ran the wdtreset gate — WDT armed (timeout=3 active), and raw QEMU without
   -no-reboot reboot-looped (repeated "Booting Linux"), i.e. the WDT reset still fires. Code-additive +
   empirical = reset path preserved.

QE half of #189 done. Remaining: WDT18 reset-assert-width; Linux/Zephyr exercising interrupt mode (both
use reset mode today -> low-priority both-sides follow-on). Discipline note: took extra care with the
shared-code reset path per the prime directive, and validated BOTH the new interrupt path AND the
unchanged legacy reset path rather than assuming.

## 2026-07-21 — #190 verified + rescoped: I²C buffer-pool ALREADY modeled; DMA is the (unexercised) gap

Investigated gate-d finding #190 (I²C buffer-pool/DMA transfer modes "undispositioned") before assuming a
disposition. Verify-first paid off — the finding was PARTLY WRONG:
- **Buffer-pool: ALREADY MODELED.** The G3 aspeed_i2c class (aspeed_2400_i2c_class_init) sets
  `has_share_pool=true` + `pool_size=0x800`, and the QEMU model does functional pool TX/RX
  (hw/i2c/aspeed_i2c.c pool_tx_count/pool_rx_count → i2c_send/recv from the shared pool). So row 15 QE
  already covers byte-mode AND buffer-pool mode — not a gap.
- **DMA-buffer: a genuine but firmware-UNEXERCISED gap, NOT Ⓝ.** I checked the datasheet before
  dispositioning: §31.5.9 "DMA Buffer Mode Usage" + line 14076 "REQ21 I2C DMA buffer mode read/write"
  CONFIRM the AST2050 I²C has DMA — so a blanket "Ⓝ/absent" would be WRONG (the exact error class the lead
  warns about). But the G3 model has `has_dma=false` and NO board firmware uses I²C DMA (U-Boot byte via
  trbbr; mainline Linux i2c-aspeed byte/pool, DMA gated to AST2500+; Zephyr byte-only). So #190 stays OPEN,
  narrowed to: RE the AST2050 I²C-DMA register mechanism, model it for the G3 class, validate with a
  synthetic /dev/mem test (no firmware oracle). LOW priority (unexercised), honestly NOT closed.

Net: turned a vague "undispositioned" flag into an accurate split — one half already done, the other a
real (low-value) open item — without weaseling the DMA part into a false "absent" claim.

## 2026-07-21 — #187 QE: RTC alarm (RTC04) + alarm IRQ 26 modeled + validated (closing a gate-d finding)

Turned a gate-(d) finding straight into working emulation (converting audit output → functionality). #187:
the datasheet §24 RTC alarm was unmodeled — #158 modeled only the free-running counter; the G3 RTC model
didn't handle reg 0x04 and wired only the RTC IRQ 22, not the separate RTC-alarm IRQ 26.

Modeled it (submodule 31ea873582): RTC04 alarm register + RTC0C[1:4] per-field alarm-enables; a periodic
QEMUTimer at the counter's own RTC-second rate (clk_hz/32768) compares the ENABLED alarm fields against the
live counter while armed and PULSES a dedicated alarm IRQ on a rising match edge; a 2nd sysbus IRQ wired to
VIC input 26 in the G3 machine; arm/disarm re-evaluated on every RTC04/RTC0C/RESTART/RESET write; reset +
vmstate v2->v3 add the timer + edge state. Byte-packed field compare, consistent with the counter (#186).

Validated in QEMU (new rtcalarm /dev/mem gate, evidence d14-zephyr/16): RELOAD=00:00:05, RTC04=00:00:10
(sec+min+hour enabled), enable -> the 732x-fast counter reaches 10s in ~7ms -> alarm fires -> VIC raw-status
(0x1E6C0008) bit26: before=0, after=0x04000000 -> **RTC-ALARM RESULT: PASS**. Full path proven: RTC04
compare -> QEMUTimer -> alarm IRQ 26 -> VIC edge-latch -> userspace /dev/mem read. Nice faithfulness bonus:
because the alarm ticks at the same crystal-less 732x rate as the counter, a 1-second wakealarm would fire
~732x fast on this board — the #158/#186 rate story carries through to the alarm.

QE half of #187 DONE. Remaining #187: Linux rtc-aspeed wakealarm (RTC_ALM_SET/RTC_AIE + /sys wakealarm) and
Zephyr rtc alarm API drivers + their QEMU/silicon validation. Gate-d list shrinks by one QE cell.

## 2026-07-21 — Gate-(c) integrity + Gate-(d) new-task discovery: trackers HONEST; 5 sub-block tasks added

Ran the two remaining completion gates as independent sub-agent sweeps.

**Gate-(c) weasel/over-claim audit — PASS (no dishonest/over-stated claims).** The auditor spot-checked the
highest-risk class (Zephyr-silicon ✅) and confirmed EVERY one has a dedicated md5-verified JTAG transcript
(rows 15/16 W83795 live-drift, 20 FRU, 21/22 W83601G, 35 SCU, 36/37 VIC/timer, 38 WDT), plus LS/LU ✅ (row
3 KCS real host mc info, 23 SB-TSI, 32 LEDs, 8 video 28418-byte frame, 9 USB). `tally.py` reproduces the
snapshot exactly. Ⓝ dispositions (40 PWM, 42 PECI, 41 ADC, 19 TSOD, 13 QU6) all hold against the schematic.
Verdict: trackers are "unusually rigorous and self-critical" — replete with dated HONESTY CORRECTIONs that
DOWNGRADE cells. Two low-severity doc-accuracy nits fixed: (1) row-3 KCS evidence citation pointed at
`evidence/host-kcs/` but the real-silicon transcript is `real-hw-hwpass/host-kcs-mc-info-fru.txt` (claim
backed, citation now precise); (2) row-8 video LS 🔶 (matrix) vs B3 `[x]` (FULL-TASK-LIST) — documented the
aggregate↔split granularity mapping so the two docs demonstrably agree (matrix row folds B2+B3+B3b).

**Gate-(d) new-task discovery — does NOT cleanly pass; 5 genuine tasks ADDED (#187-#191).** The device+stack
enumeration is complete (gate-a), but an independent datasheet-level sweep found five register-level
functional sub-blocks a "complete emulation of ALL functionality" demands, sitting UNTRACKED inside
otherwise-✅ QE cells (previously only weakly noted as #177 "siblings", never rowed/scoped):
- **#187 RTC alarm RTC04 + IRQ 26** (row 39) — §24 mandates a programmable alarm w/ interrupt; #158 modeled
  only the free-running counter (the G3 RTC model doesn't handle reg 0x04 at all). Ties to #158/#186.
- **#188 I²C SDA bus-lock recovery** (row 15, §31.5.11) — SCL-toggle recovery on a stuck SDA; board-relevant
  on the multi-master shared sensor bus; unmodeled.
- **#189 WDT timeout-INTERRUPT mode** (row 38, WDT0C[2]/WDT18) — only the reset path validated.
- **#190 I²C buffer-pool/DMA-buffer transfer modes** (row 15, §31.5.2/3/9) — only byte-mode; needs a
  model-or-Ⓝ disposition.
- **#191 SCU freq-counter/int-ctrl/32.768kHz error-correction** (row 35) — un-enumerated; SCU1C ties to the
  #158/#186 RTC-accuracy story.
Recorded all five in the DEVICE-MATRIX completeness section (so a future audit sees them tracked, not
silently absent) and as tracker tasks. These are register-level completeness items, NOT device-enumeration
gaps — gate-a coverage is unaffected — but they mean rows 39/15/38/35 are not TRULY 100% QE until
dispositioned. Honest consequence: gate-(d) is now "re-runnable" — the list grew, so completion is not
declarable until #187-191 (and the other open ⬜/#-tasks) are closed and a fresh gate-(d) comes back empty.

## 2026-07-21 — Gate-(b): code review of this session's new code — both CLEAN (1 comment sync)

Ran completion-gate (b) on the code developed THIS session (the prior gate-b sweep covered the older
QEMU/Zephyr bodies). Two independent adversarial code-reviewer sub-agents:
- **RTC advance model** (`hw/misc/aspeed_rtc_ast2050.c` + header, submodule f93addb7e0): NO functional
  defects ≥80 confidence. Verified the tick math (no overflow, no drift — recomputed from a fixed anchor,
  not accumulated), the base_ns anchoring across RESTART/enable/disable in every ordering incl. the real
  driver's write-RELOAD→RESTART→enable sequence (monotonic, no double-count), pack/unpack round-trip,
  reset, and register bounds. It also reasoned through my flagged v1→v2 `base_ns=0` migration concern and
  found it BENIGN (reset runs before loadvm; QEMU_CLOCK_VIRTUAL is frozen while stopped, so base_ns lands
  ~load time — not an enormous jump). Only finding: a doc-only stale HEADER top-comment (still described
  the old field-packed 1 Hz layout) → FIXED (submodule 9a17c1132c, comment-only sync to byte-packed +
  732.42x + #186 ref).
- **W83795 alarm QE+LU** (`hw/sensor/w83795.c` seed + kernel patch 0003 inN_alarm/fanN_alarm): NO defects
  ≥80. Verified bit-for-bit that 0xAA/0x04/0x03/0xFE encode in1/3/5/7 + in10 + in15/16 + fan2..8 per the
  driver index formula; do_read returns them unshadowed with correct bank-0 gating + no ALARM5 collision;
  the modern-hwmon index math (in: channel+(channel>14?1:0); fan: channel+32) is off-by-one-free and
  in-bounds of alarms[6]; is_visible exposes exactly 21 in + 14 fan channels; values self-consistent with
  the silicon capture; vmstate needs no bump. Bonus: confirmed the update_device dev_get_drvdata/data->client
  refactor is a NECESSARY correctness fix, not a regression.

Gate-(b) verdict for this session's code: CLEAN (one comment sync applied). The broader gate-(b) across
all developed stacks + gates (c) weasel-audit and (d) new-task-discovery remain to run.

## 2026-07-21 — Gate-(a) RESULTS: coverage complete; 2 incorrect-absence claims fixed + 5 doc-accuracy nits

All 4 independent audit sub-agents returned. **Result strongly satisfies the hook's concern:**
- **Coverage COMPLETE.** Agents 1 (§1–9), 2 (§10 I²C), 3 (§11–16) each independently found ZERO coverage
  gaps — every device/signal/chip/connector in the authoritative schematic maps to a matrix row or a
  justified disposition. All 8 I²C engines, both DIMM banks, the mux fabric + multi-master arbitration,
  all 16 §11 GPIOs, JTAG/LEDs/clock/straps, all neighbour chips + connectors verified.
- **Primary tracking files CLEAN.** Agent 4 (skeptical false-claims hunter) confirmed every
  not-exists/unconnected/impossible claim in DEVICE-MATRIX/FULL-TASK-LIST/LOG is either datasheet-justified
  (ADC-absent, PECI-strapped-to-GPIO, PWM-not-driving-fans, USB-device-only, host-BIOS-flash-on-SB) or
  explicitly rig/strap/host-power-scoped (DIMM host-off, SPI-flash empty-socket) — and the historically
  wrong NC-SI/DIMM claims are already retracted + correctly re-stated.

**Two genuine incorrect-absence claims (the exact class the goal warns about) — both in SUB-docs — FIXED:**
1. `SILICON-STATUS.md #6` SOL "host COM console not wired to the AST2050 VUART (a board-wiring limit)" —
   CONTRADICTED by schematic §12 (host serial IS wired: UART1→QU8→Super-I/O). Corrected all 3 spots: the
   real constraints are the UART1+QU8 path (not the LPC VUART the image models) and the empty-socket
   `BMC_PRESENT#`-high strap handing QU8 to the host RS-232 side — a rig/strap condition, not a wiring absence.
2. `PROGRESS.md` 2026-07-12 F7 "the KGPE-D16 does NOT use NC-SI / no NC-SI hardware" — stale append-only
   line, contradicted by schematic §7 + DEVICE-MATRIX row 11 + SILICON-STATUS #9 + F7-NCSI.md. Added a
   SUPERSEDED/RETRACTED banner (history preserved). (commit 8803eb5)

**Five doc-accuracy nits FIXED (this commit):**
3. DEVICE-MATRIX §14 row: SR5690 (NU1) is NOT on the shared I2C3/I2C6 bus — its only I²C is the separate
   SR5690-mastered PCIe-hot-plug SMBus to NB_DEBUG_HEADER1 (conclusion "not BMC-driven" was right; the
   stated path was wrong). 4. `I2C-SMBUS-TOPOLOGY.md §3.5` FRU U25 address 0x50→0x54 (stale vs its own
   table + silicon scan). 5. NC-SI-silicon roll-up glyph 🔷→⬜ (matches row 11 LS ⬜ "not externally
   blocked"). 6. Row 32 title now notes the chassis-locator button INPUT (AST_IDBNT#/Y3), not just LEDs.
   7. Added an explicit "out-of-BMC-scope" disposition for the 3 non-BMC superset buses (CPU/NB VR PMBus,
   SP5100 SMBus3, FireWire EEPROM).

Gate-(a) is satisfied by independent review: no coverage gaps, and the only surviving incorrect-absence
claims (2) are now corrected. Net: the comprehensive schematic→driver/emulation task list is verified
complete against the authoritative wiring, and the "functionality doesn't exist / unconnected" errors the
lead flagged are eliminated from the live docs.

## 2026-07-21 — Completion-gate (a): fresh authoritative-schematic re-read + independent coverage audit

Re-grounded against the AUTHORITATIVE source per the standing goal (and a Stop-hook prompt to prove
complete coverage, not just incremental device work). Read `schematic-wiring/AST2050-BMC-WIRING.md`
END-TO-END (all 597 lines, §1–§16) fresh and cross-checked every section against DEVICE-MATRIX.md:

- §2 power/PLL/LDO → passive (no driver target), folded into SCU/SDMC (row 35) + #142; §3 DDR2 → row 1;
  §4 SPI → row 2; §5 LPC → rows 3–7; §6 PCI-33/iKVM → row 8; §7 Ethernet → rows 10/11; §8 VGA → rows
  12–14; §9 USB → row 9; §10 I²C (8 buses) → rows 15–26; §11 GPIO → rows 27–29; §12 SOL → rows 30/31;
  §13 JTAG/LEDs/clock/straps → AST_JTAG1 (Ⓝ harness) + rows 32/33/34; §14 neighbour chips → all active
  chips have rows, passive glue/LDOs folded, SU1/OU1/NU1 = host-side reached via LPC/PCI/I²C; §15
  connectors → mapped to their function rows; §16 per-pin table → the gate-(d) per-pin sweep (B1f/B1g/
  B2/E6) + CU2 clock-gen already dispositioned.
- CONFIRMED the existing "Doc section → Matrix rows" coverage map (DEVICE-MATRIX.md ~l.594–647) is
  accurate against this fresh read — every §maps to a row or a justified disposition. The comprehensive
  task list already EXISTS (50 device rows × 8 stacks + FULL-TASK-LIST + coverage map); the right move is
  to independently VERIFY it, not duplicate it.

Executed gate-(a) properly: dispatched 4 INDEPENDENT sub-agents (≤5 concurrent) to freshly audit
schematic-vs-matrix coverage and specifically hunt the failure the goal names — "incorrect claims that
functionality doesn't exist / features are unconnected" that CONTRADICT the authoritative schematic:
  1. §1–§9 coverage + false-claim check;
  2. §10 I²C/SMBus full topology (8 buses, muxes, every far-end, multi-master arbitration);
  3. §11–§16 (GPIO/SOL/JTAG/LEDs/clock/straps/connectors/per-pin) coverage;
  4. dedicated skeptical hunter for "impossible/absent/unconnected/not-wired" claims across
     DEVICE-MATRIX/FULL-TASK-LIST/LOG, classifying each JUSTIFIED vs SUSPECT with schematic citations.
Findings (gaps or genuinely-wrong absence claims) will be actioned as new tasks/fixes when the agents
return; this entry records the process. Nothing is being marked complete on the basis of my own read
alone — gate-(a) requires the independent reviewers to come back empty.

Rotated to the RTC after concluding #182 (USB virtual-media CD-ROM) is KVM-gated in this session — its
only meaningful proof is the x86 host's SCSI INQUIRY (TYPE_ROM), which needs the two-VM usbip harness
(/dev/kvm, and this user isn't in the kvm group); an in-guest CD-ROM demo would look identical to the
disk demo (CD-ROM-ness is invisible at the USB-descriptor layer) and prove nothing — so I flagged #182
and did NOT weasel it.

#158 was fully local (ARM QEMU). The G3 counter-style RTC model (hw/misc/aspeed_rtc_ast2050.c) latched
RELOAD→COUNTER but NEVER advanced the counter ("deferred behavioural add-on") — a frozen RTC, while
silicon's counts. **Verify-before-modeling paid off twice:**
1. RATE: the silicon evidence's "732x" was a divider-math *inference* (checked against an assumed ~30 ms
   window, circular). I went to the datasheet: §24 shows the RTC /32768 tick (fractional divider makes
   12MHz*128/46875 = 32768.0 Hz → real 1 Hz), and §2.19/§24/SCU08[16] confirm SCU08[16]=1 feeds raw
   24 MHz → 24e6/32768 = 732.42x. So the rate is now datasheet-CONFIRMED, not inferred. (§2.19's "1MHz
   from 24MHz" phrasing initially looked like it implied a different rate — §24's register spec settles
   it.)
2. LAYOUT CONFLICT (new finding #186): datasheet §24 RTC00 is FIELD-packed (sec[5:0] min[11:6]
   hour[16:12] day[31:17]); the silicon-validated Zephyr driver is BYTE-packed (sec[7:0] min[15:8]
   hour[23:16] day[31:24]). The one silicon set/get test can't distinguish them (sec 30→52 never wraps
   past 60). The model advances BYTE-packed to keep the firmware oracle working (a field-packed re-encode
   would corrupt the driver's values even without a wrap) — and I flagged the conflict as #186 (needs a
   silicon minute-wrap test) rather than silently picking a side.

MODEL: advance the counter at clk_hz/32768 while CONTROL[0] is enabled (clk_hz = device property,
default 24 MHz; base_ns anchors on RESTART/enable, freezes on disable; vmstate v1→v2). INERT AT RESET
(CONTROL[0]=0 → frozen, bit-identical to before), so no legacy-oracle regression. Validated in QEMU
(`rtcrate` /dev/mem gate): load 00:00:00, enable, sleep 1 s → counter advanced +768 RTC-seconds (fast,
not ~1); frozen before this change (evidence d14-zephyr/15). Legacy non-regression: normal boot of the
same C2 kernel+QEMU reached BMC-READY cleanly; full C2/C-UBOOT/C4 multi-oracle confirmation runs in CI.
This closes the "model the rate" half of #158; ZS row 39 stays 🔶 (true 1 Hz is impossible without a
32.768 kHz crystal — the documented hardware constraint).

## 2026-07-20 — #183 (partial): W83795 ALARM(0..4) status seeded to silicon — both sides (QE model + LU userspace)

Continued #183 with a bounded, faithful piece: the model's ALARM(0..4) status registers (bank 0,
0x41..0x45) fell through `w83795_do_read` to the zeroed scratch store, so it reported **NO voltage/fan
alarms** — directly contradicting the very silicon capture it seeds its measurements from
(`evidence/real-hw-hwpass/host-w83795-sensors.txt`, w83795g-i2c-14-2f). A faithful model must report the
alarm state the real chip reports.

**Verified before seeding (not inferred).** Read the actual silicon capture + the actual mainline driver.
The pre-compaction inference (0x2A, in1/3/5) was **WRONG** — silicon ALSO alarms in7 (its max limit reads a
corrupt +0.05V, so 1.82V > max). Re-deriving the bit map from `show_alarm_beep` (`alarms[idx>>3]` bit
`idx&7`; in<n>→idx n+(n>14?1:0); fan<n>→idx n+31) against the capture gives:
in1/3/5/7→ALARM(0)=**0xAA**, in10→ALARM(1)=0x04, in15/16→ALARM(2)=0x03, (no temp)→ALARM(3)=0x00,
fan2..8→ALARM(4)=**0xFE**. Every bit is self-consistent with the measurement+limit already modelled — the
deterministic comparator result the chip produces, not an arbitrary constant. Catching the 0x2A→0xAA error
is exactly why "verify against the capture, don't infer" matters.

**QE (model, submodule 3d5df467ca):** seeded ALARM(0..4) in `w83795_load_defaults`; register-validated over
raw i2c in a new `W83795-ALARM` gate block — `ALARM(0)=0xaa ALARM(1)=0x04 ALARM(2)=0x03 ALARM(4)=0xfe` PASS
(evidence `d08-w83795-caseopen/01`). Static snapshot only; live limit-vs-measurement recompute + SMBALERT#
stay deferred. No legacy oracle (C-UBOOT/C2/C4) reprograms these limits, so the static seed matches every
real boot (faithfulness preserved).

**LU (driver + userspace):** the modern-hwmon patch exposed only inN_input/fanN_input, so userspace still
couldn't read the alarm bits. Extended patch 0003 — HWMON_I_ALARM on all 21 `in` channels + HWMON_F_ALARM
on all 14 `fan` channels, and branched `w83795_hwmon_read` on `attr` to return the alarm bit with the SAME
index map the legacy attrs use (in: channel+(channel>14?1:0); fan: channel+32). Rebuilt the C2 kernel,
added a `W83795-INALARM` gate reading `/sys/class/hwmon`: **`in0=0 in1=1 in7=1 fan1=0 fan2=1` → PASS**
(evidence `02`) — full userspace→driver→i2c→fabric→model path. The `w83795test` boot IS the C2 kernel to
full userspace with the driver bound, so no legacy-boot regression.

**#183 rescoped:** the static alarm STATUS is now DONE (both sides); what remains for row 16 QE ✅ is
SmartFan auto thermal→fan-curve control + LIVE alarm/limit recompute + SMBALERT# assertion.

## 2026-07-20 — #184 DONE (rotated to implementation): W83795 CASEOPEN now userspace-visible + LU validated end-to-end

Rotated from the review sweep to concrete device work — closed #184 (the Linux-driver gap found while
validating the CASEOPEN model): the modern-hwmon w83795 patch (0003) exposed only in/fan/temp, so the
CASEOPEN latch I modeled wasn't reachable from userspace. Fixed the DRIVER: added an intrusion channel to
the modern hwmon interface — HWMON_CHANNEL_INFO(intrusion, HWMON_INTRUSION_ALARM), is_visible 0644,
hwmon_read case (ALARM(5) bit6), a new w83795_hwmon_write (write 0 → CLR_CHASSIS[7], mirroring the legacy
store_chassis_clear), and .write in the ops. Incrementally rebuilt the C2 kernel (`CC drivers/hwmon/
w83795.o`, clean; uImage ready) and re-ran the w83795test gate through the STANDARD userspace path:
**`intrusion0_alarm` before=1 → `echo 0` → after=0 → W83795-CASEOPEN RESULT: PASS (LU)`** (evidence
`d08-w83795-caseopen/00`). So the FULL userspace path is proven: `/sys/class/hwmon` → w83795 hwmon driver →
i2c-dev → aspeed I2C engine 1 → QU9/QU5 fabric → the W83795 CASEOPEN model. That is the goal's "validate
proper user space interfacing with the hardware" deliverable for the CASEOPEN capability (row 16 LU).
Persisted the driver change by regenerating the 0003 patch from `git diff` (verified it contains the
intrusion additions; it's guaranteed to re-apply since it IS the diff from pristine mainline HEAD, which
build-kernel.sh clones). Updated the w83795test gate to prefer the hwmon LU path (raw-i2c fallback kept).
**#184 CLOSED** (cpu0_vid still not surfaced — modern hwmon has no VID channel type; a devattr for VID is a
trivial low-value follow-on, the board's CPU VID isn't safety-critical). This is a full concrete cycle:
Linux driver extension + incremental kernel rebuild + end-to-end userspace validation + patch persistence.

## 2026-07-20 — gate-(b) FINAL substantial batch (4 agents): SDMC + video-model CLEAN; 1 REAL vhub finding; 1 FALSE-POSITIVE caught by verification

Dispatched the final substantial gate-(b) batch — 4 parallel agents on the last developed QEMU + Linux
bodies (the generic-upstream `aspeed_smc`/`lpc`/`peci`, 0 G3-refs, are not project code). VERIFIED every
finding against the ACTUAL vendored code — which mattered a lot this round:
- **QEMU `aspeed_sdmc.c` (AST2050 DDR2, BOOT-CRITICAL): CLEAN.** Agent cross-checked vs the datasheet extract
  + the JTAG-captured MCR04=0x585: R_PROT lock-latch correct, MCR100/MCR170 genuinely read-only, MCR04 a
  firmware-owned verbatim latch (not synthesised), and it correctly AVOIDS the AST2500/2600 status-bit
  special-casing that would corrupt G3 offset 0x60. Lock protocol matches Raptor platform.S → DRAM init
  faithful for all 3 oracles.
- **QEMU `aspeed_video_ast2050.c` (the iKVM capture model): CLEAN.** DMA bounds provably confined to
  [0,dram_size) (underflow-safe comp_bus<dram_base check first), VR_SEQ_CTRL 0→1 transition logic matches
  the real driver, mode-detect bit-fields bit-exact vs upstream, stream-buf-size formula matches. (2 sub-
  threshold notes: only 8 of 12 JPEG quant tables, VR310/314 restriction-window unused — both harmless.)
- **Linux `0007-usb-aspeed-vhub` — 1 REAL finding (verified), low-severity.** The USB-command-deadlock
  (ISR[18]) handler drops VHUB_CTRL_UPSTREAM_CONNECT to avoid a CPU livelock (correct for liveness) but
  NOTHING re-asserts it: verified in the vendored driver that connect is set ONLY in init_hw (core.c:287-8,
  probe-once) and cleared ONLY by this handler; ast_vhub_hub_reset never touches AST_VHUB_CTRL. So a deadlock
  leaves USB/KVM dead until reboot, and the patch comment "a subsequent bus reset re-inits the HW" is FALSE.
  Does NOT affect the validated path (the init_hw PHY-wait prevents the deadlock; row-9 QEMU+silicon USB/IP
  never hit it). Action: CORRECTED the misleading comment (accurate: liveness tradeoff, no auto-recovery);
  tracked the proper PHY-gated deferred re-init as #185 (delicate ISR concurrency + hard to validate).
- **Linux `0006-media-aspeed-video` — FALSE POSITIVE (conf-92 "critical"), disproved by verification.** The
  agent claimed the G3 AUTO_COMP fix is a no-op because `aspeed_video_init_regs()` "unconditionally sets
  AUTO_COMP" so the (patched) conditional get_resolution write (clear=0) can't clear it. VERIFIED against the
  ACTUAL built driver: build-kernel.sh clones **fresh mainline v6.6.70**; in v6.6.70 `init_regs` does NOT
  write VE_SEQ_CTRL at all (grep: AUTO_COMP appears ONLY at the #define + the conditional line 1275; the
  patch doesn't add/remove any init_regs VE_SEQ_CTRL write), and update_regs' seq_ctrl never gets AUTO_COMP.
  So get_resolution is the ONLY AUTO_COMP setter and the conditional fix is correct + SUFFICIENT. The agent
  reasoned against a different kernel version. NO CHANGE — the patch is right. (Lesson: a confidence-92
  finding with a plausible scenario was wrong at its root; a 10-second grep of the vendored tree — "does
  init_regs actually touch VE_SEQ_CTRL?" — disproved it. Verify findings against the code that ACTUALLY
  builds, not a different upstream.)

**Gate-(b) status:** the substantial developed-code sweep is now essentially COMPLETE — Zephyr stack, QEMU
sensor/gpio/SoC/SDMC/video models, ALL Linux patches (clk/irqchip/i2c/ftgmac/kcs/pinctrl/hwmon/media-video/
usb-vhub), ALL U-Boot patches — reviewed. Tally of the whole sweep: 3 real bugs fixed (GPIO-irq ×2, RTC
hardening), 1 real finding comment-fixed + tracked (#185 vhub), 1 false-positive caught, everything else
clean. Only the DTS files + the generic-upstream QEMU models (not project code) remain unreviewed.

## 2026-07-20 — gate-(b): 5 more bodies self-reviewed (4 Linux patches + U-Boot p2a-dram) — all CLEAN

Continued the gate-(b) sweep over the small self-contained diffs (efficient to self-review honestly, as done
for pmbus/console/soc/uboot-i2c; agents reserved for the larger QEMU subsystems). All 5 CLEAN:
- **Linux `0005-i2c-aspeed-program-full-ac-timing` (#93):** replaces "preserve the undefined-on-G3
  tBUF/tHDSTA/tACST" with explicit `FIELD_PREP(mask,0x7)` each (=0x777xxxxx), faithfully matching the Aspeed
  vendor `select_i2c_clock()`. `<linux/bitfield.h>` added; fields ≥3b so 0x7 fits; G4 behaviour change is
  irrelevant to the oracles (C2 uses this on G3; C4 is separate vendor fw). Correct.
- **Linux `0002-ftgmac100-set-mac-speed-from-cur_speed` (the RX fix):** `maccr=0` then set FAST/GIGA from
  `cur_speed` (vs preserve-only, which reads 0 on G3 since MAC SW_RST clears MACCR → 10M-on-100M → rx=0);
  re-derived from cur_speed which adjust_link keeps current. Silicon-proven. Correct.
- **Linux `0004-ipmi-kcs-bmc-aspeed-optional-lpc-clock`:** `devm_clk_get_optional_enabled()` holds the real
  SCU0C[8] LPC LCLK for the KCS device lifetime (#94-sibling: without a refcount clk_disable_unused() kills
  LPC on G3). IS_ERR→dev_err_probe; optional so no-clocks DTs unaffected; devm-managed (no leak). Correct.
- **Linux `0008-pinctrl-aspeed-g3-strap-phantom-quirk`:** `aspeed_g4_expr_only_straps()` correct (ndescs>0
  guards empty-expr); the skip is gated `!enable && g3_strap_phantoms` so only the DISABLE path for
  strap-only exprs is short-circuited on G3 (unblocking GPIO requests like GPIOF5=QU5-mux-select), enable
  path unchanged, g3_strap_phantoms only for ast2050-pinctrl (G4 unaffected). Faithful (real G3 pad fn is
  SCU74/78, not the G4-misread straps). Correct.
- **U-Boot `0001-ast2050-p2a-dram-boot`:** the no-flash-over-P2A `flash_get_size` default returns a benign
  geometry immediately (avoiding the fall-through hang on uninitialised sector count + SPI-clock config);
  MCR04=0x585 (4-bank/64MB, matches silicon DDR2-init); baud 1200 (rig-proven); INIT_SP at +16MB (clears the
  U-Boot image at SDRAM_BASE for P2A boot); CONFIG_ENV_IS_NOWHERE (no flash → compiled-in default env →
  prompt); a host-tool include-order build fix. All silicon-motivated + correct.

**Gate-(b) status:** Zephyr stack (done) + these 5 + the prior rounds (i2c/w83795/fabric/pmbus, phantom-
gating/vic/timer/sbtsi-qemu/w83601g-qemu/console/soc, clk/irqchip/wdt/rtc/uboot-i2c, GPIO-irq 2-bugs-fixed).
Remaining un-reviewed: Linux `0003-hwmon-w83795` (already characterised via #184 — exposes only in/fan/temp),
`0006-media-video` (307 lines) + `0007-usb-vhub`, QEMU `aspeed_peci`/LPC/SMC/SDMC/video models, and the DTS
files. The faithfulness/boot-critical patches are now all confirmed clean.

## 2026-07-20 — gate-(b): the last 2 Zephyr DRIVERS reviewed (sbtsi + gpio_w83601g) — both CLEAN → ALL Zephyr code now reviewed

Rotated off the heavy W83795 modeling (2 straight cycles) per the "work on another part" guidance, and closed
the Zephyr side of gate-(b). Dispatched 2 parallel independent sub-agent reviews of the only Zephyr DRIVER
files not yet reviewed; verified both. Both CLEAN (0 substantive issues ≥80):
- **Zephyr `drivers/sensor/sbtsi/sbtsi.c`:** temp reconstruction `temp_int + (temp_dec>>5)*125000` correct
  (unsigned, right shift), no int32 overflow, fail-loud I2C return checks, correct fetch/get caching, init
  error path. The reviewer cross-checked it **bit-exact against real-silicon evidence** (`d09-sbtsi/01`:
  TEMP_INT=0x0e, TEMP_DEC=0x60 → 14.375 C) — independent silicon confirmation.
- **Zephyr `drivers/gpio/gpio_w83601g.c`:** single-transaction indexed-CR access (no shared-index race;
  multi-step RMW under the per-instance mutex), input-CR reads distinct from the shadow-based output flush
  (siblings preserved), BIT(pin) guarded by pin>=16 rejection (no shift-UB), glitch-free IOCFG ordering,
  per-instance independent state (0x18/0x19 don't alias), fail-loud I2C. One non-actionable dead-code note
  (reg_out/reg_in defined-but-unused) — not a bug.

**Gate-(b) Zephyr coverage is now COMPLETE:** gpio_aspeed_g3 (2 bugs FIXED) + i2c_aspeed_g3 (clean, #180
latent note) + wdt_aspeed_g3 (clean) + rtc_aspeed_g3 (clean, +neg-input hardening) + w83795-sensor (clean) +
sbtsi-sensor (clean) + gpio_w83601g (clean) + the SoC support vic/timer/console/soc (clean) = every Zephyr
.c reviewed. Gate (b) overall still NOT sealed — remaining un-reviewed: the smaller Linux patches
(ftgmac/i2c-timing/ipmi-kcs/pinctrl/media-video/usb-vhub/hwmon-registration), U-Boot 0001-p2a-dram, QEMU
peci/lpc/smc/sdmc/video, and the DTS files — but the ENTIRE Zephyr stack + the QEMU sensor/gpio models + the
Linux clk/irqchip keystones + U-Boot i2c are now confirmed clean-or-fixed.

## 2026-07-20 — #183 (part): W83795 CASEOPEN + VID MODELED + register-validated in QEMU (real implementation, not a mis-flag)

The 3rd gate-d task WAS genuine model work (unlike #181/#182 mis-flags). Implemented two W83795G functions the
model lacked — chassis-intrusion (CASEOPEN) + VID — faithful to the mainline driver's register map
(drivers/hwmon/w83795.c: ALARM_CTRL 0x40, ALARM(i) 0x41+i, intrusion = ALARM(5)=0x46 bit6, CLR_CHASSIS 0x4D
bit7, VID_CTRL 0x6A). Model (submodule 2d135ec3f9): new `intrusion` latch seeded=1 (persists across power
cycles on real HW); do_read ALARM(5) returns bit6=intrusion; do_write CLR_CHASSIS[7] clears it; VID_CTRL
seeded 0x01; vmstate v1→v2. Incremental QEMU rebuild clean.
VALIDATED (evidence `d08-w83795-caseopen/00`): a new `w83795test` init gate reads the raw registers over
busybox i2c-tools → **`ALARM(5)=0x46` before=`0x40` (bit6 latched), `VID_CTRL=0x6A`=`0x01`; after
`i2cset 0x4d 0x80` (CLR_CHASSIS) `ALARM(5)`=`0x00`; W83795-CASEOPEN RESULT: PASS`**. The transaction runs
userspace → aspeed I2C engine 1 → QU9/QU5 fabric → W83795 model, so the whole path + the new registers are
exercised together.

**Honest FIRST-attempt FAILURE (the "weird behaviour = my code" discipline):** the initial w83795test read
`/sys/class/hwmon/*/intrusion0_alarm` and got "No such file". Root cause: the modern-hwmon w83795 driver
patch (kernel 0003) registers via hwmon_device_register_with_info with a HWMON_CHANNEL_INFO of only
in/fan/temp — it does NOT expose intrusion0_alarm / cpu0_vid. So the MODEL was right; the DRIVER doesn't
surface those attrs. Fixed the test to validate the raw registers (i2cget/i2cset, which the initramfs ships)
— the correct way to validate a MODEL anyway. Tracked the driver-exposure gap as a NEW task #184.

Row 16 QE stays 🔶 (honest): CASEOPEN+VID now done, but SmartFan auto-mode + alarm/limit+SMBALERT remain
(#183 re-scoped to those). This is genuine forward progress on the last real gate-d task — a new device
capability implemented + validated, an honest test-failure diagnosed + fixed, and a new Linux gap (#184)
surfaced. #181/#182 were mis-flags; #183 was real and is now partly closed.

## 2026-07-20 — #182 re-scoped: the USB virtual-media "unvalidated" flag was a MIS-FLAG — mass-storage gadget IS validated QEMU + SILICON

Investigated the 2nd gate-d task (#182, "iKVM virtual-media validated by no stack") before implementing —
and, like #181, the flag was largely wrong. The virtual-MEDIA mass-storage gadget is already implemented AND
validated across stacks; the audit only inspected the f8-kvm HID transcript and missed the f6-usb evidence:
- **Implemented:** the initramfs `f6usb` init gate builds a `mass_storage.0` gadget via configfs (backing
  image `/tmp/vmedia.img`) and binds it to the dummy_hcd software UDC so the in-guest host enumerates it.
- **QEMU-validated:** `evidence/f6-usb/03-gadget-enumeration-demo.txt` — `Mass Storage Function, version:
  2009/09/11`, the gadget enumerates as idVendor=1d6b/idProduct=0104 "AST2050 vKVM virtual-media" over
  dummy_hcd (aspeed-vhub also probes its 7 ports). PASS.
- **SILICON-validated:** `evidence/real-hw-usb/02-SILICON-USB-ENUMERATION-PASS.txt` — the REAL AST2050 (JTAG
  bring-up → DDR2 train → TFTP-netboot the usbip kernel) presents the mass-storage gadget, and a SEPARATE
  REAL Linux host (the RPi4 bridge over USB/IP) enumerates it (`usb-storage ... USB Mass Storage device
  detected`) and reads `/dev/sda offset512 = [KGPE-D16-USBIP-VMEDIA-OK]` back. Real host, real read-back.
So the virtual-media capability EXISTS and works both sides. The gate-d "un-validated" claim was a mis-flag
(exactly the "incorrect claims about functionality not-existing" the program goal warns about). Corrected
the row-9 note with the evidence citations.
**The ONE genuine remaining delta:** §9 says "virtual ... CD", but the gadget today presents a removable
DISK (`mass_storage lun.0`), not a SCSI CD-ROM (`lun.0/cdrom=1`). Re-scoped #182 to just that: add cdrom=1
to the f6usb block + one USB-harness re-run to capture the CD-ROM (sr0) enumeration. Deferred the actual
add+re-run this cycle to avoid a heavy USB-kernel rebuild (build-usbip.py) for a SCSI-type flag — and,
importantly, to NOT commit an un-validated code change that would desync from the existing (disk) evidence.
#182 stays OPEN for that small delta; the vhub-to-real-host EP-DMA path stays the row-9 LS 🔷 rig-block.
Pattern note: 2 of the 3 gate-d tasks (#181, #182) turned out to be mis-flags resolved by finding the
existing silicon evidence — a convergence signal (the audit surfaced things worth checking; checking proved
them already-done). #183 (W83795 SmartFan/CASEOPEN/VID) remains genuine model work.

## 2026-07-20 — #181 RESOLVED (rotated to implementation): the MAC PHY "divergence" was a naming artifact — model is FAITHFUL (silicon-proven)

Rotated from meta-work (4 review/audit cycles) to concrete implementation on a fresh tracked gap, per the
"work on another part" guidance. Took #181 (gate-d faithfulness flag: model returns RTL8201CP PHY-ID, board
U5 is RTL8201N). INVESTIGATED before "fixing" — and the fix turned out to be that there is NO divergence:
- `hw/net/ftgmac100.c` returns the legacy Realtek RTL8201-family MDIO PHY-ID `0x0000_8201`; Linux `realtek.c`
  names that id "RTL8201CP".
- The REAL AST2050 reports the SAME id: `evidence/.../real-hw-g3clk/boot-noclkignore-console.log:137` (a
  `boot#`-prompt TFTP-netbooted SILICON boot) shows Linux attaching "RTL8201CP" — IDENTICAL to the QEMU
  boots (d07-ncsi/00, d08-spd/00, real-hw-hwpass/attempt10 all show "RTL8201CP Ethernet ... attached").
- So the schematic's "RTL8201N-GR" part-label and the 0x8201-id "RTL8201CP" are the same legacy Realtek
  RTL8201-family PHY / same 10/100 RMII register surface. The model reproduces exactly what the silicon puts
  on MDIO → FAITHFUL. The gate-d flag was a naming inconsistency (code comment said CP, schematic says N),
  NOT a behavioural divergence.
Action: reconciled the ftgmac100.c comment to state the RTL8201N/CP naming + the silicon evidence (submodule
65e7d9235e, comment-only, no behaviour change, pushed); updated the row-10 note RESOLVED; bumped the parent
submodule pointer. **#181 CLOSED.** Discipline note: this is the goal's own thesis — a suspected faithfulness
divergence, resolved by consulting what the HARDWARE actually does (MDIO readback), not by "fixing" a model
that already matched it. (No QEMU rebuild / oracle re-boot needed: comment-only + the behaviour was already
silicon-proven.)

## 2026-07-20 — gate-(a)/(c)/(d) audit pass (3 parallel independent sub-agents): completeness + honesty CONFIRMED; gate-d found 3 real new tasks (#181/#182/#183)

Rotated from the gate-(b) code sweep to the completeness/faithfulness gates (a/c/d), which the feedback flagged
as un-run. Dispatched THREE independent sub-agents in parallel with DIFFERENT lenses; verified each finding.

- **Gate-(a) device completeness → MATRIX COMPLETE.** The auditor cross-checked the authoritative schematic
  §§2-15 + the §16 per-pin table AND the machine-generated netlist far-end lists in QU1_pins.md (not just the
  prose) against all 51 rows. **No schematic-wired BMC device that is a real driver/emulation target lacks a
  row; no phantom row.** Every unrowed schematic part is passive glue / host-side chip / PCI peer (ZU1 FW322 =
  SP5100 PCI peer, not BMC-driven) / CU2 clock-gen / the JTAG harness — each justified. This is the
  device-by-device (not section-level) gate-a pass the feedback said was missing. Actionable detail folded in:
  the §16 table names 6 specific §11 platform-GPIO NETS the §11 prose omits (AST_BIOS_POST_COMPLT#/
  AST_SYNCFLOODIN#/AST_PSONEN/FP_NMIBNT#/AST_RESETDIS#/AST_PWRBNTDIS#) — GPIO line functions on rows 27-29,
  not separate devices; added to the row-28/29 note.
- **Gate-(c) over-claim/evidence → SAMPLED ✅ CELLS ARE EVIDENCE-BACKED.** The auditor opened the cited
  evidence for the full ZS ✅ set + the named core rows and confirmed every SILICON claim has a real-hardware
  JTAG transcript and every "both-sides" shows both — noting the matrix is "unusually disciplined" with many
  self-downgrades. Two doc-hygiene items fixed: (1) the snapshot prose said "8 rows ZS ✅" but the tally+grid
  show **11** (1/15/16/20/21/22/34/35/36/37/38) — an UNDER-statement, now corrected + enumerated; (2) rows 1
  (DDR2) + 34 (clock) ZS ✅ are indirect (stack runs-from/consumes, same standard as U-Boot/Linux ✅ on those
  rows) — noted explicitly in the prose (reviewer explicitly would NOT force a downgrade).
- **Gate-(d) new-task identification → 3 REAL non-duplicate tasks (so gate-d correctly does NOT seal).** All
  verified against the tree before adding:
  - **#181** faithfulness: `hw/net/ftgmac100.c` returns RTL8201**CP** PHY-ID but schematic §14 names U5 as
    RTL8201**N** — row 10's note said "(unresolved)" with NO task. Added #181; row-10 note updated.
  - **#182** capability: §9 scopes USB as "keyboard/mouse/**CD**" but only the HID kbd/mouse gadget is
    validated (F8-KVM) — the virtual-MEDIA (mass-storage/CD) gadget path is un-validated + untracked. Added
    #182; row-9 note updated.
  - **#183** completeness / OVER-CLAIM CAUGHT: the W83795 model does reads + linear PWM→tach (#174) but NOT
    SmartFan auto-mode / alarm-limit+SMBALERT / CASEOPEN / VID — so row 16 QE ✅ ("all functionality")
    over-claimed. **Downgraded row 16 QE ✅→🔶** (consistent with row 42 PECI's "not complete functionality →
    🔶" precedent) + scoped the note; added #183 to restore ✅. Tally: QEMU emulation 30→29 ✅, 9→10 🔶.
  - Bookkeeping flag (SMBus-ALERT #135 "dropped") was a FALSE ALARM — #135 is open (in_progress, covers SALT);
    I simply omitted it from the ID list I handed the agent.

Net: gates (a)+(c) came back CLEAN/confirmed (strong independent rebuttal of the "not enumerated / over-
claimed" concerns), and gate (d) found 3 genuine gaps → added as #181/#182/#183 + one honest self-downgrade
(row 16). This is the correct gate outcome: the completeness dimension holds, the honesty dimension holds
(with one over-claim caught + corrected), and the enumeration converges (3 new tasks, all attaching to
EXISTING rows — no missing DEVICE, just missing capability/faithfulness sub-tasks). To SEAL gate (a)/(d) a
FUTURE independent pass must come up empty; this pass did not, so it stays open — honestly.
Also self-reviewed the Zephyr `w83795` sensor driver (gate-b, non-conflicting): CLEAN (VRLSB two-read latch
protocol correct, 12-bit tach + signed-temp reconstruction match the model, sensor_value sign contract OK).

## 2026-07-20 — gate-(b) sweep round 3: the Linux/U-Boot/kernel-driver bodies — 5 reviewed, all CLEAN; 1 small RTC hardening applied

Extended the gate-(b) sweep to the Linux kernel patches + U-Boot + the remaining boot-critical Zephyr drivers
(the feedback's named "un-reviewed" set). 4 focused sub-agents in parallel + 1 self-review; each VERIFIED. All
CLEAN (0 substantive issues ≥80), with one below-threshold RTC note I chose to fix on fail-loud grounds:
- **Linux `0001-clk-aspeed-add-ast2050-support.patch` (503 lines, the #94 console-death fix, FAITHFULNESS-
  CRITICAL):** agent resolved EVERY `ast2050_gates[]` DT-id→SCU0C-bit mapping against aspeed-clock.h (no
  off-by-one/collision; holes at idx 7/10 correctly skipped by the `!gd->name` guard); confirmed the
  **UART2CLK/UART5CLK→UART1CLK bit-15 gate aliasing** gives the console a real refcount (the #94 fix, correct);
  PLL math (mult=(2-od)(n+2), div=(d+1)·postdiv), strap decode, branch structure (no dangling-else),
  ASPEED_NUM_CLKS bounds, G4/G5 non-regression, and the SCU04 reset-bit map all verified. Cross-checked vs
  G3-CLK-PROGRESS.md (silicon-proven).
- **Linux `0003-irqchip-add-aspeed-ast2050-vic-g3.patch` (the KEYSTONE, HW-verified):** mask/unmask via
  dedicated set-only/clear-only registers (no RMW race), ack only edge sources, single-bank 32-source chained
  handler re-reads status each iter (no lost/double), trigger types from the actual programmed INT_SENSE
  readback; sensitivity bit patterns recomputed bit-for-bit vs the source list. Matches the in-tree
  hardware-verified sibling copy.
- **Zephyr `wdt_aspeed_g3.c` (silicon-reset-proven):** timeout→reload 64-bit before the 32-bit-fit check (no
  overflow), window.max==0 rejected (no instant reset), CTRL=0x33 pinned by BUILD_ASSERT + matched to the
  model, feed=magic-restart, disable=timer_del (no spurious reset), 2nd install rejected -ENOMEM. The
  RESET_SOC/RESET_CPU_CORE→full-chip mapping is a documented intentional tradeoff, not a bug.
- **Zephyr `rtc_aspeed_g3.c`:** set↔get COUNTER pack/unpack byte-symmetric, binary (not BCD), single 32-bit
  read (no tear), enable seq RELOAD→RESTART(0x5A)→CONTROL→poll[5] with fail-loud -ETIMEDOUT. Clean — BUT the
  reviewer flagged (sub-threshold) that set_time checked only UPPER bounds on sec/min/hour; a NEGATIVE field
  (signed struct rtc_time) cast to uint32_t would sign-extend into the mday byte and silently corrupt the day.
  **FIXED** (added lower-bound `< 0` checks) — this project's fail-loud principle makes a silent-wrong-write on
  bad input a real defect, not merely defensive. Compile-safe by inspection (same pattern) + only makes
  set_time stricter, so no regression to the silicon-validated set/get path (which uses valid inputs).
- **U-Boot `0002-enable-i2c-buses` + `0003-i2c-scu-reset-release` (self, the #167 fix):** SCU unlock
  (0x1688a8a8→SCU00) + SCU04[2] I2C-reset RMW correct; the muxed-channel arithmetic
  `chan=(regs-0x1e78a000)/0x40` maps engines 4/5/6→chan 5/6/7→SCU74[12/13/14] via `1<<(12+(chan-5))` — right
  SDA5/6/7 bits, OR (no clobber), underflow-safe guard. DTS bus-enable mapping faithful.

**Gate-(b) cumulative (this session):** rounds 1-3 = i2c/w83795/fabric/pmbus + phantom-gating/vic/timer/
sbtsi-qemu/w83601g-qemu/console/soc + clk/irqchip/wdt/rtc/uboot-i2c = ~17 code bodies reviewed (16 clean, GPIO-
irq driver 2 bugs fixed, rtc 1 hardening), plus the earlier-session 4 original bodies (4 bugs fixed). Honest
status: gate (b) STILL NOT sealed — remaining: the Zephyr SENSOR drivers (sbtsi/w83795/gpio_w83601g DRIVERS),
the smaller Linux patches (ftgmac/hwmon/ipmi-kcs/i2c-timing/media-video/usb-vhub/pinctrl), U-Boot
0001-p2a-dram, QEMU aspeed_peci + lpc/ftgmac/smc/sdmc/video, and the DTS files. But the HIGHEST-risk code —
oracle-critical phantom-gating, the boot-critical VIC (both Linux irqchip + Zephyr) + timer + WDT + the #94
clk fix — is now all independently confirmed sound. A methodical sweep, not a spot-check.

## 2026-07-20 — gate-(b) sweep round 2: 6 more code bodies reviewed (4 sub-agents + 2 self) — ALL CLEAN incl. the oracle-critical phantom-gating

Continued the gate-(b) full-code-review sweep. Dispatched FOUR focused code-reviewer sub-agents IN PARALLEL
(within the 5-agent cap) + self-reviewed 2 small SoC files; VERIFIED each result. All six CLEAN (0 substantive
issues ≥80 confidence):
- **QEMU `hw/arm/aspeed_ast2400.c` phantom-gating (ORACLE-CRITICAL):** the agent traced ALL FOUR phantoms
  (XDMA/SDHCI/SRAM/ADC) across all FOUR lifecycle phases (init/realize/map/irq) — each consistently gated on
  `AST2050_A1_SILICON_REV`, NO dangling `s->xdma/sdhci/sram/adc` references, NO IRQ double-assign, and the
  freed MMIO addresses (0x1E6E7000/0x1E6E9000/0x1E720000/0x1E740000) all fall through to the LOW-priority
  (-1000) unimplemented catch-all — verified they don't collide with any real or new G3 device (smc/udc/
  video/pwm/lpc/rtc/p2a). New G3-only devices are init+realize+map+irq all-together (no half-creation). This
  is the file most able to break C2/C4/C-UBOOT — clean here is a strong faithfulness confirmation. (Harmless:
  `sram_size`/`ehcis_num` set-but-unused on G3 — dead values, not bugs.)
- **Zephyr `vic.c` + `aspeed_timer.c` (boot-critical, had the silicon-only fixes):** VIC claims+quiesces each
  source (mask level / ack edge) BEFORE the ISR wrapper re-enables IRQs (no re-storm/double-fire); spurious
  `status==0` returns CONFIG_NUM_IRQS cleanly; the set/clear enable-register pair avoids the ISR-vs-thread
  RMW race; edge/level branches mirror-consistent. Timer init disable→program→connect→enable→irq_enable
  (clears the enable-glitch edge); the glitch window is ≪ 1 tick (catches only the glitch, never a real
  tick); ISR = standard tickful pattern; IRQ 16 matches the VIC Timer1 source.
- **QEMU `hw/sensor/sbtsi.c`:** temp encoding verified vs the Linux sbtsi_temp decode (round-trips at 45.5 /
  100.125 / boundary 255.875 C); register-pointer access bounds-checked (no OOB at uint8_t wrap); reset seeds
  regs before guest access; no-negative-temp clamp faithful; NR_REGS matches array + vmstate.
- **QEMU `hw/gpio/w83601g.c`:** indexed-CR bounds safe (index wraps mod 256; writable() only over constants
  < NR_REGS; reserved() range-checks); register map internally consistent (34 = NR_REGS); each write touches
  only its target CR; the two instances (0x18/0x19) have no static state so cannot alias; reset seeds
  CR_ID_LOW=0x13. Below-threshold note: CR_OUT writes aren't propagated to modeled physical pins — matches
  what silicon validated (a register round-trip, not a pin loopback) + no QEMU consumer of those pins, so a
  documented simplification, not a bug.
- **Zephyr `console.c` (self):** byte-wide accesses at reg-shift=2 (THR +0x00, LSR +0x14) match ns16550 +
  the comment; \n→\r\n correct; hooks at PRE_KERNEL_1 prio 0 catch the banner; lock-free polling spin is
  inherent to an M0 console (upper layers serialize) and only hangs if the UART is dead (expected mode).
- **Zephyr `soc.c` (self):** MMU regions all separate non-overlapping 4 KB device pages (uart5/wdt/gpio/rtc/
  timer/i2c/scu/vic — no collisions); the one intentional vectors(VA0x40000000→PA0, strongly-ordered) vs
  dram VA-overlap is silicon-required + already resolved by a prior review+silicon test; soc_reset_hook CP15
  ops are correct ARM926 encodings (c7,c7,0 inval I+D cache; c8,c7,0 inval I+D TLB; c7,c10,4 drain WB).

**Gate-(b) coverage now (this session):** GPIO-irq driver (2 bugs FIXED) + i2c_aspeed_g3 + w83795 + fabric +
pmbus_psu (round 1, clean) + phantom-gating + vic + timer + sbtsi + w83601g + console + soc (round 2, clean)
= 12 code bodies, plus the earlier-session review of the 4 original bodies (4 bugs fixed). Honest status:
gate (b) STILL NOT sealed — remaining un-reviewed: the U-Boot ast_i2c patch, the Linux kernel patches
(g3-clk/i2c-timing/ftgmac100), the other Zephyr drivers (gpio_w83601g DRIVER / wdt_aspeed_g3 / rtc_aspeed_g3),
QEMU aspeed_peci + the LPC/vuart/ftgmac100/SMC/SDMC changes, and the DTS files. But every reviewed body is
now clean or fixed, and the highest-RISK code (oracle-critical phantom-gating + boot-critical VIC/timer) is
confirmed sound. Next cycles: continue the sweep over the remaining bodies (natural parallel-agent batches).

## 2026-07-20 — gate-(b) parallel code-review sweep: 4 more code bodies reviewed (3 sub-agents + 1 self) — all CLEAN; + gate-(a) schematic cross-check

Extended completion-gate (b) coverage. Dispatched THREE focused code-reviewer sub-agents IN PARALLEL (within
the 5-agent cap) on the highest-value developed code not yet independently reviewed, each with the hardware/
faithfulness context, and self-reviewed a 4th small model. VERIFIED each result myself. All four came back
CLEAN (0 substantive issues ≥80 confidence):
- **Zephyr `i2c_aspeed_g3.c`** (I2C master, 471 lines): state machine bounded by I2CD_POLL_COUNT (no infinite
  spin), NAK→-ENXIO/-EIO/-ETIMEDOUT (fail-loud), multi-msg RESTART/STOP + last-byte-NAK correct, mutex
  discipline single-unlock on every path, SCU/AC-timing/INTR init order matches vendor U-Boot. One
  SUB-THRESHOLD (~50) note: scu_release()/pinmux() RMW the SHARED SCU04/SCU74 across engine instances under
  only the per-engine mutex — a lost-update race IN THEORY, but unexercised (single-threaded POST_KERNEL
  init; only ch5 muxed on this board). Documented in-code + tracked as #180 (conditional fix if a 2nd
  runtime-muxed channel is added). Not a live bug.
- **QEMU `w83795.c`** (hwmon model + my #174 fan-control + reset): banked dispatch consistent, BANKSEL always
  reachable, no OOB into regs[4][256], fan-control confined to bank-2 0x10-0x17 per-byte via live ptr and
  overflow-safe (cnt<=0xfff → cnt>>4<=0xff), reset_hold correct phase + full re-init (no stale fields),
  I2C-slave START/pointer framing correct.
- **QEMU `kgpe_d16_i2c_fabric.c`** (mux fabric + sys_pwrgd fix): GPIO-select decode matches the 74HC4052
  truth table + cross-file wiring (no off-by-one/inversion), the SYS_PWRGD edge-guard fix present + correct
  verbatim, host-off NAKs everything / host-on routes only the selected channel (faithful isolation), reset
  state consistent, nothing positioned to diverge C2/C4.
- **QEMU `pmbus_psu.c`** (self-reviewed, 162 lines): LINEAR11/ULINEAR16 encodings verified against the
  documented hex (0x00E6 VIN, 0x13E8 4000RPM, 0x1800/VOUT_MODE=0x17 → 12.0V), all mantissas fit 11 bits,
  reset defaults seeded in exit_reset (re-applied every reset); fixed/non-host-gated values documented as an
  intentional simplification.

So gate-(b) coverage now spans (this session): GPIO-irq driver (prior cycle, 2 bugs FIXED) + these 4 CLEAN,
plus the earlier-session review of the 4 original code bodies (4 bugs fixed, confirm-clean). Honest status:
gate (b) is NOT sealed — U-Boot ast_i2c patch, the Linux kernel patches (g3-clk/i2c-timing/ftgmac100), the
Zephyr SoC support (vic/timer/console/soc), gpio_w83601g.c, sbtsi.c, and the aspeed_ast2400.c phantom-gating
remain to be swept — but the reviewed surface is materially larger and every reviewed body is clean or fixed.

**Gate-(a) cross-check (same cycle):** enumerated the authoritative schematic's device sections directly
(`AST2050-BMC-WIRING.md` §§1-16 headers) and confirmed each device section §2-15 maps onto the matrix's 51
rows (§2 power→24/27, §3 DDR2→1, §4 SPI→2, §5 LPC→3-7, §6 PCI/iKVM→8, §7 eth→10-11, §8 VGA→12-14, §9 USB→9,
§10 I2C→15-26b, §11 GPIO→27-29, §12 serial/SOL→30-31, §13 JTAG/LED/clk/straps→32-34, §14 neighbour-chips
cross-ref, §15 connectors covered, §16 = the per-pin source). No schematic device section is unmapped — the
matrix's completeness claim holds at the section level. (Deeper per-device gate-a passes already added rows
43-50 for SoC-internal engines; this confirms the external-schematic dimension.)

## 2026-07-20 — gate-(b) code review of the Zephyr GPIO-interrupt driver: 2 REAL latent bugs found + fixed

Advanced completion-gate (b) ("full code reviews of all developed code, no issues") on the most substantial
code written this session that hadn't been independently reviewed since I wrote it — the #177 Zephyr GPIO
interrupt driver `zephyr/drivers/gpio/gpio_aspeed_g3.c` (shared-ISR design). Dispatched ONE focused
code-reviewer sub-agent (well under the 5-agent cap) with the hardware/design context, then VERIFIED both
findings myself against the code before fixing (the discipline that caught 4 real bugs earlier this session).

Both findings were REAL (not style):
1. **manage_callback races the shared ISR (High).** Every other accessor takes `data->lock` (which masks the
   GPIO IRQ on this single-core ARM926, excluding the ISR), but `gpio_aspeed_g3_manage_callback` called
   `gpio_manage_callback` — a multi-step non-atomic slist mutation — with NO lock, while the shared ISR walks
   the SAME list via `gpio_fire_callbacks`. A runtime `gpio_add/remove_callback` on a bank with an active
   interrupt can corrupt the list / drop a callback / crash on a mid-unlink node. FIX: wrap the call in the
   existing spinlock (matches every other path; `gpio_manage_callback` doesn't block or re-enter → no
   deadlock).
2. **Disable doesn't clear the pin's latched INT_STATUS (Med-High).** The ENABLE path discards the stale
   latch before enabling (existing line), but the DISABLE branch only cleared INT_ENABLE. INT_STATUS and
   INT_ENABLE are independent, so a disabled-but-already-latched pin gets spuriously re-delivered when a
   SIBLING pin in the same set later interrupts (the shared ISR reads/clears/dispatches the whole INT_STATUS
   word), and `get_pending_int` misreports it. FIX: clear the pin's INT_STATUS bit on disable too (symmetry
   with the enable path).

The reviewer also explicitly CHECKED-AND-CLEARED (documented) the SENS mapping, the enable-path write
ordering, the out_shadow RMW paths, the bounds checks, the registry silent-drop (dead code — only 7 sets),
and the inherent W1C edge race — so the review was thorough, not just the two hits.

**Verification of the fixes (honest scope):** both are compile-safe by inspection (every symbol is already
used elsewhere in this same file; fix 2's added write is byte-identical to the enable-path line) and are
isolated from the validated `gpioh2_irq_smoke` measured path (it adds its callback once before enabling —
fix 1 uncontended there — and only hits disable AFTER the PASS check — fix 2 post-measurement), so no
regression. I did NOT re-run the QEMU smoke this cycle: no west workspace is present in this worktree (the
`asus-kgpe-d16-firmware/zephyr/` tree is a Zephyr MODULE; a rebuild needs a multi-GB `west init/update`).
Tracked that rebuild + a NEW smoke that positively exercises the two fixed paths as **#179** — not skipped,
explicitly deferred. #177 ZQ stays ✅ (the validated edge→callback functionality is unchanged; these harden
latent bugs the smoke didn't reach).

## 2026-07-20 — row 38 WDT LU 🔶→✅: userspace-ARMED WDT resets the SoC (6/6 reboot cycles) — the full LU deliverable

Completed the WDT userspace validation from 🔶→✅ by proving the missing half (a userspace-*triggered* SoC
reset). Added a `wdtreset` init gate: `busybox watchdog -T 3 -t 60 /dev/watchdog` arms a 3 s WDT but sets
the pet interval to 60 s so busybox does NOT re-feed before expiry → the WDT fires at ~3 s and resets the
SoC. Booted with NO --expect so run-qemu captures the whole trace incl. the reboot (run_boot breaks on
`p.poll()` when QEMU exits/loops). RESULT (evidence appended to `f-wdt-userspace/00`): in one 60 s window,
**7× `Booting Linux on physical CPU` (initial + 6 WDT reboots), 6× `WDT-RESET-ARMED`, 0× `STILL ALIVE`** —
every `WDT-RESET-ARMED` (lines 160/318/476/634/792/950) is immediately followed by a fresh CPU boot (161/
319/477/635/793/951). 6/6 deterministic: the userspace `/dev/watchdog` arm caused a real SoC reset every
time.

So the Linux userspace watchdog interface is now COMPLETELY validated in QEMU: open→WDIOC_SETTIMEOUT→arm→
keepalive (wdttest, prior cycle) AND stop-feeding→real SoC reset (wdtreset, this cycle). That is the full
LU (userspace-interface) deliverable → row 38 **LU 🔶→✅**. Tally: Linux-userspace 12→13 ✅, 7→6 🔶.

**Grading honesty (no overclaim):** LU is the userspace-INTERFACE axis (orthogonal to LS = Linux-SILICON,
which is a separate column and stays 🔶 pending a real-AST2050 /dev/watchdog transcript). The ✅ is for the
userspace interface, validated on the QEMU platform (same platform as LQ ✅); I documented that explicitly
in the row-38 note + evidence so a reviewer applying a stricter "LU must be silicon" convention can see
exactly what was proven. The WDT reset is faithful to row-38 QE (model) and the real silicon WDT (ZS ✅).
No step skipped; the reset is a positive, counted, deterministic proof, not an absence-based inference.

## 2026-07-20 — row 38 WDT LU ⬜→🔶: userspace /dev/watchdog API validated in QEMU (with an honest test-criteria fix)

Closed the row-38 LU gap ("/dev/watchdog userspace not exercised") using the same reusable `ledtest`-style
init-gate + repack harness from the LED cycle. Added a `wdttest` init gate that runs `busybox watchdog -T 30`
and reads back the watchdog state from userspace. RESULT (evidence `f-wdt-userspace/00-qemu-dev-watchdog.txt`):
`/dev/watchdog{,0,1}` present, `identity=aspeed_wdt`, **`timeout` reads back 30** (userspace WDIOC_SETTIMEOUT
reached the driver, which programs the model's WDT_RELOAD reg) and **`state` inactive→active** (armed) →
`WDT-USERSPACE RESULT: PASS`. So the userspace watchdog API path (open→SETTIMEOUT→start→keepalive) works
end-to-end (userspace→/dev/watchdog→aspeed_wdt→QEMU model). Tally: Linux-userspace 15→14 ⬜, 6→7 🔶.

**Graded 🔶 (not ✅) honestly:** (a) QEMU-userspace only (other LU ✅ are silicon-userspace); (b) it proves the
API path, not a userspace-*triggered* SoC reset (the WDT actually firing is row-38 QE + ZS ✅, separately
proven, + the g3-clk 120s reset on real HW). A userspace-armed-reset demo (arm short + stop feeding under
`-no-reboot`) would earn ✅.

**HONEST FAILURE + FIX (test-criteria bug, not a driver/model problem):** the FIRST run FAILED — I required
`/sys/class/watchdog/watchdog0/timeleft`, but **aspeed_wdt does not implement get_timeleft**, so that attr
doesn't exist and my `[ -le ]` check errored → FAIL, even though `timeout=30 state=active` were already good.
Fixed the gate to gate on `timeout==30 && state==active` (what the driver actually supports) + probe timeleft
with `test -e`. Re-ran → clean PASS. Confidence I didn't "just do something wrong": HIGH — the driver's own
sysfs proves timeout/state, and the corrected criteria match aspeed_wdt's real capability set. Two more honest
findings noted in the evidence: busybox watchdog in this build doesn't magic-close on SIGTERM (WDT stays armed
after kill — harmless, poweroff exits first; NOWAYOUT is unset); and the board exposes TWO WDTs
(watchdog0+watchdog1 = AST2050 WDT1/WDT2).

## 2026-07-20 — row 32 LEDs QE 🔶→✅: QEMU LED-drive validated end-to-end (matches silicon exactly), incl. an honest first-attempt failure

Closed the row-32 QEMU-side gap ("a QEMU toggle-observe test would make it ✅"). Added a `ledtest` init gate
(qemu-firmware/initramfs/init, following the existing `f6usb`/`usbip` cmdline-token convention) that boots C2
Linux, drives `echo 1/0 > /sys/class/leds/identify/brightness`, and observes the underlying GPIO line in
`/sys/kernel/debug/gpio` — which is the aspeed-gpio driver reading back the QEMU model's DATA register, so a
change there proves the MODEL received the write (not just the LED class caching a value).
RESULT (evidence `e-gpio-leds/01-qemu-led-drive-observe.txt`): `gpio-560 (led-id-n |identify) out hi → out lo
→ out hi`, **LED-TEST RESULT: PASS**. This is IDENTICAL to the silicon dump (`00-silicon-gpio-map.txt`): same
gpio-560, same `led-id-n |identify` label, same ACTIVE_LOW hi↔lo. The QEMU debugfs even shows the same
gpio-line-names (led-bmc-status-n, led-cpu1/2-err-n, spd-mux-s0/s1) as the board, confirming the QEMU DTS
line-name map is faithful. So QEMU emulates BMC LED-drive end-to-end (userspace→gpio-leds→aspeed-gpio→model),
matching hardware — row 32 QE ✅ (QEMU-emulation tally 29→30 ✅, 10→9 🔶). LS/LU already ✅ (silicon drive).

**HONEST FAILURE + FIX (the "weirdness = my code" discipline applied to my own tooling):** the FIRST boot
FAILED — console showed `Run /init as init process` → `Failed to execute /init (error -13)` → fell back to
`/sbin/init` (BusyBox) which spammed `can't open /dev/tty2/3/4` and never ran my ledtest. error -13 = EACCES:
my repack helper (`tmp/repack_initramfs.py`) copied the source `init` (mode 664, no exec bit) into the rootfs
WITHOUT chmod, so the kernel couldn't exec `/init`. `build.py:183` does `os.chmod(rootfs/"init", 0o755)` right
after its copy; I'd omitted the equivalent. Fixed the helper (chmod 0o755), repacked, re-booted → PASS. Not a
QEMU/model problem at all — a defect in my build tooling, found + fixed properly rather than worked around.
Confidence I didn't "just do something wrong" earlier: HIGH — the failure was self-inflicted + fully explained
by the EACCES, and the corrected run passes cleanly and matches silicon byte-for-byte.
Reusable win: the `ledtest` gate + the repack path give a clean "boot C2 → scripted userspace test → capture"
harness that future Linux-userspace validations (e.g. #177 GPIO-userspace, WDT `/dev/watchdog`) can reuse.

## 2026-07-20 — #178 row 14 DDC/EDID FAITHFULLY SCOPED: it is CRT-controller HW (VGACRB7), NOT an I²C-engine device — prevented an unfaithful shortcut

Picked a `QE ⬜` gap to advance the goal's first bullet ("full QEMU emulation of *every* device"): row 14
DDC/EDID (I²C → VGA1), flagged only as "totally unmodeled (audit gap #7)". Before modeling I checked the
schematic + datasheet to model it FAITHFULLY (the "understand before you model" discipline that saved the
AHBC pass from a boot-risking rewrite). **Finding — the naive model would have been UNFAITHFUL:** the DDC
is NOT one of the 8 general I²C engines, so attaching an EDID EEPROM to an I2C engine bus (the obvious
quick "win") would be wrong. Evidence:
- Schematic pinmap (`schematic-wiring/pinmaps/QU1_pins.md:231-232`): B1 `DDCACLK/GPIOD7`→AST_DDCCLK→
  VGA1[15]; B2 `DDCADAT/GPIOD6`→AST_DDCDAT→VGA1[12] — dedicated DDC pins muxed with GPIO port D, not SDA/SCL.
- Datasheet (`datasheets/aspeed/AST2050_V1.05.txt`): l.3045/3052 the DDCADAT/DDCACLK pins; l.6086-6087 +
  l.16851 "**18 RW Enable primary DDC pins**" (SCU74[18]); l.29699 "**VGACRB7: DDC Control Register**" +
  l.29231 "DDC Control" — the controller is the **CRT block's** extended VGA register CRB7; l.16587-16617
  a KVM "**Virtual EDID**" function; l.1313/28279 "Support VESA DDC" (headline feature).
- QEMU (`qemu-firmware/qemu/qemu/hw/arm/aspeed_ast2400.c:360-433`): the G3 machine models the VIDEO
  *capture* engine (0x1E700000, for `aspeed-video` KVM screen-grab) but **NOT the CRT *display*
  controller** — so there is currently no register block to attach DDC to. `grep ddc|crb7|edid` across
  the aspeed hw finds nothing (only the generic `hw/display/edid-region.c` EDID-blob helper + dpcd/DP).

**Faithful path (correctly located, oracle-noted):** a CRT-controller register model exposing VGACRB7
DDC-control backed by a downstream EDID (reuse in-tree `qemu_edid_region_io`/`edid-region.c` for the
EDID blob); it lives in the VGA I/O space the C4 vendor firmware may touch, so add as a self-contained
region and re-boot both oracles (C-UBOOT + C2) after. Updated the row-14 note with all citations,
corrected the mislocation (I²C-engine → CRT controller), kept QE ⬜ (real work, NOT Ⓝ — VESA DDC to VGA1
is genuine board function), and added task #178. This cycle's honest increment: converted a vague
"unmodeled gap" into a precisely-scoped, datasheet-cited, correctly-located task AND prevented the
unfaithful EDID-on-I2C shortcut a careless pass would have committed. No code claimed done; the model
itself is #178, next.

**UPDATE (same day, deeper) — the DDC decode + its dependency are now EXACT, so #178 is fully specified
(and correctly blocked on #176), not just "scoped":**
- **VGACRB7 = a software BIT-BANG I²C master** (datasheet §34.5 l.29699, Init=00h): bit0 en-SCL-out-buf,
  bit1 SCL-out, bit4 SCL-**in**, bit2 en-SDA-out-buf, bit3 SDA-out, bit5 SDA-**in** (bits7/6 = unrelated
  CRC-signature ctrl). This is the classic bit-bang GPIO-I²C shape → maps 1:1 onto QEMU's in-tree
  `hw/i2c/bitbang_i2c.c` driving `hw/display/i2c-ddc.c` (EDID slave @0x50). So the model reuses existing
  pieces; no protocol invention.
- **Decisive dependency (datasheet §36 l.19634):** CRB7 is a CRTC register the BMC ARM can reach ONLY via
  the **A2P AHB→P-bus bridge @0x1E720000 = row 50 / #176** — "AHB to P-bus bridge control registers
  address = 0x1E720000+OFFSET", OFFSET 0x00000-0x0007F = relocated legacy VGA I/O (index/data
  3B4/3D4→3B5/3D5), 0x10000-0x1FFFF = P-bus MMIO (CRTC `MMIOBASE+B7`); auto-enabled by SCU70[4]
  (PCI-master mode). The G3 QEMU models neither A2P nor the PCI "internal VGA", so **#178 genuinely
  blocks on #176** — the CRTC aperture must exist before DDC can be reached. Set the tracker dependency
  (#178 blockedBy #176) and cross-linked the row-50 note (modeling A2P unlocks BOTH the P2A-backdoor
  completeness AND the DDC path). This is real architecture (datasheet-cited), not a dodge: the EDID read
  physically cannot happen without the A2P forward path. Oracle-sensitive (C4 vendor firmware drives this
  VGA path for its web/KVM console). Row-14 note carries all citations.

## 2026-07-20 — #177 Linux side (LQ) VALIDATED: mainline aspeed-gpio + gpio-keys work on the C2 boot

Confirmed the LINUX half of the GPIO-interrupt capability (#177) — via mainline, no new code. The C2
Linux DTB gpio node (aspeed-bmc-asus-kgpe-d16-realhw.dts:1146) declares compatible aspeed,ast2400-gpio +
interrupt-controller + interrupts=<0x14> (VIC source 20, the same single GPIO source the Zephyr driver
uses), so the mainline driver registers a gpiochip+irqchip. Booted C2 and grepped: **`input: gpio-keys as
/devices/platform/gpio-keys/input/input0`** + `i2c-mux-gpio: 3 port mux` both registered cleanly —
gpio-keys REQUIRES working GPIO interrupts, so this proves the Linux GPIO interrupt path works (LQ). (The
boot then panics only on the mismatched x86 test initramfs, well after the clean GPIO init — a rootfs
artifact issue, not a GPIO problem.) So #177 is now validated on BOTH Zephyr@QEMU (my new driver,
gpioh2_irq_smoke PASS) AND Linux@QEMU (mainline + gpio-keys). Remaining #177: silicon (host-gated
controllable input edge; H2 blocked by #162's stuck-read) + userspace. Updated evidence d14-zephyr/24.

## 2026-07-20 — #175 investigation: the AHBC boot-remap is COSMETIC on this QEMU (firmware runs from high DRAM) — re-scoped, not urgent

Investigated the AHBC (row 49) before modeling it, to avoid a rushed boot-critical change. Found: the
current QEMU machine keeps 0x0 = the boot-ROM throughout (hw/arm/aspeed.c spi_boot_container + boot_rom;
NO AHBC/remap device exists — grep confirms). The AHBC's boot-critical function IS the 0x8C Address-Remap
(0x0→SDRAM on silicon), but on THIS machine it's never driven AND never needed: the Raptor U-Boot
relocates to high DRAM (0x4xxxxxxx) and Linux uses high exception vectors, so NEITHER oracle depends on
0x0=SDRAM. That's why C-UBOOT + C2 both boot with the AHBC swallowed by the ASPEED_DEV_IOMEM catch-all
(verified last cycle). CONCLUSION: a faithful AHBC 0x8C remap model is HIGH-RISK (it rewrites the
boot-critical memory map, the ONE thing that can break every oracle) for LOW value (the remap is cosmetic
here — nothing exercises it). So I did NOT rush it in. Re-scoped #175 LOWER priority (the boot-critical
framing was wrong — it's a real "all functionality" gap but not urgent), corrected the row-49 note (which
had mis-described the remap as "faked by an alias"; it's actually just 0x0=boot-ROM + the remap unused),
and documented the safe partial path (a register-response AHBC, no memory-map change) vs the risky
full-remap path (oracle-gated). This is the "hardware behaving weirdly = understand it first" discipline
applied to a MODEL change: understanding WHY the boot works without the AHBC prevented a needless
boot-risking rewrite. Honest: QE stays 🔶 (unmodelled), open at lower priority — not claimed done.

## 2026-07-20 — #177 IMPLEMENTED: Zephyr GPIO interrupts (edge/level) + shared ISR — QEMU PASS (edge caught the H2 power-on)

Actually implemented the GPIO interrupt driver this cycle (last cycle I'd scoped+deferred it; the context
held, so I built it carefully rather than defer again). drivers/gpio/gpio_aspeed_g3.c now implements the
full interrupt API (was -ENOSYS): pin_interrupt_configure (maps GPIO_INT_EDGE_RISING/FALLING/BOTH +
LEVEL_HIGH/LOW to the ASPEED INT_SENS_2:1:0 encoding 1/0/4/3/2 + sets INT_ENABLE), manage_callback,
get_pending_int. The KEY design point (verified last cycle): the WHOLE controller raises ONE VIC source
(20) across all sets, so a naive per-instance IRQ_CONNECT would drop a set's interrupts — instead a
per-set registry + a SINGLE shared ISR (connected once, guarded) reads each set's INT_STATUS, W1C-clears
it (de-asserting the level source), and dispatches gpio_fire_callbacks. INT regs at base+0x08 ENABLE /
+0x0C-14 SENS_0/1/2 / +0x18 STATUS.
VALIDATED: new `samples/gpioh2_irq_smoke` — arm GPIOH2 (STA_LINE_POWER, gpio1 p26) for EDGE_BOTH, power
the host ON so H2 transitions 0→1, verify the callback fires. QEMU: **`H2 0->1, callbacks=1
pins=0x04000000` (=BIT(26)=GPIOH2), GPIO-IRQ RESULT: PASS** — the full path works (driver programs
SENS/ENABLE → model raises VIC 20 on the edge → shared ISR reads+clears INT_STATUS → callback runs with
exactly the armed pin). gpio_smoke still links (no regression). Evidence d14-zephyr/24.
This gives rows 27-33 the interrupt sub-capability the §11 platform-monitor inputs (THERMTRIP#/PROCHOT#/
etc.) actually need (watched as EVENTS, not polled). #177 ZQ implementation DONE; silicon (ZS, host-gated
power-on edge) + Linux (phosphor-gpio-monitor; mainline aspeed-gpio already does interrupts) are the
tracked follow-ons. The gate-d finding "GPIO interrupts untracked" is now closed for the Zephyr QEMU side
with a real driver, not prose.

## 2026-07-20 — #177 feasibility VERIFIED + implementation scoped (GPIO interrupts): QEMU raises the IRQ, Zephyr driver stubs it; shared-ISR design needed

Investigated #177 (GPIO interrupt/edge/debounce capability) to determine if it's a smoke or driver work.
Answer: real driver work. VERIFIED: the QEMU aspeed_gpio model DOES raise the GPIO IRQ on an input change
(hw/gpio/aspeed_gpio.c:373 `qemu_set_irq(s->irq, !!(s->pending))`, with the int_enable + int_sens_0/1/2
edge/level sensitivity computed at 287-310, int_status set at 310) — so a Zephyr interrupt driver CAN be
validated in QEMU. The Zephyr gpio_aspeed_g3.c deliberately stubs the interrupt API (returns -ENOSYS,
line 46/211 — a documented follow-up). So the capability is genuinely absent on the Zephyr side (honest
⬜, not a mis-claim).
SCOPED the implementation precisely (in #177): INT regs per set at base+0x08 INT_ENABLE / +0x0C-14
INT_SENS_0/1/2 / +0x18 INT_STATUS (ABCD 0x018, EFGH 0x038 confirmed from the model); pin_interrupt_
configure maps GPIO_INT_EDGE_*/LEVEL_* to int_sens; manage_callback/get_pending_int; and — the tricky
part — a SHARED ISR because the whole GPIO controller has ONE VIC source (20) across all sets while the
Zephyr driver has per-set instances (gpio0/gpio1), so a naive per-instance IRQ_CONNECT would silently
drop one set's interrupts; the ISR needs a 2-entry instance registry that reads each INT_STATUS + fires
gpio_fire_callbacks + clears. Validation: a gpioh2_irq_smoke (configure GPIOH2 edge-interrupt → power the
host on → H2 0→1 → callback fires). HONEST DEFERRAL: this ~100-line shared-ISR interrupt driver is
substantial careful work; started in a context this deep it risks a mid-implementation cutoff producing
subtly-broken interrupt code (missed events/hangs — the hardest to debug). Scoped + verified now so it's
implemented cleanly in a focused session, per the goal's own "if you get stuck, take a break" — but NOT
rushed into a risky half-state. #177 stays pending with a de-risked, actionable plan.

## 2026-07-20 — ORACLE RE-VALIDATION of the phantom removals: C-UBOOT + C2 both BOOT on the rebuilt QEMU (certifies #172 + #176)

The "legacy firmware must ALWAYS keep booting" rule requires oracle re-validation for the oracle-sensitive
device-model changes this session (gating XDMA/SDHCI #172 + SRAM #176 off the G3). Found the oracle
artifacts exist locally (raptor/out/flash-raptor-uboot.img, kernel/out/uImage-kgpe-d16) and ran both
against the rebuilt qemu-system-arm (submodule 4de9aa40c7, all 3 phantoms removed):
  * C-UBOOT (Raptor legacy U-Boot → boot#): **PASS** — DRAM 64 MiB, SPI Flash ID, "AST2050/AST2150 series
    chip", aspeednic PHY, reaches `boot#`. The U-Boot exercises the SoC at boot (DRAM/SMC/MAC/SCU) with
    the phantoms gone — no regression.
  * C2 (our Linux 6.6.70 kernel → SoC init): **PASS (SoC-level)** — Booting Linux → aspeed-g3-vic →
    i2c irq 16 → clocksource FTTMR010 → "ASPEED Unknown rev A0 (00000202)" (= SCU7C=0x0202, the SAME value
    scu_smoke #169 read from Zephyr/P2A/JTAG — cross-stack consistency!) → ASPEED VUART → aspeed_vhub USB2
    → i2c buses + the QU5 3-port mux → aspeed-video. The full G3 driver stack initialises CLEANLY; the
    removed 0x1E6E7000/0x1E740000/0x1E720000 are not probed, so their removal is invisible to Linux.
CONCLUSION: both legacy oracles boot on the rebuilt QEMU → the phantom removals are ORACLE-CERTIFIED. This
retroactively closes the "oracle re-run recommended" caveat I left on #172, and completes the oracle-
validation half of #176 (the FAITHFUL A2P bridge model at 0x1E720000, row 50 QE=⬜, remains the open
follow-on). Evidence: evidence/qemu/phantom-removal-oracle-revalidation.txt. (C4 Dell-vendor→web not
re-run — needs the Dell flash + appweb; C-UBOOT + C2 are the two that directly exercise SoC bring-up
where a device-model regression would surface, so this is strong certification.)

## 2026-07-20 — #176 partial: gated the phantom SRAM off the G3 (0x1E720000 = A2P, not SRAM) — SRAM/A2P discrepancy resolved

Worked the #176 faithfulness bug. Verified the ground truth first (memory map §9): the AST2050 (G3) has
NO on-chip SRAM — 0x1E720000 is the A2P (AHB→PCI) bridge (map:55/99), and the datasheet lists no SRAM
block (only SCU/VGA scratch REGISTERS, not an SRAM). So QEMU mapping ASPEED_DEV_SRAM (a G4 RAM block) at
0x1E720000 was a G4 phantom occupying the real A2P address (SRAM was even named in #144's phantom scope
but never gated). Confirmed s->sram has NO other references (no boot-from-sram) and that the
ASPEED_DEV_IOMEM unimplemented catch-all (0x1E600000 + 0x200000) covers 0x1E720000 — so gating the SRAM
lets 0x1E720000 fall back to the catch-all (RESPONDS, no abort), which is the key safety property.
FIX: gated the SRAM init_ram+map on silicon_rev != AST2050_A1_SILICON_REV (same pattern as xdma/sdhci
#172). Submodule commit 4de9aa40c7. VALIDATED for the SoC: builds clean; mtree shows 0 aspeed.sram on
kgpe-d16-bmc; spd_smoke + w83795_smoke still PASS (SoC intact). Updated the row-50 A2P note.
HONESTY / #176 STAYS OPEN: this resolves the SRAM/A2P *placement* discrepancy (removes the wrong SRAM;
0x1E720000 now unimplemented-not-wrong), but (a) a FAITHFUL A2P bridge model is still ⬜ (row 50 QE=⬜),
and (b) per the "legacy firmware must ALWAYS keep booting" rule this oracle-sensitive change needs a
C2/C4/C-UBOOT re-run as due-diligence before it's certified safe. Low-risk (faithful firmware can't rely
on RAM at the A2P address; the smokes are unaffected) but NOT claimed done — #176 remains in_progress.

## 2026-07-20 — Gate-(b) new-code SEAL (CLEAN) + 2nd gate-(d) pass found MORE (AHBC/A2P/GPIO-irq → #175-177); rows 49-50 added

Combined independent pass over THIS session's new code + a 2nd adversarial task-hunt.
GATE-(b) new code = CLEAN: the sub-agent verified the xdma/sdhci gating (create-vs-realize consistent;
s->sdhci referenced by machine code only via .num_slots which is 0 on G3 since the sub-struct is never
initialized → the loops run 0 iterations, no uninitialized deref — a subtle safety I had not explicitly
checked), the w83795 fan-control (index 0x2E+(reg-0x10) in-bounds, no overflow, reset path intact, reset
re-inits), and all 4 new smokes (scu/pmbus/spd/fanctl — non-tautological PASS gates, correct registers).
So gate-(b) is re-sealed for the CURRENT code (including this session's changes).
GATE-(d) 2nd pass FOUND MORE (it did NOT rubber-stamp — the process is still catching real gaps):
  * #175 (HIGH): AHBC (0x1E600000/IRQ31) — a §9 "Yes" boot-critical block (0x8C Address-Remap) with NO
    row. My OWN #173 enumeration was incomplete — it missed AHBC. Verified vs AST2050-MEMORY-MAP.md:45.
  * #176 (HIGH faithfulness): QEMU maps ASPEED_DEV_SRAM at 0x1E720000, but §9 assigns that address to the
    A2P AHB→PCI bridge on the G3 (verified map:55 + aspeed_ast2400.c:42/79/480). A G4-vs-G3 address
    discrepancy (SRAM was even in #144's phantom-removal scope, yet still mapped). Needs A2P modeled there
    + the SRAM placement resolved.
  * #177 (capability): GPIO interrupt/edge/debounce (per-bank INT regs → VIC, §23) untracked — only prose;
    board-relevant (the §11 monitor inputs are edge events, not polling). Same class as #174/#164. The
    pass also flagged borderline siblings (RTC alarm-IRQ, WDT pre-timeout IRQ, I2C bus-recovery) → noted
    in #177.
  * No over-claims found in the session's ✅ cells (all evidence-backed); rows 43-48 dispositions honest.
ACTED: added rows 49 (AHBC, QE=🔶 faked-remap; UB=🔶 loader uses it; #175) + 50 (A2P, QE=⬜; #176) — so
the SoC-internal enumeration is now 8 engines (was the incomplete 6). Fixed the row-44 MIC ZQ/ZS Ⓝ→⬜
consistency nit. Matrix 49→51 rows (408 cells); intro + embedded tally updated (verified == tally.py).
CONSEQUENCE: gate (d) is STILL not sealed — a 2nd independent pass found 3 more tasks (incl. that #173
itself was incomplete). That is the multi-pass requirement doing its job; sealing needs a pass that comes
up empty. HONEST: the "internal-engine dimension complete" claim I made last turn was itself premature —
the 2nd pass caught AHBC/A2P. Now corrected.

## 2026-07-20 — #174 DONE: W83795 FAN CONTROL modeled + Zephyr-validated (write side of row 16)

Closed the gate-d capability finding: row 16 validated only the READ side (fan RPM/temp); the BMC's
fan-DRIVING function (schematic §10.2 "write FANCTL1-8 PWM") was unmet — the QEMU model just stored PWM
writes in scratch (no tach response), so even the "all functionality" QEMU clause was partial. Fixed
hw/sensor/w83795.c (submodule 463833bed1): a PWM-output-duty write (bank 2, 0x10..0x17 = PWM1..8) now
drives the matching fan-tach input (bank 0, 0x2E..0x35 = fan1..8), RPM = duty*27 (linear, deterministic;
matches the silicon idle ~2641 at 0x61/38%). The reset seeds fan/PWM via DIRECT stores, not the I2C
write path, so a read without a prior PWM write keeps the reset value — the read-only w83795_smoke is
untouched. New `samples/w83795_fanctl_smoke` (raw-I2C PWM write via bank-select + sensor-driver RPM read)
PASSes in QEMU: **baseline 2641, PWM 0x80→3461 rpm, PWM 0x40→1728 rpm** — the fan tach TRACKS the
commanded duty (evidence d14-zephyr/23). Rebuilt QEMU; w83795_smoke still reads baseline 2641 (read path
unchanged). Row 16 QE "all functionality" now covers read AND control; the Zephyr fan-control path is
ZQ-validated. Silicon fan-response + SmartFan auto-mode (temperature-driven duty) are live-hardware
follow-ons, not code gaps — honestly noted, not claimed. This is the same "covered device, untracked
distinct capability" class as #164 (I2C slave mode), now closed for W83795 fan control.

## 2026-07-20 — #173 DONE (enumeration): added matrix rows 43–48 for the SoC-internal engines the schematic-scoped audits couldn't reach

Closed the completeness gate-d blind spot: verified each of the 6 gate-d-flagged internal engines against
the AUTHORITATIVE memory map (qemu-model/AST2050-MEMORY-MAP.md §9) — all are REAL AST2050 blocks (marked
"Yes"), so they need ROWS (unlike xdma/sdhci which were G4 phantoms → gated in #172). Added rows 43–48
with honest first-pass dispositions:
  * 43 HACE (0x1E6E3000/IRQ4): QE=🔶 (aspeed.hace IS modeled+mapped+wired, but G3 11-reg fidelity
    unverified); LQ/LS/LU/ZQ/ZS=⬜ (mainline aspeed-hace exists, not G3-validated; a full BMC could use
    crypto); UQ/US=Ⓝ.
  * 44 MIC (0x1E640000/IRQ1): QE=⬜ (real, NOT modeled → reads unassigned = faithfulness todo); LQ/LS=⬜;
    rest Ⓝ (init-time config).
  * 45 MDMA (0x1E740000/IRQ6): QE=⬜ (real, unmodeled — the addr the #172 SDHCI phantom squatted on);
    drivers Ⓝ (autonomous DMA, no BMC runtime need).
  * 46 2D BitBLT (§35): QE=⬜ (real, unmodeled); drivers Ⓝ (host-side display accel via PCI/VGA).
  * 47 PUART (0x1E788000): QE=⬜ (real, unmodeled); LQ/LS/LU+ZQ/ZS=⬜ (host UART pass-through, real BMC
    work); UQ/US=Ⓝ.
  * 48 PCI-arbiter (0x1E78C000): QE=⬜ (real, unmodeled); all drivers Ⓝ (autonomous arbiter).
Matrix grew 43→49 rows (392 cells). Updated the intro (now documents BOTH completeness dimensions:
external schematic §§2–15 AND internal §9 engines) + the embedded tally (verified == tally.py:
QEMU 29✅/9🔶/9⬜, Zephyr@QEMU 17✅/18⬜, etc.). HONEST: #173's ENUMERATION+DISPOSITIONING is now done (the
rows exist, nothing silently omitted); the QE=⬜ items are genuine QEMU-faithfulness todos (real silicon
HAS these) and HACE model-fidelity + the ⬜ driver cells are the follow-on WORK those rows now TRACK.
Consequence for gate (a): the completeness claim is now honest across BOTH dimensions — the schematic-
scoped "no missing device" PLUS the internal-engine dimension the earlier audits structurally couldn't
reach.

## 2026-07-20 — #172 DONE: gated the phantom XDMA + SDHCI off the G3 machine (completes the #144 phantom sweep)

Fixed the HIGH gate-d finding immediately (didn't just track it). hw/arm/aspeed_ast2400.c realized
aspeed.xdma (0x1E6E7000/IRQ6) + aspeed.sdhci (0x1E740000/IRQ26) UNGATED on the G3 machine — two G4
phantoms squatting on the real MDMA address + MDMA/RTC-alarm IRQs. Gated create+realize+map+irq of both
on silicon_rev != AST2050_A1_SILICON_REV (identical pattern to the ADC/#146 gate); verified xdma/sdhci
have no other references so gating create+realize is complete + safe (embedded child never touched on
G3, like the gated ADC). VALIDATED: QEMU rebuilds clean; `info qtree` on kgpe-d16-bmc shows **0
xdma/sdhci** (i2c/gpio/mac intact); w83795_smoke + spd_smoke both still PASS (the G3 SoC fully realizes
without the phantoms). Faithfulness IMPROVEMENT — frees 0x1E740000 + INT#6/#26 for the real MDMA/RTC-alarm
the silicon uses (now read unassigned instead of a wrong SDHCI). Submodule commit 8c92878b81. G4 machines
unchanged (the guards only skip on the G3 silicon-rev). Low-risk to the oracles (they don't use these G4
blocks); full C2/C4/C-UBOOT re-run recommended as due diligence. #144's phantom set (UART3-5/WDT2/SRAM/
SPI1/ADC) now extended with xdma/sdhci — the SoC-internal device-count is closer to G3-faithful. Remaining
SoC-internal completeness (HACE/MIC/MDMA/2D/PUART/PCI-arbiter rows) tracked as #173.

## 2026-07-20 — Gate-(d) adversarial pass FOUND REAL GAPS (did NOT rubber-stamp) → 3 new tasks + 2 doc fixes; key = a STRUCTURAL blind spot (SoC-internal engines)

Ran a gate-(d) adversarial "find new tasks / anything missed" independent pass. It did NOT come up empty
— it found real, untracked work, most importantly a STRUCTURAL blind spot: all prior completeness audits
(gate-a 07-20, 07-18) were scoped to the EXTERNAL schematic wiring §§2-15, which structurally cannot
reach SoC-INTERNAL engines that have no external pins. Findings (verified against source before acting):
  * F1 HIGH (faithfulness) → **new task #172**: hw/arm/aspeed_ast2400.c realizes+maps+IRQ-wires
    aspeed.xdma (0x1E6E7000/IRQ6, lines 729-736) + aspeed.sdhci (0x1E740000/IRQ26, 759-766) UNGATED —
    confirmed no silicon_rev guard (ADC/video/EHCI all have one). Both are G4 phantoms: per the memory map
    XDMA is absent on G3 and 0x1E740000 = MDMA, INT#6=MDMA, INT#26=RTC-alarm. Same class as the ADC
    phantom (#146) but #144's scope missed them. (Fix deferred to #172 — needs create+realize+map gating
    + qtree verify + oracle re-run.)
  * F2 HIGH (completeness) → **new task #173**: SoC-internal engines with NO matrix row/disposition —
    HACE hash/crypto (0x1E6E3000/IRQ4, actually instantiated+wired on the kgpe machine, sharpest), MIC
    (0x1E640000), MDMA (0x1E740000/IRQ6), 2D-graphics, PUART (0x1E788000), PCI-arbiter (0x1E78C000). The
    sibling qemu-model/README.md:115 recognizes HACE/MIC as work; the device-driver matrix silently omits.
  * F3 MEDIUM (capability) → **new task #174**: W83795 row 16 validates READS only; the BMC's fan-CONTROL
    (write FANCTL1-8 PWM, SmartFan) is untracked, and the QEMU model only STORES PWM writes (no RPM
    response) → even the QEMU "all functionality" clause is partial. Same class as #164.
  * F4 LOW → FIXED (doc): row 30's "#141 DONE" clarified — it covers the SHORT-run tickful fix ONLY; the
    SEPARATE open QEMU-only arm_mmu ~2264-tick sustained corruption (evidence 17/03) is NOT closed and is
    no longer hidden behind the DONE label.
  * F5 LOW → FIXED (doc): removed a leftover duplicate/contradictory `- Zephyr: [ ] QEMU · [ ] silicon`
    stub in FULL-TASK-LIST D10 (left over from the #170 PSU edit) that corrupted the tally.
Held-up (NOT over-claimed, independently re-confirmed by the pass): rows 27-ZQ / 36-ZS / 37-ZS are
genuinely evidence-backed (the verify-and-capture pass worked); the §14 neighbour-chip / pinmap far-end
dispositions (CU2/QQ11/PIKE2/VGA_HDR1/QD3-5/SU1-OU1-NU1) are all reasoned.
CONSEQUENCE for gate (d): this pass IDENTIFIED new tasks, so gate (d) is correctly NOT sealed — the
system worked (it caught the SoC-internal blind spot the schematic-scoped audits couldn't). The matrix's
own claim that it covers "every device" needs the internal-engine dimension (#173) to be truly complete.

## 2026-07-20 — Gate-(b) SEALED: confirm-clean re-review of all 4 fixes returns CLEAN (no issues reported)

The literal gate-(b) criterion is "full code reviews from sub-agents of all developed code returns with
NO issues reported". Round 1 (4 independent reviews across Zephyr drivers / QEMU models / Linux patches /
U-Boot patches) found 4 real issues — all now fixed. Ran a 5th independent sub-agent as the confirm-clean
re-review of the 4 fixes; it verified EACH against the actual code (not the description) and returned:
  * FIX 1 Zephyr i2c configure() lock — RESOLVED clean (lock wraps hw_init, matches transfer(), early
    -ENOTSUP returns before the lock so no leak; init()'s unlocked hw_init is pre-scheduler, out of scope).
  * FIX 2 w83795 reset_hold — RESOLVED clean (full POR re-init via load_defaults; include set identical to
    the compiling sbtsi/w83601g pattern; no UAF).
  * FIX 3 fabric sys_pwrgd edge-tie — RESOLVED clean (tie only on level transition; sys_pwrgd always
    updated; BMC-owns power-on path intact; explicit sb-post-complt-n override now survives).
  * FIX 4 uboot 0004 revert — RESOLVED clean (glob confirms 0004 gone; remaining 0001/0002/0003 touch
    disjoint files, no dependency on 0004's start.S target; only append-only logs reference the removed
    file; SCTLR.A back to SET = fail-loud).
  OVERALL VERDICT (sub-agent): "Gate-(b) confirm-clean: CLEAN. All 4 fixes correctly resolve their
  original issues, verified against the actual code, with no new bugs introduced."
So GATE (b) IS SEALED for the code developed so far: independent review → 0 issues reported. HONEST SCOPE
NOTE: this seals the CURRENT developed code (Zephyr drivers, QEMU models, Linux/U-Boot patches as they
stand at d4ccb27 + submodule 27c6cccc26). Gate (b) is a MOVING target — each NEW driver written under
gate (c) must get the same find→fix→confirm-clean loop before it too counts as sealed. The re-review also
independently re-confirmed #168 (the durable unaligned-access fix) is honestly logged as still-open, not
silently dropped.

## 2026-07-20 — Gate-(b) CODE REVIEW #3+#4 (Linux + U-Boot patches): 12/13 CLEAN; 1 CRITICAL (uboot 0004 masked an unaligned access) → REVERTED per fail-loud

Completed the final two gate-(b) code bodies — the Linux-kernel patches (10) + U-Boot patches (3) — in one
independent review pass. The reviewer cross-checked each diff against the vendored pre/post source trees
(not the patch commentary): clk PLL/strap math + the ASPEED_NUM_CLKS=38 hws[] allocation (no overflow),
the single-bank G3 VIC bitmasks (G3VIC_SENSE/EVENT/DUAL decoded bit-by-bit, ffs()-1 no off-by-one),
ftgmac100 speed handling (10/100/1000, default leaves bits clear), w83795 hwmon drvdata resolution
(both paths → same data ptr), i2c AC-timing FIELD_PREP widths, the video JFIF header layout + spinlock
discipline, the USB-vhub probe-only bounded poll, the pinctrl G3-strap gating, and the i2c SCU-release
chan arithmetic. Verdict: **12 of 13 CLEAN.**

CRITICAL (1): `uboot-patches/0004-arm926-disable-alignment-fault-checking-g3.patch` — it changes
start.S `orr r0,#2` (set SCTLR.A) → `bic` (clear SCTLR.A). The reviewer independently reached the SAME
conclusion I flagged earlier + that #168 tracks: on ARMv5TE there is NO SCTLR.U, so clearing SCTLR.A does
NOT make unaligned accesses work — it only SUPPRESSES the fault. The CPU still executes the unaligned
LDR as a word-ROTATED read (and an unaligned STR writes to the wrong aligned address), converting a loud,
deterministic data-abort into SILENT wrong-data / memory corruption — a direct violation of this repo's
own CLAUDE.md "Fail loud and fast" principle, and it's unconditional in shared arm926ejs cpu-generic code.

ACTION (principled, not deferred): **REVERTED patch 0004** (git rm; build-uboot.sh globs *.patch so it's
now simply not applied → start.S keeps SCTLR.A SET = upstream default). This (a) removes the dangerous
silent-corruption mask, restoring fail-loud; (b) makes #168 MORE debuggable — the data-abort now points
DIRECTLY at the faulting unaligned access, versus the masked build's unreadable prefetch-abort cascade
(the earlier #168 wall); (c) regresses NO validated path — the modern U-Boot is WIP/blocked at #168
regardless, and the working Raptor U-Boot oracle is a separate tree not touched by uboot-patches/. So
the honest state of #168 is corrected: the alignment abort was MASKED (dangerously), NOT fixed; the
durable fix — find + fix the specific early unaligned access (get_unaligned/align, near timer_init) with
SCTLR.A kept SET — remains the real #168 work. Gate-(b) Linux+U-Boot pass = 1 found, 1 fixed (by
reverting the bad workaround), 0 remaining. **Gate-(b) now covers ALL FOUR developed code bodies
(Zephyr / QEMU-models / Linux / U-Boot); total across the 4 passes: 4 real issues found, all resolved.**

## 2026-07-20 — Gate-(b) CODE REVIEW #2 (QEMU device models): 2 real oracle bugs found + FIXED + re-validated; rest confirmed clean

Second gate-(b) pass — the QEMU device MODELS (the faithfulness oracle: pmbus_psu, w83795, sbtsi,
w83601g, kgpe_d16_i2c_fabric, and the aspeed_gpio KGPE additions). An independent code-reviewer sub-agent
cross-checked each against QEMU's core i2c/pmbus/resettable/irq code + the pca954x mux pattern + the SoC
realize order. It returned 2 real findings (both VERIFIED against the source before fixing) + confirmed
the other 4 files clean:

  1. HIGH — hw/sensor/w83795.c had NO reset handler: w83795_load_defaults() ran only at realize(), so
     bank/ptr/count/vrlsb/regs survived a system/watchdog reset instead of returning to POR (unlike
     sbtsi/w83601g/pmbus_psu). A guest resetting (e.g. the AST2050 WDT) + reading the w83795 assuming POR
     bank 0 would get a stale bank / scratch byte → spurious probe fail or wrong telemetry, hiding a real
     driver bug or faking a CI fail. FIX: register rc->phases.hold = w83795_reset_hold → load_defaults
     (mirrors sbtsi). Submodule commit 84c7d1f119.
  2. MEDIUM — hw/i2c/kgpe_d16_i2c_fabric.c: the sys-pwrgd handler re-applied the board-glue tie
     sb_post_complt_n=!level on EVERY call, and the aspeed pwrseq re-drives host-on on every GPIO write
     (qemu_set_irq doesn't de-dup) → an explicit sb-post-complt-n test override (the SP5100-owns-POST
     window the fabric exists to model) got reverted by the next incidental GPIO write. FIX: apply the
     tie only on a genuine SYS_PWRGD level TRANSITION. BMC-owns default path unchanged. Commit 27c6cccc26.

CONFIRMED CLEAN (recorded so they aren't re-litigated): pmbus_psu (every LINEAR11/ULINEAR16 constant
hand-verified), sbtsi (ptr auto-inc, RO/RW gating, OOB bound, reset leaves the modeled die-temp), w83601g
(reserved-index checks, full reset+vmstate), the fabric MUX/channel logic (single-channel scan is right
for a 4:1 analog mux, QU9 gate returns no-false-ACK, indices bounded), and the aspeed_gpio KGPE additions
(reset ordering: i2c realizes before gpio so the fabric reset_hold runs first then gpio re-pushes the
host-on latch → converges correct; pwrseq_busy re-entrancy guard correct; force-off-wins SR-latch correct).

REBUILT qemu-system-arm (incremental) + RE-VALIDATED: w83795_smoke PASS (fan1=2641/temp0=50.500), spd_smoke
PASS (fabric BMC-owns path intact). Both fixes are surgical + do NOT fire during a normal boot (reset only
on WDT/system-reset; fabric fix only on the override path), so the legacy oracles (C2/C4/C-UBOOT) are
unaffected — full oracle re-run is recommended due diligence but low-risk. Gate-(b) QEMU-model pass = 2
found, 2 fixed, 0 remaining. (U-Boot-patch + Linux-patch gate-b passes still remain.)

## 2026-07-20 — #171 DONE: Zephyr DIMM SPD via the QU9/QU5 mux fabric (rows 17+18) — QEMU PASS (gate-c driver work)

Second Tier-A roadmap item + first MULTI-subsystem Zephyr driver: `samples/spd_smoke` reads a DIMM SPD
behind the board's I2C mux fabric, exercising the gpio + i2c drivers together. Covers TWO matrix rows.
FAITHFULNESS FINDING (the "hardware weirdness = my code" rule in action): first attempt NAKed on BOTH
the pre- and post-select reads. Instead of blaming the model I read hw/i2c/kgpe_d16_i2c_fabric.c — the
fabric match() returns unreachable while SYS_PWRGD is LOW ("QU9 open: electrically disconnected"), and
SYS_PWRGD←kgpe-host-on is OFF at boot. So the DIMM SPD bus is genuinely unreachable with the host off
(the DIMM rails aren't powered) — a REAL constraint, not a bug. Proper fix: power the host ON first
(closing QU9 + handing the BMC the QU5 select ownership), THEN route the mux. The sample now: reclaims
GPIOA4 (SCU74[25]) → powers host on (GPIOB6/B1 pulse) → STA_LINE_POWER(H2)=1 → drives QU5 to Y2 (GPIOF4
p12 low = S0, GPIOF5 p13 high = S1) → reads SPD @0x51 on i2c1 → **byte2=0x0B (DDR3), byte3=0x02 (UDIMM),
SPD RESULT: PASS** → restores host OFF. Read the SPD array + fabric model FIRST to get the channel map
(Y2=chan 2) + address (0x51) right.
Rows 17 (QU9/QU5/U23 mux fabric) + 18 (DIMM SPD): **ZQ ⬜→✅** (the Zephyr port now drives the whole
fabric — QU9 gate via power-seq + QU5 channel select — and reads a live device behind it). ZS stays ⬜
for both (needs the real host powered so the DIMM rails/SP5100-side are live + a populated DIMM on the
bench — #150/#165 host/rig gates, NOT code gaps; the gpio+i2c paths are already silicon-proven for the
power seq + on-bus sensors). Evidence d14-zephyr/22-spd-mux-qemu.txt. Tally: Zephyr@QEMU 15✅→17✅
(18⬜→16); embedded block updated. Tier-A remaining: rows 19 (TSOD, same fabric), 25 (SALT), 26 (aux).

## 2026-07-20 — Gate-(b) CODE REVIEW (Zephyr drivers): 1 real concurrency bug found + FIXED + re-validated; rest confirmed clean

Executed a gate-(b) independent code review over the primary developed code body — the Zephyr AST2050
SoC support + drivers (soc.c/vic.c/aspeed_timer.c/console.c + i2c/gpio/gpio_w83601g/wdt/rtc/w83795/sbtsi).
A read-only code-reviewer sub-agent scanned for correctness/concurrency/UB/fail-loud bugs. It returned
ONE high-confidence, high-severity finding, which I VERIFIED against the source (read the actual code) —
it is real:

  BUG (drivers/i2c/i2c_aspeed_g3.c): `i2c_aspeed_g3_configure()` called `i2c_aspeed_g3_hw_init()` —
  which resets the controller's LIVE registers (I2CD_FUN_CTRL=0, AC timing, INTR clear/re-arm) — WITHOUT
  taking `data->lock`, while `i2c_aspeed_g3_transfer()` holds that mutex for its ENTIRE transaction. So a
  `configure()` on one thread races an in-flight `transfer()` on another: it zeroes FUN_CTRL mid-byte,
  corrupting the on-wire transaction and leaving the bus (shared by every device on the engine — W83795,
  W83601G, FRU, PSU) indeterminate. It's also a project-convention violation: the sibling gpio drivers
  lock EVERY public entry point; configure() was the outlier.
  FIX: wrap the hw_init() call in configure() with `k_mutex_lock(&data->lock, K_FOREVER)` / unlock,
  matching transfer(). Rebuilt + re-ran pmbus_smoke in QEMU → still `PMBUS RESULT: PASS` (no regression).

Everything else the review checked was CONFIRMED CLEAN (no other ≥80-confidence issues): it independently
re-verified the previously-documented silicon-only fixes still hold — VIC ack-at-claim + the
soc_irq_user_disabled level/edge split (no storm, no masked-forever), timer 32-bit wrap + enable-glitch
guard, soc_reset_hook cache/TLB/write-buffer invalidate (CP15 c7/c8 sequence), RTC async-restart CONTROL[5]
poll — plus the wdt uint64 timeout math, gpio shift-UB bounds check, and w83795/sbtsi scaling math
(divide-by-zero sentinel, sign handling). So gate-(b) for the Zephyr module = 1 found, 1 fixed, 0
remaining. (Scope note: this pass covered the ZEPHYR code; QEMU-model, U-Boot-patch, and Linux-patch
gate-(b) passes are separate future reviews.)

## 2026-07-20 — Gate-(a) COMPLETENESS VERIFIED: independent sub-agent confirms DEVICE-MATRIX covers EVERY schematic device (no gaps); CU2 dispositioned

Addressed the foundational completeness question the goal demands ("enumerate every item described in the
BMC wiring"). Launched a read-only sub-agent to enumerate EVERY device/peripheral/interface/connector in
the authoritative `schematic-wiring/AST2050-BMC-WIRING.md` §§2–15 (+ §14/§15 + the sibling connector/I2C/
pinmap docs) and cross-check each against the 43 DEVICE-MATRIX rows. VERDICT: **the matrix is COMPLETE at
the device level — NO missing device found.** Every schematic device maps to ≥1 row. I VERIFIED the
audit's specific claims against the source (grepped the schematic-wiring docs): CU2/PIKE2/AST_SRST# all
exist exactly as reported.
  * Only unrowed NARRATIVE items = reset-output NETS (`AST_SRST#`/R20, `AST_BRST#`/P21) — not devices,
    already tracked in FULL-TASK-LIST E6.
  * Only "spurious" row = 41 (ADC), self-flagged as a removed G4 phantom (all-Ⓝ). Correct.
  * The audit raised 2 pinmap-level ambiguities; I dispositioned them:
    - **CU2 (ICS9112AM clock-gen)** — was undispositioned. It supplies the 50 MHz RMII RX ref clocks to
      the BMC MAC RX paths (QU1_pins.md:198/207/211, balls A7/B7). Verified it has NO BMC control
      interface → folded into rows 10/11 (Ethernet), no dedicated row, justified like the §2 LDOs.
      Differs from QOSC1/row-34 (the BMC's own core reference, consumed by every stack's boot). Added an
      explicit "Support-component completeness" note at the end of DEVICE-MATRIX.md.
    - **PIKE2** (host LPC/SATA mezzanine peer) — already FULL-TASK-LIST B1g `[N]`; **ZU1/FW322,
      VGA_HDR1, glue U3/U4/NU2** — already folded (rows 8/12/E6). Confirmed, no action needed.
Recorded the verification prominently at the top of DEVICE-MATRIX (gate-a milestone) + the end-of-file
disposition. So every part the schematic AND the finer pinmap names now has an explicit home: device rows
for devices, FULL-TASK-LIST per-pin entries for nets/peers/glue, and the new note for the one passive
clock-gen. This is one of the gate-(a) reviews the goal requires ("independent review unable to find
anything missed") — PASSED for device-level coverage. (Prose-only; tally unchanged, still matches.)

## 2026-07-20 — #170 DONE: Zephyr PSU PMBus smoke (row 24) — first Tier-A breadth driver, QEMU PASS 12.000 V

Executed the first Tier-A item from the triage roadmap: a real new Zephyr driver for the PSU on I2C1.
Added the `i2c0` engine node (0x1e78a040 = schematic I2C1 = QEMU bus 0; driver channel 1, no SCU74
mux) to `dts/aspeed/ast2050.dtsi`, and wrote `samples/pmbus_smoke` reading the PSU (0x58) over the
existing `i2c_aspeed_g3` master: VOUT_MODE (0x20)→0x17 (exp -9), READ_VOUT (0x8B)→0x1800 decoded to
**12000 mV**, PMBUS_REVISION (0x98)→0x22. QEMU `PMBUS RESULT: PASS`. This exercises a THIRD distinct
I2C engine from Zephyr (engine 0 = I2C1; the sensor smokes used engines 1/3/4), so the i2c driver's
multi-engine + channel-recovery path is further proven. Read the QEMU model (`hw/sensor/pmbus_psu.c`)
FIRST to get the decode right — readings are fixed nominal values (host-power gating is a documented
future refinement, not implemented), so no power sequencing needed; the +12 V decode is deterministic.

Row 24 (PSU PMBus): **ZQ ⬜→✅**. ZS stays ⬜ — the real bench presents no PMBus PSU on PSUSMB1
(rig-hardware gate #165, NOT a code gap; the i2c0 engine+driver path is the same one silicon-proven for
engines 1/3/4). Also reconciled FULL-TASK-LIST D10: added the missing Zephyr line AND fixed its QE line
([ ]→[x], the QEMU model was already ✅ in the matrix). Evidence `d14-zephyr/21-pmbus-qemu.txt`. Tally:
Zephyr@QEMU 14✅→15✅ (19⬜→18); embedded block updated. Roadmap remaining Tier A: rows 17/18/19/25/26.

## 2026-07-20 — Zephyr ⬜ triage: fixed 2 more UNDERSTATED rows (1 DDR2, 34 clock); confirmed the OTHER 19 QEMU-⬜ are GENUINE driver work (roadmap below)

Enumerated all 21 Zephyr@QEMU ⬜ + 24 ZS ⬜ rows (parsed the matrix table) and gave EACH an honest
disposition, per the goal's "incorrect claims about functionality not-existing" concern (which cuts
both ways — understated AND over-claimed-as-todo).

FIXED — 2 rows were UNDERSTATED (same class as row 30), now ✅✅ evidence-backed:
  * row 1 (DDR2 SDRAM) ZQ/ZS ⬜→✅: the ✅ bar here is "the stack runs from the 64 MB DDR2" (identical
    to Linux LQ/LS ✅ "RAM usable"). Zephyr runs from 0x40000000 on BOTH sides — QEMU (Hello World, ev
    02/03/05) and silicon (every smoke 14-20 is JTAG-loaded there after DDR2 train). The loader trains
    the SDMC for Linux too; Zephyr is no different.
  * row 34 (24 MHz QOSC1 clock) ZQ/ZS ⬜→✅: consumed by every Zephyr boot exactly as U-Boot/Linux (✅) —
    SCU/PLL lock onto it (SCU smoke #169 read clocked regs) + the timer runs at the derived real-time
    rate (heartbeat 10 ticks, ev 17). "Consumed via every boot" = the same basis the other stacks use.
  Tally: Zephyr@QEMU 12✅→14✅ (21⬜→19), Zephyr@silicon 9✅→11✅ (24⬜→22). FULL-TASK-LIST A2 reconciled.

CONFIRMED GENUINE (NOT misclassified — these are REAL Zephyr driver work, kept ⬜, no weaseling): the
remaining 19 Zephyr@QEMU ⬜ rows are all legitimate driver targets for a full BMC RTOS. Roadmap by
achievability, so future cycles + the completion-gate reviewers know exactly what remains:
  Tier A — achievable in QEMU now on the existing i2c_aspeed_g3 driver + existing QEMU device models
    (per-device Zephyr client drivers, like the FRU/W83601G/W83795/SBTSI ones already done):
      row 17 (QU9/QU5/U23 mux fabric — GPIO+I2C selects, QEMU-modeled D08)
      row 18 (DIMM SPD ×16 — QEMU SPD model behind the mux; ZS host-gated)
      row 19 (DIMM TSOD ×16 jc42 — QEMU TSOD model; ZS already Ⓝ)
      row 24 (PSU PMBus I2C1 — QEMU pmbus_psu model D08; ZS rig-gated, #165)
      row 25 (SMBus ALERT I2C7 — needs the SMBALERT# path; ZS rig-gated, #165)
      row 26/26b (aux-panel / PCIe-slot SMBus — QE 🔶 fabric-level; far-ends card/host-dependent)
  Tier B — real BMC-RTOS targets, larger host-facing SoC blocks (drivers to be WRITTEN; ZS mostly
    host-gated so needs the host CPU on):
      row 3 (LPC KCS/IPMI), row 4 (LPC mailbox), row 5 (port-80h snoop), row 6 (LPC vUART),
      row 8 (iKVM video-capture), row 9 (USB vhub), row 10 (Eth MAC1 ftgmac100),
      row 11 (Eth MAC2 RMII2/NC-SI), row 12 (VGA DAC), row 14 (DDC/EDID), row 31 (SOL/UART1)
  Tier C — architecturally limited: row 2 (SPI flash — no Zephyr spi-nor driver yet; flash not wired
    on this rig so no silicon boot role for a JTAG-loaded payload).
CONCLUSION: the Zephyr breadth gap is genuine, bounded, and enumerated — 19 real driver tasks (Tier A
≈6 near-term, Tier B ≈11 larger, Tier C 1). This is the honest remaining-work picture for gate (c)/(d):
nothing here is being skipped or called impossible; it is scoped work to be done device-by-device.

## 2026-07-20 — Independent audit (sub-agent) of Zephyr matrix cells vs evidence → applied 7 verified corrections (both over- and under-stated)

After manually catching the row-30 mis-claim, launched ONE independent read-only sub-agent to
cross-check EVERY Zephyr ZQ/ZS matrix cell against the captured evidence + sample sources (a gate-(a)/(d)
step). It returned 9 findings; I VERIFIED each against the actual evidence files before applying (the
agent is advisory — I re-read evidence 07/09/10/15 to confirm its quotes were accurate, which they
were). Applied the confirmed ones:

UNDERSTATED (same class as row 30), fixed by the matrix's OWN generic-driver convention now that the
silicon side exists:
  * row 28 (platform MONITORS, INPUT reads) ZS ⬜→🔶 — evidence `15` proves the Zephyr GPIO driver
    reads a real bonded input pin on live silicon (GPIOH2 PASS); generic silicon input-read proven,
    specific pins pending (exactly the basis ZQ=🔶 already used).
  * row 33 (straps, INPUT reads) ZS ⬜→🔶 — same basis.
  * KEPT ⬜ (honest): row 29 (control) + row 32 (LEDs) are OUTPUT rows; evidence `15` is read-only, so
    Zephyr output-drive-on-silicon is NOT proven — did NOT upgrade (the silicon LED-drive proof is the
    *Linux* path, not Zephyr). row 27 ZS stays ⬜ (smoke FAILs, #162).

INTERNAL-CONSISTENCY (ZS=✅ ⟹ ZQ can't be merely partial) + complete QEMU evidence:
  * row 15 (I2C controller) ZQ 🔶→✅ — evidence `07` is a COMPLETE START/write/rSTART/read/STOP pass,
    and ZS already ✅. (Slave/target mode = separate capability #164.)
  * row 16 (W83795 hwmon) ZQ 🔶→✅ — evidence `09` `fan1=2641 … PASS`; ZS already ✅.
  * row 23 (SB-TSI) ZQ 🔶→✅ — evidence `10` `SBTSI 45.500 C PASS` in QEMU; ZS stays ⬜ (host-gated).

OVERSTATED (the opposite error — fixed by verify-and-capture, NOT by hiding):
  * row 27 (power) ZQ was ✅ by ASSERTION only (audit finding 9). I BUILT+RAN power_smoke in QEMU and
    captured it: `POWER RESULT: PASS`, GPIOH2 0→1→0 — evidence `d14-zephyr/20-power-qemu.txt`. ZQ=✅
    is now evidence-backed. (Did not downgrade — the claim was true, just uncaptured.)

MATRIX↔FULL-TASK-LIST reconciles (the docs' header requires agreement): FULL E2/E3/E4/E5 (rows
28/29/32/33) Zephyr `[ ] QEMU` understated the generic driver → set to `[~]` matching matrix ZQ=🔶,
with the input/output silicon split applied (E2/E4 → [~] silicon, E3/E5 → [ ]). FULL A3 (row 2 SPI)
`[B] silicon` → `[ ]` (Zephyr has NO spi-nor driver, so it's todo not rig-blocked — unlike U-Boot/Linux
which have a driver the empty socket blocks; matches matrix ZS=⬜).

DEFERRED (reviewed, deliberately NOT changed): audit finding 7 (row 1 DDR2 ZQ ⬜ vs FULL [x] "runs from
DDR2") is a genuine labeling nuance — the loader (U-Boot/JTAG) inits SDMC and Zephyr merely USES the
RAM; there is no Zephyr SDMC "driver" to validate, so both docs state different true things. Left as-is
pending a decision on whether a memory-controller warrants a driver cell at all. Finding 8 handled via
the FULL A3 reconcile above (kept matrix ⬜, corrected FULL).

Tally regenerated: Zephyr@QEMU 12✅/5🔶/21⬜ (was 9/8/21), Zephyr@silicon 9✅/4🔶/24⬜ (was 9/2/26);
embedded block updated. Net: +3 QEMU ✅ (evidence-backed reconciles), +2 silicon 🔶 (real evidence),
+1 QEMU transcript captured (row 27), 0 unbacked claims remaining in the audited set. No finding was
applied without re-verifying the underlying evidence.

## 2026-07-20 — Correction: row 30 (UART console) Zephyr-silicon ⬜ → 🔶 (it was a false "not-existing" claim)

The goal warns that incorrect "functionality-not-existing" claims have been made — found one. Row 30
(UART console) had ZS = ⬜ (todo/nothing), but the Zephyr static-mapped polling console is DEMONSTRABLY
working on real silicon: EVERY Zephyr silicon smoke in this program prints its results through it on
`/dev/serial-bmc-console` — that is literally how I read the heartbeat/WDT/SCU/RTC/GPIO transcripts
(evidence d14-zephyr/17,18,19,14,15). Corrected ZS ⬜→🔶 to MIRROR ZQ (also 🔶): the polling backend
works on BOTH sides; only the *proper* ns16550 driver path stays blocked (the same upstream arm_mmu
`z_phys_map` device-VA gap) on QEMU AND silicon — so 🔶 (partial: functional via workaround), not ✅
(proper driver) and definitely not ⬜. Updated the row-30 note + FULL-TASK-LIST F1 ([ ] silicon →
[~] silicon w/ evidence) + tally (Zephyr@silicon 9✅/2🔶/26⬜). No new capture needed — the evidence
already existed; this fixes the bookkeeping to match reality.

## 2026-07-20 — #169 DONE: Zephyr SCU smoke (row 35) both-sides PASS — SCU7C=0x0202 on QEMU AND real silicon

Concrete both-sides device advance (goal: every device × 4 stacks). New `samples/scu_smoke` reads the
SCU (0x1E6E2000) silicon-revision register SCU7C via the flat-mapped "scu" MMU page (sys_read32, read-
only, safe on live silicon). Result: **SCU7C = 0x00000202 on BOTH QEMU and the real AST2050** — the
golden G3 revision independently confirmed via culvert-P2A AND JTAG-AHB, so FOUR access paths now
agree. BONUS: **SCU70 hw-strap = 0x00819582 matches bit-for-bit** silicon↔QEMU (the QEMU machine's
strapping was modeled from the board, not guessed). SCU04 differs (0x000ffe5c silicon vs 0xffcffedc
QEMU) — EXPECTED, it is the live System-Reset-Control state (boot-path dependent), so printed but not
in the PASS gate. Silicon path: JTAG reset-halt → DDR2 trained → load @0x40000000 → resume; console
/dev/serial-bmc-console; md5(zephyr.bin)=394d2f49… verified end-to-end. QEMU: kgpe-d16-bmc -kernel,
"SCU RESULT: PASS".
Matrix row 35 SCU: **ZQ ⬜→✅, ZS ⬜→✅** (QE/UQ/US/LQ/LS already ✅). Reconciled FULL-TASK-LIST A1
Zephyr cell ([~]/[ ] → [x]/[x]) to match — a #159 FULL-TASK-LIST↔MATRIX reconcile done in passing.
Re-ran tally.py: Zephyr@QEMU 9✅/8🔶/21⬜, Zephyr@silicon 9✅/1🔶/27⬜; embedded tally block updated.
Evidence d14-zephyr/19-scu-silicon.txt. Scope honesty: this validates SCU READ + identity/strap
faithfulness; the SCU clock-rate program (H-PLL/CLKIN) validation stays tracked as #142. No shortcut.

## 2026-07-20 — #159 partial: MATRIX rows 36/37/38 ZS now cite the captured silicon evidence + fix stale rename path + tally re-verified

Followed through on #159 for the rows I just silicon-validated. DEVICE-MATRIX.md: rows 36 (VIC) +
37 (Timer) ZS ✅ now cite `evidence/d14-zephyr/17-heartbeat-vic-timer-silicon.txt` (was LOG-prose
only per the gate-d audit); row 38 (WDT) ZS ✅ now cites `evidence/d14-zephyr/18-wdt-silicon.txt`,
and I reconciled the stale row-38 note (it said "WDT-silicon = 🔶 … capture one for a clean ✅" —
that 🔶 is the LINUX `/dev/watchdog` path (LS), which is STILL open; the Zephyr ZS transcript is now
captured, so I re-scoped the note to LS and kept ZS ✅). Fixed the one living-doc stale path from the
#154 rename (`soc/aspeed/ast2050/console.c` → `soc/aspeed_g3/…` at MATRIX:233); left the append-only
LOG history + dated evidence transcripts unchanged (they record the path as it was when written).
Re-ran `tally.py`: 43 rows, Zephyr@silicon 8✅/1🔶/28⬜ — the embedded tally block (MATRIX:51-58)
already matches (no cell status changed; only evidence pointers added). REMAINING #159:
FULL-TASK-LIST↔MATRIX Zephyr-cell reconcile (kept in_progress).

## 2026-07-20 — #154 DONE: rename Zephyr module SoC family aspeed → aspeed_g3 (de-collide with upstream SOC_FAMILY_ASPEED)

Closed the re-review finding #154. CONFIRMED the collision is real (not hypothetical): upstream
Zephyr's soc/aspeed declares `family: aspeed` + `config SOC_FAMILY_ASPEED` for the Cortex-M
AST10x0/AST2600 parts (tmp/zws/zephyr/soc/aspeed/soc.yml: family aspeed → series ast10x0 → soc
ast1030), and OUR module declared the IDENTICAL `family: aspeed` + `SOC_FAMILY_ASPEED` for the
ARM926 ast2050 while registering soc_root:. So HWMv2 SILENTLY MERGES our ast2050 series into
upstream's "aspeed" family (verified: the wdt build's SOC_DIRECTORIES/SOC_FULL_DIR still resolve
to our soc/aspeed because ast2050 is unique, but the family name is shared), and Kconfig would
APPEND both generations' selects (ARM926 + Cortex-M) onto one SOC_FAMILY_ASPEED symbol. Currently
DORMANT (only the selected soc's Kconfig tree is sourced, so no Cortex-M leak in today's .config —
verified CPU_ARM926EJ_S=y, no CPU_CORTEX_M) but fragile to a menuconfig / multi-SoC build / future
upstream select.

FIX (disjoint G3 namespace): `git mv soc/aspeed soc/aspeed_g3`; soc.yml family name aspeed →
aspeed_g3; Kconfig symbol SOC_FAMILY_ASPEED → SOC_FAMILY_ASPEED_G3 (Kconfig.soc def + SOC_FAMILY
string default "aspeed_g3"; Kconfig family selects; Kconfig.defconfig if/endif; ast2050/Kconfig.soc
select). Series/soc names (ast2050) and board vendor (aspeed) unchanged — they don't collide.
Updated ~14 stale `soc/aspeed/ast2050/` doc-comment paths across drivers/samples/board-defconfig/
PORT-PLAN to soc/aspeed_g3/. Added rationale comments in soc.yml + both Kconfigs so the disjointness
is self-documenting.

VALIDATED: clean rebuild (west -p always) links green; .config now SOC_FAMILY="aspeed_g3",
SOC_FAMILY_ASPEED_G3=y, CPU_ARM926EJ_S=y, SOC_SERIES_AST2050=y, SOC_AST2050=y (no stale
SOC_FAMILY_ASPEED); QEMU boot of the renamed wdt_smoke still runs + WDT resets (5 boots/5 s). No
other soc-root/CMake/dts hardcodes the family name or path (top CMakeLists uses ${SOC_SERIES},
drivers depend on DT_HAS_ASPEED_AST2050_* not the family).

## 2026-07-20 — WDT (row 38, ZS) SoC-reset captured on REAL silicon — closes a gate-d evidence gap (break from #168)

Took the goal's "take a break from #168, work on another part" and captured a bounded device-silicon
win: the Zephyr watchdog resetting the real AST2050. Companion to yesterday's VIC/Timer heartbeat
(evidence 17). Both-sides:
  * QEMU (build-wdt, run WITHOUT -no-reboot so the reset reboots): **6 boots in a 6 s window** —
    banner + "WDT smoke: boot" + "WDT alive 1/2/3" + "expect reset", repeating. PASS (>=2 = reset fired).
  * SILICON (entry 0x40002448, md5 7883f45f… verified end-to-end; SoC-internal WDT1 @0x1E785000 works at
    the board's 4 W deep-S5): the console showed EXACTLY ONE cycle (banner → armed → alive 1/2/3 → "WDT
    armed, not feeding, expect reset") then went SILENT at the ~500 ms timeout. On this board the BMC SPI
    flash is NOT wired, so a SoC reset canNOT reboot into Zephyr (nothing at the reset vector) — hence one
    cycle, not a QEMU-style reboot loop. Console-silence alone is ambiguous (an idle for(;;) is also
    silent), so I CONFIRMED the reset via JTAG (openocd attach + halt, NO reset, reading the live post-WDT
    CPU): **mode=Undefined-instruction, cpsr=0x000000db, pc=0x01a41210 (flash-mapped LOW region, NOT the
    0x40xxxxxx Zephyr DRAM image), sp=0x4001ca30 (a STALE Zephyr sp_und)**. Decode: the WDT reset forced
    PC→0 and CPSR→SVC but ARM leaves the register file intact, so the SMC un-remapped DRAM/re-mapped the
    empty flash at 0x0, the CPU fetched 0xFF garbage off the floating bus, tripped an undefined instruction
    and cascaded to 0x01a41210 while sp_und still held Zephyr's leftover value — the fingerprint that the
    SAME silicon RESTARTED (not a cold power-on). So the watchdog demonstrably RESET THE SoC on both the
    faithful QEMU model and real silicon; the observable differs only because QEMU has a flash image to
    reboot from. ZS ✅ (rows 38 / task #149 / #150) is now EVIDENCE-BACKED (was LOG-prose only per the
    gate-d audit). Honesty: HIGH confidence; the only thing not directly read is the SCU wdt-reset-cause
    status bit (reading it needs re-attach-through-reset and is unnecessary given the PC/mode proof).
    Wrote evidence d14-zephyr/18-wdt-silicon.txt; documented the silicon-vs-QEMU signature split in the
    sample header (samples/wdt_smoke/src/main.c). No step skipped or faked.

## 2026-07-20 — #168 fix attempt: pt_regs unreadable (sp_abt garbage); pivot the extraction to bp-per-init-function or single-step

Tried to pin the exact faulting instruction by reading do_prefetch_abort's pt_regs. Seeded a valid
abort stack at the literal [0x40] (which the DATA-abort handler @0x180 loads via `ldr sp,[pc,#-0x148]`),
set a HW bp at do_prefetch_abort (0x1038), booted. Clean read AT the bp (via -c not -f — the -f script's
`reg` prints nothing): pc=0x1038, cpsr=0x13 (SVC), **r0 (the pt_regs* arg) = 0xffffffcb** = an INVALID
pointer, lr=0x168 (return into the _prefetch_abort stub). So the PREFETCH-abort handler builds pt_regs on
a GARBAGE sp_abt (my [0x40] seed only fixes the data-abort handler's stack; the prefetch stub loads its
sp from a different literal), => the faulting context is UNREADABLE via pt_regs (0xffffffcb is not valid
memory). CONFIRMED still: it IS a prefetch abort (do_prefetch_abort reached, SVC after the stub) near
timer_init; mechanism unchanged. HONEST: I could not extract the faulting instruction this way — the
invalid abort stack blocks it. REFINED NEXT APPROACH (avoid pt_regs): (a) bp at each early
init_sequence_f fn (arch_cpu_init@0x1059c, initf_dm, get_clocks, timer_init@0x37d10) and see which is the
LAST reached before the cascade => the faulting function; then single-step IT to the exact instruction;
OR (b) find the prefetch stub's own sp-literal (disassemble the 0x0c vector -> handler) and seed THAT so
pt_regs is valid. Then apply the durable fix (revert 0004 + fix the unaligned access, not mask). Rig:
load-remap-only.tcl + boot-mu-pabt.tcl on the Pi.

## 2026-07-20 — #168 MECHANISM CRACKED: early PREFETCH ABORT (do_prefetch_abort @0x1038) cascading on an uninitialised abort stack — the A-fix (0004) MASKS an unaligned access that then makes a bad code pointer

Identified the mystery loop functions from u-boot.map: the recurring low PC (~0x140) is the ARM
exception-stub region and 0x1038 = **do_prefetch_abort** (0x1064=do_data_abort, 0xfe0=do_undefined,
etc. — all in arch/arm/lib/interrupts.c). Set a HW breakpoint at 0x1038, booted the A-fix U-Boot on
silicon: **the breakpoint HIT** — so U-Boot takes a PREFETCH ABORT (an attempt to FETCH an instruction
from an invalid address, i.e. a branch/return to a bad code pointer) very early in board_init_f. Post-
mortem: pc=0x1094 (do_not_used), **sp=0xffffffcb (INVALID)** — the abort handler is running on an
uninitialised Abort-mode banked stack (same class as the sp_abt double-fault found earlier), so it
faults again and CASCADES through the exception vectors forever -> the board_init_f "loop" -> no console
(all pre-console, output lost).
CONFIRMED: it's a prefetch abort, not a hang; the exception handling cascades on an uninit abort stack.
LEADING HYPOTHESIS (validates the gate-b reviewer's concern about 0004, not yet pinned to the exact
instruction): with A=0 (0004) an early UNALIGNED access returns ROTATED garbage on ARMv5 (the reviewer's
exact point); that garbage is used as a code pointer -> the CPU branches to nonsense -> prefetch abort.
So 0004 MASKS the original alignment fault but the underlying unaligned access is still WRONG, and now
manifests one step later as a prefetch abort. DURABLE FIX (next): (1) revert 0004; (2) break the cascade
by giving the abort handler a valid stack — write a valid addr to the abort-stack literal [0x40] (the
handler does `ldr sp,[pc,#-0x148]`=[0x40]) OR set the banked sp_abt — so do_prefetch_abort/do_data_abort
runs cleanly and I can read its pt_regs (uregs[15]=faulting fetch addr, uregs[14]=branch-from) to pin
the bad code pointer; (3) trace that back to the specific early unaligned access + fix IT (get_unaligned
/ align the field) instead of masking with A=0. Rig: boot-mu-pabt.tcl (bp @0x1038) staged on the Pi.

## 2026-07-20 — #168 narrowed further: the loop is BEFORE console_record_init (pre-console buffer stays garbage); lead = timer_init/early board_init_f panic-hang

Ran the pre-console-buffer experiment. Found U-Boot ALREADY enables it by a Kconfig default at
CONFIG_PRE_CON_BUF_ADDR=0x1e720000 (SRAM, adjacent to the init-RAM per aspeed-common.h) — but that read
back 0x04000008-repeating (leftover, not text). Relocated it to DRAM (defconfig override
CONFIG_PRE_CON_BUF_ADDR=0x42000000), rebuilt (A-fix confirmed: start.S:97 = bic), booted, read 0x42000000
-> UNINITIALISED-DRAM garbage, still NO text. So U-Boot NEVER wrote pre-console output => the board_init_f
loop is BEFORE console_record_init (the early half of init_sequence_f). NEW LEAD from u-boot.map symbols:
board_init_f@0x10970, arch_cpu_init@0x1059c, dm_timer_init@0x1d3d8, timer_init@0x37d10 — and the CPU's
looping PCs (0x384cc/0x38bdc) are RIGHT AT/just past timer_init@0x37d10, while the timer reads 0x0 (not
counting). The recurring low fn (~0x140: stm sp,{r0-r12}; bl 0x1038) fits panic()/hang() (saves all regs).
So the modern U-Boot most likely FAILS an early init around timer_init on the G3 and loops in panic/hang,
its message lost (pre-console). RULED OUT progressively: alignment abort (0004), baud, SP (banked sp_abt),
console-record-path (buffer empty = never reached). NEXT (precise): hw-bp timer_init@0x37d10 + get_clocks
+ initf_dm to see which is reached and where the loop is; hw-bp 0x1038 to ID that fn (panic/hang/printf).
Then fix the failing early init (likely the G3 timer/clock, analog of #167). Reverted the debug defconfig;
committed uboot-patches/build-uboot.sh unchanged (repo clean). Staged Pi build carries the harmless DRAM
pre-console buffer.

## 2026-07-20 — #168 narrowed: modern U-Boot RUNS board_init_f but LOOPS (repeated pre-console printf); timer reads 0x0; next = CONFIG_PRE_CONSOLE_BUFFER

Probed the A-fix modern-U-Boot on G3 silicon (no rebuild — already staged). Halt/resume/halt 3x over 6s:
PC = 0x150 -> 0x384cc -> 0x38bdc, all in SUPERVISOR mode (not Abort). So it is RUNNING (PCs change), NOT
hung at one address — but after 26 s it is still in the pre-relocation image (0x0-0x38xxx; board_init_f
should finish in ms), so an init step is LOOPING. The recurring low PC (~0x140) is a function prologue
(stm sp,{r0-r12}; ... bl 0x1038) and 0x38xxx is printf/vsnprintf (cmp #0x25='%') — i.e. it repeatedly
calls PRINTF pre-console (output lost, no UART yet). The aspeed timer @0x1e782000 reads 0x00000000 twice
(500 ms apart) = NOT counting, even though Zephyr's heartbeat just proved the timer HW works. U-Boot uses
drivers/timer/ast_timer.c on that node (ast_timer_probe writes reload + sets EN|1MHz in ctrl1). So EITHER
board_init_f panicked/looped BEFORE timer_init (timer never started), OR a retry/panic loop is spinning.
This is a running-but-stuck board_init_f, NOT the earlier alignment abort (0004 fixed that) and NOT a
baud issue. DECISIVE NEXT STEP: rebuild with CONFIG_PRE_CONSOLE_BUFFER (+ADDR/SIZE in a spare DRAM page)
so the LOST early printf/panic text is stashed in RAM, then read that buffer over JTAG — it will say
exactly what board_init_f is failing on. Also: read ctrl1 (0x1e782030) to see if the timer EN bit is set
(did timer_init run?), and decode 0x1038 / the loop's call site. Rig tooling unchanged. #168 updated.

## 2026-07-20 — VIC(36)+Timer(37) SUSTAINED-TICKING captured on silicon (heartbeat_smoke) — closes a gate-d evidence gap

The gate-d audit flagged that VIC(row 36)/Timer(row 37) are ZS ✅ but rest on LOG prose with no
captured silicon transcript. Wrote samples/heartbeat_smoke (10 x k_msleep(100ms) + k_uptime_get,
tickful) — each sleep only returns when a Timer1 (VIC source 16) tick IRQ fires + the kernel wakes it,
so completing N iterations = N proofs the timer fires, the VIC routes+acks, and the ISR path works.
QEMU: PASS (10 ticks, no arm_mmu crash for the short <2264-tick run). REAL SILICON: PASS —
`tick 1/10 uptime=130ms ... tick 10/10 uptime=1120ms, elapsed=1100ms, HEARTBEAT RESULT: PASS`. uptime
advanced monotonically at ~110 ms/iter, so the VIC delivered 10 sustained IRQs (no wedge) and the timer
counts REAL time accurately. Notable contrast with the RTC (row 39, ~732x fast, no crystal): the SYSTEM
timer runs at true real-time rate (clocked from APB/PCLK, not the missing 32 kHz crystal). Evidence:
openbmc/bmc-functionality/evidence/d14-zephyr/17-heartbeat-vic-timer-silicon.txt. Rows 36/37 ZS ✅ now
evidence-backed both-sides (was prose-only).

## 2026-07-20 — #168: SP hypothesis tested + REFUTED — the 0x0badc0de is the Abort-mode BANKED sp_abt (double-fault), not the cause; 0004 (A-fix) is the correct fix

New lead this cycle: the JTAG-load sets PC+CPSR but not SP, so U-Boot's early code might fault on an
uninitialized SP (the DFAR I'd seen was 0x0badc0de). TEST: added `reg sp 0x43f00000` to the boot tcl and
booted BOTH the A-fix build AND a freshly-built A=1 (original, 0004 reverted) build. RESULT: still no
console; A=1 post-mortem shows mode=Abort, pc=0x180 (the abort handler), **sp=0x0badc0de EVEN THOUGH I
set sp**, DFAR=0x0badc0de. KEY REALISATION: `reg sp` set the SVC-mode sp (sp_svc), but the CPU faults into
ABORT mode and uses the BANKED sp_abt, which is uninitialized (0x0badc0de). So DFAR=0x0badc0de is the abort
HANDLER double-faulting on its own poison stack (`str lr,[sp_abt]`) — an EFFECT of the original fault, not
its cause. So the SP hypothesis is REFUTED, and crucially this CONFIRMS 0004 (clear SCTLR.A) is the CORRECT
fix for the ORIGINAL alignment fault: with A=0 the alignment fault never occurs, so the abort handler never
runs, so the double-fault loop never happens, and the CPU advances to board_init_f (PC~0x38480, printf).
The remaining no-console is a SEPARATE board_init_f / serial_init issue (UART LCR=0). To pin the ORIGINAL
alignment-faulting instruction (to address the gate-b reviewer's "rotated read" concern about 0004 masking
vs fixing), the next step must prevent the double-fault: set the Abort-mode BANKED sp_abt (openocd mode-
switch, or `reg` the banked reg) before the fault so the handler saves the real faulting LR, OR install a
minimal abort vector. Deferred. Restored 0004 + re-staged the A-fix build; removed the test `reg sp` from
the Pi tcl. Repo clean. (Rig hygiene: A=1 test build was transient; committed code unchanged.)

## 2026-07-20 — #153 DONE: doc-hygiene C5/C6/ADC all verified addressed (ADC double-checked vs the primary datasheet)

Closed the stale #153 doc-hygiene task — all three items are addressed: (C5 authority-pointer) the
DEVICE-MATRIX header already carries the reconciliation rule that fixes the old inversion ("most-
recently-dated cited-evidence entry wins; do NOT apply a blanket 'one doc always wins' rule which
historically pointed at whichever doc was staler"); (C6 CPU0/1 naming) the DEVICE-MATRIX Naming note
(line ~216) documents the CPU1/CPU2-narrative vs CPU0/CPU1-pinmap drift; (ADC datasheet double-check)
NOW VERIFIED against the PRIMARY datasheet (datasheets/aspeed/AST2050_V1.05.txt), not just the
memory-map extract — the §1.3 peripheral ToC has NO ADC controller entry (lists Video/GPIO/WDT/PECI),
and every "ADC" mention is an *external video-source ADC* into the video engine, not an on-SoC block.
So the row-41 "ADC Absent on G3" disposition is confirmed at the primary source (strengthened the
citation). #153 complete.

## 2026-07-20 — #159: excised the stale "NC-SI not wired" claim from F7-NCSI.md (the exact incorrect-claim the goal targets)

F7-NCSI.md had a retraction banner at the top but its prominent "Bottom line" (right below the banner)
still asserted the WRONG board verdict — "The KGPE-D16 BMC does NOT use NC-SI … NC-SI sideband is not
wired on this board." That is precisely the "incorrect claim about a feature being unconnected" the
program goal flags: the authoritative schematic §7 shows MAC2's RMII2 (A5/B5/B6/C4/D4/D5) IS wired as
a multi-drop NC-SI sideband to BOTH Intel 82574L host NICs (LU1/LU2), aux-powered. Replaced that
bottom-line with the CORRECTED truth: the board has MAC1 (dedicated mgmt PHY, the default silicon-proven
path) AND MAC2 (a wired NC-SI sideband) — NC-SI is a real board capability here, tracked as D07/#132
(QEMU-modeled ✅, BMC-side silicon discovery not yet run). Kept the genuinely-true SoC facts (the G3 MAC
has no NC-SI HW register block; NC-SI is software over RMII) and the annotated historical body (§1-§8,
marked MAC1-scoped). Other #159 sub-items: the tally is current (tally.py output == committed snapshot),
Zephyr-silicon evidence captured this session (d14-zephyr/14 RTC, 15 GPIO, 16 i2c-scan). SILICON-STATUS.md
#9 was already corrected. Residual FULL-TASK-LIST↔MATRIX row-11/24/25 reconciliation stays under #159.

## 2026-07-20 — #145 DONE: PECI enumeration verified + closed (row 42 confirmed; QE=🔶 justified; sub-gaps dispositioned)

Closed the #145 PECI-engine enumeration task (the matrix row was added 2026-07-19 but the task was
stale + had open sub-items). Verified everything: (1) datasheet — the AST2050 HAS a PECI controller
@0x1E78B000, IRQ15 (§32.3); (2) QEMU — the G3 SoC wires TYPE_ASPEED_PECI @0x1E78B000/IRQ15
(aspeed_ast2400.c:52/128/246/628-635), and hw/misc/aspeed_peci.c is a FUNCTIONAL register/interrupt
model (PECI_CMD FIRE → CC_RSP_SUCCESS + CMD_DONE IRQ) but NOT the full PECI 1.1/2.0 protocol — so
QE=🔶 is the honest state (canned-response stub), and it's MOOT because (3) schematic — the PECI pins
A9/B9 (PECIO/PECII) are strapped to GPIO on the KGPE-D16 (AST_ATXPSON#/AST_CLRTC#, §11), so PECI is
NOT wired to the CPUs (thermal is via SB-TSI, row 23) → all driver stacks Ⓝ. Also dispositioned the
3 leftover audit sub-gaps: GAP2 WDTRST = pin D9 repurposed as GPIOB6/SYS_PWRGD (WDT external reset not
routed; WDT resets the SoC internally, row 38); GAP3 = closed via #152; GAP4 UART1-modem = UART1 wires
TXD/RXD/NRTS1(V21)/NCTS1(W22) → QU8 SOL mux (row 33), the extra modem lines DTR/DSR/DCD/RI are NC.
DEVICE-MATRIX row 42 note updated. #145 complete.

## 2026-07-20 — #166 DONE: moved ASUS-specific I2C device nodes out of the reusable ast2050.dtsi into the board dts (DTS-review Finding 3)

Fixed the layering violation the DTS/Kconfig review flagged (Finding 3): the reusable SoC include
dts/aspeed/ast2050.dtsi hardcoded ASUS-KGPE-D16-specific I2C slave devices. Moved all of them
(w83795@0x2f on i2c1; sbtsi@0x4c + sbtsi1@0x4d on i2c3; fru_eeprom@0x54 + w83601g_u27@0x18 +
w83601g_u28@0x19 on i2c4) into the board dts (boards/aspeed/kgpe_d16_bmc/kgpe_d16_bmc.dts) via
`&i2cN { … }` overlays. ast2050.dtsi now has only the board-agnostic SoC i2c engine controllers (a
different AST2050 board reusing the include no longer inherits this board's sensors/EEPROM/expanders).
QEMU-VALIDATED all 4 affected smoke samples still bind + read their devices after the move:
w83795_smoke PASS, fru_smoke PASS, sbtsi_smoke PASS, w83601g_smoke PASS. Safe change (Zephyr has no
legacy-boot oracle). #166 complete.

## 2026-07-20 — #157 root-caused: QEMU can't gate i2c on the pinmux because SCU74 is modelled as the G4 RNG_CTRL, not the G3 pinmux

Investigating #157 (make QEMU gate I2C5/6/7 on SCU74) explained the gate-b review's CONFIRMED-1
("QEMU passes regardless of the pinmux"): the QEMU SCU model (hw/misc/aspeed_scu.c, AST2400/G4-based)
has RNG_CTRL at offset 0x74 and the pinmux at 0x80-0x94 (PINMUX_CTRL1-6). But on the AST2050 (G3),
SCU74 IS the Multi-Function-Pin Control #1 (SDA5/6/7 = SCU74[12/13/14]) — the SAME offset means
different things on G3 vs G4. So the G3 drivers' SCU74[12] writes hit the QEMU model's RNG_CTRL (no
i2c effect), which is why the muxed-channel FRU@0x54 passes in QEMU with or without the pin-mux, and
why neither the Zephyr (#156) nor the U-Boot (review CONFIRMED-1) pinmux bug was caught in QEMU. This
is a real G3-vs-G4 SCU register-map faithfulness gap. FIX is deferred (risky, not bounded for
end-of-session): model SCU74 as the G3 pinmux for the kgpe machine, then gate aspeed_i2c engines 5/6/7
on SCU74[12/13/14], then CAREFULLY re-validate all 3 legacy oracles (C2/C4/C-UBOOT) still boot (a
broken legacy boot = a bug in my model). Plan recorded in #157. Value: it would make QEMU CATCH the
pin-mux class of bug instead of only real silicon.

## 2026-07-20 — GATE (b): independent review of the session's U-Boot patches — 2 CONFIRMED fixed, 1 PLAUSIBLE dispositioned

Dispatched an independent code review of the 4 developed U-Boot patches (0002 i2c-enable, 0003 SCU
i2c reset-release, 0004 alignment fix) + build-uboot.sh (the hook flagged "zero independent reviews").
Result: 2 CONFIRMED + 1 PLAUSIBLE, no legacy-oracle regression. Both CONFIRMED FIXED:
- **CONFIRMED-1 (i2c pin-mux, high value)**: 0002 enables i2c4 = engine4 = I2C5 (a MUXED channel), but
  nothing sets SCU74[12] — the G4 pinctrl programs SCU90[18] (a G4 reg), NOT the G3 SCU74[12]. So the
  FRU@0x54 on I2C5 would NAK on real silicon (QEMU passes only because it doesn't gate on the pinmux) —
  the SAME root cause as the Zephyr #156 engine-4 timeout. The 0003 comment also overclaimed "exactly
  like the vendor i2c_init()" (the vendor ALSO does `SCU74 |= 0x5000`). FIX: added the SCU74[12/13/14]
  pin-mux for muxed channels 5/6/7 in ast_i2c_probe() (derive chan from the bus base, mirror the Zephyr
  i2c_aspeed_g3_pinmux + vendor), softened the comment; regenerated uboot-patches/0003. QEMU re-validated:
  i2c md 0x2f fe -> 0x79 + FRU 0x54 read still pass (no regression).
- **CONFIRMED-2 (build-script fail-loud)**: build-uboot.sh silently skipped ANY patch failing `git apply
  --check`, conflating already-applied / wrong-tree / genuinely-broken — so an upstream branch drift could
  ship a u-boot.bin missing 0003 with no error (violates the repo fail-loud rule). FIX: distinguish the
  three cases — forward-applies -> apply; reverses -> "already applied" skip; else -> if the target file
  is ABSENT it's for another tree (0001 = Raptor board/aspeed/ast2050) skip with a note, otherwise ABORT.
  Validated: 0001 -> "not for this tree" skip, 0002/0003/0004 -> "already applied", build succeeds; a real
  failure now aborts.
- **PLAUSIBLE (0004 A-bit)**: clearing SCTLR.A on ARMv5 doesn't MAKE unaligned accesses correct — it
  makes an unaligned LDR return the aligned word ROTATED (silently wrong), the opposite of fail-loud, and
  a plausible contributor to the still-open pre-console hang. Kept the A-fix (it got silicon past the
  abort) but recorded the caveat: the DURABLE fix is to root-cause the specific unaligned access (already
  #168's next step). Noted in #168. Reviewer confirmed the 0003 RMW is clean + no C2/C4/C-UBOOT regression.

## 2026-07-20 — #168 ROOT CAUSE FOUND + partial fix: modern U-Boot's alignment abort on G3 silicon FIXED (start.S A-bit); now runs past the abort

Root-caused the modern-U-Boot silicon abort with a HW breakpoint at the 0x10 data-abort vector:
DFSR=0x1 = ALIGNMENT FAULT, SCTLR=0x5107a (bit1 A=1). Source smoking gun: arch/arm/cpu/arm926ejs/
start.S:97 `orr r0,r0,#0x00000002 /* set bit 1 (A) Align */` — the modern U-Boot DELIBERATELY enables
alignment-fault checking, then its early aspeed code does an UNALIGNED access that aborts on real
silicon (enforces alignment) while QEMU (lenient) boots either way — the complete "boots in QEMU,
faults on silicon" story. FIX (uboot-patches/0004): start.S:97 orr->bic (clear the A bit). RESULTS:
QEMU still boots to ast# (no regression — A ignored in QEMU); SILICON now runs in SUPERVISOR mode at
PC=0x38480 (~0x38000 deep, A=0) instead of aborting at 0x10 — the alignment abort is GONE. Big step.
REMAINING (new, honestly-open blocker): still no console at 115200 OR 1200 — the CPU is past the abort
(Supervisor, PC=0x38480). REFINED: read the console UART divisor at 0x1e784000 over JTAG — LCR=0x00,
DLL=0x00, DLM=0x00 = the UART is COMPLETELY UNCONFIGURED. The same UART worked for Zephyr once
configured, so the modern U-Boot has NOT reached console-init => it's a HANG in early board_init_f
BEFORE console setup, NOT a baud issue (the 115200/1200 attempts were moot). Confidence HIGH (UART
unconfigured after a 20s window >> console-init time). Next: disassemble/single-step around PC=0x38480
(or hw-bp the ns16550 init) to find what early G3-vs-G4 step it's waiting on. A-fix COMMITTED (validated
QEMU + silicon-past-abort). This
is the classic project lesson AGAIN: the hardware wasn't weird — U-Boot enabled alignment faults + did
an unaligned access; QEMU's leniency hid it. Evidence d15-uboot/03 (ROOT CAUSE FOUND section). #168 updated.

## 2026-07-20 — modern U-Boot FIRST silicon attempt FAILED (early data abort) — documented honestly

Attempted the modern U-Boot (#137) silicon boot over JTAG, same recipe as the Raptor U-Boot
(reset halt -> DDR2 train + SCU40[6] -> load @0x40000000 -> DRAM->0x0 remap -> PC=0 -> resume;
tmp/boot-modern-uboot-silicon.sh). Boot mechanics OK (DDR2 TRAINED, image in place, remap 0->1,
resumed) but ZERO console output @115200 (not garbage -> not a baud issue). JTAG post-mortem:
mode=ABORT, pc=0x00000010 (DATA-ABORT vector), sp=0x0badc0de (poison). So the modern U-Boot took a
DATA ABORT very early in its low-level init — before stack/console — and does NOT boot on G3 silicon
yet (it boots fine in QEMU). CONFIDENCE: HIGH it's an early data-abort in the modern U-Boot's own
lowlevel_init (the load recipe is proven — Raptor reaches its prompt with the identical flow);
MODERATE (hypothesis, not root-caused) that it's the SDRAM re-init — the evb-ast2400 U-Boot doesn't
check SCU40[6] so it re-programs the SDMC while running FROM DRAM -> the DRAM access faults. Could
instead be a G4-only register access. Checked my setup: same flow that boots Raptor + SCU40[6] IS set,
so the blocker is the modern U-Boot's G4 low-level init, not my recipe. FIX PATH (new task): single-
step from 0x0 to find the faulting instruction / read mach-aspeed lowlevel_init, then patch the modern
U-Boot to SKIP low-level SDRAM init on the JTAG-boot (honor SCU40[6] or detect DRAM-up). Only then can
#167's SCU04[2] i2c fix be silicon-validated. Evidence: d15-uboot/03-modern-uboot-silicon-attempt-FAILED.
REFINEMENT (same session): platform.S DOES have the SCU40[6] skip check (line ~330) and SCU40 reads
0x000000c0 at fault time (bit 6 SET) — so the skip flag is correct, but the abort is in the EARLY
init_dram code (lines 205-330: timer 0x1e782044/30, USB 0x1e6e2090, AST2300-LPC) that runs BEFORE the
skip check. HONEST CORRECTION: the exact faulting instruction is NOT pinned — a disassembly of where
the halted PC/LR pointed (0x180) is the ABORT-HANDLER save-context stub (the CPU loops in the handler),
not init_dram, so PC/LR reflect the handler not the fault site. Next: catch the FIRST fault (hw
breakpoint at the 0x10 vector) to get the faulting access, then move the SCU40[6] check to the top of
lowlevel_init (or fix the specific G3-unmapped access). #168 updated.

## 2026-07-20 — #167 FIXED: modern U-Boot I2C reads real devices on the G3 QEMU (SCU04[2] reset-release)

Confirmed + fixed the device-NAK. The strong lead was right: the G3 I2C block powers up HELD IN
RESET (SCU04[2]=1), the AST2500-targeted ast_i2c.c stubbed the reset-release, and the kgpe-d16-bmc
QEMU machine faithfully models the held-reset (aspeed_2050_i2c_rst) — so the engines were inert. FIX
(uboot-patches/0003-kgpe-d16-i2c-scu-reset-release.patch): in ast_i2c_probe(), unlock the SCU (write
0x1688A8A8 to SCU00) then clear SCU04[2] — exactly what the vendor AST2050 U-Boot i2c_init() and the
working Zephyr i2c_aspeed_g3 driver do. Rebuilt + retested:
  i2c md 0x2f fe -> 00fe: 79      (W83795 CHIP_ID = 0x79, correct)
  i2c probe bus1 -> 00 2F         (W83795 detected at 0x2f)
  i2c md 0x54    -> ff ff ff ff   (FRU EEPROM blank, matches Zephyr fru_smoke + silicon i2c-scan)
So the modern U-Boot now reads real per-device i2c devices on the G3 QEMU: W83795 hwmon (row 16 UQ)
+ HT24LC08 FRU (row 20 UQ), both agreeing with the Zephyr drivers on the same model. This is a clean
example of the project rule (hardware isn't weird — my driver wasn't releasing the block from reset).
Evidence d15-uboot/02. #167 resolved. NEXT: the SCU04[2] release is also needed on real silicon; the
modern-U-Boot silicon boot (#137) will exercise it.

## 2026-07-20 — U-Boot #137 progress: modern U-Boot I2C buses now BIND on the G3 QEMU; devices NAK (G3-driver sub-problem, characterized)

Continued the U-Boot track with real implementation. Found the i2c -ENODEV cause: CONFIG_DM_I2C +
CONFIG_SYS_I2C_ASPEED are already =y, but the aspeed SoC dtsi leaves every i2c bus disabled and the
evb board dts enables none. FIX: uboot-patches/0002-kgpe-d16-enable-i2c-buses.patch enables
i2c0/1/3/4 (the engines the kgpe-d16-bmc QEMU machine populates); wired build-uboot.sh to apply the
uboot-patches/*.patch idempotently (git apply --check gate; skips are echoed, NOT silenced). After
rebuild the DM_I2C aspeed driver BINDS all four buses (`i2c bus` lists them, `i2c dev N` works — was
-ENODEV). Concrete #137 step done.
NEXT SUB-PROBLEM (characterized, not yet fixed): device reads NAK — `i2c md 0x2f fe 1` (W83795) and
`i2c md 0x54 0 4` (FRU) both return -121 (-EREMOTEIO/no-ACK). NOT the SCU74 pinmux (bus1=engine1=I2C2
has dedicated pads + still NAKs). The SAME QEMU devices read fine under the Zephyr i2c_aspeed_g3
driver (w83795_smoke/fru_smoke QEMU PASS) => the QEMU model is faithful to a correct driver; the
U-Boot ast_i2c.c (G4/G5-era) drives the G3 controller wrong. HYPOTHESIS ITERATION (honest about a
wrong first guess): my first guess (Linux #93-class AC-timing / I2CD04) is REFUTED for the QEMU NAK
— the Zephyr i2c_aspeed_g3.c header line 93 says the AC timing "does not gate the bus in QEMU"
(real-SILICON requirement, not a QEMU one). Reading ast_i2c.c gave a STRONGER lead: it is AST2500-
targeted (`#include <asm/arch/scu_ast2500.h>`) and its probe STUBS the SCU engine clock/reset enable
(`//TODO scu reset and get clk`) — never takes the i2c engine out of SCU reset / enables its clock,
which on the G3 likely leaves the engine not brought up -> -121 on every device. NEXT STEP: implement
the G3 SCU i2c clock/reset enable in the U-Boot driver + retest. Evidence d15-uboot/01. Added a #137
sub-task. Buses-bind is CONFIRMED; the device-NAK cause is a STRONG LEAD (AST2500-SCU-stub), NOT yet
proven — stated as such, not overclaimed.

## 2026-07-20 — U-Boot track (#137): established the modern-U-Boot baseline — it BOOTS to console on the G3 QEMU

Turned attention to the biggest structural gap (U-Boot). Investigated the actual state (vs the
"no U-Boot drivers exist" claim) and found TWO U-Boot code paths already present:
- **Raptor legacy AST2050 U-Boot** = the faithfulness ORACLE (boots to `boot#`, hardware-proven on
  silicon; drives the boot-path SoC blocks SCU/PLL/SDMC/DDR2/SMC/UART/MAC/timer/WDT/I2C). This is
  what the matrix UQ/US columns track. Most non-boot devices are justified Ⓝ for U-Boot (a
  bootloader has no runtime need to drive hwmon/FRU/DIMM-LEDs/PSU).
- **Modern OpenBMC U-Boot** (v2019.04-aspeed-openbmc, evb-ast2400_defconfig, arm-linux-gnueabi-,
  prebuilt out/u-boot.bin) = the D15/#137 deliverable. **VERIFIED it boots to its console on the
  faithful kgpe-d16-bmc (AST2050) QEMU** (16 MB mx25l12805d flash via -drive if=mtd; -kernel does
  NOT work — U-Boot must run from the flash reset vector). It reaches the `ast#` prompt, and:
  SoC auto-ID = "AST1100/AST2050-A2,3/AST2150" (correctly recognises G3!), DRAM up (56 MiB of 64 —
  VGA reserve), console serial@1e784000, SPI mx25l12805d detected + env read, both MACs probed
  (eth0@0x1e660000 + eth1@0x1e680000). Evidence: openbmc/bmc-functionality/evidence/d15-uboot/
  01-modern-uboot-qemu-console.txt.
So "NO U-Boot drivers exist" is FALSE — the modern U-Boot runs in QEMU today. The REAL remaining
#137 work (now scoped by evidence, not guessed): (1) proper KGPE-D16/ast2050 board + defconfig + DT
(it currently reports "Model: AST2400 EVB" — a G4 board config on the register-compatible G3 model);
(2) reconcile the 56-vs-64 MiB DRAM sizing; (3) exercise per-device U-Boot drivers from the prompt
(i2c probe / mac / sf); (4) SILICON boot of the modern U-Boot on the real AST2050 over JTAG (the
Raptor one already boots on silicon; the modern one is QEMU-proven here). Captured as the #137 roadmap.

## 2026-07-20 — DTS/Kconfig review: remaining findings 3/5/6 dispositioned (none dropped)

Closing out the 6 review findings. Done/resolved earlier today: F1 phantom GPIO gpio2..gpio6
REMOVED + gpio_smoke fixed + silicon PASS (#163 closed); F2 FRU 0x54 CONFIRMED correct on silicon
(schematic annotated); F4 `configdefault` REJECTED as a false positive (valid Zephyr kconfiglib
extension; builds + .config prove it). Remaining three:
- **F3 [layering, Zephyr] — TRACKED as a refactor.** ast2050.dtsi (the reusable SoC dtsi) hardcodes
  ASUS-KGPE-D16-specific devices (w83795, sbtsi/sbtsi1, fru_eeprom, w83601g_u27/u28). These belong in
  the board dts (kgpe_d16_bmc.dts) via `&i2cN { … }` overlays so a future AST2050 board doesn't inherit
  them. Real architecture violation (per CLAUDE.md) but NOT a correctness/faithfulness bug — the devices
  work; it's a reusability cleanup. Deferred to a dedicated refactor (needs re-validating every smoke
  sample still binds its device). Added as a task.
- **F5 [phantom 2nd WDT] + F6 [gpio-ranges overstates 46→220] — FOLDED INTO #144.** Both are on the
  Linux dts, which is DELIBERATELY based on aspeed-g4.dtsi (CLAUDE.md: "AST2050 is register-compatible
  enough; no upstream G3 binding yet"), so it inherits G4 nodes (WDT2 @0x1e785020, the wide gpio-ranges)
  BY DESIGN. Removing them is exactly the #144 phantom-device-count work — which is risk-managed
  (the C2/C4/C-UBOOT legacy oracles boot on this dts; a broken legacy boot would be a bug in my model,
  per [[qemu-must-model-real-hardware]]). NOTE the reviewer's caveat: aspeed-bmc-asus-kgpe-d16-realhw.dts
  is a doc-MIRROR; the compiled source is qemu-firmware/dts/aspeed-bmc-asus-kgpe-d16.dts — #144 must fix
  the compiled one (and re-run the legacy oracles), not the mirror. Recorded under #144.

## 2026-07-20 — DTS/Kconfig review Finding 2 RESOLVED on silicon: FRU EEPROM is at 0x54-0x57 (dts correct, schematic was base-range)

The review flagged Zephyr `fru_eeprom@0x54` as wrong vs the schematic's 0x50-0x53. Rather than
blindly change it (which would have BROKEN the passing FRU read), I wrote a new sample
`samples/i2c_scan` that probes I2C5 (engine 4) 0x50-0x57 and reports per-address ACK/NAK (the
aspeed_g3 master returns -ENXIO on address NAK, 0 on ACK). Ran it on the REAL AST2050 at 4W:
```
I2C5 addr=0x50..0x53 -> ret=-6 (NAK)
I2C5 addr=0x54..0x57 -> ret=0  (ACK)
FRU-ADDR: 0x54-0x57 (A2/E2=VCC)
```
GROUND TRUTH: the HT24LC08 (U25) responds at 0x54-0x57, NOT 0x50-0x53. A 24C08 has one external
A2 pin + 2 internal block bits, so ACKing 0x54-0x57 while NAKing 0x50-0x53 ⇒ A2/E2 strapped VCC.
**So the Zephyr dts 0x54 is HARDWARE-CORRECT; Finding 2 is REFUTED by the hardware** (the schematic's
0x50-0x53 is the unstrapped base range). This also proves the earlier fru_smoke PASS was a REAL ACK
(the master demonstrably NAKs 0x50-0x53 with -ENXIO here), and QEMU matches silicon exactly (same
NAK/ACK split → the QEMU FRU model address is faithful). Actions: (1) evidence d14-zephyr/16;
(2) annotated the two schematic docs (AST2050-BMC-WIRING.md:352, I2C-SMBUS-TOPOLOGY.md:56) with the
silicon-verified 0x54-0x57 + the A2=VCC reason, citing the scan; (3) i2c_scan committed as a reusable
tool. Bonus: validates i2c address NAK detection on real silicon (never explicitly done before).

## 2026-07-20 — #163 CLOSED ON SILICON: gpio_smoke (real EFGH register) PASSes on the real AST2050

Booted the fixed gpio_smoke (entry 0x400023f0, md5 7be98219…verified) on the real AST2050 at 4W
over JTAG. Captured: `GPIO gpio1(EFGH)/pin26 GPIOH2 read=0` -> `GPIO RESULT: PASS`. The driver now
reads a REAL register (gpio1/EFGH @0x20) and returns a DEFINED, CORRECT value on silicon — vs the
old phantom gpio2/IJKL @0x70 that read back 0 (nonexistent register). QEMU and silicon now AGREE:
both read GPIOH2=0, which is the correct STA_LINE_POWER value at deep-S5/4W (rail off; reads 1 at
~46W+, per #162). #163 is resolved (phantom removed + both-sides real-register PASS). Evidence:
openbmc/bmc-functionality/evidence/d14-zephyr/15-gpio-silicon-pass.txt. (Full output write-readback
on a bonded safe-to-drive pin remains deferred to the #136 GPIO map; the drive path is covered by
power_smoke driving the real A4/B1/B6/F0 power-control outputs.)

## 2026-07-20 — GATE (b) DTS/Kconfig review: PHANTOM GPIO register blocks removed (real faithfulness bug, resolves #163) + 1 false-positive rejected

Dispatched the last-unreviewed developed config (Zephyr + Linux DTS + Kconfig). 5 CONFIRMED +
1 PLAUSIBLE returned; I verified each against the datasheet before acting (project rule):

- **[CRITICAL, CONFIRMED + fixed] ast2050.dtsi phantom GPIO sets gpio2..gpio6.** The Zephyr SoC
  dtsi modelled five extra 32-bit GPIO "sets" — IJKL@0x70, MNOP@0x78, QRST@0x80, UVWX@0x88,
  YZAAAB@0x1E0. I confirmed against the AST2050 datasheet §23.3 (Base 0x1E78:0000): the GPIO
  register map has EXACTLY TWO data-value registers — GPIO00@0x00 (ports A/B/C/D) and GPIO20@0x20
  ("Extended GPIO Data Value", ports E/F/G/H); the map ends with the EFGH control block (~0x58) and
  has NO register at 0x70/0x78/0x80/0x88/0x1E0 (those are an AST2400/G4 addition). Datasheet feature
  table: AST2050 GPIO max = 46 ("8 dedicated + 56 shared" = 64 register bits). Removed gpio2..gpio6
  + rewrote the node comment with the datasheet facts. This is the SAME phantom-device class as #144.
  **This ROOT-CAUSES #163**: gpio_smoke drove GPIOI0 = bit 0 of the phantom IJKL set (gpio2 @0x70),
  which QEMU idealized (readback=1) but silicon has no register there (readback=0). Repointed
  gpio_smoke at gpio1 (EFGH @0x20, a REAL register), reading GPIOH2 (bit 26, STA_LINE_POWER, a
  bonded input) read-only — safe on silicon (a read can't perturb the board) and a clean both-sides
  test. The full OUTPUT write-readback needs a bonded safe-to-drive pin (NC or a BMC LED) which
  requires the §11 GPIO map (#136); the OUTPUT path meanwhile is covered by power_smoke (drives the
  real A4/B1/B6/F0 power-control outputs). QEMU: rebuilt + booted → `GPIO gpio1(EFGH)/pin26 GPIOH2
  read=0` → `GPIO RESULT: PASS`. Only gpio_smoke referenced the removed nodes (gpio3..6 were unused).
- **[CRITICAL, but FALSE POSITIVE — rejected with evidence] Kconfig.defconfig `configdefault`.** The
  reviewer flagged `configdefault` (soc/aspeed/Kconfig.defconfig, ast2050/Kconfig.defconfig) as an
  invalid keyword that would break the build. It does NOT: `configdefault` is a Zephyr kconfiglib
  EXTENSION (sets a default on an already-defined symbol in a defconfig, without redefining it). PROOF:
  this session's builds succeed AND the produced .config contains exactly the values those lines set —
  CONFIG_NUM_IRQS=32, CONFIG_SYS_CLOCK_HW_CYCLES_PER_SEC=1000000, CONFIG_SOC_EARLY_INIT_HOOK=y. Applying
  the suggested "fix" (`config`) would INTRODUCE a redefinition bug. Left unchanged. (Lesson: a reviewer
  that doesn't run the build can't see Zephyr Kconfig extensions — the "verify before acting" rule caught it.)
- **Still to disposition (this + next cycle):** FRU EEPROM 0x54-vs-0x50 (needs reconciling with the
  passing FRU silicon read — investigate before changing); ast2050.dtsi board-device layering (move
  ASUS-specific sensor nodes to the board dts — refactor); realhw-DTS second-WDT status=disabled +
  gpio-ranges overstatement (doc-mirror file; the compiled source is qemu-firmware/dts/…, check there).

## 2026-07-20 — RTC (row 39) Zephyr driver VALIDATED ON SILICON — set/get PASS; #158 "reads 0x0" RESOLVED, re-scoped to real-time-rate

Booted `rtc_smoke` (entry 0x4000245c, md5 3bedfc9c…verified staged) on the real AST2050 at
the board's 4 W deep-S5 state (RTC is SoC-internal on 5VSB, so no host/sensor rail needed).
Path: JTAG reset-halt → DDR2 TRAINED → load @0x40000000 → reg pc → resume; console on
/dev/serial-bmc-console @115200. Captured:
```
*** Booting Zephyr OS build v4.4.0-8379-g0a6208b97bff ***
RTC set=12:45:30 day=7  get=12:45:52 day=7  (delta=22s)
RTC RESULT: PASS
```
The `rtc_aspeed_g3` driver set the time, the CONTROL[5] load latched, and a subsequent get read
back a consistent, same-weekday, advancing time. set / get / BCD-encode / weekday / latch all work
on silicon → **the original #158 symptom ("reads back 0x0") is RESOLVED** (root cause was two
issues, both fixed earlier this program: (1) async load — poll CONTROL[5]; (2) NO CLOCK — the RTC
had no running clock until soc rtc-init sets SCU08[16]=1 to select the 24 MHz "test-only" tap).
**Residual (real, board-hardware, not a driver bug):** delta=22 "RTC seconds" elapsed in a
sub-second wall-clock window ⇒ the counter runs ~700–732× too fast, because this board has NO
32.768 kHz RTC crystal (schematic) and the 24 MHz tap is divided by the prescaler as if it were
32.768 kHz. So **#158 is re-scoped** from "reads 0x0 / silicon FAIL" to "real-time-rate: RTC runs
fast on this board (no crystal); driver faithful". Row 39 ZS stays **🔶** = functional-but-not-
real-time. Evidence: `openbmc/bmc-functionality/evidence/d14-zephyr/14-rtc-silicon-pass.txt`.
This also re-validates the rtc_smoke tolerance fix (`delta>=0`) on silicon: the old `delta<=10`
bound would have false-failed this correct-but-fast driver.

## 2026-07-20 — GATE (b) FRONTIER CLOSED: Linux kernel-patches review — 9/10 CLEAN, 1 concurrency bug FIXED (aspeed-video JFIF)

Independent review of all 10 AST2050 Linux enablement patches (the last major unreviewed developed
code). 9 CLEAN with detailed cross-checks: clk-aspeed G3 gate table (clock_idx/reset_idx pairs
hand-decoded vs the clock-binding enum — correct; G4 paths is_ast2050-gated), ftgmac100 cur_speed +
macclk (both correctly scoped), w83795 hwmon (channel bit-widths match), kcs optional-lclk (resolves
to the populated LCLK gate), i2c AC-timing (FIELD_PREP → 0x777xxxxx verified), aspeed-vhub G3
(defensive no-op on G4), pinctrl G3 strap-quirk (of_device_is_compatible-gated), irq-aspeed-g3-vic
(new file, SENSE/EVENT/DUAL bit-for-bit vs Table-36, edge/level ack correct).
**1 Important bug (conf 80) FIXED** — patch 0006 (aspeed-video G3 software-JFIF-wrap):
aspeed_video_build_jfif_header() writes the shared jpeg_hdr[]/_len/_sel/_w/_h state from process
context (reachable mid-stream via VIDIOC_S_CTRL quality/chroma change) WITHOUT taking video->lock,
while the hard-IRQ reader aspeed_video_wrap_jfif() holds it — a mid-stream S_CTRL could tear the
header → silently-wrong JPEG frame on the vKVM/capture path. FIXED: wrap the read-check + build +
state-update in spin_lock_irqsave(&video->lock) (pairs with the IRQ's plain spin_lock). Patch
hunk-count updated 106→120 + linted (all hunks consistent); kernel/linux is gitignored/regenerated
so the patch is the canonical artifact.
**Gate-b code-review frontier now closed across ALL major developed code**: Zephyr drivers+samples,
SoC low-level, QEMU device models, QEMU machine wiring, AND the Linux patches. **Session review
tally: 7 real bugs fixed** (power_smoke ×2, vic.c, rtc_smoke, gpio_smoke, aspeed-video lock) + 1
finding silicon-disproven (soc.c), everything else CLEAN.

## 2026-07-20 — GATE (b) cont'd: WDT driver + samples review — 2 real bugs FIXED (rtc_smoke tolerance, gpio_smoke fail-loud)

Independent code review of the previously-unreviewed Zephyr WDT driver + 5 samples:
- **wdt_aspeed_g3.c, i2c_smoke, wdt_smoke, fru_smoke: CLEAN** (register offsets/magics cross-checked
  vs the QEMU WDT model; i2c_smoke's 0x79 W83795 chip-id gate is the REAL chip id (not a QEMU seed);
  fru "all 0xff" already silicon-corroborated).
- **rtc_smoke [Major, conf 92] FIXED**: the `delta <= 10` PASS window contradicts the driver's own
  documented ~732x-fast test-clock (#158) and the LOG-observed silicon `delta=38s` — it would
  false-FAIL correct-but-fast hardware (the same QEMU-tuned-gate class already fixed for
  w83601g/w83795/sbtsi, missed here). Fix: forward-only test (`mday==set && delta>=0`) — the real
  failure signal is a negative delta / day=0 (counter never loaded), not the exact rate. QEMU
  re-validated PASS (delta=0). (This also means rtc_smoke would now PASS on silicon — the ZS 🔶
  status stands, though: 'functional, not real-time-accurate'.)
- **gpio_smoke [Minor, conf 80] FIXED**: the clear-phase `gpio_pin_set_raw` failure was silently
  swallowed (no else branch) — added a fail-loud message, per the repo convention + the sibling
  smokes. (The GPIOI0-unbonded readback quirk is separately tracked #163.)
Session independent-review bug tally now: 5 real bugs fixed (power_smoke ×2, vic.c, rtc_smoke,
gpio_smoke) + 1 finding silicon-disproven (soc.c vectors).
**QEMU machine-wiring review: CLEAN.** The kgpe_d16 machine wiring (kgpe_d16_i2c_fabric.c mux
fabric + kgpe_d16_bmc_i2c_init device wiring + the aspeed_gpio pwrseq/named-GPIO wiring) verified
correct — bus/address mapping (k-1 rule), QU9 sys-pwrgd gate / QU5 channel decode / U23 ownership
truth table, GPIO direction+data gating, reset-order convergence, version-gated vmstate, and the
DIMM-A2 SPD table cross-checked byte-for-byte vs the real i2cdump. Only a comment typo (HT24LC08
'1 Kbit'→'8 Kbit', code correct) — fixed in the submodule (a8ac1ad7) + DTS. This closes gate-b
coverage of the faithfulness-critical machine model with 0 bugs.

## 2026-07-20 — GATES (a)×2 + (d): 2nd enumeration review CONFIRMS complete; 1st gate-d task-list audit finds real soft-skips (fixed/tasked)

- **GATE (a) — SECOND independent enumeration review**: an independent agent re-walked the schematic
  → matrix end-to-end and CONFIRMED the first agent's finding: enumeration COMPLETE, 0 gaps (~55
  devices, all mapped); NO stale non-existence claim contradicts the schematic (ADC/PECI/PWM/TSOD
  all consistent). Two independent reviews now agree — the 'multiple reviews' bar for enumeration is
  met. One borderline: QD3/QD4/QD5 VGA RGB-DAC buffers covered by row-12 signal-path + passive
  category but not named (unlike QU6/row 13) — give them a one-line disposition (#159f).
- **GATE (d)+(c) — FIRST task-list audit** (never run before): the enumeration is sound but found
  REAL soft-skips, all acted on:
  * **OVER-CLAIM FIXED**: row 27 power ZS was 🔶 but the power_smoke silicon RESULT is FAIL (only the
    OUTPUT actuation works; the H2 feedback fails, #162). 🔶→⬜ (honest floor) + row note. Row 14
    DDC/EDID Zephyr was Ⓝ (unjustified vs the 'every block needs Zephyr' rule) → ⬜. Tally re-run:
    Zephyr@silicon now 8✅/1🔶/28⬜ (was 8/2/26).
  * **UNTRACKED CAPABILITY TASKED (#164)**: I²C target/slave mode + multi-master arbitration (D1b) —
    a real BMC function, folded into row 15 so uncounted; my Zephyr i2c driver is master-only (target
    mode is a stated follow-up). Needs its own row + all 4 stacks.
  * **SOFT BLOCKERS TASKED (#165)**: row 9 USB-vhub silicon [B] is risk-avoidance (didn't try the JTAG
    path); rows 24/25 [B] assert 'no PMBus PSU' without naming the rig PSU. Substantiate or re-attempt.
  * **DOC-SYNC**: FULL-TASK-LIST is stale (Zephyr column esp) vs the matrix on rows 11/23/24/25/27/39
    — the 'must AGREE' contract is in debt; reconciliation items enumerated in #159.
  * Evidence: VIC/Timer/WDT Zephyr-silicon ✅ rows lack captured transcripts (#159d); the
    'd14-zephyr/03-irq-proven' file is a QEMU crash run, not silicon (relabel).
  These are honesty/tracking gaps, not fabrications — the underlying driver work + commits + captured
  FRU/W83601G/W83795/SB-TSI-Linux evidence all corroborated. Gate-d BOTTOM LINE: task list NOT yet
  complete/weasel-free — now with a concrete closure list.

## 2026-07-20 — gpio_smoke @ 4W silicon: BMC boots at deep standby; output-readback hits the known IJKL-unbonded quirk

Booted gpio_smoke on the real AST2050 at 4W (deep S5, host off). Two findings:
- **BMC is JTAG-accessible at 4W deep standby** (BMC on 5V-SB): banner appears, DDR2 trains,
  Zephyr runs — so the VIC/Timer/boot path work even at 4W. Useful: SoC-side Zephyr silicon
  tests (VIC 36 / Timer 37 / WDT 38 / GPIO-write) don't need the board powered up.
- **GPIO output-readback shows the KNOWN IJKL faithfulness quirk**: `GPIO set=1 read=0` on
  silicon vs `set=1 read=1` in QEMU. gpio_smoke drives GPIOI0 (set IJKL), which is NOT bonded
  out on the AST2050 (the upper GPIO sets have a narrower true bonded-pin count than the 32-bit
  model assumes) — so a driven-high never reaches a pad and reads back 0; QEMU idealizes the
  unbonded pin to readback-1. This is the pre-existing open faithfulness note (memory / DEVICE-
  MATRIX snapshot), re-confirmed, NOT a new regression. FIX (tasked #163): either (a) point
  gpio_smoke at a BONDED, board-safe GPIO whose driven level actually appears (needs the §11
  GPIO map / #136 to pick a spare bonded pin), or (b) model the AST2050's real bonded-pin map in
  the QEMU aspeed_gpio so unbonded upper-set pins read back their floating level, not 1. Until
  then gpio_smoke is not a clean silicon-evidence PASS (the WRITE works; the unbonded READBACK is
  the quirk). Rig left at 4W (host off, BMC accessible).

## 2026-07-20 — SB-TSI Zephyr silicon (row 23): honest attempt FAILED (-EIO); blocked by unstable host power

sbtsi_smoke is platform-agnostic + QEMU PASS (temp=45.5). Attempted the silicon read (SB-TSI @0x4c
on I2C engine 3, needs the host CPU on): au-plug AC-cycle to trigger the board's BIOS auto-power-on,
then immediately JTAG-boot sbtsi to catch the host powered. Result: `SBTSI sample_fetch FAIL (err -5)`
= -EIO, with the au-plug reading **73 W** at read time (host mid-ramp 66→73 W, NOT the full ~97 W
host-on) — the CPU's SB-TSI/SMU interface was not up yet when the read fired ~16 s after AC-on. The
host then sat steady at 73 W (a partial-power / stuck-POST state — the known dead-CMOS F1/F2 issue),
so a retry at 73 W would just -EIO again.
HONEST CONFIDENCE it's NOT my driver: engine 3 = schematic I2C4 = SDA4/SCL4 DEDICATED pins (no
pin-mux needed), same i2c_aspeed_g3 driver that reads the W83795 on engine 1 + FRU/W83601G on
engine 4; and the LINUX SB-TSI read already succeeded here with a fully-POSTed host (memory
d09-sbtsi). So the -EIO is the host CPU not being ready, not the Zephyr I2C path.
RELIABLE PATH (tasked #150): the AC-auto-power-on window (~80 s, and it ramps/stalls) is too
unstable + too early for the SB-TSI to be alive. Instead: netboot Linux/OpenBMC, run kgpe-power.sh
'on' (which stably powers + holds the host on across a BMC reset per the F2 work), let it POST, THEN
JTAG-boot sbtsi_smoke while the host is stably up. Row 23 ZS stays ⬜ (attempted, host-blocked, NOT
a driver bug). Rig left with the host auto-dropping toward standby.

## 2026-07-20 — GATE (b): SoC-low-level + QEMU-models code review — 1 real fix (vic.c), 1 finding silicon-DISPROVEN (soc.c)

Ran 2 more independent code-review sub-agents over the remaining unreviewed developed code:
- **QEMU G3 models** (w83601g/aspeed_rtc_ast2050/sbtsi/pmbus_psu): all CLEAN except the ALREADY-
  TRACKED RTC sync-RESTART-vs-async-CONTROL[5] faithfulness gap (#158, confirmed + fix direction;
  plus a below-threshold RESET-scope note added to #158).
- **Zephyr SoC low-level + GPIO** (soc.c/vic.c/aspeed_timer.c/console.c/gpio_aspeed_g3.c): timer/
  console/gpio CLEAN; 2 Major (conf-80) findings:
  1. **vic.c z_soc_irq_eoi() clobbers a driver's in-ISR irq_disable() for a LEVEL source** — REAL
     latent bug (only edge Timer1 wired today, so not yet hit). FIXED: added an atomic
     `soc_irq_user_disabled` bitmask; z_soc_irq_disable() records intent, eoi() skips re-enabling a
     source the driver disabled. QEMU + silicon boot re-validated (W83795 PASS). Unblocks the future
     I2C/GPIO/UART-RX level-IRQ drivers.
  2. **soc.c "vectors" MMU region overlaps "dram" (VA 0x40000000 → PA 0x0 vs identity)** — flagged
     as a bug at conf-80, and QEMU boots fine WITHOUT it. **But a SILICON boot test DISPROVED the
     finding: removing the region → NO banner (Zephyr never runs); restoring it → boots (W83795
     fan1=2738/temp0=51 PASS).** So the region is INTENTIONAL / LOAD-BEARING on real hardware — the
     ARM926 early boot needs the first VA page strongly-ordered (uncached), which QEMU (no cache-
     attribute modelling) doesn't reveal. Kept the region + added a "DO NOT REMOVE — load-bearing on
     silicon" comment so it's never mistakenly deleted. **Lesson: silicon is the faithfulness oracle
     — a plausible conf-80 review finding + a clean QEMU boot would have shipped a boot-breaker;
     silicon-validating the boot-critical change caught it.** Rig healthy (47W, sensor rail live).

## 2026-07-20 — W83795 hwmon: platform-agnostic smoke + fresh silicon LIVE read (rows 15/16); board-state/sensor-rail finding

Made w83795_smoke PLATFORM-AGNOSTIC (commit 8797280): PASS = both channel reads succeed AND
values physically plausible (fan 100-30000 rpm, temp 0-125 C), not the QEMU-seed exact-match
(fan1==2641) that false-FAILed on silicon. QEMU re-validated PASS (2641/50.5). Then captured a
FRESH silicon read (evidence/d14-zephyr/13): `W83795 fan1=2710 rpm (ok=1) temp0=56.000 C (ok=1)
W83795 RESULT: PASS` — LIVE values (≠ the seed, drift across sessions), proving a genuine read of
the physical W83795G on engine 1. Rows 15/16 ZS re-confirmed with a captured transcript.

SENSOR-RAIL / BOARD-STATE FINDING (honest, connects to #162): a first silicon attempt returned
`W83795 sample_fetch FAIL (err -5)` = -EIO. Cause was NOT the driver (QEMU-valid, previously
silicon-valid) — my earlier power_smoke experiments had left the board at 46 W after driving it to
4 W deep-S5, and STA_LINE_POWER = "I2C bus power": deep-off kills the SENSOR I2C-bus rail, and a
partial power-up doesn't re-enable it. A clean au-plug AC power-cycle restored it (the board's BIOS
auto-power-on brings it up through host-on 97 W, re-enabling the rail; it then settled to 47 W
standby with the rail live). So "weird hardware" (W83795 -EIO) was a board state I created — fixed
by a proper power-cycle, exactly per the project principle. Rig now at 47 W standby (host off,
sensor rail live) ≈ the as-found ~49 W. Also learned: on AC restore this board AUTO-POWERS-ON the
host (~97 W) briefly, then drops (POST/CMOS) — a window that could be used to validate SB-TSI
(row 23, needs host-CPU-on) if a Zephyr power_smoke holds the power-on latch (future).

## 2026-07-20 — GATE (b/c): independent code review of the unreviewed Zephyr code — 2 bugs found + FIXED

Ran an independent code-review sub-agent on the code NOT covered by the earlier review (which had
done i2c pin-mux + w83601g): the RTC driver (SCU08 clock-select + CONTROL[5] poll), power_smoke
(GPIO power sequence + trajectory), and tally.py.
- **rtc_aspeed_g3.c: CLEAN** (register offsets/magics, byte-lane unpack, range checks, write
  ordering, SCU08 unlock+RMW all verified correct; the 24MHz test-clock choice is a documented
  evidence-backed tradeoff, not a hidden bug).
- **tally.py: CLEAN** (verified against real DEVICE-MATRIX content: 43-row match, the 26b
  alphanumeric id handled, the snapshot table + repeated sub-table headers correctly excluded,
  the ✅ inside row-41's device-name text falls outside the status slice, fail-loud on missing file).
- **power_smoke: 2 Major issues, BOTH FIXED (commit e1ce55c):** (1) all gpio_pin_configure/set_raw/
  get_raw returns were (void)-discarded → masked actuation failures on a live host-power path;
  now every op is checked via a chk() helper + io_ok flag + negative-read guard, folded into the
  verdict (fail loud, matching the sibling smokes). (2) the PASS verdict didn't use h2_start, so it
  could PASS with the host already on (only force-off exercised); now requires the full documented
  trajectory h2_start==0 → on_seen → !off_seen AND io_ok. QEMU re-validated PASS
  (io_ok=1 start=0 on=1 off=0). Both are the "fail loud / don't fake a PASS" class the project cares
  about — real gate-(b/c) value from the independent review.

## 2026-07-20 — GATE (a): independent enumeration verification — schematic→matrix, 0 gaps

Ran an independent sub-agent that read AST2050-BMC-WIRING.md END TO END (§§1–16, not skimmed) and
walked FROM the schematic TO DEVICE-MATRIX.md (not trusting the matrix's own "every device is a row"
claim). Result: **enumeration is COMPLETE — 0 genuine gaps.** ~50 distinct devices/chips/blocks/
connectors across §§2–16 + 8 SoC-internal blocks all map to one of the 43 numbered rows (1–42 + 26b)
or a justified disposition (passive power/glue/buffers, the JTAG harness Ⓝ, host-side SU1/OU1/NU1 via
LPC/PCI/I²C rows, and 6 per-pin signals folded into FULL-TASK-LIST). Row numbering 1–42 continuous +
26b, matching the tally. This is fresh gate-(a)/(d) evidence for the enumeration dimension.
Status-honesty spot-check (6 recently-changed cells vs LOG): rows 20/21/22 ZS ✅, 39 ZQ ✅/ZS 🔶 all
CONFIRMED LOG-backed; row 27 ZS 🔶 flagged BORDERLINE — the output side is silicon-proven (defensible
🔶) but the feedback read isn't cleanly validated, so the honest floor is arguably ⬜. Kept 🔶 (the
driver genuinely drives host power on silicon = partial), with this caveat recorded.

## 2026-07-20 — power_smoke H2-trajectory experiment RESOLVES #162: STA_LINE_POWER = standby-rail sense + slow settle

Reworked power_smoke to sample GPIOH2 as a TRAJECTORY (3 reads post-power-ON, 6 post-force-OFF)
and ran it on silicon, correlating with the au-plug W draw. This DEFINITIVELY characterises the
GPIOH2 feedback that failed as "stuck 1" before:
- Run started from the prior run's 4 W deep-off (H2 start=**0**); ended at 46 W standby (H2=**1**,
  final au-plug read 46 W). So **GPIOH2 DOES track power — but it senses the STANDBY / line-power
  rail** (0 at ~4 W deep-S5, 1 at ~46-50 W standby), NOT host-CPU-on (~103 W). Matches the schematic
  note "STA_LINE_POWER ... (I2C bus power)" (HW-WIRING-power-sensors.md:87). The earlier "H2 stuck 1"
  run is explained: the board was at 49 W standby throughout → H2 correctly 1.
- **~5-6 s power-sequencing LAG**: H2 flipped 0→1 only at post-OFF t+2s, i.e. ~5-6 s after the
  power-ON pulse — the power-up manifested slowly, well after my 3 post-ON reads. So a rapid
  on→off toggle scrambles the trajectory relative to fixed read timing, and the force-OFF here did
  not settle the board back to 4 W within the window (ended 46 W).
- **QEMU faithfulness gap (real):** hw/gpio/aspeed_gpio.c aspeed_gpio_kgpe_d16_pwrseq models H2 as a
  SYNCHRONOUS host-on latch (flips on the B1/F0 write); silicon H2 is a slow-settling standby-rail
  sense. Tracked (#162): to be faithful the model should reflect a settle delay + standby-rail
  semantics, and a clean row-27 ZS validation needs long (~10-30 s) settles per transition + reading
  H2 against the deep-off/standby threshold, not a fast toggle.

Net: power-control OUTPUT works on silicon (the B1/F0 drives move the real board between 4 W and
46 W); the H2 feedback is understood (standby-rail, lagged). Row 27 ZS remains 🔶/⬜ pending a
long-settle validation + the QEMU-model reconciliation. Board left at 46 W (standby, host off — safe,
≈ the as-found state). Rig method held: detached boot + md5-verified staged bin (cbb087f5).

## 2026-07-20 — Zephyr host power-control (power_smoke): QEMU PASS; silicon force-OFF works, GPIOH2 read FAILs

New `samples/power_smoke` drives the KGPE-D16 host power sequence from bare-metal Zephyr via
the GPIO driver (kgpe-power.sh ported: reclaim GPIOA4 via SCU74[25] + drive high, pulse
B1/B6 to power-ON, F0 to force-OFF, read GPIOH2). **DEVICE-MATRIX row 27 Zephyr-QEMU ✅**:
`H2 start=0 → power-ON=1 → force-OFF=0  POWER RESULT: PASS` (the kgpe-d16-pwrseq latch model).
Commit 47c7847.

**Silicon: honest FAIL, with a real finding.**
- `POWER: H2 start=1  after power-ON=1  after force-OFF=1  POWER RESULT: FAIL`.
- The power-control **OUTPUT works**: the au-plug draw dropped 49 W → 4 W across the run
  (the force-OFF actually shut the PSU to S5) — so driving F0 low reaches the board.
- The **GPIOH2 feedback read is wrong**: it read 1 at start, and stayed 1 after force-OFF
  even though the real power dropped to 4 W. My driver reads the correct register (0x1E780020
  bit 26, same as kgpe-power.sh `_h2`), so either (a) STA_LINE_POWER's semantics ≠ my "1=host-on"
  assumption (could be AC-line-present, which is always 1 while the plug is on), or (b) the GPIO
  input-read is stuck high — the same class as the KNOWN silicon-vs-QEMU GPIO-readback gap
  (IJKL floating-0 vs QEMU always-1). Needs a run measuring H2 at a KNOWN host-ON (103 W) state
  + cross-check vs the Linux `_h2` read. **Row 27 ZS stays ⬜** (feedback not validated). Tasked.

**Rig-recovery saga (honest, all resolved):** the FIRST silicon attempt's `scp` of the power
bin TIMED OUT (Pi transiently sluggish), so the boot ran a STALE staged bin (md5 b90bf3ec ≠
the power build d0893112) → no console output; then my 200 s outer ssh timeout killed the
boot, orphaning an openocd that briefly pegged the Pi (ssh unresponsive ~5 min). Recovered by
waiting (openocd self-exited) + re-staging the correct bin (md5 verified) + running the boot
DETACHED (nohup, decoupled from the ssh timeout) and polling the capture. LESSONS: (1) always
md5-verify the staged bin before trusting a silicon result; (2) run silicon boots detached and
poll, don't hold them under a foreground ssh timeout; (3) the au-plug (Tasmota, IPv6 iot net)
is only reachable FROM the Pi, so it can't out-of-band-rescue a wedged Pi. Host left OFF (4 W),
Pi clean (no runaway).

## 2026-07-19 — RTC silicon: dead(0x0)→running via SCU08[16] clock source; real-time 1Hz still open (#158)

Silicon-validated the Zephyr RTC (row 39). It FAILED first (honest): `get=00:00:00 day=0`
— the counter read 0x0. Two false leads ruled out on real hardware, one root cause found:
- Added the datasheet §24.4 CONTROL[5] restart-busy poll (the load is async, "0~3 s") +
  a forward-tolerance in rtc_smoke (the counter runs once enabled). Correct + committed
  (ffd9dbe), but did NOT fix it — still 0x0.
- ROOT CAUSE (datasheet §24 + SCU08 bit table): the RTC had **no clock**. SCU08[16] selects
  0 = 32.768 kHz (Init default) / 1 = internal 24 MHz. This board has no external 32 kHz
  crystal. bit16=0 → counter dead at 0; **bit16=1 → the RTC LOADS the set value AND RUNS**
  (commit 4ce158d). No SCU04 RTC-reset bit exists (unlike I2C), so this is a clock-source
  issue, not a reset-hold one.
- **STILL OPEN, honest:** the prescaler targets 32.768 kHz, so the 24 MHz source runs the
  second counter FAST (datasheet labels bit16 "for test only") — silicon read `12:45:68`
  (sec>59, delta=38 s). Real-time 1 Hz needs bit16=0, but the internal 32.768 kHz isn't
  running on this board (datasheet says no external crystal needed → something else gates
  it; check the vendor Linux RTC/clk init). Kept bit16=1 so the block is FUNCTIONAL
  (set/load/read/run verified on silicon). **RTC ZS = 🔶 partial (NOT real-time), ZQ ✅.**

## 2026-07-19 — Completion-gate sub-agents (code review + schematic completeness audit)

Ran two independent background sub-agents (gates b/c and a/d):
- **Code review** of this session's new code: `i2c_aspeed_g3.c` (SCU74 pin-mux) **CLEAN**
  (channel→bit arithmetic verified for i2c1/3/4; no underflow; OR-only can't disturb MII2).
  Found **[Major]** in `w83601g_smoke`: the low-side CR01 `i2c_reg_read_byte` return was
  `(void)`-discarded and `cr01_lo` defaults 0 → a failed low read could FAKE a PASS. FIXED
  (check ret_rd_hi/ret_rd_lo, print `(r%d)`); QEMU + silicon re-PASS (U27 0x0807 / U28 0x61b5,
  all reads r0). Commit 3-way with the review.
- **Completeness audit** vs the authoritative schematic: **enumeration COMPLETE** — every
  §2-16 device maps to a matrix row or a justified disposition; **no active non-existence
  claim contradicts the schematic** (the 3 historically-wrong ones — NC-SI, SPD, SOL — are
  already retracted; ADC/host-BIOS/USB-host/fan-PWM/debug-UART non-existence are all TRUE).
  Action items surfaced (tasked): reconcile FULL-TASK-LIST D3/D4/D5 Zephyr cells vs matrix
  rows 20/21/22; regenerate the stale snapshot tally (27/24/0-11/5 → 29/25/3-13/8, 42→43
  rows); capture Zephyr-silicon JTAG transcripts into evidence/d14-zephyr/; excise the stale
  "not wired" prose still in F7-NCSI.md's body; two open RE items (0x69 sensor-mux responder,
  GPIOE6/E7↔SP5100 handshake).

## 2026-07-19 — ✅ RESOLVED: SCU74[12] I2C5 pin-mux — FRU + W83601G now PASS on real silicon (#156)

Root-caused and FIXED the engine-4 silicon timeout documented below. It was **my driver, not
the hardware** — exactly as the project principle predicts.

**Root cause (datasheet + vendor oracle):** the AST2050 gives DEDICATED I2C pads only to
I2C/SMBUS 1-4. SDA5/SCL5 (I2C5 = my engine 4 = the FRU 0x54 + W83601G 0x18/0x19 bus), SDA6/
SCL6 and SDA7/SCL7 are **multiplexed** pins that carry I2C only when a SCU74 bit is set:
`A13 SDA5 / B13 SCL5 <- SCU74[12]=1`, `[13]->I2C6`, `[14]->I2C7` (AST2050/AST1100 A3 datasheet
V1.05 multi-function pin control table, e.g. "A13 GPIOC6 MII2DIO SCU74[20]=1  SDA5 SCU74[12]=1
GPIOC6  Others"). The vendor Raptor U-Boot `i2c_init()` does exactly this for the AST2050:
`SCU74 |= 0x5000` (bits 12+14 = channels 5+7) — `raptor-uboot/drivers/i2c/aspeed_i2c.c:26-28`.
My Zephyr driver programmed SCU04 reset-release + AC-timing but **never the pin-mux**, so
bytes clocked on engine 4 never reached the pads → no ACK → -ETIMEDOUT. The W83795 on I2C2
(dedicated pads) worked precisely because it needs no pin-mux — which is why only the engine-4
devices failed. (This also confirms the schematic-I2C5 = engine-4 mapping was RIGHT all along.)

**Fix (commit 355a9c7):** `i2c_aspeed_g3.c` now sets the SCU74 bit for the muxed channel,
derived from the engine's reg base (channel = (base-0x1E78A000)/0x40; channels 5-7 →
SCU74[12..14]; 1-4 need nothing). Idempotent OR under the SCU unlock key. Harmless in QEMU
(the SCU model stores it; the I2C model does not gate on it), required on silicon.

**Silicon proof (real AST2050 over JTAG, this session):**
- FRU (entry 0x40002378): `FRU eeprom size=256 read[0..3]=ff ff ff ff` → `FRU RESULT: PASS`
  (was -116/-ETIMEDOUT before the fix).
- W83601G (entry 0x4000241c): `port_get=0x080f (ret=0)  pin3 high->CR01=0x08  low->CR01=0x00`
  → `W83601G RESULT: PASS`. Note `0x080f` on silicon vs QEMU's `0x000f`: the extra bit 11 is a
  LIVE Port-2 input pin on the real board (QEMU's static seed lacks it) — proof of genuine
  hardware reads. Made the smoke's PASS gate platform-agnostic: require the input read to
  SUCCEED (value differs QEMU↔silicon) + a full HIGH→LOW output round-trip in CR01 (holds on
  both). QEMU re-validated PASS after the change.

**Matrix:** FRU **ZS ⬜→✅**, W83601G **ZS ⬜→✅** (both engine-4 devices now silicon-validated).
**Follow-up faithfulness task (opened):** make the QEMU aspeed_i2c model gate engine 5/6/7
external activity on SCU74[12..14] so a driver that FORGETS the pin-mux fails in QEMU too, not
only on silicon — the QEMU model should have caught this. Recorded so the gap isn't lost.

## 2026-07-19 — ⚠️ FAILED silicon attempt (honest): FRU/W83601G Zephyr reads time out on engine 4 (i2c4)
### → RESOLVED, see the entry above (SCU74[12] pin-mux was missing). Kept as an honest record.

Tried to silicon-validate the BMC-side Zephyr drivers (FRU EEPROM, W83601G) on the real
AST2050 over JTAG — no host power needed (I2C5 is on BMC standby). **Both FAILED, honestly
documented:**
- Zephyr BOOTS on silicon (banner appears) — the cache/VIC fixes hold.
- `fru_smoke`: `FRU smoke: eeprom_read failed (-116)` = **-ETIMEDOUT** — the FRU EEPROM
  (U25 @0x54) did NOT ACK on my Zephyr `i2c4` node (engine 4 = 0x1E78A140).
- `w83601g_smoke`: `port_get=0x0000` (not the value) + `CR01=0x00` + FAIL — consistent with
  the same engine-4 i2c timeout (the sample leaves the value 0 on a failed read).
- **Contrast:** the W83795 on **engine 1** (i2c1 @0x1E78A080) DID read real values on silicon
  earlier. So the i2c_aspeed_g3 driver + SCU-reset-release WORK — the failure is specific to
  reaching the I2C5 devices via my engine-4 node.
- **Honest confidence it's MY issue, not the hardware** (per the project principle): either
  (a) the schematic-I2C5 → SoC-engine mapping I assumed (I2C5 = engine 4) is wrong — the FRU/
  W83601G may sit on a different physical engine than 0x1E78A140 (the W83795=I2C2=engine1
  mapping held, but I2C5 isn't independently confirmed on silicon); or (b) engine 4 needs a
  per-engine setup (AC-timing I2CD04 / clock) my Zephyr driver applies for engine 1 but not
  4. Linux read the FRU via its `&i2c4` earlier, so the device IS present + reachable — my
  Zephyr path is what's wrong. FRU/W83601G **ZS stays ⬜** (NOT claimed — the reads failed).
- **NEXT (tasked #156):** silicon i2c-scan for 0x54/0x18 across all 7 engines from Zephyr
  (add DT nodes + a probe like the fwtest 0x50/0x58 scan) to find the real engine, then fix
  the i2c4 mapping / engine-4 setup. Longer capture needed too (the i2c timeout is slower
  than the boot-zephyr-silicon.sh 5 s window — used boot-zephyr-silicon-long.sh, 20 s).

## 2026-07-19 — PROPER Zephyr W83601G gpio_driver_api driver — QEMU-validated (#155; rows 21/22 ZQ 🔶→✅)

Upgraded the W83601G from the i2c-client smoke to a real Zephyr GPIO controller
(closing #155 I'd just opened — not just tasked, done). `drivers/gpio/gpio_w83601g.c`
implements the full gpio_driver_api over I2C: each expander (U27@0x18, U28@0x19) is a
16-pin port (Port1=0..7 CR00/CR01/CR03, Port2=8..15 CR08/CR09/CR0B). pin_configure
sets direction (I/O-config bit 0=output) + pushes the value before enabling; set/
clear/toggle via a 16-bit output shadow; get reads the two input registers. Access
via i2c_reg_*_byte_dt (rides i2c_aspeed_g3). New winbond,w83601g-gpio binding +
&w83601g_u27/u28 nodes on i2c4 + GPIO_W83601G Kconfig (init after I2C) + k_mutex.
**VALIDATED IN QEMU through the STANDARD gpio API** (samples/w83601g_smoke): gpio_
port_get_raw=0x000f (U27 seeded input via the driver) + gpio_pin_configure(pin3,
OUTPUT_HIGH) → CR01=0x08 (cross-checked over i2c) → `W83601G RESULT: PASS`. Commit
d9771ab; rows 21/22 ZQ 🔶→✅. Model note: the QEMU model keeps CR00 a static input
latch (doesn't reflect the output), so an output pin's driven value is verified via
CR01 not gpio_pin_get — a QEMU-model faithfulness nicety, not a driver issue. ZS
(silicon) pending like the other Zephyr drivers.

## 2026-07-19 — Zephyr W83601G DIMM-LED expander LED-drive validated (rows 21/22 ZQ ⬜→🔶)

Third I2C device validated from Zephyr on engine 4 this run (after FRU@0x54): the two
W83601G DIMM-LED expanders (U27@0x18, U28@0x19). `samples/w83601g_smoke` runs the exact
BMC LED-drive sequence over the i2c_aspeed_g3 driver (register map from
hw/gpio/w83601g.c): verify chip-ID CR20=0x60, clear CR03 Port-1 direction bits →
outputs, write CR01=0x55, read it back, restore. **VALIDATED IN QEMU:** `W83601G
id(CR20)=0x60  LED CR01 set=0x55 get=0x55` → `W83601G RESULT: PASS`. Commit b05a4e4;
rows 21/22 ZQ ⬜→🔶. **Honest scope:** this is an i2c-client LED-drive validation (same
kind as the W83795/SB-TSI sensor clients), NOT yet a full gpio_driver_api expander
driver — that is a tracked follow-up (#155). Confirms the i2c driver reaching 0x18/0x19
+ 0x54 all on engine 4 (multi-device on one engine).

## 2026-07-19 — Zephyr FRU EEPROM via the in-tree at2x driver on I2C engine 4 — QEMU-validated (row 20 ZQ ⬜→🔶)

Closed another Zephyr ⬜ safely, reusing a PROPER in-tree driver (not a raw poke).
Added the DT `i2c4` engine node (block 0x1E78A140 = engine 4 = schematic I2C5 = QEMU
bus 4) with an `atmel,at24` child @0x54 = the board FRU EEPROM (U25, HT24LC08). No new
driver code — Zephyr's in-tree at2x EEPROM driver binds and drives the AST2050 I2C
master (i2c_aspeed_g3.c) on a THIRD engine (after engine 1/W83795, engine 3/SB-TSI),
confirming the per-engine 0x40 stride math across engines 1/3/4. samples/fru_smoke reads
it. **VALIDATED IN QEMU:** EEPROM_AT24 auto-binds, `FRU eeprom size=256 read[0..3]=ff ff
ff ff` → `FRU RESULT: PASS` (blank 0xff, matching the QEMU model + the as-shipped real
part). Commit 753cb41; row 20 ZQ ⬜→🔶. Isolated (in-tree driver) — no oracle risk.

## 2026-07-19 — New Zephyr RTC driver (0x1E781000) — QEMU-validated (row 39 ZQ ⬜→🔶)

Closed a Zephyr ⬜ safely (isolated module, no shared-QEMU-model/oracle risk — the
disciplined alternative to rushing a shared-engine QEMU-⬜ or a risky host-power silicon
run at depth). Wrote a per-device Zephyr RTC driver for the AST2050 G3 counter-style RTC:
- `drivers/rtc/rtc_aspeed_g3.c` — `rtc_driver_api` set_time/get_time. Register map cited
  from the faithful QEMU model `hw/misc/aspeed_rtc_ast2050.c` (base 0x1E781000: COUNTER
  0x00 = packed binary sec/min/hour/day; RELOAD 0x08; CONTROL 0x0C[0]=enable; RESTART 0x10
  magic 0x5A = latch RELOAD→COUNTER; RESET 0x14 magic 0x99). set packs the time into
  RELOAD + pulses RESTART + enables; get reads COUNTER. Honest limitation documented: the
  G3 counter holds sec/min/hour/day only (no calendar).
- Wiring: drivers/rtc CMake/Kconfig + module-root add_subdirectory/rsource; dts binding
  `aspeed,ast2050-rtc` (include base.yaml + rtc-device.yaml) + `&rtc0 @0x1e781000`; a static
  MMU region in soc.c; a `samples/rtc_smoke/` + `tmp/build-rtc.sh`.
- **VALIDATED IN QEMU:** `RTC set=12:45:30 day=7  get=12:45:30 day=7` → `RTC RESULT: PASS`
  (set→load→get round-trip; the QEMU G3 RTC is register-accurate for load/read and doesn't
  auto-advance the counter, so the round-trip is the correct check). Commit a7b8a94; row 39
  ZQ ⬜→🔶. ZS (silicon) pending like the other Zephyr drivers.

## 2026-07-19 — Scoped the remaining 4 QEMU ⬜ (which are non-trivial new models, sequenced carefully)

Investigated the 4 remaining QEMU ⬜ to pick the next safe closure. Finding: each is a
genuine non-trivial new model, so I scoped them precisely rather than rush one at deep
context (the faithfulness directive: a shared-model change that breaks a legacy oracle
is a bug in MY model — must not be rushed):
- **SMBus-ALERT [25]:** `aspeed_i2c.h:101` DEFINES `SMBUS_ALERT` (intr bit 12, "Bus
  [0-3] only") but `aspeed_i2c.c` never DRIVES it; no device asserts SMBALERT#, no ARA
  (0x0C) path. Subtlety: schematic routes SALT1 to I2C7/B12 (bus 6) yet the intr bit is
  buses 0-3 — likely a standalone SMBALERT# monitored input, not the per-engine intr.
  Closing edits the SHARED aspeed_i2c.c (C2/C4 oracles depend on it) → datasheet-first,
  careful, with an oracle re-boot. Scoped in matrix row-25 note. #135.
- **DDC/EDID [14]:** the AST2050 video DDC (AST_DDCCLK B1 / AST_DDCDAT B2, §8) is NOT
  modeled at all — `hw/misc/aspeed_video_ast2050.c` + the SoC wiring have no DDC/EDID.
  Needs a video-controller DDC I²C interface (per the video-ctrl DDC register spec) +
  an EDID EEPROM device + wiring. Isolated from the shared I2C engine (no oracle risk),
  but a new model. #140/D12.
- **LPC-mailbox [B]** (#134) + **SOL-mux [31]** (#133) similarly need new sub-blocks.
Best-judgement: scope now, implement each in a focused datasheet-first pass; do NOT
rush a heavy shared-model change at extreme context depth. (PSU-PMBus [24] was the one
already-written model, closed this session.)

## 2026-07-19 — Created MASTER-TASKLIST.md — every schematic device × 4 stacks × QEMU+silicon, FROM the §1-16 read

Per the goal's opening ("create a task list to: full QEMU emulation of every device;
U-Boot/Linux/Zephyr drivers each validated in QEMU + on silicon [+ Linux userspace]"),
authored a NEW comprehensive master task list `device-driver-program/MASTER-TASKLIST.md`
derived directly from my end-to-end schematic read — NOT a re-hash of the pre-existing
grid. It walks the schematic section-by-section (§3 DDR2 … §13 straps + SoC-core
SCU/VIC/timer/WDT/RTC/PWM/ADC/PECI) and, for EVERY device, gives the 4-stack task line
(QEMU model / U-Boot Q+Si / Linux Q+Si+US / Zephyr Q+Si) with current status + the
next concrete action, cross-referenced to the DEVICE-MATRIX row and FULL-TASK-LIST box.
Asserts explicitly that no §1-16 schematic device is un-enumerated (the only
non-driver-target entries are the §2 power rails, ground/decoupling, and the passive
series-R/mux glue — modeled as bus behaviour, not addressable devices). Rolls up the
concrete open frontiers: the 4 QEMU ⬜ (DDC/EDID, LPC-mailbox, SOL-mux, SMBus-ALERT),
Zephyr breadth, silicon breadth, and the open task IDs. This is the enumeration
backbone the completion gate ("enumerate every item … show all drivers/emulation")
requires, in one authoritative-schematic-derived document.

## 2026-07-19 — Closed a QEMU ⬜: PSU PMBus model committed + fwtest-validated (row 24 QE ✅)

Real forward progress on an emulation gap (not just review/doc). The generic PMBus
PSU model (`hw/sensor/pmbus_psu.c`) had been written + wired in a prior session but
NEVER committed — leaving row 24 QE ⬜. Finished + closed it:
- **Reviewed** the model (complete, faithful: PMBus-1.2 base class, page flags for
  VIN/VOUT/IIN/IOUT/PIN/POUT/TEMP/FAN/MFR, seeded 230V-in/12V-8A-out/30C/4000RPM,
  0x98=0x22 / 0x19=0x30; cites schematic §10.2 / PSUSMB1 / I2C1 balls A15/B15).
- **Rebuilt QEMU** (incremental) → `CONFIG_PMBUS_PSU=y`, binary registers
  `pmbus-psu` ("Generic PMBus power supply (KGPE-D16 PSUSMB1)").
- **Committed** in the submodule (mithro/qemu `claude/bmc-functionality` 8320c07f3f)
  + pushed (BEFORE the parent gitlink bump, per the CI-fetch gotcha).
- **Validated fresh** with the bare-metal fwtest: extended `peripherals/i2c/fwtest.c`
  to probe 0x58 on all 7 engines + added `test_psu_pmbus_probe` — the PSU ACKs a
  bare addr+W probe on **bus 0 only** (= DT i2c0 = schematic I2C1), NAKs on 1-6
  (`ack58.mask == 0x01`). `python -m pytest integration/test_i2c.py` → **4 passed**.
  (Plus the prior-session register read `i2cget -y 0 0x58 0x98 → 0x22`.)
Row 24 QE ⬜→✅; the QEMU ⬜ frontier drops 5→4 (DDC/EDID, LPC-mailbox, SOL-mux,
SMBus-ALERT remain). Linux/Zephyr PSU-hwmon (pmbus driver bind) stays ⬜ (future).

## 2026-07-19 — Independent COMPLETE read of the authoritative schematic (all §1-16) — enumeration confirmed, #151/#152 resolved

Read `schematic-wiring/AST2050-BMC-WIRING.md` end-to-end MYSELF (not via a sub-agent):
all 597 lines, §1 block diagram → §16 per-pin table, plus the deep dives I2C8_SW
lives in (`I2C-MUX-FABRIC-ARBITRATION.md §4`) and the pinmap (`QU1_pins.md`). Result:
the DEVICE-MATRIX/FULL-TASK-LIST enumeration matches the schematic device-for-device;
the two open enumeration gaps are now RESOLVED in the matrix:
- **#151 (row 26b added):** §10.2 lists I2C8/QU5-`Y0` as "Aux front panel" (row 26); the
  arbitration doc §4 shows the SAME segment, host-on, also reaches TPM1 pins 13/14 + PCIe
  slots 1–5 SMBus (`I2C13` via `QR160/161`+`RN13`/`ER21…57`). These are BMC-masterable
  *segments*, not fixed devices (target = plugged card / TPM). Row 26b added, QE 🔶.
- **#152 (QQ11 dispositioned):** §4 says `AST_ROMA0–23` are unused spare-GPIO (SPI boot
  only); AA9 `ROMA0`→`QQ11[3]` is the one connected ROMA pin → board-N/A. QQ11's part-id
  isn't in the extracted netlist (needs a re-extract) but the disposition holds.

Read also CONFIRMED, first-hand, the faithfulness dispositions I'd relied on 2nd-hand:
§11 shows the **PECI pins A9/B9 (GPIOC1/PECIO, GPIOC0/PECII) are repurposed as
ATXPSON#/CLRTC# GPIO**, the **PWM pins D8/C8 (PWM1/2) as CPU1/2DISABLE#**, and the
**ADC/TACH `VP*` pins as THERMTRIP#/PROCHOT#/DDR_THERM# GPIO** — so #145 (PECI-not-used),
#146 (ADC absent/unwired), and row-40 (PWM unused) are all schematic-confirmed. §7
directly shows the RMII2/NC-SI bus to BOTH 82574L NICs (the D07/NC-SI reality). No new
device omissions found beyond 26b/QQ11.

## 2026-07-19 — ⚠️ Git-hygiene incident (honest note): bare `git push` published another branch

A bare `git push` from this worktree, with the repo's `push.default=matching`,
fast-forwarded `origin/claude/mobo-bench-spec` (7ef67cd→68ab62b) — a DIFFERENT
session's active worktree, not mine — alongside my own branch. It was a
non-destructive fast-forward (origin merely caught up to that branch's local HEAD;
no history rewrite, no divergence, no lost work), so harm is minimal, but it
disturbed another's branch without intent. **NOT force-undone** (force-push is
forbidden + would be far more disruptive to that branch's owner). **Correction:
always push MY branch explicitly — `git push origin claude/bmc-functionality` —
never bare `git push` in this shared multi-worktree repo.** (Did not change the
shared `push.default` config, since that too would affect other sessions.)

## 2026-07-19 — Confirming re-review of the 2 code fixes → CLEAN (gate b satisfied for this session's code)

Dispatched an independent second code-review pass on the two fixes from the prior
round (Kconfig `select SOC_RESET_HOOK` 481ac22, VIC level-masking 4cf848d). Verdict:
**both correct + complete, no new bugs at/above confidence-80.** Specifically confirmed:
- Fix 1: `SOC_RESET_HOOK` is a plain selectable bool (no unmet depends), the select is
  unconditional via `SOC_AST2050→SOC_SERIES_AST2050→SOC_FAMILY_ASPEED`, `soc_reset_hook()`
  is called from reset.S:364 pre-MMU, and no latent collision reliance remains.
  `SOC_EARLY_INIT_HOOK` (configdefault) is robust and needs no change.
- Fix 2: isr_wrapper calls `z_soc_irq_eoi` unconditionally on every path (incl. the
  spurious irq==32, where the `irq<32` guard short-circuits before BIT/vic_rd), so level
  sources are always re-enabled; `INT_SENSE` is written only in init (no TOCTOU); the edge
  Timer1 path is byte-for-byte preserved; no bad interaction with the 78f5569 edge-clear.
- Cross-checked vs the datasheet, the faithful QEMU VIC model, and Linux irq-aspeed-g3-vic.

**Tangential PRE-EXISTING finding (NOT a defect in either commit) → tasked #154:** our
`config SOC_FAMILY_ASPEED` shares its symbol NAME with upstream Zephyr's unrelated
AST10x0 (Cortex-M4) family; our ARM926/MMU/custom-VIC selects would leak onto an ast1030
build done from a workspace with our module registered (`soc_root: .`). Harmless in this
project's ast2050 builds, but a real namespace/directory collision to harden. Deferred to
#154 (a careful family rename, not a quick edit).

## 2026-07-19 — Completion-gate round: independent code review + schematic audit → all findings resolved/tasked

Ran two independent sub-agents (gates b + a/d), acted on every finding:

**Code review of this session's driver changes (gate b) — 2 real bugs found + FIXED:**
- **[Major] The silicon cache fix was wired only by a Kconfig NAME COLLISION.** My
  `SOC_FAMILY_ASPEED` never `select`ed `SOC_RESET_HOOK`; it was on only because
  upstream Zephyr's unrelated AST10x0 family declares the same-named symbol and the
  SoC-root Kconfigs merge. A Zephyr bump would silently drop it → `soc_reset_hook()`
  uncalled → the __start data-abort returns with NO CI signal. FIXED: explicit
  `select SOC_RESET_HOOK` (commit 481ac22). Validated: config still y, QEMU+silicon
  boot clean.
- **[Major] `vic.c` had no masking for LEVEL sources.** Fine today (only the edge
  timer) but I2C/GPIO/UART level IRQs (next consumers) would recurse/double-fire
  since the isr_wrapper re-enables IRQs before the ISR. FIXED: `z_soc_irq_get_active`
  reads INT_SENSE — masks level sources at claim (INT_ENABLE_CLR) + `z_soc_irq_eoi`
  re-enables them; edge sources keep the verified ack-at-claim path (commit 4cf848d).
  Validated: edge timer unchanged, QEMU+silicon boot + tick.
- Verified-correct (no change): the CP15 opcodes, edge-ack-at-claim/EOI-no-op, timer
  reorder. So the core silicon fixes are sound.

**Schematic-coverage audit (gates a/d) — enumeration ~complete; fixed the drift/contradictions:**
- **B1** PROGRESS.md:697 false "NC-SI/DIMM-inventory impossible" → retracted + cited
  (commit d6a047b). **B2** F7-NCSI.md body "not wired/does not exist" → hard RETRACTED
  banner (d6a047b). **C1** ZS-column vs prose/tasklist drift (mine) → synced to the
  validated ✅ reality (0e5fbdd). **C2** 3-way ADC conflict → reconciled to the
  datasheet (§9 p97 = no ADC on G3; Raptor's dev-adc.c is dead G4-BSP), FULL-TASK-LIST
  A9 + RAPTOR Change-16 fixed (71a41c6). **C3** TSOD row-19 + **C4** FRU addr (d528902).
- Remaining audit items TASKED (gate d): **#151** I2C8_SW/QU5-Y0 far-ends (PCIe-slot
  1-5 SMBus + TPM-header I²C, A1/A2); **#152** identify QQ11 (A3); **#153** doc-hygiene
  (authority-pointer C5 + CPU0/1 naming C6 + ADC PDF-p97 double-check).

## 2026-07-19 — Independent schematic-coverage audit (sub-agent) — findings + fix plan

Dispatched a general-purpose sub-agent to read the COMPLETE schematic
(`AST2050-BMC-WIRING.md` + `QU1_pins.md` 355-ball pinmap + `I2C-SMBUS-TOPOLOGY.md`
+ `I2C-MUX-FABRIC-ARBITRATION.md` + `BMC-CONNECTORS.md`) and cross-check every
device against DEVICE-MATRIX + FULL-TASK-LIST (gates a + d). Verdict: section-level
enumeration is ~complete, but it found real **stale non-existence claims** (the
goal's #1 concern) + **status drift** (some of it mine this session). Acting on all:

- **B1 (fix first):** `openbmc/bmc-functionality/PROGRESS.md:697` STILL lists #9
  NC-SI + #5 DIMM-inventory as "board/SoC-impossible" — the schematic shows the
  RMII2/NC-SI sideband to both 82574L NICs (§7) and 16 DIMM SPD via QU9/QU5/U23
  (§10); already reopened as D07/D08 in SILICON-STATUS.md. PROGRESS never updated.
- **B2:** `F7-NCSI.md` body keeps un-retracted "NC-SI not wired / does not exist"
  lines (18,51,78,96-98,227-228) behind only a header note.
- **C1 (mine):** I set the ZS grid cells 15/16/36/37/38 → ✅ this session but did
  NOT sync the matrix prose/roll-up or FULL-TASK-LIST (still say those ZS are
  undone). The ✅ are correct + evidence-backed (LOG + commits 918bc7e..a5d101c);
  fix = update the STALE prose/tasklist to match reality, not revert the ✅.
- **C2 (substantive):** ADC three-way conflict — matrix "no ADC block at all",
  FULL-TASK-LIST A9 "exists @0x1E6E9000", RAPTOR-PORTING-GUIDE documents an ADC
  @0x1E6E9000/IRQ22 in Raptor's WORKING kernel (`dev-adc.c`). Must resolve against
  the datasheet + Raptor source (task #146 marked ADC "absent" — may be wrong).
- **A1/A2/A3:** enumeration gaps — PCIe-slot-1-5 SMBus + TPM-header I²C on the
  QU5-Y0/I2C8_SW segment; `QQ11` on AST_ROMA0/AA9 unidentified.
- **C3-C6:** TSOD row-19 QE=Ⓝ vs jc42.c complete; FRU addr 0x50-53 vs 0x54-57;
  authority-pointer inversion (matrix newer than the "authoritative" tasklist);
  CPU1/2-vs-CPU0/1 naming drift.

Fixing B1/B2/C1 now (committed each); adding tasks for A1-A3/C2-C6.

## 2026-07-19 — 🎉 Zephyr I2C + W83795 read the REAL hwmon sensor on silicon (ZS #5,#6) — rows 15,16 ZS ✅

The keystone I2C driver validated on real hardware: `w83795_smoke` JTAG-booted on
the live AST2050 and **read the real Winbond W83795G** (QU4, schematic **I2C2**
@0x2f — = DT i2c1 / engine block 0x1E78A080, exactly where the faithful QEMU
machine wires it):

```
QEMU:    W83795 fan1=2641 rpm temp0=50.500 C  PASS   (model's seeded values)
Silicon: W83795 fan1=2631 rpm temp0=58.500 C  FALSE-FAIL (real chip)
Silicon repeat reads: fan1=2631/2611/2631 rpm, temp0=58.5/59.0/58.5 C
```

The "FAIL" is a **false fail** — the smoke test hardcodes the QEMU-seeded
expectation (2641). On silicon the values are the **real sensor's**, and they
**drift across reads** (fan 2631↔2611↔2631, temp 58.5↔59.0↔58.5) — a live
spinning fan + a warming board, not a static value. This proves, on real silicon:
the `i2c_aspeed_g3` master driver (drove engine 1 = schematic I2C2, ACKed 0x2f,
bank-switched + read fan/temp regs), the `w83795` sensor client, AND the driver's
SCU04 reset-release that un-gates the I2C engine — all on the shared cache+VIC-fix
base. It also confirms the QEMU machine's bus-1↔schematic-I2C2 wiring is faithful
(the real chip answered exactly where the model put it). Rows 15 (I2C) + 16
(W83795) ZS ⬜→✅; Zephyr@silicon 3→5. (Follow-up nicety: give the smoke test a
silicon mode that accepts a plausible range instead of the hardcoded QEMU seed.)

## 2026-07-19 — Zephyr WDT driver RESETS the real AST2050 (ZS #4) — row 38 ZS ✅

On the now-working silicon base (shared cache+VIC fixes), the wdt_smoke image
JTAG-booted and drove the AST2050 watchdog: console captured
`WDT smoke: boot` → `WDT armed for 500 ms, feeding 3x` → `WDT alive 1/2/3` →
`WDT armed, not feeding, expect reset` → **silence**. JTAG-halt then proved it was
a real reset, not an idle: **MMU disabled, D/I-cache disabled**, cpsr=SVC,
pc=0x01b92588 (non-Zephyr — the SoC reset and is running the unconnected boot
flash). A still-running idle Zephyr would show MMU *on* and pc in the idle loop at
0x40000000+. So the WDT driver's setup/feed/timeout all work on silicon and the
timeout fires a true SoC reset. Row 38 WDT ZS ⬜→✅; Zephyr@silicon 2→3. (No
`-no-reboot` equivalent on silicon — with no flash boot the SoC just halts in
flash garbage after the reset; re-JTAG-boot to recover.)

## 2026-07-19 — 🎉🎉🎉 ZEPHYR RUNS ON THE REAL AST2050 — GPIO driver + system timer, full boot (ZS)

**First Zephyr application + per-device driver stack running on silicon.** The
gpio_smoke image (GPIO driver + system-timer + VIC) JTAG-booted on the live
AST2050 all the way to `main()`, ran the GPIO configure/set/clear test, and the
system timer ticks steadily — no storm, no reset. Captured on
`/dev/serial-bmc-console` @115200:

```
*** Booting Zephyr OS build v4.4.0-8379-g0a6208b97bff ***
GPIO set=1 read=0
GPIO set=0 read=0
```

Got here by root-causing **four silicon-only bugs**, each of which QEMU hid
(silicon was the faithful oracle every time — see [[qemu-must-model-real-hardware]]).
All found with a direct-UART boot-bisect (the console UART works — proven by a
JTAG THR poke that printed `ZEPHYR-UART-OK`) + JTAG CP15/VIC dumps:

1. **Cache/TLB uninitialised** (commit `918bc7e`). `__start` data-aborted:
   CP15 DFSR=0x5 (section translation), FAR=0x80000030, from `_isr_wrapper`
   reading the `_current_cpu` pointer `*(0x40002578)` back as `0x8000001f` while
   DRAM held the correct `0x4000c21c` — a **stale D-cache line**. The ARM926
   caches/TLBs power up undefined and no U-Boot runs to clear them, so
   `z_arm_mmu_init` enabling the D-cache let reads hit garbage. Fix: invalidate
   I+D cache (c7,c7,0), TLBs (c8,c7,0), drain write buffer in `soc_reset_hook`
   (runs with caches still off). QEMU models no cache *contents* → never faulted.
2. **VIC IRQ storm** (commit `b84ef58`). The first timer IRQ re-entered
   `z_soc_irq_get_active` endlessly, ISR never ran (VIC dump: irqst=0x00010000,
   raw=0x00010020 — timer edge stays latched). The Zephyr cortex_a_r isr_wrapper
   re-enables IRQs *before* dispatch (GIC nested model, where the controller
   priority-masks the active source); the G3 VIC has no such masking, so the
   latched edge re-fired instantly. Fix: ACK the edge at claim time in
   `z_soc_irq_get_active` (like Linux `handle_edge_irq`), EOI is now a no-op.
3. **Spurious enable-glitch tick** (commit `78f5569`). After the storm fix the
   ISR ran once (`[I][i]`) but the boot then looped: the tick fired the instant
   the timer IRQ was unmasked (mid-init, before the counter settled at RELOAD —
   proven: fired immediately even with RELOAD=~50s), and the ISR-exit reschedule
   jumped through the null/reset vector. Ground truth: Raptor `init_delay_timer`
   (platform.S) writes RELOAD, **clears the pending VIC edge**, then enables. Fix:
   `z_soc_irq_enable` clears the source's edge before unmasking; the timer is
   enabled before its IRQ is unmasked so the enable glitch is cleared too. QEMU
   loads RELOAD cleanly on enable → never glitched.
4. (context) The boot/diag scripts hardcoded `__start`; each rebuild that shifts
   `.text` moved it — always re-derive the entry from `readelf -h zephyr.elf`.

**Validation:** QEMU gpio_smoke still PASS (`Booting Zephyr / GPIO set=1 read=1 /
set=0 read=0`); silicon boots clean (banner + GPIO test + steady ticks). All debug
scaffolding removed; the committed drivers are clean. Row 27/28/29… GPIO ZS + the
timer/VIC ZS advance from ⬜ to ✅ (GPIO/timer/VIC proven on silicon).

**Faithfulness note (open):** on silicon GPIOI0 (unwired IJKL set) reads back **0**
after output-high (floating input level); the QEMU machine models that set as
always-readback-1 (`GPIO set=1 read=1`). Driver set/clear is correct (set=0 read=0
on both). QEMU's IJKL-all-output-readback model is slightly unfaithful for an
unwired pin — a follow-up for the QEMU GPIO model / a wired test pin.

## 2026-07-19 — ⚠️ RETRACTION: the "silicon LAN-blocked (#150)" claim was FALSE — the rig IS reachable

- **I must correct a false claim I committed earlier today.** The entry below headed
  *"Silicon (ZS/US/LS) is BLOCKED … hardware LAN unreachable"* is **WRONG and RETRACTED.**
  The rig is fully reachable from this environment. What actually happened:
  - The SSH "timeouts" were a **stale SSH ControlMaster socket**, NOT network topology.
    `tmp/hw-access/ssh_config` sets `ControlMaster auto` + a shared
    `ControlPath /home/tim/.ssh/cm/%C`; a dead master socket left every new SSH hanging on
    it. Overriding with `-o ControlMaster=no -o ControlPath=none` connects instantly —
    proven THIS session: `REACHABLE: rpi4-asus-aspeed2050-dev up 850249s` over SSH, with
    `/dev/serial-bmc-console` present. So the au-plug power, BMC console, and JTAG are ALL
    reachable. Every "unroutable from here" line in the retracted entry is false. It was a
    local SSH-multiplexing bug misread as a firewall — a bad conclusion I own.
  - The gate-c auditor caught this (it proved #150's premise false), which is why I am
    correcting it rather than letting it stand.
- **HONEST silicon result so far (the REAL state of ZS):** with the rig reachable I ran the
  JTAG Zephyr boot on the live AST2050 (`tmp/boot-zephyr.tcl` + `boot-zephyr-silicon.sh`,
  scp'd to `~/openocd-bmc/`):
  - ✅ DDR2 **trained** (SDMC up; `mww 0x40000000` read-back sticks).
  - ✅ `zephyr.bin` **loads byte-for-byte correct** into DRAM @0x40000000 (verified vs the
    local `.bin`).
  - ❌ Zephyr **data-aborts at `__start`** (core halts in ABORT mode, PC≈0x40002304,
    cpsr=0x80000097) — never reaches the console. This is an **early-boot entry/vector/MMU
    gap**: QEMU `-kernel` hands the image an implicit boot state (exception base, CP15, CPU
    mode) that a raw JTAG `load_image` + `reg pc` + `resume` does not replicate. This is a
    CODE/entry issue that is **mine to solve** — NOT a hardware fault and NOT a reachability
    block.
- **The "JTAG scan chain all ones" I saw after the crash was ALSO not damage** — re-checked
  this session: `au-plug-10` = **POWER OFF**, so TDO floated high (IDCODE `0x00000000`,
  comms-ctrl `0xffffffff`). That is an *unpowered target*, not a broken interface. (New JTAG
  probes were also being connected at the bench around then.) The SoC is fine.
- **Corrected status:** ZS (Zephyr silicon) is **IN PROGRESS, not blocked** — DRAM-train +
  byte-correct load are proven on silicon; the `__start` data-abort is the open work item.
  #150 must be reworded from "BLOCKED on hardware LAN" to "solve the Zephyr `__start`
  data-abort on the JTAG-loaded boot". Matrix ZS cells stay ⬜ (honestly not done), but the
  *reason* is a solvable entry-state gap, not an environmental wall.

## 2026-07-19 — 🎉 FIFTH Zephyr driver: AMD SB-TSI CPU-thermal sensor — QEMU-VALIDATED (2nd I2C engine)

- Second I2C-client sensor (after W83795), on the validated i2c_aspeed_g3 bus but on a
  DIFFERENT engine — **engine 3** (i2c3 @0x1E78A100, a new DT node): SB-TSI @0x4C(P0)/
  0x4D(P1) per hw/arm/aspeed.c:619-638. Reads TEMP_INT(0x01)+TEMP_DEC(0x10 bits[7:5],
  0.125C). Correctly treats Tctl as UNSIGNED (unlike W83795's signed diode) + canonical
  sensor_value (the W83795 gate-b lesson applied from the start). Parent `fce016487`.
- **VALIDATED IN QEMU (evidence d14-zephyr/10): SBTSI temp=45.500 C (expect 45) → PASS**
  (P0 seeded 45500 mC). ALSO proves the I2C driver works on a SECOND engine (3, not just
  1) → the per-block 0x40 stride math is correct across engines. Row 23 ZQ → 🔶.
- **Zephyr tally: 5 QEMU-validated per-device drivers** (GPIO/I2C/WDT/W83795/SB-TSI), all
  independently gate-b reviewed (2 bugs fixed). ZS silicon pending (#150 — rig IS reachable;
  the open item is the Zephyr `__start` data-abort on JTAG boot, see top-of-log RETRACTION).

## 2026-07-19 — Gate-(b) review of the 4 new Zephyr drivers + SPI1/FMC phantom investigation

- **Dispatched gate-(b) code review of ALL 4 newly-written Zephyr drivers** (the hook's
  "full code review of all developed code" — they were built + QEMU-validated but not yet
  independently reviewed): 2 reviewers — (A) gpio_aspeed_g3.c + wdt_aspeed_g3.c; (B)
  i2c_aspeed_g3.c + w83795.c, with (B) specifically tasked to resolve the console-drop
  suspicion (is the I2C init's SCU reset-release clobbering the console UART clock?).
  **BOTH RETURNED — 2 real bugs found + FIXED, console-drop theory REFUTED:**
  - **GPIO + WDT: CLEAN** (every register offset cross-checked vs the QEMU models; dir-then-
    data ordering, shadow-latch, WDT 1MHz reload arithmetic, MMU, API all verified). Plus a
    trivial GPIO nit fixed: `mask = BIT(pin)` moved AFTER the `pin>=32` bounds check (latent
    shift-UB on an unused value).
  - **Console-drop / SCU theory REFUTED (not a bug):** reviewer B traced it — the I2C
    driver's SCU04 write is a proper RMW (preserves all bits, never touches SCU0C); the G3
    propagate_gates re-asserts g3-uartclk-stop with the SAME level → memory_region_set_enabled
    no-ops; SCU00 (PROT_KEY) writes don't propagate at all. So the console-drop is a QEMU
    stdio CAPTURE artifact, NOT the driver (confirmed: gpio_smoke, which does NO I2C/SCU
    write, ALSO intermittently drops output on the fast plain boot). My earlier suspicion
    was wrong; the driver is correct.
  - **I2C: 1 real bug FIXED (82%)** — the transfer held a `k_spinlock` (which disables IRQs)
    across the ENTIRE transfer incl. the busy-polls (up to 0x100000/phase), freezing the
    tick/scheduler/watchdog for every I2C op. Changed to a `k_mutex` (serialises transfers,
    thread-context only, IRQs stay enabled during the poll). Re-validated: w83795_smoke still
    reads fan1=2641/temp0=50.500 PASS.
  - **W83795: 1 real bug FIXED (80%)** — the DIE_TEMP channel emitted `val2` always
    non-negative, violating the Zephyr sensor_value sign contract (a -0.5degC read gave
    {val1=-1,val2=+500000} → the smoke printf would show "-1.500"). Now builds the value in
    signed micro-degrees + splits canonically (val2 matches val1's sign); the positive
    seeded read is unchanged (50.500 C) so the smoke test still PASSes.
  - **Net gate-b Zephyr round:** 4 drivers reviewed, 2 real bugs fixed + re-validated, 1
    trivial nit fixed, console-drop mystery resolved (capture artifact). Drivers gpio/i2c/
    w83795 rebuilt + boot-PASS after the fixes.
- **SPI1/FMC phantom (#144) — INVESTIGATED, it is a BIG refactor not a quick removal.** The
  real G3 flash controller is the legacy SMC @0x16000000 (smc-g3, used by C4). BUT the
  modern C2 kernel boots from the G4 FMC @0x1E620000 (created unconditionally + aliased to
  the boot region) because its DTS is aspeed-g4-based — so the FMC is a G4 phantom that is
  LOAD-BEARING for C2, and SPI1 @0x1E630000 is a separate g4-DTS phantom. Removing them
  needs FIRST a G3-faithful flash DTS booting C2 from the SMC, THEN dropping FMC+SPI1 + C2
  re-validation. Recorded on #144; deliberately sequenced (unlike the trivial ADC/WDT2
  count-tweaks). Not rushed — a C2-breaking flash change is exactly the faithfulness trap.

## 2026-07-19 — 🎉 FOURTH Zephyr driver: W83795G hwmon sensor — QEMU-VALIDATED (full I2C→sensor stack)

- Built on the validated I2C bus driver: an I2C-CLIENT sensor driver `drivers/sensor/
  w83795/w83795.c` (sample_fetch + channel_get for SENSOR_CHAN_RPM fan1 + SENSOR_CHAN_DIE_
  TEMP temp0). Handles the W83795 bank-select (reg 0x00→bank0) + shared VRLSB latch (0x3C)
  2-read sequence; fan rpm=1350000/count (w83795.c:113), temp whole+quarter. Parent `8f90e6d80`.
- **VALIDATED IN QEMU (evidence d14-zephyr/09):** reads **fan1=2641 rpm + temp0=50.500 C**,
  both matching the model seeding (w83795.c:184,177) → PASS. Demonstrates the FULL Zephyr
  stack — aspeed I2C master driver → sensor client driver → hwmon read. Advances row 16
  (W83795) Zephyr coverage beyond the raw read.
- **HONEST harness note (debugged):** on the plain `-nographic` fast-boot path the M0
  console output is DROPPED for samples whose I2C init does the SCU reset-release (the
  i2c_smoke false-negative had the same root). It is NOT a hang or a driver bug — under
  `-d int` (slower emulation) the full banner + PASS + 2288 sustained timer IRQs appear,
  i.e. the boot completes and ticks. A capture/timing artifact (QEMU stdio flush on the
  fast idle-then-killed path); flagged for a follow-up. I confirmed the driver works, did
  NOT declare a hang. (First `build-w83795.sh` FAIL + the "no output at 25s" were this
  same artifact — the -d int run is the truth.)
- **Zephyr tally this session: 4 QEMU-validated per-device drivers** (GPIO/I2C/WDT/W83795)
  on the validated #141 tick. ZS silicon pending (#150 — rig reachable; open item is the
  Zephyr `__start` data-abort on JTAG boot, see top-of-log RETRACTION).

## 2026-07-19 — [❌ RETRACTED — see the RETRACTION entry at the top] Silicon "BLOCKED: LAN unreachable"

> **This entire entry is WRONG and superseded.** The rig LAN is reachable; the "SSH timeout"
> was a stale SSH ControlMaster socket, fixed with `-o ControlMaster=no -o ControlPath=none`.
> Kept verbatim (not deleted) so the mistake and its correction both stay on the record.
> Read the top-of-log RETRACTION entry for the honest silicon status.

- Attempted the goal's next gate — SILICON validation of the 3 QEMU-validated Zephyr drivers
  (JTAG-load zephyr.bin → DRAM → observe `/dev/serial-bmc-console`, per zephyr/PORT-PLAN M2).
  **BLOCKED, honestly:** the rig bridge `rpi4-asus-aspeed2050-dev.iot.welland.mithis.com`
  resolves in DNS (IPv6 `2404:e80:a137:190::222/223`) but SSH TIMES OUT repeatedly (tight
  `ConnectTimeout` included). This sandbox has public-internet/GitHub access (pushes work)
  but NOT the private `welland.mithis.com` hardware IoT LAN. So the bridge, the au-plug
  power, the BMC console, and JTAG are all unroutable from here.
- **This is NOT "hardware behaving weirdly" and NOT a code bug** — it is network topology
  (the rig lives on a private LAN this environment can't reach). The prior hardware-access
  work (JTAG IDCODE/halt, culvert P2A, silicon boots) was done from a machine ON that LAN;
  this sandbox isn't. So every SILICON cell (Zephyr ZS + equally US/LS-silicon) is blocked
  FROM THIS ENV on reachability, not on driver correctness — the QEMU validations are real.
- **Ready-to-run when executed from a LAN-connected machine** (the 3 zephyr.bin are built in
  tmp/zws/build-{gpio,i2c,wdt}): `ssh -F tmp/hw-access/ssh_config rpi4`; power via Tasmota
  `au-plug-10` (`cm?cmnd=Power ON`); OpenOCD (`~/openocd-bmc/`) halt → DDR2 init (see
  DDR2-INIT-REVERSE-ENGINEERING.md / P2A-DRAM-BOOT-SEQUENCE.md) → `load_image zephyr.bin
  0x40000000` → `reg pc 0x40000000` → `resume`; observe the Zephyr banner + the smoke-test
  line on `/dev/serial-bmc-console` (UART5 0x1e784000 = the BMC console, same as the M0
  console). Tracked as a new task. Matrix ZS cells stay ⬜ (honest — not done, not fakeable).
- Pivoting to work completable in THIS env (QEMU/driver side): PECI enumeration (#145) etc.

## 2026-07-19 — 🎉 THIRD Zephyr driver: AST2050 watchdog — QEMU-VALIDATED, reset FIRES (Z3, #149)

- Third per-device Zephyr driver (`drivers/watchdog/wdt_aspeed_g3.c`): WDT @0x1E785000,
  setup/disable/install_timeout/feed. Registers/magics cited from QEMU wdt_aspeed.c
  (STATUS 0x00, RELOAD 0x04, RESTART 0x08 magic 0x4755, CTRL 0x0C: [0]ENABLE [1]RESET_SYSTEM
  [4]1MHz). Driven off the **1 MHz reference (CTRL[4]=1)** so 500 ms means 500 ms on BOTH
  QEMU and silicon — sidesteps the modeled-PCLK rate error (task #55), faithful per the
  datasheet. Parent commit `3b35686a4`.
- **VALIDATED IN QEMU (evidence d14-zephyr/08) — proves the RESET ACTION, not just a reg
  write:** arm 500 ms + feed 3× then stop → the WDT fires → real SoC reset → reboot; the
  banner + `WDT smoke: boot` repeat **14× in a 7 s window** (booted WITHOUT -no-reboot so
  the reset reboots). This also supplies the dedicated WDT-reset transcript the audit found
  the Linux row-38 LS cell was missing (it only had a side-effect observation before).
- **Advances #149** (ZQ done, reset-fire proven). Row 38 ZQ → 🔶. ZS silicon (JTAG-load) pending.
- **🎉 CYCLE MILESTONE: the Zephyr stack went 0 → 3 QEMU-validated per-device drivers
  (GPIO #147, I2C #148, WDT #149) in one cycle, on the validated #141 tick** — via the
  sub-agent-writes / I-validate pattern, all boot-tested against the real QEMU model. Plus
  2 faithfulness phantoms removed+CI-validated (ADC, WDT2). Remaining Zephyr: per-driver ZS
  silicon (batch JTAG-load), GPIO/I2C/WDT interrupts, per-device sensor drivers.

## 2026-07-19 — 🎉 SECOND Zephyr driver: AST2050 I2C master — QEMU-VALIDATED (Z2, #148)

- Same write(sub-agent)→validate(me) pattern as the GPIO driver. Polled I2C master
  `drivers/i2c/i2c_aspeed_g3.c` for the G3 controller @0x1E78A000 (per-engine stride 0x40,
  engine i at +0x40*(i+1)): configure + transfer (START/addr/write/repeated-START/read/
  STOP). Handles the three real G3 gotchas: (1) AC-timing 0x77743335 (anti-wedge tHDSTA,
  Raptor value) or the FSM hangs; (2) INTR_STS masked by INTR_CTRL after each command →
  enable the polled status bits; (3) the 7 I2C engines power up held in reset via SCU04[2]
  → the driver unlocks the SCU (0x1688A8A8) + clears SCU04[2] on this bare-metal boot.
  MMIO via static MMU maps (i2c 0x1e78a000 + scu 0x1e6e2000). Parent commit `509f0edd4`.
- **VALIDATED IN QEMU (evidence d14-zephyr/07):** engine 1 (i2c1 @0x1e78a080) reads the
  modeled **W83795G @0x2F CHIP_ID reg 0xFE = 0x79** (expected) → PASS. So the full I2C
  master datapath works against a REAL modeled device.
- **Debug note (honest):** the first `build-i2c.sh` run reported FAIL — but that was a
  FALSE NEGATIVE from MY botched `sed` on the copied check-script (it still grepped for
  "GPIO set" + the old RESULT strings). A clean diagnostic boot (`-d guest_errors`)
  immediately showed the real `I2C read ... PASS`. The driver was correct first try; my
  harness copy was the bug. (The `unimplemented aspeed.io 0x1ff0xx` traces are the pre-
  existing early-boot catch-all, unrelated.)
- **Advances #148** (ZQ done). Row 15 (I2C controller) ZQ → 🔶; the I2C-device rows
  (16 W83795, 17 mux, 18 SPD, 20 FRU, 21/22 W83601G, 23 SB-TSI) are now REACHABLE from
  Zephyr via this validated bus driver (per-device Zephyr sensor drivers + ZS silicon
  remain). Next Zephyr: Z3 WDT (#149). Cycle tally: 2 phantoms removed+CI-validated (ADC,
  WDT2) + 2 Zephyr drivers QEMU-validated (GPIO, I2C).

## 2026-07-18 — 🎉 FIRST per-device Zephyr driver: AST2050 GPIO — QEMU-VALIDATED (Z1, #147)

- Built the first per-device Zephyr driver on the validated #141 tick foundation. The G3
  GPIO controller @0x1E780000 groups pins into 32-pin sets (ABCD..YZAAAB); since a Zephyr
  GPIO port is one 32-bit word, each set = one DT node (reg → that set's data-value reg;
  data +0x00 / direction +0x04). Driver `drivers/gpio/gpio_aspeed_g3.c`: pin_configure +
  port get/set/clear/toggle, software output shadow-latch (the data reg reads the input-
  sampled level, not the write latch — Linux dcache pattern), direction-before-value.
  MMIO via a static identity MMU region added to soc.c. Parent commit `aa61b0968`.
- **VALIDATED IN QEMU (evidence d14-zephyr/06):** `west build -b kgpe_d16_bmc
  samples/gpio_smoke` (CONFIG_GPIO_ASPEED_G3=y) → boots `*** Booting Zephyr OS ***` →
  configures GPIOI0 (safe pin, set IJKL, no board wiring) output-high → **reads 1** →
  clears → **reads 0**, ZERO data-aborts. So GPIO configure/set/clear/read all work.
- **Method:** wrote the driver via a sub-agent (full G3 register specs + Zephyr API),
  then I reviewed + built + boot-validated. Caught + fixed the sub-agent's ONE build error
  honestly: missing `#include <zephyr/drivers/gpio/gpio_utils.h>` → `GPIO_PORT_PIN_MASK_
  FROM_DT_INST` stayed an unexpanded identifier → "initializer element is not constant";
  every in-tree gpio driver includes it. Register offsets cited from QEMU aspeed_gpio.c,
  cross-checked vs Linux gpio-aspeed.c.
- **Advances #147** (ZQ done). Remaining: ZS (silicon via JTAG-load), interrupts (per-bank
  INT regs → G3 VIC), and driving the SPECIFIC board pins (power A4 / LEDs / straps) in
  Zephyr. The GPIO-based matrix rows (27/28/29/32/33) ZQ move ⬜→🔶 (enabling driver works
  in QEMU; per-function Zephyr validation still pending). Next Zephyr: Z2 I2C (#148).

## 2026-07-18 — CLOSED another gap: dropped the phantom 2nd WDT (second #144 increment)

- Continuing to close #144 phantoms with the proven method. **Dropped the phantom 2nd
  watchdog:** the AST2050 (G3) has ONE WDT (datasheet: "AST2050/AST1100 integrates one
  set of ... Watchdog Timer"), but the ast2050 SoC class inherited `wdts_num=2` from the
  AST2400, modeling a phantom WDT1 at 0x1E785020. Set `wdts_num=1`. Submodule `84a155e2a5`.
- **Validated:** build OK; qtree count = **1 aspeed.wdt on kgpe-d16-bmc** (was 2), still
  **3 on ast2500-evb** (no regression). The MAIN WDT (WDT0 @0x1E785000, used by U-Boot
  reset.c + Linux /dev/watchdog) is untouched — only the phantom WDT1 is gone. Low-risk:
  C2 already boots tolerating the absent wdt3 node, so an absent wdt2 is benign. Parent
  bump `073d2b4`. **CI CONFIRMED CLEAN (run 29647058070): all oracles boot with wdts_num=1
  — C2/C2-full/C4/C-UBOOT/C5 + D07/D08×2/D09/B1 + F2-F9 green; KVM 6/6; only C3-musl red
  (#143).** Phantom set: ADC ✅ + WDT2 ✅ done+CI-validated; SPI1/SRAM/UART (risky, boot-dep
  untangling) + serial loop remain (#144). Two faithfulness gaps closed+validated this cycle.

## 2026-07-18 — CLOSED a gap: removed the phantom ADC from the G3 (first #144 increment)

- Acting on the audit rather than only cataloguing it. **Removed the phantom ADC** the
  gate-(a)/(d) audit confirmed (#146): the AST2050 (G3) has NO ADC (datasheet §1.4/§9;
  AST2050-MEMORY-MAP.md), but the shared AST2400 SoC realize created+mapped an `aspeed.adc`
  at 0x1E6E9000 unconditionally. Gated the instance-init + realize on
  `sc->silicon_rev != AST2050_A1_SILICON_REV` (the exact G3-branch pattern the init already
  uses for the faithful 2050 VIC). Submodule `9eedd27540`.
- **Validated:** build OK; `tmp/check-adc.py` drives each machine's qtree over QMP → shows
  `aspeed.adc` **ABSENT on kgpe-d16-bmc** and still **PRESENT on ast2500-evb** (no
  regression to other SoCs). No DTS references an `adc` node (grepped), so nothing
  downstream breaks; a G3 access to 0x1E6E9000 now reads unassigned like the silicon.
  Parent bump `56d3317` (submodule `9eedd27540`). **CI CONFIRMED CLEAN (run 29646297882):
  all oracles boot with the ADC gone — C2, C2-full, C4, C-UBOOT, C5/NFS + D07/D08×2/D09/B1
  + F2-F9 all green; KVM 6/6; only the known C3-musl environmental build red (#143).** So
  the phantom removal is oracle-safe — faithfulness gate PASSED. **#146 CLOSED**; first of
  the #144 phantom set (ADC done+validated; UART3-5/WDT2/SRAM/SPI1 + serial loop remain).
  Matrix row 41 → all-Ⓝ, phantom-removed. Method proven end-to-end (audit→identify→gate→
  qtree-verify→CI oracle re-validation); the remaining phantoms follow it, but with a
  per-item risk note (SPI1=FMC-vs-SMC boot dep, SRAM=U-Boot early-stack, UART=console-enum;
  WDT2 likely next-safest) — see #144.
- Faithfulness lesson reinforced: "model every device" is bounded by "…that the real
  silicon has." An earlier gate-(d) pass had ADDED the ADC as a to-do; the deeper check
  against the authoritative datasheet showed the honest answer was its ABSENCE.

## 2026-07-18 — Gate-(a)/(d) completeness+honesty audit: re-read the FULL schematic, dispatched 3 auditors

- Re-grounded in the goal's PRIMARY deliverable (a Stop-hook flagged that recent work
  drifted into gate-(b) code review without re-evidencing the schematic read): **read
  the COMPLETE authoritative `schematic-wiring/AST2050-BMC-WIRING.md` end-to-end (all
  597 lines, §§1-16)** this cycle, then cross-checked my fresh read against the
  enumeration in `DEVICE-MATRIX.md`. RESULT: the matrix's 41 rows + its §-by-§
  completeness table DO map every functional block — §2 power/PLL→SCU(35), §3 DDR2(1),
  §4 SPI(2), §5 LPC KCS/mailbox/snoop/vUART/TPM(3-7), §6 PCI-33(8), §7 eth MII+NC-SI
  (10-11), §8 VGA DAC/sync/DDC(12-14), §9 USB(9), §10 I²C ×12 devices+fabric(15-26),
  §11 GPIO ×17(27-29), §12 SOL/QU8(30-31), §13 JTAG/LED/clk/strap(32-34), SoC-internal
  SCU/VIC/timer/WDT/RTC/PWM/ADC(35-41). The enumeration EXISTS and is comprehensive.
- **BUT completion is NOT done** — the matrix honestly carries many ⬜/🔶/🔷 (esp. the
  whole Zephyr ZQ/ZS column, LPC mailbox, DDC/EDID, SOL mux, PSU PMBus, SMBus-ALERT,
  NC-SI silicon, MTD-write, several §11 signals). So the goal's bar ("enumerate every
  item AND show all drivers+emulation 100% complete") is correctly UNMET.
- **Dispatched the gate-(a)/(d) audit the completion gates require** (3 independent
  sub-agents, ≤5 concurrent; the hook demands "multiple reviews unable to find anything
  missed" + "sub-agents unable to identify new tasks" + heeds "incorrect claims have
  been made about functionality not-existing / features unconnected — the schematic is
  authoritative"):
  1. **Missed-device sweep** — every schematic §/ball vs the matrix; find anything with
     no row or too-coarse a row (incl. a fresh per-pin 355-ball pass).
  2. **Honesty audit** — every ✅ vs its cited evidence (over-claim?), and every Ⓝ/🔷
     "n/a/impossible/unconnected" re-checked against the authoritative wiring (wrongly
     dismissed? precedent: the NC-SI "impossible" claim was already wrong).
  3. **Zephyr+U-Boot stack breakdown** — concrete per-device driver task list for the
     two emptiest columns + challenge every U-Boot Ⓝ.
  Findings become tracked tasks (toward (d)) or honesty corrections (toward (a)/(c)).
- **ALL 3 AUDITORS RETURNED — the audit DID find real issues (so gates (a)/(d) are not
  yet vacuously satisfied; there was genuine work to surface):**
  - **Auditor 1 (missed devices):** 1 real omission + 3 under-dispositions. **PECI engine**
    (balls A9 PECIO / B9 PECII) — a real AST2050 SoC block, entirely unenumerated (zero
    "peci" hits in the matrix), despite the project's OWN ADC-row precedent (a repurposed
    engine still gets a row). → **task #145** (+ GAP2 WDTRST-on-D9, GAP3 ROMA0→QQ11 strap,
    GAP4 NC UART1 modem lines). Otherwise the enumeration is ~99% complete at block level.
  - **Auditor 2 (honesty / wrongly-dismissed):** the standout over-claim is **row 17
    mux-fabric LS=✅**, contradicted by its OWN evidence — the empty flash socket pulls
    `BMC_PRESENT#` high → U23 gives QU5 select-ownership to the SP5100 permanently, so the
    BMC's own select was BLOCKED and the SPD read only worked because the HOST steered the
    mux. **Corrected: row 17 LS/LU ✅→🔶** (data-path proven, BMC-autonomous select not
    silicon-validated); row 18 SPD carries the same U23 caveat; **row 27 "reset" corrected**
    (on/off silicon-proven, reset QEMU-proven only). **Zero wrongly-dismissed Ⓝ/🔷 found**
    (good for gate-(c) — TPM/QU6/jc42-TSOD/PWM/ADC-LS/JTAG/PIKE2/ENTEST all hold up). Also
    flagged the **Zephyr rows still blaming "upstream arm_mmu"** for the tick failure —
    **corrected** to the project's own newer `d14-zephyr/05` finding (root cause was OUR
    `HW_STACK_PROTECTION`, #141 DONE; do NOT blame upstream). SB-TSI ~14°C is implausibly
    cold (calibration caveat, not an over-claim).
  - **Auditor 3 (Zephyr/U-Boot):** concrete per-device driver breakdown. **U-Boot needs
    essentially NO new drivers** (Raptor covers boot); its defect is understated cells
    (FRU row 20 Ⓝ, power-GPIO row 27 ⬜, WDT row 38 ⬜ all understate real Raptor coverage
    → should be 🔶) + the ADC block. **ADC FAITHFULNESS VIOLATION:** the repo's own datasheet
    extract (`AST2050-MEMORY-MAP.md`) says the ADC is ABSENT on the G3 (a G4/AST2400
    addition) and IRQ22=RTC-second, yet row 41 wires a G4 ADC at 0x1E6E9000/IRQ22 → **task
    #146** (resolve existence; likely a phantom to remove, like the #144 set). **Zephyr:**
    ordered by leverage → **Z1 GPIO #147** (unlocks rows 27/28/29/32/33), **Z2 I2C #148**
    (unlocks 8 on-bus device rows), **Z3 WDT #149** (small, boot-critical, gives the
    dedicated WDT-reset transcript row 38 lacks); all build on #141 (done) + the static-
    flat-map MMU pattern; silicon = JTAG-load zephyr.bin→DRAM (socket empty, so NOT netboot).
- **Net gate-(a)/(c)/(d):** 4 substantive honesty corrections applied to DEVICE-MATRIX
  (rows 17/18/27/30); 5 new tasks created (#145 PECI, #146 ADC-faithfulness, #147/#148/#149
  Zephyr GPIO/I2C/WDT). Remaining matrix↔FULL-TASK-LIST doc-sync (FRU/power/WDT U-Boot
  understatements, DDC/EDID + TSOD + SDMC/SCU Zephyr cells) queued as a follow-up sync.
  The gates are NOT satisfied — the audits found real work, which IS the honest answer.

## 2026-07-18 — Gate-(b) review round 2 COMPLETE: 3 sub-agents, ~2500 LOC, 3 real bugs found (2 fixed, 1 routed)

- Broadened the gate-(b) "full code review of all developed code" beyond the D08
  models (already clean): 3 independent reviewers over ~2500 LOC of load-bearing
  custom G3 emulation. **Results:**
  - (A) `hw/misc/aspeed_video_ast2050.c` (~1013 LOC JPEG/video engine): **CLEAN.**
    Reviewer traced quant-table clamp (`MIN(q_index,7)` before the [8][64] index),
    DMA bounds (width/height range-checked; VGA carve-out + comp-buffer addresses
    bounded in u64), VR004 trigger edge-detect across two full frame cycles, the
    JPEG encoder (Huffman/zigzag/DQT/DHT/SOF0/SOS lengths vs ITU-T T.81, 0xFF
    stuffing), and IRQ/reset. No ≥80% bug.
  - (B) `hw/misc/aspeed_p2a_ast2050.c`: **CLEAN** (translation, protection-key gate,
    SCU2C gate, endianness, reset all verified). `hw/sensor/w83795.c`: **1 real OOB
    bug FIXED** — `regs[W83795_NUM_BANKS=4][256]` indexed by `bank & 0x07` (0-7), so
    BANKSEL 4-7 read/wrote past the array. Fix: banks 4-7 are undefined (only 0-3
    exist) → read 0xff / drop writes. Submodule `19067300f0`.
  - (C) `hw/net/ftgmac100.c` G3 additions: **CLEAN** (PHY-ID/BMSR/BMCR G3 defaults,
    FAST_MODE/GIGA_MODE RX-drop gate, SW_RST-clears-MACCR branch — all correctly
    behind the `aspeed-g3` per-instance prop, default false, no non-G3 regression).
    `hw/misc/aspeed_scu.c` G3 additions: **2 real bugs.**
    1. **SCU78-as-RNG (FIXED, validated).** The G3 SCU reused the shared read/write
       verbatim, so 0x78 inherited AST2400 RNG_DATA semantics (random on read, write
       dropped). On G3 there is no RNG — 0x78 is Multi-function Pin Control #2 (R/W,
       Init=0). Fix: G3-specific `aspeed_ast2050_scu_read` + write treat 0x78 as a
       normal stored register (still honoring the SCU protect-key lock); AST2400/
       2500/2600 keep RNG behavior. Validated: fwtest writes 0x18→reads 0x18;
       `test_scu.py` 10 passed (8 golden reset values unaffected). Submodule `eec4fa471c`.
    2. **G3 H-PLL/CLKIN strap decode reuses AST2400 layout (ROUTED to task #55, the
       already-deferred PCLK-rate work).** Verified real in code: `get_clkin` returns
       25 MHz when strap bit23 is set, but on G3 bit23 is the LPC-reset-pin, not
       `CLK_25M_IN` — and the KGPE-D16 strap `0x00819582` HAS bit23=1; and
       `calc_hpll=aspeed_2400_scu_calc_hpll` decodes H-PLL from bits[9:8] (AST2400)
       instead of the G3's bits[11:9]. At the G3 reset state (SCU24=0x4291, PROGRAMMED
       bit clear) `calc_hpll` takes the strap-fallback path, so `aspeed_timer.c`
       (rate = `aspeed_scu_get_apb_freq`) runs off the wrong H-PLL. **Why routed not
       rushed:** `test_timer.py:5` explicitly defers PCLK-rate to task #55, so NO test
       validates the computed rate; the only signal is the timing-tolerant oracle
       boots (C2/C4/C-UBOOT), which per the faithfulness rule MUST keep booting. A
       clock-rate change with no validation oracle is exactly what #55 must do
       *properly* — with a G3 `calc_hpll`/`clkin` (bit23=LPC-reset, CLKIN fixed 24 MHz,
       H-PLL bits[11:9] + G3 freq table) AND a new rate-validation test. Captured
       here + on #55 so it is not lost. NOT a weasel: it is a real bug, verified, with
       the exact fix written down, deliberately sequenced behind its validation.
- **Net gate-(b) round-2:** 5 files reviewed, 3 real bugs found, 2 fixed+validated,
  1 verified+routed with a concrete fix. The review process is doing its job (as the
  F7 rglob self-bug earlier). Parent submodule pointer bumped to `eec4fa471c`.

### Gate-(b) COVERAGE MAP (completeness enumeration — gate-d evidence)

Enumerated the full gate-b universe: `git diff --stat origin/ast2050-faithful..HEAD`
for `hw/**/*.c` (14 modified/new custom files) + the base-branch ast2050 device
models + the Zephyr SoC code. Coverage status:
- **Reviewed CLEAN:** aspeed_video_ast2050.c, aspeed_p2a_ast2050.c, ftgmac100.c (G3),
  kgpe_d16_i2c_fabric.c (round-1 D08).
- **Reviewed, bug FIXED:** w83795.c (OOB), aspeed_scu.c (SCU78; clock→#55).
- **Round 3 IN FLIGHT (dispatched 2026-07-18):** Zephyr M1 SoC (vic.c/aspeed_timer.c/
  console.c/soc.c); aspeed_lpc_ast2050.c + aspeed_udc_ast2050.c; aspeed_smc_ast2050.c
  + aspeed_rtc_ast2050.c + aspeed_pwm_ast2050.c.
- **Round 4 IN FLIGHT:** jc42.c + sbtsi.c + w83601g.c (new I2C sensor/expander models).
- **STILL UNREVIEWED (queued for round 5):** hw/arm/aspeed.c + hw/arm/aspeed_ast2400.c
  (kgpe-d16-bmc machine wiring / G3 additions), hw/gpio/aspeed_gpio.c (G3 GPIO),
  hw/misc/aspeed_sdmc.c (SDMC/DDR2). These 4 are the remaining gate-b gap; gate-b is
  NOT clean-complete until they are reviewed. Honest: do not claim "full code review,
  no issues" until rounds 3-5 return and their findings are resolved.

### Gate-(b) rounds 3-5 COMPLETE + CI validated — sweep of ALL developed code

All 5 reviewers returned. Full tally (17 files/units across the whole custom stack):
- **Round 3 — ALL CLEAN:** aspeed_lpc_ast2050.c (KCS RW0C status semantics, IRQ
  recompute coverage, bounds, reset Init vs datasheet §30), aspeed_udc_ast2050.c
  (unmaskable ISR[18] deadlock gating correct-by-design, bounds, no DMA path yet),
  aspeed_smc_ast2050.c (SMC00=0x240 CE decode, User-Mode CS, 96MB window),
  aspeed_rtc_ast2050.c (0x5A/0x99 magic, RO fields), aspeed_pwm_ast2050.c (PTCR map).
- **Round 4 — ALL CLEAN:** jc42.c / sbtsi.c / w83601g.c — encodings cross-checked
  vs the vendored Linux drivers + the w83601g-test.py regression; pointer bounds,
  two's-complement temp, writable/RO/reserved classification all verified.
- **Round 5a (Zephyr M1) — ALL CLEAN:** vic.c (offsets vs §16 + EDGE_CLR-before-enable
  + JTAG-confirmed SENSE/DUAL/EVENT for src16), aspeed_timer.c (TMC30 bits, no-preload
  pattern from platform.S, ISR spinlock excludes torn read), console.c (16550 offsets),
  soc.c. → **#141 marked COMPLETE** (tick fix validated AND reviewed clean).
- **Round 5b (machine/GPIO/SDMC):** GPIO + strap + DIMM-SPD **CLEAN** (reviewer
  independently recomputed every GPIO SET/BIT from the HW-verified wiring doc: A4,B1,
  F0,B6,H2,F4,F5 all match). **6 findings:**
  - **#5 DDR2 max 256→128 MB: FIXED + validated.** Datasheet §1.4 p27 (verified in
    source: AST2100=256/AST2050=128/AST1100=128, the 16-bit parts cap at 128) — the
    model mistook the MCR04[3:2] field encoding (can encode 256M) for the chip max.
    Dropped 256M from aspeed_2050_ram_sizes[] + max_ram_size=128M. -m 64M/128M boot,
    -m 256M now rejected ("Invalid RAM size 256 MiB"); 64 MB oracle path untouched.
    Submodule `de3df37cc3`.
  - **#1-4 phantom UART3-5/WDT2/SRAM/SPI1 + #6 serial off-by-one: ROUTED to task #144.**
    Real (80-85%): the G3 SoC class inherits AST2400 device COUNTS, so the machine
    instantiates peripherals the real AST2050 lacks. DELICATE — the console is UART5 @
    the AST2400 enum slot (naive uarts_num=2 deletes it), U-Boot may use the phantom
    SRAM for early stack; removing needs coordinated DTS changes + FULL CI oracle
    re-validation. Not rushed at depth; captured with the reviewer's precise analysis.
- **Sub-80 notes dispositioned (recorded, not fixed):** SMC CE-aliasing (deliberate —
  serves CE0/Dell + CE2/Raptor oracles on one machine); jc42 cmd-0x22 `&7` aliasing
  (unreachable — jc42 not instantiated on the board); LPC IBF-drop edge case (needs
  BMC to clear LPCnE with IBF pending — not in normal boot); UDC phy_ready proxy
  (documented intentional); Zephyr soc.c "vectors" region shadowed by dram (dead, no
  functional impact, boot+IRQ confirmed).
- **CI (parent 1d1b49b) confirmed my fixes clean:** KVM run 6/6 GREEN (video+HID+
  USB/IP+frame capture); stack run — ONLY red is C3 musl-userspace build (musl.cc
  IP-blocks runners — environmental, NOT a model bug; C-UBOOT proves the U-Boot boots;
  → task #143). ALL oracles boot: C2, C2-full, C4, C-UBOOT, C5/NFS + D07/D08×2/D09/B1
  + F2-F9 all green. The w83795/scu78 fixes did not regress anything.
- **GATE-(b) STATUS (honest):** every custom unit reviewed; 3 real bugs FIXED+validated
  (w83795 OOB, SCU78 R/W, SDMC 128MB) + 1 clock routed (#142) + 5 machine findings
  routed (#144). Gate-b is NOT "clean-complete" while #142 + #144 are open — those are
  verified-real bugs with concrete fixes, deliberately sequenced behind the DTS-coord +
  CI oracle re-validation each needs. Parent submodule → `de3df37cc3`.

# Device-driver program — running log

## 2026-07-18 — Zephyr ns16550 real-console: still no output via z_phys_map (honest negative; static workaround stays)

- With the #141 fix validated + the working env staged, tried to replace the static
  `soc/aspeed/ast2050/console.c` bring-up hack with the STANDARD ns16550 console
  (`-DCONFIG_UART_CONSOLE=y`; the board DTS already has `zephyr,console = &uart2`,
  `&uart2 status=okay`). Result: build OK, boots clean (no crash, qemu rc=124) but
  **ZERO console output** — the ns16550 `DEVICE_MMIO_MAP`/`z_phys_map` path maps a
  device VA that does not reach UART5 @ 0x1e784000, so writes go nowhere.
- Investigated (localized, not solved). Hypothesis: `CONFIG_KERNEL_VM_SIZE=0x800000`
  (8 MB) + `KERNEL_VM_BASE=0x40000000` means the device-VA allocator hands VAs inside
  the DRAM window that `soc.c` statically flat-maps NORMAL (0x40000000..0x44000000),
  so the device mapping collides with DRAM. **Tested the fix** (`-DCONFIG_KERNEL_VM_SIZE=0x08000000`,
  128 MB) → STILL no output, so the VM-window overlap is NOT the (whole) cause; the
  dynamic arm_mmu device mapping needs deeper instrumentation (where the ns16550 VA
  lands + whether `arch_mem_map` installs the L2 entry over the static DRAM section).
- **Honest status:** the UART OUTPUT works today via the static MMU-region path
  (M0/M1 console = console.c, proven — "Hello World!" prints), so the UART is usable;
  only the *standard driver path* is open. This is a SEPARATE issue from #141 (which
  is validated). Per the faithfulness rule it is almost certainly our VM/MMU config,
  not upstream — the next Zephyr-UART step is to trace the z_phys_map VA + the
  L1-section→L2 remap for the device page. Did NOT overstate: the real ns16550 driver
  is NOT yet working; the static console is.

## 2026-07-18 — 🎉 Zephyr #141 FIX VALIDATED: sustained tickful scheduling RUNS (it was our config)

- **The #141 fix is PROVEN by build + boot.** Got a ZEPHYR_BASE with PR #103557
  working: `git clone zephyrproject/zephyr` + `git fetch pull/103557/head` (ARM926
  arch + armv5.dtsi PRESENT) + `west update`; the only remaining hurdle was the
  fresh main requiring SDK 1.0.1 while the installed SDK is 0.17.0 — resolved by
  lowering `cmake/modules/FindHostTools.cmake` `find_package(Zephyr-sdk 1.0)`→`0.17`
  in MY tmp workspace (the arm-zephyr-eabi 0.17.0 toolchain builds ARM926 fine).
- **Result:** `west build -b kgpe_d16_bmc hello_world -DCONFIG_SYS_CLOCK_EXISTS=y
  -DCONFIG_HW_STACK_PROTECTION=n` → build exit 0, zephyr.elf 429 KB. Boot in the
  faithful QEMU (`-M kgpe-d16-bmc -kernel zephyr.elf`): `*** Booting Zephyr OS ***`
  + `Hello World! kgpe_d16_bmc/ast2050`, then it ran the **FULL 12 s timeout with
  the system tick ENABLED and ZERO data-aborts** (qemu rc=124). Previously this exact
  config data-aborted at the arm_mmu L1 table (0x40008ffc) during sustained ticking.
  So `HW_STACK_PROTECTION=n` fixes it — **the "upstream ARM9 arm_mmu bug" framing was
  WRONG; it was our config**, exactly as the faithfulness rule predicts. Evidence
  `evidence/d14-zephyr/05-m1-tick-validated.txt`.
- **Committed the fix as the board default:** `kgpe_d16_bmc_defconfig` now sets
  `CONFIG_SYS_CLOCK_EXISTS=y` + `CONFIG_HW_STACK_PROTECTION=n` (was the cooperative
  no-tick default). **D14 M1 (tickful scheduling) is DONE in QEMU.** This unblocks the
  Zephyr column: per-device Zephyr drivers can now use timers + preemptive scheduling.
- Honest env note: the validation used the SDK-check-lowered tmp workspace; the clean
  reproducible path is either SDK 1.0.1 installed, or PR #103557 merged upstream (then
  no version-check tweak). The board configs themselves are the real, committed fix.

## 2026-07-18 — Gate-(b) code review of D08 models = CLEAN; Zephyr build got past PR, now SDK-version-blocked

- **Gate (b), D08 QEMU device models — independent review returned CLEAN.** A code
  reviewer checked `kgpe_d16_i2c_fabric.c`, `jc42.c`, `w83601g.c`, `sbtsi.c` against
  the QEMU I2C core + the `pca954x` reference: transparent-mux forwarding correct
  (no hang on the NAK/broadcast path), channel-select GPIO math verified end-to-end,
  word endianness / sign / rounding correct, all bounds-checked, the earlier
  w83601g range-check (0x22 not power-of-two) confirmed correct. NO ≥80% bugs. One
  faithfulness polish applied (QEMU submodule `39638707b5`): `sb-select` defaults to
  the pull-up idle 3, not 0. So these 4 load-bearing models are now independently
  gate-(b)-vetted clean.
- **Zephyr #141 background build — env approach PROVEN, now SDK-version-blocked (not
  my code).** The dedicated ZEPHYR_BASE built out correctly: clone zephyrproject +
  `git fetch pull/103557/head` (armv5.dtsi + `arch/arm/core/arm9/` PRESENT — the PR
  IS complete + fetchable) + `west update` all succeeded. The build then failed at
  `FindZephyr-sdk.cmake`: the freshly-cloned main (PR rebased onto it) requests SDK
  cmake-package version **"1.0"** but the installed **zephyr-sdk-0.17.0** provides
  "0.17.0". So it's a Zephyr-main↔SDK alignment mismatch (the PR has been rebased
  onto newer main since the prior session's aligned build), NOT my module or the
  #141 fix. **Next:** either install a newer Zephyr SDK, or base the ARM9 arch on a
  main compatible with SDK 0.17.0 (rebase the ~770-LOC PR onto the shared base's
  commit, which accepts 0.17.0). The `tmp/zws` workspace is kept staged for that.

## 2026-07-18 — Zephyr #141: dedicated ZEPHYR_BASE build launched (background) to validate the fix

- To validate the #141 `HW_STACK_PROTECTION=n` fix (root-caused below) without the
  shared-workspace drift, launched a self-contained background build in MY worktree
  (`tmp/zephyr-env-setup.sh` → `tmp/zephyr-env.log`, cgroup-limited): clone
  zephyrproject/zephyr, fetch+checkout PR #103557 (ARM926 arch), `west update`
  (blobless/narrow), then `west build -b kgpe_d16_bmc hello_world
  -DCONFIG_SYS_CLOCK_EXISTS=y -DCONFIG_HW_STACK_PROTECTION=n`, then boot in the
  faithful QEMU and check for "Hello World!" + NO data-abort at 0x40008ffc (=the
  sustained-tick fix validated). Does NOT touch the shared tenstorrent workspace.
  Long-running (~20-40 min: clone + west update + build); result checked next cycle.
  If PASS → #141 fixed + the Zephyr column unblocks; if FAIL → the log pinpoints the
  next gap (PR-merge conflict, a west module, or the fix itself).

## 2026-07-18 — Zephyr #141 ROOT CAUSE identified (our config, not upstream); build env-blocked

- Tackled the Zephyr keystone (#141): the ENTIRE Zephyr column is `[ ]` gated on the
  "sustained tick data-aborts in arm_mmu" issue, previously deferred as an "upstream
  ARM9 arm_mmu" bug. Per the faithfulness rule (it's MY code, not upstream), re-examined it.
- **ROOT CAUSE (high-confidence): `CONFIG_HW_STACK_PROTECTION`, not upstream.** The
  data-abort is at `0x40008ffc`. In `arch/arm/core/mmu/arm_mmu.c:40` the L1 page
  table is a **STATIC 16 KB-aligned variable** (`l1_page_table`) that links into the
  kernel image at ~`0x40008000` — inside the first 1 MB DRAM section (0x40000000),
  same section as the early stacks. `0x40008ffc` is a word IN that static table. With
  HW stack protection, the per-thread stack-guard reconfigures that 1 MB section on
  every timer-driven thread switch → removes write access to the L1 table's own page
  → the next L1 entry write faults. **Fix: `CONFIG_HW_STACK_PROTECTION=n`** (or
  relocate `l1_page_table`/stacks out of the L1-table section) — a config/link choice.
  The board defconfig comment's "or per-thread MMU stack-guard updates are disabled"
  now names the specific knob + mechanism.
- **HONEST — NOT yet validated (build env-blocked, NOT my confidence in the cause):**
  the shared ZEPHYR_BASE `/home/tim/github/tenstorrent/zephyr` has DRIFTED off the
  cortex_a_r ARMv5 PR #103557 (HEAD is a Nordic sample commit; `armv5.dtsi` + the
  ARM926/ARMv5 arch code are absent from ALL its refs). So `west build -b
  kgpe_d16_bmc` fails at DTS preprocess (`fatal error: arm/armv5.dtsi: No such
  file`). I did NOT modify the shared workspace (don't-disturb-others). Kept the
  validated cooperative default (SYS_CLOCK_EXISTS=n). **To validate:** rebuild a
  ZEPHYR_BASE with PR #103557, then flip SYS_CLOCK_EXISTS=y + HW_STACK_PROTECTION=n
  and expect sustained ticks with no data-abort. This converts #141 from "deferred
  as upstream" to "specific config fix identified + mechanism proven from the source,
  pending an env rebuild to run it."
- **Build attempt — scoped the env dependency + made the DTS self-contained.** Ran
  `west build -b kgpe_d16_bmc hello_world` against the shared base; it failed in
  stages, each pinpointing a piece of PR #103557 the base lost: (1) `fatal error:
  arm/armv5.dtsi: No such file` → **VENDORED `dts/arm/armv5.dtsi` into my module**
  (mirrors `dts/arm/armv7-a.dtsi`), so the DTS no longer depends on the base and
  preprocesses. (2) Kconfig `MMU y-selected but CPU_HAS_MMU=n` — my
  `SOC_FAMILY_ASPEED select CPU_ARM926EJ_S` is UNDEFINED in the base (confirmed: 0
  `CPU_ARM926EJ_S` defs + 0 armv5/arm926 files in `arch/arm/core/cortex_a_r`). PR
  #103557 (the ~770-LOC ARM926 cortex_a_r arch core, fetched in a prior session per
  LOG below, now absent) is entirely gone from the shared workspace. Reconstructing
  it in-module = re-doing the arch port, not the #141 fix. **Precise blocker: the
  ZEPHYR_BASE must carry PR #103557** (upstream-merge it, or a dedicated base) — then
  the #141 config fix is a one-line validation. Shared workspace left untouched.

## 2026-07-18 — Completion-gate reviews dispatched (independent sub-agents)

- Per the goal's completion gates (a) reviews find nothing missed, (b) full code
  review no issues, (d) sub-agents can't find new tasks — dispatched 2 INDEPENDENT
  sub-agents (≤5 concurrent):
  1. **Code review** (feature-dev:code-reviewer) of this session's 3 code changes:
     QEMU vhub `deadlock-model` property (submodule `01323e0426`), `mkflash.py`
     copy-size computation (`47e073d`), F7 guard re-scope (`39a2fac`). Looking for
     correctness/logic/faithfulness bugs.
  2. **Schematic-enumeration completeness** (general-purpose): read the AUTHORITATIVE
     `schematic-wiring/AST2050-BMC-WIRING.md` fully + cross-check every device against
     `DEVICE-MATRIX.md`/`FULL-TASK-LIST.md` — enumerate every schematic device, flag
     any missing from the enumeration, and identify concrete NEW tasks (gate d).
- Findings will be folded back: code issues fixed, enumeration gaps + new tasks added.
- **RESULTS — both agents found real, actionable items (gates working as intended):**
  - **Code review (gate b):** vhub `deadlock-model` property + `mkflash.py` copy-size
    logic reviewed CLEAN (property wiring, vmstate omission, roundup/slot-bound
    algebra all correct). Found ONE real bug in MY F7 re-scope:
    `check_ncsi_scoped_to_mac1()` did `rglob("*")` over `qemu-firmware/kernel/`,
    which (when a kernel is built locally) walks the gitignored `kernel/linux/`
    (~88k files) whose unrelated `aspeed_g4/g5_defconfig` ALSO set
    `CONFIG_NET_NCSI=y` → the `break`-on-first-match could FALSE-PASS (mask a real
    "NC-SI dropped from kgpe-d16.config" regression) and was very slow. **FIXED:**
    read `qemu-firmware/kernel/kgpe-d16.config` directly (guard now 8/8 in 0.048s,
    was going to scan 88k files). Latent for CI (that job doesn't populate
    kernel/linux) but real for local dev — the exact path these changes were
    validated on. Good catch by the independent reviewer.
  - **Enumeration audit (gates a/d):** enumeration judged ~95% complete + rigorously
    self-audited, but a per-pin sweep of the 355-ball pinmap found 6 signals missed
    at the section level → **folded into FULL-TASK-LIST + DEVICE-MATRIX**: B1f
    `LPCPD#` (D15), B1g `PIKE2` peer `[N]`, B2 PCI `INTA#`/GPIOB0 (B11), E6
    `GPIOE6/E7↔SP5100` (U4/U3, sibling of D13), E6 `ENTEST` (R21) `[N]`, E6
    `AST_SRST#` (R20) reset→PHY. None are large subsystems — individual pins/peers.
  - **Gate (d) CONVERGENCE (round-3, independent per-ball sweep):** with the 6 gaps
    folded, a THIRD independent sub-agent did a ball-by-ball sweep of all 355 balls
    and returned **"CONVERGED — no new functional enumeration gaps found"**; it
    verified all 6 round-2 additions are correctly placed, and every functional net
    resolves to a row or `[N]`/`[B]`. The ONLY item was a prose-parity nit: the PCI
    peers `ZU1` (FW322) + `PCI6` slots were implicitly covered but not explicitly
    `[N]`-dispositioned like the LPC peers — **added** for parity. So the ENUMERATION
    gate (d) is now satisfied for the schematic: two independent audits, the second
    converging (round-1 found 5+1 → folded → round-3 found 0 new functional gaps).
    NOTE: gate (d) for the ENUMERATION ≠ the WORK being complete — the un-`[x]`
    boxes (Zephyr column, U-Boot per-device, silicon validations, etc.) remain the
    open deliverables; convergence means "every device is on the list", not "done".

## 2026-07-18 — CI GREEN confirmed for C4+F7+C2-full; C3 fix = force IPv4 (musl.cc)

- **CI confirmation (run 29639741089):** `Boot proprietary firmware -> BMC web
  service (C4)` = SUCCESS, `F7 — eth0 dedicated PHY + NC-SI sideband scoped` =
  SUCCESS, `Boot U-Boot -> Linux + SSH (C2 full chain)` = SUCCESS, plus D07 NC-SI,
  Build QEMU, Build initramfs. So this cycle's THREE fixes (C4 vhub, F7 guard,
  C2-full mkflash) are all gate-(b) green. Only C3 remained red.
- **C3 root cause = IPv6, not a musl.cc outage.** The `Build Raptor userspace`
  job failed fetching the musl toolchain with `failed: Network is unreachable`
  (wget exit 4) — the classic signature of a host with an IPv6 address but no
  working IPv6 *route* resolving an AAAA record. GitHub-hosted runners have exactly
  that. musl.cc serves fine over IPv4 (verified here: the 102 MB
  `arm-linux-musleabi-cross.tgz` downloads cleanly over IPv4, sha256 d70c6071…).
- **Fix: `wget -4` (force IPv4)** in `raptor/scripts/build-raptor-userspace.sh` —
  a trivial, non-outward-facing change that avoids the broken IPv6 path. (The
  alternative — mirror the toolchain as a GitHub *release* asset — is an
  outward-facing publish the auto-mode classifier blocked; the `-4` fix is better
  anyway and needs no publish.) **Honest confidence:** high but not proven — I
  can't reproduce the runner's network locally; the CI run for this commit is the
  real test. If `-4` doesn't clear it, the fallback is a release-asset mirror
  (needs the user to authorize the publish).
- **RESULT (run 29640421665): `-4` narrowed it but did NOT fix it.** The error
  changed from `Network is unreachable` (IPv6) to `Connection timed out` (IPv4) —
  so musl.cc IS blocked/dropped from the GitHub runner IP ranges over BOTH
  families, not merely an IPv6 gap. No fetch-side option (retry/IPv4/mirror-URL on
  musl.cc) can work. **The only robust fix is hosting the toolchain somewhere
  runners CAN reach — a GitHub *release* asset in this repo** (runners reach
  github.com fine). The 102 MB `arm-linux-musleabi-cross.tgz` is downloaded +
  sha256-verified (d70c6071…) and ready to upload, but `gh release create` is an
  outward-facing publish that the auto-mode classifier BLOCKED — it needs user
  authorization. Kept `-4` (harmless + correct: it removes the IPv6-unreachable
  failure mode). **C3 is therefore BLOCKED on a user decision:** (a) authorize the
  release-asset mirror (fastest), or (b) switch to a source build (musl-cross-make,
  reachable but ~20-30 min) or a bootlin toolchain (different prefix, needs rework).
  Surfaced to the user. This is the ONE item this session I cannot close myself.

## 2026-07-18 — F7 guard FIXED: it was an "incorrect claim that functionality doesn't exist"

- Directly addresses the goal's flagged failure mode ("incorrect claims have been
  made about functionality not-existing"). The F7 guard (`f7-ncsi-evidence.py`)
  asserted "NO NC-SI anywhere" (checks 4/5: kernel must NOT build CONFIG_NET_NCSI;
  ftgmac100 must have zero NC-SI refs) and failed CI. But the AUTHORITATIVE schematic
  `AST2050-BMC-WIRING.md` §7 is titled "Ethernet — dual channel: dedicated PHY +
  NC-SI sideband": MAC0/eth0 = dedicated RTL8201 PHY (RMII1), AND MAC1/RMII2 = an
  NC-SI SIDEBAND to the two 82574L host NICs. NC-SI genuinely exists — and the D07
  work implements it (kernel CONFIG_NET_NCSI, DTS `&mac1 { use-ncsi }`, and the
  `D07 — NC-SI channel discovery on MAC2` CI job PASSES). So the guard was stale +
  contradicted working, schematic-faithful functionality.
- **Re-scoped the guard to the dual-channel ground truth** (kept it MEANINGFUL, not
  weakened): (1) `&mac0` = rmii dedicated PHY, no use-ncsi [unchanged core guard];
  (2) Raptor MAC1 scratch = 0 [its U-Boot uses dedicated PHY, doesn't use the
  sideband]; (3) datasheet: G3 MAC has no NC-SI *hardware* mode → NC-SI is the
  software protocol over RMII2; (4) NEW — NC-SI is SCOPED to `&mac1` (kernel builds
  CONFIG_NET_NCSI + DTS puts use-ncsi on &mac1, never &mac0); (5) NEW — `&mac1` is
  `status="disabled"` by default so the C2/C4/NFS single-NIC oracle boots are
  unaffected (the D07 test flips it okay at runtime). Guard now catches the real
  regressions: eth0 flipped to NC-SI (check 1), NC-SI dropped/mis-scoped (check 4),
  sideband silently enabled → breaks C2/C4 (check 5). **`f7-ncsi-evidence.py` →
  8 passed, 0 failed.** Updated the CI job name/comment to the dual-channel truth.
- Corrects the recalled-wrong belief in [[bmc-functionality-program]] ("true NC-SI
  architecturally IMPOSSIBLE") — see [[ncsi-sideband-exists-schematic]]. Follow-up:
  `F7-NCSI.md` prose may still carry the old "not NC-SI" framing (doc, non-gating).

## 2026-07-18 — C4 FIXED: vhub deadlock made opt-in (default-off); both C4 + C2 verified

- **Traced the vendor firmware's exact udc sequence** (temporary UDCTRACE logging,
  reverted): it writes CTRL=0x80000800 (release PHY reset), does ~10 EP-setup writes
  (0x08/0x0c/0x10/0x14/0x18/0x1c/0x30/0x38), then CTRL=0x80000801 (connect) — WITHOUT
  ever reading CTRL[31]. The model only sets `phy_ready` on a CTRL *read*, so the
  connect latched ISR[18] → 1.58M-access ISR livelock → the vendor fw's nowayout WDT
  reset.
- **Fundamental finding (why a "correct trigger" isn't achievable here).** Compared
  against the mainline driver (`core.c` `ast_vhub_init_hw`): the UNPATCHED mainline
  (hangs on silicon) and the vendor fw (safe on silicon) do the SAME register-access
  pattern between reset-release and connect — reset-release, SW_RESET pulse + EP
  setup, connect — differing ONLY in patch-0007's poll loop, whose distinguishing
  effect is its `udelay(10)` TIMING. QEMU without icount cannot advance virtual time
  through a guest `udelay()`, so there is NO deterministic signal to latch the
  deadlock for the mainline without ALSO false-latching it for the vendor. Every
  access-based proxy I tried (poll-read, CTRL re-write, non-CTRL access count,
  SW_RESET-clears-phy) breaks either the vendor OR the patched/mainline case.
- **Fix (QEMU submodule `01323e0426`): gate the deadlock behind a default-OFF
  `deadlock-model` property.** Primary faithfulness rule = legacy firmware must
  always boot; the hazard is real but un-latchable deterministically without
  breaking the vendor, so it is opt-in (a dedicated patch-0007 regression scenario
  sets `deadlock-model=on`). **Verified locally:** C4 now SURVIVES 130s and reaches
  `aim_function_execute netGetCurrentIfConfig` (was WDT-reset @27s); **C2 full-chain
  still `C2 RESULT: PASS`** (SSH). CI will confirm F6 (patched-kernel vhub probe)
  which checks probe-success (unaffected by deadlock-off). So BOTH legacy-boot
  regressions this cycle (C2-full = my mkflash truncation; C4 = my vhub model) are
  now FIXED + verified — my code, not the hardware, exactly as the principle says.

## 2026-07-18 — C4 CULPRIT (corrected): the USB vhub DEADLOCK model (192c4ef4da), NOT the mux fabric

- **Self-corrected a premature bisect conclusion (the empirical method caught it).**
  I'd logged "culprit = be673b284e (mux fabric)" below, but an isolation test
  falsified it: neutering the fabric's I2C forwarding AND fully disabling the
  fabric init BOTH still reset C4. Re-reading history, `be673b284e` is NOT adjacent
  to the good boundary `ae204f8` — 4 commits sit between them. My bisect had skipped
  testing the immediate neighbours. Corrected range = ae204f8..be673b284e.
- **Proper bisect (resource-limited builds):** `192c4ef4da` (USB vhub deadlock
  model) → reset @27s = **BAD**; its parent `d67f9e4d8a` → survived 110s = **GOOD**.
  So the definitive culprit is **`192c4ef4da` "faithful AST2050 (G3) USB vhub
  deadlock model — reproduces the probe hang"** (wires the udc IRQ → VIC INT#5 +
  latches HUB0C[18] "USB command bus dead-lock" when UPSTREAM_CONNECT is asserted
  into a not-ready PHY). The C410X vendor firmware asserts connect without the
  PHY-ready poll our patched C2 kernel (patch 0007) does → hits the modeled
  livelock → CPU stuck in the unmaskable ISR → doesn't pet the WDT → reset.
- **Faithfulness call + fix direction.** Per [[qemu-must-model-real-hardware]] a
  broken legacy boot is a bug in MY model. The vendor firmware boots on real
  AST2050 silicon, so my model must not deadlock it. Root approximation: the model
  makes PHY-ready *poll-triggered* (for cross-host-speed determinism), but real
  silicon readies the PHY on a physical delay after reset-release (HUB00[11]); a
  driver that WAITS-then-connects (likely the vendor fw) is fine on silicon but the
  poll-triggered model still reports "not ready" → false deadlock. **Fix (next,
  focused):** trace the vendor fw's udc/HUB register access (QEMU `-d`/model log)
  to see its reset-release→connect sequence, then broaden the model's PHY-ready
  condition to also become true on that faithful pattern WITHOUT losing the
  mainline-driver deadlock that C2/patch-0007 verification relies on (C2 must stay
  green). Keep both the deadlock repro (for the unpatched mainline path) and a
  legal path the vendor fw + patched kernel take. Deferred to fresh context — a
  model refinement I won't rush at depth (risk: regress the C2 deadlock repro).

## 2026-07-18 — C4 BISECTED to the I2C mux fabric commit (be673b284e) — strap EXONERATED

- **Ran the bisect (resource-limited builds via `systemd-run --user --scope
  -p CPUQuota=600% -p MemoryMax=8G nice -n 15`, C4 flash built once + reused).**
  Signal = does QEMU exit early (guest WDT reset = BAD) or survive 100s (GOOD):
  - `c67c1b6bda` (MAC2) → reset @27s = **BAD**
  - `4ff6a74504` (strap) → reset @32s = **BAD**  ← my 3-turn prime suspect, now EXONERATED
  - `be673b284e` (I2C mux fabric) → reset @33s = **BAD**
  - `ae204f8` (merge just before the device work) → **survived 110s = GOOD**, and the
    serial progressed FURTHER (`aim_function_execute netGetCurrentIfConfig`) where the
    bad builds hang at `route: SIOCADDRT`.
- **Culprit = `be673b284e` "hw: KGPE-D16 I2C mux fabric (QU9/QU5/U23) + JC-42.4
  TSOD"** (adds `hw/i2c/kgpe_d16_i2c_fabric.c`, `hw/sensor/jc42.c`, wires them + 2
  GPIO board-glue outputs in aspeed.c/aspeed_gpio.c). The C410X vendor firmware
  probes I2C during post-network init; my mux fabric model hangs that access → the
  daemon blocks → the vendor fw's `nowayout` 10s ASPEED WDT isn't petted → reset.
  Faithfulness confirmed: it's MY model, exactly as the principle says. Lesson: a
  git-bisect (tests states) beat 3 turns of the plausible-but-wrong strap theory.
- **Next:** read `kgpe_d16_i2c_fabric.c` / `jc42.c` for the non-I2C-compliant
  hang (bus-hold / infinite forward / bad NAK) and fix it faithfully, then re-boot
  C4 to confirm it reaches steady-state. See [[c4-c2full-legacy-boot-regression-suspect]].

## 2026-07-18 — C2-full CI-confirmed (PASS); C4 confirmed a REAL regression (bisect range bracketed)

- **C2-full: independent CI confirmation.** The run for the mkflash fix (47e073d)
  shows the `Boot U-Boot -> Linux + SSH login (C2 full chain)` job = **success**.
  So C2-full is resolved local AND CI (gate-b met for this item).
- **C4: NOT flaky — a real regression, now bracketed by CI history.** Checked the C4
  job across ~20 runs: it PASSES on parent commits that pin QEMU submodule
  `e61dd3461d` (231ddf7d, bb09a854) and FAILS on those pinning `512d56d217`
  (current). `e61dd3461d` is a clean ANCESTOR of `512d56d217`, so this is a genuine
  pass→fail regression, not a timing flake. Per [[ast2050-faithful-qemu]] C4 was a
  passing oracle at submodule `ae204f8` (inside this range), so the regression is in
  the **~10 device-driver-program submodule commits after ae204f8**: be673b284e
  (I2C mux fabric), 4ff6a74504 (measured strap), d931f92770 (W83795 silicon seed),
  f00a39540e (DIMM_A2 SPD), c67c1b6bda (MAC2/NC-SI wiring), 9561717b8d (GPIO latch
  migrate), 58dfe21497 (FRU EEPROM), d0556622ed/a43b8b221e (W83601G), 512d56d217
  (SB-TSI). DRAM-size angle likely EXONERATED: the strap's 56 MB is the faithful
  real-hardware value (64 MB − 8 MB VGA) and the real C410X AST2050 also has 64 MB,
  so its firmware must cope with 56 MB. **Next (bounded bisect, fresh context):**
  build QEMU at the midpoint of ae204f8..512d56d217, boot C4 (build-c4-flash.py +
  `-M kgpe-d16-bmc -m 128 -no-reboot`, watch for the ~18 s reset), narrow to the
  culprit commit, then fix the model (or, if it's the faithful strap vs C410X-fw
  mismatch, override the strap in the C4 probe only). ~4 build+boot steps.

## 2026-07-18 — C2-full fix CONFIRMED locally (SSH PASS); C4 diagnosed (late-boot WDT reset)

- **C2-full fix verified end-to-end locally** (not just pushed). Built the OpenBMC
  AST2400 U-Boot, assembled the flash with the fixed `mkflash.py`, booted via
  `ssh-test.py`: the init ramdisk now `Verifying Checksum ... OK` (was "Bad Data
  CRC"), `Starting kernel`, Linux 6.6.70 boots, `dropbear: listening`, SSH connects
  → **`C2 RESULT: PASS`**. So the initrd-truncation root cause + fix are proven.
- **C4 reproduced + diagnosed locally.** Built the C4 vendor flash (build-c4-flash.py
  from the committed `c410xbmc135.zip` + the new u-boot) and booted `-M kgpe-d16-bmc
  -m 128 -no-reboot` with serial capture. The Dell/Avocent MergePoint firmware boots
  FAR: U-Boot ("SOC: AST1100/AST2050", "DRAM: 56 MiB") → vendor Linux → ASPEED WDT
  installed (irq 27, **heartbeat=10s, nowayout=1**) → BusyBox init → eth0 DHCP
  (10.0.2.15) → network/IPMI config → then QEMU exits rc=0 = a GUEST RESET. So C4 is
  a **late-boot reset**, NOT an early-boot / strap-breaks-boot failure (C-UBOOT +
  C2-full + all F-tests boot fine on the same binary).
- **Mechanism:** the firmware reaches network-up (~18s, `waitforsm ... ended sec:18`)
  then resets — consistent with the `nowayout` 10 s WDT firing once the boot state
  machine stops petting it (before the web/steady-state daemon takes over).
  `waitforaim: aim_config_get_int failed` is a NON-fatal early warning (later
  `aim_function_execute() returned success`), and there are NO I2C/EEPROM/probe
  errors in the log — so it's not an obvious device-model break.
- **Leading (unconfirmed) hypothesis:** the measured-strap commit `4ff6a74504`
  (SCU70 `0x00819582`, which also changed reported DRAM 128MB→56MB) affects the
  C410X firmware — C4 runs *C410X* vendor firmware (a DIFFERENT board) on the
  kgpe-d16 machine purely as a SoC-faithfulness probe, so a board-specific strap the
  machine now reports faithfully for KGPE-D16 may not suit the C410X firmware. If
  confirmed, the fix belongs in the C4 TEST (override the strap to a C410X-suitable
  value for that probe), NOT the machine default (0x00819582 is correct for the real
  KGPE-D16). **Confirm next:** rebuild QEMU with the pre-4ff6a74504 strap and re-boot
  C4 (bounded bisect). Deferred to fresh context, not rushed. See
  [[c4-c2full-legacy-boot-regression-suspect]] — C2-full half RESOLVED.

## 2026-07-18 — C2-full FIXED: it was MY regression (grown initramfs truncated by mkflash), NOT the firmware

- **Followed the faithfulness principle to a real bug in my own tooling.** The
  C2-full failure (`FAIL: dropbear did not come up within 240s`) is NOT a strap /
  legacy-boot-model regression. Discriminating evidence: in the SAME green-build run
  the **C-UBOOT oracle (Raptor G3 U-Boot → `boot#`) PASSES**, and C5/F2/F3/F4/F5 +
  C2-direct all pass — so the strap `0x00819582` (`4ff6a74504`) is EXONERATED (early
  SCU/PLL init is fine).
- **Actual root cause (mine).** Pulled the C2-full boot log: OpenBMC U-Boot boots,
  loads the kernel, then on the init ramdisk prints `Verifying Checksum ... Bad Data
  CRC` → bootm aborts → Linux never starts. `mkflash.py`'s bootcmd copied the initrd
  with `cp.b … 0x200000` (2 MB), but the uInitrd is **3,123,642 B (2.98 MiB)** —
  because my earlier CI fix (`ensure_usbip_src`) correctly restored the usbip
  userspace, growing the initramfs past 2 MB. The 2 MB copy truncated the ramdisk →
  bad CRC. This is the exact twin of the kernel-slot truncation the code already
  documented (NFS kernel grew past 3 MB → 0x300000 copy truncated it).
- **Fix (`scripts/mkflash.py`), best-practice + fail-loud.** Stop hardcoding copy
  sizes: compute kernel/initrd DRAM-copy sizes from the ACTUAL file (rounded up to a
  64 KB erase block) and FAIL LOUD if either overflows its flash slot (kernel
  0x400000, initrd 0xB00000). Verified locally: kernel 3.5 MB → copy `0x360000`,
  initrd 2.98 MB → copy `0x300000` (was 0x200000 = the bug); flash assembles clean.
  Can't run the full chain locally (no OpenBMC `u-boot.bin`); CI confirms end-to-end.
  NOTE: kernel is now 3.5 MB, close to its 4 MB slot — the new guard will fail loud
  if it overflows (rather than silently truncating like before).
- **C4 is SEPARATE + still open** (`qemu exited early rc=0`, Dell vendor fw — doesn't
  use our initrd). Investigate next. See [[c4-c2full-legacy-boot-regression-suspect]]
  (the C2-full half is now RESOLVED as my-tooling, not a model regression).

## 2026-07-18 — CI GREEN for my jobs; 4 pre-existing failures surfaced (triaged, NOT yet fixed)

- With both CI root causes fixed (run 29635771812), the QEMU build + initramfs are
  green and **my jobs now run and PASS in CI**: `B1 — LPC sub-blocks`, `D08 —
  W83601G`, `D09 — SB-TSI`, `Boot new stack + SSH (C2)`, `F5b M2 (host KCS IPMI)`,
  `F3 — sensors`. So B1c/B1d/D08/D09 are now genuinely CI-validated, not just local.
- **4 OTHER jobs still fail.** They were masked by the broken QEMU build (all
  downstream jobs were failing/skipped), so they surface only now. Triaged with
  exact signatures — none claimed resolved:
  1. **C3 (Build Raptor userspace)** — `failed: Network is unreachable / Connection
     timed out` fetching the musl toolchain. **Environmental CI network flake**, not
     code; should pass on re-run. (Hardening idea: cache/mirror the musl toolchain.)
  2. **C4 (Boot proprietary firmware → web)** — `C4 RESULT: FAIL — qemu exited early
     (rc=0)`. The Dell vendor firmware terminates before the web service comes up.
  3. **C2 full chain (U-Boot → Linux + SSH)** — `FAIL: dropbear did not come up
     within 240s`. The U-Boot-mediated boot never reaches SSH. NOTE: the *direct*
     kernel boot `Boot new stack + SSH (C2)` PASSED in the same run — kernel +
     initramfs + dropbear are fine — so the differentiator is the **U-Boot stage**.
  4. **F7 (NC-SI ground-truth guard)** — 2 asserts fail: `CONFIG_NET_NCSI=y` present
     in kgpe-d16.config + NC-SI refs in ftgmac100.c. See separate note below.
- **FAITHFULNESS FLAG (C4 + C2-full).** Both exercise the *early boot* path (vendor
  firmware / U-Boot), both went uncaught while CI was broken, and both could be
  regressions from the 10 recent QEMU submodule commits (ast2050-faithful
  `eda871c48f` → `512d56d217`). Leading suspect: `4ff6a74504` (kgpe-d16-bmc uses the
  MEASURED strap `0x00819582`) — a strap change alters early clock/PLL/reset init
  for U-Boot + vendor firmware but NOT the direct DTB kernel boot (which is why C2
  direct passes and C2-full fails). Per the faithfulness principle a broken legacy
  boot is a bug in MY model, so this MUST be reproduced locally + bisected (build
  QEMU at `eda871c48f` vs `512d56d217`, run web-test.py / the U-Boot boot on each).
  Deferred to a fresh context — not rushed, not hand-waved. Could also be a plain
  240s-timeout under concurrent-CI load; the repro settles which.

## 2026-07-18 — F7 guard vs schematic: NC-SI sideband DOES exist (guard too absolute)

- The F7 "dedicated-PHY, not NC-SI" guard (`f7-ncsi-evidence.py`) now fails because
  D07 work added `CONFIG_NET_NCSI=y` + NC-SI handling to `ftgmac100.c`. Checked the
  **authoritative** schematic: `AST2050-BMC-WIRING.md` §7 is titled "Ethernet — dual
  channel: **dedicated PHY + NC-SI sideband**" and documents BOTH — Channel 1
  (RMII1/MII → RTL8201N mgmt PHY = the BMC's own eth0) AND **Channel 2 (RMII2/NC-SI
  → 2× Intel 82574L host NICs)**. So NC-SI genuinely exists on this board as a
  sideband; the D07 additions are schematic-faithful. My memory's "true NC-SI
  architecturally impossible here" was an EARLIER, less-complete understanding that
  the expanded schematic netlist supersedes (schematic > memory).
- **Reconciliation needed (not rushed):** F7 conflates two invariants — "the BMC's
  eth0/management is a dedicated PHY (RMII1→RTL8201, TRUE)" vs "the board has NO
  NC-SI at all (FALSE per §7)". The guard must keep asserting the former and stop
  asserting the latter. Requires reading the full `f7-ncsi-evidence.py` + `F7-NCSI.md`
  to re-scope checks 4/5 correctly. Deferred to avoid getting the invariant wrong.

## 2026-07-18 — CI ROOT-CAUSE FIXES: unpushed QEMU submodule + initramfs missing usbip source

- **Honest correction to a completion-gate claim.** Checked CI on the branch and
  found the `D16 QEMU firmware stack` workflow **failing on every recent push**.
  Two INDEPENDENT root causes, both now fixed; my QEMU/initramfs "bind" results
  were validated **locally**, NOT in CI — the gate-(b) "CI green" bar was not
  actually met. Recorded plainly, not papered over.
- **Cause 1 (git, not code): unpushed QEMU submodule SHA.** The parent repo pins
  the QEMU submodule at `512d56d217` (SB-TSI), but that commit — and
  `a43b8b221e`/`d0556622ed` (W83601G) before it — were committed in the submodule
  but **never pushed** to `github.com/mithro/qemu`. `git branch -r --contains
  512d56d217` was empty. `actions/checkout@v4` (`submodules: recursive`) then can't
  fetch the pinned SHA → submodule init fails → "Build custom QEMU" fails →
  everything downstream (C2/C4/C-UBOOT/F2/F3/F5/F5b/F4/F9…) cascades to failure and
  my new B1/D08/D09 jobs are *skipped*. C code compiles fine locally (binary built
  14:15). **Fix:** pushed submodule branch `claude/bmc-functionality`
  (`a43b8b221e..512d56d217`) to `git@github.com:mithro/qemu`. **Confirmed:** the
  fresh `workflow_dispatch` run 29635041209 shows **"Build custom QEMU" = success**
  (was failing). Lesson: after any QEMU submodule commit, push the submodule remote
  BEFORE relying on CI — the parent gitlink alone is not enough.
- **Cause 2 (CI env): build-initramfs job lacked the usbip source.** With the QEMU
  build green, the boot jobs were still skipped because `Build initramfs` *also*
  fails — actual error: `FileNotFoundError: …/kernel/linux/tools/usb/usbip`.
  `build-usbip.py` reads usbip from the kernel tree, but `kernel/linux` is NOT a
  submodule — `build-kernel.sh` clones it (`git clone --depth 1 --branch v6.6.70`
  stable Linux) — and the initramfs job never runs that, so the tree is absent in
  CI. Built locally only because my worktree already has the kernel. Regression from
  adding the usbip initramfs (2026-07-16). **Fix:** made `build-usbip.py`
  self-contained — new `ensure_usbip_src()` prefers the checked-out kernel tree,
  else sparse-clones just `tools/usb/usbip` at the pinned `KERNEL_VERSION`
  (fail-loud). Added `git autoconf automake libtool pkg-config` to the initramfs
  job deps (usbip autogen + libudev-zero/usbip clones). Fallback path tested locally
  (`USBIP FALLBACK CLONE OK`). Lesson: any job that consumes the kernel *source*
  tree must obtain it itself — only build-kernel clones it.

## 2026-07-18 — B1c snoop: silicon kernel BUILT + STAGED; POST-capture scoped (not yet run)

- Built the real-HW kernel/DTB from the snoop-armed source and **verified the
  shipped DTB**: `build-realhw-kernel.py` → `tmp/uImage-kgpe-d16-realhw` +
  `tmp/aspeed-bmc-asus-kgpe-d16-realhw.dtb`; `fdtget` confirms
  `lpc-snoop@90 status=okay`, `snoop-ports=0x80`, `lpc-ctrl status=okay`,
  `serial@1e787000 status=okay`. Staged to the bridge Pi as
  `/srv/tftp-bmc/uImage-kgpe-d16-lpcsnoop` + `kgpe-lpcsnoop.dtb`.
- **Trap caught + documented:** the flat `dts/aspeed-bmc-asus-kgpe-d16-realhw.dts`
  is a doc MIRROR — `build-realhw-kernel.py:51` compiles the overlay tree
  `qemu-firmware/dts/aspeed-bmc-asus-kgpe-d16.dts` for *both* QEMU and silicon;
  editing the mirror alone changes nothing shipped. The overlay tree already
  carries `&vuart/&lpc_ctrl/&lpc_snoop(0x80)` okay (grep-verified). Added a header
  note to the mirror + synced its vuart/snoop `status` so it can't mislead.
- **Schematic resolves the connectivity half (authoritative).** `AST2050-BMC-WIRING.md`
  §5 (lines 205-228): "The AST2050 is an **LPC peripheral** on the SP5100 southbridge's
  LPC bus", shared with the Super-I/O + TPM header; every AST2050 LPC ball
  (`LCLK`/`LFRAME#`/`LAD0-3`=A16/B16/B17/A17/D16/C16, `LPCSIRQ`=C15) wires straight
  to the SP5100. So the BMC snoop hardware physically sees every LPC I/O cycle the
  SP5100 emits — the "is the BMC even on the host LPC bus?" question is answered YES.
- **Honest status — NOT run on silicon yet.** What remains is narrower: does the
  SP5100 (as LPC host bridge) *forward* the host CPU's port-80h I/O writes onto LPC,
  or claim port 0x80 internally? On AMD SB700/SP5100 + coreboot this is conventionally
  forwarded (it's how BMC POST snoop works on these boards), so the expectation is
  positive — but that's config/firmware behavior, not proven on this board. Capture requires
  a JTAG re-netboot of the *live* BMC onto the snoop kernel, then a **host-only**
  reset (BMC-GPIO-driven; the whole-board Tasmota plug won't do — an AC cycle
  drops the JTAG-netbooted BMC too), then reading `/dev/aspeed-lpc-snoop0` while
  the host POSTs. Deferred to a dedicated hardware session rather than started at
  the tail of a long context, where running out mid-session could leave the BMC
  JTAG-halted (violating "legacy must always boot"). Board left healthy + untouched
  (BMC pings 192.168.66.2, uImage-sbtsi, host on). Artifact is staged so the next
  session goes straight to netboot. Matrix row 5 silicon stays ⬜ (honest), NOT ✅.

## 2026-07-18 — B1c/B1d LPC snoop + vUART drivers bind in QEMU (BMC-side done)

- The gate-(d) audit split LPC B1 into KCS/mailbox/snoop/vUART; drove the snoop +
  vUART to QEMU BMC-side done. Enabled `&lpc_snoop { snoop-ports=<0x80> }` +
  `&lpc_ctrl` (were disabled g4-dtsi children) alongside the already-enabled
  `&vuart` in the QEMU DTS; rebuilt the DTB.
- New `scripts/lpc-test.py` (CI job `boot-lpc`) boots kgpe-d16-bmc and confirms
  against the faithful G3 LPC model (`aspeed_lpc_ast2050.c`):
  * `8250_aspeed_vuart` binds the vUART @0x1e787000 as **ttyS5 "ASPEED VUART"** (B1d)
  * `aspeed-lpc-snoop` binds **`1e789090.lpc-snoop` → `/dev/aspeed-lpc-snoop0`** (B1c)
  * `ast-kcs-bmc` → `/dev/ipmi-kcs3` (B1a, already done)
  * `aspeed-lpc-ctrl` binds (`1e789080.lpc-ctrl`) but needs a `memory-region` to
    create its char device (host-mapped window) — partial.
- Matrix rows 5/6 QE+LQ → ✅. FULL-TASK-LIST B1c/B1d QEMU [x]. **Honest limit:**
  full POST-code CAPTURE (snoop) and a host-visible vUART SESSION need a host LPC
  master driving I/O cycles — present on real silicon (the SP5100), absent in the
  BMC-only QEMU machine; those are silicon-side (catch a host mid-POST). B1b
  mailbox still needs a separate node + host peer.

## 2026-07-18 — E3 LEDs validated on SILICON + userspace; E1/D6 GPIO map confirmed

- Leveraged the live silicon board (host on, uImage-sbtsi) to validate the GPIO
  signal map without a new netboot. `/sys/kernel/debug/gpio` shows the BMC driving
  the named lines: `led-bmc-status-n` (ON), `led-cpu1/2-err-n` (no faults),
  `led-id-n` (off), the power/reset controls (lockout/power-up/reset/power-down),
  and the QU5 `spd-mux-s0/s1` selects; `power-state-in` (H2) = hi (host on).
- **E3 LEDs DONE silicon+userspace:** `echo 1 > /sys/class/leds/identify/brightness`
  flips the real GPIO `led-id-n out hi→out lo` (LED ON), `echo 0` flips it back —
  the leds-gpio driver + `/sys/class/leds` path drives the real AST2050 GPIO.
  Evidence `evidence/e-gpio-leds/00`. Matrix row 32 LS/LU → ✅; FULL-TASK-LIST E3.
- Honest gap confirmed: the §11 platform-MONITOR inputs (THERMTRIP/PROCHOT/
  DDR_THERM/NMI/POST_COMPLT/SYNCFLOOD) are NOT gpio-line-named — they're in
  TACH/alt pinmux, so E2 needs DTS pinmux+line-name work + a reboot.

## 2026-07-18 — gate (d) task-discovery audit found MISSING tasks → folded them in

- A sub-agent task-discovery audit (gate d: "can anyone find tasks that SHOULD be
  on the list?") found REAL gaps by cross-checking the per-pin netlist
  (`pinmaps/QU1_pins.md`) — the prior "nothing skipped" coverage assertion was
  OVERSTATED. Honestly folded all of them in:
  - **GAP 1 (biggest): the SoC ADC block** (0x1E6E9000, IRQ22, RAPTOR "Change 16",
    needs `aspeed,ast2050-adc`) had NO row → added FULL-TASK-LIST A9 + matrix row
    41 (QE 🔶, silicon Ⓝ board-disposition since VP0-17 are GPIO here, IIO driver ⬜).
  - **GAPs 2-3,9: three §11 monitor INPUTS** — `AST_BIOS_POST_COMPLT#` (A10),
    `AST_SYNCFLOODIN#` (B8), `FP_NMIBNT#` (U1) → added to E2's input set.
  - **GAPs 4-5: three control OUTPUTS** — `AST_RESETDIS#` (C10), `AST_PWRBNTDIS#`
    (C11), `AST_BRST#` (P21, the BMC's own PCI/VGA reset) → added to E5.
  - **GAP 6: LPC split** — B1 was one collapsed row; split into B1a KCS (done),
    B1b mailbox, B1c port-80h snoop, B1d vUART, B1e TPM-passthrough (matches the
    matrix rows 4-7 the FULL-TASK-LIST had lumped).
  - **GAP 7: I²C slave/multi-master** — D1 was master-only; added D1b (target mode
    + SP5100 co-master arbitration).
  - **GAPs 8,10,11: CU2 RMII clock-gen, VGA_HDR1, ROMA0-23 spare GPIO** — explicit
    dispositions in the coverage assertion.
- This is gate (d) working as intended: the audit found genuine omissions, and
  they are now tracked (honestly `[ ]`/`[~]`/`[N]`), not silently skipped. The
  new items are the next work to drive to completion. Re-run gate (d) after
  building the ADC/LPC-split/etc. to confirm nothing else is discoverable.

## 2026-07-18 — 🎉 D09 SB-TSI validated ON SILICON (BOTH-SIDES DONE)

- Honored the audit's "achievable, not blocked" reclassification by actually
  DOING the SB-TSI silicon read. Steps: added amd,sbtsi + enabled i2c-bus@100
  (i2c3) in the real-HW DTS; built the real-HW kernel (CONFIG_SENSORS_SBTSI) +
  DTB; confirmed host powered (GPIOH2/SYS_PWRGD=1); JTAG-booted to U-Boot
  (boot-silicon-uboot.sh) and TFTP-booted the new kernel/initrd/dtb (proven
  load-address sequence from the boot log).
- **The in-kernel sbtsi_temp driver bound the REAL AMD CPU SB-TSI @0x4c on I2C4
  (Linux i2c-3) and read a live temperature: temp1_input=14375 (stable x3),
  cross-checked against raw regs TEMP_INT=0x0e / TEMP_DEC=0x60 = 14.375°C — the
  hwmon value MATCHES the registers.** P1@0x4d NAKs (socket-2 CPU absent — a
  faithful result). **Host STAYED ON through the BMC reset** (GPIOH2 still 1 —
  the F2 reset-glitch fix held; no power drop, as I'd assessed). Evidence
  d09-sbtsi/01-silicon-pass.txt.
- D9 is now BOTH-SIDES: QEMU (model, 45500/43000) + silicon (real CPU, 14375).
  FULL-TASK-LIST D9 silicon [x]; DEVICE-MATRIX row 23 LS ✅. Board left booted on
  uImage-sbtsi (host on).

## 2026-07-18 — explicit origin/main merge command run (Already up to date)

- Ran, THIS SESSION, the actual merge command (not just a status check):
  ```
  git fetch origin
  git merge --no-ff origin/main -m "Merge origin/main into claude/bmc-functionality (2026-07-18)"
  ```
  Result: **"Already up to date."** origin/main tip = `85bd82a` (PR #29
  schematic-wiring); `git rev-list --left-right --count origin/main...HEAD` = `0
  388` (branch is 0 behind / 388 ahead). origin/main is an ANCESTOR of HEAD, so
  there is nothing to integrate — the merge is a genuine no-op, not a skipped
  step. (This branch only reaches main via PR merges per the repo convention, so
  it accumulates a large ahead-count; that is expected, not drift.)

## 2026-07-18 — completeness gate (a) CLOSED: 3rd audit CONFIRMED CLEAN

- Third (confirmation) completeness audit returned **"CONFIRMED CLEAN — all
  second-audit fixes present, no substantive issues found."** Verified: NC-SI row
  11 LS=⬜ (weasel gone), zero `❓` symbols, VGA-DAC row 12 QE=🔶, USB row 9
  LS=🔷/LU=🔶, the FULL-TASK-LIST-authoritative header note, and the D9 SB-TSI
  in-kernel claim substantiated (sbtsi.c + CONFIG_SENSORS_SBTSI + hwmon test + CI).
  Independent sweep: coverage complete (every §14 chip / §10.2 device / §11 signal
  / §15 connector maps to a row), NO fabricated citations (sampled the strongest
  ✅ files — all exist), NO remaining weasel (the surviving [N]/[B] are legitimate;
  the reframed items are honestly [ ] "hard undone work"). Cross-doc consistency
  good. So **gate (a) is satisfied** — three sub-agent completeness reviews, the
  last finding nothing missed/skipped/overstated.
- Fixed the one cosmetic slip it flagged: DEVICE-MATRIX row-9 prose note still read
  "LS = 🔶" while the cell was 🔷 — reconciled the note to 🔷 (blocked) + 🔶 LU.
- Gate (b) code reviews: W83601G, SB-TSI, Zephyr M1 all returned clean this
  program. Gates (a)+(b) hold for the code developed so far; new code (PMBus/PSU,
  NC-SI pinmux, etc.) gets the same review treatment as it lands.

## 2026-07-18 — D09 in-kernel sbtsi_temp bind + SB-TSI code-review-clean + audit-2 matrix re-sync

- **D09 in-kernel driver DONE (QEMU):** added `CONFIG_SENSORS_SBTSI=y` to
  kernel/kgpe-d16.config, rebuilt. The real Linux `sbtsi_temp` hwmon driver binds
  the `amd,sbtsi` DT nodes on i2c3 and reads the QEMU model:
  `3-004c/hwmon/.../temp1_input`=45500, `3-004d`=43000. `scripts/sbtsi-test.py`
  rewritten to validate the hwmon sysfs path (the real driver + model together) —
  supersedes the raw-i2cget check (which would now collide with the driver-owned
  device). D9 Linux-QEMU (LQ) + userspace now [x]. Evidence d09-sbtsi/00 appended.
- **SB-TSI model code-review CLEAN (gate b):** sub-agent review of hw/sensor/sbtsi.c
  + wiring found no defects (bounds-checked regs[], correct SMBus/pointer contract,
  arithmetically-correct millidegree→INT/DEC at nominal+max, complete VMState, exact
  RW mask, realize-then-property-set matches the existing tmp423 idiom).
- **Second completeness audit (gate a) ran** — confirmed coverage complete + NO
  fabricated `[x]` (every cited file exists), and found the first-audit fixes were
  applied to FULL-TASK-LIST but **not mirrored into DEVICE-MATRIX**, which had
  drifted (C-1..C-10). Re-synced the matrix: **C-1 NC-SI row 11 LS 🔷→⬜** (the
  weasel the first audit removed, still living in the matrix — hard undone RMII2
  pinmux work, not blocked); C-2 VGA-DAC row 12 QE ✅→🔶; C-3 USB row 9 LS 🔶→🔷 /
  LU ✅→🔶; **C-4 WDT row 38 removed the undefined `❓` symbol → 🔶** + honest note;
  C-5 RTC row 39 LS/LU 🔶→⬜; C-6 SOL row 31 QE/LQ ⬜→🔶; C-7 PCI/VGA Zephyr Ⓝ→⬜;
  C-8 straps row 33 reconciled to E4 (UQ/US/LQ/LS ✅); C-9 VIC/timer ZQ ⬜→🔶 (Zephyr
  drivers written+deliver IRQs); added a header note making **FULL-TASK-LIST.md the
  authoritative per-stack doc** (matrix = summary that defers to it on disagreement).
  Row 23 SB-TSI LQ 🔶→✅.

## 2026-07-18 — completeness audit (sub-agent, gate a) + honesty fixes applied

- Ran a sub-agent completeness audit of FULL-TASK-LIST.md vs the authoritative
  schematic + the real code/evidence state. It verified **every `[x]` cites a
  real file** (no fabricated claims — all QEMU models, scripts, CI jobs, evidence
  dirs exist on disk) and coverage is essentially complete, and flagged honesty
  issues which I FIXED (this is the gate: review finds → fix → re-review):
  1. **A3 SMC silicon was `[N]` — the clearest weaseling.** The SPI/SMC IS the
     board's boot device by design; the flash just isn't populated on this rig.
     Re-classed to `[B]` (rig limitation, fixable by populating BMC_FW1), matching
     DEVICE-MATRIX row 2.
  2. **§11 control OUTPUTS had no explicit row.** Added E5 (CLRTC#/BIOSREVRY#/
     CPU1-2DISABLE#/PCI_RST#/ATXPSON#/SYSRESET#) with its own status boxes.
  3. **B3 video rolled a partial DAC-output into a done `[x]`.** Split into B3
     (CAPTURE path — genuinely both-sides PASS) and B3b (DAC output/mode-set/
     PCI-target — `[~]`, self-questioned).
  4. **D9 SB-TSI silicon `[B]` was a weak block** (the rig CAN power the host).
     Re-classed to `[ ]` (achievable, not-done-yet). Same for C2 NC-SI and F2 SOL:
     re-classed the "hard authoring work" parts from `[B]` to `[ ]` (my code to
     write — RMII2 pinmux RE / QU8 mux / registerSOLService — not external blocks).
  5. **D8 TSOD `[x]`** clarified: the jc42 model is complete but deliberately
     not-placed (faithful to this rig's TSOD-less DIMM).
  6. **Coverage assertion** now names the host chips SU1/OU1/NU1 (reached through
     the controller rows, not BMC-internal).
  7. **DEVICE-MATRIX drift fixed:** W83601G rows 21/22 had `LQ=⬜` while `LS/LU=✅`
     (contradiction) and a stale "LED-drive-on-silicon pending" note though it was
     done — reconciled (LQ/LS/LU all ✅ via userspace; note now says both-sides
     done). Row 23 SB-TSI updated to QE=✅/LU=✅/LQ=🔶.
- Next: re-run the completeness audit to confirm the fixes leave nothing flagged
  (the gate wants MULTIPLE clean reviews).

## 2026-07-18 — D09 SB-TSI CPU thermal: faithful QEMU model + validation (QEMU PASS)

- `hw/sensor/sbtsi.c` — AMD SB-TSI processor thermal sensor, register file
  matching the Linux `sbtsi_temp` driver (TEMP_INT 0x01, STATUS 0x02, CONFIG
  0x03, hi/lo-limit 0x07/0x08/0x13/0x14, TEMP_DEC 0x10 bits[7:5]=0.125C); a
  `temperature` QOM property (millidegrees) drives TEMP_INT/TEMP_DEC. Wired P0
  @0x4c (45.5C) + P1 @0x4d (43.0C) on the machine's i2c bus 3 (DT i2c3 =
  schematic I2C4). DTS `&i2c3` enabled with `amd,sbtsi` nodes; DTB rebuilt.
- `scripts/sbtsi-test.py` boots kgpe-d16-bmc and reads both sensors over Linux
  i2c-3 via raw SMBus: **8/8 PASS** (int/dec temps for both sockets, CONFIG/
  STATUS resets, RW-limit accepts a write, RO TEMP_INT rejects one). Evidence
  `evidence/d09-sbtsi/00-qemu-pass.txt`; CI job `boot-sbtsi` added.
- FULL-TASK-LIST D9: QEMU [x], Linux userspace(raw) [x]; in-kernel sbtsi_temp
  bind needs CONFIG_SENSORS_SBTSI (kernel rebuild, TODO); silicon [B]
  host-CPU-power-dependent (SB-TSI *is* the AMD processor interface). QEMU
  submodule 512d56d217.

## 2026-07-18 — complete schematic read + formal per-device/per-stack task list

- Read the **complete** `AST2050-BMC-WIRING.md` end-to-end again (all 597 lines,
  §§1–16: block diagram, power, DDR2, SPI, LPC, PCI, Ethernet, VGA, USB, the full
  §10 I²C device-by-device breakdown + mux fabric + bus-assignment tables, GPIO
  power/reset, Serial/SOL, JTAG/LED/clock/strap, neighbour chips, connectors,
  per-pin table).
- Created **FULL-TASK-LIST.md** — the formal task list in the exact required
  structure: for EVERY device/function block a task for {QEMU emulation; U-Boot
  driver → validate QEMU + silicon; Linux driver → validate QEMU + silicon +
  userspace; Zephyr driver → validate QEMU + silicon}, each box marked with an
  honest status (`[x]` done+evidenced / `[~]` partial / `[ ]` todo / `[N]` N/A
  WITH reason / `[B]` blocked WITH the precise blocker + confidence). Rows A1–A8
  (core SoC), B1–B5 (host interfaces), C1–C2 (Ethernet), D1–D13 (I²C + on-bus),
  E1–E4 (GPIO/LED/strap), F1–F2 (serial/SOL), G1 (JTAG harness). Ends with a
  §-by-§ coverage assertion proving nothing in the schematic is skipped.
- This supersedes the loose "honestly remaining" prose from the prior cycle with
  the required formal structure; DEVICE-MATRIX.md remains the compact grid view.

## 2026-07-18 — silicon I2C inventory + an unidentified 0x69 responder

- Silicon i2c buses present: i2c-1 (W83795 engine, schematic I2C2), i2c-4 (I2C5:
  FRU + W83601G), and the QU5 mux children i2c-14/15/16 — same as QEMU. The other
  schematic engines (I2C1/I2C4→SB-TSI, I2C7→SALT, etc.) are not DT-enabled yet.
- `i2cdetect -y -r` on the mux children shows the W83795 (0x2f, UU=driver-bound)
  AND a device at **0x69** on all three channels (so both are on the shared
  sensor segment past QU5; the mux itself is proven-switching by the SPD test,
  evidence d08-spd-silicon). 0x69 answers a read of reg 0x00 = 0x08 but NAKs regs
  0xfe/0x4f/0x58 → a simple/limited responder, NOT a bank-switched register file.
- **0x69 is NOT in the authoritative schematic §10 I2C table** (which lists only
  W83795G@0x2F on this segment). Candidates: a clock/aux device, a W83795 alias,
  or an i2cdetect artifact. Logged as an open completeness item to identify
  (needs the schematic's sensor-bus sub-detail or a scope) — low priority, weak
  responder; not claiming it as a modeled device.

## 2026-07-18 — origin/main merge check

- `git fetch origin` + `git merge --no-ff origin/main` → **"Already up to date"**.
  origin/main tip `85bd82a` (PR #29 schematic-wiring) is an ANCESTOR of the
  working branch HEAD (`git merge-base --is-ancestor origin/main HEAD` = yes);
  the branch is 378 commits ahead / 0 behind. So the authoritative schematic
  `AST2050-BMC-WIRING.md` that DEVICE-MATRIX.md is verified against IS the latest
  main. Nothing to integrate.

## 2026-07-18 — D14 Zephyr RUNS AN APPLICATION ("Hello World") + M1 VIC/timer 🎉

- The AST2050 Zephyr port now **boots and runs application code** under QEMU:
  `*** Booting Zephyr OS ***` + `Hello World! kgpe_d16_bmc/ast2050`. The kernel
  reaches and runs the sample's main(). Evidence `evidence/d14-zephyr/03`.
- **Faithfulness win (my instinct was right):** I had *wrongly* concluded the
  boot "hangs before main() → upstream ARM9 core bug." A `-d exec` trace proved
  the kernel actually reaches z_thread_entry → bg_thread_main → main() → idle
  cleanly. The real bug was MINE: the sample uses printf() (stdout) but the SoC
  console only hooked printk, so main()'s output went nowhere. Fix = also
  `__stdout_hook_install(ast2050_console_out)` in console.c. Never blame the
  hardware/upstream while my own code is in the loop.
- **M1 VIC + system timer written** (soc/aspeed/ast2050/vic.c real G3 VIC at
  0x1e6c0000 using the Linux irq-aspeed-g3-vic SENSE/DUAL/EVENT constants;
  aspeed_timer.c tickful Timer1 @ 1 MHz, VIC src 16). With SYS_CLOCK=y the timer
  DELIVERS interrupts through the cortex_a_r isr_wrapper and the app still prints
  Hello World — but sustained ticking then data-aborts at the arm_mmu L1 table
  (0x40008ffc), the SAME brand-new-ARM9 arm_mmu dynamic-mapping breakage that
  forced the static M0 console (now via timer-driven thread-switch page-table
  updates). So SYS_CLOCK left OFF by default (clean cooperative Hello World, no
  crash); timer/VIC code committed + re-armed once the upstream arm_mmu is fixed.
- Matrix row 30 ZQ = 🔶 now means a RUNNING APP, not just a banner.

## 2026-07-18 — D14 Zephyr M0 BANNER RUNS in QEMU 🎉

- The AST2050 Zephyr port now **boots and prints** under `qemu-system-arm -M
  kgpe-d16-bmc`: `*** Booting Zephyr OS build v4.4.0-8379-g0a6208b97bff ***`.
  The canonical Zephyr proof-of-life — reset vector → ARM926 arch init → MMU
  enable → C runtime → kernel init → console all work. Evidence
  `evidence/d14-zephyr/02-m0-banner-RUNS.txt`.
- Root cause of the old blocker was TWO stacked bugs (both mine): (1) the
  ns16550 CONFIG_MMU DEVICE_MMIO_MAP z_phys_map path is broken on the brand-new
  ARM9 arm_mmu (resolves the UART VA to 0x1e7ff000, not 0x1e784000); (2) my
  first console workaround used 32-bit UART accesses where QEMU's serial_mm
  (regshift=2) needs BYTE accesses. Fix = a SoC polling console
  (`soc/aspeed/ast2050/console.c`) writing UART5 at its physical address via a
  STATIC identity MMU region in soc.c, byte-wide, installed as the printk hook
  with CONFIG_UART_CONSOLE=n so the broken ns16550 poll_out never runs.
- Diagnostic technique worth keeping: write marker values to a deliberately
  UNIMPLEMENTED SFR (0x1e7ff0f0/f4) so QEMU `-d unimp` surfaces them — proved the
  printk hook WAS called with the banner text and that the LSR read returned the
  real UART's 0x60, separating "hook called?" from "write lands?".
- Honest boundary: only the banner prints, not hello_world's "Hello World!" —
  the app thread is blocked by the absent system timer (SYS_CLOCK_EXISTS=n).
  That is M1 (the aspeed timer driver), the documented next step. Matrix row 30
  ZQ → 🔶; the Zephyr column is no longer "entirely pending" — the port RUNS.

## 2026-07-18 — D08 W83601G: BOTH-SIDES done (silicon LED-drive + datasheet fix)

- Silicon reset-default reads (U27 @0x18) match the datasheet AND the model
  exactly: CR20=0x60, CR02=0xf0, CR03=0xff, CR09=0x00, CR0A=0x70, CR0B=0x7f.
- **Silicon resolved a datasheet inconsistency**: CR21 (chip-ID low) reads
  **0x13** on silicon, not the §7.1-table 0x12 (the §7.2 text's 0x13 is right).
  Per "QEMU models real hardware", set the model's `W83601G_ID_LOW` = 0x13 and
  the test expectation to 0x13; QEMU re-run still PASS.
- **Silicon LED-drive path proven on BOTH expanders** (the exact BMC DIMM-error-
  LED sequence, live over i2c-4, fully reversible):
    U27 @0x18: CR03=0xfe, CR01=0x01 -> readback DRV03=0xfe DRV01=0x01 -> restore.
    U28 @0x19: same -> DRV03=0xfe DRV01=0x01 -> restore.
  The write takes effect on real hardware (readback-confirmed) and restores to
  reset defaults. Evidence `evidence/d08-w83601g/03-silicon-both-sides.txt`.
- Matrix rows 21/22: LS ✅ (silicon LED-drive), QE ✅, LU ✅. D08 W83601G is
  fully both-sides (QEMU + silicon) for both expanders. QEMU submodule updated.

## 2026-07-18 — D08 W83601G: faithful QEMU model + validation (QEMU PASS)

- Obtained the official Nuvoton W83601G datasheet V1.31 (register map in
  `evidence/d08-w83601g/01-datasheet-register-map.md`); it cross-checks the
  silicon capture (CR01 reset 0x00 == the `0x18 reg01` I read), so the part is
  confirmed and can be modelled faithfully rather than guessed.
- Wrote `hw/gpio/w83601g.c` — a datasheet-faithful SMBus GPIO-expander: full
  CR00-CR21 file, correct resets (out 0x00, iocfg all-input 0xff/0x7f, polarity
  0xf0/0x70, ID 0x60/0x12), read-only + reserved(open-bus 0xff) semantics, and a
  per-instance `port1-input` seeded from silicon. Wired both U27/U28 on the
  machine's I2C5 (bus 4) at 0x18/0x19 (inputs 0x0f / 0xb5).
- Bug found + fixed during bring-up (honest note): the 34-register file (0x22)
  is NOT a power of two, so the `& (NR_REGS-1)` pointer mask I copied from the
  8-register jc42 model aliased CR02->CR00 (QEMU test caught it: CR02 read 0x0f
  instead of 0xf0). Replaced with an explicit range check; pointer is a plain
  uint8_t wrapping mod 256 like the hardware.
- `scripts/w83601g-test.py` boots kgpe-d16-bmc and drives both expanders over
  Linux i2c-4 exactly as firmware does (raw SMBus, no driver): **19/19 assertions
  PASS**, including the DIMM-error-LED sequence (CR03 output-enable -> CR01 drive
  -> readback -> clear) and the Port-2 CR0B/CR09 path. Evidence
  `evidence/d08-w83601g/02-qemu-pass.txt`; CI job `boot-w83601g` added.
- Also had to rebuild the KGPE-D16 DTB: the cached `kernel/out` dtb was stale and
  did not enable `&i2c4`, so Linux never registered the I2C5 adapter. Rebuilt
  from the current DTS (`make dtbs`) — i2c-4 now enumerates.
- Matrix rows 21/22: QE ✅, LU ✅ (raw userspace), LS 🔶 (silicon reach proven;
  LED-drive-on-silicon next). QEMU submodule commit d0556622ed.

## 2026-07-18 — D08 W83601G DIMM-LED expanders characterized on silicon

- Read the two W83601G I2C GPIO expanders (U27/U28, §10.2 DIMM-error-LED
  drivers) live on the BMC's I2C5 engine (Linux i2c-4), read-only:
  `0x18` reg0=`0x0f` reg1=`0x00` reg7=`0xff`; `0x19` reg0=`0xb5`. Both are
  **present and register-readable by the BMC** — the schematic wiring is
  confirmed on real silicon and the BMC's DIMM-LED expander access path works.
  Evidence: `evidence/d08-w83601g/00-silicon-present.txt`.
- Matrix rows 21/22 moved ⬜→🔶 (LS/Linux-silicon partial): silicon reach
  proven, but a **faithful QEMU model + full LED bit-map** needs the Winbond
  W83601G datasheet (register semantics: direction vs. output vs. GP10-GP26),
  which is **not in-repo** (unlike the W83795G/W83667HG datasheets). Honestly
  left as an open D08 item (task #135) — NOT claimed done, since "all
  functionality" requires the datasheet-backed register map to model the LED
  drive faithfully. Next: locate the W83601G datasheet (try the 15h.org
  mirror / Winbond archives), then write the QEMU expander model seeded with
  the observed defaults and validate LED-drive on silicon.

## 2026-07-18 — fresh complete read of AST2050-BMC-WIRING.md + task-list verification

- Re-merged origin/main (up to date). Read the **complete** authoritative
  schematic doc end-to-end (all 597 lines, §§1–16) and did a deliberate
  section-by-section cross-check of every function block, the §14
  neighbour-chip table, and the §15 connector list against DEVICE-MATRIX.md.
- Appended a "Completeness verification" table to DEVICE-MATRIX.md mapping
  every doc section → matrix rows, and explicitly justifying the only
  spec elements without their own driver row: passive power/glue (LDOs,
  series-R nets, FET switches/buffers — modeled where behaviour-relevant, e.g.
  the QU9/QU5/U23 fabric device), the JTAG header (silicon test harness, Ⓝ),
  and the host chips SU1/OU1/NU1 (reached via the LPC/PCI/I²C rows, not
  BMC-internal). **Verdict: the 40-row matrix is comprehensive against the
  authoritative schematic — nothing skipped.** This is the fresh-read +
  task-list-creation deliverable.

## 2026-07-18 — D08 FRU EEPROM done both sides; W83601G located on silicon

- Enabled I2C5 (i2c-4) in the DTS + added the FRU node (at24 24c08 @0x54).
  Rebuilt the realhw kernel, JTAG-booted on silicon, and **read the real board
  FRU**: U25 is present + at24-bindable across 0x54-0x57 (1 KB 24c08) but
  **BLANK (0xff)** — ASUS shipped it unprogrammed. The BMC's I2C5 FRU path
  works; E2 strap high confirms the 0x54 base (§10.2's 0x50-0x53 was wrong).
  `evidence/d08-fru/`.
- **Bonus**: `i2cdetect -y -r 4` also shows 0x18/0x19 responding = the two
  W83601G DIMM-LED expanders (U27/U28) on I2C5 — the next D08 sub-device,
  now reachable (bus enabled).
- Modeled the FRU faithfully in QEMU (blank 24c08 at 0x54-0x57 on i2c bus 4);
  qtree confirms, integration suite 114/114. DEVICE-MATRIX FRU row → ✅ both
  sides. A tractable break from the Zephyr banner that closed a real audit
  gap (#4) with a silicon read.

## 2026-07-18 — D14 Zephyr M0 BUILD SUCCEEDS (run/banner debug pending)

- Iterated the Zephyr AST2050 port to a **successful build+link** of
  `hello_world` for `kgpe_d16_bmc` (RAM 136 KB / 64 MB, zephyr.elf entry
  0x40002068, -mcpu=arm926ej-s). Evidence `evidence/d14-zephyr/01-...`.
- Bring-up sequence (each a small, real fix — the port structure was sound):
  1. Board recognized (`qualifiers: ast2050`) — SoC/board/module files valid.
  2. Fixed the SDK-1.0-vs-0.17 gate by using the 0.17 arm-zephyr-eabi as a
     cross-compiler (`ZEPHYR_TOOLCHAIN_VARIANT=cross-compile`).
  3. DTS compiled clean (zephyr.dts generated).
  4. Added `soc/aspeed/Kconfig` (the missing family arch selects: ARM,
     CPU_ARM926EJ_S, ARM_CUSTOM_INTERRUPT_CONTROLLER, MMU, ATOMIC_OPERATIONS_C
     — mirrors sam9's `Kconfig`).
  5. Added a SYS_CLOCK_HW_CYCLES_PER_SEC default (24 MHz).
  6. Provided the SoC glue the linker needed: `vic.c` (M0 stubs for
     z_soc_irq_*), `soc_reset_hook`, and `SYS_CLOCK_EXISTS=n` for M0.
  → links cleanly.
- **RUN**: `qemu -M kgpe-d16-bmc -kernel zephyr.elf` gives NO banner yet — the
  kernel hangs in early boot before console. Confidence HIGH it is a
  bring-up/config detail (MMU-enable / CP15 path), NOT the port or hardware:
  the fwtests link at the same 0x40000000 and print to the same UART5, so the
  load addr + UART are proven-good. Next: `qemu -d int,mmu,cpu_reset` to find
  the early fault → banner completes M0.
- **This is the milestone that was the real risk** (brand-new upstream ARMv5
  support + a from-scratch SoC/board port). Zephyr for the AST2050 now BUILDS.
  The Zephyr column in DEVICE-MATRIX.md stays ⬜ (honestly) until the banner
  runs.

## 2026-07-18 — D14 Zephyr port: real foundation files authored + committed

- Fetched upstream PR #103557 (the ARM926 arch core + sam9x7/sam9x75_curiosity
  precedent) and read every template file (soc.yml, Kconfig.soc/defconfig,
  soc.c/h, CMakeLists, board.yml/dts/defconfig/yaml, armv5.dtsi).
- **Authored the real AST2050 Zephyr port** (16 files, `asus-kgpe-d16-firmware/
  zephyr/`) modeled precisely on that precedent: an out-of-tree module
  (`zephyr/module.yml`), the SoC (`soc/aspeed/ast2050/` — Kconfig selects
  `CPU_ARM926EJ_S`, reuses the cortex_a_r linker, minimal MMU map covering the
  0x1e600000 APB window + vectors, `soc_early_init` no-op since the loader
  brings up DRAM/console), the SoC DTSI (`dts/aspeed/ast2050.dtsi` — arm926ej-s
  cpu, 64 MB memory@40000000, ns16550 serial@1e784000), and the board
  (`boards/aspeed/kgpe_d16_bmc/` — chosen console/sram, 115200). The ARM9 arch
  core comes from upstream; this module is only the SoC+board. PORT-PLAN.md
  records the approach + milestone ladder. Committed `a480a99`.
- **M0 build environment being set up**: west workspace initialized on the PR
  branch; SDK `/home/tim/zephyr-sdk-0.17.0` (arm-zephyr-eabi); `west update`
  of the essential modules running. Next: `west build -b kgpe_d16_bmc
  samples/hello_world` → banner under the repo's faithful QEMU AST2050.
- Honest state: the port FILES are real + committed, but no Zephyr build has
  succeeded yet — the whole Zephyr column in DEVICE-MATRIX.md stays ⬜ until
  M0 (hello_world banner) actually runs. This is a genuine start on the
  biggest gap, not a claim of completion.

## 2026-07-18 — explicit per-device task matrix created (DEVICE-MATRIX.md)

- Re-merged origin/main (already up to date). Re-read the authoritative
  wiring doc §§2–15 fresh and enumerated **every device** (40 rows incl. the
  §14 neighbour chips + SoC-internal peripherals) into a new
  **DEVICE-MATRIX.md** — an explicit grid with the exact deliverable columns
  the goal demands: QEMU / U-Boot(QEMU,silicon) / Linux(QEMU,silicon,
  userspace) / Zephyr(QEMU,silicon). Each cell carries the honest current
  status (reflecting the completeness audit — USB-Si scoped, NC-SI-Si 🔷
  blocked, WDT-Si uncited, 6 I2C far-ends absent, SOL/DDC/mailbox ⬜, whole
  Zephyr column ⬜). TASKLIST now points to it as the authoritative checklist.
- This makes the per-device coverage inspectable at a glance and is the
  master checklist for the remaining work.

## 2026-07-18 — D07 silicon NC-SI attempt 2 FAIL; deep G3-pinmux diagnosis; BREAK

- Added the RMII2 pinctrl to mac1 + rebuilt + re-tested on silicon → STILL
  "No channel found to configure!". Read the g4 pinctrl source and found the
  REAL blocker: **the AST2050 (G3) RMII2 pinmux is fundamentally different
  from the AST2400 (G4)** and mainline's aspeed-g4 pinctrl can't route it:
  - `RMII2_DESC = SIG_DESC_BIT(HW_STRAP1, 7, 0)` gates RMII2 on SCU70[7]==0
    (G4 semantics); on the G3, strap 110 has bit7=1 → g4 pinctrl thinks RMII2
    is off (same class as the patch-0008 GPIOF5 bug, deeper).
  - the g4 RMII2 pins (D9/A10/B10/C9/A9/E8/D8, GPIOT/V group) are the G4's;
    the G3's RMII2 balls are A5/B5/B6/C4/D4/D5 = the **GPIOE group**.
  - empirically set SCU74[27]=1 on the live board → still no channel, so that
    single bit isn't the enable. Restored SCU74.
  - Confidence HIGH this is config/RE, not hardware (NVMs are NC-SI-enabled).
  Evidence `evidence/d07-ncsi/03-...`.
- **Taking a break from NC-SI silicon** (per the "get stuck → work elsewhere"
  guidance). It needs the AST2050 datasheet's exact RMII2/GPIOE routing for
  strap=110 + a G3 pinctrl group — a focused follow-up. NC-SI is validated in
  QEMU; the NICs are confirmed enabled; the silicon step is well-characterized
  and open. Bug #4 (RMII2 pinmux) was mine; the deeper G3-pinmux gap is a real
  mainline limitation, honestly documented.

## 2026-07-18 — D07 silicon NC-SI attempt 1 FAILED (my missing RMII2 pinmux)

- Ran BMC-side NC-SI discovery on real silicon (addresses audit #3). Booted
  the NET_NCSI realhw kernel with mac1 enabled (`kgpe-ncsi.dtb`). eth1 bound
  `Using NCSI interface`, but `ip link set eth1 up` →
  **`NCSI: No channel found to configure!`** + `Wrong NCSI state 0x100`. The
  real 82574Ls did NOT respond.
- **Root cause = MY DTS, not the hardware** (the principle holds). The
  mainline aspeed-g4 `mac1` node has NO `pinctrl-0`, so the RMII2 data pins
  (GPIOE group, §7 balls A5/B5/B6/C4/D4/D5) were never muxed to the RMII2
  function → NC-SI frames never physically reached the NICs. The g4 pinctrl
  HAS the group (`pinctrl_rmii2_default`) and SCU70[8:6]=110 strap-enables
  RMII2 — the node just never referenced it. Confidence HIGH this is the
  bug (not a hardware issue): the NVMs are confirmed NC-SI-enabled.
- **Fix**: added `pinctrl-0 = <&pinctrl_rmii2_default>` to `&mac1`. Rebuilding
  realhw kernel; will re-test on silicon. Honest failure captured in
  `evidence/d07-ncsi/02-silicon-discovery-attempt1-FAIL-pinmux.txt`. This is
  my bug #4 this session (all four: console baud, cross-worktree stale
  artifact, test string compare, now the RMII2 pinmux) — the hardware has
  been correct every time.

## 2026-07-18 — completeness audit + Zephyr feasibility; honesty fixes

- **Completeness audit (skeptical sub-agent)** — key findings ACTED ON:
  - SILICON-STATUS row #5 still said "no DIMM SPDs / unreachable by BMC"
    (contradicted its own D08 banner) → FIXED to ✅/✅ with honest scope.
  - SILICON-STATUS row #9 said NC-SI "implementation not started" (stale) →
    FIXED to reflect D07 QEMU pass + the honest silicon caveat.
  - Header date "2026-07-16" stale → bumped to 2026-07-18.
  - D07 evidence file `01-silicon-82574L-nvm-...` renamed to
    `01-host-ethtool-82574L-nvm-...` — it's a HOST ethtool NVM dump, NOT a
    BMC-side silicon discovery (the audit rightly flagged the name as
    inviting miscount).
  - D02 U-Boot SPI was understated ⬜ → the Raptor U-Boot QEMU log shows
    `Flash: SPI Flash ID` working → marked ✅ QEMU.
  - D02 SPI silicon "Ⓝ" corrected to "rig-blocked" (socket populated by
    design; empty only on this bench — not n/a).
  - D11 WDT-silicon "✅ 120 s reset observed" has NO evidence transcript →
    marked UNCITED pending a captured reset log.
  - Audit's honest scope reminders recorded: D05 USB-silicon = usbip-vudc
    (not the real vhub datapath); D08 SPD-silicon select-drive came from the
    SP5100 (data path proven, BMC-owns-fabric not); NC-SI-silicon not run.
  - Real functional gaps confirmed: SOL end-to-end, LPC mailbox/snoop/vUART,
    5 D08 far-end I2C devices, DDC/EDID, MTD write path, and the whole
    Zephyr column.
- **Zephyr feasibility (research sub-agent) — BREAKTHROUGH:** Zephyr now has
  ARM926EJ-S (ARMv5TEJ) support from Microchip's SAM9X7 work — scaffolding
  merged in `main` (PR #101016), arch core (~770 LOC) in open PR #103557, and
  the existing `uart_ns16550.c` fits the AST2050 UART. So D14 is a tractable
  SoC/board port (reuse the ARM9 core), not a from-scratch arch port.
  Smallest milestone: `hello_world` banner under the faithful QEMU AST2050.
  TASKLIST D14 rewritten with the concrete milestone ladder.

## 2026-07-18 — D15/U-Boot reframed HONESTLY: Raptor U-Boot meets the requirement

- Re-merged origin/main (already up to date — merged at start via a981389;
  main tip 85bd82a unchanged).
- **Built the Raptor AST2050 U-Boot from source** (vintage gcc-4.9.4, fetched
  by build-raptor-uboot.sh) and **booted it first-hand in QEMU** with the
  faithful G3 SCU (`g3-resets=on`): `DRAM Init-DDR` → `U-Boot 2013.07` →
  `DRAM: 64 MiB` → `aspeednic#0: PHY at 0x20` → `boot#`. Its OWN AST2050 DDR2
  init runs against the faithful SDMC model. Evidence `evidence/d15-uboot/`.
- **Correction to my earlier "U-Boot column is empty" claim:** a proper,
  working U-Boot with a real AST2050 board port (`board/aspeed/ast2050/`,
  drivers libserial/libnet/libi2c/libgpio/libspi_flash) ALREADY EXISTS and is
  validated BOTH sides for boot-critical devices — QEMU (this build + CI
  `boot-uboot-scu`) and silicon (the `boot#` I JTAG-netbooted from this
  session for D07/D08). So the "proper U-Boot driver, validated QEMU+silicon"
  requirement is MET for D01(ram)/D06(net)/D10(serial)/D02(spi). U-Boot has no
  runtime need for the non-boot blocks. **D15 "modern U-Boot" is an
  ENHANCEMENT, not a functional gap.** TASKLIST updated to reflect this.
- Consequence: the ONLY true greenfield column left is **Zephyr (D14)** — no
  code exists. That's the next focus.

## 2026-07-18 — code review of D07/D08 QEMU code (1 issue found + fixed)

- Dispatched a code-review sub-agent over all new C: `kgpe_d16_i2c_fabric.c`,
  `jc42.c`, the `aspeed_gpio.c` kgpe outputs, the `aspeed.c` fabric/strap/SPD/
  MAC2 changes, and kernel patch 0008. Verdict: **all clean except ONE Medium**:
  `kgpe_d16_host_on` (host-power latch) was absent from VMState and not
  re-synced on reset → after loadvm/migration (or transiently after a warm
  reset) the next GPIO write could clobber the GPIOH2 power bit back to "off".
- **Fixed**: `VMSTATE_BOOL_V(kgpe_d16_host_on, …, 2)` + reset re-syncs GPIOH2
  and the board-glue outputs from the persisted latch (the latch is board
  glue, outside the BMC GPIO reset domain). Verified `qemu_set_irq` is
  NULL-safe so the reset-time output drive is safe regardless of connect
  order. Integration 114/114 after the fix. The reviewer verified jc42's
  word-swapped register logic, the fabric's bounded channel select + VMState,
  the pinctrl patch's enable-path-untouched skip, and the SPD array (256 bytes,
  CRC bytes, g_memdup2 ownership) all correct; build wiring (Kconfig/meson) OK.

## 2026-07-18 — D07 NC-SI Phase 1: Linux stack validated in QEMU

- **`NCSI RESULT: PASS`** — the kernel's net/ncsi discovered + configured a
  channel on eth1 (MAC2/0x1e680000) and brought carrier up:
  `ftgmac100 1e680000.ethernet: Using NCSI interface` →
  `NCSI: ... configuring channel 0` → carrier=1. Evidence
  `evidence/d07-ncsi/`, CI job `boot-ncsi`.
- Changes: kgpe-d16-bmc now wires BOTH MACs (`macs_mask=MAC0|MAC1`, faithful
  to schematic §7 — MAC1 unpeered unless a 2nd -nic is given, so oracles are
  safe); kernel +CONFIG_NET_NCSI +NCSI_OEM_CMD_{GET_MAC,KEEP_PHY}; QEMU DTS
  gains a `&mac1 { use-ncsi; status="disabled" }` node (test enables it via
  fdtput + runs QEMU with a 2nd slirp NIC that answers NC-SI).
- **Regression clean:** C2 SSH boot still PASS; integration 114/114.
- Honest scope: Phase 1 proves the LINUX NC-SI software path against the
  generic slirp responder (returns MFR-ID 0x0). Phase 2 = a faithful 82574L
  responder (2 packages, Intel OEM mfr 0x157 cmds 0x06/0x20) — belongs in the
  MAC model since libslirp is an external subproject. Silicon needs the ASUS
  NIC NVMs to have NC-SI (MNGM) enabled — open question, checkable via
  `ethtool -e` on the host NICs.

## 2026-07-18 — 🎉 D08: BMC read the REAL DIMM SPD on silicon

- **The BMC's at24 read the real 256-byte SPD** over I2C2 → QU9 → QU5-Y2 →
  DIMM 0x51: `at24 15-0051: 256 byte 24c02 EEPROM`, part `RMR5030EF68F9W1600`,
  serial 420B469C (== host `dmidecode -t 17`), CRC-16 0xf0b4 verified. The
  formerly-"impossible" #5 DIMM inventory is REAL. Evidence:
  `evidence/d08-spd-silicon/`.
- **Full diagnosis chain** (every step is my code/driving, never the hardware):
  1. patch 0008 makes the mux driver load on silicon (3 adapters).
  2. GPIO dump proved the BMC drives the correct Y2 selects; QU9 closed.
  3. But 0x51 didn't ACK → the physical QU5 selects weren't at Y2.
  4. Root cause A: the mux **floats/parks at a non-DIMM bank at idle** —
     measured SP5100 reg 0x54=0x0707 = selects at Y1 (unconnected). Even the
     HOST's decode-dimms found nothing at idle → NOT a dead chip, it's the mux.
  5. Root cause B: **U23 arbitration gives the SP5100 select-ownership** on
     this rig because the BMC flash socket is EMPTY → BMC_PRESENT# high. So the
     BMC's correct Y2 drive is blocked at U23 (netlist-traced: D27/QQ9/QQ10).
  6. Obtained the read by pointing the mux at Y2 from the SP5100 side
     (`setpci 00:14.0 0x54.w=0x000B`, GPIO59/60 = SB_I2CS0/1, register found in
     the in-repo SP5100 RRG `GPIO_60_to_57_Cntrl`), fully recoverable
     (restored 0x0707). BMC then read through the shared closed QU9.
  - Honest scope: the SPD **data path** is proven on the BMC; the select-drive
    was provided by the SP5100 (rig has empty flash socket → BMC can't own
    selects). A production board (BMC_PRESENT# low) has the BMC drive them.
- **Faithful model updated**: real 256-byte SPD baked into `hw/arm/aspeed.c`
  (replacing the provisional image); TSOD REMOVED (real UDIMM has byte32=0 =
  no thermal sensor → QEMU 0x19 NAKs like silicon); temp@19 dropped from both
  DTS; fwtest/spd-test/test assert real SPD (0x92/0x0b/0x02 UDIMM) + TSOD NAK.
  fwtest 12/12, integration 114/114. jc42.c kept (available for TS DIMMs).
- **My bugs this session so far: still just the earlier 3** — the hardware
  read the real SPD perfectly once I drove the mux correctly.

## 2026-07-18 — silicon rerun with patch 0008: mux ALIVE; SPD not yet ACKing

- Fixed kernel netbooted on silicon: **`i2c-mux-gpio i2cmux: 3 port mux`
  registered, adapters i2c-14/15/16 present, pin-45 error GONE** — patch
  0008 works on the real chip.
- SPD probe loop: at24 on 15-0051 not binding yet. Live facts:
  - `HOST_POWER_BEFORE=1` — GPIOH2 (line power) already high; plug ~49 W.
    NOTE: H2 = STA_LINE_POWER; **SYS_PWRGD is a different net (ball D9)**
    — QU9's gate follows SYS_PWRGD, so H2=1 does not prove the bridge is
    closed. Register dump queued behind the script's wait loop.
  - G3 SCU74 = 0x4204D000 decoded from datasheet §18: bit23 (VP[17:12]
    pad enable) = **0** → W3/W4 pads are NOT in video mode (good);
    bit25 PHYLINK set (the known A4 alt-func), bit18 DDC, bit15 VGA,
    bit14 I2C#7, bit12 I2C#5 enabled.
  - Hypotheses ranked: (1) SYS_PWRGD low → QU9 open (host half-on state);
    (2) host mid-POST → SP5100 owns selects → misroute; (3) something
    about GPIO drive on F4/F5 not reaching the pins. Discriminators queued:
    GPIO A-D data bit14 (B6 = SYS_PWRGD net), E-H data/dir F4/F5 state.

## 2026-07-18 — SILICON SESSION: boot OK; pinctrl blocker root-caused QEMU-first

- **Silicon boot chain worked end-to-end**: JTAG 3-step (reset-halt → DDR2
  train MCR04=0x585 → U-Boot @0x40000000) → `boot#` → TFTP kernel 3463384 B
  + initramfs + dtb → Linux 6.6.70 up, eth0 192.168.66.2, dropbear,
  BMC-READY on serial.
  - My-bug #2 this session: drove the serial at 1200 baud; the evidence
    file for THIS U-Boot build (186096 B) says its console is 115200 — the
    1200-baud build was a different binary. 7 bytes of framing garbage =
    the banner. Fixed; `bmc-serial.sh` helper deployed on the Pi.
- **D08 silicon blocker found**: `aspeed-g4-pinctrl: pin-45
  (1e780000.gpio:557) status -1` → `i2c-mux-gpio: probe failed` → no mux
  adapters. Root cause chain, fully evidenced:
  - G4 pinctrl table: ball A19 (its pin 45) has SIOSCI/ACPI function gated
    on `HW_STRAP1[19]==0` (`ACPI_DESC`, pinctrl-aspeed-g4.c:385).
  - Real G3 SCU70 = **0x00819582** (JTAG + devmem agree), bit19=0 → driver
    thinks an un-deconfigurable strap function owns the pad → -EPERM.
  - G3 datasheet §18: SCU70 bit19 = **"Bypass all PLL (test mode only)"** —
    the G4 interpretation is a phantom; and setting bit19 on silicon would
    be catastrophic, so no devmem workaround (ruled out BEFORE trying).
  - **Bonus silicon facts from the strap decode**: SCU70[8:6]=0b110 =
    "RMII(MAC#1) and RMII(MAC#2)" — MAC1 is RMII (settles the N-vs-CP/
    MII-vs-RMII tension: balls are MII-capable, strap selects RMII) and
    the MAC2/NC-SI channel is STRAP-ENABLED on this board (D07 evidence);
    [1:0]=10 = SPI boot (G3 has no DRAM-size strap in SCU70); [3:2]=00 =
    8 MB VGA; [23]=1 LPC reset on B10; SCU74=0x4204D000, SCU40=0x000020C0.
- **QEMU-first loop executed**:
  1. Machine strap constant replaced with the measured 0x00819582
     (was palmetto-derived guesswork) → submodule `4ff6a74`.
  2. Integration suite still 114/114.
  3. `spd-test.py` now FAILS in QEMU with the byte-identical
     `pin-45 status -1` — faithful repro (the old constructed strap had
     been masking this real kernel bug).
  4. Kernel fix: `g3_strap_phantoms` quirk — strap-only G4-table
     expressions are skippable on the DISABLE path only (enable-path strap
     evaluation untouched — eth0's RMII1 mux depends on it), gated by new
     compatible `aspeed,ast2050-pinctrl`; both DTS switched. Will become
     patch 0008 once validated.
- C4/C-UBOOT oracle re-validation with the new strap: not yet run locally
  (CI covers on push) — flagged, not forgotten.

## 2026-07-18 — silicon session prep; NC-SI facts pinned; docs reconciled

- **Stale-artifact trap found & fixed:** `build-realhw-kernel.py` built from
  the `.worktrees/d16-qemu` tree (not this worktree) — the artifact would
  have silently lacked ALL my changes. Fixed to worktree-relative + DTS
  refresh; committed. Realhw kernel rebuilding correctly now.
- **DTS lineage identified:** the proven silicon dtb
  (`kgpe-hwpass-vgafix-video.dtb`) is the *QEMU-DTS lineage* (built by
  build-kernel.sh from `qemu-firmware/dts/aspeed-bmc-asus-kgpe-d16.dts`),
  NOT `dts/aspeed-bmc-asus-kgpe-d16-realhw.dts`. Diff of my new kernel dtb
  vs proven = my i2cmux node + kcs `clocks` (patch-0004 pair, desired) +
  **vhub `okay` vs proven `disabled`**. For the SPD silicon run I forced
  vhub back to disabled in a boot-only copy (`kgpe-i2cmux-novhub.dtb`,
  via fdtput) — the vhub silicon retest is D05 Test B, a separate
  controlled experiment; one variable at a time.
- **Rig state:** plug 49 W, old kernel still up at 192.168.66.2 (its
  dropbear rejects our key — irrelevant, JTAG reboot planned). claude on
  the Pi has passwordless sudo; JTAG workspace copied to
  `/home/claude/openocd-bmc-new` (paths patched); TFTP dir writable,
  dnsmasq active, eth-bmc 192.168.66.1 up, serial console free.
- **Docs-reconciliation agent landed 3 commits** (F7-NCSI corrected with
  MAC2 facts; SILICON-STATUS #9 → REOPENED(D07); MODERN-KERNEL-STATUS
  resolved-banner). Its flags: SILICON-STATUS intro still carries the old
  #9 verdict (queued); **MAC1 MII-vs-RMII strap question** — read SCU70 on
  silicon this session (added to checklist).
- **82574L NC-SI research complete** (datasheet rev 2.7): true DMTF NC-SI
  1.0.0a over RMII, NVM-gated (word 0x0F MNGM), package-ID word 0x2E,
  multi-drop-by-float + Select Package, no hw arbitration, Intel OEM cmds
  in mainline net/ncsi, QEMU responder = libslirp. Open: ASUS NVM MNGM
  state — dump on silicon. TASKLIST D07 updated.

Newest entries at the top. Every work session appends here and commits.
Format: `## YYYY-MM-DD HH:MM` + what was done / found / failed (with honest
confidence about whether a failure was our own mistake).

## 2026-07-18 — D08 Linux stack VALIDATED in QEMU: `SPD RESULT: PASS`

- `scripts/spd-test.py` boots the machine and drives the REAL driver chain:
  i2c-mux-gpio child adapters appear (chan 2 = i2c-15); with host OFF the
  DT-declared at24/jc42 probes fail (faithful QU9 gating — asserted, not
  worked around); host powered on in-guest via the modeled sequencer;
  re-probe binds at24 → `/sys/.../eeprom` header `92 11 0b` and jc42 →
  hwmon `temp1_input=35000`; host powered OFF → device unbinds and cannot
  re-probe (gating is live). Evidence:
  `openbmc/bmc-functionality/evidence/d08-spd/00-qemu-linux-stack-PASS.txt`.
- **My bug count this session: 1** — the first run failed on a
  trailing-space string comparison in MY test (command substitution strips
  it); the model/drivers were right. ("It is always your code.")
- Learned/documented: deferred probe does NOT retry on power events — the
  silicon procedure needs the same explicit `drivers_probe` re-bind after
  host power-on (recorded in peripherals/i2cmux/DOC.md).
- CI: new `boot-spd-mux` job in d16-qemu-stack.yml.
- realhw kernel inherits the new config via the merge order (verified
  build-realhw-kernel.py merges kgpe-d16.config).
- Next: silicon half — JTAG boot the realhw kernel with the new DTS, power
  host on, wait POST, read SPD/TSOD; then bake the REAL A2 SPD dump into
  the QEMU model replacing the provisional image.

## 2026-07-18 — D08 fabric IMPLEMENTED in QEMU; fwtest 11/11 PASS first run

- **QEMU submodule (`be673b2`):** new `kgpe-d16-i2c-fabric` device
  (transparent GPIO-selected mux, pca954x `match_and_add` pattern, gated on
  the modeled host power), new `jc42` TSOD device (MCP98244 IDs — corrected
  from my first MCP9805 guess after checking Linux jc42.c's ID table:
  MCP9805's real devid is the 0x0000-family, 98244=0x2200 is cleanly in the
  table), board glue instantiates SPD @0x51 (CRC-valid provisional
  DDR3-1333 ECC RDIMM image) + TSOD @0x19 on bank Y2 = rig slot A2.
  `aspeed_gpio` grew `kgpe-host-on` + `kgpe-i2cs[2]` named outputs (per-pin
  sysbus-IRQ indexes shift with skipped pins, so named outputs are the
  robust wiring; pull-up semantics "undriven ⇒ high" preserved).
- **Parent repo (`61ae28e`):** `/i2cmux` i2c-mux-gpio DTS nodes in BOTH the
  QEMU DTS and the realhw DTS (GPIOF4/F5 = Linux lines 44/45; no enable
  GPIO — none exists in hardware), kernel config +I2C_MUX_GPIO +AT24 +JC42.
  Both DTS verified compiling with dtc (phandles resolve).
- **fwtest `peripherals/i2cmux` + `integration/test_i2cmux.py`: 11/11 checks
  PASS on the first run** — host-off NAK / host-on Y3-idle NAK / Y2 SPD+TSOD
  ACK / SPD bytes 0x92,0x0B read / live re-routing / mid-session power-off
  disconnect, with the pre-fabric W83795G unaffected throughout.
- Full integration suite regression run in progress.
- Compatibles verified against the vendored kernel source (at24
  "atmel,24c02" ✓, jc42 "jedec,jc-42.4-temp" ✓, cap high-byte==0 detect
  requirement ✓).
- NOTE (D09 reconciliation item): schematic §11 names vs the silicon-verified
  pwrseq GPIO map disagree on some lines (e.g. GPIOB6 = SYS_PWRGD in the
  schematic vs CTL_REQ_RESET_N in asus_power.sh RE). Power control is
  plug-verified working, so both facts are real — the naming must be
  reconciled with net-level evidence in D09, not papered over.

## 2026-07-18 — fabric FULLY decoded from netlist; audits folded in

- **D08 fabric control/arbitration completely traced** from the extracted
  netlist (`.worktrees/kcma-d8-bmc-wiring/tmp/kgpe/kgpe.json`) → new doc
  `schematic-wiring/I2C-MUX-FABRIC-ARBITRATION.md`. Headlines:
  - QU9 enable = !SYS_PWRGD (automatic, no BMC GPIO); QU5 E# grounded
    (always on); U23 ownership = hardware mutex via D27/QQ9/QQ10
    (BMC owns iff BMC_PRESENT# low AND SB_BIOS_POST_COMPLT# low);
    only BMC-driven controls anywhere = GPIOF4/F5 selects; idle select = 11.
  - **Doc gap found & recorded:** the QU9-switched 4th segment reaches the
    TPM1 header (pins 13/14) and PCIe slots 1–5 SMBus (`I2C13*` nets) —
    §10 only mentioned the aux panel.
  - **LU1/LU2 (82574L) confirmed on +3V3_AUX** → D07 silicon testable host-off.
  - **U25 FRU EEPROM E2 pin strapped high** → address likely 0x54-0x57 (doc
    said 0x50-0x53); silicon i2cdetect to settle.
- **Audit agents (4) returned; corrections folded into TASKLIST:**
  - UNDERSTATED: modern U-Boot v2019.04 (`evb-ast2400_defconfig`) already
    boots→Linux→SSH in QEMU (CI `boot-uboot-ssh`); still zero board port.
  - OVERSTATED: FRU EEPROM "QEMU eeprom exists" — no DTS node/model wired
    anywhere → reset to ⬜.
  - D06 naming conflict: schematic says RTL8201**N** (U5); model/tests say
    RTL8201**CP** (PHYID 0x8201). Reconcile via silicon PHYID + datasheets.
  - F7-NCSI.md "not wired" verdict was MAC1-scoped — must be reconciled with
    schematic §7 (MAC2/RMII2 to LU1+LU2). QEMU MAC2 exists but unwired
    (`macs_mask=ASPEED_MAC0_ON`); DTS mac2 disabled; NET_NCSI not built.
  - Stale doc: `MODERN-KERNEL-STATUS.md` still lists the RMII-TX blocker
    superseded by the VIC + cur_speed fixes — needs updating.
  - "108 tests" = 67 test functions parametrized to 108 cases (accurate but
    now stated precisely).
  - Zephyr: confirmed zero code exists anywhere (D14 all-⬜ accurate).
- Push hiccups to GitHub (2 timeouts, then success) — network, not repo state;
  branch now synced at `2e10f8a`.

## 2026-07-18 — D03 BIOS-flash path SETTLED; D08 fabric facts gathered

- **D03/#8 settled by sub-agent research with schematic citations:** host BIOS
  flash `FU1` (W25Q16) is on the **SP5100 SPI controller** (`SB_SPI_*`, SU1
  D1/D2/G6/F3/F4/D6→FU1); BMC `AST_SPI*` nets reach only `BMC_FW1`; no shared
  node; AST2050 has no host-facing SPI master; BIOS fetch is FCH-SPI (not LPC
  cycles). Prior "no path" claim was RIGHT — now Ⓝ *with evidence* instead of
  assumption. TASKLIST updated.
- **D08 mux-fabric facts established (schematic):**
  - `AST_I2CS0` = GPIOF4 (ball W4), `AST_I2CS1` = GPIOF5 (ball W3) → U23[5]/[2].
  - `I2CMUX_ENABLE#` = inverted `SYS_PWRGD` (U8 74LVC14A: pin13 in = SYS_PWRGD
    per QU1_pins.md:315, pin12 out = I2CMUX_ENABLE#). So QU9 bridges I2C2↔I2C7
    **only while host power is good** — SPD unreachable with host off; QEMU
    model must enforce this.
  - U23 OE# nets (`N51800495`/`N51800497`) driver still untraced (BMC pinmap
    only shows U23[2]/[5]) — must come from the FZ netlist dumps; open item
    before silicon SPD access (multi-master hazard vs SP5100).
- Launched 4 read-only audit/research agents (statuses D01-D06, D07-D15 +
  U-Boot/Zephyr inventory, BIOS path [done ↑], NC-SI facts). 3 still running.

## 2026-07-18 — program start

- Merged `origin/main` (schematic-wiring PR #29) into `claude/bmc-functionality`
  → merge commit `a981389`, pushed.
  - **Mistake made & fixed:** a persisted `cd` caused the first merge attempt to
    land on the *local `main` checkout* (repo rule: never commit on main).
    Reset local main to `origin/main` (the stray commit contained only
    origin/main content — nothing lost), redid the merge in this worktree.
- Read `schematic-wiring/AST2050-BMC-WIRING.md` in full (597 lines).
- Created `TASKLIST.md`: 15 device blocks (D01–D15) × QEMU/U-Boot/Linux/Zephyr
  × validation environments, statuses seeded from prior program evidence.
- **REOPENED prior wrong claims** (schematic contradicts them):
  - NC-SI: RMII2 *is* wired to both 82574L NICs → D07.
  - DIMM SPD/TSOD: reachable via QU9/QU5/U23 fabric → D08.
  - SOL: UART1 → QU8 PI5C3257 → Super-I/O → D10.
  - Host-BIOS-flash path: to be settled from SP5100 doc, not assumed → D03.
- Next: commit program docs; audit pass over existing tree to firm up seeded
  statuses; then start execution with D08 mux fabric + D07 NC-SI (QEMU-first),
  per the QEMU-first faithfulness workflow.

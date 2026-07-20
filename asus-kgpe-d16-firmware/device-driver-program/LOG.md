# Device-driver program — running log

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

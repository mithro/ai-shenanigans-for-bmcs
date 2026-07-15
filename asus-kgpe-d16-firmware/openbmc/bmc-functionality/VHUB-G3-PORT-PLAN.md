# Porting `aspeed-vhub` to the AST2050 (G3) — actionable plan

Goal: make the BMC present a USB device to the x86 host on real silicon (features
2 "connect USB devices" + 3b "send keyboard events" — the vKVM/virtual-media
datapath). This is the single largest remaining silicon gap. Analysis below is
from a driver+datasheet review (2026-07-15); file:line refer to
`asus-kgpe-d16-firmware/qemu-firmware/kernel/linux/drivers/usb/gadget/udc/aspeed-vhub/`,
page cites to `dell-c410x-firmware/datasheets/AST2050_AST1100_A3_Datasheet_V1.05.pdf`
(USB = §10 p.99, §15 p.154-178) and `asus-kgpe-d16-firmware/qemu-model/peripherals/usb/DATASHEET-USB.md`.

## The hang is NOT a stuck poll
`ast_vhub_probe` (core.c:294-413) is straight-line — there is no `readl_poll`/
`while` busy-wait in the probe path. On silicon the whole SoC locks up (console +
network dead — `evidence/real-hw-consolidated/usb-vhub-silicon-boundary.txt`).
That is an **IRQ livelock**, triggered in `ast_vhub_init_hw` (core.c:168-254).

## Register offsets are IDENTICAL G3 vs G4
HUB/DEV/EPP offsets match the datasheet exactly (that is why the driver binds at
all). The differences are **semantic**, three of them:

1. **`CTRL`[31] `VHUB_CTRL_PHY_CLK` is READ-ONLY on the G3** — a PHY-clock-ready
   status mirroring SCU0C[14] (datasheet p.156-157). The driver *writes* it
   (core.c:175,198) expecting to enable the PHY; on the G3 that is a no-op, so the
   PHY only runs if the clock gate is already on.
2. **`ISR`[18] `VHUB_IRQ_USB_CMD_DEADLOCK` is a fatal, level-triggered condition**
   (clock stopped / PHY failed / stuck in Suspend, datasheet §15.3.2 p.159-160).
   `ast_vhub_irq` (core.c:93-166) W1C-acks the whole ISR (core.c:109) but has **no
   corrective branch for bit 18**, so if the underlying condition persists the
   level line never drops → CPU spins 100% in the ISR → console+network die.
3. **The 21-endpoint pool extends to 0x34F** (EPP#16-#20 at 0x300-0x34F, p.155),
   but the DT `reg` is `<0x1e6a0000 0x300>` (aspeed-g4.dtsi:172) → `ast_vhub_alloc_epn`
   (epn.c:831) computes register addresses past the ioremap for the 17th+ generic
   EP. Runtime fault (heavy gadget use), not the probe hang.

The **count** difference (7 ports/21 EP vs 5/15) is already DT-driven and correct
(core.c:306-328, DTS sets `<7>`/`<21>`) — not a bug.

## Trigger
`ast_vhub_init_hw` tail (core.c:242-253): assert `UPSTREAM_CONNECT` then unmask
IER, with the handler already installed and INT#5 unmasked. Connecting into a
not-yet-ready G3 PHY sets ISR[18] → livelock (item 2).

## Minimal fixes (probe-survival first)
1. **PHY-ready gate** — before `UPSTREAM_CONNECT`, bounded-wait for `CTRL`[31] to
   read set (don't rely on *writing* it). On the G4 it reads back what we wrote
   (immediate); on the G3 it reflects SCU0C[14]. Prevents connecting into a dead PHY.
2. **De-livelock the deadlock IRQ** — in `ast_vhub_irq`, on `VHUB_IRQ_USB_CMD_DEADLOCK`
   drop `UPSTREAM_CONNECT` (quiesce the bus) + rate-limited warn, so a bad PHY state
   can't wedge the CPU (safety net even after fix 1).
3. **Widen the register window** — DT `reg = <0x1e6a0000 0x350>` + QEMU
   `ASPEED_UDC_AST2050_NR_REGS >= 0x350/4` so EPP#16-#20 are mapped.
4. **Clean G3 binding** — add `"aspeed,ast2050-usb-vhub"` to `ast_vhub_dt_ids`
   (core.c:415) + a per-SoC config (default 7/21, the PHY-ready + deadlock handling)
   so the G3 path is explicit instead of borrowing the ast2400 compatible.

## QEMU faithfulness (so the fix is testable without silicon)
The model `hw/misc/aspeed_udc_ast2050.c` is a passive RW `uint32_t[]` (never raises
IRQ#5, never sets ISR[18]) — which is why the *unfixed* driver "binds cleanly" in
QEMU yet hangs on silicon. To reproduce silicon and regression-test the port:
- Make `CTRL`[31] read-only, driven by the SCU0C[14] USB clock gate (PHY-ready).
- On `UPSTREAM_CONNECT` while the PHY clock is off, set ISR[18] and raise INT#5
  (level) — so the unfixed driver livelocks in QEMU too, and the PHY-ready-gated
  driver does not.
- Grow `NR_REGS` to cover 0x34F.

## Status (2026-07-15)
- **Analysis:** complete + cited (above).
- **Driver patch:** fixes 1 (PHY-ready gate), 2 (de-livelock on ISR[18]), and 4
  (explicit `ast2050-usb-vhub` compatible) implemented in
  `kernel/patches/0007-usb-aspeed-vhub-ast2050-g3.patch`, wired into
  `build-kernel.sh`. **Compiles clean** (arm cross). Fix 3 (widen DT `reg` to
  0x350 + QEMU `NR_REGS`) is a runtime-robustness follow-up, not yet applied.
- **QEMU verification — DONE (faithful model reproduces the hang; fix resolves it).**
  The QEMU udc model is now faithful (QEMU submodule: `aspeed_udc_ast2050.c` models
  CTRL[31] read-only PHY-ready + the level-triggered, unmaskable ISR[18] deadlock on
  connect-into-not-ready-PHY; the udc IRQ is wired to VIC INT#5; reg window widened
  to 0x350). Result via the F6 USB test (`scripts/usb-test.py`):
  - **UNFIXED mainline driver → livelocks in QEMU** (no `Initialized virtual hub` →
    FAIL) — reproduces the silicon hang.
  - **FIXED driver (patch 0007) → probes cleanly** (`Initialized virtual hub`, 7
    ports p1-p7, mass-storage gadget enumerates → PASS).
  So QEMU now mirrors silicon for the vhub, and patch 0007 is verified against a
  model that actually reproduces the hang (not just a permissive stub). The F6 CI
  job now effectively gates the fix (the unfixed driver would fail it). The PHY
  ready-on-poll modeling is deterministic across host speeds (QEMU w/o icount does
  not advance virtual time through guest `udelay()`), and captures the essential
  semantic: a driver that polls PHY-ready succeeds; one that connects blind deadlocks.
- **Silicon verification:** ATTEMPTED but **blocked by P2A rig degradation** — the
  bench BMC boots into volatile DRAM over the P2A siphon, which corrupts large
  (~3.5 MB) kernel loads after ~15 boot cycles in a session ("kernel did not start
  cleanly — flaky P2A load"). Both boot attempts of the vhub-fixed kernel +
  vhub-enabled DTB (`uImage-kgpe-d16-vhubfix` + `kgpe-hwpass-usb.dtb`) hit flaky
  loads and did not reach userspace, so it is **undetermined** whether the box now
  survives the vhub probe. Resetting the P2A path needs a Tasmota `au-plug-10`
  power-cycle, which was NOT done because the host can halt at F1/F2 on a cold boot
  (dead CMOS battery, see the d16-host-pxe-boot notes) — that would strand the host
  (no host → no P2A → unrecoverable remotely), a worse state than the current one.
- **Recommended next step:** make the QEMU model faithful (CTRL[31] read-only +
  ISR[18] on connect-into-dead-PHY, §"QEMU faithfulness" above) and gate the fix in
  CI there — this verifies the port WITHOUT the fragile P2A rig. Then re-test on
  silicon on a fresh boot (early in a session, before P2A degrades) or a
  flash-resident BMC.  **[DONE 2026-07-15 — the faithful model + CI gating is
  implemented and verified; see "QEMU verification" above.]**

## Why the silicon retest was NOT forced (power-cycle risk analysis)
Resetting the degraded P2A siphon needs a Tasmota `au-plug-10` power-cycle. That was
deliberately NOT done: on a cold boot the host halts at **F1/F2** (dead CMOS battery,
confirmed — the COM1 serial log shows `Intel Boot Agent GE v1.3.24` at the last cold
boot). Recovering past F1/F2 needs driving the host BIOS over the COM1 serial
(`seriald.py` + `com1.tx` under the Pi's `tim` user) — a path that could not be
verified without first being AT an F1/F2 prompt (chicken-and-egg). If that recovery
failed, the host would halt forever → no host → no P2A → **the entire rig's silicon
access is lost for the whole program** (a catastrophic, physically-unrecoverable
outcome vs. the current state where a hung BMC is re-bootable). Since patch 0007 is
already QEMU-verified against a hang-reproducing model AND independently re-confirmed,
that marginal silicon retest does not justify risking all silicon access. The clean
path is a fresh session (P2A un-degraded) or a flash-resident BMC — neither of which
risks the rig.

**Empirical follow-up (2026-07-15, 3rd attempt):** retried the vhub-fixed boot with
the BMC **quiescent** (net down, NOT running Linux) to rule out the
running-BMC-corrupts-siphon theory — it was STILL flaky ("kernel did not start
cleanly"). So the degradation is **persistent DDR2/rig state**, not live siphon
corruption; the JTAG run-control "halt the ARM" idea therefore would NOT help (the
ARM is not the corruptor), and only a power-cycle (catastrophic F1/F2 strand risk)
resets it. Silicon retest of patch 0007 is thus genuinely blocked this session with
no safe unblock. (A JTAG-based DDR2 re-init via `~/openocd-bmc/ddr2-init.tcl` is a
possible independent path but needs a custom boot flow that skips the P2A DDR2 init
and hands the JTAG-trained DRAM to U-Boot — untested, next-session work.)

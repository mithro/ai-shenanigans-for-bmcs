# RTC — AST2050 driver + faithfulness doc

**Base 0x1E781000.** A **counter-style** RTC (datasheet §24): four independent
up-counters (sec/min/hour/day), loaded via a reload register + a restart magic.
This is **not** the AST2400 BCD/CMOS RTC, despite sharing the base address. Full
detail: **[`DATASHEET-RTC.md`](DATASHEET-RTC.md)**.

## 1. Registers (reset = X — volatile, no battery backup)

| Off | Register | Notes |
|---|---|---|
| 0x00 | counter status (R) | `[5:0]`sec `[11:6]`min `[16:12]`hour `[31:17]`day |
| 0x04 | (alarm/day) | |
| 0x08 | reload | value to load |
| 0x0C | control | `[0]` enable (default 0) |
| 0x10 | restart | write **0x5A** to load the counter from reload |
| 0x14 | reset | write **0x99** |

**Clock:** SecCnt ticks at 1 Hz off **CLK32K** (~32.768 kHz, synthesized from the
24 MHz reference — SCU clock tree). Set the time by writing reload then restart
(0x5A). Five VIC IRQs (INT22–26).

## 2. QEMU faithfulness — layout gap (like the VIC)

`peripherals/rtc/fwtest.c` vs the current model — the G3-layout checks **FAIL**:
- writing `0x0C` bit0 does not read back (control is not at 0x0C in the AST2400 model);
- writing reload (0x08) + restart magic (0x10 = 0x5A) does **not** load the counter
  at 0x00.

Root cause: the machine (qom_socname `ast2400`) instantiates the **AST2400
`aspeed_rtc`**, whose register model differs from the G3 (a host-time-offset model,
not the counter/reload/restart-magic scheme). The mainline `aspeed-rtc` Linux driver
matches the AST2400 model — so, exactly as with the VIC, a faithful G3 RTC needs a
matching **G3 kernel RTC driver** (co-evolution of our own firmware), while the legacy
Raptor/vendor kernels drive the real G3 RTC.

## 3. Faithful-model plan (oracle-gated)

- Add an `aspeed.rtc-ast2050` counter-style model (sec/min/hour/day at 0x00, reload
  0x08, control 0x0C, restart-magic 0x10=0x5A, CLK32K 1 Hz tick).
- Wire it only with the matching G3 kernel RTC driver, keeping the legacy boots green.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ (G3-layout checks fail against the AST2400 model — documents the gap) |
| 2 | doc (this + `DATASHEET-RTC.md`) | ☑ |
| 3 | QEMU model | ☐ counter-style G3 RTC pending (§3, oracle-gated) |
| 4 | integration test (`../../integration/test_rtc.py`) | ◐ observations pass; G3-layout checks xfail |

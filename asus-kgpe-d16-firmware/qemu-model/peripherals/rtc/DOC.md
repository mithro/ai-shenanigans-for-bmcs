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

## 2. QEMU faithfulness — MODELLED (`aspeed.rtc-ast2050`)

`peripherals/rtc/fwtest.c` — the G3-layout checks **PASS**: control (0x0C) is RW, and
writing reload (0x08) then the restart magic (0x10 = 0x5A) loads the counter (0x00),
which reads back the programmed sec/min/hour. Implemented as a new **`aspeed.rtc-ast2050`**
device (`hw/misc/aspeed_rtc_ast2050.c`) replacing the AST2400 `aspeed_rtc` for the G3
(keyed on silicon-rev; the AST2400 rtc is skipped in `_init` to satisfy qdev realize).

**Boot-safe (CI-validated):** unlike the VIC, wiring the G3 RTC keeps all C1–C4 boots
green — the mainline `aspeed-rtc` driver expects the AST2400 layout but merely reads a
wrong/zero time rather than hanging, so the boot proceeds. (A G3 kernel RTC driver would
give correct time, but is not required for the oracle.)

*Refinement (deferred):* the 1 Hz CLK32K counter advance (the model loads + holds the
counter; it does not tick). The load/read register path is faithful.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ control RW + counter load (restart-magic) |
| 2 | doc (this + `DATASHEET-RTC.md`) | ☑ |
| 3 | QEMU model | ☑ `aspeed.rtc-ast2050` counter-style (boot-safe; 1 Hz tick deferred) |
| 4 | integration test (`../../integration/test_rtc.py`) | ☑ passes |

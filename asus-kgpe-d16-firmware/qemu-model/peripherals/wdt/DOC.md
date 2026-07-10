# Watchdog Timer (WDT) — AST2050 driver + faithfulness doc

**Base 0x1E785000.** A PCLK/1 MHz down-counter that resets the SoC (or interrupts)
on timeout. Register + bit detail is in the shared
**[`../timer/DATASHEET-TIMER.md`](../timer/DATASHEET-TIMER.md)** (timer + WDT).

## 1. Registers

| Off | Register | Reset | Notes |
|---|---|---|---|
| 0x00 | counter / status | `0x03EF1480` | current down-count |
| 0x04 | reload | `0x03EF1480` | 66,000,000 = 1 s @66 MHz PCLK |
| 0x08 | restart (magic) | — | write **`0x4755`** to reload the counter |
| 0x0C | control | 0 | `[0]`enable `[1]`reset-system `[2]`interrupt `[4]`clock (0=PCLK,1=1 MHz) |

## 2. Driver notes

- Kick the watchdog by writing `0x4755` to the restart register (0x08); this reloads
  the counter from the reload register. Linux `aspeed_wdt` / U-Boot do exactly this.
- To arm: set reload, then control `[0]`enable (+`[1]`reset-system for a real reset).
- Timeout = reload / PCLK. **The absolute rate depends on PCLK** (SCU H-PLL post-
  divider — task #55); QEMU currently hardcodes 24 MHz (a rate error, not a register
  one).

## 3. QEMU faithfulness

`peripherals/wdt/fwtest.c` (4 checks) vs the current model — **all PASS**: reload +
control reset values match the datasheet; writing the `0x4755` magic reloads the
counter from the (rewritten) reload value. The AST2400 `aspeed_wdt` model is
register-faithful for the G3. **No model change needed** (so no risk to the legacy
boot oracle). The safety rule (never set reset-system in the test) keeps the machine
from resetting mid-transcript.

*Deferred (rate fidelity):* the hardcoded 24 MHz PCLK → the emulated timeout is ~2.75×
too long vs the real 66 MHz; fixed with the SCU clock-tree work + validated by a timing
measurement on silicon (HW-VALIDATION-CHECKLIST), not a register test.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ 4 checks (reset + restart-magic) |
| 2 | doc (this + `../timer/DATASHEET-TIMER.md`) | ☑ |
| 3 | QEMU model | ☑ register-faithful (PCLK rate deferred → task #55) |
| 4 | integration test (`../../integration/test_wdt.py`) | ☑ |

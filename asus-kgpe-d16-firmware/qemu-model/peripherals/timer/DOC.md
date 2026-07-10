# Timer (FTTMR010) — AST2050 driver + faithfulness doc

**Base 0x1E782000.** Three independent **PCLK down-counters** (timer1/2/3), each
with count / reload / two match registers, plus one shared control register.
Full page-cited reference: **[`DATASHEET-TIMER.md`](DATASHEET-TIMER.md)** (also
covers the WDT). Datasheet: all registers 0x00–0x30 reset to 0; **G3 has only 3
timers and one control register** (no AST2400 ctrl2/ctrl3/irq-status at 0x34+).

## 1. Register map

| Off | Register | Reset |
|---|---|---|
| 0x00/0x10/0x20 | timer1/2/3 count (down) | 0 |
| 0x04/0x14/0x24 | timer1/2/3 reload | 0 |
| 0x08/0x18/0x28 | timer1/2/3 match #1 | 0 |
| 0x0C/0x1C/0x2C | timer1/2/3 match #2 | 0 |
| 0x30 | control (shared) | 0 |

**Control TMC30** — 4 bits per timer (timer1 = `[2:0]`, timer2 = `[6:4]`, timer3 =
`[10:8]`): `[0]` enable, `[1]` clock-select (0 = **PCLK**, 1 = 1 MHz CLK1M),
`[2]` overflow-interrupt enable.

## 2. Clock & driver notes

- Each timer counts from **PCLK** (= SCU H-PLL / SCU08[25:23] APB divider, ≈66 MHz
  on real boards) or a fixed **1 MHz** reference — *not* 32.768 kHz (that's the RTC).
- Linux drives it via `timer-fttmr010.c` (`aspeed,ast2400-timer`, reused for G3) as
  PCLK down-counters; the clockevent programs match/reload and takes the timer IRQ
  (VIC sources 16/17/18, **rising-edge** — see `peripherals/vic`).
- Two match IRQs per timer are ungateable; firmware silences an unused match by
  setting it to 0xFFFFFFFF.

## 3. QEMU faithfulness

`peripherals/timer/fwtest.c` (6 checks) vs the current model — **all PASS**:
control + count reset to 0; enabling timer1 (control `0x1`, PCLK) loads from reload
and **counts down** (verified: two reads after spin loops show a monotonic
decrease). The AST2400 timer model is functionally faithful for the G3's three
low timers; the extra AST2400 registers at 0x34+ are unused by G3 firmware.

**Deferred (rate fidelity, not register behaviour):** the exact PCLK *frequency*
depends on the SCU H-PLL post-divider `[14:12]` (task #55). QEMU currently derives
the timer clock from the AST2400 H-PLL formula (no post-divider), so the absolute
tick rate may be ~2× off even though counting is correct. This is validated by a
timing measurement on silicon (HW-VALIDATION-CHECKLIST), not by a register test —
and fixed together with the SCU clock-tree work.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ 6 checks (reset + functional down-count) |
| 2 | doc (this + `DATASHEET-TIMER.md`) | ☑ |
| 3 | QEMU model | ☑ observable behaviour faithful (absolute PCLK rate deferred → task #55) |
| 4 | integration test (`../../integration/test_timer.py`) | ☑ |

# PWM / Tachometer — AST2050 driver + faithfulness doc

**Base 0x1E786000.** **4 PWM outputs + 16 fan-tach inputs** (datasheet §28). OpenBMC
uses this for fan speed control and RPM monitoring (hwmon). Full detail:
**[`DATASHEET-PWM.md`](DATASHEET-PWM.md)**.

## 1. Registers

| Off | Register | Notes |
|---|---|---|
| 0x00 | general control (PTCR00) | `[0]` master clock, `[11:8]` PWM A–D enable, `[15:12]` type M/N, `[31:16]` tach enable |
| 0x04 | clock control | prescaler / type M & N timing |
| 0x08/0x0C | PWM duty (rise/fall) | 8-bit, 1/256 |
| 0x2C | tach result (PTCR2C, R) | `[31]` full, `[19:0]` value |

**Tach → RPM** = `(24e6 × 60) / (2 × TachoValue × TachoClkDiv)`. Nothing exists at or
above 0x40. Single level IRQ (VIC INT28).

## 2. QEMU faithfulness — MODELLED (`aspeed.pwm-ast2050`)

`peripherals/pwm/fwtest.c` vs the model — **all checks PASS**: PTCR00 general control
(master-clock enable, PWM-A enable) and the duty register are RW. Implemented as a new
**`aspeed.pwm-ast2050`** device (`hw/misc/aspeed_pwm_ast2050.c`): a register-accurate 4
PWM + 16 tach model, register window 0x00–0x3C, PTCR2C tach result read-only, INT28.
Mapped at 0x1E786000 (mainline QEMU leaves it unmapped), keyed on the G3 silicon-rev so
AST2400/2500 are unchanged. **OpenBMC fan hwmon can now bind + drive PWM/duty.**

*Refinement (deferred):* compute the tach RPM result (PTCR2C) from the programmed duty
+ a synthetic fan model, so `hwmon-fan` reads a plausible RPM. The register interface is
faithful; the RPM synthesis is a behavioural add-on.

## 3. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ 3 checks (PTCR00 + duty RW) |
| 2 | doc (this + `DATASHEET-PWM.md`) | ☑ |
| 3 | QEMU model | ☑ `aspeed.pwm-ast2050` (register-accurate; tach RPM synthesis deferred) |
| 4 | integration test (`../../integration/test_pwm.py`) | ☑ passes |

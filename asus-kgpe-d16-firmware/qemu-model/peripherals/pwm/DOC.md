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

## 2. QEMU faithfulness — UNMODELLED

`peripherals/pwm/fwtest.c` vs the current model — **all checks FAIL**: PTCR00 reads 0,
writes are ignored, the duty register doesn't hold. The AST2050 PWM/tach block is **not
modelled** on this machine (the `-M kgpe-d16-bmc` "tolerate unmodelled MMIO → 0" flag
returns 0 for `0x1E786000`). **OpenBMC fan control/monitor cannot be verified** until a
faithful model exists.

## 3. Faithful-model plan (oracle-safe — new device at an unmodelled address)

Add an `aspeed.pwm-ast2050` device: 4 PWM channels (enable + duty), 16 tach inputs
(programmable RPM result), PTCR00-3C register layout, INT28. Mapping it at 0x1E786000
(currently returning 0) is low oracle-risk — the legacy boots don't depend on the block
being absent — but must be CI-validated to keep C1–C4 green. This unblocks OpenBMC hwmon
fan verification.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ (documents the unmodelled block) |
| 2 | doc (this + `DATASHEET-PWM.md`) | ☑ |
| 3 | QEMU model | ☐ new `aspeed.pwm-ast2050` device (§3) |
| 4 | integration test (`../../integration/test_pwm.py`) | ◐ checks xfail until §3 |

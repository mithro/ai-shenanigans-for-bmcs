# AST2050 / AST1100 PWM & Fan Tachometer Controller — Datasheet Extraction

Source: **ASPEED AST2050/AST1100 A3 Datasheet V1.05**, PDF at
`datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf`.
Every value cites the printed page number (footer == physical PDF page here).

Cross-referenced against `asus-kgpe-d16-firmware/hwreg.h` — which **has no PWM /
Fan-Tach definitions at all** (no `AST_PWM_BASE`, no `PTCRxx`), so there is no
Raptor fallback; all offsets come from the datasheet.

Scope for QEMU faithful emulation:
- **PWM & Fan Tacho Controller** — base **0x1E78:6000**, sixteen 32-bit
  registers **PTCR00–PTCR3C**. **4 PWM outputs** (A/B/C/D) + **16 fan-tach
  inputs** (#0–#15). The register file is named `PTCRxx` (the datasheet's
  ordering, §28.1 p290) — *not* the AST2400/2500 PWM/tach layout.

---

## 0. Where this block lives (memory map, §9)

Memory-map table, **page 97**:

| Range | Size | Block |
|---|---|---|
| `1E78:5000–1E78:5FFF` | 4K | Watchdog Timer |
| **`1E78:6000–1E78:6FFF`** | 4K | **PWM & Fan Tacho Controller** |
| `1E78:7000` | 4K | Virtual UART |

Chapter location (via the §9 memory map, per request):
- **Chapter 28 "PWM & Fan Tacho Controller"** — pages **290–295**
  (§28.3 register base `0x1E78:6000`, p290; register tables p291–295;
  RPM formula p295).

Base agrees with the task's stated **0x1E786000**. Interrupt line (§10, p99):
**INT28 "Tachometer interrupt", "Sensitive high level trigger"** — a **single**
level IRQ shared by all 16 fan-tach channels (per-channel status in PTCR34).

---

## 1. Channel counts & features (§28.2, p290)

**PWM Controller (p290):**
- "**Support 4 PWM outputs**" (ports **A, B, C, D**).
- "Support both **low-frequency and high-frequency** PWM for fan speed control."
- "**Duty cycle from 0 to 100 % with 1/256 resolution** incremental." (⇒ 8-bit
  period; duty set by an 8-bit rising point + 8-bit falling point.)
- "Support low-frequency PWM pulse stretching for fan speed measurements."
- "**Shared with GPIO pins.**"

**Fan Tachometer Controller (p290):**
- "Directly connected to APB bus."
- "**Support 16 tachometer inputs**" (fan tach **#0–#15**).
- "Measurement schemes: **rising edge, falling edge or both edges**."
- "Support **interrupt trigger** when over fan speed limitation setting."
- "**4 tachometer input pins are dedicated, 12 tachometer input pins are shared
  with DVO input pins.**"

**Feature-comparison cross-check (§1.4/§1.5, p27–28):** AST2050, AST1100 and
AST2100 all list **PWM Outputs = Yes (x4)** and **Fan Tech = Yes (x16)**. The
older **AST2000 has PWM = No and Fan Tech = No** (p28) — the PWM/tach block did
not exist on AST2000.

### The "Type M / Type N" concept (crucial for the model)

The block has **two independent timing "types", M and N**. Each of the four PWM
ports is bound to one type (PTCR00[15:12]); each of the two fan-tach engines is
configured per type (PTCR10/14 = Type M, PTCR18/1C = Type N). So there are **two
PWM clock/period programmings** (M and N) that the four ports and 16 tach inputs
draw from — not four fully independent PWM generators. A faithful model
implements **two type-M/N clock+period generators** feeding 4 duty comparators
and 16 tach counters.

---

## 2. PWM/tach clock tree (§8.1 p84, §8.2 Fig 19 p85, Fig 37 p93)

- Base clock is **`CLK24M` = 24 MHz** (the external 24 MHz source).
- §8.1 (p84): `PWMCLK` = "24 MHz (max), divided from the external 24 MHz clock
  source"; `TACHCLK` = "6 MHz (max), divided from the external 24 MHz clock
  source".
- Clock & Reset Tree (Fig 19, p85): the **PWM** row lists Clock Tree =
  `PCLK, PWMCLK, PWMCLKM, PWMCLKN, TACHCLKM, TACHCLKN` and Reset Tree =
  `PWM_RST_N`. (`PCLK` clocks the register interface.)
- Figure 37 "PWM Clock" (**p93**): a *PWM Clock Generation* block takes `CLK24M`
  plus control bits **PTCR00[0], PTCR04[7:0], PTCR04[23:16], PTCR10[3:1],
  PTCR18[3:1]** and produces **PWMCLK, PWMCLKM, PWMCLKN, TACHCLKM, TACHCLKN**.
- **PTCR00[0] "Enable PWM & Fan Tach clock"** is the master clock gate — nothing
  runs until it is 1.

---

## 3. Register map (Chapter 28, base 0x1E78:6000)

Sixteen registers, **PTCR00–PTCR3C** (§28.1 list, p290). Reset column from the
register boxes (p291–295): PTCR00 `Init = 0xXXXXX000` (low 12 bits 0, upper bits
undefined); **all other registers `Init = X` (undefined)**.

| Off | Name | R/W | Reset | Purpose |
|-----|------|-----|-------|---------|
| 0x00 | PTCR00 General Control | RW | `0xXXXXX000` | Master clock enable, per-port PWM enable + type select, per-channel fan-tach enable. (p291) |
| 0x04 | PTCR04 Clock Control | RW | X | Type M & Type N PWM period + clock dividers. (p291–292) |
| 0x08 | PTCR08 Duty Control 0 | RW | X | PWM A & PWM B rising/falling points (duty). (p292) |
| 0x0C | PTCR0C Duty Control 1 | RW | X | PWM C & PWM D rising/falling points (duty). (p292) |
| 0x10 | PTCR10 Type M Control 0 | RW | X | Type-M fan-tach period, mode, clock div, smart-tach, enable. (p292–293) |
| 0x14 | PTCR14 Type M Control 1 | RW | X | Type-M fan-tach rising/falling point. (p293) |
| 0x18 | PTCR18 Type N Control 0 | RW | X | Type-N fan-tach period, mode, clock div, smart-tach, enable. (p293) |
| 0x1C | PTCR1C Type N Control 1 | RW | X | Type-N fan-tach rising/falling point. (p293) |
| 0x20 | PTCR20 Tach Source | RW | X | Which PWM (A/B/C/D) drives each fan-tach channel. (p294) |
| 0x28 | PTCR28 Trigger | RW | X | Per-channel 0→1 trigger to (re)start a fan-tach measurement. (p294) |
| 0x2C | PTCR2C Result | **R** | X | Measured fan-tach value + full/partial status (selected channel). (p294) |
| 0x30 | PTCR30 Interrupt Control | RW | X | Per-channel fan-tach interrupt enable. (p294–295) |
| 0x34 | PTCR34 Interrupt Status | RW | X | Per-channel fan-tach interrupt pending (write-1-to-clear style). (p295) |
| 0x38 | PTCR38 Type M Limit | RW | X | Type-M fan-tach limit (over-speed compare). (p295) |
| 0x3C | PTCR3C Type N Limit | RW | X | Type-N fan-tach limit (over-speed compare). (p295) |

(Offsets 0x24 is not defined; the list skips from PTCR20 to PTCR28.)

---

## 4. PWM control & duty registers

### PTCR00 General Control (0x00, RW, Init = 0xXXXXX000) (p291)

| Bit | Field | Meaning |
|-----|-------|---------|
| **31:16** | Enable Fan Tach #15 ~ #0 | bit `16+n` enables fan-tach channel `n` (1: enable, 0: disable). |
| **15** | Type select PWM **D** port | 0: type M, 1: type N |
| **14** | Type select PWM **C** port | 0: type M, 1: type N |
| **13** | Type select PWM **B** port | 0: type M, 1: type N |
| **12** | Type select PWM **A** port | 0: type M, 1: type N |
| **11** | Enable PWM **D** port | 0: disable, 1: enable |
| **10** | Enable PWM **C** port | 0: disable, 1: enable |
| **9** | Enable PWM **B** port | 0: disable, 1: enable |
| **8** | Enable PWM **A** port | 0: disable, 1: enable |
| 7:1 | Reserved | — |
| **0** | **Enable PWM & Fan Tach clock** | 0: disable, 1: enable (master gate) |

Reset `0xXXXXX000` ⇒ low 12 bits are 0 (all PWM ports + master clock disabled at
reset); the fan-tach enable bits [31:16] are undefined. The model should treat
the whole block as **off** until PTCR00[0] and the per-port/per-channel enables
are set.

### PTCR04 Clock Control (0x04, RW) (p291–292)

Two PWM clock generators (type N in the high half, type M in the low half):

| Bit | Field | Meaning |
|-----|-------|---------|
| **31:24** | Type N PWM period [7:0] | in units of type-N PWM clock (period = duty denominator, 8-bit → 1/256 res) |
| **23:20** | Type N PWM clock division **H** [3:0] | 0000: ÷1, 0001: ÷2, 0010: ÷4, 0011: ÷8, … 1111: ÷32768 |
| **19:16** | Type N PWM clock division **L** [3:0] | 0000: ÷1, 0001: ÷2, 0010: ÷4, 0011: ÷6, … 1111: ÷30 |
| **15:8** | Type M PWM period [7:0] | in units of type-M PWM clock |
| **7:4** | Type M PWM clock division **H** [3:0] | 0000: ÷1 … 1111: ÷32768 |
| **3:0** | Type M PWM clock division **L** [3:0] | 0000: ÷1 … 1111: ÷30 |

The two-stage divider (H × L) sets each type's PWM clock; the 8-bit period sets
the duty resolution/denominator.

### PTCR08 Duty Control 0 (0x08, RW) — PWM A & B (p292)

| Bit | Field |
|-----|-------|
| 31:24 | **PWM B falling** point [7:0] of period |
| 23:16 | **PWM B rising** point [7:0] of period |
| 15:8 | **PWM A falling** point [7:0] of period |
| 7:0 | **PWM A rising** point [7:0] of period |

### PTCR0C Duty Control 1 (0x0C, RW) — PWM C & D (p292)

| Bit | Field |
|-----|-------|
| 31:24 | **PWM D falling** point [7:0] |
| 23:16 | **PWM D rising** point [7:0] |
| 15:8 | **PWM C falling** point [7:0] |
| 7:0 | **PWM C rising** point [7:0] |

**Duty semantics for the model:** each PWM port's duty is the window between its
**rising point** and **falling point** within the 8-bit period (0–255). Duty% =
`(falling − rising) / period` giving the stated 0–100 % at 1/256 resolution
(§28.2, p290). The output high/low interval is what physically stretches the fan
tach measurement window (pulse stretching, §28.2).

---

## 5. Fan-tach configuration, measurement & interrupts

### PTCR10 Type M Control 0 (0x10, RW) (p292–293) — Type N is PTCR18, identical layout (p293)

| Bit | Field | Meaning |
|-----|-------|---------|
| **31:16** | Type M fan-tach **period** [15:0] | in units of type-M PWM clock |
| 15:8 | Reserved (0) | — |
| **7** | Enable **smart** fan tach of type M | 0: disable, 1: enable |
| 6 | Reserved | — |
| **5:4** | Type M fan-tach **mode** [1:0] | 00: falling edge, 01: rising edge, 10: both edges, 11: reserved |
| **3:1** | Type M fan-tach **clock division** [1:0-ish] | 000: ÷4, 001: ÷16, 010: ÷64, 011: ÷256, … 111: ÷65536 |
| **0** | Enable fan tach of type M | 0: disable, 1: enable |

### PTCR14 Type M Control 1 (0x14, RW) — Type N is PTCR1C (p293)

| Bit | Field |
|-----|-------|
| 31:16 | Type M fan-tach **falling** point [15:0] of period |
| 15:0 | Type M fan-tach **rising** point [15:0] of period |

### PTCR20 Tach Source (0x20, RW) (p294)

2 bits per fan-tach channel selecting which PWM output drives it:
fan-tach #15 = [31:30], #14 = [29:28], … #0 = [1:0]; value **00: PWM A,
01: PWM B, 10: PWM C, 11: PWM D**.

### PTCR28 Trigger (0x28, RW) (p294)

[15:0] = "Trigger to read fan tach #15 ~ #0 (**0-to-1 trigger**)"; bit `n`'s
0→1 transition starts a fresh measurement of fan-tach channel `n`. [31:16]
reserved.

### PTCR2C Result (0x2C, R) (p294)

| Bit | Field |
|-----|-------|
| **31** | Fan tach # **full measurement status** — 0: partial measurement, 1: full measurement |
| 30:20 | Reserved (0) |
| **19:0** | **Measured fan tach # value** [19:0] |

There is a **single** result register; the channel it reports corresponds to the
one triggered via PTCR28 (and sourced via PTCR20). Bit 31 tells software whether
a complete period has been captured yet.

### PTCR30 Interrupt Control (0x30, RW) (p294–295)

[15:0] = "Enable fan tach #15 ~ #0 interrupt"; bit `n` enables the over-limit
interrupt for channel `n` (1: enable). [31:16] reserved.

### PTCR34 Interrupt Status (0x34, RW) (p295)

[15:0] = "Fan tach #15 ~ #0 interrupt status"; bit `n` = 1 means channel `n`
interrupt is **pending** (0: no interrupt). [31:16] reserved. These OR together
to drive the single **INT28** tachometer IRQ (§10, p99).

### PTCR38 / PTCR3C Type M / Type N Limit (0x38 / 0x3C, RW) (p295)

[19:0] = "Type M / Type N fan-tach **limit**" [19:0]; [31:20] reserved. A
measured value crossing the limit raises the channel's interrupt (over-speed /
under-speed detection per §28.2 "interrupt trigger when over fan speed
limitation setting").

### RPM conversion (formula printed at p295)

```
RPM = (24000000 * 60) / (2 * TachoValue * TachoClkDivision)
```
where `24000000` = the 24 MHz base clock, `TachoValue` = PTCR2C[19:0], and
`TachoClkDivision` = the selected type-M/N fan-tach clock division (PTCR10[3:1]
or PTCR18[3:1]; values 4/16/64/256/…/65536). This confirms the tach time-base is
the 24 MHz source, and gives the exact number a faithful model must reproduce
when firmware reads PTCR2C.

---

## 6. AST2050 vs AST2400 / AST2500 / AST2600 (for a faithful QEMU model)

1. **Channel counts (cited): 4 PWM + 16 fan-tach** (§28.2 p290; §1.4/1.5 feature
   table p27–28). Model exactly four PWM comparators (A–D) and sixteen tach
   counters (#0–#15) — of which 4 tach pins are dedicated and 12 are muxed with
   DVO input pins (p290).
2. **This `PTCRxx` (0x00–0x3C) register layout is generation-specific.** It is
   organised around **two timing "types" M and N** (PTCR10/14 vs PTCR18/1C) with
   port-to-type binding in PTCR00[15:12]. Newer ASPEED parts (AST2400/2500) use a
   **different, larger PWM & Fan-Tach register map** (and later revisions add
   more PWM/tach channels and a third timing type); the AST2600 replaces the
   block entirely. Do **not** assume the newer layout — implement exactly
   PTCR00–PTCR3C as above. *(The AST2050 datasheet itself only defines M and N;
   any third type is out of scope for this chip.)*
3. **Single shared level IRQ (INT28), not per-channel VIC lines** (§10 p99);
   per-channel enable/status live in PTCR30/PTCR34. (Contrast the RTC, which has
   five separate VIC inputs.)
4. **24 MHz-based measurement with the exact RPM formula at p295** — reproduce
   `RPM = 24e6*60 / (2*TachoValue*TachoClkDivision)` so firmware fan-speed
   readouts match.
5. **PWM pins are shared with GPIO** (§28.2 p290): enabling a PWM port
   reassigns the pin away from GPIO — a faithful SoC model must coordinate the
   pin-mux with the GPIO block.
6. **No Raptor/`hwreg.h` cross-check exists** — `hwreg.h` omits PWM entirely, so
   the datasheet (this file) is the sole register authority. The historical
   revision note (p4, rev 0.92) "Remove PWM registers PTRC40 ~ PTRC7C, they
   don't exist" confirms the register file **ends at PTCR3C** — model nothing at
   0x40 and above.

---

## Quick reference (model constants)

```
PWM/TACH base = 0x1E786000   16 regs PTCR00..PTCR3C
  4 PWM outputs (A,B,C,D)  +  16 fan-tach inputs (#0..#15)  [4 tach dedicated, 12 muxed w/ DVO]
  two timing "types" M and N; each PWM port bound to a type via PTCR00[15:12]
  PTCR00 General Ctrl   RW  reset 0xXXXXX000  [31:16]tachEn#n=bit(16+n) [15:12]typeSel D/C/B/A [11:8]pwmEn D/C/B/A [0]master clk en
  PTCR04 Clock Ctrl     RW  [31:24]N period [23:16]N div H/L [15:8]M period [7:0]M div H/L
  PTCR08 Duty0          RW  [31:24]Bfall [23:16]Brise [15:8]Afall [7:0]Arise   (8-bit points, 1/256 duty)
  PTCR0C Duty1          RW  Dfall/Drise/Cfall/Crise
  PTCR10/14 Type M tach ; PTCR18/1C Type N tach  (period[15:0], mode 00fall/01rise/10both, clkdiv 4..65536, smart-tach, enable)
  PTCR20 Tach Source    RW  2b/ch: 00=A 01=B 10=C 11=D
  PTCR28 Trigger        RW  [15:0] 0->1 per-ch start measurement
  PTCR2C Result         R   [31]full/partial  [19:0]measured value
  PTCR30 IntEn / PTCR34 IntStatus  [15:0] per-ch ; PTCR38/3C Type M/N limit [19:0]
  base clock = CLK24M (24MHz); master gate = PTCR00[0]; single IRQ = INT28 (level)
  RPM = (24000000*60) / (2 * TachoValue * TachoClkDivision)          (p295)
  nothing exists at offset >= 0x40 (PTRC40..7C removed, p4)
```

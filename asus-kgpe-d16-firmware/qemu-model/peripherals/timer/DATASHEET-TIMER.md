# AST2050 / AST1100 Timer + Watchdog — Datasheet Extraction

Source: **ASPEED AST2050/AST1100 A3 Datasheet V1.05** (titled internally
"AST1100 Software Programming Guide"), PDF at
`datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf` (403 pages).
Every value below cites the printed datasheet page number (the number in the
page footer, which equals the physical PDF page here).

Cross-referenced against `asus-kgpe-d16-firmware/hwreg.h` (Raptor register
defs) and the vendored AST2400 QEMU models
`qemu-firmware/qemu/qemu/hw/timer/aspeed_timer.c` /
`hw/watchdog/wdt_aspeed.c` for the AST2400-vs-AST2050 comparison.

Scope for QEMU faithful emulation:
- **Timer (FTTMR010 / "TMC")** — base **0x1E78:2000**, three 32-bit timers.
- **Watchdog (WDT)** — base **0x1E78:5000**.

---

## 0. Where these blocks live (memory map, §9)

Memory map table, **page 97** (`0x1E78:xxxx` peripheral window):

| Range | Size | Block |
|---|---|---|
| `1E78:0000–1E78:0FFF` | 4K | GPIO Controller |
| `1E78:1000–1E78:1FFF` | 4K | Real-Time Clock (RTC) |
| **`1E78:2000–1E78:2FFF`** | 4K | **Timer #1, #2, #3 Controller** |
| `1E78:3000 / 1E78:4000` | 4K | UART #1 / UART #2 |
| **`1E78:5000–1E78:5FFF`** | 4K | **Watchdog Timer (WDT)** |
| `1E78:6000` | 4K | PWM & Fan Tacho |

Chapter locations (found after the §9 memory map, per the request):
- **Chapter 25 "Timer Controller"** — pages **275–278** (§25.3 register base `0x1E78:2000`, p275).
- **Chapter 27 "Watchdog Timer"** — pages **287–289** (§27.3 register base `0x1E78:5000`, p287).

Both bases agree with `hwreg.h`: `AST_TIMER_BASE 0x1E782000`, `AST_WDT_BASE 0x1E785000`.

---

## 1. Timer register map (Chapter 25, base 0x1E78:2000)

**Overview (p275):** "Timer Controller (TMC) includes **3 sets of 32-bit
decrement counters**, based on either **APB clock or external clock**. Each
counter is equipped with **two sets of matching registers**. When any one of
the Match registers equals the corresponding counter value, a timer interrupt
will be triggered. Each counter also can be programmed to trigger an interrupt
or not whenever **overflow** occurs. All the counter values can be read back at
any time." Features (p275): "Free-running or periodic mode", "Maskable
interrupts", "Directly connected to APB Bus."

TMC implements **13 registers total, 0x00–0x30** (p275). Register map (p275–277):

| Off | Name (datasheet) | R/W | Reset | Meaning |
|-----|------------------|-----|-------|---------|
| 0x00 | TMC00 Counter #1 Status | RW | **0** | Current value of down-counter #1. Decrements when `TMC30[0]`=1; CPU may write any time. (p275) |
| 0x04 | TMC04 Counter #1 Reload Value | RW | **0** | Loaded into counter #1 when it decrements to zero. (p276) |
| 0x08 | TMC08 Counter #1 First Match | RW | **0** | Counter #1 == this ⇒ edge-triggered interrupt. (p276) |
| 0x0C | TMC0C Counter #1 Second Match | RW | **0** | Secondary match ⇒ edge-triggered interrupt. (p276) |
| 0x10 | TMC10 Counter #2 Status | RW | **0** | Down-counter #2; enable = `TMC30[4]`. (p276) |
| 0x14 | TMC14 Counter #2 Reload Value | RW | **0** | Reload for counter #2. (p276) |
| 0x18 | TMC18 Counter #2 First Match | RW | **0** | Match #1 for counter #2. (p276) |
| 0x1C | TMC1C Counter #2 Second Match | RW | **0** | Match #2 for counter #2. (p276) |
| 0x20 | TMC20 Counter #3 Status | RW | **0** | Down-counter #3; enable = `TMC30[8]`. (p277) |
| 0x24 | TMC24 Counter #3 Reload Value | RW | **0** | Reload for counter #3. (p277) |
| 0x28 | TMC28 Counter #3 First Match | RW | **0** | Match #1 for counter #3. (p277) |
| 0x2C | TMC2C Counter #3 Second Match | RW | **0** | Match #2 for counter #3. (p277) |
| 0x30 | TMC30 Control | RW | **0** | Shared control for all three timers (see §2). (p277–278) |

Notes for the model:
- Counters are **down-counters** ("decrement", "decrease to zero"), 32-bit.
- All 13 registers **reset to 0** (each register box shows `Init = 0`, p275–278),
  so the whole block is zero at reset — nothing runs until software sets a Reload
  and enables via TMC30.
- `hwreg.h` names match one-to-one (COUNT=Status, RELOAD, FIRST_MATCH, SEC_MATCH;
  `TIMER_CONTROL_REG = 0x30`).

### Interrupt-status / clear at 0x34+? — **None on AST2050.**
The datasheet register list ends at **TMC30 (0x30)**; there is **no** register
at 0x34/0x38/0x3C. `hwreg.h` likewise defines nothing past 0x30. Timer
interrupts are **edge-triggered pulses** (p276) with no latched status inside the
timer block — they are cleared at the **VIC** (`AST_IC_BASE 0x1E6C0000`,
`IRQ_CLEAR_REG +0x14`, per `hwreg.h`), not in the timer. This is a key
divergence from the AST2400 (see §5).

---

## 2. Timer Control Register TMC30 (0x30) — bit fields (p277–278)

`Init = 0`. Layout is **4 bits per timer** (timer #1 = bits 0–2, #2 = bits 4–6,
#3 = bits 8–10; bits 3/7 reserved), all `RW`:

| Bit | Field | Meaning (datasheet text) |
|-----|-------|--------------------------|
| 31:11 | Reserved (0) | — |
| **10** | Enable Interrupt, Timer #3 | 0: no interrupt on overflow; **1: interrupt generated on overflow** |
| **9**  | Clock select, Timer #3 | **0: APB clock (PCLK); 1: External clock (1 MHz)** |
| **8**  | Timer enable, Timer #3 | 0: disable; 1: enable. *"When timer is disabled, all action for counter, reload, and interrupt will be gated."* |
| 7 | Reserved (0) | — |
| **6**  | Enable Interrupt, Timer #2 | 0/1 as above |
| **5**  | Clock select, Timer #2 | **0: PCLK; 1: External clock (1 MHz)** |
| **4**  | Timer enable, Timer #2 | 0: disable; 1: enable (gates all action) |
| 3 | Reserved (0) | — |
| **2**  | Enable Interrupt, Timer #1 | 0/1 as above |
| **1**  | Clock select, Timer #1 | **0: PCLK; 1: External clock (1 MHz)** |
| **0**  | Timer enable, Timer #1 | 0: disable; 1: enable (gates all action) |

**Operation (§25.4, p278):** Reload, Match1, Match2 and Control[Interrupt] must
be set before use. Reload sets the period between two overflows — e.g. Reload =
0x02 gives the count sequence `2,1,0,2,1,…`. An interrupt is generated when the
counter reaches zero **if** Control[Interrupt] is set. Sequence: (1) set Reload,
(2) set Control[Interrupt], (3) enable via Control[Enable].

**Programming note (§25.5, p278):** `TMC30[2]` (the interrupt-enable bit) does
**not** gate the *match-register* interrupt. So the two match registers fire
edge interrupts independently of the enable-interrupt bit; **to suppress unused
match interrupts, write the match registers to `0xFFFFFFFF`.** (For QEMU: model
two always-armed match sources per timer plus the overflow source that the
enable-interrupt bit gates.)

---

## 3. What clock each timer counts from

Per TMC30 bits 1/5/9 (p277–278), each timer independently selects:
- **0 → APB clock = PCLK** (the SoC APB bus clock), or
- **1 → External clock, explicitly "1 MHz"**.

This is corroborated by the **Clock & Reset Tree** (§8.2, Figure 19, **p85**):
the *Timer* row lists clock tree = **`PCLK`, `CLK1M`**; the *Watchdog* row is
identical (`PCLK`, `CLK1M`). There is **no 32.768 kHz option** for the timer or
WDT — only the **RTC** uses `CLK32K` (p85). So the request's "32.768 kHz
reference" does **not** apply to this block.

Clock definitions (§8.1 clock table, **p84**):
- **PCLK**: "100 MHz (max), generated from a dedicated PLL (H-PLL)"
  (footnote: "there is a limitation on the PCLK frequency allowed").
- **CLK1M**: "1 MHz, divided from the external 24 MHz clock source".
- (CLK32K: 32 kHz, RTC only.)

**PCLK derivation for tick fidelity:** PCLK is the H-PLL output run through the
APB post-divider in the SCU. The relevant SCU regs (`hwreg.h`):
`SCU_H_PLL_PARAM_REG` (`0x1E6E2024`) and `SCU_CLK_SELECT_REG`
(`0x1E6E2008`, which holds the APB divider). The datasheet's own worked example
assumes **PCLK = 66 MHz** (WDT §27.4, p289 — see §4), so a faithful AST2050
model should drive the timer/WDT APB tick at the **actual SCU-derived APB
frequency (≈66 MHz on real boards)**, not a fixed value.

**Linux cross-check (fttmr010 / aspeed timer):** The mainline driver is
`drivers/clocksource/timer-fttmr010.c` (compatible `aspeed,ast2400-timer`; the
G3/AST2050 reuses it — see `RAPTOR-PORTING-GUIDE.md` "Change 7: Timer",
`arch/arm/plat-aspeed/timer.c` → `timer-fttmr010.c` + DT). It programs the
timers as **down-counters** driven by the DT-supplied **PCLK** (clock-select
bit = 0, the APB path), matching "decrement + reload" semantics above. It does
**not** use the 1 MHz external path for the system clockevent/clocksource, so the
emulated PCLK rate is what determines clockevent accuracy — reinforcing that the
model's APB frequency must track the SCU H-PLL/divider.

---

## 4. Watchdog register map (Chapter 27, base 0x1E78:5000)

**Overview (p287):** WDT prevents deadlock; on timeout it can assert three
signals — **System reset**, **Interrupt**, and **External signal** (external
"**Only work for A1 version chip**"). Features (p287): single 32-bit
programmable counter, generates interrupt or reset on count-down to zero.
(WDTRST output pin note, p46: "Not work at A0 version".)

Register map (p287–289):

| Off | Name | R/W | Reset | Meaning |
|-----|------|-----|-------|---------|
| 0x00 | WDT00 Counter Status | **R** | **0x03EF1480** | Current counter value. After `HRST_N` = `0x03EF1480`. Writing `0x4755` to Restart loads Reload here. Counts down once `WDT0C[0]`=1; holds value when disabled. (p287) |
| 0x04 | WDT04 Counter Reload Value | RW | **0x03EF1480** | Value auto-loaded into WDT00 on reset/restart. (p288) |
| 0x08 | WDT08 Counter Restart | **W** [15:0] | 0 | Write **`0x4755`** ⇒ Reload → WDT00 and counter restarts (if `WDT0C[0]` set). [31:16] reserved. (p288) |
| 0x0C | WDT0C Control | RW | **0** | See bit table below. (p288) |
| 0x10 | WDT10 Timeout Status | **R** | 0 | bit0: 1 = a timeout has occurred (sticky record); 0 = never. (p288) |
| 0x14 | WDT14 Clear Timeout Status | **W** | 0 | Write bit0 = 1 to clear WDT10. (p288–289) |
| 0x18 | WDT18 Reset Width | RW [7:0] | **0xFF** | Assert duration of `wdt_intr`/`wdt_ext`. Default 0xFF = **256 PCLK cycles**. When `WDT0C[1]` (1 MHz clk) selected, pulse width ≤ 1.25 µs. (p289) |

`hwreg.h` only defines 0x00–0x0C (Status/Reload/Restart/Control) and stops
there; the datasheet additionally defines WDT10/WDT14/WDT18 — the model should
implement all six.

### WDT0C Control Register bit fields (p288)

`Init = 0`, all `RW`:

| Bit | Field | Meaning |
|-----|-------|---------|
| 31:5 | Reserved (0) | (but see §5 discrepancy — Raptor uses bit 5) |
| **4** | Clock select for WDT counter | **0: PCLK; 1: 1 MHz clock source** |
| **3** | `wdt_ext` — external signal enable after timeout | drives external WDTRST pin D9 (active-high); 0: disable, 1: enable |
| **2** | `wdt_intr` — interrupt enable after timeout | 0: disable, 1: enable |
| **1** | Reset system after timeout | 0: disable, 1: enable |
| **0** | WDT enable | 0: disable, 1: enable |

### Restart magic + reload semantics
- **Restart magic = `0x4755`** written to WDT08 (p288). Confirmed by Raptor
  U-Boot `reset.c` (`RAPTOR-UBOOT-ANALYSIS.md`: writes reload, `restart=0x4755`,
  control for full-chip reset) and by QEMU `WDT_RESTART_MAGIC 0x4755`.
- **Operation (§27.4, p289):** Reload sets the timeout period. Default Reload
  `0x03EF1480` = **66,000,000** ⇒ **1 second in a 66 MHz system**. Example:
  Reload `0xEC08CE00` (= 3,960,000,000 = 60 × 66 M) ⇒ **1 minute**. Steps:
  (1) disable WDT, (2) set Reload, (3) write `0x4755` to Restart, (4) set
  `WDT0C[4]` (clock select), (5) enable via `WDT0C[0]`.
- Arithmetic check: `0x03EF1480` = 66,000,000 exactly ⇒ 1 s @ 66 MHz PCLK; this
  is the datasheet's own assumed PCLK. **The default WDT counts on PCLK**
  (`WDT0C[4]`=0), not 1 MHz.

---

## 5. AST2050 vs AST2400 (for the QEMU aspeed_timer / aspeed_wdt models)

The vendored QEMU models (`hw/timer/aspeed_timer.c`, `hw/watchdog/wdt_aspeed.c`,
class `aspeed-2400-*`) are register-compatible supersets. Differences a faithful
**G3/AST2050** model must respect:

### Timer
1. **Timer count: 3 (AST2050) vs 8 (AST2400).** Datasheet p275 defines only
   timers #1–#3 (registers 0x00–0x2C). QEMU `aspeed_timer.h` sets
   `ASPEED_TIMER_NR_TIMERS 8` and exposes per-timer registers up to timer #8.
   The AST2050 window is only 0x00–0x30 — timers 4–8 do not exist.
2. **Only one control register on AST2050.** AST2050 has just `TMC30` (0x30,
   p277). The AST2400 QEMU state adds `ctrl2`, `ctrl3` and `irq_sts`
   (control-2/3 + interrupt-status, at 0x34/0x38/0x3C). **A faithful G3 model
   must not implement 0x34+** (or must RAZ/WI them).
3. **Per-timer control stride is identical (4 bits).** QEMU
   `TIMER_CTRL_BITS 4` with ops `enable(0)/external_clock(1)/overflow_int(2)/
   pulse_enable(3)` maps exactly onto TMC30's bits 0–2 / 4–6 / 8–10 — **except**
   AST2050 marks the 4th bit (3/7/11) **Reserved (0)** (p277–278), whereas
   AST2400 uses it as **pulse-enable**. Pulse mode is also gated by
   `timer_can_pulse()` = `id >= 4`, i.e. only AST2400 timers 5–8. So **AST2050
   has no pulse mode** — matching the note in
   `qemu-firmware/AST2050-PERIPHERAL-MODELING.md` ("aspeed_timer pulse mode …
   unsupported … noise").
4. **External clock = 1 MHz, same on both.** QEMU `TIMER_CLOCK_EXT_HZ 1000000`
   ⇔ datasheet "External clock (1 MHz)" (p277). PCLK path uses
   `aspeed_scu_get_apb_freq(scu)` in QEMU — good; keep that SCU-derived APB
   frequency for AST2050 (≈66 MHz), do not hardcode.
5. **Reset values identical:** all timer regs reset to 0 (p275–278). No change.

### Watchdog
1. **Use the `aspeed-2400-wdt` class defaults, not 2500+.**
   `aspeed_2400_wdt_class_init` sets `default_status = default_reload_value =
   0x03EF1480` and `ext_pulse_width_mask = 0xff` — these match the AST2050
   datasheet exactly (WDT00/WDT04 = `0x03EF1480`, p287–288; WDT18 = 0xFF /
   256 PCLK cycles, p289). AST2500/2600 changed the default to `0x014FB180`
   and force the 1 MHz clock — **wrong for AST2050**.
2. **Restart magic `0x4755` — same** on AST2050 and AST2400 (p288 / QEMU
   `WDT_RESTART_MAGIC`).
3. **PCLK-frequency fidelity bug to fix.** QEMU `wdt_aspeed.c` hardcodes
   `s->pclk_freq = PCLK_HZ = 24000000` with an explicit **FIXME** ("should be
   derived from the SCU hw strapping register SCU70"). The AST2050 datasheet
   default `0x03EF1480` = 1 s **only at 66 MHz** (p289); at QEMU's 24 MHz the
   default timeout becomes 66e6/24e6 ≈ **2.75 s** — wrong. A faithful AST2050
   WDT must derive `pclk_freq` from the SCU H-PLL/APB divider (≈66 MHz), like
   the timer model already does. (Contrast: the *timer* model correctly uses
   `aspeed_scu_get_apb_freq()`; only the *WDT* hardcodes 24 MHz.)
4. **Reset-mode bit — datasheet/silicon discrepancy.** The A3 datasheet marks
   `WDT0C[31:5]` Reserved (p288). QEMU `aspeed_2400_wdt` keeps 16 bits
   (`data & 0xffff`) and defines `WDT_CTRL_RESET_MODE` at bits **[6:5]**
   (SOC vs full-chip). Raptor U-Boot `reset.c` writes `control = 0x23` (bit 5
   set) for "full chip reset" (`RAPTOR-UBOOT-ANALYSIS.md`), implying the
   reset-mode bit **is functional on AST2050** despite the datasheet's
   "reserved". A faithful model should honor bit 5 (reset-mode) even though the
   A3 register table calls [31:5] reserved. `RAPTOR-PORTING-GUIDE.md`
   "Change 12" also notes SOC/full-chip/ARM-only reset modes on the AST2050 WDT.
5. **External-signal caveat:** WDT external output (`wdt_ext`, pin D9) only
   works on the **A1** silicon revision (p287; WDTRST "Not work at A0 version",
   p46) — a documentation note, not a register difference.

### Reset domains (context, §8.2/§8.3, p85–86)
Both Timer and Watchdog are reset by **`HRST_N`** and belong to the `SRST#` and
`WDT` global-reset columns (Figure 20, p86). The Timer/WDT do **not** survive a
watchdog reset (they are in the WDT reset domain). The WDT's own counter reset
value after `HRST_N` is `0x03EF1480` (p287).

---

## Quick reference (model constants)

```
TIMER  base = 0x1E782000   3 timers, regs 0x00..0x30, all reset 0
  per-timer: STATUS(0x0)/RELOAD(0x4)/MATCH1(0x8)/MATCH2(0xC), stride 0x10 (down-counter)
  TMC30 ctrl bits (x=timer 0..2): enable=4x+0, clocksel=4x+1(0=PCLK,1=1MHz), int=4x+2
  no reg > 0x30; match IRQ ungateable (set match=0xFFFFFFFF to disable)
  ext clock = 1 MHz; PCLK = SCU-derived APB (~66 MHz)

WDT    base = 0x1E785000
  WDT00 status  R  reset 0x03EF1480
  WDT04 reload  RW reset 0x03EF1480   (= 66,000,000 = 1 s @ 66 MHz PCLK)
  WDT08 restart W  magic = 0x4755
  WDT0C ctrl    RW reset 0:  [0]en [1]reset-sys [2]intr [3]ext [4]clk(0=PCLK,1=1MHz) [5]reset-mode*
  WDT10 timeout-status R ; WDT14 clear W ; WDT18 reset-width RW reset 0xFF (256 PCLK)
  * bit5 reserved per A3 datasheet but used by Raptor U-Boot (full-chip reset)

QEMU: use aspeed-2400-timer / aspeed-2400-wdt classes, but
  - cap timers at 3, drop ctrl2/ctrl3/irq_sts and pulse mode
  - fix WDT pclk_freq (24 MHz hardcode) → SCU APB (~66 MHz)
```

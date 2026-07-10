# AST2050 / AST1100 Real-Time Clock (RTC) — Datasheet Extraction

Source: **ASPEED AST2050/AST1100 A3 Datasheet V1.05**, PDF at
`datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf`.
Every value below cites the printed datasheet page number (the footer number,
which equals the physical PDF page here).

Cross-referenced against `asus-kgpe-d16-firmware/hwreg.h` (Raptor register defs)
— note that `hwreg.h` **has an empty "RTC Register Locations" section** (lines
156–158): it defines **no** RTC base or registers, so there is no Raptor
fallback for offsets; everything here comes from the datasheet.

Scope for QEMU faithful emulation:
- **Real-Time Clock (RTC)** — base **0x1E78:1000**, six 32-bit registers
  (0x00–0x14). This is a **counter-style** RTC (sec/min/hour/day up-counters),
  **not** a MC146818 CMOS RTC and **not** the AST2400-family RTC.

---

## 0. Where this block lives (memory map, §9)

Memory-map table, **page 97** (`0x1E78:xxxx` peripheral window):

| Range | Size | Block |
|---|---|---|
| `1E78:0000–1E78:0FFF` | 4K | GPIO Controller |
| **`1E78:1000–1E78:1FFF`** | 4K | **Real-Time Clock (RTC)** |
| `1E78:2000–1E78:2FFF` | 4K | Timer #1/#2/#3 Controller |

Chapter location (found via the §9 memory map, per the request):
- **Chapter 24 "Real Time Clock (RTC)"** — pages **270–274**
  (§24.3 register base `0x1E78:1000`, p270; register tables p271–272;
  programming modes §24.4 p273–274).

Base agrees with the task's stated base **0x1E781000**. (`hwreg.h` gives no RTC
base to cross-check; its RTC section is a stub.)

Interrupt lines (§10 Interrupt Source Table, **page 99**) — the RTC owns **five**
VIC inputs, all "**Edge trigger and both edge**":

| INT# | Description |
|---|---|
| 22 | RTC second interrupt |
| 23 | RTC day interrupt |
| 24 | RTC hour interrupt |
| 25 | RTC minute interrupt |
| 26 | RTC alarm interrupt |

---

## 1. Overview & clock source (§24.1–24.2, p270)

**Overview (p270):** "Real Time Clock (RTC) is a flexible real time clock. When
the system enters sleeping mode, the PCLK clock of APB bus can be gated and the
RTC keeps on counting." — i.e. the register interface is clocked by **PCLK**
(APB), but the **time-base keeps running when PCLK is gated**, because the
counter runs off a separate always-on clock (see below).

"RTC provides **separated second, minute, hour and day counters**. The second
counter is toggled once every second, the minute counter is toggled once every
minute, the hour counter is toggled once every hour and the day counter is
toggled once every day." (p270) — the counters are **independent up-counters**,
so software just reads them; it does **not** have to derive minutes/hours from a
single seconds count.

**Features (§24.2, p270):**
- "Directly connected to APB bus."
- "**Clock source is divided from 24 MHz clock input.**"
- "24-Hour timer mode with highest precision of a second."
- "Programmable alarm with interrupt generation."
- "Maskable interrupt."
- "**No battery backup supported.**"
- "**Precision ≈ 50 ppm** (24 MHz input precision), approximately 1 second
  deviation for each 12 hours."

### The two-level clock story (reconciles §24.2 with the clock tree)

The RTC has **two clocks** per the Clock & Reset Tree (Figure 19, §8.2,
**page 85**): the RTC row lists **Clock Tree = `PCLK`, `CLK32K`** and
**Reset Tree = `PWRSTN_N`**.

- **Register access clock = `PCLK`** (APB). Gated in sleep (§24.1, p270).
- **Time-base clock = `CLK32K`** — the classic 32.768 kHz RTC tick.
  §8.1 (**page 84**) defines `CLK32K` as "**32 KHz, divided from the external
  24 MHz clock source**", synthesized `CLK12M × 256 / 46875` (Figure 35,
  **page 92**). So §24.2's "divided from 24 MHz" (the ultimate reference) and
  the request's "32.768 kHz from SCU" (the derived RTC tick) are **both correct**
  — 24 MHz is the crystal, `CLK32K` is what actually clocks the RTC counter.
- The RTC internally divides `CLK32K` down to **1 Hz** so `SecCnt` advances
  once per second (§24.1, p270). **For QEMU it is enough to advance `SecCnt` at
  1 Hz** (host wall-clock or a 1 Hz QEMU timer) and cascade min/hour/day — the
  exact `CLK32K` synthesis is irrelevant to the register model.
- Because there is **no battery backup** (§24.2), the RTC is **volatile**:
  reset domain `PWRSTN_N` clears it at power-up, and it starts at an
  **undefined** value (all register `Init = X`, p271–272). A faithful model
  should not persist RTC state across a cold reset.

---

## 2. Register map (Chapter 24, base 0x1E78:1000)

Six 32-bit registers, offsets **0x00–0x14** (§24.3 list, p270). All reset
values are **`Init = X` (undefined)** in the datasheet register boxes
(p271–272) — there is no battery/backup and no defined power-on value.

| Off | Name (datasheet) | R/W | Reset | Purpose |
|-----|------------------|-----|-------|---------|
| 0x00 | RTC00 Counter Status | **R** | X | Live sec/min/hour/day up-counters (read the current time). (p271) |
| 0x04 | RTC04 Clock Alarm | RW | X | Specific-time alarm match (hour:min:sec). (p271) |
| 0x08 | RTC08 Reload Value | RW | X | Value loaded into the counters on Restart. Used to *set* the time. (p271–272) |
| 0x0C | RTC0C Control | RW | X | RTC enable + per-field alarm enables + restart status. (p272) |
| 0x10 | RTC10 Restart | **W** [7:0] | X | Write **`0x5A`** ⇒ copy Reload → counters. (p272) |
| 0x14 | RTC14 Reset | RW [7:0] | X | Write **`0x99`** ⇒ reset RTC immediately. (p272) |

---

## 3. Time/date counter register — RTC00 Counter Status (0x00, R) (p271)

Read-only; each sub-field auto-increments off the RTC time-base. Reset `X`.

| Bit | Field | Width / range | Meaning (datasheet text, p271) |
|-----|-------|---------------|--------------------------------|
| **31:17** | **DayCnt** — Status of Day Counter | 15 bits | "the RTC day counter register … When RTC is enabled, the DayCnt value always increases by day." Set an initial value via Reload+Restart before enabling. |
| **16:12** | **HourCnt** — Status of Hour Counter | 5 bits, **0–23** | "increases by hour. When HourCnt exceeds 23, the value is reset to zero … If the RTC is disabled, the HourCnt will hold the value." |
| **11:6** | **MinuCnt** — Status of Minute Counter | 6 bits, **0–59** | "increases by minute. When MinuCnt exceeds 59, the value is reset to zero … holds when disabled." |
| **5:0** | **SecCnt** — Status of Second Counter | 6 bits, **0–59** | "increases by second. When SecCnt exceeds 59, the value is reset to zero … holds when disabled." |

Counting semantics for the model (p271, §24.1 p270):
- These are **up-counters** with rollovers Sec 59→0 (carry minute), Min 59→0
  (carry hour), Hour 23→0 (carry day), Day free-running 15-bit.
- Counting only runs while **RTC0C[0] (RTC enable) = 1**; when disabled the
  counters **hold** their values.
- The counters are **read-only**: the only way to write time is via
  RTC08 (Reload) + RTC10 (Restart) — see §5.

---

## 4. Control, alarm, reload, restart, reset registers

### RTC04 Clock Alarm Register (0x04, RW) — the specific-time alarm (p271)

| Bit | Field | Meaning (p271) |
|-----|-------|----------------|
| 31:13 | Reserved (0) | — |
| **16:12** | Hour alarm | "If user wants to trigger RTC alarm interrupt at 12:10:15, the register needs to set 0xC. If the register value exceeds 0x17, RTC alarm will never be triggered. But the RTC counter keeps on counting." |
| **11:6** | Minute alarm | "…set 0xA. If the value exceeds 0x3B, RTC alarm will never be triggered." |
| **5:0** | Second alarm | "…set 0xF. If the value exceeds 0x3B, RTC alarm will never be triggered." |

So the clock alarm is a **hour:minute:second match** (12:10:15 → hour=0xC,
min=0xA, sec=0xF). Out-of-range fields disable the alarm without stopping the
clock. This drives **INT26 "RTC alarm interrupt"** (§10, p99). **Note:** there
is **no day field** in RTC04 ([31:13] reserved) even though RTC0C[4] is
"Enable day alarm" — see the ambiguity note in RTC0C below.

### RTC08 Reload Value Register (0x08, RW) (p271–272)

Same field layout as RTC00, all `RW`: **[31:17] reload day, [16:12] reload
hour, [11:6] reload minute, [5:0] reload second**. "User can adjust the clock by
setting reload value, and restart RTC. After restart RTC, the reload value will
be reloaded into the {day/hour/minute/second} counter. The method of restart is
described on restart register." (p271–272) — i.e. **this is how you set the
time**: write RTC08, then trigger RTC10.

### RTC0C Control Register (0x0C, RW) (p272)

`Init = X`, but "**RTC enable … Default setting is disabled**" (bit 0).

| Bit | Field | Meaning (p272) |
|-----|-------|----------------|
| 31:6 | Reserved (0) | — |
| **5** | Restart status (**R**) | "1: Now, RTC is reloading the reload value into counter. 0: not restart period." (busy flag — poll for 0 after a Restart) |
| **4** | Enable **day** alarm | 1: enable / 0: disable |
| **3** | Enable **hour** alarm | 1: enable / 0: disable |
| **2** | Enable **minute** alarm | 1: enable / 0: disable |
| **1** | Enable **second** alarm | 1: enable / 0: disable |
| **0** | **RTC enable** | 1: enable / 0: disable. Default **disabled**. |

**Alarm-enable ambiguity (record faithfully, do not invent):** §24.1 (p270)
says "When turned on the second alarm function, the RTC will auto trigger an
interrupt **each second**. Also, the auto minute, hour alarm can be turned on."
This means RTC0C[1:4] behave as **periodic tick-interrupt enables** — enabling
"second alarm" fires an interrupt every second (→ **INT22 RTC second**),
"minute alarm" every minute (→ **INT25**), "hour alarm" every hour (→ **INT24**),
"day alarm" every day (→ **INT23**). The **specific-time match** in RTC04 is a
separate thing that raises **INT26 "RTC alarm"**. The datasheet does not state
which enable (if any) gates the RTC04 match, and RTC04 has no day field though
RTC0C[4] exists — model RTC0C[1:4] as the five periodic-tick enables per §24.1,
keep RTC0C[4] as a storable bit, and treat RTC04 as the INT26 alarm-match
source. Flag any consumer that relies on the exact gating.

### RTC10 Restart Register (0x10, W [7:0]) (p272)

"When **0x5A** value is written to this register, the reload value register will
be loaded into counter of RTC whenever RTC function is enabled (RTC0C[0]) or
not. After write cycle finish, **RTC0C[5] will auto reset to zero**." So:
write RTC08 → write RTC10 = `0x5A` → RTC0C[5] pulses 1 then clears when the
reload-into-counter completes.

### RTC14 Reset Register (0x14, RW [7:0]) (p272)

"Writing data **0x99** to this register will **reset RTC immediately**." A
distinct soft-reset path from the restart mechanism (used at the start of every
init sequence — see §5).

---

## 5. Operation / programming (§24.4, p273–274)

**Warning (p273):** "Update the RTC whenever the RTC is under **reload busy
state** may cause **RTC dead lock**. It needs a long reset procedure to recover
the dead lock condition." ⇒ a faithful model should honour the RTC0C[5] busy
window and not accept a new Restart while busy.

There are **3 programming modes**, differing in whether/when software waits for
the restart (reload-busy) status RTC0C[5]:

**Mode 1 — No waiting restart status (§24.4.1, p273):**
Initial: (1) `RTC14=0x99` (reset), (2) set time in `RTC08`, (3) delay 1 s,
(4) `RTC14=0x0` (clear reset), (5) `RTC10=0x5A` (restart), (6) `RTC0C[0]=1`
(enable). Update: same but skip the enable step.

**Mode 2 — Waiting restart status at the start (§24.4.2, p273):**
Initial: `RTC14=0x99`; delay 1 s; `RTC14=0x0`; set `RTC08`; `RTC10=0x5A`;
`RTC0C[0]=1`. Update: wait until `RTC0C[5]=0`, set `RTC08`, `RTC10=0x5A`.

**Mode 3 — Waiting restart status at the end (§24.4.3, p274):**
Initial: `RTC14=0x99`; delay 1 s; `RTC14=0x0`; set `RTC08`; `RTC10=0x5A`;
`RTC0C[0]=1`; wait until `RTC0C[5]=0` ("needs about 0 ~ 3 seconds"). Update:
set `RTC08`; `RTC10=0x5A`; wait until `RTC0C[5]=0`.

Common thread for the model: **reset (`0x99`) → load Reload (RTC08) → restart
(`0x5A`) → optionally poll RTC0C[5] → enable (RTC0C[0])**. The `0 ~ 3 s` restart
latency (p274) is a real behaviour worth approximating if firmware polls
RTC0C[5].

---

## 6. AST2050 vs AST2400 / AST2500 / AST2600 (for a faithful QEMU model)

This block is an **ASPEED "counter" RTC**, distinct from what mainline QEMU
models today. Differences a faithful AST2050 model must respect:

1. **Counter-style, not BCD/CMOS.** Time is four independent binary
   up-counters (Sec/Min/Hour/Day in one status word RTC00, p271), read directly.
   There is **no** MC146818/BCD register file and no century/date-of-month/month
   fields — only a raw 15-bit day counter. Firmware computes calendar date in
   software.
2. **Six registers only (0x00–0x14).** The AST2050 RTC is exactly
   Counter/Alarm/Reload/Control/Restart/Reset. The AST2400-family RTC
   (`hw/rtc/*` / device-tree `aspeed,ast2400-rtc`, base `0x1E781000`) exposes a
   different, larger register file (counter1/counter2, alarm, alarm-status,
   control) — a faithful G3 model must implement **this** layout, not the
   AST2400 one, even though the base address `0x1E781000` is the same.
3. **Set-time via Reload + Restart magic, not direct counter writes.** RTC00 is
   read-only; you write RTC08 then pulse `RTC10=0x5A` (p272). Magic constants:
   **restart `0x5A`**, **reset `0x99`** — model these exactly.
4. **Volatile (no battery backup, §24.2 p270).** Reset value is **undefined**
   (`Init = X`), cleared by `PWRSTN_N` (Fig 19, p85). Do not persist across a
   cold reset. (Contrast: PC-style RTCs are battery-backed and non-volatile.)
5. **Five separate VIC interrupts** (second/day/hour/minute/alarm = INT22–26,
   §10 p99), all *both-edge* — not a single consolidated RTC IRQ. The four
   periodic ticks (§24.1 p270) are enabled by RTC0C[1:4]; the RTC04 time-match
   drives the alarm IRQ (INT26).
6. **Time-base is `CLK32K` (~32.768 kHz), register clock is `PCLK`** (Fig 19,
   p85). Counter keeps running when PCLK is gated (§24.1 p270). Model `SecCnt`
   as a 1 Hz tick independent of the APB clock.

`hwreg.h` provides **no** RTC definitions (stub at lines 156–158), so there is
no Raptor cross-check for offsets; the Linux side (Raptor 2.6.28 / mainline
`rtc-aspeed`-style) programs exactly the six registers above.

---

## Quick reference (model constants)

```
RTC base = 0x1E781000   six regs 0x00..0x14, all reset = X (undefined, volatile)
  RTC00 Counter Status  R   [31:17]DayCnt [16:12]HourCnt(0-23) [11:6]MinuCnt(0-59) [5:0]SecCnt(0-59)  (up-counters)
  RTC04 Clock Alarm     RW  [16:12]hour [11:6]min [5:0]sec  (specific-time match -> INT26; no day field)
  RTC08 Reload Value    RW  same layout as RTC00 (write here to set the time)
  RTC0C Control         RW  [5]restart-busy(R) [4]dayAlarmEn [3]hourAlarmEn [2]minAlarmEn [1]secAlarmEn [0]RTC-enable(def 0)
  RTC10 Restart         W   write 0x5A -> Reload copied into counters; RTC0C[5] pulses then self-clears
  RTC14 Reset           RW  write 0x99 -> immediate RTC reset
  time-base = CLK32K (~32.768kHz, div from 24MHz); register clock = PCLK; keeps counting when PCLK gated
  IRQs: INT22 sec / INT23 day / INT24 hour / INT25 min / INT26 alarm  (all both-edge)
  set-time: RTC14=0x99 -> RTC08=time -> RTC14=0x0 -> RTC10=0x5A -> [wait RTC0C[5]=0] -> RTC0C[0]=1
```

# AST2050 / AST1100 GPIO Controller — Datasheet Extract

Source: **ASPEED AST2050/AST1100 A3 Datasheet, V1.05** (dated May 25, 2010).
File: `datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf`
(Note: the task referenced `datasheets/AST2050_..._V1.05.pdf`; the actual in-repo
path is under `datasheets/aspeed/`. A copy also lives in
`asus-kgpe-d16-firmware/datasheets/` and `dell-c410x-firmware/datasheets/`.)

Purpose: authoritative reference for a **faithful QEMU model** of the AST2050
GPIO controller. Every value below carries a datasheet page cite. Where the
datasheet is silent, this is stated explicitly and the `hwreg.h` / Linux
`gpio-aspeed` fallback is used. Printed page numbers equal the physical PDF page
numbers for the body, so `Read` the PDF at the pages cited directly.

Base address: **GPIO = 0x1E78_0000** (physical address = base + offset).
Cross-checks:
- Raptor register header `asus-kgpe-d16-firmware/hwreg.h` line 30 —
  `#define AST_GPIO_BASE 0x1E780000`. **hwreg.h defines only the base address**:
  the "GPIO Registers" comment block (lines 119-122) is empty (it jumps straight
  to the Interrupt Controller section). So every register offset below comes from
  the datasheet, not from hwreg.h.
- The 0x1E78_0000 block is a family of 1-KiB peripheral slots (GPIO 0x…0000, RTC
  0x…1000, Timer 0x…2000, UART1 0x…3000, UART2 0x…4000, WDT 0x…5000, PWM 0x…6000,
  VUART 0x…7000, PUART 0x…8000, LPC 0x…9000, I2C 0x…A000, PECI 0x…B000). GPIO
  itself only uses offsets 0x00-0x58.

---

## 0. Where it lives in the datasheet

| What | Chapter | Page |
|---|---|---|
| GPIO feature summary | §1.3.16 GPIO Controller | p.23 (ToC) |
| GPIO overview | §2.16 GPIO Controller | p.33 (ToC) |
| **GPIO pin summary / ball map (which pins physically exist)** | **§3.5 GPIO Summary** | **p.58-59** |
| **GPIO register definitions** | **§23 GPIO Controller** | **p.262-269** |
| Interrupt Source Table (Table 36) — GPIO is VIC source 20 | §10 | p.99 |

---

## 1. Pin / bank count — what the AST2050 has, and what it must NOT expose

### 1.1 Headline numbers (§23.1 Overview, p.262; §23.2 Features, p.263)

- §23.1 (p.262, verbatim): *"AST2050 / AST1100 Integrates one set of GPIO
  Controller with **maximum 64 control pins** to provide general-purpose
  input/output functions. All the I/O buffers are 3.3V with 5V tolerance
  capability, and all the GPIO pins can be categorized into **7 groups**."*
- §23.2 Features (p.263): *"Support **8 dedicated and 56 shared GPIO pins**"*
  (8 + 56 = 64), *"Support interrupt triggered by all the 64 GPIO pins."*
- **Crucial caveat (p.262, printed in red):** *"This is a superset of registers
  definition. For AST2050/AST1100 chip, **only partial GPIO bits are
  supported**."* → The register file below describes a 64-pin superset; only the
  pins physically bonded out (listed in §3.5) actually exist on silicon. A
  faithful model may implement the full 64-bit register file but must understand
  that reads of unbonded input bits reflect the internal pull (default
  pull-down, §23.2) rather than any external signal.

### 1.2 The banks that actually exist (§3.5 GPIO Summary, p.58-59)

The AST2050 organises GPIO into **letter-named ports of 8 pins** (GPIOA[7:0] …).
§3.5 (p.58-59) lists **exactly banks A through H**. Pin population per bank as
tabulated in §3.5:

| Bank | Pins physically listed in §3.5 | Notes (ball / mux, p.58-59) |
|---|---|---|
| **GPIOA** | A4, A5 only | A4=PHYLINK (D11), A5=PHYPD# (C11); both 16 mA, TTL |
| **GPIOB** | B0-B7 (8) | INTA#, FLBUSY#, FLWP#, GPIOB3, VBCS/LRST#, VBCK, VBDO/WDTRST, VBDI/EXTRST#; Schmitt inputs |
| **GPIOC** | C0-C7 (8) | PECII, PECIO, PWM1-4, SDA5, SCL5 |
| **GPIOD** | D6, D7 only | DDCADAT (B2), DDCACLK (B1); internal Pull-Up |
| **GPIOE** | E0-E7 (8) — **two muxed groups** | Group 1 = VP0-7/TACH0-7; Group 2 = MII/RMII. **Only one group usable at a time, selected by SCU74[27]** (§3.5 note, p.59). Default internal Pull-Down |
| **GPIOF** | F0-F7 (8) | VP8-15 / TACH8-15 |
| **GPIOG** | G0, G1 only | VP16/G0 (Y4), VP17/G1 (Y3) |
| **GPIOH** | H0-H7 (8) | SDA6, SCL6, SDA7/SALT2, SCL7/SALT1, VPAHSYNC/HSYNC, VPAVSYNC/VSYNC, VPADE, VPACLK |

Driving strength (§3.5, p.58-59; §23.2 p.263): **8 of the 64 pins drive 16 mA,
the rest 8 mA** (16 mA pins visible in §3.5: A4, A5, B0, B1, B2, B5, B6-note,
H5, plus 12 mA on the I2C SDA/SCL pins C6/C7/H0-H3). All GPIO have **default
internal pull-down resistors** and **need external pull-ups** (§23.2, p.263).

**What the model must NOT expose:** the AST2050 has **only banks A-H (max 64
pins), addressed entirely by registers GPIO00-GPIO3C**. There is **no GPIOI,
GPIOJ, GPIOK, … GPION** and no register offsets above 0x58. The AST2400 (G4),
AST2500 (G5) and AST2600 (G6) add many more banks (up to GPIO group "AC"/"Y"
etc.) at higher offsets (0x70, 0x78, 0x1E0…); **a faithful AST2050 model must
decode only 0x00-0x58 and treat everything else as reserved/unimplemented.**

> ⚠️ **Discrepancy to flag for the C410X work.** The C410X pin-mapping doc
> (`dell-c410x-firmware/io-tables/gpio-pin-mapping.md`) references **GPIOI,
> GPIOJ, GPIOM, GPION** (e.g. GPIOM0 = PS_ON#, GPION5 = slot-power enable). Those
> bank letters do **not** exist in the AST2050 A3 datasheet register map (banks
> A-H only). That naming almost certainly came from the AST2400/G4 device tree
> the C410X `.dts` is based on, not from AST2050 silicon. For a faithful AST2050
> GPIO model the datasheet is authoritative: **A-H / GPIO00-GPIO3C only.** The
> real host-power/presence/LED lines the C410X drives are reachable within A-H
> or via the off-chip PCA9555 I2C expanders described later in that same doc.

> Minor internal datasheet inconsistency: §23.1 says "7 groups" but §3.5 lists 8
> letter-groups (A-H). Treat the §3.5 pin table as authoritative for which pins
> exist; the register file spans 8 banks (A-H) regardless.

---

## 2. Register map (§23.3, p.263-269; base = 0x1E78_0000)

§23.1 (p.262): *"GPIO implements **16 sets of 32-bit registers** … Each register
has its own specific offset value, ranging from 0x00 to 0x3Ch."* The 16 core
registers are the two 8-bank interrupt/data/direction blocks below (0x00-0x3C);
the debounce registers (0x40-0x58) are **additional** to that count.

Every register's **reset value is 0** ("Init = 0" on every table, p.263-269).
Each 32-bit register packs **four 8-pin banks**, one per byte lane. The two
blocks are:

- **0x00-0x3C** cover banks **A (bits 7:0), B (15:8), C (23:16), D (31:24)**.
- **0x20-0x3C** ("Extended") cover banks **E (7:0), F (15:8), G (23:16),
  H (31:24)**.

| Offset | Register (datasheet name) | Banks (byte lanes 7:0 / 15:8 / 23:16 / 31:24) | R/W | Reset | Page |
|---|---|---|---|---|---|
| 0x00 | GPIO00 GPIO Data Value | A / B / C / D | RW | 0 | p.263 |
| 0x04 | GPIO04 GPIO Direction | A / B / C / D | RW | 0 | p.263 |
| 0x08 | GPIO08 GPIO Interrupt Enable | A / B / C / D | RW | 0 | p.263-264 |
| 0x0C | GPIO0C GPIO Interrupt Sensitivity Type 0 | A / B / C / D | RW | 0 | p.264 |
| 0x10 | GPIO10 GPIO Interrupt Sensitivity Type 1 | A / B / C / D | RW | 0 | p.264 |
| 0x14 | GPIO14 GPIO Interrupt Sensitivity Type 2 | A / B / C / D | RW | 0 | p.264 |
| 0x18 | GPIO18 GPIO Interrupt Status | A / B / C / D | RW (W1C) | 0 | p.265 |
| 0x1C | GPIO1C GPIO Reset Tolerant | A / B / C / D | RW | 0 | p.265 |
| 0x20 | GPIO20 Extended GPIO Data Value | E / F / G / H | RW | 0 | p.265 |
| 0x24 | GPIO24 Extended GPIO Direction | E / F / G / H | RW | 0 | p.266 |
| 0x28 | GPIO28 Extended GPIO Interrupt Enable | E / F / G / H | RW | 0 | p.266 |
| 0x2C | GPIO2C Extended GPIO Interrupt Sensitivity Type 0 | E / F / G / H | RW | 0 | p.266 |
| 0x30 | GPIO30 Extended GPIO Interrupt Sensitivity Type 1 | E / F / G / H | RW | 0 | p.267 |
| 0x34 | GPIO34 Extended GPIO Interrupt Sensitivity Type 2 | E / F / G / H | RW | 0 | p.267 |
| 0x38 | GPIO38 Extended GPIO Interrupt Status | E / F / G / H | RW (W1C) | 0 | p.267-268 |
| 0x3C | GPIO3C Extended GPIO Reset Tolerant | E / F / G / H | RW | 0 | p.268 |
| 0x40 | GPIO40 GPIO Debounce Setting #1 | A / B / C / D | RW | 0 | p.268 |
| 0x44 | GPIO44 GPIO Debounce Setting #2 | A / B / C / D | RW | 0 | p.268 |
| 0x48 | GPIO48 Extended GPIO Debounce Setting #1 | E / F / G / H | RW | 0 | p.268 |
| 0x4C | GPIO4C Extended GPIO Debounce Setting #2 | E / F / G / H | RW | 0 | p.269 |
| 0x50 | GPIO50 Debounce Timer Setting #1 | value in bits [23:0], [31:24] reserved(0) | RW | 0 | p.269 |
| 0x54 | GPIO54 Debounce Timer Setting #2 | value in bits [23:0], [31:24] reserved(0) | RW | 0 | p.269 |
| 0x58 | GPIO58 Debounce Timer Setting #3 | value in bits [23:0], [31:24] reserved(0) | RW | 0 | p.269 |

Byte-lane → bank mapping is explicit in every per-register table (p.263-268),
e.g. GPIO00 (p.263): bits [7:0]=Port GPIOA, [15:8]=GPIOB, [23:16]=GPIOC,
[31:24]=GPIOD; GPIO20 (p.265): [7:0]=GPIOE, [15:8]=GPIOF, [23:16]=GPIOG,
[31:24]=GPIOH.

---

## 3. Data read / write semantics (GPIO00 & GPIO20, p.263 & p.265)

The datasheet labels **GPIO00 / GPIO20 as a single "Data Value Register", each
byte "Port GPIOx[7:0] data register", attribute RW** (p.263, p.265). Direction
is selected by the **separate Direction register** GPIO04 / GPIO24 (p.263,
p.266): per bit `0 = input mode`, `1 = output mode` (reset 0 → **all pins are
inputs at reset**).

- There is **no separate read-input vs write-output register** on the AST2050 —
  a single data register per block (unlike some later Aspeed additions). Writes
  target the output latch; reads target the pin/latch.
- **The datasheet does not spell out the exact read behaviour** (it only marks
  the bits "RW data register"). The standard Aspeed / Linux `gpio-aspeed`
  behaviour — used as the documented fallback here — is:
  - **Write** to a data-register bit sets the **output latch**; that value drives
    the pad only when the corresponding Direction bit = 1 (output mode).
  - **Read** of a data-register bit returns the **live input pin level** when the
    pin is an input (Direction = 0), and returns the **output latch** when the
    pin is an output (Direction = 1).
  - Because reset direction = input and default internal resistor = pull-down
    (§23.2, p.263) with external pull-ups required, an unmodelled/floating input
    reads back its pull-down default (0) unless externally driven.
- A QEMU model should therefore keep an internal output-latch word and an input
  word per block; the value returned on a data-register read is
  `(latch & dir) | (input & ~dir)` per bit.

---

## 4. Interrupt configuration (p.264, p.266-267, p.269) — GPIO is VIC source 20

### 4.1 Enable and status

- **Interrupt Enable** GPIO08 (A-D, p.263-264) / GPIO28 (E-H, p.266): per bit
  `0 = disable interrupt`, `1 = enable interrupt`. Reset 0.
- **Interrupt Status** GPIO18 (A-D, p.265) / GPIO38 (E-H, p.267-268): per bit —
  *Read 0 = no interrupt pending; Read 1 = interrupt pending; Write 0 = no
  operation; **Write 1 = clear interrupt status flag***. i.e. **write-1-to-clear
  (W1C)**. Reset 0.

### 4.2 Sensitivity — three "Type" registers encode the mode

Each pin's trigger mode is encoded across **three sensitivity registers**
(Type 0 / Type 1 / Type 2), one bit per pin in each. The decode table is printed
verbatim at **p.269** (*"The definition of interrupt trigger mode registers
GPIO0C ~ GPIO14, GPIO2C ~ GPIO34"*):

| Type 2 (0x14/0x34) | Type 1 (0x10/0x30) | Type 0 (0x0C/0x2C) | Trigger mode |
|:---:|:---:|:---:|---|
| 0 | 0 | 0 | falling-edge |
| 0 | 0 | 1 | rising-edge |
| 0 | 1 | 0 | level-low |
| 0 | 1 | 1 | level-high |
| 1 | x | x | **dual-edge (both-edge)** |

Per-register bit meanings (consistent with the table):
- **Type 0** GPIO0C/GPIO2C (p.264, p.266): `0 = falling-edge or level-low`,
  `1 = rising-edge or level-high` (selects polarity).
- **Type 1** GPIO10/GPIO30 (p.264, p.267): `0 = edge trigger`,
  `1 = level trigger`.
- **Type 2** GPIO14/GPIO34 (p.264, p.267): `0 = edge or level (use Type1/Type0)`,
  `1 = dual-edge trigger` (overrides — Type 2 = 1 gives both-edge regardless of
  Type1/Type0, hence the `x x` in the table).

Reset for all three = 0 → default mode is **falling-edge** on every pin.
Minimum input pulse width for edge trigger must be **> 2 PCLK cycles** (§3.5
header note, p.58).

### 4.3 Aggregation to the VIC

All 64 GPIO interrupts are OR-reduced into **one VIC line**: §10 Interrupt
Source Table (Table 36, p.99) lists **INT# 20 = "GPIO interrupt", attribute
"Sensitive high level trigger"**. So at the VIC the GPIO aggregate line is
**active-high level**; the per-pin edge/level/both-edge shaping happens inside
the GPIO block (registers above), and any pending, enabled GPIO status bit holds
VIC source 20 asserted until cleared via GPIO18/GPIO38 W1C. A faithful model
raises VIC IRQ 20 whenever `(GPIO18|GPIO38) & (GPIO08|GPIO28) != 0`.

### 4.4 Debounce (input filtering) — GPIO40-GPIO58 (p.268-269)

- Overview (p.262) lists de-bounce options **0ms / 1ms / 5ms / 10ms**; §23.2
  Features (p.263) lists **0ms / 1us / 1ms / 5ms / 10ms**. (Both cited; the
  Features list is the fuller one.)
- **Debounce Setting** registers GPIO40/GPIO44 (A-D) and GPIO48/GPIO4C (E-H),
  one bit per pin in each of the two "Setting #1 / #2" registers. Decode
  (verbatim, p.269):

  | Setting #2 (0x44/0x4C) | Setting #1 (0x40/0x48) | Function |
  |:---:|:---:|---|
  | 0 | 0 | No Debounce |
  | 0 | 1 | Select GPIO50 as debounce timer |
  | 1 | 0 | Select GPIO54 as debounce timer |
  | 1 | 1 | Select GPIO58 as debounce timer |

- **Debounce Timer** registers GPIO50 / GPIO54 / GPIO58 (p.269): value in bits
  **[23:0]** (bits [31:24] reserved, read 0), RW, reset 0.
  **Debounce time = PCLK cycle time × Debounce timer value** (p.269).

### 4.5 WDT reset tolerance — GPIO1C / GPIO3C (p.265, p.268)

Per-bit `0 = the GPIO00/GPIO04 (resp. GPIO20/GPIO24) register bit **will be
reset** by a WDT reset`; `1 = will **not** be reset by WDT reset`. Reset 0 (so by
default GPIO data+direction latches clear on a watchdog reset). Each pin is
individually selectable. This lets firmware keep critical output states (e.g. a
power-hold line) across a watchdog reset. Note the tolerance covers **only the
data and direction registers** (§23.1 lists reset tolerance as "for non-interrupt
related registers only", p.262).

---

## 5. AST2050-vs-newer differences a faithful model must capture

| Aspect | AST2050 (G3, this datasheet) | AST2400/2500/2600 (later G4+) — do NOT copy in |
|---|---|---|
| **Bank count** | **Banks A-H only, max 64 pins.** Registers GPIO00-GPIO3C + debounce 0x40-0x58. | Many more banks (I, J, … up to "AC"/"Y") at higher offsets (0x70, 0x78, 0x1E0…). |
| **Register window** | **0x00-0x58 used; nothing above 0x58.** | Extra data/dir/int blocks, per-bank command-source arbitration, tolerance, input-mask regs at 0x60+. |
| **Data register** | **Single Data Value register per block** (GPIO00, GPIO20), RW; no separate read-only input register. | G5/G6 add separate "Data Read" registers and per-bank register groups. |
| **Interrupt sense encoding** | **3-register Type0/Type1/Type2 scheme** with the p.269 truth table (falling/rising/level-lo/level-hi/dual). | Same 3-register scheme survives, but replicated across the many extra banks. |
| **Command source / coprocessor arbitration** | **Absent** — no per-pin "command source" or ARM-vs-LPC/coprocessor ownership registers. | G4+ add GPIO command-source and input-mask registers. Must not model on AST2050. |
| **Debounce** | GPIO40-4C selectors + 3 timers (GPIO50/54/58), [23:0] each. | Timers and selectors expanded per added banks. |
| **VIC routing** | **Single aggregate line, VIC source 20, level-high** (p.99). | G4+ can route GPIO IRQs more granularly. |
| **"Superset" caveat** | Register file is a documented **superset**; only §3.5 pins are real (p.262). | Later parts populate far more of the space. |
| **GPIOE muxing** | GPIOE has two mutually-exclusive pin groups selected by **SCU74[27]** (p.59). | Pin-mux handled by that generation's SCU, different bits. |

### Bottom line for the QEMU model
Decode a **single 0x1E78_0000 register bank, offsets 0x00-0x58 only**. Implement
two 8-bank blocks (A-D at 0x00-0x1C/0x40-0x44, E-H at 0x20-0x3C/0x48-0x4C) plus
three debounce timers. All resets = 0 (inputs, no interrupts, no debounce). Data
read = `(latch & dir) | (input & ~dir)` per bit; interrupt status is W1C;
aggregate into **VIC line 20 (active-high level)**. Do **not** add G4+ banks
(I/J/M/N…), separate data-read registers, or command-source arbitration.

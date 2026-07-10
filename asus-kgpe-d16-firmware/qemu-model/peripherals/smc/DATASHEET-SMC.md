# AST2050 / AST1100 Static Memory Controller (SMC / SPI Flash) — Datasheet Extraction

Source: **ASPEED AST2050/AST1100 A3 Datasheet V1.05**, PDF at
`datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf`.
Every value cites the printed page number (footer == physical PDF page here).

Cross-referenced against `asus-kgpe-d16-firmware/hwreg.h`, which defines
**`AST_SMC_BASE 0x16000000`** (line 25) — the SMC **control-register** base
below. `hwreg.h` gives no `SMCxx` register offsets, so the datasheet is the
authority for register contents.

Scope for QEMU faithful emulation:
- **Static Memory Controller (SMC)** — control registers at base **0x1600:0000**
  (eight regs, SMC00–SMC1C); flash **data** memory-mapped at **0x1000:0000**
  (CE0/CE1/CE2 windows). This is the **legacy AST2050 SMC**, *not* the AST2400
  FMC at `0x1E620000` — see §6.

---

## 0. Where this block lives (memory map, §9, p97)

Two distinct regions (memory-map table, **page 97**):

| Range | Size | IP Module |
|---|---|---|
| `0000:0000–01FF:FFFF` | 32M | **Static Memory (boot-up default)** — the boot CE aliased to 0x0 for the CPU reset vector |
| `0000:0000–0FFF:FFFF` | 256M | **SDRAM (After Re-map)** — 0x0 becomes SDRAM once AHBC remaps |
| **`1000:0000–15FF:FFFF`** | 96M | **Static Memory** — flash **data** window (CE0/CE1/CE2) |
| **`1600:0000–17FF:FFFF`** | 32M | **Static Memory Controller (SMC)** — the **control registers** |

So there are two addresses to keep straight:
- **SMC control registers → base `0x1600:0000`** (`AST_SMC_BASE` in `hwreg.h`).
- **Flash data (what code executes / reads) → base `0x1000:0000`** (96 MB span =
  three 32 MB chip-select windows, see §2).

Chapter location (via the §9 memory map, per request):
- **Chapter 11 "Static Memory Controller"** — pages **100–112**
  (§11.1 overview p100, Fig 57 memory-space organization p101, §11.2 timing
  p102–104, §11.3 register base `0x1600:0000` p105–112).

Interrupt line (§10, p99): **INT19 "SMC interrupt", "Sensitive high level
trigger"** (used by the NOR-ACK-timeout and NAND-timer/R-B# interrupts in
SMC10).

---

## 1. Overview — what the AST2050 SMC actually is (§11.1, p100)

"Static Memory Controller (SMC) implements **8 sets of 32-bit registers** … to
program the various static memory interfaces … Each register has its own
specific offset value." (p100)

**Critical AST2050 caveat (p100, red text):**
> "This is a **superset** of registers definition. **For AST2050/AST1100 chip,
> only SPI flash type interface is supported.**"

So although the register set describes **NOR, NAND and SPI** flash, only the
**SPI** path is functional silicon on the AST2050/AST1100. A faithful model
should implement the register **layout** in full (firmware may still poke NOR/
NAND fields) but only the **SPI** behaviour needs to actually work. The
feature-comparison tables (§1.4/§1.5, p27–28) confirm: AST2050 / AST1100
"**Flash Memory Controller = SPI Flash**" (whereas AST2100 also lists NOR/NAND).

**Three chip selects, base 0x10000000 (§11.1, p100):**
> "AST2050/AST1100 also provides **three chip select pins (CE0, CE1 and CE2)** …
> each of which can also be programmed to be any one of the three flash memory
> types … each chip select pin is assigned to different non-overlapping address
> regions."
- **Base address of CE0: `0x10000000`**
- **Base address of CE1: `0x10000000 + (Segment Size)`**
- **Base address of CE2: `0x10000000 + (Segment Size × 2)`**

"Segment Size is determined by SMC00 Bit[1:0]." (p100; see Figure 57, p101.)
Default **Segment Size = 32 MB** (SMC00[1:0]=00), so on the KGPE-D16 the windows
land at:

| CE | Default type | Window (32 MB segments) |
|----|--------------|-------------------------|
| **CE0** | NOR | **`0x10000000`–`0x11FFFFFF`** |
| **CE1** | NAND | **`0x12000000`–`0x13FFFFFF`** |
| **CE2** | SPI | **`0x14000000`–`0x15FFFFFF`** |

That is exactly the 96 MB "Static Memory" region at p97. (The task's "boot flash
mapped at ~0x10000000 / 0x14000000" = **CE0 at 0x10000000** and **CE2 at
0x14000000** under the default 32 MB segmentation.)

**Boot behaviour (§11.1, p100):**
> "Only one of the three chip select pin can be assigned, by **external trapping
> resistors**, to support CPU boot code fetches (**starting address
> 0x00000000**). When selected, the addressing space of the assigned chip select
> pin will additionally include CPU boot code addressing space as well."

Default flash type per CE (p100): **CE0 = NOR, CE1 = NAND, CE2 = SPI.** Note the
AST2050 caveat: since only SPI is functional, the boot flash is an **SPI** device
on whichever CE is strapped, and its type field must be set to SPI (SMC00[…]=1x).

**Reset-vector aliasing for the model:** at power-up the strapped boot CE is
**also** visible at `0x00000000` (the "Static Memory (boot-up default)" 32 MB
window, p97). After the AHB Bus Controller remap (`AHBC8C` =
`AHB_ADDR_REMAP_REG` = `0x1E60008C` in `hwreg.h`), `0x00000000` switches to
**SDRAM** (the "SDRAM (After Re-map)" 256 MB window, p97). A faithful SoC model
must alias boot-flash → 0x0 until that remap bit flips.

---

## 2. Flash memory-space organization (Figure 57, §11.1, p101)

Figure 57 shows the three CE windows stacked, sized by the segment selection:
- **4 MB**, **8 MB**, **16 MB**, or **32 MB** per segment (CE0 lowest, then CE1,
  then CE2), matching **SMC00[1:0]** = 11/10/01/00.
- Total decoded flash window = 3 × Segment Size (max 96 MB at 32 MB, = the p97
  Static-Memory span).

Timing waveforms (§11.2, p102–104) cover NOR read/write (Fig 58/59), NOR ACK
control (Fig 60/61), **SPI R/W (Fig 62)**, **SPI dual-input R/W (Fig 63)**, and
NAND (Fig 64). For a functional model the SPI ones (Fig 62/63) are what matter;
they show the classic Mode-0/Mode-3 SPI clock, MSB-first shift, and a
**"Data Latch Point"** on the rising edge, plus dual-I/O (2 bits/clock).

---

## 3. Register map (Chapter 11, base 0x1600:0000, §11.3 p105)

Eight registers, offsets **0x00–0x1C** (§11.1 list, p100; details p105–112):

| Off | Name (datasheet) | R/W | Reset | Purpose |
|-----|------------------|-----|-------|---------|
| 0x00 | SMC00 CE0 Segment AC Timing Register | RW | **`0x00000240`** | Per-CE flash **type** select, per-CE **write-enable**, **segment size**. (p105) |
| 0x04 | SMC04 CE0 Control Register | RW | **0** | CE0 control; **layout depends on CE0 flash type** (SMC00[5:4]). (p105–108) |
| 0x08 | SMC08 CE1 Control Register | RW | **0** | CE1 control; layout depends on CE1 type (SMC00[7:6]). (p105–108) |
| 0x0C | SMC0C CE2 Control Register | RW | **0** | CE2 control; layout depends on CE2 type (SMC00[9:8]). (p105–108) |
| 0x10 | SMC10 Misc. Control Register | RW | **0** | NOR timer / NAND timer + ECC-mode / WP# / R-B# control + their interrupts. (p109–110) |
| 0x14 | SMC14 NAND ECC Generation Control/Status | RW | **0** | NAND ECC gen enable/reset + read-back ECC value. (p111) |
| 0x18 | SMC18 NAND ECC check value | RW | **0** | SW-supplied stored ECC for the HW check. (p111–112) |
| 0x1C | SMC1C NAND ECC check result | **R** | **0** | NAND ECC check outcome (pass / correctable / uncorrectable + positions). (p112) |

(SMC14/18/1C are NAND-only; irrelevant on the SPI-only AST2050 except as
storable/zero registers.)

---

## 4. SMC00 — CE0 Segment AC Timing Register (0x00, RW, Init = 0x00000240) (p105)

| Bit | Field | Values |
|-----|-------|--------|
| 31:13 | Reserved (0) | — |
| **12** | Enable CE2 flash memory **segment write** | 0: read-only segment; 1: read/write |
| **11** | Enable CE1 flash memory segment write | 0: read-only; 1: read/write |
| **10** | Enable CE0 flash memory segment write | 0: read-only; 1: read/write |
| **9:8** | **CE2 flash type** selection | 00: NOR; 01: NAND; **1x: SPI NOR (default)** |
| **7:6** | **CE1 flash type** selection | 00: NOR; **01: NAND (default)**; 1x: SPI NOR |
| **5:4** | **CE0 flash type** selection | **00: NOR (default)**; 01: NAND; 1x: SPI NOR |
| 3:2 | Reserved | — |
| **1:0** | **Segment size** selection | **00: 32 MB (default)**; 01: 16 MB; 10: 8 MB; 11: 4 MB |

**Reset value 0x00000240 decoded** (self-consistency check): `0x240` = bit 9 +
bit 6 ⇒ **[9:8]=10 → CE2 = SPI (default)**, **[7:6]=01 → CE1 = NAND (default)**,
**[5:4]=00 → CE0 = NOR (default)**, **[1:0]=00 → 32 MB segments**, and write-
enable bits [12:10]=0 ⇒ **all segments read-only at reset**. This matches the
per-CE defaults stated in §11.1 (p100). Model this exact reset value.

---

## 5. SMC04 / SMC08 / SMC0C — CE Control Registers (0x04/0x08/0x0C, RW, Init = 0)

"The definition of this register **depends on the selected flash memory type**"
i.e. on SMC00[9:4] for that CE (p105). Three sub-layouts follow. **For the
SPI-only AST2050, the SPI layout is the operative one.**

### 5a. SPI Flash Interface layout (p107–108) — the AST2050 path

| Bit | Field | Values |
|-----|-------|--------|
| 31:28 | Reserved | — |
| **27:24** | CE# **inactive** pulse width | 0000: 16T (1T = 1 HCLK) … 1111: 1T |
| **23:16** | **Command data** | data byte used for Fast Read or Byte Write CMD phase |
| 15:13 | Reserved | — |
| **12** | Disable SPI flash **read-command merge** | 0: enable (default — merges continuous-address reads within 16 clocks); 1: disable (perf penalty) |
| 11 | Reserved | — |
| **10:8** | **SPI clock frequency** (t-CK) | 000: HCLK/16 (default); 001: /14; 010: /12; 011: /10; 100: /8; 101: /6; 110: /4; 111: /2 |
| **7:6** | Dummy cycles before data for fast read | 00: 0 Byte (default); 01: 1; 10: 2; 11: 3 |
| **5** | MSB/LSB first control | 0: **MSB first** (default for boot code); 1: LSB first |
| **4** | Clock **Mode_0 / Mode_3** selection | 0: Mode 0 (clock idle 0); 1: Mode 3 (clock idle 1) |
| **3** | Enable **dual data input** mode | 0: 1 bit/clock; 1: 2 bits/clock (doubles data rate) |
| **2** | **User Mode CE# active control** | in User Mode, SPI cycle stays active (CE# low) until this bit set to 1 |
| **1:0** | **Command Mode** | 00: Normal Read (03h + addr + read 1/2/3/4 B); 01: Fast Read; 10: Normal Write; 11: User Mode (raw read/write 1–4 B) |

Notes (p108): in non-User modes the address space supports up to **16 MB** max;
in User Mode all decoded addresses in the segment are valid and data is
read/written LSB-byte-first of each 32-bit AHB word (flexible custom-command
path). Default clock **HCLK/16**, **MSB-first**, **Normal Read (03h)** — this is
the reset boot-read behaviour a model must reproduce.

### 5b. NOR Flash Interface layout (p108–109) — present but non-functional on AST2050

| Bit | Field |
|-----|-------|
| 31:30 | Timer value unit (00: 0.5 µs, 01: 1.0 µs, 10: 2.0 µs, 11: 4.0 µs; value at SMC10[31:24]) |
| 29:28 | Operation mode (0x: Normal; 10: t-WEL/t-OEL long mode; 11: ACK control mode) |
| 27:24 | t-CEH — CE# high pulse width per AHB command (0000: no requirement; 0001: >2T … 1111: >16T) |
| 23:20 | t-ACT2CE — OE#/WE# high to CE# high delay |
| 19:16 | t-WEH — WE# high pulse width |
| 15:12 | t-WEL — WE# low pulse width |
| 11:8 | t-OEH — OE# high pulse width |
| 7:4 | t-OEL — OE# low pulse width |
| 3:0 | t-CE2ACT — CE# low to OE#/WE# low delay (0000: 16T default … 1111: 1T) |

Read data latched on the rising edge of OE#; write data on the rising edge of
WE# (p109).

### 5c. NAND Flash Interface layout (p105–107) — present but non-functional on AST2050

| Bit | Field |
|-----|-------|
| 31:28 | t-WEH — WE# pulse width high (0000: 16T=16 HCLK … 1111: 1T) |
| 27:24 | t-WEL — WE# pulse width low |
| 23:20 | t-REH — RE# pulse width high |
| 19:16 | t-REL — RE# pulse width low |
| 15:12 | t-CESH — CE# active-to-command-start / command-end-to-CE#-deassert delay |
| 11:10 | t-WTR — WE# rising to RE# falling delay (00: 32T; 01: 24T; 10: 16T; 11: 8T) |
| 9:4 | t-R — Boot-mode read-command busy wait (000000: ~63 µs … 111111: ~1 µs; 1 MHz-based timer) |
| 3 | User-mode row address cycle selection (0: 3-cycle; 1: 2-cycle) |
| 2 | User-mode CE# active control (0: active only during command; 1: always active) |
| 1 | Random-read capability (boot mode only) |
| 0 | Operation mode (0: **Boot Mode** default; 1: User Mode) |

Boot-Mode NAND requires 2048-byte pages, page-read cmd `00h+2CA+3RA+30h`,
random-read `05h+2CA+E0h`, busy < 64 µs, first block valid/no-ECC (p107).

---

## 6. SMC10 / SMC14 / SMC18 / SMC1C — misc + NAND ECC (NAND-only, zero on AST2050)

### SMC10 Misc. Control Register (0x10, RW, Init = 0) (p109–110)

| Bit | Field |
|-----|-------|
| 31:24 | NOR timer value setting (unit at SMC04/08/0C[31:30]) |
| 23 | NOR ACK# control **timeout interrupt status** (W1C) |
| 22 | NOR ACK# control timeout interrupt enable |
| 21 | NAND timer interrupt status (W1C) |
| 20 | NAND timer interrupt enable |
| 19 | NAND timer enable |
| 18:8 | NAND timer value setting (0: disable; else value × 4 µs) |
| 7:6 | **NAND ECC mode** (00: 256 B; 01: 512 B; 10: 1024 B; 11: 2048 B) |
| 5 | WP# output value (0: write disabled; 1: enabled) |
| 4 | WP# pin supported |
| 3 | R/B# pin input value (**R**; 0: busy, 1: normal) |
| 2 | R/B# rising-edge detect status (W1C) |
| 1 | Enable R/B# status interrupt |
| 0 | R/B# pin supported |

Note (p110): "R/B# and WP# pins not only can be used for NAND flash, **NOR flash
also can use it**." These interrupt sources drive **INT19** (§10, p99).

### SMC14 NAND ECC Generation Control/Status (0x14, RW, Init = 0) (p111)
[29] ECC Reset Enable, [28] ECC Generation Enable (max 2048-byte SECDED),
[27:0] ECC Value (**R**). Reserved [31:30].

### SMC18 NAND ECC check value (0x18, RW, Init = 0) (p111–112)
[27:0] SW-written stored ECC (operates against generated ECC for a HW check;
"only useful for Flash Read"). Reserved [31:28].

### SMC1C NAND ECC check result (0x1C, R, Init = 0) (p112)
[31] Unrecoverable error; [30] Field error (1-bit, no correct needed);
[29] Recoverable error (need SW correct at [13:0]); [28] Check pass;
[27:16] ECC accumulate counter; [13:3] recoverable error **byte** position;
[2:0] recoverable error **bit** position. Reserved [15:14].

On the SPI-only AST2050 these four registers are inert (model as storable/zero).

---

## 7. AST2050 legacy SMC vs AST2400+ FMC (for a faithful QEMU model)

**This is the single most important difference to capture: the AST2050 SMC is
NOT the AST2400 FMC.**

1. **Different base + register layout.**
   - AST2050 **SMC**: control regs at **`0x16000000`** (`AST_SMC_BASE`), 8 regs
     `SMC00–SMC1C` (this file); flash data window at **`0x10000000`**
     (CE0/CE1/CE2, §11.1 p100).
   - AST2400+ **FMC** (Firmware Memory Controller): control regs at
     **`0x1E620000`**, with separate SPI masters at `0x1E630000`/`0x1E631000`;
     a completely different register file (CE type reg, CE control, interrupt
     control, command control, per-CE control 0x10–0x1C, **segment-address regs
     0x30–0x3C**, DMA control). AST2400 flash windows are at **`0x20000000`**
     (FMC) and **`0x30000000`** (SPI), *not* 0x10000000.
   A faithful G3/AST2050 model must implement the **0x16000000 / 8-register**
   block and the **0x10000000** data windows — do **not** reuse the FMC layout.
2. **Mainline QEMU does not model this block.** QEMU's ASPEED flash model
   (`hw/ssi/aspeed_smc.c`) targets the **AST2400+ FMC/SPI** controllers only;
   there is **no** device for the legacy `0x16000000` SMC. A faithful AST2050
   model needs a **new device**: 8 MMIO control registers at 0x16000000 + three
   MMIO-mapped flash windows at 0x10000000/0x12000000/0x14000000 + the reset-time
   alias of the boot CE to 0x00000000 (cleared by the AHBC remap at 0x1E60008C).
3. **SPI-only silicon, superset registers.** Per p100 the register set describes
   NOR/NAND/SPI but **only SPI works** on AST2050/AST1100. NAND ECC (SMC14/18/1C)
   and the NOR/NAND timing sub-layouts exist in the register map but are not
   functional — model the layout, but only SPI needs real behaviour.
4. **Three CEs, 4/8/16/32 MB segments, boot-CE strapping.** CE0/1/2 with default
   types NOR/NAND/SPI, segment size from SMC00[1:0] (default 32 MB), and exactly
   **one** CE strapped as the boot device aliased to 0x0 (§11.1 p100). AST2400
   FMC uses per-CE segment-address registers instead of a single global segment
   size.
5. **`hwreg.h` cross-check:** only `AST_SMC_BASE 0x16000000` is defined (line
   25); no per-register offsets and **no** 0x10000000 flash-window macro. The
   register contents here have no Raptor fallback — datasheet is authoritative.
6. **Reset defaults to reproduce:** SMC00 = **0x00000240** (CE0 NOR / CE1 NAND /
   CE2 SPI, 32 MB, read-only) (p105); SMC04/08/0C/10/14/18/1C = **0** (p105–112);
   SPI read defaults = HCLK/16, MSB-first, Normal-Read 03h (p107–108).

---

## Quick reference (model constants)

```
SMC control regs base = 0x16000000   (hwreg.h AST_SMC_BASE)   8 regs SMC00..SMC1C
Flash DATA window     = 0x10000000   CE0=0x10000000  CE1=+segsz  CE2=+2*segsz
  default 32MB segments -> CE0 0x10000000 / CE1 0x12000000 / CE2 0x14000000  (p100/p97)
  boot CE also aliased to 0x00000000 until AHBC remap (0x1E60008C) -> SDRAM
  AST2050/AST1100 = SPI flash ONLY (register set is a NOR/NAND/SPI superset, p100)

  SMC00 Seg/Type   RW reset 0x00000240  [12:10]CE2/1/0 write-en  [9:8]CE2type [7:6]CE1 [5:4]CE0 (00NOR 01NAND 1xSPI)  [1:0]segsz(00=32M 01=16M 10=8M 11=4M)
    reset decode: CE0=NOR CE1=NAND CE2=SPI, 32MB, all read-only
  SMC04/08/0C CE0/1/2 Ctrl  RW reset 0  (layout depends on that CE's type)
    SPI: [27:24]CE# inactive [23:16]cmd data [12]disable read-merge [10:8]clk(000=HCLK/16 def..111=/2)
         [7:6]fast-read dummy [5]MSB(0)/LSB [4]Mode0/3 [3]dual-in [2]userCE# [1:0]cmd(00 NormRead03h/01 FastRead/10 NormWrite/11 User)
  SMC10 Misc       RW reset 0  (NOR/NAND timers, NAND ECC mode [7:6], WP#/R-B# + interrupts -> INT19)
  SMC14/18/1C NAND ECC  reset 0  (NAND-only; inert on AST2050)

  IRQ = INT19 (level).  NOT the AST2400 FMC (that is 0x1E620000 / window 0x20000000) — mainline QEMU models the FMC, not this legacy SMC.
```

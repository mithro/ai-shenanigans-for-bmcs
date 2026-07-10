# AST2050 / AST1100 DDR2 SDRAM Controller — Datasheet Extract

Source: **ASPEED AST2050 / AST1100 A3 Datasheet, Version 1.05 (May 25, 2010)**,
`datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf`.
Chapter **17 "SDRAM Memory Controller"**, printed/PDF pages **183–203**
(the memory map §9 places the SDRAM controller in its own chapter; in this
datasheet that is §17, not §11/§12 which are the Static Memory Controller and
AHB Bus Controller respectively). PDF page index maps 1:1 to the printed page
number in the footer.

Purpose: reference for a **faithful QEMU DDR2 `aspeed_sdmc`-style model** of the
AST2050 (base `0x1E6E0000`, **DDR2**, not the AST2400/G4 DDR3 controller).

Every value below is cited to a datasheet page. Where the datasheet is silent,
that is stated explicitly, and the `platform.S` / `hwreg.h` firmware fallback is
given. Firmware cross-reference files:
- `asus-kgpe-d16-firmware/platform.S` (Raptor DDR2 `lowlevel_init`)
- `asus-kgpe-d16-firmware/hwreg.h` (register offset macros)
- `asus-kgpe-d16-firmware/DDR2-INIT-REVERSE-ENGINEERING.md` (prior RE, corrected below)

> **Terminology.** The datasheet calls these registers **MCRxx** ("Memory
> Controller Register" at offset `xx`). `hwreg.h` uses `SDRAM_*_REG` names.
> Both refer to the same offset from base `0x1E6E0000`.

---

## 0. Key facts up front

| Fact | Value | Datasheet page |
|------|-------|----------------|
| Base address | `0x1E6E_0000` (MCR) | p183 |
| Register count documented | **30** registers | p183 |
| Protection key (unlock) | `0xFC600309` | p184 |
| Max addressing space | **256 MB** (28-bit internal address) | p201 |
| Internal data-bus width | always **64-bit** | p202 |
| Refresh clock reference | **12 MHz** (`Refresh Freq = 12MHz / MCR0C[15:8]`) | p186 |
| MRS/EMRS have distinct **DDR vs DDR2** bit layouts | yes (MCR2C/MCR30) | p191–192 |

**Important structural finding:** the datasheet's 30-register list on p183 goes
`… MCR48, MCR60 …` — i.e. offsets **`0x4C`, `0x50`, `0x54`, `0x58`, `0x5C` are
NOT documented** in the A3 datasheet. `hwreg.h` names `0x4C` (unnamed) and
`0x50–0x5C` as `SDRAM_ECC_*`, and `platform.S` writes `0x00000000` to all of
them, but **there is no ECC register block in this datasheet**. The MCR04
capacity field (p185) *mentions* ECC memory overhead but no ECC control/status
register is defined. A faithful model should treat `0x4C`–`0x5C` as
reserved/zero (writes accepted, read back what firmware wrote or 0). See §3 note.

---

## 1. MCR00 — Protection Key Register (offset `0x00`)  [p184]

- **Bits [31:0], RW.** `Init = 0`.
- **Unlock value = `0xFC600309`** (datasheet: "The password of the protection
  key is **0xFC600309**"). Confirms `platform.S` line 288 (`ldr r1,=0xfc600309`).
- **Write semantics:** write `0xFC600309` → **unlock** MCR04–MCR7C for writing;
  write **any other value** → **lock** the registers.
- **Read-back semantics (critical for the model):** "Reading back SDRAM
  registers is irrelevant with this register." The register does **not** read
  back the written key. Instead:
  - **Locked** (reset state): read-back = `0x00000000`.
  - **Unlocked:** read-back = `0x00000001`.
- Reset/initial state is **locked**. Firmware must re-lock after init (write 0).
  `platform.S` verifies unlock by reading and comparing to `#0x01` (lines
  291–294), and re-locks with `0x00000000` at `reg_lock` (lines 594–596).

**Model note:** MCR00 is a 1-bit lock latch exposed as read-only `0`/`1`, *not*
a value register. This differs from the AST2400 aspeed_sdmc protection key
(`0xFC600309` is the same magic there too, but the AST2400 model reports the
unlocked state differently — verify against your G4 model).

---

## 2. MCR04 — Configuration Register (offset `0x04`)  [p185–186]

`Init = 0`, all fields RW except bit 6 (R). This is the register firmware writes
to declare the installed DRAM geometry, and the register U-Boot/Linux reads back
to discover it.

| Bits | R/W | Field | Encoding (datasheet p185–186) |
|------|-----|-------|-------------------------------|
| 31:12 | — | Reserved (0) | |
| **11** | RW | **Select bank mode** | 0 = 4-bank, 1 = 8-bank. "Must be set exactly the same as the SDRAM specification, or the controller will malfunction." |
| **10** | RW | **Enable SDRAM auto pre-charge** | 0 = disable, 1 = enable. (Disable = perf penalty; "insurance policy only".) |
| **9:8** | RW | **Select SDRAM data bus width** | `01` = 16-bit (DQ15–DQ0); **others = Reserved**. |
| **7** | RW | **Select DRAM burst length** | 0 = BL2 (1 clock/transaction), 1 = BL4 (2 clocks). |
| **6** | **R** | **SDRAM Bus Width Status** | 0 = 32 bits, 1 = 16 bits. Read-only, **decoded from bits [9:8]**. "Used for AST2000 backward compatible." |
| **5:4** | RW | **Graphics (VGA) memory aperture size** | 00=8 MB, 01=16 MB, 10=32 MB, 11=64 MB. Set from external strap **SCU70[3:2]** (p217); must match the strap. Graphics memory is at the highest address segment. |
| **3:2** | RW | **Total data memory capacity** | 00 = ≤32 MB, 01 = 64 MB, 10 = 128 MB, 11 = 256 MB. (Does *not* count ECC overhead.) |
| **1:0** | RW | **Number of column-address bits** | 00 = 9 col bits; 01 = 10; 10 = 11; 11 = Reserved. Per-density JEDEC mapping listed (DDR2 256Mb/512Mb/1Gb/2Gb x8/x16). |

### 2.1 There is NO explicit "DDR vs DDR2 type" bit in MCR04

The datasheet MCR04 has **no DRAM-type selector**. DDR-vs-DDR2 is expressed
**only** through the mode-register encodings (MCR2C/MCR30, which have separate
"For DDR SDRAM type" and "For DDR2 SDRAM type" bit definitions, p191–192) and
the I/O-buffer voltage standard (MCR60, SSTL18 vs SSTL2, p196). This **corrects**
`DDR2-INIT-REVERSE-ENGINEERING.md §4.7.4`, which guessed "bit 7 = DDR2 mode"
and "bit 10 = 8 banks" — those are wrong; bit 7 is burst length and bit 10 is
auto-precharge per the datasheet.

### 2.2 Cross-check against Raptor `platform.S` CONFIG_*_DDRII values

`platform.S` (lines 369–377) loads MCR04 from a compile-time constant, then ORs
in `SCU70[3:2] << 2` (the VGA size strap) into bits [5:4]:

**`CONFIG_1G_DDRII` → `0x00000D89`** decodes (datasheet fields):
- bit11 = 1 → **8-bank**
- bit10 = 1 → auto pre-charge enabled
- bits9:8 = `01` → **16-bit** data bus
- bit7 = 1 → **BL4**
- bits5:4 = `00` → 8 MB VGA aperture (base, before OR with strap)
- bits3:2 = `10` → **128 MB total capacity**
- bits1:0 = `01` → **10 column-address bits**

**`CONFIG_512M_DDRII` → `0x00000585`** decodes:
- bit11 = 0 → **4-bank**
- bit10 = 1 → auto pre-charge enabled
- bits9:8 = `01` → **16-bit** data bus
- bit7 = 1 → **BL4**
- bits3:2 = `01` → **64 MB total capacity**
- bits1:0 = `01` → **10 column-address bits**

**Interpretation:** the "1G"/"512M" in the config names refer to the **per-chip
DDR2 device density in bits** (1 Gbit / 512 Mbit), giving **128 MB / 64 MB total
board DRAM** respectively — NOT 1 GB/512 MB. This corrects the
`DDR2-INIT-…md` §2.1 overview claim of "Max DRAM 512 MB or 1 GB": the datasheet
hard-caps total capacity at **256 MB** (p185 bits3:2 and p201).

---

## 3. Full register map, `0x00`–`0x7C` (+ `0x100/0x120/0x170`)

Reset values are the datasheet **`Init =`** annotations at each register header.
Where firmware programs a value, the Raptor `platform.S` value is shown for the
QEMU model's reference (firmware-programmed, *not* a reset value).

| Offset | MCR | Name | `Init=` | Raptor writes | Datasheet page |
|--------|-----|------|---------|---------------|----------------|
| `0x00` | MCR00 | Protection Key | 0 (locked→rd 0) | `0xFC600309` unlock / `0` lock | p184 |
| `0x04` | MCR04 | Configuration | 0 | `0xD89`/`0x585` +strap | p185 |
| `0x08` | MCR08 | Graphics Memory Protection | 0 | `0x0011030F` | p186 |
| `0x0C` | MCR0C | Refresh Timing | 0 | `0x5A08` then `0x5A21` | p186–187 |
| `0x10` | MCR10 | Normal-Speed AC Timing #1 | 0 | `0x22201725` | p187–188 |
| `0x14` | MCR14 | Low-Speed AC Timing #1 | 0 | `0x22201725` | p187–188 |
| `0x18` | MCR18 | Normal-Speed AC Timing #2 | 0 | `0x1E29011A` | p188–189 |
| `0x1C` | MCR1C | Low-Speed AC Timing #2 | 0 | `0x1E29011A` | p188–189 |
| `0x20` | MCR20 | Normal-Speed Delay Control | 0 | `0x00C82222` | p189–190 |
| `0x24` | MCR24 | Low-Speed Delay Control | 0 | `0x00C82222` | p189–190 |
| `0x28` | MCR28 | Mode Setting Control | 0 | `5,7,3,1` sequence | p190 |
| `0x2C` | MCR2C | MRS/EMRS2 Mode Setting | **X** | `0x732`→`0x632` | p190–191 |
| `0x30` | MCR30 | EMRS/EMRS3 Mode Setting | **X** | `0x040`/`0x3C0`/`0x040` | p191–192 |
| `0x34` | MCR34 | Power Control | 0 | `0x01` then `0x7C03` | p192–194 |
| `0x38` | MCR38 | Page Miss Latency Mask | 0 | `0xFFFFFF82` | p195 |
| `0x3C` | MCR3C | Priority Group Setting | 0 | `0x00000000` | p195 |
| `0x40` | MCR40 | Maximum Grant Length #1 | 0 | `0x00000000` | p195–196 |
| `0x44` | MCR44 | Maximum Grant Length #2 | 0 | `0x00000000` | p195–196 |
| `0x48` | MCR48 | Maximum Grant Length #3 | 0 | `0x00000000` | p195–196 |
| `0x4C` | — | **Undocumented** (fw writes 0) | — | `0x00000000` | (absent) |
| `0x50` | — | **Undocumented** (`hwreg.h`: ECC Ctrl) | — | `0x00000000` | (absent) |
| `0x54` | — | **Undocumented** (`hwreg.h`: ECC Seg En) | — | `0x00000000` | (absent) |
| `0x58` | — | **Undocumented** (`hwreg.h`: ECC Scrub) | — | `0x00000000` | (absent) |
| `0x5C` | — | **Undocumented** (`hwreg.h`: ECC 1st Err) | — | `0x00000000` | (absent) |
| `0x60` | MCR60 | IO Buffer Mode | 0 | `0x032AA02A` | p196–197 |
| `0x64` | MCR64 | DLL Control #1 | 0 | `0x00050000`→`0x002D3000` | p197–198 |
| `0x68` | MCR68 | DLL Control #2 | 0 | `0x02020202` | p198 |
| `0x6C` | MCR6C | DLL Control #3 | 0 | `0x00909090` | p198–199 |
| `0x70` | MCR70 | Testing Control/Status | 0 | `0x00000000` | p199–200 |
| `0x74` | MCR74 | Testing Start Addr & Length | 0 | `0x00000000` | p200 |
| `0x78` | MCR78 | Testing Fail DQ Bit | 0 | `0x00000000` | p200 |
| `0x7C` | MCR7C | Test Initial Value | 0 | `0x00000000` | p201 |
| `0x100` | MCR100 | AST2000-compat SCU Password | **`0x000000A8`** (R) | — | p201 |
| `0x120` | MCR120 | AST2000-compat SCU MPLL Param | 0 | `0x00004C41` | p201 |
| `0x170` | MCR170 | AST2000-compat SCU HW-Strap Value | 0 (R, all `0`) | — | p201 |

### 3.1 Register-by-register detail (fields the model must implement)

**MCR08 Graphics Memory Protection [p186]** — bits[31:0] RW, `Init=0`.
Bit[n] = "protect REQn": 1 → all accesses from REQn are address-remapped to the
highest memory space (the VGA aperture defined by MCR04[5:4]); 0 → not changed.
(REQ list is the Fixed-Priority table, §5 below.)

**MCR0C Refresh Timing [p186–187]** — `Init=0`.
- [31:16] Reserved.
- **[15:8] Period of high-priority refresh cycle.** `SDRAM Refresh Frequency =
  12 MHz / MCR0C[15:8]`. Raptor `0x5A` = 90 → 133.3 kHz → **7.5 µs** period
  (JEDEC DDR2 = 7.8 µs; within spec).
- [7:6] Reserved.
- **[5] Enable low-priority refresh** (fills idle bandwidth; auto-issues once the
  refresh counter passes half the [15:8] period; up to 8 cycles/request).
- **[4] Force all banks pre-charged before refresh** ("insurance policy only").
- **[3:0] Refresh cycles per refresh period.** 0000 = disabled; 0001 = 1;
  0010 = 2; … `1xxx` = 8. **"DRAM read data will be valid only if refresh is
  enabled, else the read-back data will be random value."**
- Raptor: initial `0x5A08` = period 0x5A, **8 cyc/period**, low-pri **off**;
  final `0x5A21` = period 0x5A, **1 cyc/period**, low-pri **on**. (Corrects the
  RE-doc's guess that "bit 5 = full refresh rate".)

**MCR10/14 Normal/Low-Speed AC Timing #1 [p187–188]** — `Init=0`. Fields:
`[31:28] t-RP` (0000=2T…1111=17T), `[27:24] t-RRD` active-to-active (0000=1T…16T),
`[23:20] t-RCD` active-to-r/w (0000=2T…17T), `[19:16] t-APD`, `[15:12] t-RTP`
read-to-precharge, `[11:8] t-WTP` write-to-precharge, `[7:4] t-RTW` read-to-write
(0000=2T…17T), `[3:0] t-WTR` write-to-read (0000=2T…17T).

**MCR18/1C Normal/Low-Speed AC Timing #2 [p188–189]** — `Init=0`. Fields:
`[31:30] Reserved`, `[29:24] t-XSNR` (000010=3T…111111=64T; must be >2),
`[23:21] Write latency` (000=1T…100=5T; **"For DDR2 write latency = CAS
latency − 1T"** ← DDR2-specific), `[20:16] t-RAS` active-to-min-precharge
(00000=1T…11111=32T), `[15:12] Reserved`, `[11:8] tMRD` mode-set interval
(0000=1T…16T), `[7:6] Reserved`, `[5:0] t-RFC` refresh interval (000000=2T…65T).

**MCR20/24 Normal/Low-Speed Delay Control [p189–190]** — `Init=0`. DQS/DLL delay
trims: `[23] DQS window size`, `[22:21] DQS window mode` (00 normal / 01 extend
0.5T / 10 delay 0.5T), `[20:18] window enable delay read→DQS`, `[17] read-latch
edge select`, `[16] CK/CKN output phase`, `[15:12] CK/CKN output delay` (DLL-off
only, `0.3ns + val*0.25ns`), `[11:8] DQS read window delay`, `[7:4] DQS feedback
delay` (DLL-off only), `[3:0] DQS output delay` (DLL-off only).

**MCR28 Mode Setting Control [p190]** — `Init=0`.
- **[2:1] Mode register selection:** `00`=MRS, `01`=EMRS(1), `10`=EMRS2, `11`=EMRS3.
- **[0] Fire mode-register-set / status flag:** write 1 to fire; HW auto-clears
  to 0 when done. **While firing, the AHB bus is locked** so SW can issue the
  sequence back-to-back with no delay. The command uses MCR2C for MRS/EMRS2 and
  MCR30 for EMRS(1)/EMRS3 as the payload.
- **Raptor drives the raw values `0x05,0x07,0x03,0x01`** (lines 494–508), i.e.
  bit0=fire plus the selector in [2:1]. A faithful model must, on each write with
  bit0=1, latch the appropriate MRS/EMRS payload and immediately present bit0=0
  on read-back (self-clearing).

**MCR2C MRS/EMRS2 Mode Setting [p190–192]** — `Init=X`. `[28:16]=EMRS2`,
`[12:0]=MRS`. **MRS layout is DDR-type-dependent** (p191–192):
- *DDR2:* [12] active-power-down exit (0 fast/t-XARD, 1 slow/t-XARDS), [11:9]
  Write Recovery (001=2T…101=6T), [8] DLL Reset, [7] Test Mode, [6:4] CAS
  latency (010=2T…110=6T), [3] burst type (0 sequential), [2:0] burst length
  (010=BL4, 011=BL8).
- *DDR:* [8] DLL reset, [6:4] CL (010=2T,011=3T), [3] burst type, [2:0] BL.
- Raptor DDR2: `0x732` (CL3, BL4, WR4, DLL-reset) → `0x632` (DLL-reset cleared).

**MCR30 EMRS/EMRS3 Mode Setting [p191–192]** — `Init=X`. `[28:16]=EMRS3`,
`[12:0]=EMRS(1)`. **EMRS1 layout is DDR-type-dependent**:
- *DDR2:* [11] RDQS enable (not supported), [10] DQS# control, [9:7] OCD
  calibration (000 exit / 111 default), **[6,2] ODT resistance** (00 disable,
  01 = 75 Ω, 10 = 150 Ω, 11 invalid), [5:3] additive latency (000=0; 1–4 "not
  supported"), [1] output driver impedance (0 = 100 %, 1 = 60 %), [0] DLL disable.
- *DDR:* [1] output drive strength, [0] disable DLL.
- Raptor DDR2: `0x040` (DLL enable, 150 Ω ODT via A6) / `0x3C0` (OCD default).

**MCR34 Power Control [p192–194]** — `Init=0`. Large register; key RW bits:
- **[31] R** current clock-speed mode (debug: 0 normal / 1 low).
- **[30:28] R** auto slow-down clock FSM status (debug).
- **[27] R** current CKE pin value (debug); **[26:24] R** self-refresh FSM (debug).
- **[22] clock switch mode** (0 manual / 1 auto), **[21] clock speed select**
  (0 normal / 1 low), **[20] clock switch control/enable**, **[19:17] slow-clock
  divider** (0=÷2 … 7=÷16).
- **[16] ODT auto-OFF post-amble**, **[15] ODT auto-ON preamble**,
  **[14] internal-ODT auto for reads**, **[13] internal-ODT auto for writes**,
  **[12] SDRAM-ODT auto for reads**, **[11] SDRAM-ODT auto for writes**,
  **[10] Enable SDRAM ODT**.
- **[9:7] CKE delay power-down→active** (000=1T…8T).
- **[6] disable SDRAM read-buffer power saving**, **[4] disable ctrl outputs in
  self-refresh**, **[3] disable CLK/CLKn in self-refresh**, **[2] force
  self-refresh**, **[1] enable auto power-down**, **[0] SDRAM CKE enable**.
- Raptor: initial `0x00000001` = **CKE enable only**; final `0x00007C03` =
  CKE + auto-power-down (bit1) + the five ODT-enable/auto bits [14:10]. (Corrects
  the RE-doc's "self-refresh enable / power-down timer" guess for `0x7C03`.)

**MCR38 Page Miss Latency Mask [p195]** — `Init=0`. `[31:3]` per-REQ mask
(bit3=REQ0, bit4=REQ1, …; 1 = mask this request when page-miss counter exceeds
threshold; high-priority requests left unmasked to avoid CRT-refresh starvation).
`[2:0]` page-miss latency threshold. Raptor `0xFFFFFF82` → threshold=2, REQ0
(bit3) unmasked.

**MCR3C Priority Group Setting [p195]** — `Init=0`. bit[n]: `0` → priority of
REQ(n) > REQ(n+1); `1` → priorities equal. Raptor `0` = strict fixed priority.

**MCR40/44/48 Maximum Grant Length #1–#3 [p195–196]** — `Init=0`. A **96-bit**
field spread over three 32-bit registers: 4 bits per request REQ0..REQ22
(MCR40[3:0]=REQ0 … MCR48[27:24]=REQ22; MCR48[31:28] reserved). Encoding
bit[3:0]→grant length: `0,1`=2× … `14,15`=16×. Raptor leaves all `0` (2× each).

**MCR60 IO Buffer Mode [p196–197]** — `Init=0`. DDR pad electrical config:
`[25]/[24]` enable SDRAM IO byte-lanes DQ[15:8]/DQ[7:0] (power-gating),
**[23] DDR IO LVCMOS select**, **[22] DDR IO DS select (SSTL18 1.8V vs SSTL2
2.5V)**, `[21:20]` programmable drive strength for ODT pin (S1,S0 table: SSTL18/
SSTL2/MDDR/LVTTL), `[19:18]/[17:16]/[15:14]/[13:12]` drive strength for
CS/RAS/CAS/WE/CKE/MA/BA, CK/CKN, DQS/DQSn, DQ/DM, `[11:10]` ODT resistance
(A6,A2: 00 disable / 01 75 Ω / 10 150 Ω), `[9:8]…[1:0]` per-pin-group ODT mode.
Raptor `0x032AA02A`.

**MCR64 DLL Control #1 [p197–198]** — `Init=0`. `[24] DLL3 ref-clk select`,
`[22] DLL1 ref-clk select`, `[21] DLL3 reset` (0 reset/1 normal), `[19] DLL1
reset`, `[18] DLL3 power-down` (0 pd/1 normal), `[16] DLL1 power-down`,
`[15:8] DLL3 output-phase SADJ (CK/CKn)`, `[7:0] DLL3 output-phase SADJ (DQS)`.
Raptor pre-config `0x00050000` (bits 16&18 set = DLL1 pd-normal path), final
`0x002D3000`.

**MCR68 DLL Control #2 [p198]** — `Init=0`. `[15:8] DLL1 input-phase SADJ (DQS1)`,
`[7:0] DLL1 input-phase SADJ (DQS0)`. Raptor `0x02020202` (upper half is
reserved; only low 16 bits meaningful).

**MCR6C DLL Control #3 [p198–199]** — `Init=0`. `[23:16] DLL3 master adjust MADJ`,
`[7:0] DLL1 master adjust MADJ`. **DLL note (p199):** min MADJ = 40;
`MIN_freq = 67 MHz * 120 / MADJ`, `MAX_freq = 347 MHz * 120 / MADJ`;
`delay(ns) = (SADJ+24)/MADJ * Tref + 0.1ns`. Raptor `0x00909090` (MADJ=0x90=144
for DLL1 and DLL3).

**MCR70 Testing Control/Status [p199–200]** — `Init=0`. Built-in memory BIST:
`[31:16] R` fail count, `[7] R` result (0 pass/1 fail), `[6] R` finish (0 busy/1
done), `[5:3] data-generation mode`, `[2:1] testing mode` (write-only / read-cmp
/ write-then-read / loopback), `[0] enable testing`. Raptor `0` (disabled).

**MCR74 Testing Start Addr & Length [p200]** — `Init=0`. `[27:23]` test base
(8 MB-granular), `[22:3]` total length (8-byte boundary, ≤8 MB). Raptor `0`.

**MCR78 Testing Fail DQ Bit [p200]** — `Init=0`, R. bit n = DQn failed. Raptor `0`.

**MCR7C Test Initial Value [p201]** — `Init=0`. Seed for the BIST pattern
generator (interpretation depends on MCR70[5:3] mode). Raptor `0`.

**MCR100 AST2000-compat SCU Password [p201]** — `Init = 0x000000A8`, **R**.
Backward-compat shadow of the SCU key; read-only, reads `0xA8`. (`hwreg.h`
`AST2100_COMPATIBLE_SCU_PASSWORD` @ +0x100.)

**MCR120 AST2000-compat SCU MPLL Parameter [p201]** — `Init=0`. `[15:14] Post
Divider`, `[13:5] Numerator`, `[4:0] Denumerator`. Raptor writes `0x00004C41`
(line 546). (`hwreg.h` `AST2100_COMPATIBLE_SCU_MPLL_PARA` @ +0x120.)

**MCR170 AST2000-compat SCU HW-Strapping Value [p201]** — `Init=0`, **R**,
reads all `0`.

---

## 4. Reset ("Init=") values a bare-metal test reads before firmware runs

From the register headers (datasheet p184–201). **Everything is `Init = 0`
except**:
- **MCR2C = X** (undefined) and **MCR30 = X** (undefined) — the two mode-set
  payload registers power up indeterminate. A faithful model may reset them to 0
  but must not rely on 0 being architectural.
- **MCR100 = `0x000000A8`** (read-only).
- **MCR170 = 0** (read-only, all zeros).
- **MCR00** resets **locked**; a locked read yields `0x00000000` (not the key).

Consequences for a bare-metal reader before DRAM is programmed:
- **MCR04 = 0** → bank mode 4-bank, bus width `00` (reserved/decodes 32-bit
  status via bit6), 0 refresh cycles, ≤32 MB capacity. DRAM is **not usable**.
- **MCR0C = 0** → **refresh disabled**, so "DRAM read data will be random value"
  (p187) until firmware programs a non-zero refresh.
- **MCR34 = 0** → **CKE disabled** (bit0=0 "force CKE at 0 after power-on reset",
  p194) → DDR2 devices held un-clocked.

---

## 5. How firmware detects DRAM size on the AST2050

**Answer: it does NOT auto-detect. Total DRAM size is a compile-time constant
that firmware WRITES into MCR04.** There is no SPD read, no size strap for total
DRAM, and no memory-probe in the boot path.

Evidence:
- `platform.S` (lines 369–377) selects the MCR04 value at build time from
  `#ifdef CONFIG_1G_DDRII` / `CONFIG_512M_DDRII` (`0xD89` / `0x585`) — no probe.
- The **only** strap that feeds MCR04 is **SCU70[3:2] = VGA memory size**
  (8/16/32/64 MB), which firmware masks and shifts into **MCR04[5:4]** (the VGA
  *aperture*, not total DRAM). Datasheet: MCR04[5:4] note "set by external
  trapping resistors SCU70[3:2]" (p185); SCU70[3:2] "VGA memory size selection …
  VGA memory will share with SOC memory from SDRAM Controller" (p218).
- **SCU70 has no total-DRAM-size field** (full SCU70 decode, p217–218: LPC reset,
  test mode, PCI AD reverse, M-bus disable, PLL bypass, VGA prefetch, boot speed,
  PCI class, DAC bypass, CPU/AHB ratio, H-PLL freq, MAC mode, VGA-BIOS enable,
  and **[3:2] VGA memory size** — nothing about total DRAM capacity).

**Discovery direction is one-way:** later software (U-Boot/Linux) that wants the
geometry **reads MCR04 back** and decodes bits [3:2] (total capacity), [1:0]
(column bits), [11] (bank mode), [9:8] (bus width). So the model must make MCR04
read back exactly what firmware wrote (a plain RW latch, with bit6 = !bit9 status
mirror). The AST2400 Linux/U-Boot `aspeed_sdmc` size discovery works the same way
(read the config register), but with the **G4 DDR3 encoding**, not this one.

Related handshake straps firmware uses (not size, but boot flow), datasheet p216
(SCU40 SoC scratch): **D[7] = "DRAM Initial Selection" (0 VBIOS / 1 SOC firmware
inits DRAM)** and **D[6] = "SOC Firmware Initial DRAM Status" (0 not ready / 1
ready)** — exactly the bits `platform.S` sets/checks at lines 138 (set D7),
144–147 (check D6 to skip re-init on warm reset), and 563 (set D6 when done).

---

## 6. AST2050 (DDR2) vs AST2400 (DDR3) — what a faithful model must capture

The upstream QEMU `aspeed_sdmc` models the **AST2400/G4 DDR3** controller. An
AST2050 (G3) DDR2 model differs in these datasheet-grounded ways:

1. **Config-register (MCR04) encoding is different (p185–186).** The AST2050
   DDR2 layout above (bit11 bank, bit10 auto-precharge, [9:8] bus width, bit7
   burst length, bit6 R width-status, [5:4] VGA aperture, [3:2] total capacity,
   [1:0] column bits) is **not** the G4 DDR3 layout. In particular the AST2050
   caps total capacity at **256 MB** ([3:2]) and has a read-only **bus-width
   status bit (6)** decoded from [9:8] for AST2000 back-compat — features the G4
   model does not have. A model that reuses the G4 field decode will mis-report
   size and geometry. **There is no DRAM-type bit in MCR04** (see §2.1); do not
   invent one.

2. **Mode registers are DDR2-specific (p191–192).** MCR2C/MCR30 carry two
   distinct encodings and the DDR2 branch adds: WR field [11:9] (2T–6T), active-
   power-down-exit bit [12], CAS latency up to 6T, and the DDR2 EMRS1 with OCD
   calibration [9:7] and ODT [6,2] (75/150 Ω). DDR3 uses different MR fields
   (e.g. no OCD, different ODT/RTT values). The faithful model should accept the
   MCR28 fire-and-self-clear protocol and the DDR2 MR payloads without asserting
   DDR3 semantics.

3. **Write latency is DDR2-derived (p188).** MCR18[23:21] note: "For DDR2 write
   latency = CAS latency − 1T" (for DDR it is always 1T). This coupling is a
   DDR2 rule the model's timing/consistency checks should reflect.

4. **I/O buffer standard is DDR2 SSTL18/SSTL2 (p196–197).** MCR60 selects SSTL18
   (1.8 V) or SSTL2 (2.5 V) and ODT 75/150 Ω — DDR2 signalling, not DDR3 SSTL15.
   The datasheet is silent on any 1.5 V/DDR3 mode here (there is none on AST2050).

5. **Refresh reference clock is 12 MHz (p186).** `Refresh Freq = 12 MHz /
   MCR0C[15:8]`. The model's refresh-interval decode must use the 12 MHz base
   (do not copy a G4 value). Also model the "refresh disabled → reads return
   random data" rule (MCR0C[3:0]=0 at reset).

6. **Protection key read-back is a lock latch, not the key (p184).** Same magic
   `0xFC600309`, but reads yield `0`/`1` (locked/unlocked). Confirm your G4 model
   matches; if it stores/returns the written value, the DDR2 model must instead
   return the 1-bit lock state, and reset **locked** (reads 0).

7. **Undocumented `0x4C`–`0x5C` and no ECC block (p183).** Only 30 registers are
   defined; there is no documented ECC control/status region on the AST2050 A3.
   `platform.S` writes 0 to `0x4C/0x50/0x54/0x58/0x5C`, so the model should
   accept writes there (RW-as-scratch or ignore) but must not advertise ECC
   behaviour the datasheet doesn't define.

8. **AST2000 backward-compat shadows at `0x100/0x120/0x170` (p201).** MCR100
   reads `0xA8`, MCR170 reads `0`, MCR120 mirrors an SCU MPLL parameter. The G4
   model has no such shadows. Include them for firmware that pokes them
   (`platform.S` writes MCR120 = `0x00004C41`).

9. **96-bit max-grant field across MCR40/44/48 and 23-entry REQ arbitration
   (p184, p195–196).** The AST2050 fixed-priority table has REQ0..REQ22 (§ below)
   and grant lengths packed 4-bit/request over three registers — a structure to
   preserve if the model implements arbitration/QoS at all.

### Fixed-Priority DRAM Request table (datasheet p184, for MCR08/38/3C/40–48)

REQ0 VGA HW cursor read · REQ1 VGA text CG font · REQ2 VGA text ASCII · REQ3 VGA
CRT read · REQ4 Video high-pri write · REQ5 USB2.0 DMA · REQ6 CPU data · REQ7 CPU
instruction · REQ8 PCI write · REQ9 PCI read · REQ10 AHB · REQ11 MAC1 DMA · REQ12
MAC2 DMA · REQ13/14 Reserved · REQ15 Encryption engine · REQ16 2D cmd-queue read
· REQ17 Video flag · REQ18 Video low-pri write · REQ19 MDMA · REQ20 2D engine data
· REQ21 I2C DMA-buffer · REQ22 Memory-Integrity-Check engine read.

---

## 7. Address & data arrangement (for the memory-window model)

- **Max addressing space = 256 MB, 28-bit internal address** (p201). Address
  translation Row(Page)/Bank/Column depends on MCR04[1:0] (CA bits) and the
  bus-width/bank setting — Figure 66 (p202) gives the exact A[27:x] → Row/BA/Col
  slicing for CA=9/10/11 in both 16-bit-or-ECC and 32-bit-bus layouts.
- **No out-of-range protection:** accesses above the configured size have their
  MSBs ignored (alias into the low address), datasheet p202.
- **Graphics (VGA) memory base is at the top of DRAM** (p202):
  MCR04[5:4]=0 (8 MB)→`0xF80_0000`; =1 (16 MB)→`0xF00_0000`;
  =2 (32 MB)→`0xE00_0000`; =3 (64 MB)→`0xC00_0000`.
- **Internal data bus is always 64-bit** (p202); 16-bit external mode maps one
  64-bit internal word to four DQ[15:0] beats (Figure 67).

## 8. Memory-clock switch & self-refresh sequences (p203)

- **Normal→low speed (DLL on):** set MCR14/1C/24 low-speed AC params → set MCR2C
  low-speed MR → set MCR34[22:21]=`0x3` and [19:17]=divider → set MCR34[20]=1.
- **Low→normal speed:** set MCR2C normal MR → MCR34[22:21]=`0x2` → MCR34[20]=1.
- **Enter self-refresh:** quiesce all IP / swap ARM code to static flash → set
  MCR34[2]=1 (optionally [4:3] for more saving).
- **Exit self-refresh:** MCR34[2]=0 → reset DRAM DLL (MCR2C[8]=1 then MCR28=1) →
  clear DLL reset (MCR2C[8]=0 then MCR28=1).

---

## Appendix: page index of the SDRAM chapter (PDF = printed page)

| Section | Pages |
|---------|-------|
| 17.1 Overview + 30-register list | 183 |
| 17.2 Fixed Priority DRAM Request | 184 |
| 17.3 Registers (MCR00 … MCR170) | 184–201 |
| 17.4 Address Arrangement (translation, VGA base) | 201–202 |
| 17.5 Data Arrangement (64-bit internal, 16-bit map) | 202 |
| 17.6 Memory Clock Switch Control | 203 |
| 17.7 Self Refresh Command Sequence | 203 |
| (cross-ref) SCU40 scratch D[7:6] DRAM-init handshake | 216 |
| (cross-ref) SCU70[3:2] VGA memory size strap | 217–218 |

# AST2050 / AST1100 Vector Interrupt Controller (VIC) — Datasheet Extract

Source: **ASPEED AST2050/AST1100 A3 Datasheet, V1.05** (dated May 25, 2010).
File: `datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf`
(Note: the task referenced `datasheets/AST2050_..._V1.05.pdf`; the actual in-repo
path is under `datasheets/aspeed/`. Identical copies also live in
`asus-kgpe-d16-firmware/datasheets/` and `dell-c410x-firmware/datasheets/`.)

Purpose: authoritative reference for a **faithful QEMU model** of the AST2050
VIC. Every value below carries a datasheet page cite. Where the datasheet is
silent, this is stated explicitly and the `hwreg.h` / measured-silicon fallback
is used.

Base address: **VIC = 0x1E6C_0000** (physical address = base + offset).
Cross-checks:
- Raptor register header `asus-kgpe-d16-firmware/hwreg.h` — `AST_IC_BASE 0x1E6C0000`,
  registers `IRQ_STATUS 0x00 … PROTECT_ENABLE 0x20`.
- Measured-on-silicon VIC config words (culvert session on the real KGPE-D16
  AST2050): `SENSE = 0x903897fe`, `BOTH-EDGE(dual) = 0x07c00000`,
  `EVENT = 0x983f97fe`.

---

## 0. Where it lives in the datasheet

| What | Chapter | Printed page (= physical PDF page) |
|---|---|---|
| ARM Address Space Mapping (§9) — VIC memory window | §9 | p.97 |
| VIC overview | §2.9 Vector Interrupt Controller | p.32 |
| VIC feature summary | §1.3.10 | p.21 (ToC) |
| **Interrupt Source Table (Table 36)** | **§10 Interrupt Source Table** | **p.99** |
| **VIC register definitions** | **§16 Interrupt Controller** | **p.179–182** |

The interrupt-controller register chapter is **§16** (p.179), not §10; **§10**
(p.99) is the separate *Interrupt Source Table*. Printed page numbers equal the
physical PDF page numbers for the body (front-matter aligns), so `Read` the PDF
at the pages above directly.

Memory window (§9 ARM Address Space Mapping, p.97): address range
`1E6C:0000–1E6D:FFFF`, **128K**, write mode 1/2/4, read mode 1/2/4, IP module
**"Vector Interrupt Controller (VIC)"**. So the decode window is 128 KiB but the
register file itself is a single compact bank at offsets 0x00–0x38 (below).

Overview (§2.9, p.32, verbatim): *"ARM CPU is equipped with a Vector Interrupt
Controller with **maximum 32 input sources**. Each interrupt source can be
programmed to support rising/falling-edge trigger mode or high/low-level trigger
mode… Each interrupt source can be programmed to generate FIRQ or IRQ… Table 36
lists the arrangement of each interrupt source for Interrupt Controller."*

---

## 1. Full register map (§16, p.179–182)

§16.1 (p.179) states verbatim: *"VIC implements the following **13 registers**…
Base address of VIC = 0x1E6C_0000."* The register list on p.179 and the
per-register tables on p.180–182 give:

| Offset | Name | R/W | Reset (Init) | Function (datasheet wording) | Page |
|---|---|---|---|---|---|
| 0x00 | VIC00 IRQ Status | **R** | 0 | Status after masking by VIC10 (enable) and VIC0C (select). `1` = active, asserts IRQ to CPU. | p.180 |
| 0x04 | VIC04 FIQ Status | **R** | 0 | Status after masking by VIC10 and VIC0C. `1` = active, asserts FIQ. | p.180 |
| 0x08 | VIC08 Raw Interrupt Status | **R** | 0 | Status **before** masking by VIC10. `1` = request active before masking. | p.180 |
| 0x0C | VIC0C Interrupt Selection | **RW** | 0 | Per-source route select: `1` = FIQ, `0` = IRQ. | p.180 |
| 0x10 | VIC10 Interrupt Enable | **RW** | 0 | Read `1`=enabled. Write `1` **sets** (enables); write `0` = no effect. Clear only via VIC14. | p.180 |
| 0x14 | VIC14 Interrupt Enable Clear | **W** | 0 | Write `1` **clears** the matching VIC10 bit to 0; write `0` = no effect. | p.180 |
| 0x18 | VIC18 Software Interrupt | **RW** | 0 | Write `1` sets a bit → generates a software interrupt for that source **before masking**; write `0` = no effect. | p.181 |
| 0x1C | VIC1C Software Interrupt Clear | **W** | 0 | Write `1` clears the matching VIC18 bit to 0; write `0` = no effect. | p.181 |
| 0x20 | VIC20 Protection Enable | **RW** (bit 0; 31:1 reserved=0) | 0 | Bit0: enable protected access → only privileged-mode accesses may touch VIC regs. This register itself is privileged-only. | p.181 |
| 0x24 | VIC24 Interrupt Sensitivity | **RW** | 0 | Per-source: `1` = level-sensitive, `0` = edge-triggered. | p.181 |
| 0x28 | VIC28 Interrupt Both-Edge Trigger Control | **RW** | 0 | Per-source: `1` = both edge, `0` = single edge. **No effect when the source is level-sensitive** (VIC24 bit = 1). | p.181 |
| 0x2C | VIC2C Interrupt Event | **RW** | 0 | Per-source polarity: `1` = high-level sensitive OR rising-edge; `0` = low-level sensitive OR falling-edge. | p.181 |
| 0x30 | VIC30 **Reserved** | — | **X** (undefined) | *"Any read/write to this register can cause incorrect operation."* Leave untouched. | p.181 |
| 0x38 | VIC38 Edge-Triggered Interrupt Clear | **W** | 0 | Write `1` clears the matching bit in the internal **edge-detection register**. For an edge source you must first write `1` here (clear stale detect) **then** enable in VIC10, otherwise the old latched status re-fires. | p.182 |

Notes / gaps:
- **All functional registers reset to 0** (Init = 0), per the per-register
  headers on p.180–182. Only VIC30 is `Init = X`.
- **Offset 0x34 is not defined** (there is no VIC34). The map jumps 0x30
  (reserved) → 0x38. Do not model a register at 0x34.
- `hwreg.h` only enumerates 0x00–0x20 (`IRQ_STATUS_REG … PROTECT_ENABLE_REG`)
  and does **not** define 0x24/0x28/0x2C/0x38 — those trigger-config registers
  come from the datasheet (§16, p.181–182), and the values firmware programs into
  them come from the measured silicon (§3). The datasheet is authoritative here.

### Single 32-bit bank — CONFIRMED (no second bank)

The AST2050 VIC is a **single 32-bit bank of 32 sources**, offsets **0x00–0x38
only**. Evidence:
- §16.1 register list (p.179) enumerates exactly VIC00…VIC38 and stops; the
  highest offset is 0x38.
- §16.2 Features (p.179): *"Support up to 32 interrupt sources"* — one 32-bit
  word covers every source, so no high bank is needed.
- Every status/config register is documented as `Bit 31:0` covering all 32
  sources in one word (p.180–182).
- There is **no** VIC80/VIC84… block and **no** `(L)/(H)` register pairs (those
  exist only on the AST2400 — see §4). No second bank at +0x40 or +0x80.

---

## 2. Interrupt source assignment table (§10, Table 36, p.99)

Verbatim from **Table 36: Interrupt Source Table** (p.99). "Attribute" is the
**required trigger type** for that source (the value firmware must program into
VIC24/28/2C).

| INT# | Source (Description) | Attribute (required trigger) |
|---|---|---|
| 0 | Reserved | Reserved |
| 1 | MIC interrupt (Memory Integrity Check) | Sensitive high level trigger |
| 2 | **MAC1 interrupt** | Sensitive high level trigger |
| 3 | **MAC2 interrupt** | Sensitive high level trigger |
| 4 | Crypto interrupt (HACE) | Sensitive high level trigger |
| 5 | USB 2.0 interrupt | Sensitive high level trigger |
| 6 | MDMA interrupt | Sensitive high level trigger |
| 7 | Video Engine interrupt | Sensitive high level trigger |
| 8 | LPC interrupt | Sensitive high level trigger |
| 9 | **UART1 alarm interrupt** | Sensitive high level trigger |
| 10 | **UART2 alarm interrupt** | Sensitive high level trigger |
| 11 | Reserved | Reserved |
| 12 | **I2C/SMBus interrupt** | Sensitive high level trigger |
| 13 | Reserved | Reserved |
| 14 | Reserved | Reserved |
| 15 | PECI interrupt | Sensitive high level trigger |
| 16 | **Timer — 1st counter** | Rising-edge trigger |
| 17 | **Timer — 2nd counter** | Rising-edge trigger |
| 18 | **Timer — 3rd counter** | Rising-edge trigger |
| 19 | SMC interrupt (Static Memory Ctrl) | Sensitive high level trigger |
| 20 | **GPIO interrupt** | Sensitive high level trigger |
| 21 | SCU interrupt | Sensitive high level trigger |
| 22 | RTC second interrupt | Edge trigger and both edge |
| 23 | RTC day interrupt | Edge trigger and both edge |
| 24 | RTC hour interrupt | Edge trigger and both edge |
| 25 | RTC minute interrupt | Edge trigger and both edge |
| 26 | RTC alarm interrupt | Edge trigger and both edge |
| 27 | **WDT alarm interrupt** | Rising-edge trigger |
| 28 | Tachometer interrupt (PWM/Fan Tacho) | Sensitive high level trigger |
| 29 | Reserved | Reserved |
| 30 | Reserved | Reserved |
| 31 | AHBC interrupt (AHB Bus Controller) | Sensitive high level trigger |

Key sources (task focus): timer1/2/3 → **16/17/18** (rising-edge);
UART1/UART2 → **9/10** (level-high); MAC1/MAC2 → **2/3** (level-high);
I2C/SMBus → **12** (level-high); WDT → **27** (rising-edge);
GPIO → **20** (level-high).

Trigger-type classes present:
- **Sensitive high-level**: 1,2,3,4,5,6,7,8,9,10,12,15,19,20,21,28,31
- **Rising-edge (single)**: 16,17,18,27
- **Both-edge**: 22,23,24,25,26 (the five RTC sources)
- **Reserved**: 0,11,13,14,29,30

---

## 3. How VIC24/VIC28/VIC2C encode trigger type — and reconciliation with silicon

Per-source encoding (§16, p.181), for bit `n` = source INT#`n`:

| VIC24[n] (sense) | VIC28[n] (both-edge) | VIC2C[n] (event) | Meaning |
|---|---|---|---|
| 1 | (ignored) | 1 | **High-level** sensitive |
| 1 | (ignored) | 0 | Low-level sensitive |
| 0 | 0 | 1 | **Rising-edge** (single) |
| 0 | 0 | 0 | Falling-edge (single) |
| 0 | 1 | (don't-care) | **Both-edge** |

(VIC28 "has no effect when sensitivity type is level sensitive", p.181; for
both-edge the polarity bit VIC2C is irrelevant.)

### Reconciliation with the measured silicon — EXACT MATCH

The three measured words are **not** register reset values (the datasheet resets
all three to 0 — see below). They are the values **firmware programs** to make
each source match the *required* trigger type in Table 36. Deriving the three
words directly from Table 36 with the encoding above reproduces the silicon
**bit-for-bit** (verified programmatically):

| Register | Derived from Table 36 | Measured on silicon | Match |
|---|---|---|---|
| VIC24 sensitivity | `0x903897FE` | `0x903897fe` | ✅ |
| VIC28 both-edge | `0x07C00000` | `0x07c00000` | ✅ |
| VIC2C event | `0x983F97FE` | `0x983f97fe` | ✅ |

Worked interpretation (LSB = INT#0):
- **VIC24 = 0x903897FE**: bits set (level-sensitive) =
  1,2,3,4,5,6,7,8,9,10,12,15,19,20,21,28,31 — exactly the "level-high" sources.
  Edge sources 16,17,18 (timer) and 22–27 (RTC/WDT) are 0 (edge). Reserved bits
  0/11/13/14/29/30 are 0.
- **VIC28 = 0x07C00000**: bits set (both-edge) = 22,23,24,25,26 — exactly the
  five RTC sources. All other bits 0 (single edge / level).
- **VIC2C = 0x983F97FE**: bits set (high-level or rising-edge) = all level-high
  sources **plus** rising-edge 16,17,18,27. The both-edge RTC bits 22–26 read
  0 here (polarity is don't-care for both-edge; firmware left them 0). Reserved
  bits 0.

**Conclusion:** The measured HW words are the exact, correct encoding of Table 36.
The datasheet does **not** publish these as register defaults; it publishes the
*required per-source attribute* (Table 36) and resets the config registers to 0.
The correspondence "Table 36 → (VIC24,VIC28,VIC2C)" is deterministic and the
silicon confirms it.

### Reset-value caveat (important for the model)

Per §16 p.181, **VIC24 = VIC28 = VIC2C reset to 0** on the AST2050. At reset,
therefore, *every source is edge-triggered / single-edge / falling-edge* until
firmware programs the words above. A faithful model must reset these three to 0
and rely on firmware (u-boot/Linux VIC driver) to write 0x903897FE / 0x07C00000 /
0x983F97FE. This is the **opposite** of the AST2400, where these registers are
read-only and hardwired to non-zero defaults (see §4). Do **not** pre-load the
AST2050 model with the measured words as "reset" state.

---

## 4. AST2050 vs AST2400 (G4) — what a faithful model must change

Reference for AST2400: **ASPEED AST2400/AST1250 A1 Datasheet V1.4**
(`datasheets/aspeed/AST2400_Datasheet.pdf`), §15 Interrupt Controller,
§15.3 "VIC Registers: Base Address = 0x1E6C:0000" (p.250–256), and
§7 Interrupt Source Table (Tables 55/56/57, p.119–121).

The upstream QEMU `hw/intc/aspeed_vic` device models the **AST2400/AST2500**
VIC, which is structurally different from the AST2050. Differences:

| Aspect | AST2050 (this datasheet) | AST2400 (QEMU aspeed_vic) |
|---|---|---|
| Source count | **32** max, one 32-bit word (§16.2 p.179) | **51** for ARM CPU (§15.2 p.251) → modeled as two 32-bit words |
| Register banking | **Single bank**, offsets 0x00–0x38 only | **Dual (L)/(H) bank**: legacy 0x00–0x38 (low 32) **plus** a canonical block 0x80–0xE4 with `(L)`/`(H)` register pairs (p.250–256) |
| Second-bank offsets | none | 0x80/84=IRQ Status(L/H), 0x88/8C=FIQ, 0x90/94=Raw, 0x98/9C=Select, 0xA0/A4=Enable, 0xA8/AC=Enable-Clear, 0xB0/B4=SW-Int, 0xB8/BC=SW-Int-Clear, 0xC0/C4=Sensitivity, 0xC8/CC=Both-Edge, 0xD0/D4=Event, 0xD8/DC=Edge-Clear, **0xE0/E4=Edge-Triggered Interrupt STATUS** (p.252–256) |
| Trigger-config regs (sense/both/event) | **RW, reset 0** — firmware programs them (§16 p.181) | **Read-only, hardwired defaults** (feature bullet "Hardwired pre-defined interrupt trigger type settings", p.251). e.g. VIC24 Init=0xFFF8FFFF (R), VIC28 Init=0x00070000 (R), VIC2C Init=0xFFF8FFFF (R); VICC4=0x00001F07, VICCC=0x000000F8, VICD4=0x00005F07 (p.251–255) |
| Edge status | **No** dedicated edge-status register; only VIC38 edge-**clear** | Adds VICE0/E4 Edge-Triggered Interrupt **Status** registers (p.256), distinct from the edge-clear VICD8/DC |
| Extra interrupt controllers | none | **SVIC** @ 0x1E6C:1000 (System-LPC, 16 src) and **CVIC** @ 0x1E6C:2000 (Coprocessor, 31 src) (p.256–258) |
| Source assignment | Table 36 (32 entries) — its own numbering | Table 55 "BMC Interrupt Source Table" (different, more sources) |

**Faithful AST2050 model — required changes vs the AST2400 aspeed_vic model**
(datasheet-grounded; QEMU-internal specifics flagged as such):

1. **One 32-bit bank, 32 lines.** Drop the 64-bit / two-word (L,H) internal state
   the AST2400 model uses; a single `uint32_t` per register suffices.
2. **Decode only 0x00–0x38.** Remove the entire 0x80–0xE4 canonical block, the
   0xE0/E4 edge-status registers, and the SVIC (0x1000)/CVIC (0x2000) sub-blocks.
   The 128 KiB window (§9 p.97) otherwise reads as unimplemented.
3. **Make VIC24/VIC28/VIC2C writable and reset them to 0.** On AST2400 these are
   read-only hardwired constants; on AST2050 they are RW (§16 p.181) and must
   start at 0. Do **not** hardwire AST2400's 0xFFF8FFFF/0x00070000 defaults — the
   AST2050 source map (Table 36) is different and firmware supplies the words
   (§3: 0x903897FE / 0x07C00000 / 0x983F97FE).
4. **No 0x34 register**; keep 0x30 as the reserved/undefined VIC30 (Init=X).
5. **Edge handling via VIC38 only.** Model the internal edge-detection latch and
   the "write-1-to-clear then enable" ordering (§16 p.182); there is no separate
   edge-status read register to expose.
6. **Clear/enable semantics** (identical pattern to AST2400's low bank, but named
   differently): enable = VIC10 (write-1-set), enable-clear = VIC14 (write-1-clr);
   SW-int = VIC18 / SW-int-clear = VIC1C; edge-clear = VIC38. There is only one of
   each (no `(L)/(H)` twins).
7. **Source-to-line wiring must use Table 36** (§2), not the AST2400 Table 55.
   Notably MAC1/2 = 2/3, UART1/2 = 9/10, I2C = 12, timer1/2/3 = 16/17/18,
   GPIO = 20, WDT = 27, AHBC = 31.

> QEMU-model caveat: the upstream `hw/intc/aspeed_vic.c` source is **not present
> in this repo**, so the exact register-decode/clear code paths above are
> described from the AST2400 datasheet (authoritative for the HW being modeled)
> plus general knowledge of the aspeed_vic device. Verify the specific offsets
> and 64-bit handling against the actual QEMU source before editing it.

---

## Appendix A — quick offset table for the model

```
VIC_BASE            0x1E6C0000
VIC00_IRQ_STATUS    0x00  R    reset 0
VIC04_FIQ_STATUS    0x04  R    reset 0
VIC08_RAW_STATUS    0x08  R    reset 0
VIC0C_SELECT        0x0C  RW   reset 0   (1=FIQ,0=IRQ)
VIC10_ENABLE        0x10  RW   reset 0   (write1=set)
VIC14_ENABLE_CLR    0x14  W    reset 0   (write1=clear VIC10)
VIC18_SOFTINT       0x18  RW   reset 0   (write1=set soft int)
VIC1C_SOFTINT_CLR   0x1C  W    reset 0   (write1=clear VIC18)
VIC20_PROTECT       0x20  RW   reset 0   (bit0 only; 31:1 rsvd)
VIC24_SENSITIVITY   0x24  RW   reset 0   (1=level,0=edge)     fw→0x903897FE
VIC28_BOTH_EDGE     0x28  RW   reset 0   (1=both,0=single)    fw→0x07C00000
VIC2C_EVENT         0x2C  RW   reset 0   (1=hi/rising,0=lo/falling) fw→0x983F97FE
VIC30_RESERVED      0x30  --   reset X   (do not touch)
-- no 0x34 --
VIC38_EDGE_CLR      0x38  W    reset 0   (write1=clear edge-detect latch)
```

## Appendix B — sources & page cites

- AST2050/AST1100 A3 Datasheet V1.05:
  §9 ARM Address Space Mapping — **p.97** (VIC window 1E6C:0000–1E6D:FFFF, 128K).
  §2.9 Vector Interrupt Controller — **p.32** (max 32 sources; rising/falling
  edge or high/low level; FIQ/IRQ; refers to Table 36).
  §10 Interrupt Source Table, **Table 36** — **p.99**.
  §16 Interrupt Controller: §16.1 overview + register list — **p.179**;
  §16.2 Features — **p.179**; §16.3 register definitions — **p.180–182**.
- AST2400/AST1250 A1 Datasheet V1.4: §15.2 Features — **p.251**;
  §15.3 VIC Registers (dual-bank, hardwired trigger defaults, VICE0/E4) —
  **p.250–256**; SVIC/CVIC — **p.256–258**; §7 source tables — **p.119–121**.
- `asus-kgpe-d16-firmware/hwreg.h` — `AST_IC_BASE 0x1E6C0000`, offsets 0x00–0x20
  (does not cover 0x24/0x28/0x2C/0x38).
- Measured silicon (culvert session, real KGPE-D16 AST2050):
  VIC24=0x903897fe, VIC28=0x07c00000, VIC2C=0x983f97fe — all three reproduced
  bit-for-bit from Table 36 (verified; `tmp/vic_calc.py`).

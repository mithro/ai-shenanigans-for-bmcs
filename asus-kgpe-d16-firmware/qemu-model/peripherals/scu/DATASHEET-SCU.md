# AST2050 / AST1100 (A3) — System Control Unit (SCU) Register Reference

Datasheet-derived register model of the ASPEED AST2050/AST1100 System Control
Unit, for a QEMU faithful-emulation effort. Every value below is quoted from
the **ASPEED AST2050/AST1100 A3 Datasheet V1.05** (the "Confidential"
watermarked PDF), section **18 System Control Unit (SCU)**, pp. 204–220.

Source PDF:
`datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf`

Cross-references (used to validate, not to trust blindly):
- Raptor register map: `asus-kgpe-d16-firmware/hwreg.h`
- Raptor DDR2/clock init assembly: `asus-kgpe-d16-firmware/platform.S`

> **Page numbering note:** the page numbers cited are the datasheet's own
> footer page numbers, which coincide with the PDF page index for this file
> (verified: PDF page 205 has footer "205"). Every register in §18.2 gives an
> explicit `Init =` (reset) value in its table header; those are quoted verbatim.

---

## 0. Base address and register map (§18.1, p204)

- **SCU base = 0x1E6E_2000** (datasheet writes "Base address of SMC = 0x1E6E_2000";
  physical address = base + offset). Matches `AST_SCU_BASE 0x1E6E2000` in `hwreg.h`.
- Datasheet warning (p204): *"Changing SCU registers usually results in
  significant impact on SOC operations. Therefore, all these registers have to
  be well protected."*

Full offset list as printed on p204 (this is the entire SCU register file —
there is **nothing above 0x7C** on the AST2050; the AST2400/2500 0x80+ block
does not exist here):

| Offset | Register | Init (reset) | Page |
|--------|----------|--------------|------|
| 0x00 | Protection Key Register | 0 (locked) | 205 |
| 0x04 | System Reset Control Register | 0x000FFE5C | 205–207 |
| 0x08 | Clock Selection Register | 0xE3F00070 | 207–209 |
| 0x0C | Clock Stop Control Register | 0x000C3E8B | 209–210 |
| 0x10 | Frequency Counter Control Register | 0 | 210–211 |
| 0x14 | Frequency Counter Measurement Register | 0 | 211 |
| 0x18 | Interrupt Control and Status Register | 0 | 211 |
| 0x1C | 32.768 KHz Error Correction Register | 0x0000001B | 211–212 |
| 0x20 | M-PLL Parameter Register | 0x00004291 | 212 |
| 0x24 | H-PLL Parameter Register | 0x00004291 | 212–213 |
| 0x28 | Frequency Counter Comparison Range | 0 | 213 |
| 0x2C | Misc. Control Register | 0 | 213–214 |
| 0x30 | PCI Configuration Setting Register #1 | 0x20001A03 | 214 |
| 0x34 | PCI Configuration Setting Register #2 | 0x20001A03 | 214 |
| 0x38 | PCI Configuration Setting Register #3 | 0x03000000 | 215 |
| 0x3C | System Reset Control Register (reset flags) | 0x00000001 | 215 |
| 0x40 | SOC Scratch Register #1 | 0 | 215–216 |
| 0x44 | SOC Scratch Register #2 | 0 | 216 |
| 0x50–0x6C | VGA Scratch Registers #1–#8 | 0 | 216–217 |
| 0x70 | Hardware Trapping Register | 0 (strap-latched) | 217–219 |
| 0x74 | Multi-function Pin Control #1 | 0x40048000 | 219–220 |
| 0x78 | Multi-function Pin Control #2 | 0 | 220 |
| 0x7C | Silicon Revision ID Register | 0x00000202 | 220 |

### hwreg.h vs datasheet cross-check

The Raptor `hwreg.h` offsets **all agree** with the datasheet map:
`0x00` key, `0x04` system-reset, `0x08` clock-select, `0x0C` clock-stop,
`0x10/0x14` freq counter, `0x18` interrupt, `0x1C` 32k-err, `0x20` M-PLL,
`0x24` H-PLL, `0x28` freq-range, `0x40/0x44` scratch, `0x70` strap, `0x7C` rev.
Two naming caveats:
- `hwreg.h` names 0x28 `SCU_FREQ_CNTR_CTRL_RANGE_REG`; datasheet calls 0x28
  the *Frequency Counter Comparison Range* and puts the *control* at 0x10.
  The offset is right, the label conflates 0x10/0x28.
- `hwreg.h` has **no macro for 0x2C** (Misc. Control). See §UART note below —
  this matters because `platform.S` reads the UART div13 bit which lives in
  0x2C, but its macro resolves to 0x28.

---

## 1. SCU00 — Protection Key Register (p205, Init = 0, locked)

| Bits | R/W | Field |
|------|-----|-------|
| 31:0 | RW | Protection Key |

- **Unlock password = `0x1688A8A8`** (quoted verbatim, p205). This exactly
  matches Raptor's `ldr r1, =0x1688a8a8` (`platform.S` lines 133, 241, 335).
- **Unlock:** write `0x1688A8A8`. **Lock:** write any other value (Raptor locks
  by writing `0x00000000`, `platform.S` line 591).
- **Read-back semantics (p205, key for emulation):**
  - unlocked → reads back **`0x00000001`**
  - locked  → reads back **`0x00000000`**
  - This is why Raptor validates the unlock with `cmp r1, #0x01`
    (`platform.S` line 246) rather than comparing to the password.
- Initial state after reset is **locked**. "Whenever finished the
  initialization of SCU registers, please always set SCU registers into locked
  mode."
- Note: when locked, writes to the other SCU registers are dropped
  ("protect SCU registers from unpredictable updates"). QEMU must gate SCU
  writes on the unlocked state and expose the 0/1 read-back.

---

## 2. SCU04 — System Reset Control Register (p205–207, Init = 0x000FFE5C)

Per-controller synchronous/async reset holds. Each bit: `0 = no operation`,
`1 = hold in reset`. Verified: the quoted `Init = 0x000FFE5C` is exactly the
listed default state of every bit below (bit-for-bit, checked by hand).

| Bits | Field | Reset default |
|------|-------|---------------|
| 31:22 | Reserved (0) | 0 |
| 21 | PCI Host Reset Output Enable Control (BRST# I/O dir; 0=input) | 0 |
| 20 | Force PCI Host Reset Output High | 0 |
| 19 | Reset PCI Host Bus Controller (async) | 1 |
| 18 | Reset MIC Controller (async) | 1 |
| 17 | Reserved, must keep "1" | 1 |
| 16 | Reset MDMA Controller (async) | 1 |
| 15 | Reserved, must keep "1" | 1 |
| 14 | Reset USB2.0 Controller (async) | 1 |
| 13 | Reserved, must keep "1" | 1 |
| 12 | Reset MAC#2 Controller (async) | 1 |
| 11 | Reset MAC#1 Controller (async) | 1 |
| 10 | Reset PECI Controller | 1 |
| 9  | Reset PWM Controller | 1 |
| 8  | Reset PCI Slave and VGA Controller | 0 |
| 7  | Reserved, must keep "0" | 0 |
| 6  | Reset Video Engine (async) | 1 |
| 5  | Reset LPC Controller (also resets embedded BMC ctrl) | 0 |
| 4  | Reset HAC Engine (async) | 1 |
| 3  | Reserved, must keep "1" | 1 |
| 2  | Reset I2C/SMBus Controller (async; write 0 → all 7 sets reset) | 1 |
| 1  | Reset AHB Bridges (AHB↔M-Bus, ↔APB, ↔P-Bus) | 0 |
| 0  | Reset SDRAM Controller (async) — dangerous, data loss | 0 |

Note (p207): most peripherals come out of reset held asserted; firmware
de-asserts them during bring-up. SDRAM (bit0) and AHB bridges (bit1) start
un-reset so the CPU can run.

---

## 3. SCU08 — Clock Selection Register (p207–209, Init = 0xE3F00070)

This is the central clock-tree mux/divider register. All divider fields share
the encoding `000:/2 001:/4 010:/6 011:/8 100:/10 101:/12 110:/14 111:/16`
(i.e. divide by `2·(field+1)`).

| Bits | Field | Reset (0xE3F00070) |
|------|-------|--------------------|
| 31:29 | LPC Master **LHCLK** divider (of H-PLL) | 111 → H-PLL/16 |
| 28 | LHCLK clock generation/output enable (1=internal) | 0 (from external LCLK pin) |
| 27:26 | Reserved, don't use | 00 |
| 25:23 | APB Bus **PCLK** divider (of H-PLL) | 111 → **PCLK = H-PLL/16** |
| 22:20 | PCI Host **BHCLK** divider (of H-PLL) | 111 → H-PLL/16 |
| 19 | BHCLK clock generation/output enable | 0 |
| 18:17 | Reserved, don't use | 00 |
| 16 | RTC clock source (test only): 0=32.768 kHz, 1=24 MHz | 0 |
| 15:11 | Reserved, must keep "0" | 0 |
| 10:8 | Video Port A output clock delay bits[3:1] (bit[0] in SCU2C[9]) | 000 |
| 7 | **ARM CPU clock throttling enable** (0=disable) | 0 |
| 6:4 | ARM CPU clock throttling divider (000:/2 … 111:/16) | 111 |
| 3:2 | **ECLK** (Video Engine) source: 00=M-PLL, 01=H-PLL, 10=inv M-PLL, 11=inv H-PLL | 00 (M-PLL) |
| 1:0 | **MCLK** (SDRAM) source: 00=M-PLL, 01=H-PLL, 10=inv M-PLL, 11=inv H-PLL | 00 (M-PLL) |

Key facts for emulation:
- **PCLK (APB) = H-PLL / 16 by default** (field 25:23 = 111). The APB clock is
  divided **from H-PLL, not from HCLK**.
- **MCLK (DRAM) is sourced from M-PLL** (bits 1:0 = 00). The datasheet warns
  (p209) to change MCLK source only at boot before DRAM init, and to stop MCLK
  via SCU0C[2] first.
- There is **no dedicated "UART clock source" field in SCU08.** The UART
  reference is the 24 MHz REFCLK, optionally /13 — see SCU2C[12] (§10).
- CPU throttling (bit7/bits6:4) is the "low-speed boot" mechanism; see
  SCU70[16].

---

## 4. SCU0C — Clock Stop Control Register (p209–210, Init = 0x000C3E8B)

Each clock-gate bit: `0 = clock running (enable)`, `1 = clock stopped`
(except bit14 which is inverted — an *enable* bit). Verified the quoted
`Init = 0x000C3E8B` matches every default below bit-for-bit.

| Bits | Field | Reset default |
|------|-------|---------------|
| 31:20 | Reserved (0) | 0 |
| 19 | Stop BHCLK (PCI Host Controller) | 1 (stopped) |
| 18 | Reserved, must keep "1" | 1 |
| 17:16 | Reserved (0) | 0 |
| 15 | **Stop UARTCLK (UART1/UART2)** | 0 (running) |
| 14 | **Enable USB2.0 clock** (0=stopped+PHY power-down) | 0 (stopped) |
| 13 | Stop YCLK (HAC) | 1 (stopped) |
| 12:9 | Reserved, must keep "1111" | 1111 |
| 8 | Stop LCLK (LPC Controller) | 0 (running) |
| 7 | Stop UCLK (USB1.1) | 1 (stopped) |
| 6 | REFCLK Stop Enable (24 MHz) | 0 (running) |
| 5 | Stop DCLK (VGA) | 0 (running) |
| 4 | Stop BCLK (PCI Slave) | 0 (running) |
| 3 | Stop V1CLK (Video Capture #1) | 1 (stopped) |
| 2 | Stop MCLK (SDRAM Controller) | 0 (running) |
| 1 | Stop GCLK (2D Engine) | 1 (stopped) |
| 0 | Stop ECLK (Video Engine) | 1 (stopped) |

For emulation: **UARTCLK (bit15) and MCLK (bit2) run at reset**; the UART is
therefore usable from cold boot, consistent with Raptor emitting "DRAM Init"
banner over UART2 before touching the PLLs (`platform.S` lines 161–226).

---

## 5. SCU10 / SCU14 / SCU28 — Frequency Counter (p210–211, 213)

### SCU10 Frequency Counter Control (Init = 0)
| Bits | R/W | Field |
|------|-----|-------|
| 7 | R | Compare result (0=fail, 1=pass) — SCU14 vs SCU28 limits |
| 6 | R | Measurement finished (clear by writing SCU10[1]=0) |
| 5:2 | RW | Clock source under test: 0000 delay-cell ring-osc /16; 0001 NAND ring-osc /16; 0010 PCI bus; 0011 D2-PLL; 0100 M-PLL; 0101 H-PLL; 0110 LPC bus; 0111 Video Port B; 1011 D-PLL; 1111 Video Port A |
| 1 | RW | Oscillator Counter Enable (0=reset counter) |
| 0 | RW | Enable Ring Oscillator |

Procedure (p211): SCU10=0x16 → wait SCU14=0 → set SCU10[0]=1 + source →
delay 1 ms → SCU10[1]=1 → wait SCU10[6]=1 → read SCU14.

### SCU14 Frequency Counter Measurement (Init = 0)
- bits 13:0 R: counter value. **Frequency = (24 MHz / 512) × (Value + 1)**
  (p211). This equation confirms the fixed **24 MHz reference clock**.

### SCU28 Frequency Counter Comparison Range (Init = 0)
- bits 29:16 RW Upper Limit; bits 13:0 RW Lower Limit; rest reserved.

**Raptor discrepancy (important):** `platform.S` line 166 loads
`SCU_FREQ_CNTR_CTRL_RANGE_REG` (macro = base+0x28) but comments it `@0x1e6e202c`
and then tests **bit 12** (`lsr #12; tst #0x01`) to pick the UART divisor. Bit 12
of the *comparison-range* register (0x28) is part of the Lower Limit and has no
UART meaning; the intended register is **SCU2C[12] "div13"** (see §10). Because
both 0x28 and 0x2C reset to 0, Raptor still picks the non-div13 divisor at boot,
so the bug is latent — but a faithful model should not let a read of 0x28[12]
mean anything about UART baud.

---

## 6. SCU18 / SCU1C — Interrupt & RTC trim (p211–212)

### SCU18 Interrupt Control and Status (Init = 0)
- bit17 RW VGA scratch-register-change interrupt+status (W1C)
- bit16 RW VGA cursor-change interrupt+status (W1C)
- bit1 RW enable scratch-change interrupt; bit0 RW enable cursor interrupt.

### SCU1C 32.768 KHz Error Correction (Init = 0x0000001B)
- bits 7:0 RW Error-correcting value.
  **RTC clock = 12 MHz × 128 / (46848 + ECV)** (p212).
  Default ECV = 0x1B (27) → 32768.0 Hz exactly. (26 → +1.8 s/day, 28 → −1.8 s/day.)

---

## 7. SCU20 — M-PLL Parameter Register (p212, Init = 0x00004291)

M-PLL generates the **memory-controller running frequency** (feeds MCLK).

| Bits | Field |
|------|-------|
| 31:18 | Reserved (0) |
| 17 | Enable M-PLL bypass mode (1 → output = external 24 MHz ref) |
| 16 | Turn off M-PLL (1 → power-down, output constant 0). *Default OFF if hardware trapping boots low-speed, i.e. SCU70[16]=0.* |
| 14:12 | **M-PLL Post Divider**: `0xx`=÷1, `100`=÷2, `101`=÷4, `110`=÷8, `111`=÷16 |
| 10:5 | **M-PLL Numerator** (N) |
| 4 | **M-PLL Output Divider** (OD) |
| 3:0 | **M-PLL Denumerator** (D) |

**Output frequency (p212, quoted verbatim):**

```
Output frequency = 24MHz × (2 − OD) × [ (Numerator + 2) / (Denumerator + 1) ]
```

then divided by the Post Divider field [14:12]. Datasheet: "The default
frequency of M-PLL settings is always 133 MHz."

**Verification against the reset value 0x00004291:**
N(=[10:5]) = 20, OD(=[4]) = 1, D(=[3:0]) = 1, PostDiv[14:12] = 100 (÷2).
`(2−1)·(20+2)/(1+1) = 11`; `× 24 MHz = 264 MHz`; `÷2 (post) = 132 MHz ≈ 133 MHz`.
The post-divider is **required** to reach the datasheet's stated 133 MHz.

**Verification against Raptor's programmed DDR2 value 0x000041F0**
(`platform.S` line 339, comment "denumerator=0b0000; output divider=1;
numerator=0b001111; post divider=div by 2"):
D=0, OD=1, N=15, PostDiv=100(÷2). `(2−1)·(15+2)/(0+1)=17`; `×24=408 MHz`;
`÷2 = 204 MHz` → MCLK ≈ 200 MHz (DDR2-400). Decode matches the comment exactly.

> Raptor also writes an **AST2000 backward-compatible M-PLL shadow** at
> `0x1E6E_0120` (in the SDRAM controller, *not* the SCU): `0x00004C41`
> (`platform.S` line 546). That register uses the legacy AST2000 encoding and is
> not part of the SCU; QEMU can treat it separately.

---

## 8. SCU24 — H-PLL Parameter Register (p212–213, Init = 0x00004291)

H-PLL generates the **ARM CPU running frequency** (root of CPU/HCLK/PCLK).

| Bits | Field |
|------|-------|
| 31:19 | Reserved (0) |
| 18 | **H-PLL parameter selection**: 0 = use **trapping resistors**; 1 = use programmed SCU24[17:0]. *(M-PLL has no equivalent bit.)* |
| 17 | Enable H-PLL bypass mode (1 → output = external 24 MHz ref) |
| 16 | Turn off H-PLL (1 → power-down, output 0) |
| 14:12 | **H-PLL Post Divider**: `0xx`=÷1, `100`=÷2, `101`=÷4, `110`=÷8, `111`=÷16 |
| 10:5 | **Numerator** (N) |
| 4 | **H-PLL Output Divider** (OD) |
| 3:0 | **H-PLL Denumerator** (D) |

**Output frequency (p213, verbatim):**

```
Output frequency = 24MHz × (2 − OD) × [ (Numerator + 2) / (Denumerator + 1) ]
```

then divided by Post Divider [14:12]. "The default frequency of H-PLL settings
depends on the related trapping resistors. The available options include
100/133/166/200 MHz" (selected by **SCU70[11:9]**).

Because SCU24[18] defaults to 0 (trapping resistors), the **programmed reset
value 0x00004291 is ignored at power-on** — the real CPU clock comes from the
SCU70[11:9] strap. Raptor never writes SCU24, i.e. it relies on the board straps
for CPU speed.

### Does the AST2050 H-PLL use the same bit layout as the QEMU AST2400 model?

**Core multiplier: YES, identical.** QEMU's AST2400 formula is
`multiplier = (2 − OD)·((N+2)/(D+1))` with `N = bits[10:5]`, `OD = bit[4]`,
`D = bits[3:0]`. The AST2050 datasheet fields line up one-to-one:
Numerator = [10:5], Output Divider (OD) = [4], Denumerator = [3:0], and the same
`(2−OD)·(N+2)/(D+1)` expression (p213). So for the N/OD/D portion the AST2400
QEMU code can be reused unchanged.

**Difference: the AST2050 adds a Post Divider at bits [14:12]** (÷1/2/4/8/16)
that the stock AST2400 QEMU `calc_hpll`/`calc_mpll` does **not** apply. This is
not cosmetic: the AST2050 reset value 0x00004291 only evaluates to the
datasheet's stated defaults (133 MHz H-PLL, 133 MHz M-PLL) **with** the ÷2
post-divider; without it the formula yields 264 MHz. A faithful AST2050 model
must include the [14:12] post-divide stage on both SCU20 and SCU24.

**Second difference:** SCU24 bit[18] "parameter selection (strap vs
programmed)" — on the AST2050 the H-PLL defaults to the **strap** value
(SCU70[11:9]); the programmed register only takes effect when bit18=1.

---

## 9. SCU2C — Misc. Control Register (p213–214, Init = 0) — UART clock bit

| Bits | Field |
|------|-------|
| 15 | Enable internal link between UART1 and UART2 |
| 14 | Enable MUX function of UART1 pins |
| 13 | Timeout control bit for VUART |
| **12** | **Enable reference clock divider (div13) for UART1 & UART2** |
| 11 | Enable inverting YCLK |
| 9 | Video Port A output clock delay bit[0] (with SCU08[10:8]) |
| 8 | Disable PCI slave→AHB bus bridge |
| 6 | Disable VGA CRT display in Video Direct Fetch mode |
| 5 | Enable VGA register access when not trapping VGA mode |
| 3 | Disable video DAC |
| 2 | Disable D1-PLL |
| 1 | OSC clock output pin selection (test) |
| 0 | Disable SMC output buffers |

**SCU2C[12] is the UART baud-clock control (p214):**
- `0` → baud = **24 MHz / (16 × divisor)**
- `1` → baud = **(24 MHz / 13) / (16 × divisor)**

At reset SCU2C[12]=0, so the UART reference is the raw 24 MHz REFCLK. Raptor
programs the divisor latch DLL accordingly (`platform.S` lines 170–176):
DLL=`0x0D`(13) with div13=0 → `24e6/(16·13)=115384 ≈ 115200`; or DLL=`0x01`
with div13=1 → `(24e6/13)/16 = 115384 ≈ 115200`. **UART baud in QEMU must be
computed from 24 MHz (optionally /13), independent of the H-PLL.**

---

## 10. SCU30 / SCU34 / SCU38 — PCI Configuration (p214–215)

| Offset | Init | Fields |
|--------|------|--------|
| 0x30 | 0x20001A03 | [31:16] PCI Device ID, [15:0] PCI Vendor ID (0x1A03 = ASPEED) |
| 0x34 | 0x20001A03 | [31:16] PCI Sub-System ID, [15:0] PCI Sub-Vendor ID |
| 0x38 | 0x03000000 | [31:8] Class Code, [7:0] PCI Revision ID |

VGA/PCI identity for the integrated graphics function; "changing the ID is
usually not recommended."

---

## 11. SCU3C — System Reset Control Register / reset-flags (p215, Init = 0x00000001)

A second "System Reset Control" register (distinct from SCU04); this one is the
reset-source status + EXTRST# control.

| Bits | Field |
|------|-------|
| 3 | Enable external SOC reset function (GPIOB7 → EXTRST#, active-low; resets all modules **except** DRAM controller) |
| 2 | External reset flag (set by EXTRST#, W-clear) |
| 1 | Watchdog reset flag (set by internal WDT, W-clear) |
| 0 | **Power-on reset flag** (set by SRST# power reset, W-clear) |

Reset value `0x00000001` = power-on-reset flag set. QEMU should present bit0=1
after a cold reset so firmware can distinguish power-on from WDT/external reset.

---

## 12. SCU40 / SCU44 — SOC Scratch Registers (p215–216, Init = 0)

64 bits of ARM↔host scratch (SCU40 = bits[31:0], SCU44 = bits[63:32]),
readable by the host CPU over PCI. Bit meanings are software-defined, **but the
datasheet documents the ASPEED SDK/VBIOS handshake convention** for SCU40 (this
is exactly what Raptor uses):

| Bits | Meaning (ASPEED VGA handshake, p215–216) |
|------|------------------------------------------|
| 31:24 | Scratch for ASPEED SDK/SLT. **0x5A = "Embedded Linux boot to Linux properly"** |
| 15:14 | MAC#1 PHY mode (00 Dedicate, 01 NCSI, 10 Intel NCSI EVB) |
| 13:12 | MAC#2 PHY mode (same encoding) |
| 7 | **DRAM Initial Selection**: 0 = VBIOS inits DRAM, 1 = SOC firmware inits DRAM |
| 6 | **SOC Firmware Initial DRAM Status**: 0 = not ready, 1 = ready |
| 4 | KVM Virtual EDID Function enable |

Datasheet Note 1 (p216): if `0x1E6E_2040[7]==0` VBIOS inits DRAM; else SOC
firmware inits DRAM, sets `[6]=1` when ready, and VBIOS POST waits on `[6]`.

**Raptor uses precisely this handshake:**
- `platform.S` line 138 sets `SCU40[7]=1` (firmware-inits-DRAM flag) before init.
- line 284 writes `SCU40 = 0x5A000080` = boot-key `0x5A` in [31:24] + `[7]=1`.
- line 145–147 checks `SCU40[6]` (DRAM-already-done) to skip re-init.
- line 563 sets `SCU40[6]=1` after DRAM init completes.
This confirms the datasheet's [31:24]=0x5A / [7] / [6] semantics against real firmware.

---

## 13. SCU50–SCU6C — VGA Scratch Registers (p216–217, Init = 0)

Eight 32-bit registers = 256 bits of host→ARM scratch (host CPU writes,
**ARM reads — read-only from the ARM/SCU side**), for embedded firmware.
Meaning is software-defined.

---

## 14. SCU70 — Hardware Trapping Register (p217–219, Init = 0)

The strap/boot-configuration register. **Modeling caveat:** although the table
prints `Init = 0`, this is a *hardware trapping register* — at power-on the
lower bit-fields are **latched from external strap resistors**, not zero. A
faithful QEMU model must seed SCU70 from a board-strap property (QEMU's
`hw-strap1`), only bits[31:24] being a pure software scratch.

| Bits | Field | Encoding |
|------|-------|----------|
| 31:24 | Software-defined trapping registers | (scratch) |
| 23 | Enable LPC dedicated reset pin function | 0=share PCI reset, 1=pin B10 |
| 22 | Enable test mode | |
| 21 | Reverse PCI AD[31:0] pin sequence | for PCB routing |
| 20 | Disable ARM CPU→M-bus bridge | 1=CPU reaches memory only via AHB |
| 19 | Bypass all PLL (test only) | |
| 18 | Reserved, keep 0 | |
| 17 | PCI VGA Config Space prefetch bit | |
| 16 | **SOC Boot Up Full Speed Mode** | 0 = ARM boots at **1/16 speed** (CPU throttle 1/16, **M-PLL OFF, MCLK from 24 MHz ref**); 1 = full speed. *"software must set this bit to 1 for full speed."* |
| 15 | PCI Class Code selection | 0=video device, 1=VGA device |
| 14 | Bypass VGA DAC (test) | |
| **13:12** | **CPU/AHB clock frequency ratio** | **00 = 1:1, 01 = 2:1, 10 = 4:1, 11 = 3:1** |
| **11:9** | **H-PLL default clock frequency** | 00x Reserved; **010 = 200 MHz; 011 = 166 MHz; 100 = 133 MHz; 101 = 100 MHz**; 110 Reserved; 111 = 24 MHz (H-PLL bypass) |
| 8:6 | MAC interface mode | 011 = MII(MAC#1) only; 100 = RMII(MAC#1) only; 110 = RMII(MAC#1)+RMII(MAC#2); 111 = Disable MAC; others reserved |
| 5 | Enable VGA BIOS ROM | 0=on-board, 1=add-on |
| 4 | Reserved, keep 0 | |
| **3:2** | **VGA memory size** | 00 = 8 MB, 01 = 16 MB, 10 = 32 MB, 11 = 64 MB (shared with SOC memory) |
| **1:0** | **ARM CPU boot code selection** | 0x = Reserved; **10 = Boot from SPI flash**; 11 = Disable ARM CPU |

Answers to the specific strap questions:
- **Input reference clock select (24/25/48 MHz): NOT present.** The AST2050 has
  no strap for reference frequency — the external reference is **always 24 MHz**
  (stated explicitly in the SCU20/SCU24 bypass notes, p212, and by the fixed
  "24 MHz/512" in the SCU14 equation). Unlike AST2400/2500, there is no 24/25 MHz
  CLKIN strap bit here.
- **CPU:AHB ratio → SCU70[13:12]** (00=1:1, 01=2:1, 10=4:1, 11=3:1).
- **CPU (H-PLL) frequency → SCU70[11:9]** (100/133/166/200 MHz options).
- **Boot source → SCU70[1:0]** (10 = SPI flash).
- **VGA memory size → SCU70[3:2]**. Raptor reads exactly these bits
  (`platform.S` lines 363–367: `SCU70 & 0xC`, then `<<2`) to fold VGA size into
  the SDRAM config register — confirming the [3:2] field.
- **Total DRAM size is *not* a SCU70 strap** on the AST2050 — only the VGA
  carve-out (bits 3:2). Full DRAM geometry is set in the SDRAM controller
  (MCR04 @ 0x1E6E_0004), e.g. Raptor's `CONFIG_512M_DDRII` / `CONFIG_1G_DDRII`
  paths (`platform.S` lines 369–377).
- **MAC mode → SCU70[8:6]**.

---

## 15. SCU74 / SCU78 — Multi-function Pin Control (p219–220)

### SCU74 Multi-function Pin Control #1 (Init = 0x40048000)
32 individual pin-mux enables. Notable bits: 31 Enable HCLK output; 30 Enable
VGA external DAC sense; 27 Enable GPIOE group shared w/ MAC (valid SCU70[8:6]=2,4,7);
25 MAC PHY#1 PHYLINK/PHYPD#; **24 Enable full UART2 pins**; 23 VP[17:12]; 22 VP[11:0];
20 MAC#2 MDC/MDIO; 18 primary DDC; 16 Video Port A output ctrl; 15 VGA pins;
14/13/12 I2C#7/#6/#5 pins; 11–8 PWM4–1; 7 PECI; 6–3 PCI REQ/GNT4–1; 2 flash
FLBUSY#/FLWP#; 1 NOR flash ACK ctrl; 0 NOR flash ROMA24. Reset value 0x40048000 =
bit30 (VGA DAC sense) + bit18 (primary DDC) + bit15 (VGA pins) enabled; note
bit24 (full UART2 pins) = 0 at reset. Datasheet: "The pin multiplexing function
… is totally determined by this register"; default leaves most muxed pins as
tri-stated GPIO.

### SCU78 Multi-function Pin Control #2 (Init = 0)
- 4 Disable PCI INTA# output; 3 Enable Watchdog reset-event output;
  2 Enable Video Port A RGB666 18-bit output; 0 Enable Video Port A single-edge I/O.

---

## 16. SCU7C — Silicon Revision ID Register (p220, Init = 0x00000202)

| Bits | R/W | Field |
|------|-----|-------|
| 31:10 | — | Reserved (0) |
| 9:8 | R | **Chip bounding option** (reflects bonding option for product differentiation) |
| 7:0 | R | **Silicon revision ID**: 0 = A0, 1 = A1, 2 = A2/A3, … |

**Silicon-revision table (p220, quoted rows):**

| Part | SCU7C value |
|------|-------------|
| AST1100-A0 | 0x00000200 |
| AST1100-A1 | 0x00000201 |
| AST1100-A2 | 0x00000202 |
| AST1100-A3 | 0x00000202 |
| AST2050-A0 | 0x00000200 |
| AST2050-A1 | 0x00000201 |
| AST2050-A2 | 0x00000202 |
| **AST2050-A3** | **0x00000202** |
| AST2100-A0 | 0x00000300 |
| AST2100-A1 | 0x00000301 |
| AST2100-A2 | 0x00000302 |
| AST2100-A3 | 0x00000302 |

**Confirmed: AST2050-A3 → SCU7C = `0x00000202`** (matches the expected value
and the table header `Init = 0x00000202`). Field decode: bits[9:8] = `0b10`
(chip bonding option = 2), bits[7:0] = `0x02` (A2/A3 silicon).

Raptor's rev check (`platform.S` lines 150–154) reads SCU7C, shifts right 8,
and compares to `0x02`: `0x00000202 >> 8 = 0x02` selects the **AST2050/AST1100
family** (vs. AST2100's `0x00000302 >> 8 = 0x03`). Confirmed against firmware.
Note A2 and A3 are **indistinguishable** by SCU7C (both 0x202); the two-bit
chip-bonding field [9:8] is what varies by product, not the A2/A3 stepping.

---

## 17. Clock tree summary (for QEMU timer/UART fidelity)

Reference: **24 MHz** external crystal (fixed; shared with USB — SCU20/24 notes;
SCU14 "24 MHz/512" equation). No 24/25/48 MHz strap exists.

```
 24 MHz REF ─┬─► H-PLL (SCU24) ── CPU clock ─┬─► HCLK (AHB) = CPU / [SCU70[13:12] ratio: 1:1|2:1|4:1|3:1]
             │   default via SCU70[11:9]     │
             │   strap (100/133/166/200 MHz) └─► PCLK (APB) = H-PLL / SCU08[25:23] (÷2..÷16; reset ÷16)
             │                                    ├─► LHCLK (LPC) = H-PLL / SCU08[31:29]
             │                                    └─► BHCLK (PCI host) = H-PLL / SCU08[22:20]
             │
             ├─► M-PLL (SCU20, default 133 MHz) ─► MCLK (DRAM) = M-PLL  [SCU08[1:0]=00]
             │                                     ECLK (Video) src = SCU08[3:2]
             │
             ├─► UART ref = 24 MHz, optional ÷13 (SCU2C[12]); baud = ref/(16×DLL). Gate: SCU0C[15].
             │
             └─► RTC = 12 MHz×128/(46848+SCU1C) = 32768 Hz;  RTC src test-sel SCU08[16].
```

Consequences for a faithful model:
- **CPU/HCLK/PCLK all trace back to H-PLL, whose default is the SCU70[11:9]
  strap (not the SCU24 programmed value, because SCU24[18]=0).** Set the QEMU
  strap so H-PLL and the CPU:AHB ratio match the board (KGPE-D16 / C410X).
- **ASPEED APB timer (0x1E78_2000) is clocked from PCLK** (H-PLL/16 at reset) —
  or its selectable external tick; getting H-PLL and SCU08[25:23] right is what
  makes the emulated timer tick rate correct.
- **UART baud is derived from 24 MHz (÷13 optional), fully decoupled from
  H-PLL** — model it from the fixed reference, not the CPU clock.
- **The [14:12] PLL post-divider must be applied** on SCU20/SCU24 (see §7/§8);
  omitting it (as the stock AST2400 QEMU formula does) doubles the computed
  PLL output.

---

## 18. Registers where AST2050 semantics differ from the QEMU AST2400 model

1. **PLL post-divider [14:12] on SCU20/SCU24** — present and functional on
   AST2050 (÷1/2/4/8/16); the AST2400 QEMU `calc_hpll`/`calc_mpll` ignores it.
   Must be added, or reset defaults compute 2× too high (§7, §8).
2. **SCU24[18] H-PLL "parameter selection" (strap vs programmed)** — on AST2050
   the H-PLL uses the SCU70[11:9] strap unless [18]=1. CPU clock at reset comes
   from the strap, not the programmed 0x00004291.
3. **No reference-clock strap** — AST2050 CLKIN is fixed 24 MHz; there is no
   24/25 MHz select bit in SCU70 (AST2400/2500 have one). Do not model a
   configurable CLKIN.
4. **SCU register file ends at 0x7C** — the AST2400/2500 0x80+ block
   (extra clock/PLL, JTAG, misc) does not exist on AST2050 (§0, p204). The
   AST2000-compatible M-PLL shadow lives at 0x1E6E_0120 in the **SDRAM
   controller**, not the SCU.
5. **Two separate "System Reset Control" registers** — SCU04 (per-controller
   reset holds, Init 0x000FFE5C) and SCU3C (reset-source flags + EXTRST#, Init
   0x00000001). AST2400 reorganises resets across SCU04/SCU2C; keep the AST2050
   split.
6. **VGA-memory strap is SCU70[3:2]** with encoding 8/16/32/64 MB — offsets and
   encoding differ from later parts; total system DRAM is *not* strapped in SCU
   (it is an SDRAM-controller MCR04 setting).
7. **Silicon-ID (SCU7C)** decode differs: A2 and A3 share 0x00000202; the
   distinguishing field is chip-bonding [9:8], and the family nibble is in
   bits[15:8] (0x02 = AST2050/1100, 0x03 = AST2100).

Everything above is quoted or derived from the AST2050/AST1100 A3 Datasheet
V1.05, §18 (pp. 204–220); where the datasheet is silent it is called out
explicitly and the Raptor `hwreg.h`/`platform.S` behaviour is noted as the
fallback evidence.

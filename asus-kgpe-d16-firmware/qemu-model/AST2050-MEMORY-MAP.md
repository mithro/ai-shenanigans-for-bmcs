# AST2050 (A3) Peripheral Memory Map — Authoritative Extract for QEMU

This document is the authoritative peripheral memory map of the ASPEED
**AST2050 / AST1100 (A3 silicon)** SoC, extracted from the vendor datasheet
**"ASPEED AST2050/AST1100 A3 Datasheet – V1.05" (dated May 25, 2010)**, whose
internal title page reads *"AST1100 Software Programming Guide"*. Every base
address and register value below is taken from that datasheet and cited by
section (chapter) and **printed** page number. The single most authoritative
source is **§9 "ARM Address Space Mapping", printed pages 97–98**, which is the
chip's complete address decode table; the per-controller register chapters
(§11–§35) each restate their own base address in a `Registers : Base Address =`
heading, and those were cross-checked against §9. The Raptor-Engineering
register header `asus-kgpe-d16-firmware/hwreg.h` (labelled "AST2100 SOC
Register locations", used by the working Linux 2.6.28.9 AST2050 port) was used
only as a **cross-check** — where it agrees with the datasheet this is noted;
where it is silent or diverges this is flagged. The datasheet **does** contain a
real memory-map table (§9), so nothing here is reconstructed from scattered
chapters except where explicitly stated.

> Reference used for the cross-check: `hwreg.h` defines
> `AST_SMC_BASE 0x16000000`, `AST_MAC1_BASE 0x1E660000`,
> `AST_MAC2_BASE 0x1E680000`, `AST_GPIO_BASE 0x1E780000`,
> `AST_SDRAMC_BASE 0x1E6E0000`, `AST_SCU_BASE 0x1E6E2000`,
> `AST_TIMER_BASE 0x1E782000`, `AST_IC_BASE 0x1E6C0000`,
> `AST_WDT_BASE 0x1E785000`, `AST_UART1_BASE 0x1E783000`,
> `AST_UART2_BASE 0x1E784000`, `AST_AHBC_BASE 0x1E600000`. **All twelve match
> the datasheet §9 table exactly.**

---

## 1. Complete peripheral base-address table

Source table: **§9 ARM Address Space Mapping, p97** (address ranges, sizes, and
access widths quoted verbatim), refined with each controller's own
`Base Address =` chapter heading. "Write width" is the datasheet "Write Mode
(Byte)" column: `4` means the block accepts **word (32-bit) writes only** — a
detail a faithful QEMU model must enforce (byte/half writes give
"un-predictable result", §9 note, p97).

### 1a. AHB peripheral controllers (the register blocks)

| Peripheral | Base address | Size | Write width | Datasheet §/page | Present on AST2050? | Notes |
|---|---|---|---|---|---|---|
| Static Memory Controller (SMC) — flash controller regs | `0x1600_0000` | 32 MB window (regs in first 8×32-bit) | 4 (word writes only) | §9 p97; §11.3 p105 | **Yes** | Control regs SMC00–SMC1C. Controls CE0/CE1/CE2 flash chip-selects; flash *data* is memory-mapped separately (see §1b). See §3.4. |
| AHB Bus Controller (AHBC) | `0x1E60_0000` | 128 KB | 1/2/4 | §9 p97; §12.3 p114 | **Yes** | Only 4 regs: 0x00 key, 0x80 priority, 0x88 IRQ ctrl, 0x8C **Address Remap** (boot remap of 0x0). |
| Memory Integrity Check (MIC/MICE) | `0x1E64_0000` | 128 KB | 4 (word writes only) | §9 p97; §13.3 p116 | **Yes** | 8 regs. Present on AST2050/AST1100; *absent* on AST2000 (§1.5 p28). |
| Fast Ethernet MAC #1 (MAC1) | `0x1E66_0000` | 128 KB | 1/2/4 | §9 p97; §14 p124 | **Yes** | 10/100 Mbps, MII×1 or RMII×2. `ftgmac`-family. |
| Fast Ethernet MAC #2 (MAC2) | `0x1E68_0000` | 128 KB | 1/2/4 | §9 p97; §14 p124 | **Yes** | Second identical MAC. |
| USB 2.0 Virtual Hub Controller | `0x1E6A_0000` | 128 KB | 4 (word writes only) | §9 p97; §15.3 p155 | **Yes** | Device/vhub controller (up to 7 devices, EP#0–20). **No** USB1.1 host (AST2100-only, §1.4 p27). |
| Vector Interrupt Controller (VIC) | `0x1E6C_0000` | 128 KB | 1/2/4 | §9 p97; §16.3 p180 | **Yes** | Single compact bank, 32 sources, offsets 0x00–0x38 (see §3.2). |
| SDRAM Memory Controller (MMC) | `0x1E6E_0000` | 4 KB | 4 (word writes only) | §9 p97; §17.3 p184 | **Yes** | Shares the 0x1E6E page with SCU and HACE. Regs MCR00–MCR7C + AST2000-compat aliases MCR100/120/170. |
| System Control Unit (SCU) | `0x1E6E_2000` | 4 KB | 4 (word writes only) | §9 p97; §18.2 p205 | **Yes** | Clock/reset/strap/rev-ID/pinmux. See §3.1. |
| Hash & Crypto Engine (HACE) | `0x1E6E_3000` | 4 KB | 4 (word writes only) | §9 p97; §19.3 p222 | **Yes** | 11 regs. MD5/SHA1/224/256 + AES/RC4. |
| Video (Compression/Capture) Engine | `0x1E70_0000` | 128 KB | 1/2/4 | §9 p97; §20.3 p234 | **Yes** | Video *capture/compression* engine (§2.5). Distinct from the VGA display controller (§34) and 2D engine (§35), which are reached via the PCI/VGA path, not this AHB base. |
| AHB→PCI (P-Bus) Bridge Controller (A2P) | `0x1E72_0000` | 128 KB | 1/2/4 | §9 p97 ("AHB to PCI (P-Bus) Bridge"); §21 p256 | **Yes** | AHB→PCI direction. The reverse PCI→AHB ("P2A") backdoor is via the PCI **slave** controller BARs (§33). Relevant to the culvert `p2a` path. |
| MDMA Controller | `0x1E74_0000` | 128 KB | 4 (word writes only) | §9 p97; §22.3 p257 | **Yes** | Memory DMA engine. |
| GPIO Controller | `0x1E78_0000` | 4 KB | 4 (word writes only) | §9 p97; §23.3 p263 | **Yes** | 46 shared GPIO pins (§1.3.16 p23). AST2000 had 32. |
| Real-Time Clock (RTC) | `0x1E78_1000` | 4 KB | 4 (word writes only) | §9 p97; §24.3 p270 | **Yes** | **No battery backup** (§1.3.20 p24). `hwreg.h` does not define it. |
| Timer #1/#2/#3 Controller | `0x1E78_2000` | 4 KB | 4 (word writes only) | §9 p97; §25.3 p275 | **Yes** | Three 32-bit timers. Regs TMC00–TMC30. |
| UART #1 | `0x1E78_3000` | 4 KB | 4 (word writes only) | §9 p97; §26.3 p280 | **Yes** | 16550, full flow-control pins. |
| UART #2 | `0x1E78_4000` | 4 KB | 4 (word writes only) | §9 p97; §26.3 p280 | **Yes** | 16550, TX/RX only (no flow control) (§1.4 p27). |
| Watchdog Timer (WDT) | `0x1E78_5000` | 4 KB | 4 (word writes only) | §9 p97; §27.3 p287 | **Yes** | Single 32-bit WDT (regs WDT00–WDT0C). |
| PWM & Fan Tacho Controller | `0x1E78_6000` | 4 KB | 4 (word writes only) | §9 p97; §28.3 p290 | **Yes** | 4 PWM outputs, 16 tach inputs (§1.4 p27). |
| Virtual UART (VUART) | `0x1E78_7000` | 4 KB | 4 (word writes only) | §9 p97; §29.3 p297 | **Yes** | LPC-side virtual 16550. |
| Pass-through UART (PUART) | `0x1E78_8000` | 4 KB | 4 (word writes only) | §9 p97; §29.4 p308 | **Yes** | LPC pass-through 16550. |
| LPC Controller | `0x1E78_9000` | 4 KB | 4 (word writes only) | §9 p97; §30.3 p312 | **Yes** | Slave+Master, SIRQ, port-80 snoop, IPMI KCS/BT (§1.3.21 p24). Host↔BMC mailbox/scratch live here + in SCU scratch regs. |
| I2C / SMBus / FML Controller | `0x1E78_A000` | 4 KB | 4 (word writes only) | §9 p97; §31.4 p334 | **Yes** | **7** controllers in one 4 KB page; 256-byte shared FIFO; 2 can be FML (§1.3.15 p22). Global regs at 0x00; per-device at 0x40 stride. |
| PECI Controller | `0x1E78_B000` | 4 KB | 4 (word writes only) | §9 p97; §32.3 p357 | **Yes** | PECI 1.1/2.0. |
| PCI Arbiter | `0x1E78_C000` | 4 KB | 4 (word writes only) | §9 p97 | **Yes** | Listed only in the §9 map (no dedicated register chapter). |

### 1b. Memory / bus windows (address decode, not register blocks)

| Region | Address range | Size | Datasheet §/page | Notes |
|---|---|---|---|---|
| Static Memory (boot-up default) | `0x0000_0000`–`0x01FF_FFFF` | 32 MB | §9 p97 | At reset, CPU boot fetches come from flash mapped here. |
| SDRAM (after re-map) | `0x0000_0000`–`0x0FFF_FFFF` | 256 MB | §9 p97 | After AHBC8C[0] "Boot Area Remap" = 1, low space maps to SDRAM (§12.3 p115). |
| Static Memory (flash CE0/CE1/CE2 data) | `0x1000_0000`–`0x15FF_FFFF` | 96 MB | §9 p97; §11.1 p100 | CE0 base `0x1000_0000`; CE1/CE2 at +segment-size (default 32 MB segments, SMC00[1:0]). |
| SMC register/aperture window | `0x1600_0000`–`0x17FF_FFFF` | 32 MB | §9 p97; §11.3 p105 | Where SMC00–SMC1C registers live. |
| SDRAM (normal aperture) | `0x4000_0000`–`0x4FFF_FFFF` | 256 MB | §9 p97 | Main DRAM aperture; VGA/graphics memory sits at the top (§9 p98 table, gated by SCU70[3:2]). |
| AHB→LPC Bus Bridge | `0x5000_0000`–`0x5FFF_FFFF` | 256 MB | §9 p97 | Window onto the LPC bus. |
| PCI Host Memory #1 | `0x6000_0000`–`0x7FFF_FFFF` | 512 MB | §9 p97 | Remappable via AHBC8C[4]. |
| PCI Host Memory #2 | `0x8000_0000`–`0xFFFF_FFFF` | 2 GB | §9 p97 | Remappable via AHBC8C[5]. |

### 1c. Blocks reached via PCI/VGA rather than an AHB base

| Peripheral | Datasheet §/page | Present on AST2050? | Notes |
|---|---|---|---|
| PCI Slave Controller | §33 p363 | **Yes** | Conventional 32-bit **PCI** (not PCIe). Exposes BMC to a host PCI bus; its BARs are the PCI→AHB ("P2A") backdoor. |
| VGA Display Controller | §34 p369 | **Yes** | Legacy VGA register file (SEQ/CRT/GC/ATC/RAMDAC + Extended CRT), accessed through PCI config + legacy VGA I/O, not a 0x1Exx AHB base. |
| 2D Graphics Engine | §35 p393 | **Yes (2D only)** | 64-bit 2D BitBLT accelerator. **No** 3D/graphics *display* controller — that is AST2100-only (§1.4 p27). |

### 1d. Controllers that exist on AST2400/2500/2600 but are ABSENT or different on AST2050

| Block | Status on AST2050 | Evidence |
|---|---|---|
| ADC (10-bit analog-to-digital) | **Absent** | No ADC chapter and no ADC entry in the §9 map (p97). ADC (`0x1E6E_9000` on G4) was introduced with the AST2400. |
| eSPI controller | **Absent** | Not in §9 map; AST2050 has conventional **LPC** only (§30). eSPI is AST2500+. |
| SD/eMMC controller | **Absent** | No SDHCI block in §9 map. Added on AST2400 (`0x1E74_0000` on G4 is SDHCI; on AST2050 that address is the **MDMA** engine — see divergences). |
| X-DMA / PCIe-to-AHB (P2A) engine | **Different** | AST2050 uses conventional **PCI** (A2P bridge `0x1E72_0000` + PCI slave §33), not the AST2400 PCIe/X-DMA block. |
| FMC + dedicated SPI flash controllers (`0x1E62_0000`/`0x1E63_0000`) | **Different / absent** | AST2050 flash is the legacy **SMC at `0x1600_0000`** with flash data at `0x1000_0000` (§11), not the G4 FMC/SPI at `0x1E62_/0x1E63_0000` with flash at `0x2000_0000`. |
| UARTs #3–#5 | **Absent** | AST2050 has only UART1/UART2 (§1.4 p27; §9 p97 lists exactly two). G4 has 5 built-in UARTs. |
| Graphics *display* controller, USB1.1 host, ECC, 32-bit DRAM | **Absent** | §1.4/§1.5 comparison tables, p27–28 (all marked "No" for AST2050). |
| Second VIC bank / >32 interrupt sources | **Absent** | §10 Interrupt Source Table lists exactly INT#0–31 (p99); §16 VIC is one 32-bit bank (p179–181). |
| Coprocessor (LPC-side CM3/CPU), MCTP, PWM tach banks >1, GPIO banks >1 | **Absent / reduced** | Not present in the §9 map; single GPIO block (46 pins), single PWM/tach block. |

---

## 2. Cross-check against `hwreg.h` (Raptor Engineering)

| Symbol in `hwreg.h` | Value | Datasheet §9 value | Verdict |
|---|---|---|---|
| `AST_SMC_BASE` | `0x16000000` | `0x1600_0000` | Match |
| `AST_MAC1_BASE` | `0x1E660000` | `0x1E66_0000` | Match |
| `AST_MAC2_BASE` | `0x1E680000` | `0x1E68_0000` | Match |
| `AST_GPIO_BASE` | `0x1E780000` | `0x1E78_0000` | Match |
| `AST_SDRAMC_BASE` | `0x1E6E0000` | `0x1E6E_0000` | Match |
| `AST_SCU_BASE` | `0x1E6E2000` | `0x1E6E_2000` | Match |
| `AST_TIMER_BASE` | `0x1E782000` | `0x1E78_2000` | Match |
| `AST_IC_BASE` (VIC) | `0x1E6C0000` | `0x1E6C_0000` | Match |
| `AST_WDT_BASE` | `0x1E785000` | `0x1E78_5000` | Match |
| `AST_UART1_BASE` | `0x1E783000` | `0x1E78_3000` | Match |
| `AST_UART2_BASE` | `0x1E784000` | `0x1E78_4000` | Match |
| `AST_AHBC_BASE` | `0x1E600000` | `0x1E60_0000` | Match |

`hwreg.h` does **not** define I2C, RTC, PWM, VUART/PUART, LPC, PECI, HACE, MIC,
USB, MDMA, Video, or the PCI/A2P bases; those come from the datasheet §9 table
above. The `hwreg.h` "SDRAM" block also declares three aliases the datasheet
confirms as **AST2000-backward-compatibility** registers inside the MMC page:
`AST2100_COMPATIBLE_SCU_PASSWORD` = MMC+0x100, `..._SCU_MPLL_PARA` = MMC+0x120
(datasheet §17: **MCR100** "AST2000 Backward Compatible SCU Password",
**MCR120** "AST2000 Backward Compatible SCU MPLL Parameter", **MCR170**
"AST2000 Backward Compatible SCU Hardware Strapping Value", p184/§17 register
list).

---

## 3. Key-controller register detail

### 3.1 System Control Unit — SCU, base `0x1E6E_2000` (§18, p204–220)

Protection: SCU registers are locked until the password **`0x1688A8A8`** is
written to `SCU00` (§18.2 p205 — *"The password of the protection key is
0x1688A8A8"*). Full register list (§18.1 p204):

| Offset | Name | Init | Notes |
|---|---|---|---|
| 0x00 | Protection Key Register | 0 | Unlock = write `0x1688A8A8`; reads back `0x00000001` when unlocked. |
| 0x04 | System Reset Control Register | `0x000FFE5C` | |
| 0x08 | **Clock Selection Register** | `0xE3F00070` | LHCLK/PCLK/BHCLK dividers off H-PLL (see below). |
| 0x0C | Clock Stop Control Register | — | Per-block clock gating. |
| 0x10 | Frequency Counter Control | — | |
| 0x14 | Frequency Counter Measurement | — | |
| 0x18 | Interrupt Control and Status | — | |
| 0x1C | 32.768 KHz Error Correction | — | |
| 0x20 | **M-PLL Parameter Register** | `0x00004291` | Memory clock PLL (see below). |
| 0x24 | **H-PLL Parameter Register** | `0x00004291` | ARM CPU clock PLL (see below). |
| 0x28 | Frequency counter comparison range | 0 | |
| 0x2C | Misc. Control Register | — | |
| 0x30/0x34/0x38 | PCI Configuration Setting #1/#2/#3 | — | |
| 0x3C | System Reset Control Register (#2) | — | |
| 0x40/0x44 | SOC Scratch Register #1/#2 | — | General scratch (host/BMC comms). |
| 0x50–0x6C | VGA Scratch Register #1–#8 | — | |
| 0x70 | **Hardware Trapping Register** | 0 | Strap latch / soft overrides (see below). |
| 0x74/0x78 | Multi-function Pin Control #1/#2 | — | Pinmux. |
| 0x7C | **Silicon Revision ID Register** | `0x00000202` | Read-only rev/bonding (see below). |

**SCU7C — Silicon Revision ID (§18.2, p220).** Exact datasheet wording:

> *"7:0  R  Silicon revision ID — 0: Represent A0 silicon; 1: Represent A1
> silicon; **2: Represent A2/A3 silicon** …"*
> *"9:8  R  Chip bounding option — reflect the status of the chip bonding option
> which is designed for product differentiation."*

The datasheet's revision-ID lookup table (p220) reads verbatim:

```
AST1100-A0  0x00000200      AST2050-A0  0x00000200      AST2100-A0  0x00000300
AST1100-A1  0x00000201      AST2050-A1  0x00000201      AST2100-A1  0x00000301
AST1100-A2  0x00000202      AST2050-A2  0x00000202      AST2100-A2  0x00000302
AST1100-A3  0x00000202      AST2050-A3  0x00000202      AST2100-A3  0x00000302
```

**⇒ For the QEMU model, `SCU7C` must read `0x00000202` on AST2050-A3.** Note A2
and A3 are indistinguishable by this register (both `0x00000202`), and the low
byte is the family/rev field while the AST2100 uses the `0x03xx` band. (For
contrast, the AST2400/G4 reports a `0x02000303`-class value from *its* SCU7C —
**not in this datasheet; from G4 knowledge** — so a model keyed off this
register is how firmware tells the parts apart.)

**SCU70 — Hardware Trapping Register (§18.2, p217).** Latches boot straps;
several bits are software-writable overrides. Key bits a model must honour:

- **[16] SOC Boot-Up Full-Speed Mode** — *"0: ARM CPU will boot up at low speed
  mode (1/16 of full speed) … 1: ARM CPU will boot up at full speed mode … When
  boot up at low speed mode, software must set this bit to 1 for full speed
  operation, else it will always operates at low speed mode."* (When low-speed,
  M-PLL is off and MCLK sources the 24 MHz reference.)
- **[13:12] CPU/AHB clock frequency ratio** — 00=1:1, 01=2:1, 10=4:1, 11=3:1.
- **[11:9] H-PLL default clock selection** — 010=200 MHz, 011=166 MHz (and lower
  options; 00x reserved).
- **[3:2]** — VGA/graphics memory aperture size strap (referenced by MCR04[5:4],
  §17 p185).
- **[23]** LPC dedicated reset pin enable; **[22]** test mode; **[21]** reverse
  PCI AD[31:0] pin order; **[20]** disable ARM→M-bus bridge; **[19]** bypass all
  PLL (test); **[31:24]** software-defined trapping bits.

**SCU20 — M-PLL / SCU24 — H-PLL (§18.2, p212).** Both `Init = 0x00004291`.
Output-frequency formula (identical for both): `Fout = 24 MHz × (2^-OD) ×
[(Numerator+2) / (Denumerator+1)]`, with fields **[14:12] Post Divider**,
**[10:5] Numerator**, **[4] Output Divider (OD)**, **[3:0] Denumerator**. M-PLL
default is 133 MHz (memory clock); H-PLL default 100/133/166/200 MHz selected by
trapping resistors (SCU24[18]=0) or by the programmed register (SCU24[18]=1).
SCU24[17] bypass, [16] power-off. **SCU08 — Clock Selection** (`0xE3F00070`):
[31:29] LPC LHCLK divider, [28] LHCLK gen enable, [25:23] APB **PCLK** divider,
[22:20] PCI **BHCLK** divider, [19] BHCLK gen enable — all divide H-PLL by
2/4/…/16.

### 3.2 Vector Interrupt Controller — VIC, base `0x1E6C_0000` (§16, p179–181)

The AST2050 VIC is a **single compact 32-bit bank** — *"VIC implements the
following 13 registers … VIC supports up to 32 interrupt requests"* (§16.1
p179). This is the ARM PL190-style layout, **not** the two-bank / 51-source
arrangement of the AST2400. Full offset list (§16.1 p179, §16.3 p180–181):

| Offset | Name | Access | Meaning |
|---|---|---|---|
| 0x00 | VIC00 IRQ Status | R | Status after masking (VIC10 & VIC0C). |
| 0x04 | VIC04 FIQ Status | R | FIQ status after masking. |
| 0x08 | VIC08 Raw Interrupt Status | R | Status before masking. |
| 0x0C | VIC0C Interrupt Selection | RW | 1=FIQ, 0=IRQ, per source. |
| 0x10 | VIC10 Interrupt Enable | RW | Write 1 sets enable; clear via VIC14. |
| 0x14 | VIC14 Interrupt Enable Clear | W | Write 1 clears the matching VIC10 bit. |
| 0x18 | VIC18 Software Interrupt | RW | Write 1 raises a software IRQ. |
| 0x1C | VIC1C Software Interrupt Clear | W | Write 1 clears the matching VIC18 bit. |
| 0x20 | VIC20 Protection Enable | RW | [0] privileged-only access. |
| 0x24 | VIC24 Interrupt Sensitivity | RW | 1=level, 0=edge. |
| 0x28 | VIC28 Both-Edge Trigger Control | RW | 1=both edges (edge mode only). |
| 0x2C | VIC2C Interrupt Event | RW | 1=high-level/rising, 0=low-level/falling. |
| 0x30 | VIC30 Reserved | — | *"Any read/write … can cause incorrect operation."* |
| 0x38 | VIC38 Edge-Triggered Interrupt Clear | W | Clears latched edge interrupts. |

`hwreg.h` names the first nine identically (IRQ_STATUS 0x00 … PROTECT_ENABLE
0x20) and omits 0x24/0x28/0x2C/0x38 — consistent, just incomplete.

**Interrupt source assignment (§10 Interrupt Source Table, p99)** — exactly 32
sources, fixed mapping (relevant for wiring a QEMU model):

```
0  Reserved            8  LPC                16 Timer1 (rising edge)   24 RTC hour
1  MIC (hi level)      9  UART1 (hi level)   17 Timer2 (rising edge)   25 RTC minute
2  MAC1 (hi level)     10 UART2 (hi level)   18 Timer3 (rising edge)   26 RTC alarm
3  MAC2 (hi level)     11 Reserved           19 SMC (hi level)         27 WDT (rising edge)
4  Crypto/HACE (hi)    12 I2C/SMBus (hi)     20 GPIO (hi level)        28 Tacho (hi level)
5  USB2.0 (hi level)   13 Reserved           21 SCU (hi level)         29 Reserved
6  MDMA (hi level)     14 Reserved           22 RTC second (both edge) 30 Reserved
7  Video Engine (hi)   15 PECI (hi level)    23 RTC day (both edge)    31 AHBC (hi level)
```

### 3.3 SDRAM Memory Controller — MMC, base `0x1E6E_0000` (§17, p183–200)

Word-write-only 4 KB block sharing the `0x1E6E` page with SCU (+0x2000) and HACE
(+0x3000). Register list (§17 p184): MCR00 Protection Key, MCR04 Configuration,
MCR08 Graphics Memory Protection, MCR0C Refresh Timing, MCR10/14 Normal/Low
Speed AC Timing #1, MCR18/1C AC Timing #2, MCR20/24 Normal/Low Speed Delay
Control, MCR28 Mode Setting Control, MCR2C MRS/EMRS2, MCR30 EMRS/EMRS3, MCR34
Power Control, MCR38 Page-Miss Latency Mask, MCR3C Priority Group, MCR40/44/48
Max Grant Length #1–#3, MCR60 IO Buffer Mode, MCR64/68/6C DLL Control #1–#3,
MCR70 Testing Control/Status, MCR74 Test Start Addr/Length, MCR78 Test Fail DQ,
MCR7C Test Initial Value, plus the **AST2000-compat aliases MCR100 / MCR120 /
MCR170** (SCU password / MPLL param / hardware strapping). This 1:1 matches the
`hwreg.h` `SDRAM_*` list.

**MCR04 Configuration (§17, p185; Init = 0)** — the fields a model needs to size
DRAM correctly:

- **[11] Bank mode** — 0 = 4-bank, 1 = 8-bank. *(For the real KGPE-D16/AST2050
  bring-up, 4-bank/64 MB/DLL settings were the working combination.)*
- **[9:8] Data bus width** — `01` = 16-bit (DQ15–DQ0); *"others: Reserved"* —
  i.e. AST2050 is **16-bit DRAM only** (§1.4 p27 confirms).
- **[6] Bus-width status** — read-only, *"used for AST2000 backward compatible"*.
- **[5:4] Graphics memory aperture** — 8/16/32/64 MB; must equal SCU70[3:2].
- **[3:2] Total memory capacity** — 00 ≤32 MB, 01 = 64 MB, 10 = 128 MB, 11 =
  256 MB. **AST2050 max is 128 MB** (§1.4 p27), so `11` is not a valid AST2050
  configuration even though the field encodes it.
- **[1:0] Column-address count** — 9/10/11 bits per JEDEC.

### 3.4 Static Memory / Flash Controller — SMC, register base `0x1600_0000` (§11, p100–105)

*"Static Memory Controller (SMC) implements 8 sets of 32-bit registers … For
AST2050/AST1100 chip, only SPI flash type interface is supported"* (§11.1 p100 —
note the overview also lists NOR/NAND as a hardware superset; the shipped
AST2050 use-case is SPI). This is the **legacy SMC**, distinct from the AST2400
FMC. Two distinct address roles:

- **Register block:** base **`0x1600_0000`** (§11.3 p105), holding:

| Offset | Name | Init | Notes |
|---|---|---|---|
| 0x00 | SMC00 CE0 Segment AC Timing | `0x00000240` | Segment size + per-CE flash type + write-enable (see below). |
| 0x04 | SMC04 CE0 Control | 0 | Timing; meaning depends on SMC00[9:4] flash-type. |
| 0x08 | SMC08 CE1 Control | 0 | |
| 0x0C | SMC0C CE2 Control | 0 | |
| 0x10 | SMC10 Misc. Control | 0 | |
| 0x14 | SMC14 NAND ECC Generation Control/Status | 0 | |
| 0x18 | SMC18 NAND ECC check value | 0 | |
| 0x1C | SMC1C NAND ECC check result | — | |

- **Flash *data* aperture (memory-mapped):** *"Base address of CE0:
  0x10000000; Base address of CE1: 0x10000000 + (Segment Size); Base address of
  CE2: 0x10000000 + (Segment Size × 2)"* (§11.1 p100). Segment size is set by
  **SMC00[1:0]**: `00` = **32 MB (default)**, `01` = 16 MB, `10` = 8 MB, `11` =
  4 MB. Only one CE (external strap) also answers at CPU boot address
  **`0x0000_0000`**; §9 shows that boot window as 32 MB "Static Memory
  (boot-up default)".
- **SMC00 other fields (§11.3 p105):** [12/11/10] per-CE segment write-enable
  (0=read-only, 1=writable); [9:8]/[7:6]/[5:4] per-CE flash type
  (00=NOR, 01=NAND, 1x=SPI NOR). Defaults: CE0=NOR, CE1=NAND, CE2=SPI (§11.1
  p100). `hwreg.h` supplies only `AST_SMC_BASE 0x16000000` (matches) and no SMC
  sub-registers.

> **QEMU-model divergence:** on the AST2400/G4 the flash controller is the FMC
> at `0x1E62_0000` (+ SPI at `0x1E63_0000`) with flash data mapped at
> `0x2000_0000`. The AST2050 has neither — it is SMC-at-`0x1600_0000` with data
> at `0x1000_0000`/`0x0000_0000`. **This is not in this datasheet for the G4;
> the G4 addresses are from mainline/G4 knowledge and flagged as such.**

---

## 4. AST2050-vs-AST2400 divergences a QEMU model MUST capture

Each item cites the AST2050 datasheet evidence; the *contrasting* AST2400/G4
behaviour is external knowledge and is explicitly marked
"**[G4: not in this datasheet]**".

- **Silicon revision ID.** `SCU7C` = **`0x00000202`** for AST2050-A3 (§18.2,
  p220, verbatim table). Firmware/QEMU part-detection keys off this. **[G4: not
  in this datasheet]** the AST2400 reports a `0x02000303`-class value — a model
  that returns the G4 value will be mis-detected as a newer part.
- **Interrupt controller shape.** One 32-bit VIC bank, offsets `0x00–0x38`, 32
  sources with the fixed §10 mapping (§16 p179–181, §10 p99). **[G4: not in this
  datasheet]** the AST2400 has 51 sources spread across a second register bank at
  `+0x40`. A faithful AST2050 model must expose *only* the single bank.
- **Flash controller.** Legacy **SMC at `0x1600_0000`**, flash data at
  `0x1000_0000` (and boot `0x0000_0000`), 32 MB default segments (§11 p100–105).
  **[G4: not in this datasheet]** the AST2400 uses FMC `0x1E620000` + SPI
  `0x1E630000`, flash at `0x2000_0000`.
- **Bus fabric is conventional PCI, not PCIe.** A2P bridge `0x1E72_0000`, PCI
  slave §33, PCI arbiter `0x1E78_C000`, PCI host windows `0x6000_0000` /
  `0x8000_0000` (§9 p97, §33 p363). The culvert "P2A" backdoor is the PCI-slave
  BAR path, not a PCIe X-DMA engine. **[G4: not in this datasheet]** the AST2400
  replaced this with PCIe + X-DMA.
- **DRAM limits.** 16-bit data bus only (MCR04[9:8] — *"others: Reserved"*),
  128 MB max, **no ECC** (§17 p185; §1.4/§1.5 p27–28). A model must not offer
  32-bit or >128 MB DRAM.
- **Peripheral roster.** Exactly 2 UARTs (§9 p97), single GPIO block (46 pins,
  §1.3.16 p23), single PWM/tach block (§28), USB2.0 **device/vhub only** (no
  USB1.1 host, §1.4 p27), **no ADC / no SD-eMMC / no eSPI** (absent from the §9
  map, p97). The 4 KB SoC-register page order at `0x1E78_x000` is
  GPIO/RTC/Timer/UART1/UART2/WDT/PWM/VUART/PUART/LPC/I2C/PECI/PCI-Arbiter
  (§9 p97) — a different population and, in several slots, a different occupant
  than the G4 map.
- **Shared `0x1E6E` page.** SDRAM MMC (`0x1E6E_0000`), SCU (`0x1E6E_2000`) and
  HACE (`0x1E6E_3000`) are three 4 KB blocks inside one 64 KB region, and the
  MMC block carries **AST2000-backward-compat SCU aliases** at MCR100/120/170
  (§17 p184). A model that assumes the flat G4 SCU-only layout at `0x1E6E_xxxx`
  will mis-decode.

---

## 5. Source-quote appendix (exact wording, with page)

- **Silicon revision ID value** (§18.2, p220): *"2: Represent A2/A3 silicon"*
  and table rows *"AST2050-A2  0x00000202"*, *"AST2050-A3  0x00000202"*,
  register header *"SCU7C: Silicon Revision ID Register   Init = 0x00000202"*.
- **SCU unlock password** (§18.2, p205): *"The password of the protection key is
  0x1688A8A8."*
- **Boot-speed strap** (§18.2, SCU70[16], p217): *"0 : ARM CPU will boot up at
  low speed mode (1/16 of full speed)   1 : ARM CPU will boot up at full speed
  mode … software must set this bit to 1 for full speed operation, else it will
  always operates at low speed mode."*
- **Boot-area remap** (§12.3, AHBC8C[0], p115): *"Boot Area Remap … 0: Mapping
  to Static memory   1: Mapping to SDRAM memory"* over range
  `0x0000_0000 ∼ 0x0FFF_FFFF`.
- **SMC flash apertures** (§11.1, p100): *"Base address of CE0: 0x10000000;
  Base address of CE1: 0x10000000 + (Segment Size); Base address of CE2:
  0x10000000 + (Segment Size x 2)."*
- **VIC size** (§16.1, p179): *"VIC supports up to 32 interrupt requests."*
- **DRAM width** (§17, MCR04[9:8], p185): *"01: Select 16-bit data bus width
  (DQ15–DQ0)   others: Reserved."*
- **Access-width caveat** (§9 note, p97): *"Program access the IP using
  un-supported access mode will get an un-predictable result."*

---

*Derived entirely from AST2050/AST1100 A3 Datasheet V1.05 (2010-05-25);
`hwreg.h` used only for cross-check. Any statement about the AST2400/G4 is
marked "[G4: not in this datasheet]" and is external knowledge, not a datasheet
claim.*

# AST2050 / AST1100 LPC Controller — Datasheet Extract

Source: **ASPEED AST2050/AST1100 A3 Datasheet, V1.05** (May 25, 2010).
File: `datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf`
(Copies also live under `asus-kgpe-d16-firmware/datasheets/` and
`dell-c410x-firmware/datasheets/`. The printed page numbers equal the physical
PDF page numbers, so `Read` the PDF at the pages cited directly.)

Purpose: authoritative reference for a **faithful QEMU model** of the AST2050 LPC
controller — the BMC's host-facing interface. OpenBMC drives the **IPMI KCS** and
**IPMI BT** channels through this block (the host BIOS/OS talks IPMI to the BMC),
the **port-80h snoop** for POST codes, and the host reaches BMC AHB through the
**iLPC2AHB** bridge (culvert's `ilpc` backend). Every value below carries a
datasheet page cite; where the datasheet is silent, this is stated.

**Base address of LPC Controller = `0x1E789000`** (§30, p.311; also §9 ARM
Address Space Mapping, p.97, "LPC Controller 1E78:9000-1E78:9FFF, 4K").
Physical address of register = base + offset.

> ⚠️ **The task brief's "IBT/BT at 0x1E789140" is the AST2400/2500 layout, not
> AST2050.** On the AST2050 (this datasheet) the IPMI **BT** register block lives
> at LPC offsets **0x48–0x68** (BTR0=0x48 … BTFVSR1=0x68, p.316–318). Offset
> 0x140 is where later Aspeed SoCs (G4/G5/G6) place their "iBT". A faithful
> AST2050 model must use the 0x48 layout. See §"AST2050 vs newer" below.

---

## 0. Where it lives in the datasheet

| What | Section | Page |
|---|---|---|
| Feature summary (§1.3.21 LPC Bus Interface) | ToC | p.24 |
| Overview + base + full register list | §30.1 | **p.311–312** |
| Features (dual mode, IPMI KCS/BT, SerIRQ, snoop) | §30.2 | p.312 |
| **Registers, base 0x1E789000** | §30.3 | **p.312–326** |
| HICR0–2 | | p.313 |
| HICR3–4, LADR3H/L | | p.314 |
| LADR12H/L, IDR1–3, ODR1–3, STR1 | | p.315 |
| STR2–3, BTR0–1 | | p.316 |
| BTCSR0–1, BTCR, BTDTR, BTIMSR | | p.317 |
| BTFVSR0–1, SIRQCR0–2 | | p.318 |
| SIRQCR3, **HICR5 (iLPC2AHB)** | | p.319 |
| HICR6/HICR7 (iLPC2AHB), | | p.320 |
| HICR8, SNPWADR, SNPWDR, LHCR0 | | p.321 |
| LHCR0–3 (LPC Host Controller) | | p.322–324 |
| LHCR4–B | | p.325–326 |
| Interrupt: **LPC = INT#8**, sensitive high level | §10 Table 36 | p.99 |

**Overview verbatim (p.311):** *"AST2050 / AST1100 integrates both LPC Host
Controller and LPC Slave Controller, but only one of the two controllers can be
enabled at one time. LPC Slave Controller also integrates IPMI 2.0/1.1 compliant
BMC controller. There are totally 49 registers…"* and (p.312) *"The definition of
BMC related registers, from offset 0x00 to offset 0x7C, are basically compatible
with the popular BMC controller — H8S/2168."* So the KCS/BT programming model is
**H8S/2168-compatible**, not the AST2400 model.

**Features (p.312):** directly on APB; dual modes — **Master** (update host BIOS /
TPM / LPC keyboard controller via I/O, memory, firmware cycles) and **Slave** (BMC
functions); Serial IRQ; port 80h/81h snoop with interrupt; two Virtual UART
(16550) sets; **IPMI 2.0 KCS + BT**: Channel #1 KCS, Channel #2 KCS, Channel #3
KCS *or* BT; three I/O channels each with IDR/ODR/STR; **two 64×8 embedded SRAMs
for BT**; LPC S/W & H/W power-down; LPC Abort monitoring.

---

## 1. Full register map (offsets from p.311–312, confirmed in per-register tables)

`R`=readable `W`=writable `W1C`=write-1-clear `W0C`=write-0-clear
`W1S`=write-1-set `W1T`=write-1-toggle `U`=unknown-at-reset. Two access columns
in the datasheet — **Slave** (BMC/ARM side) and **Host** (LPC host side).

| Off | Reg | Init | Purpose |
|----|-----|------|---------|
| 0x00 | HICR0 | 0 | Host Interface Control 0 — channel enables |
| 0x04 | HICR1 | 0 | Host Interface Control 1 — busy/reset/shutdown |
| 0x08 | HICR2 | 0 | Host Interface Control 2 — IPMI interrupt status/enables |
| 0x0C | HICR3 | U | LPC pin monitoring (LFRAME/CLKRUN/SERIRQ/LRESET/LPCPD/PME) |
| 0x10 | HICR4 | U | Ch#3 KCS/BT enable, LADR12 select |
| 0x14 | LADR3H | 0 | Channel #3 host I/O address [15:8] |
| 0x18 | LADR3L | 0 | Channel #3 host I/O address [7:0] |
| 0x1C | LADR12H | 0 | Channel #1/#2 host I/O address [15:8] |
| 0x20 | LADR12L | 60h/62h | Channel #1/#2 host I/O address [7:0] |
| 0x24 | IDR1 | U | **KCS ch#1 Input Data** (host→BMC) |
| 0x28 | IDR2 | U | **KCS ch#2 Input Data** |
| 0x2C | IDR3 | U | **KCS ch#3 Input Data** |
| 0x30 | ODR1 | U | **KCS ch#1 Output Data** (BMC→host) |
| 0x34 | ODR2 | U | **KCS ch#2 Output Data** |
| 0x38 | ODR3 | U | **KCS ch#3 Output Data** |
| 0x3C | STR1 | 0 | **KCS ch#1 Status** |
| 0x40 | STR2 | 0 | **KCS ch#2 Status** |
| 0x44 | STR3 | 0 | **KCS ch#3 Status** |
| 0x48 | BTR0 | 0 | **BT** Status Register 0 (host-side interrupts) |
| 0x4C | BTR1 | 0 | **BT** Status Register 1 |
| 0x50 | BTCSR0 | 0 | **BT** Control/Status 0 — FIFO sel + int enables |
| 0x54 | BTCSR1 | 0 | **BT** Control/Status 1 — int enables |
| 0x58 | BTCR | 0 | **BT Control Register** (the IPMI BT_CTRL) |
| 0x5C | BTDTR | U | **BT Data Buffer** (the BT FIFO data port) |
| 0x60 | BTIMSR | 0 | **BT** Interrupt Mask Register |
| 0x64 | BTFVSR0 | 0 | **BT** FIFO valid size (host-write transfer) |
| 0x68 | BTFVSR1 | 0 | **BT** FIFO valid size (host-read transfer) |
| 0x70 | SIRQCR0 | 0 | SERIRQ Control 0 |
| 0x74 | SIRQCR1 | 0 | SERIRQ Control 1 |
| 0x78 | SIRQCR2 | 0 | SERIRQ Control 2 |
| 0x7C | SIRQCR3 | 0 | SERIRQ Control 3 (output select) |
| 0x80 | HICR5 | 0 | **iLPC2AHB** enable + IRQX + snoop enables |
| 0x84 | HICR6 | 0 | **iLPC2AHB** decode range + snoop int status |
| 0x88 | HICR7 | 0 | **iLPC2AHB** remap base [31:16] |
| 0x8C | HICR8 | 0 | **iLPC2AHB** remap mask [31:16] |
| 0x90 | SNPWADR | U | Port-80h snoop address #0/#1 |
| 0x94 | SNPWDR | U | Port-80h snoop data #0/#1 |
| 0xA0 | LHCR0 | — | LPC **Host** Controller ctrl 0 (APB→LPC bridge) |
| 0xA4 | LHCR1 | U | LPC Host ctrl 1 — timeout, abort, fire |
| 0xA8 | LHCR2 | 0 | LPC Host ctrl 2 — SIRQ/int enables |
| 0xAC | LHCR3 | U | LPC Host ctrl 3 — busy/wait/int status |
| 0xB0 | LHCR4 | U | LPC Host ctrl 4 — APB→LPC base, command, header |
| 0xB4 | LHCR5 | U | LPC Host ctrl 5 — host address |
| 0xB8 | LHCR6 | U | LPC Host ctrl 6 — host write data |
| 0xBC | LHCR7 | U | LPC Host ctrl 7 — host read data (RO) |
| 0xC0 | LHCR8 | U | reserved |
| 0xC4 | LHCR9 | U | reserved |
| 0xC8 | LHCRA | U | LPC Host SIRQ edge-trigger mode [20:0] |
| 0xCC | LHCRB | U | LPC Host SIRQ high/rising-trigger mode [20:0] |

---

## 2. IPMI KCS channels (data / status / command)

Three KCS channels, each a classic H8S/2168 KCS interface = one **Input Data
Register (IDR)**, one **Output Data Register (ODR)**, one **Status Register
(STR)**, plus a host **I/O address** register (LADR). (p.315)

**Channel enables — HICR0 (0x00, p.313):**
- bit7 `LPC3E` — Enable LPC Channel #3 (Slave RW)
- bit6 `LPC2E` — Enable LPC Channel #2
- bit5 `LPC1E` — Enable LPC Channel #1
- bit3 `SDWNE` — Enable LPC software shutdown; bit2 `PMEE` — Enable PME output

**Channel #3 mode select — HICR4 (0x10, p.314):**
- bit7 `LADR12AS` — Channel address selection (use LADR12H or LADRL)
- bit2 `KCSENBL` — **Enable KCS interface in Channel #3**
- bit0 `BTENBL` — **Enable BT interface in Channel #3**
(So Channel #3 is either KCS *or* BT, chosen here.)

**Host I/O addresses (LADR, p.314–315):** these set the LPC I/O port the host
uses to reach a channel.
- `LADR3H`/`LADR3L` (0x14/0x18): Channel #3 host address bits [15:0] (Slave RW).
- `LADR12H`/`LADR12L` (0x1C/0x20): Channel #1/#2 host address [15:0], selected by
  `LADR12AS` (HICR4[7]). **`LADR12L` resets to `60h`/`62h`** (p.315) — i.e. the
  classic keyboard-controller / KCS default host ports.

**Data registers (p.315):**
- `IDR1/2/3` (0x24/0x28/0x2C): Channel N input data [7:0]. Slave=R, Host=W
  (host writes command/data to the BMC).
- `ODR1/2/3` (0x30/0x34/0x38): Channel N output data [7:0]. Slave=RW, Host=R
  (BMC posts response bytes; host reads them).

**Status register (STR1 0x3C, STR2 0x40, STR3 0x44, p.315–316):**
- bit0 `OBF1` — Output data register full (Slave RW0C, Host R)
- bit1 `IBF1` — Input data register full (Slave R, Host R)
- bit2 `DBU12` — "Defined by user"
- bit3 `C/D1` — **Command/Data** (host wrote to command vs data port; Slave R, Host R)
- bit4..7 `DBU14..DBU17` — "Defined by user"

**KCS ↔ IPMI mapping.** This is the standard IPMI KCS SMS interface: the host sees
two I/O ports at `LADR` (even = data, odd = command/status). `OBF`/`IBF`
flow-control the byte handshake; `C/D` tells the BMC whether the host wrote a
command or a data byte. The IPMI KCS *state* bits (S0/S1) and `SMS_ATN` are **not
hardwired** — the datasheet marks bits 2,4–7 as *"Defined by user"* (p.315), so
firmware places the IPMI state/attention bits there per the IPMI spec. The
datasheet is **silent** on the exact user-bit assignment; do not invent one.

**IPMI interrupt status/enables — HICR2 (0x08, p.313):**
- bit6 `LRST` (RW0C) LPC reset int status; bit5 `SDWN` shutdown int status;
  bit4 `ABRT` LPC Abort int status; bit3 `IBFIF3` enable IBFI3 int;
  bit2 `IBFIF2` enable IDR2 receive-completion int; bit1 `IBFIE1` enable IDR1
  receive-completion int; bit0 `ERRIE` enable error int.

**OpenBMC use:** the mainline/OpenBMC IPMI KCS driver (`drivers/char/ipmi/
kcs_bmc_aspeed.c`, plus `kcs_bmc.c` and phosphor-host-ipmid) exposes each channel
to userspace; the host BIOS/OS IPMI stack does IPMI messaging (`ipmitool`, ID
0x20) over the KCS port. Receive-completion is signalled to the ARM via the
`IBFIFn` interrupts (HICR2) and to the host via SERIRQ (below).

---

## 3. IPMI BT (Block Transfer) interface — offsets 0x48–0x68

Channel #3 in BT mode (`HICR4.BTENBL`=1). BT uses a FIFO (two 64×8 SRAMs, p.312)
rather than single-byte KCS handshaking. Register map (p.316–318):

**BTCR — BT Control Register (0x58, p.317) — the IPMI `BT_CTRL`:**
| bit | name | Slave | Host | meaning |
|--|--|--|--|--|
| 7 | `B_BUSY` | RW | R | BMC busy (BT write-transfer busy) |
| 6 | `H_BUSY` | R | W1T | Host busy (BT read-transfer busy) |
| 5 | `OEM0` | RW | RW0S | user-defined |
| 4 | `BEVT_ATN` | RW1S | RW1C | Event/SMS attention (the BT `SMS_ATN`) |
| 3 | `B2H_ATN` | RW1S | RW1C | BMC→Host buffer write-end (BMC has a message) |
| 2 | `H2B_ATN` | RW0C | RW1S | Host→BMC buffer write-end (host has a message) |
| 1 | `CLR_RD_PTR` | RW0C | W1S | Clear read pointer |
| 0 | `CLR_WR_PTR` | RW0C | W1S | Clear write pointer |

This is the canonical IPMI BT control register bit-for-bit
(`B_BUSY/H_BUSY/OEM0/SMS_ATN/B2H_ATN/H2B_ATN/CLR_RD_PTR/CLR_WR_PTR`).

**BTDTR — BT Data Buffer (0x5C, p.317):** [7:0] BT mode buffer read/write data
(Slave RW, Host RW). The single FIFO data port; both sides read/write message
bytes here after setting the pointer-clear bits.

**BTR0 — BT Status 0 (0x48, p.316, RW0C):** bit4 `FRDI` FIFO read-request int,
bit3 `HRDI` BT host read int, bit2 `HWRI` BT host write int, bit1 `HBTWI` BTDTR
host-write-start int, bit0 `HBTRI` BTDTR host-read-end int.
**BTR1 — BT Status 1 (0x4C, p.316, RW0C):** bit6 `HRSTI` BT reset int, bit4
`BEVTI` BEVT_ATN-clear int, bit3 `B2HI` read-end int, bit2 `H2BI` write-end int,
bit1 `CRRPI` read-pointer-clear int, bit0 `CRWPI` write-pointer-clear int.
**BTCSR0 (0x50, p.317):** bit6/5 `FSEL1/FSEL0` BT transfer FIFO selection; bits4–0
`FRDIE/HRDIE/HWRIE/HBTWIE/HBTRIE` enable the BTR0 interrupts.
**BTCSR1 (0x54, p.317):** bit7 `RSTREN` enable slave reset read, bit6 `HRSTIE`,
bits4–0 `BEVTIE/B2HIE/H2BIE/CRRPIE/CRWPIE` enable the BTR1 interrupts.
**BTIMSR — BT Interrupt Mask (0x60, p.317–318):** bit7 `BMC_HWRST` slave reset
(Slave RW0C / Host RW1S), bits4–2 `OEM3/OEM2/OEM1` user-defined.
**BTFVSR0 (0x64) / BTFVSR1 (0x68) (p.318, R):** valid byte count in the FIFO for
host-write / host-read transfers respectively (`N7..N0`).

**OpenBMC use:** the mainline IPMI BT driver (`drivers/char/ipmi/bt-bmc.c`) maps
`BT_CTRL`(=BTCR), the data port (=BTDTR) and the interrupt-mask (=BTIMSR); OpenBMC
moves whole IPMI messages through the FIFO. Note the driver's register offsets
assume the AST2400+ layout (BT at 0x140) — see §"AST2050 vs newer".

---

## 4. Serial IRQ (SERIRQ) — SIRQCR0–3 (0x70–0x7C)

Routes BMC-side IPMI attention to a host IRQ over the LPC SERIRQ line so the host
IPMI driver need not poll. (p.318–319)
- `SIRQCR0` (0x70): bit7 `Q_C` Quiet/Continuous mode flag (R); bit5 `IEDIR`
  Interrupt Enable Direct mode; bit3 `SMIE3A` host SMI enable 3A; bit2 `SMIE2`
  host SMI enable 2; bit1 `IRQ12E1` host IRQ12 enable; bit0 `IRQ1E1` host IRQ1
  enable.
- `SIRQCR1` (0x74): per-source host IRQ enables (`IRQ11E3/IRQ10E/IRQ9E3/IRQ6E3`
  and `IRQ11E2/IRQ10E2/IRQ9E2/IRQ6E2`).
- `SIRQCR2` (0x78): bit7 `IEDIR3` Interrupt Enable Direct mode 3.
- `SIRQCR3` (0x7C): `SELIRQ11/10/9/6`, `SELSMI`, `SELIRQ12`, `SELIRQ1` — select
  which SERIRQ line each channel drives.

---

## 5. iLPC2AHB bridge — the culvert `ilpc` path (HICR5–HICR8)

This is the **LPC→AHB backdoor**: the host, over LPC, reaches arbitrary BMC AHB
addresses (memory-mapped registers, SRAM). culvert's `ilpc` backend uses exactly
this. All four registers are in the **Slave** register set (BMC-writable), but the
host can reach them via the same bridge / SuperIO path once partially enabled.

**HICR5 (0x80, p.319–320):**
- [31:24] `HWMBASE` — **LPC→AHB bridge address decoding base bit [31:24]** (which
  host LPC addresses the bridge claims).
- [23:20] `ID3IRQX`, [19:16] `ID2IRQX` — select IRQX ID for channel #3 / #2.
- [15] `SEL3IRQX`, [14] `IRQXE3`, [13] `SEL2IRQX`, [12] `IRQXE2` — IRQX select /
  enable for channels #3 / #2 (the "KCS channel #2 IRQX" used by the A3 nIRQ→host
  feature, see p.7 migration note).
- [10] `ENFWH` — **Enable LPC FWH cycles** (the bridge decodes FWH/firmware-hub
  cycles).
- [9] `ENINT_PME` — enable PME# interrupt.
- [8] `ENL2H` — **Enable LPC to AHB bridge** (master enable for the backdoor).
- [5] `ENSET_SF` enable SIRQ start-frame capability; [4] `ENLCLK_REQ` enable
  LCLK/CLOCKRUN# request; [3] `ENINT_SNP1W` / [1] `ENINT_SNP0W` snoop int enables;
  [2] `EN_SNP1W` / [0] `EN_SNP0W` snoop enables (port-80h, §6).

**HICR6 (0x84, p.320):**
- [27:24] `HWNCARE` — **Address decoding range control [27:24] of the LPC→AHB
  bridge** (a "don't-care" mask that widens the window that `HWMBASE` matches).
- [2] `STR_PME` (RW1C) PME# int status; [1] `STR_SNP1W` / [0] `STR_SNP0W` snoop
  int status (RW1C).

**HICR7 (0x88, p.320):** [31:16] `ADRBASE` — **Remapping address base [31:16] of
the LPC→AHB bridge** (top half of the BMC AHB address the matched host cycle is
redirected to).
**HICR8 (0x8C, p.321):** [31:16] `ADRMASK` — **Remapping address mask [31:16] of
the LPC→AHB bridge**.

**How the backdoor works (synthesised from the four register descriptions):** the
host issues an LPC FWH/memory cycle; the bridge claims it when the host address's
top bits match `HWMBASE[31:24]` within the range loosened by `HWNCARE[27:24]`;
the matched host address is then remapped into a BMC **AHB** address via
`ADRBASE`/`ADRMASK` (top half taken from `ADRBASE` where `ADRMASK` selects). With
`ENL2H`(HICR5[8]) and `ENFWH`(HICR5[10]) set, an external host can therefore
read/write any AHB location — the essence of the iLPC2AHB exploit. The revision
history (p.7, item 4) shows the *same* HICR5/7/8 used to point the host at the
`0x1E78xxxx` APB block (`HICR7[31:16]=16'h1e78, HICR8[31:16]=16'hffff`) when
remapping PUART as a host COM port — concrete confirmation of the remap math.

**SuperIO / host-config:** the AST2050 does **not** document a discrete
`0x2E/0x2F` SuperIO index/data block in this chapter (**datasheet silent** here).
The host-visible "SuperIO"-style configuration is these HICR/LADR/SIRQCR slave
registers, reached either from the BMC side (APB) or from the host through the
iLPC2AHB bridge itself (and the VUART/PUART logical devices, §29). On AST2050
there is **no SCU "SIO decode disable" lockdown listed** for this bridge — it is
gated purely by `ENL2H`/`ENFWH`. (A faithful security model should note the
backdoor is enabled by these bits alone.)

---

## 6. Port-80h POST-code snoop — SNPWADR / SNPWDR (0x90/0x94)

- `SNPWADR` (0x90, p.321): [31:16] snoop address #1, [15:0] snoop address #0 —
  set to `80h`/`81h` to watch host BIOS I/O-write cycles.
- `SNPWDR` (0x94, p.321): [15:8] snoop #1 data, [7:0] snoop #0 data — records the
  last data of matched LPC write cycles (auto-updated).
Enabled via `HICR5.EN_SNP0W/EN_SNP1W`; interrupt via `ENINT_SNP0W/1W`; status in
`HICR6.STR_SNP0W/1W`. OpenBMC's `aspeed-lpc-snoop` driver reads `SNPWDR` for POST
codes.

---

## 7. LPC **Host** Controller (Master mode) — LHCR0–LHCRB (reverse direction)

Distinct from the iLPC2AHB backdoor: this is the **APB→LPC bridge** that lets the
**BMC** master the LPC bus to update the *host's* BIOS flash / TPM. Not the
culvert path. Enable only when the host is fully shut down (LPC has no
multi-master). Key registers:
- `LHCR0` (0xA0, p.321–322): bit4 `ENP2L` **Enable APB to LPC bridge**; bit0
  `ENLPC-HOST` **Enable LPC Host Controller** (*"only when host platform has been
  full shutdown; otherwise… serious LPC bus conflictions"*, p.322); bit2
  `ENLHSIRQ`; bit1 `ENLHTM-OUT`; bit23 `LRSTNO`/bit15 `LRSTNOEN` LPC reset-pin
  drive; **bit12** *"Disable vector interrupt output connected to host serial
  IRQ"* (init 1) — the A3 feature that feeds the VIC `nIRQ` to the host through
  KCS channel #2 IRQX (p.7 migration item 7).
- `LHCR1` (0xA4, p.323): [31:16] `LHTMOUTLMT` timeout limit; bit1 `LHS-ABORT`
  force abort; **bit0 `LHFIRE`** fire one LPC bus cycle (using LHCR4/5/6; read
  data latched to LHCR7).
- `LHCR2` (0xA8, p.323–324): [28:8] `ENLHSR-INT` per-source SIRQ int enables
  (bit[0]=IRQ0 … [15]=IRQ15, [16]=IOCK, [17]=INTA … [20]=INTD); bit3
  `ENLHTO-INT`, bit2 `ENLHES-INT`, bit1 `NLHNS-INT`, bit0 `ENLHDN-INT`.
- `LHCR3` (0xAC, p.324): bit31 `LHBUSY`, bit30 `LHWAIT` (RO status); [28:8]
  `STR_LHSRINT` SIRQ int status (W1C); bit3 `STR_LHTOINT`, bit2 `STR_LHESINT`,
  bit1 `STR_LHNSINT`, bit0 `STR_LHDNINT`.
- `LHCR4` (0xB0, p.325): [31:28] `P2LBASE` APB→LPC remap base; [7:4] `LHCMD` LPC
  host command; [3:0] `LHHDR` LPC host start header.
- `LHCR5` (0xB4): `LHADR` [31:0] LPC host address.
- `LHCR6` (0xB8): `LHTXD` [31:0] LPC host write data.
- `LHCR7` (0xBC, RO): `LHRXD` [31:0] LPC host read data (latched from last cycle).
- `LHCR8`/`LHCR9` (0xC0/0xC4): reserved.
- `LHCRA` (0xC8): `LSIRQEG` [20:0] SIRQ edge-trigger mode.
- `LHCRB` (0xCC): `LSIRQHV` [20:0] SIRQ high/rising-trigger mode.

---

## 8. Interrupt

LPC controller → **VIC INT#8**, *"Sensitive high level trigger"* (§10 Table 36,
p.99). Both the KCS `IBFIFn` completions (HICR2) and the BT interrupts (BTR0/BTR1)
funnel to this single line on the ARM side; SERIRQ (§4) delivers attention to the
*host* side.

---

## 9. AST2050 vs AST2400 / 2500 / 2600 — what a faithful model must capture

1. **BT/iBT offset differs.** AST2050 BT block = **0x48–0x68** (H8S/2168 layout,
   p.316–318). AST2400/2500/2600 place the "iBT" at **0x140**. The task brief's
   `0x1E789140` is the *newer* layout. → An AST2050 model must not reuse the
   AST2400 offsets; mainline `bt-bmc.c` / `aspeed_lpc.c` assume 0x140.
2. **KCS is H8S/2168-style** (IDR/ODR/STR triples at 0x24–0x44, user-defined
   status bits) rather than the AST2400 named `KCSn` register set with hardwired
   `SMS_ATN`. Channel #3 is KCS-*or*-BT (`HICR4`), not four fixed KCS channels.
3. **iLPC2AHB registers at HICR5–8 (0x80–0x8C)** with `ENL2H` as the enable and
   `HWMBASE/HWNCARE`+`ADRBASE/ADRMASK` as decode/remap. Later SoCs relocate these
   (HICR7/8/9 etc.) and add an **SCU-based SIO-decode lock**; AST2050 has **no
   such lock** here — the backdoor is gated only by the HICR bits.
4. **Only one of Host/Slave controller may be enabled at a time** (p.311).
5. `LADR12L` reset default `60h/62h` (p.315) is an AST2050 specific reset value.

## 10. Does mainline QEMU model it?

- `hw/misc/aspeed_lpc.c` **does** model the AST2400/2500/2600 LPC controller —
  KCS channels 1–4 and the **iBT** (at the 0x140 layout), plus SerIRQ. It does
  **not** implement the AST2050/H8S2168 layout (BT at 0x48, KCS IDR/ODR/STR,
  Ch#3 KCS-or-BT). So the modelled KCS/BT logic exists but at the **wrong
  offsets** for AST2050 — a derived model is needed.
- The **iLPC2AHB** bridge is generally **not** modelled as a functional
  host→AHB path in QEMU (no MMIO passthrough). For the `kgpe-d16-bmc` machine,
  culvert's `ilpc` backend has nothing to talk to unless this is added.
- Bottom line for the AST2050 QEMU model: reuse the *concepts* from
  `aspeed_lpc.c` but re-map the register file to the 0x00–0xCC AST2050 layout
  above, and (optionally) implement the iLPC2AHB decode/remap into the machine's
  AHB address space for culvert-`ilpc` faithfulness.

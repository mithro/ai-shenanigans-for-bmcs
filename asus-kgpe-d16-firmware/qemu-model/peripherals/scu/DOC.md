# SCU (System Control Unit) — AST2050 driver + faithfulness doc

**Base 0x1E6E2000.** The SCU owns SoC identity, the clock tree (PLLs, dividers,
gates), per-controller resets, hardware straps, and pin-mux. It gates *everything*
— wrong SCU behaviour means wrong CPU/timer/UART clocks and mis-detected silicon.

Full register-by-register datasheet reference (every offset, reset value, bitfield,
page cite): **[`DATASHEET-SCU.md`](DATASHEET-SCU.md)** (A3 V1.05 §18, pp.204–220).
This file is the *driver + QEMU-faithfulness* view.

## 1. What a driver must know (U-Boot / Linux / Zephyr)

- **Unlock before writing.** Write `0x1688A8A8` to SCU00 to unlock; writes to
  SCU04..SCU7C are dropped while locked. Read SCU00 → `1` unlocked / `0` locked
  (not the key back). Re-lock (write anything else) when done.
- **Clock tree (see DATASHEET-SCU.md §17).** 24 MHz fixed reference →
  H-PLL (SCU24) → CPU clock; HCLK = CPU / `SCU70[13:12]` ratio (1:1/2:1/4:1/3:1);
  **PCLK (APB) = H-PLL / SCU08[25:23]** (÷2..÷16, reset ÷16); M-PLL (SCU20) → MCLK
  (DRAM). The **ASPEED APB timer @0x1E782000 is clocked from PCLK**, so timer tick
  fidelity depends on H-PLL + SCU08[25:23]. **UART baud = 24 MHz (÷13 optional via
  SCU2C[12]) / (16 × DLL)** — decoupled from the H-PLL entirely.
- **CPU speed comes from straps by default.** SCU24[18]=0 → H-PLL uses the
  `SCU70[11:9]` strap (100/133/166/200 MHz), *not* the programmed SCU24 value.
  A mainline `clk-aspeed` driver / U-Boot reads these to compute rates.
- **DRAM handshake.** SCU40 carries the ASPEED VBIOS handshake: `[7]`=firmware-
  inits-DRAM, `[6]`=DRAM-ready, `[31:24]`=`0x5A` boot key (Raptor uses exactly
  this — DATASHEET-SCU.md §12).
- **Reset source.** SCU3C `[0]` power-on / `[1]` WDT / `[2]` external reset flags.

## 2. AST2050 (G3) quirks vs AST2400/2500/2600 — what the model MUST get right

From DATASHEET-SCU.md §18 (each is a real divergence, not cosmetic):

1. **PLL post-divider `[14:12]` on SCU20/SCU24** (÷1/2/4/8/16) — present on the
   AST2050, **absent in stock QEMU AST2400 `calc_hpll`/`calc_mpll`**. Without it the
   reset value `0x00004291` computes **264 MHz instead of the datasheet's 133 MHz**.
2. **SCU24[18] strap-vs-programmed** — CPU clock at reset comes from `SCU70[11:9]`,
   not the programmed register.
3. **No reference-clock strap** — CLKIN is **fixed 24 MHz**; there is no 24/25/48 MHz
   select bit (AST2400/2500 have one). Do not model a configurable CLKIN.
4. **SCU register file ends at 0x7C** — no AST2400/2500 `0x80+` block. The
   AST2000-compat M-PLL shadow lives at `0x1E6E0120` in the **SDRAM controller**.
5. **Two reset registers** — SCU04 (per-controller holds) *and* SCU3C (reset flags).
6. **Strap layout (SCU70)** is G3-specific: `[1:0]` boot, `[3:2]` VGA size,
   `[8:6]` MAC mode, `[11:9]` H-PLL freq, `[13:12]` CPU:AHB ratio, `[16]` full-speed.
7. **Rev-id (SCU7C)** — A2 and A3 both `0x00000202`; family nibble in `[15:8]`.

## 3. Golden reset values (datasheet Init) — what the firmware test checks

| Reg | Datasheet Init (real AST2050) | QEMU (`aspeed.scu-ast2050`) | Status |
|---|---|---|---|
| SCU04 sysreset | `0x000FFE5C` | `0x000FFE5C` | ✓ FIXED |
| SCU08 clksel | `0xE3F00070` | `0xE3F00070` | ✓ FIXED |
| SCU0C clkstop | `0x000C3E8B` | `0x000C3E8B` | ✓ FIXED |
| SCU20 mpll | `0x00004291` | `0x00004291` | ✓ FIXED |
| SCU24 hpll | `0x00004291` | `0x00004291` | ✓ FIXED |
| SCU3C resetflags | `0x00000001` | `0x00000001` | ✓ FIXED |
| SCU74 pinmux1 | `0x40048000` | `0x40048000` | ✓ FIXED |
| **SCU7C revid** | **`0x00000202`** | **`0x00000202`** | ✓ FIXED |
| SCU00 protect (read) | `0x00000000` (locked) | `0x1688a8a8` | ⚠ n/a via `-kernel` |

All reset-value gaps closed by the G3 reset table (`aspeed.scu-ast2050`);
`peripherals/scu/fwtest.c` → **8/8 checks PASS**. **SCU00 lock-state is not
testable via this harness** — QEMU pre-unlocks the SCU on a `-kernel` boot (no
U-Boot to unlock it), so `prot` reads the key back. The model itself is faithful
(default `hw-prot-key`=0 = locked); validate via a flash/U-Boot boot later.

## 4. Faithful-model plan (QEMU `mithro/qemu@ast2050-faithful`)

- [x] **Rev-id** SCU7C `0x00000202` — `AST2050_A1_SILICON_REV` fixed; wired to the
  machine (boot-safe: the modern-kernel direct boot passes CI with it).
- [~] **G3 reset table** (`ast2050_a3_resets`) — implemented + fwtest-validated (8/8
  when applied), but **NOT applied by default**. CI proved it breaks the legacy
  boots tuned for the AST2400 machine: the **OpenBMC AST2400 U-Boot** and the
  **RE-patched Dell vendor firmware** read AST2400 SCU values the G3 map zeroes
  (UART_HPLL_CLK 0x160, SOC_SCRATCH1 DRAM-ready, …) → the boot hangs. The machine
  keeps the AST2400 reset table (+ faithful rev-id); the G3 table is the **opt-in**
  table for the co-evolution work. *Same lesson as the VIC: a faithful G3 SoC needs
  a G3-aware firmware stack.*
- [ ] **PLL post-divider** — G3 `calc_hpll`/`calc_mpll` applying `[14:12]`, and
  `get_apb` using SCU08[25:23]; so the emulated CPU/PCLK (→ timer) is 133 MHz not
  264. *Deferred to the timer peripheral (needs clock-rate, not register, testing;
  the reset SCU24[18]=0 strap path is unaffected).*
- [ ] **Strap (SCU70)** — seed `hw-strap1` with the **G3 bit layout** (clksel[11:9],
  cpu:ahb[13:12], MAC[8:6], VGA[3:2], boot[1:0]) matching the KGPE-D16. *Currently
  a G4-macro value; decoded in the fwtest but not yet asserted.*
- [ ] **SCU00 lock-state** — faithful in the model (`hw-prot-key`=0), but not
  observable through the `-kernel` harness (QEMU pre-unlocks). Validate via
  flash/U-Boot boot.

## 5. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ dumps+decodes the whole file; 8 golden checks |
| 2 | doc (this file + `DATASHEET-SCU.md`) | ☑ |
| 3 | QEMU model | ◐ rev-id faithful + wired; G3 reset table built but opt-in (co-evolution); PLL/strap pending |
| 4 | integration test (`../../integration/test_scu.py`) | ◐ rev-id + reset-flag pass; 6 reset-table checks xfail (co-evolution) |

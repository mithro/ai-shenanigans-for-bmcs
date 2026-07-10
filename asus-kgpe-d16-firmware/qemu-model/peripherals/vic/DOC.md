# VIC (interrupt controller) — AST2050 driver + faithfulness doc

**Base 0x1E6C0000.** The AST2050 VIC is a **single 32-bit bank** of 13 registers
(offsets 0x00–0x38) covering **32 interrupt sources** — *not* the AST2400's
two-bank, 64-source interleaved VIC that stock QEMU `aspeed_vic.c` models.

Full register + source-table reference (page-cited): **[`DATASHEET-VIC.md`](DATASHEET-VIC.md)**
(datasheet §16 pp.179–182; source assignment §10 Table 36 p99).

## 1. Register map (§16) — all reset 0

| Off | Register | R/W | Notes |
|---|---|---|---|
| 0x00 | IRQ status | R | pending & enabled & (IRQ-selected) |
| 0x04 | FIQ status | R | pending & enabled & (FIQ-selected) |
| 0x08 | raw status | R | raw pending (pre-mask) |
| 0x0C | IRQ/FIQ select | RW | 1 = route source to FIQ |
| 0x10 | enable (set) | RW | write 1 = unmask |
| 0x14 | enable clear | W | write 1 = mask |
| 0x18 | soft-int set | RW | write 1 = assert soft IRQ |
| 0x1C | soft-int clear | W | write 1 = deassert |
| 0x20 | protection | RW | bit0 |
| 0x24 | sensitivity | RW | 1 = level, 0 = edge |
| 0x28 | both-edge | RW | 1 = trigger on both edges |
| 0x2C | event | RW | 1 = active-high / rising |
| 0x38 | edge status clear | W | write 1 = clear latched edge |

## 2. Interrupt sources (§10 Table 36) and their trigger types

| IRQ | Source | Trigger |
|---|---|---|
| 2 / 3 | MAC1 / MAC2 | level-high |
| 5 | USB2.0 | level-high |
| 9 / 10 | UART1 / UART2 | level-high |
| 12 | I2C/SMBus | level-high |
| 16 / 17 / 18 | Timer1 / Timer2 / Timer3 | **rising-edge** |
| 20 | GPIO | level-high |
| 22–26 | RTC (5 sources) | **both-edge** |
| 27 | WDT | rising-edge |
| 31 | AHB controller | level-high |

The firmware-programmed trigger words (level/edge/polarity) reconstruct
**bit-for-bit** from this table and match real silicon (culvert capture):
`sensitivity=0x903897FE`, `both-edge=0x07C00000`, `event=0x983F97FE`. These are
*programmed* values; the registers **reset to 0**.

## 3. Driver notes (U-Boot / Linux / Zephyr)

- Mainline Linux binds via a G3 VIC irqchip (`aspeed,ast2050-vic`; see the
  culvert-session `irq-aspeed-g3-vic.c`). Init: program `sensitivity`/`both-edge`/
  `event` per Table 36, then `enable` the sources in use; ack edge IRQs by writing
  `edge-clear` (0x38). Timers 16/17/18 are **rising-edge** — the clocksource/event
  driver depends on this being modelled correctly, or timer IRQs are lost.
- The single-bank layout means **no** 64-bit / `(L)/(H)` register pairs and **no**
  registers above 0x38.

## 4. QEMU faithfulness — current gaps (fwtest baseline)

`peripherals/vic/fwtest.c` vs the current AST2400-based model:

| Check | Golden (G3) | Current QEMU | Status |
|---|---|---|---|
| irq/fiq/raw/select/enable/softint/protect reset | 0 | 0 | ✓ (7) |
| sensitivity (0x24) reset | 0 | `0xfff8ffff` | ✗ |
| both-edge (0x28) reset | 0 | `0x00070000` | ✗ |
| event (0x2C) reset | 0 | `0xfff8ffff` | ✗ |
| 0x24/0x28/0x2C writable (RW) | writes stick | masked (writes lost) | ✗ (3) |

Root cause: `aspeed_vic.c` models the AST2400 — 64-bit `sense`/`dual_edge`/`event`
**hardwired** at reset and only partially writable (only the top-4 GPIO IRQs may
change `event`). The AST2050 registers are 32-bit, reset 0, fully RW.

## 5. Faithful-model plan (QEMU `mithro/qemu@ast2050-faithful`)

The **`aspeed.vic-ast2050`** type (`TYPE_ASPEED_2050_VIC`, a `bool ast2050`
variant) is implemented and **passes 13/13 fwtest checks when wired** — trigger
config resets 0 and is fully writable. **It is NOT wired to the machine by
default**, for a reason CI proved:

> **Faithful VIC ⟹ needs a faithful kernel driver.** With the G3 VIC wired, the
> C2 kernel boots to userspace and then **hangs — the timer IRQ dies at ~0.83 s**.
> The mainline `aspeed,ast2400-vic` driver treats the VIC trigger config as *fixed
> AST2400 hardware defaults* (its writes go to the read-only 0x80+ bank), so on a
> faithful G3 VIC (reset 0) the timer's rising-edge config is never programmed and
> the IRQ never fires. The "working" C1–C4 boots worked *because* the AST2400 VIC
> was unfaithful.

### End-to-end G3 VIC bring-up (the real fix — tracked as a task)
1. Kernel: add `irq-aspeed-g3-vic` (the compact-VIC irqchip from the culvert HW
   work) that programs sensitivity/both-edge/event at 0x24/0x28/0x2C per the DTS.
2. DTS: the kgpe-d16 interrupt-controller node → `compatible = "aspeed,ast2050-vic"`.
3. QEMU: re-wire the SoC to `TYPE_ASPEED_2050_VIC` (one line in aspeed_ast2400.c).
4. Re-validate: fwtest 13/13 **and** C1–C4 boots green together.

Until (1)+(2) land, the machine keeps `TYPE_ASPEED_VIC` (boots stay green) and the
six G3 fwtest checks are xfail. *Deferred refinement:* also stop decoding the
AST2400 0x80+ aliases (G3 never uses them).

## 6. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ 13 checks |
| 2 | doc (this + `DATASHEET-VIC.md`) | ☑ |
| 3 | QEMU model (`aspeed.vic-ast2050`) | ◐ built + passes when wired; not wired to the machine pending the G3 kernel driver (§5) |
| 4 | integration test (`../../integration/test_vic.py`) | ◐ 7 pass, 6 xfail until end-to-end |

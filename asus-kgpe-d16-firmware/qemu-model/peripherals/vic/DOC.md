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

> **Hardware-confirmed (JTAG, 2026-07-11).** Read on the real AST2050 over JTAG:
> `0x1e6c0024/28/2c` all read **0** at reset, and writes to them **stick** (fully
> RW). `enable(0x10)` is write-1-to-set (clear via `0x14`); `status(0x00)` is
> read-only. All match the G3 model exactly. Full capture:
> [`../../results/vic-hardware-crosscheck.md`](../../results/vic-hardware-crosscheck.md).

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
| 3 | QEMU model (`aspeed.vic-ast2050`) | ◐ built + drives our kernel; NOT wired (breaks the C4 vendor firmware) |
| 4 | integration test (`../../integration/test_vic.py`) | ◐ 7 pass, 6 xfail (G3 VIC blocked by the C4 oracle) |

## 7b. Real-silicon cross-check reframes the C4 block (2026-07-11)

JTAG reads of the real AST2050 (see [`../../results/vic-hardware-crosscheck.md`](../../results/vic-hardware-crosscheck.md))
**confirm the G3 register model is faithful and the AST2400 model is not**: on
silicon, `0x24/0x28/0x2c` reset to 0 and are fully writable.

Tracing the C4 vendor firmware then corrected the *whole* earlier story:
- The vendor kernel **does** program the trigger config — it writes `sense=0xfff8ffff
  / dual=0x70000 / event=0xfff8ffff` (the AST2400-style "all level except timers"),
  so the steady-state config is identical on both VIC models.
- The **`div0` in `aess_write_spi_nor_flash` is the unmodelled legacy SMC** (flash ID
  reads 0), **not** the VIC — it fires on the AST2400 VIC too, non-fatal.
- With the G3 VIC wired (+ a combinational-level fix), C4 boots *past* the div0 to
  BusyBox, then its **main thread blocks after line 151 and the watchdog resets it
  at ~16 s**. Root cause **NOT yet pinned** — investigation ruled out the div0
  (SMC), the combinational fix (disabling it changed nothing), `0x14`/`0x38` read
  semantics (JTAG-confirmed 0), and the irqmap (every vendor-used device maps to
  Table-36 lines ≤31 on both models). The two VIC types present identical
  vendor-visible state yet diverge.

**Resolution for now:** the register model is hardware-confirmed faithful; wiring
the G3 VIC hangs C4 for a subtle, still-unidentified reason (needs a trace-diff of
AST2400-vs-G3 VIC events or gdb into the 2.6.23 vendor kernel). Keep the AST2400
VIC (all legacy boots green; C4 PASS). See the ruled-out table in
[`../../results/vic-hardware-crosscheck.md`](../../results/vic-hardware-crosscheck.md) §5.
§7 below is the pre-hardware state, superseded.

## 7. End-to-end bring-up: driver ready, but BLOCKED by the C4 oracle (2026-07-10)

The faithful G3 VIC is now wired to the machine and boots Linux:
- **QEMU:** the AST2050 SoC uses `TYPE_ASPEED_2050_VIC` (trigger config RW, reset 0;
  edge latching already correct). `hw/arm/aspeed_ast2400.c`, gated on silicon_rev.
- **Kernel:** a dedicated `irq-aspeed-g3-vic` irqchip driver (single 32-bit bank,
  4-byte register spacing at 0x1e6c0000) that **programs** SENSE=0x903897fe /
  DUAL=0x07c00000 / EVENT=0x983f97fe at init (the AST2400 hardwires these; the G3
  resets them to 0). `asus-kgpe-d16-firmware/qemu-firmware/kernel/drivers/`.
- **DTS:** the `&vic` node → `compatible = "aspeed,ast2050-vic"`, `reg = <0x1e6c0000 0x40>`.
- **Result:** C2, C2-full, C5 (our modern kernel + G3 driver) all boot to a shell —
  the timer IRQ works. **BUT C4 (proprietary C410X firmware) breaks**: the vendor
  kernel oops's (div0 in aess_write_spi_nor_flash during ftgmac100_open) and reboots
  (confirmed locally + CI run 29099450053). C4 is an UNPATCHABLE legacy-boot oracle,
  so per qemu-must-model-real-hardware the machine KEEPS the AST2400 VIC and the 6
  G3 checks stay xfail. The G3 VIC model + irq-aspeed-g3-vic driver + DTS snippet
  remain in-tree, ready to re-wire once validated against the KGPE-D16's own
  firmware (Raptor/C3). To re-enable: TYPE_ASPEED_2050_VIC in aspeed_ast2400.c +
  the `&vic` DTS override + the build-kernel.sh driver cp (all commented in place).

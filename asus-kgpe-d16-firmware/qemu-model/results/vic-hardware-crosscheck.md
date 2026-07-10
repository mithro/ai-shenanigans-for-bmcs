# VIC faithfulness — real-silicon cross-check over JTAG (2026-07-11)

The QEMU G3 VIC model (`TYPE_ASPEED_2050_VIC` in `aspeed_vic.c`) was validated
against the **real ASUS KGPE-D16 AST2050 BMC** over JTAG (RPi4 + OpenOCD
`0.12.0+dev`, IDCODE `0x07926f0f`, per [`../../JTAG-USAGE-GUIDE.md`](../../JTAG-USAGE-GUIDE.md)).
Access path: `ssh rpi4 → openocd -f rpi4-jtag.cfg -f kgpe-d16-bmc.cfg`, halt, `mdw`/`mww`.
The stock BMC firmware on this board is dead (never runs meaningfully), so the VIC
holds its **hardware reset values** — exactly what the model's reset path claims.

VIC base **0x1E6C0000**. Sanity anchor: `SCU7C` (0x1e6e207c) read `0x00000202`
over JTAG — matches the P2A/culvert path and the datasheet silicon-rev, proving
the AHB read path is valid.

## 1. Reset values — sense/dual/event reset to 0 (CONFIRMED)

`mdw` of the whole region `0x1e6c0000..0x1e6c00ff`, both as-found and after
`reset halt`, read **all zeros**:

```
### RESET-HALT: VIC region 0x1e6c0000 x64 words ###
0x1e6c0000: 00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
0x1e6c0020: 00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
... (entire 0x1e6c0000..0xff = 0) ...
### RESET-HALT: VIC trigger-config words (0x24/0x28/0x2c) ###
0x1e6c0024: 00000000 00000000 00000000
```

→ **`sensitivity(0x24)=0`, `both-edge(0x28)=0`, `event(0x2c)=0` at reset.**
The G3 model's `aspeed_vic_reset()` (`s->sense=s->dual_edge=s->event=0` when
`ast2050`) is **faithful**. The stock `aspeed_vic.c` AST2400 path resets these to
`0x1F07FFF8FFFF / 0xF800070000 / 0x5F07FFF8FFFF` (low words `0xfff8ffff /
0x00070000 / 0xfff8ffff`) — **unfaithful** for the AST2050.

## 2. Writability — sense/dual/event are fully RW (CONFIRMED)

Wrote the firmware trigger words, read them back, then restored:

```
### originals (expect 0 0 0) ###
0x1e6c0024: 00000000 00000000 00000000
### wrote 0x903897fe / 0x07c00000 / 0x983f97fe ; readback ###
0x1e6c0024: 903897fe 07c00000 983f97fe        <- writes STICK => fully writable
```

→ **`0x24/0x28/0x2c` are fully writable on real AST2050.** The G3 model (stores
the written word, re-evaluates) is faithful. The AST2400 path treats `0x24/0x28`
as **read-only** and `0x2c` as only-top-4-bits-writable — **unfaithful** for G3.

## 3. Control-register behaviour (CONFIRMED as modelled)

| Reg | Test | Real silicon | Model (`aspeed_vic.c`) | Verdict |
|---|---|---|---|---|
| `enable(0x10)` | write `0xffff` | reads `0xffff` (set) | `s->enable \|= data` (write-1-set) | ✓ |
| `enable(0x10)` | then write `0x0` | **stays `0xffff`** (not cleared) | write-0 is a no-op (OR) | ✓ |
| `enable-clear(0x14)` | write `0xffffffff` | `enable` → `0` | `s->enable &= ~data` | ✓ |
| `status(0x00)` | write `0xffffffff` | **stays** (read-only) | logged read-only | ✓ |

`enable(0x10)` is **write-1-to-set** (a companion `enable-clear(0x14)` clears) —
writing `0` does not clear, exactly as the model's `|=` implements. Hardware was
restored to the as-found all-zero state via `0x14` after the test.

## 4. Consequence for the C4 oracle

This is the crux the earlier revert hinged on. My G3 VIC model matches silicon on
**every** measured point (reset 0, fully RW, write-1-set enable, RO status). The
AST2400 VIC model does **not**. Therefore the previous conclusion — "wiring the G3
VIC breaks the C4 vendor firmware, so keep the AST2400 VIC" — was **treating a
false green as the oracle**: the C4 vendor boot only survived because QEMU's
AST2400 VIC hands the firmware non-zero `sensitivity`/`event` reset values that
the *real* AST2050 does not have (it resets them to 0, and something in the real
boot chain must program them).

The faithful fix is therefore **not** to keep the unfaithful AST2400 VIC. It is to
(a) keep the faithful G3 VIC model, and (b) make the C4 boot harness faithful —
i.e. ensure the vendor VIC-init that runs on real hardware also runs under QEMU
(next: inspect the C4 boot harness to see whether it skips the stage that
programs `0x24/0x28/0x2c`). Tracked under the HW-cross-reference task.

## 5. Why C4 crashed on the G3 VIC — vendor-firmware trace (QEMU, 2026-07-11)

Booted the C4 vendor firmware on the **current AST2400-VIC** model with
`-trace aspeed_vic_write`/`aspeed_vic_read` to see exactly how the vendor C410X
kernel drives the VIC. Over 60 s it:

- **writes the trigger config** — `0x24 sense = 0xfff8ffff` (×10), `0x28 dual =
  0x00070000` (×1), `0x2c event = 0xfff8ffff` (×11). These are the **AST2400
  hardwired values** ("all level except timers 16–18"), *not* the precise AST2050
  Table-36 words (`0x903897fe/0x07c00000/0x983f97fe`). So the vendor kernel *does*
  program the VIC — it just programs the coarse AST2400-style config.
- **hammers the ack path** — reads `0x14` (enable-clear) 28 190×, reads `0x38`
  (edge-clear) 13 341×, writes `0x14` 16 483× and `0x38` 7 492× (hot IRQ handler).

**Consequence.** Because the vendor writes the same values the AST2400 hardwires,
the **steady-state** `sense/dual/event` are identical on both models — so the C4
crash on the faithful G3 VIC is **not** a steady-state trigger-config difference.
The only difference is the **reset transient**: on the G3 model `sense` resets to
`0` (edge) until the vendor programs it, whereas the AST2400 model has `sense`
non-zero (level) from t=0. QEMU's `aspeed_vic_set_irq` only updates `s->raw` on
*line transitions*; it does **not** re-evaluate `raw` when `sense`/`event` change.
So a level-high source asserted-and-static across the `sense: 0→level` write is
never latched into `raw` → its IRQ is lost → the vendor's ftgmac100/SPI-NOR path
waits on that IRQ, times out with a 0 geometry, and divides by zero (`__div0` in
`aess_write_spi_nor_flash` during `ftgmac100_open`).

**Fix applied + tested — and it exposed the *real* blocker.** Made level
sensitivity **combinational** in the G3 model (on a write to `sense(0x24)`/
`event(0x2c)`, re-derive `raw` for level sources from `s->level`) and wired
`TYPE_ASPEED_2050_VIC`. Result: C4 now boots **past** the div0 and reaches BusyBox
`rcS` (further than before), but then **hangs and the watchdog resets it at ~16 s**
(the vendor installs the WDT at 10 s, `nowayout=1`). Root cause, found by tracing
`aspeed_vic_set_irq`: **the div0 is a red herring** — it comes from the *unmodelled
legacy SMC/SPI-NOR* (`SPI Flash ID: 0x0 … doesn't support`) and fires on the
AST2400 VIC too (non-fatal). The G3-specific hang is **IRQ routing**: this SoC uses
the AST2400 irqmap, which wires `UART2-4 → lines 32-34` and `TIMER4-8 → 35-39` —
**above** the G3's single 32-bit bank, so those raise `raw` bits the guest can
never read. On the faithful single-bank G3 VIC the vendor firmware then stalls and
the WDT reboots it.

**So the model is right; the wiring is incomplete.** Completing the G3 VIC needs
(a) its **own Table-36 irqmap** (device→line per §10, e.g. UART1/2=9/10, timers
16/17/18) with matching **DTS interrupt numbers** for our kernel, and (b) the
**legacy SMC** model (to kill the div0 / let the vendor flash probe succeed).
Until both land, the machine keeps the AST2400 VIC so every legacy boot stays green
(C4 re-verified PASS after reverting the wiring). The G3 VIC register model +
combinational-level fix remain in-tree, hardware-confirmed and ready. This
supersedes the earlier "G3 VIC breaks C4 via div0" conclusion — the div0 was never
the VIC.

## Provenance

- Rig: bridge Pi `rpi4-asus-aspeed2050-dev`, AST2050 over JTAG, 2026-07-11.
- All fenced blocks are verbatim OpenOCD `-c "mdw …/mww …"` output.
- §5 trace blocks are verbatim `-trace aspeed_vic_write` histograms from the C4
  vendor-firmware boot on the AST2400-VIC model.
- Board left in its as-found state (VIC region all-zero; enable cleared via 0x14).

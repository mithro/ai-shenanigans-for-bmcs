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

## Provenance

- Rig: bridge Pi `rpi4-asus-aspeed2050-dev`, AST2050 over JTAG, 2026-07-11.
- All fenced blocks are verbatim OpenOCD `-c "mdw …/mww …"` output.
- Board left in its as-found state (VIC region all-zero; enable cleared via 0x14).

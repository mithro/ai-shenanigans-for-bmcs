# SoC registers — real-silicon cross-check over JTAG (2026-07-11)

Read on the real ASUS KGPE-D16 AST2050 BMC over JTAG (RPi4 + OpenOCD, IDCODE
`0x07926f0f`), halted, `mdw`. The stock firmware is dead, so most blocks hold
reset / early-boot values. `SCU7C = 0x00000202` anchors the AHB read path.
Companion to [`vic-hardware-crosscheck.md`](vic-hardware-crosscheck.md).

> These are **as-found** (halt) reads, not `reset halt`. Identity/strap registers
> are silicon constants (authoritative); clock/PLL/reset-control registers reflect
> the running state after reset de-assertion, so they cross-check the *general*
> value but a strict reset-value check wants a `reset halt` capture (flagged below).

## 1. SCU `0x1E6E2000` — verbatim

```
0x1e6e2000: 00000000 000ffe5c e3f00070 000c3e8b 00000000 00003eff 00000000 0000001b
0x1e6e2020: 00004291 00004291 01280028 00000000 20001a03 20001a03 03000000 00000001
0x1e6e2040: 00000000 00000000 00000000 00000000 3d0700a8 077f01ff 00000000 00310140
0x1e6e2060: 00000000 00000000 00000000 3b000000 00819582 40048000 00000000 00000202
0x1e6e2080: 00000000 01009040 ...
```

### Cross-check vs QEMU `ast2400_a0_resets` (hw/misc/aspeed_scu.c)

| Off | Register | Real silicon | QEMU reset | Verdict |
|---|---|---|---|---|
| 0x30 | PCI_CTRL1 | `0x20001a03` | `0x20001A03` | ✅ exact |
| 0x34 | PCI_CTRL2 | `0x20001a03` | `0x20001A03` | ✅ exact |
| 0x3c | SYS_RST_STATUS | `0x00000001` | `0x00000001` | ✅ exact |
| 0x7c | silicon rev | `0x00000202` | `0x00000202` (wired) | ✅ exact |
| 0x70 | HW strap1 | `0x00819582` | property (machine) | ℹ️ silicon strap value |
| 0x04 | SYS_RST_CTRL | `0x000ffe5c` | `0xFFCFFEDC` | ⚠️ running (reset bits deasserted) |
| 0x08 | CLK_SEL | `0xe3f00070` | `0xF3F40000` | ⚠️ running (clocks configured) |
| 0x0c | CLK_STOP_CTRL | `0x000c3e8b` | `0x19FC3E8B` | ⚠️ running (clocks enabled) |
| **0x20** | **M-PLL param** | **`0x00004291`** | **`0x00030291`** | ❌ **differs (G3 PLL)** |
| **0x24** | **H-PLL param** | **`0x00004291`** | **`0x00000291`** | ❌ **differs (G3 PLL)** |

**Key finding — PLL params.** On real AST2050 silicon both M-PLL (0x20) and H-PLL
(0x24) read **`0x00004291`**; QEMU's AST2400 reset table has `0x00030291` /
`0x00000291`. The low 12 bits (`0x291`) match but bit 14 (`0x4000`) is set on the
G3 and clear (H-PLL) / different (M-PLL) in the AST2400 table. This is the AST2050
PLL-layout data that **task #55 (PLL post-divider + G3 strap)** needs — the AST2400
reset values are not faithful to the G3 PLL. (These are running values; capture
with `reset halt` before treating `0x4291` as the exact reset constant, but the
`0x4000` divergence is structural, not a running-state artefact.)

## 2. SDMC / DRAM controller `0x1E6E0000` — verbatim

```
0x1e6e0000: 00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000
0x1e6e0020: 00000000 00000000 00000000 00000632 00000040 00000000 00000000 00000000
```

`MCR04` (DRAM config, 0x04) reads **0** — the DRAM is **untrained** (dead firmware
never programmed the SDMC), consistent with the JTAG guide's DDR2 note and the
64 MB story. Only `0x2c = 0x00000632` and `0x30 = 0x00000040` are non-zero
(SDMC defaults). A trained-DRAM capture (after `ddr2-init.tcl`) would show
`MCR04 = 0x00000585` (from the SCU70 strap) — deferred; this confirms the
untrained baseline.

## 3. Timer `0x1E782000` — all zero

The three-channel timer reads all-0 (not running) — matches the QEMU timer model's
zero reset. ✅

## 4. WDT `0x1E785000` — verbatim

```
0x1e785000: 03ef1480 03ef1480 00000000 00000000 00000000 00000000 000000ff 00000000
0x1e785020: 03ef1480 03ef1480 00000000 00000000 00000000 00000000 000000ff 00000000
```

Two watchdogs (0x1E785000 + 0x1E785020). Both show reload/counter (0x00/0x04) =
**`0x03ef1480`** (= 66,000,000 ≈ the 1 s @ ~66 MHz PCLK reload) and `0x18 =
0x000000ff`. Cross-check the QEMU aspeed_wdt reset value against `0x03ef1480` when
modelling the G3 WDT reload.

## Provenance

- Rig: bridge Pi `rpi4-asus-aspeed2050-dev`, AST2050 over JTAG, 2026-07-11.
- Fenced blocks are verbatim OpenOCD `mdw` output; board left as-found (read-only).

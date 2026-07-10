# AST2050 / AST1100 Video Engine — Datasheet Extract

Source: **ASPEED AST2050/AST1100 A3 Datasheet, V1.05** (May 25, 2010).
File: `datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf`
(Copies also under `asus-kgpe-d16-firmware/datasheets/` and
`dell-c410x-firmware/datasheets/`. Printed page = physical PDF page.)

Purpose: reference for a **faithful QEMU model** of the AST2050 Video Engine —
the **KVM screen-capture** path. This is the hardware OpenBMC's `aspeed-video`
V4L2 driver drives to grab and JPEG-compress the host (or BMC-VGA) display for
remote KVM. This is a **large block (~256 registers spanning offsets 0x000–0x4FC)**;
below prioritises the control/status/buffer registers a driver or QEMU model
actually needs, each with a datasheet page cite. Where the datasheet is silent
this is stated; no bit fields are invented.

**Base address of Video Engine = `0x1E700000`** (§20.1, p.232; §9 map p.97,
"Video Engine 1E70:0000–1E71:FFFF, 128K"). Register = base + offset (`VRxxx`).
Interrupt: **Video Engine = INT#7**, "Sensitive high level trigger" (§10, p.99).

> **AST2050-only block.** The ToC lists §1.3.6 as *"Video Compression Engine
> (AST2050 only)"* (p.19) — the sibling **AST1100 does not include the video
> compression engine**. A model tied to the `ast1100` SKU must gate it off.

---

## 0. Where it lives in the datasheet

| What | Section | Page |
|---|---|---|
| Feature summary (§1.3.6, AST2050 only) | ToC | p.19 |
| Overview + buffers + base | §20.1 | **p.232** |
| Features (JPEG+VQ, YUV420/444, RC4, mode detect) | §20.2 | p.232–233 |
| **Registers, base 0x1E700000** | §20.3 | **p.234–255** |
| VR000 key, VR004 sequence-control | | p.234–236 |
| VR008 video-control | | p.236–238 |
| VR00C/VR010 timing, VR014 scaling, VR018–024 filter | | p.238–240 |
| VR02C BCD, VR030/VR034 windows | | p.241 |
| VR038–VR058 **buffer base addresses** | | p.242–244 |
| VR060 **compression control** | | p.244–246 |
| VR070–VR07C read-back counters | | p.246–247 |
| VR090–VR098 **mode-detection read-back** | | p.247–248 |
| VR300 ctrl, **VR304/VR308 interrupt enable/status** | | p.249–250 |
| VR30C mode params, VR310/VR314 mem-restriction | | p.251 |
| VR320/VR324 CRC, VR328 truncation | | p.252–253 |
| VR340–VR35C VGA-scratch remap read-back | | p.253–255 |
| VR400–VR4FC RC4 key SRAM | | p.255 |

**Overview (p.232):** JPEG + Vector-Quantization (VQ) mixed compression. Requires
five DRAM buffers: **Video Source Buffer #1**, **Video Source Buffer #2**, **CRC
Buffer** (optional, quick scene-change), **Block-Change-Detection (BCD) Flag
Buffer**, **Compressed Video Stream Buffer**.

**Features (p.232–233):** register access over AHB, video **data** over M-Bus
(bypasses AHB); ≤266 MHz; source = **internal VGA output or external DVO**; engine
clock from CPU or memory clock, gated when idle; **YUV420** (higher ratio) /
**YUV444** (higher quality); up to 1920×1200×32bpp@60; 30 fps @1280×1024 YUV420;
CRC per-scan-line scene detection; direct VGA-frame-buffer fetch (high-res only,
Quick Cursor required); 4×2 down-scaling filter; **RC4 stream encryption** (256×8
key SRAM); mode-change watchdog interrupt; bit-resolution truncation; 12 JPEG
quality levels; VQ mode; **auto stream mode + single-frame trigger mode**.

---

## 1. Core control / status registers (the ones a model must implement)

### VR000 — Protection Key Register (0x000, p.234)
[31:0] RW. Password **`0x1A03_8AA8`** unlocks all VR registers; any other value
locks (registers stay readable when locked). Read-back = `0x0000_0001` when
unlocked, `0x0000_0000` when locked. Reset by POR / watchdog / SCU-sw-reset; S/W
must wait ≥1 µs after reset before unlocking.

### VR004 — Video Engine Sequence Control Register (0x004, p.234–236)
The master trigger/status register.
| bit | acc | meaning |
|--|--|--|
| 18 | R | **Video compression engine status** (0 busy / 1 idle) |
| 16 | R | **Video capture engine status** (0 busy / 1 idle) |
| 11:10 | RW | Video data format for compression (00 YUV444, 01 YUV420) |
| 7 | RW | Enable watchdog for input-resolution mode change |
| 6 | RW | Trigger full-frame compression insert (stream mode) |
| 5 | RW | **Enable automatic video compression** (0 single / 1 multi-frame) |
| 4 | RW | **Enable / Trigger video compression** (0→1 triggers) |
| 3 | RW | Enable capturing multiple frames (needs double buffer) |
| 2 | RW | Force compression engine idle |
| 1 | RW | **Enable / Trigger video capture** (0→1 triggers) |
| 0 | RW | Trigger video mode-detection hardware (0→1) |

Auto/trigger matrix (p.235, VR004[3],[5]): `0,0`=single-frame + software trigger +
frame buffer; `0,1`=single-frame + hardware auto-trigger; `1,1`=multiple-frame +
hardware auto-trigger + **stream buffer mode**. S/W must confirm the engine is
idle (VR004[18]/[16]=1) before triggering, and insert ≥1 read cycle / 1 µs between
consecutive triggers.

### VR008 — Video Control Register (0x008, p.236–238) — source select
| bit | meaning |
|--|--|
| 23:16 | Max frame-rate control (max fps = VR008[23:16]·source/60) |
| 13 | Digital-video-input clock mode (single/dual edge) |
| 12 | Video input port width (0 = 24-bit, 1 = 18-bit) |
| 11:10 | Clock delay control for digital video input |
| 8 | (VR008[5]=0) Disable HW-cursor overlay for internal VGA; (VR008[5]=1) auto mode for direct fetch |
| 7:6 | Data format for capture (00 CCIR601-2 YUV, 01 full-range YUV, 10 RGB) |
| 5 | **Fetch video data directly from VGA frame buffer (internal VGA only)** |
| 4 | internal/external DE signal (VR008[5]=0) / VGA bpp mode (VR008[5]=1) |
| 3 | external-source is digital/ADC (VR008[5]=0) / VGA 16bpp color (VR008[5]=1) |
| 2 | **Video source select (0 = integrated VGA controller, 1 = external source)** |
| 1 | Video source VSYNC polarity |
| 0 | Video source HSYNC polarity |

**For BMC KVM**: `VR008[2]=0` selects the SoC's own VGA CRT output as the source,
and `VR008[5]=1` enables low-bandwidth **direct fetch from the VGA display frame
buffer** (requires Quick Cursor; cursor overlay is composited client-side). This
is the standard KVM screen-capture configuration.

### VR300 — Video Control Register (0x300, p.249)
bit15 RC4 non-auto reset (rec. 1), bit14 RC4 save mode (rec. 1), bit9 RC4 test,
bit8 RC4 initial reset (set when idle to reset RC4 state), [5:4] enable vertical
down-scaling line buffer (01 = enable), bit2 delay internal VSYNC by 12 HSYNC
(auto-mode anti-flicker), bit1 stream-buffer controller save mode (rec. 1).

---

## 2. Interrupt (the KVM completion path)

### VR304 — Video Interrupt Control Register / enables (0x304, p.249–250)
bit5 enable **frame-complete** int; bit4 **mode-detection-ready** int; bit3
**compression-complete** int; bit2 **compression-packet-ready** int; bit1
**frame-capture-complete** int; bit0 **mode-detection watchdog out-of-lock** int.

### VR308 — Video Interrupt Control Register / status (0x308, p.250, W1C)
Same bit order (5..0): frame-complete, mode-detection-ready, compression-complete,
compression-packet-ready, capture-complete, watchdog-out-of-lock status. Each
"Clear this register by writing 1."

All feed **VIC INT#7** (§10, p.99). A driver waits on capture-complete (bit1) /
compression-complete (bit3) / packet-ready (bit2) to drain the stream buffer.

---

## 3. DRAM buffer base-address registers (the five buffers)

| Off | Reg | Field | Buffer (p.) |
|----|-----|-------|------|
| 0x040 | VR040 | [27:3] | **CRC Buffer** base (optional scene-change) (p.242) |
| 0x044 | VR044 | [27:8] | **Video Source Buffer #1** base (p.242) |
| 0x048 | VR048 | [13:8] | Scan-line offset of source buffer (line stride) (p.242–243) |
| 0x04C | VR04C | [27:8] | **Video Source Buffer #2** base (double-buffer) (p.243) |
| 0x050 | VR050 | [27:3] | **BCD Flag Buffer** base (4 bits/block) (p.243) |
| 0x054 | VR054 | [27:7] | **Compressed Video Stream Buffer** base (p.243) |
| 0x058 | VR058 | [4:3]/[2:0] | Stream buffer packet number (4/8/16/32) / packet size (1KB…128KB) (p.243–244) |

Stream-buffer read/write bookkeeping: `VR038` process offset [21:7] (p.242),
`VR03C` read offset [21:7] (p.242), `VR05C` write-offset read-back [21:7] (p.244),
`VR078` frame-end offset read-back [21:3] (p.247, last-frame end = VR054+VR078).

Memory-write guard: `VR310` (0x310) restriction-area start [27:16] (init 0),
`VR314` (0x314) restriction-area end [27:16] (init `0x0FFF_0000`) — video writes
outside the window are **discarded** (p.251).

---

## 4. Compression & scene-detection controls

### VR060 — Video Compression Control Register (0x060, p.244–246)
[21:20] JPEG Huffman table select (00 Y+UV rec.); [15:11] DCT **luminance**
quantization table select (bit15 = luma/chroma table bank, [14:11] one of 12
tables); [10:6] DCT **chrominance** quantization table select; **bit5 Enable RC4
encryption**; bit1 Enable 4-color VQ (0 = 2-color); **bit0 JPEG-only encoding**
(0 = JPEG/VQ mixed mode, 1 = pure JPEG). 12 selectable quality levels come from
the quant-table selects.

### VR02C — Video BCD Control Register (0x02C, p.241)
[23:16] BCD tolerance value; bit1 delay block-change update by one frame; **bit0
Enable Block-Change-Detection** — when on, only changed blocks are compressed
(big bandwidth saving). Uses the BCD Flag Buffer (VR050).

### VR320 / VR324 — CRC scene-change (0x320/0x324, p.252)
`VR320`: primary CRC polynomial (upper16 [31:16], lower8 [15:8]) for source buffer
#1; [7:2] max-frame-skip; **bit0 scene-change scheme select** (0 pixel-by-pixel,
1 CRC — CRC recommended, lower bandwidth). `VR324`: secondary CRC polynomial for
source buffer #2. (24-bit CRC.)

### Windows / scaling / truncation
`VR030` (0x030) capture window: H total pixels [27:16], V total scan-lines [10:0]
(p.241). `VR034` (0x034) compression window (same layout, p.241). `VR014` (0x014)
down-scaling factor: vertical [31:16], horizontal [15:0] (≥4096) (p.239).
`VR018–VR024` (0x018–0x024) 2×4 scaling-filter parameters F00–F33, S2.5 2's-comp
(p.240). `VR00C`/`VR010` (0x00C/0x010) timing-generator active-pixel/scan-line
setup (VR008[5]=0) or direct-frame-buffer base/line-offset (VR008[5]=1) (p.238–239).
`VR328` (0x328) R/G/B channel bit-reduction (truncation) (p.252–253).

---

## 5. Mode-detection & read-back (auto-resize / diagnostics)

- `VR090` (0x090, p.247): source left/right edge, no-display-clock/active/HSYNC/
  VSYNC-detected flags.
- `VR094` (0x094, p.247–248): source top/bottom edge.
- `VR098` (0x098, p.248): **Mode-detection status** — HSYNC/VSYNC ready [31/30],
  polarity [29/28], vertical scan-lines [27:16], out-of-sync [15], V/H stable
  [14/13], auto source type (DVI vs ADC) [12], horizontal period [11:0].
- `VR30C` (0x30C, p.251): mode-detection tolerances/minimums/edge threshold.
- `VR070` (0x070, p.246): total compressed-stream size [19:0] (double-word units).
- `VR074` (0x074, p.246): compressed block counter [29:16] / processed block
  counter [13:0] (YUV420 only).
- `VR07C` (0x07C, p.247): compressed-frame counter [31:0].
- `VR340–VR35C` (0x340–0x35C, p.253–255): **VGA-scratch remap read-back** — the
  engine mirrors the internal VGA controller's cursor position/type/enable and CRT
  scratch registers CR80–CR9E (so KVM can read display mode/cursor state that VGA
  BIOS recorded, avoiding external ADC probing).
- `VR400–VR4FC` (0x400–0x4FC, p.255): **RC4 key SRAM** — 256 bytes (64 double
  words) for the RC4 encryption keys; initialise before enabling RC4 (VR060[5]).

---

## 6. Typical KVM capture flow (synthesised from the register descriptions)

1. Wait ≥1 µs after reset, then unlock `VR000` = `0x1A03_8AA8` (p.234).
2. Select source: `VR008[2]=0` (internal VGA CRT) and, for low-bandwidth KVM,
   `VR008[5]=1` (direct VGA-frame-buffer fetch) (p.236–237).
3. Allocate DRAM and program buffer bases: src#1 `VR044`, src#2 `VR04C` (double
   buffer), BCD flag `VR050`, CRC `VR040`, compressed stream `VR054` + size
   `VR058` (p.242–244).
4. Set format/quality/scaling: `VR004[11:10]` YUV420/444; `VR060` JPEG/VQ, quant
   tables, RC4; `VR014`/`VR018–024` scaling; `VR030`/`VR034` windows;
   `VR02C`/`VR320` scene-detection (p.240–246).
5. Trigger mode detection `VR004[0]` 0→1; read `VR098`/`VR090`/`VR094` (p.235,248).
6. Enable interrupts `VR304`; then either single-shot (`VR004[1]` capture then
   `VR004[4]` compress) or auto-stream (`VR004[3],[5]=1,1`) (p.235,249).
7. On INT#7, read `VR308` status (capture/compression complete), read stream size
   `VR070` and frame-end offset `VR078`, drain the compressed stream from
   `VR054` base (p.246–247,250).

---

## 7. AST2050 vs AST2400 / 2500 / 2600 — differences a faithful model must capture

1. **Present only on AST2050** (not AST1100), §1.3.6 (p.19). Model must gate by SKU.
2. **RC4 stream-encryption engine** (VR060[5], VR300, VR400–4FC key SRAM) is an
   AST2050-era feature; later parts change/drop it. Model the key SRAM + enable.
3. **Register file / semantics differ from G4/G5/G6.** Mainline `aspeed-video`
   (`drivers/media/platform/aspeed/aspeed-video.c`) targets AST2400/2500/2600
   offsets and adds JPEG-partial / dual-JPEG / capture-format features not in this
   VR map. AST2050 has the VR000 key, VR004 trigger/status, VR008 source select,
   VR060 compression control, VR304/VR308 interrupts, and the VR040–058 buffers as
   its minimum surface — those are what the model must reproduce first.
4. Data path uses the **M-Bus** (direct DRAM), not AHB, for pixel data (p.232) —
   only registers are on AHB. A model can ignore M-Bus timing but must accept the
   buffer-base writes and produce plausible read-back (VR070/074/078/098).

## 8. Does mainline QEMU model it?

**No.** There is no `aspeed_video` device in QEMU; the 0x1E700000 region is
unmapped for this SoC, so reads return 0 and writes are dropped. This matches the
prior modelling notes (`qemu-firmware/AST2050-PERIPHERAL-MODELING.md` §1: ~110
accesses to `aspeed.video`=0x1E700000, "gap: reads 0, writes dropped"). A faithful
KVM path therefore needs a **new** model: minimally VR000 key gating, VR004
trigger→status (set idle bits, latch a synthetic "capture/compress complete"),
VR304/VR308 interrupt on INT#7, and honouring the VR040–058 buffer bases (so the
driver sees a JPEG frame appear in the compressed-stream buffer).

# Video engine (KVM capture) — AST2050 faithfulness doc

**Base 0x1E700000, VIC INT#7.** Captures the host VGA/CRT framebuffer for KVM (OpenBMC
`aspeed-video`). AST2050-specific block (the AST1100 variant lacks it). Full detail:
**[`DATASHEET-VIDEO.md`](DATASHEET-VIDEO.md)**.

## 1. Key registers

| Off | Register | Notes |
|---|---|---|
| 0x000 | protection key (VR000) | unlock = write `0x1A038AA8` |
| 0x004 | capture / compress trigger + status | |
| 0x008 | source select | VGA vs external |
| 0x040–0x058 | five DRAM capture buffer bases | |
| 0x060 | JPEG/VQ compression | (has an RC4 engine) |
| 0x304 / 0x308 | interrupt enable / status | |

## 2. QEMU faithfulness — UNMODELLED

`peripherals/video/fwtest.c`: VR000/VR008 read **0**, and writing the unlock key does
not take (VR000 not readable-back as unlocked). The video engine is **not modelled** in
mainline QEMU (nor on this machine — the "tolerate unmodelled MMIO → 0" flag). **OpenBMC
KVM screen capture cannot be verified** until a model exists. It reads the VGA
framebuffer that the machine already reserves (`vga_memory` no-map region).

## 3. Faithful-model plan (large, oracle-safe)

A new `aspeed.video-ast2050` device: protection key, capture control/status, source
select, the five buffer-base registers, and an interrupt — enough for the OpenBMC
`aspeed-video` driver to bind and capture a frame from the reserved VGA memory. New
device at an unmodelled address (low oracle-risk; CI-validate).

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ (documents the unmodelled block) |
| 2 | doc (this + `DATASHEET-VIDEO.md`) | ☑ |
| 3 | QEMU model | ☐ new `aspeed.video-ast2050` (§3) |
| 4 | integration test (`../../integration/test_video.py`) | ◐ checks xfail until §3 |

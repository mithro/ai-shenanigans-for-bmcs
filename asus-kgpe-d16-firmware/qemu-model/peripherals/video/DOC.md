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

## 2. QEMU faithfulness — MODELLED (`aspeed.video-ast2050`)

`peripherals/video/fwtest.c`: VR000 is a **protection-key lock latch** — write the
unlock key `0x1A038AA8` → reads back **1** (unlocked); the remaining registers are RW
while unlocked. Implemented as a new **`aspeed.video-ast2050`** device
(`hw/misc/aspeed_video_ast2050.c`), replacing the AST2400 unimplemented stub for the G3
(keyed on silicon-rev). **The OpenBMC `aspeed-video` driver can now bind and program the
capture engine**; it reads the VGA framebuffer the machine already reserves (`vga_memory`
no-map region).

*Refinement (deferred):* the actual frame capture + compression (VR004 trigger → read
the reserved VGA memory → produce a JPEG/VQ stream) + the INT7 completion IRQ. The
register interface is faithful; the capture datapath is a behavioural add-on.

## 3. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ VR000 protection-key |
| 2 | doc (this + `DATASHEET-VIDEO.md`) | ☑ |
| 3 | QEMU model | ☑ `aspeed.video-ast2050` (register interface; capture datapath deferred) |
| 4 | integration test (`../../integration/test_video.py`) | ☑ passes |

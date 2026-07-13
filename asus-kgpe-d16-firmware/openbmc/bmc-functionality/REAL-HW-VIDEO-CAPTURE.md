# Real-silicon aspeed-video capture on the AST2050 — status & the compression boundary

**Date:** 2026-07-13. **Board:** ASUS KGPE-D16, Aspeed AST2050 (G3), silicon rev
SCU7C=0x00000202. **Access:** P2A boot (culvert on the PXE host via the Pi bridge)
→ Linux over the BMC UART (ttyS4). Kernel: mainline v6.6.70 + our G3 patches,
`aspeed,ast2400-video-engine` bound to the AST2050 video engine at `0x1E700000`.

This extends [F8-KVM.md](F8-KVM.md) §5 (which was **QEMU-only**) with **real-silicon
results**: the video-capture *front-end* is proven working on the AST2050; the one
remaining gap is precisely localized to the **JPEG compression-complete** stage.

## What is PROVEN on silicon

Boot: minimal busybox initramfs (no OpenBMC → idle, memory-rich box), CMA kernel,
video DTB, `f8capture` cmdline gate. Evidence: `evidence/real-hw-video/f8capture-silicon.log`.

| Step | Result on real AST2050 | Evidence |
|---|---|---|
| aspeed-video driver binds → `/dev/video0` | ✅ | `aspeed-video 1e700000.video: irq 23`; `CAP: driver=aspeed-video card=Aspeed Video Engine` |
| JPEG-header DMA buffer allocated | ✅ | `alloc mem size(24576) at 0x42840000 for jpeg header` (from the CMA pool) |
| Engine detects a **live host VGA signal** | ✅ | `INPUT: 'Host VGA capture' status=0x0 (SIGNAL)` |
| Engine **mode-detects the real host resolution** | ✅ | `FMT: JPEG 1024x768 sizeimage=524288` — the actual host VGA mode, read off the live signal |
| **Mode-detect interrupt** (VR308 bit) fires + is handled | ✅ | mode-detect must complete for `FMT` to report 1024x768; proves INT#7→virq23 delivery works |
| `VIDIOC_REQBUFS` + `STREAMON` (contiguous DMA buffers) | ✅ | no `ENOMEM` (see the CMA fix below); streaming starts |
| **Capture/compression completes → frame dequeued** | ❌ | `poll: no frame yet` ×12 over 12 s, `f8capture exited 2` — no `VE_INTERRUPT_COMP_COMPLETE` |

So on real silicon the AST2050 video engine **captures a live 1024×768 host-VGA
signal and drives the whole path up to and including mode-detection**, with the
interrupt infrastructure proven (mode-detect's own IRQ fires). The mainline driver
then triggers capture+JPEG-compression and waits on `VE_INTERRUPT_COMP_COMPLETE`
(0x308 bit 3) — which **never fires**.

## The boundary: G3 JPEG compression-complete

The interrupt-register offsets the mainline driver uses **match the AST2050
datasheet** (`VE_INTERRUPT_CTRL=0x304`, `VE_INTERRUPT_STATUS=0x308` = datasheet
VR304/VR308), and the mode-detect IRQ demonstrably works — so this is **not** an
IRQ-routing problem. The gap is that the **G3 compression engine does not complete**
when programmed the AST2400 way:

- The driver selects JPEG mode via `AST2400_VE_SEQ_CTRL_JPEG_MODE = BIT(8)` of
  VE_SEQ_CTRL (0x004) for the `ast2400-video-engine` compatible the G3 binds to.
- The AST2050 datasheet §20.3 documents its compression control in **VR060**
  (`VE_COMP_CTRL`) with a different layout, plus RC4 stream-encryption bits
  (VR060[5]/VR300/VR400–4FC) the G4 driver knows nothing about.
- This is the exact "residual G3-vs-G4 tension" [F8-KVM.md](F8-KVM.md) §3.1 flagged
  ("dedicated G3 tuning is future work"): the driver's G4-isms are accepted as
  register writes but the G3 compressor doesn't produce a completed JFIF frame.

**Closing it = a G3-specific `aspeed-video` compression patch** (correct VR060 setup
/ JPEG-mode select / quant-table + buffer programming so the engine finishes and
raises `COMP_COMPLETE`). That needs the datasheet §20 compression detail (and ideally
Raptor's working 2.6.28 AST2050 KVM driver as an oracle) and should be developed
QEMU-first against the `aspeed.video-ast2050` model, then re-verified on silicon.

## Infrastructure solved along the way (all on real silicon)

These were prerequisites discovered and fixed to even reach the boundary above:

1. **`/dev/video0` never appeared** → the `video@1e700000` DTS node was
   `status="disabled"`. Enabled it (`aspeed-bmc-asus-kgpe-d16-realhw.dts`); driver
   now binds.
2. **`VIDIOC_REQBUFS` → ENOMEM** → vb2-dma-contig needs a contiguous 512 KB
   (order-7) buffer; the fragmented 64 MB box offers ≤128 KB (order-5) and the
   kernel had **no CMA and no compaction**. Added `kgpe-d16-video-cma.config`
   (CONFIG_CMA/DMA_CMA/COMPACTION) + boot `cma=<N>M`; REQBUFS + the JPEG-header
   alloc now succeed from the CMA pool.
3. **A blocking `VIDIOC_DQBUF` wedged the box** → an active video engine that never
   completes free-runs the shared DRAM/M-bus and starves the CPU (SSH banner
   timeouts, then a full crash). `f8capture` now uses a **bounded `poll()`** (12 s
   budget → prompt STREAMOFF), so a non-completing engine can never hang the box.
4. **Full OpenBMC + capture doesn't fit 64 MB** → running the capture under the full
   OpenBMC image thrashed (52 MB working set → NBD-swap-over-eth0 death spiral →
   crash). The **minimal initramfs** (busybox only) is the correct capture harness:
   idle, memory-rich, no M-bus contention — exactly how the QEMU proof
   (`f8video`) is structured. (Boot-time NBD swap + `cma=2M` were also added for the
   OpenBMC path.)

## Reproduce

```sh
# CMA kernel + video DTB + minimal f8capture initramfs, capture over serial:
uv run linux-boot.py \
  --kernel uImage-kgpe-d16-hwpass-cma --dtb kgpe-hwpass-vgafix-video.dtb \
  --initrd initramfs-f8capture.cpio.gz --cmdline-initrd <size> \
  --bootargs "console=ttyS4,115200n8 mem=64M cma=8M clk_ignore_unused f8capture rdinit=/init" \
  --watch 220
# -> F8-CAPTURE-BEGIN ... FMT: JPEG 1024x768 (SIGNAL) ... poll: no frame ... F8-CAPTURE-END
```

# Real-silicon aspeed-video capture on the AST2050 — WORKING (full pipeline)

**Date:** 2026-07-14. **Board:** ASUS KGPE-D16, Aspeed AST2050 (G3), silicon rev
SCU7C=0x00000202. **Access:** P2A boot (culvert on the PXE host via the Pi bridge)
→ Linux over the BMC UART (ttyS4). Kernel: mainline v6.6.70 + our G3 patches,
`aspeed,ast2050-video-engine` bound to the AST2050 video engine at `0x1E700000`.

This extends [F8-KVM.md](F8-KVM.md) §5 (which was **QEMU-only**) to a **fully working
real-silicon capture**: the AST2050 video engine captures a live 1024×768 frame of
the host's VGA output, JPEG-compresses it, and the mainline `aspeed-video` V4L2
driver dequeues it — a **real image was reconstructed and viewed**
(`evidence/real-hw-video/captured-frame-silicon.png`: a cyan panel over a gray body,
the host's live screen). This required an aspeed-video **G3 compression fix**
(patch `0006`, below) that was reverse-engineered from the datasheet + the AMI
"videocap" driver and **verified register-by-register on silicon**.

## TL;DR — the fix (patch 0006)

The compression engine hung because mainline programs the G3 the AST2400 way. Three
changes (behind a new `aspeed,ast2050-video-engine` compatible / `jpeg_only`):
1. **Select pure JPEG via `VE_COMP_CTRL[0]` (VR060[0]=1)**, not `VE_SEQ_CTRL[8]`
   (VR004[8] is reserved-must-be-0 on the G3; mainline poked it and never set VR060[0],
   leaving the G3 in JPEG/VQ mixed mode).
2. **Clamp the DCT quant-table selector to 0-7** — the G3 has only 8 *internal ROM*
   quant tables; mainline's 0-11 range selected a nonexistent table (live dump showed
   index 11) which **wedged the compressor** (COMP_BUSY stuck). This was THE hang.
3. Clear the G4-only HQ fields (VR060[16],[31:22]) and AUTO_COMP (VR004[5]).

Result on silicon: `COMPC060=0x00083DC1`, `COMPSZ078=0x6C80` (27776-byte frame),
`COMP_COMPLETE` fires, `/dev/video0` DQBUF returns the frame. The engine emits the
**raw ASPEED compressed stream (no JFIF header)** — a standard JPEG is reconstructed
by prepending the header the driver already builds (`jpeg_header + jpeg_dct[q] +
jpeg_quant`) with the SOF0 dimensions patched to 1024×768.

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
| **Capture/compression completes → frame dequeued** | ✅ | after patch 0006: `COMPSZ078=0x6C80`, `COMP_COMPLETE`, `DQBUF` returns a 27776-byte frame (`f8capture rc=0`) |
| **Reconstructed JPEG decodes as a real image** | ✅ | 1024×768, cyan panel + gray body — the host's live screen (`captured-frame-silicon.png`) |

## How the compression fix was found (silicon register forensics)

A `vediag` initramfs gate (busybox `devmem`) sampled the engine registers *during* a
capture. The capture engine always completed (`VR004[16]` idle, `VR308[1]`
CAPTURE_COMPLETE) but the compression engine wedged: `VR004[18]` COMP_BUSY stuck at 0,
`VR078` size 0, `VR308[3]` COMP_COMPLETE never firing. The interrupt offsets match the
datasheet and mode-detect's own IRQ works, so it was never an IRQ-routing problem —
it was the **compression programming**. The decisive clue was `VR060` during capture:

```
before fix:  COMPC060=0x04085EC1  (bit0 set OK, but DCT selector = 11)  -> COMP_BUSY stuck
after  fix:  COMPC060=0x00083DC1  (DCT selector clamped to 7)          -> COMPSZ=0x6C80, done
```

The AST2050 has only **8 internal ROM quant tables (index 0-7)**; mainline's 0-11
quality range selected table 11, a nonexistent table, wedging the compressor. See the
patch-0006 commit message and [F8-KVM.md](F8-KVM.md) §3.1 for the full datasheet/AMI-
driver derivation. Register semantics match the AMI "videocap" G3 driver
(`ya-mouse/openwrt-linux-aspeed`, `arch/arm/plat-aspeed/videocap/`).

## Standards-compliant JPEG — done in the driver (patch 0006)

The G3 engine emits the raw ASPEED compressed stream (no JFIF header — `0x040` is the
CRC buffer on the G3, so the G4's engine-prepended header mechanism is inert). The
driver now wraps it: `aspeed_video_build_jfif_header()` assembles the header the G4
would have prepended (`jpeg_header + jpeg_dct[sel] + jpeg_quant`) with the SOF0 (`FF C0`)
dimensions patched to the captured WxH (deterministic offset 175), and
`aspeed_video_wrap_jfif()` — in the threaded COMP_COMPLETE IRQ — memmoves the entropy up,
prepends the header, and appends the EOI marker. `/dev/video0` therefore returns a
directly-decodable `V4L2_PIX_FMT_JPEG` (FFD8..FFD9, correct SOF0 dims) that obmc-ikvm or
any viewer opens as-is; no offline reconstruction needed. The G3 engine writes the
entropy MSB-first, so no word-swap is required (the `as-is` variant of the real-silicon
capture decodes; `wordswap` is flat grey). The offline
`evidence/real-hw-video/reconstruct-jpeg.py` remains only as the pre-driver-fix reference.

**QEMU mirrors silicon.** The `aspeed.video-ast2050` model now emits the same headerless
entropy in pure-JPEG mode (VR060[0]) using the AST2050 ROM quant tables, and the kgpe-d16
QEMU DTS binds `aspeed,ast2050-video-engine`, so `video-capture-test.py` drives the real
G3 wrapping path end to end (all 8 colour bars pixel-verify on the wrapped frame).

**PROVEN ON REAL SILICON (2026-07-15).** Booted the wrapping kernel (`uImage-kgpe-d16-jfif`)
+ `kgpe-hwpass-vgafix-video.dtb` over P2A; `f8capture` on `/dev/video0` reported
`bytesused=28418` = **640 (JFIF header) + 27776 (raw entropy) + 2 (EOI)** — the driver
wrapped the frame in-kernel on the AST2050. The captured base64 decodes **directly** (no
reconstruction): `ff d8` SOI, `ff d9` EOI, 1024×768, real host-screen content
(`evidence/real-hw-video/silicon-direct-jpeg.png`, extracted by
`evidence/real-hw-video/decode-silicon-frame.py`).

The `bytesused=28418` value is the decisive proof that the **kernel driver** (not any
offline tool) did the wrapping: it is the payload size `VIDIOC_DQBUF` returned. An
unwrapped G3 driver returns the raw entropy size **27776**; the wrapped driver returns
**27776 + 640 + 2 = 28418**. The full live `f8capture` stdout is committed at
[`evidence/real-hw-video/silicon-f8capture-transcript.txt`](evidence/real-hw-video/silicon-f8capture-transcript.txt)
(`FRAME … bytesused=28418`, `first4: ff d8 ff e0`, `last2: ff d9`). NB: the older
`f8capture-silicon.log` in that dir is a **pre-fix (Jul 13) FAILED capture** kept only as
the historical "compression hung" record — the transcript above supersedes it.

## Remaining follow-up (not blocking capture)
- **Capturing a specific BIOS screen.** The captured frame is whatever the host is
  currently scanning out; to capture a specific POST screen, warm-reset the host
  (`kgpe-power.sh reset`) after the BMC is up so a fresh POST re-renders the AST2050
  VGA, then capture.

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

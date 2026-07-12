# Video engine (KVM capture) — AST2050 faithfulness doc

**Base 0x1E700000, VIC INT#7.** Captures the host VGA/CRT framebuffer for KVM (OpenBMC
`aspeed-video`). AST2050-specific block (the AST1100 variant lacks it). Full detail:
**[`DATASHEET-VIDEO.md`](DATASHEET-VIDEO.md)**.

## 1. Key registers

| Off | Register | Notes |
|---|---|---|
| 0x000 | protection key (VR000) | unlock = write `0x1A038AA8` |
| 0x004 | capture / compress trigger + status | [16]/[18] read 1=idle |
| 0x008 | source select | VGA vs external |
| 0x030/0x034 | capture / compression windows | H [27:16], V [10:0] |
| 0x040–0x058 | five DRAM capture buffer bases | 0x054 = compressed stream |
| 0x060 | JPEG/VQ compression | [15:11] quality select (has an RC4 engine) |
| 0x070/0x078/0x07C | stream-size / frame-end / frame-counter read-back | 0x078 is what `aspeed-video` reads as frame size |
| 0x090–0x0A0 | mode-detection read-back | frame edges, V-lines, sync widths |
| 0x304 / 0x308 | interrupt enable / status (W1C) | → VIC INT#7 (level-high) |

## 2. QEMU faithfulness — MODELLED (`aspeed.video-ast2050`), capture datapath included

`peripherals/video/fwtest.c` drives the full §20.6-style flow and all checks PASS:

- **VR000** protection-key lock latch (write `0x1A038AA8` → reads 1; other regs RW
  while unlocked, writes dropped while locked).
- **Mode detection** (VR004[0] 0→1): the modelled internal-VGA source reports a fixed
  **640x480@60** scanout (classic VGA timing: 800x525 total, hsync 96 / vsync 2,
  positive polarities) via VR090/VR094 frame edges, VR098 V-lines + stable bits,
  VR09C sync widths, VR0A0 H-total; then mode-detection-ready (VR308[4]) on INT#7.
- **Capture + compression** (VR004[1]/[4] 0→1): the engine reads the source frame out
  of the **VGA carve-out at the top of BMC DRAM** (VR008[2]=0 internal-VGA source;
  carve-out size = the SCU70[3:2] strap — 8 MB on the KGPE-D16, hardware-verified via
  the live JTAG `MCR04 = 0x00000585` read-back), JPEG-compresses it, DMAs the frame to
  the VR054 stream buffer (clamped to the VR058 size → oversize = truncated JPEG, like
  silicon), updates VR070/VR078/VR07C, and raises capture- + compression-complete
  (VR308[1]/[3]) on **INT#7 (now wired to the G3 VIC)**. VR004[16]/[18] read busy (0)
  while the ~2 ms frame timer is in flight.
- The OpenBMC `aspeed-video` driver binds, detects 640x480, streams, and **dequeues a
  real JPEG frame** — verified end-to-end by `scripts/video-capture-test.py` (guest
  writes a test pattern into the carve-out; the dequeued V4L2 frame decodes to it).

### Modelling contracts (documented approximations)

1. **Scanout format.** The BMC-only machine has no VGA-controller model, so the
   internal-VGA source is contractually a **linear 640x480 XRGB8888** frame at the
   carve-out base (stride width*4) — i.e. "the host set 640x480x32". On silicon the
   mode/format follow the host's actual VGA mode-set (VR340–35C scratch read-back).
2. **Bitstream format.** The datasheet documents buffer/trigger/status/IRQ semantics
   but **not the G3 compressed bitstream format**. The model emits a self-contained
   baseline **JFIF JPEG** (YCbCr 4:4:4, ITU-T T.81 Annex K tables, quality from
   VR060[15:11]) — what the (G4-class) `aspeed-video` driver + userspace consume.
   Real-G3 divergences the model tolerates rather than reproduces: the driver writes
   its G4 JPEG-header-table address to 0x040 (VR040 = **CRC buffer base** on the G3)
   and sets VR004[8] ("AST2400 JPEG mode", undocumented on the G3, where pure-JPEG is
   VR060[0]); both are stored as plain RW bits. Capturing the true G3 bitstream needs
   real-silicon captures (see HW-VALIDATION-CHECKLIST).
3. The internal source-double-buffer staging (VR044/VR04C) is not modelled — the
   addresses are honoured as registers, but the engine compresses straight from the
   scanout (their content layout is not documented and nothing reads them).

## 3. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ VR000 key + mode-detect + capture→JPEG→INT#7 (13 checks) |
| 2 | doc (this + `DATASHEET-VIDEO.md`) | ☑ |
| 3 | QEMU model | ☑ `aspeed.video-ast2050` register interface + capture datapath |
| 4 | integration test (`../../integration/test_video.py`) | ☑ passes (6 tests) |
| 5 | Linux end-to-end (pattern → /dev/video0 JPEG frame) | ☑ `scripts/video-capture-test.py` + CI `d16-kvm.yml` |

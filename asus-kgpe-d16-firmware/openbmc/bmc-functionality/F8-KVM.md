# F8 — KVM-over-IP on the AST2050 BMC ("see the virtual VGA screen and send keyboard events")

**Goal (user):** be able to *see the virtual VGA screen and send keyboard events* —
i.e. KVM-over-IP (vKVM): the BMC captures the host's VGA framebuffer, presents a
virtual keyboard/mouse to the host, and streams video + injects HID over the network.

**Headline (faithfulness-first):** KVM-over-IP on the AST2050 is **three real
silicon blocks**, each already modelled register-accurately in the faithful QEMU
machine, plus one userspace daemon:

| Layer | AST2050 hardware | Base / IRQ | OpenBMC driver / daemon | F8 status |
|---|---|---|---|---|
| **1. Video capture** | Video Engine (JPEG/VQ compressor) | `0x1E700000`, VIC **INT#7** | `aspeed-video` (V4L2) → `/dev/video0` | **REAL FRAME captured in QEMU: pattern in VGA DRAM → dequeued JPEG verified (§3.1)** |
| **2. Virtual HID** | USB2.0 device / virtual-hub | `0x1E6A0000`, VIC **INT#5** | `aspeed-vhub` UDC + configfs `f_hid` → `/dev/hidgN` | **HID kbd+mouse gadget + keypress bytes in QEMU** |
| **3. Stream+inject** | *(userspace)* | — | `obmc-ikvm` (RFB/VNC server) → Redfish `GraphicalConsole` | **assessed for 64 MB (see §4)** |

Everything demonstrated here is **QEMU-only** (see §5 for the real-HW status and the
honest boundary of each layer). This builds directly on **[F6-USB.md](F6-USB.md)**
(the vhub / USB gadget groundwork) and the prior `aspeed.video-ast2050` depth model.

---

## 1. Ground truth — what the AST2050 video hardware really is (datasheet)

Source: **ASPEED AST2050/AST1100 A3 Datasheet V1.05** (in-repo:
`dell-c410x-firmware/datasheets/AST2050_AST1100_A3_Datasheet_V1.05.pdf`). Full
register-level extract with page cites:
[`qemu-model/peripherals/video/DATASHEET-VIDEO.md`](../../qemu-model/peripherals/video/DATASHEET-VIDEO.md).

- **§9 memory map (p.97):** **"Video Engine 1E70:0000–1E71:FFFF, 128 KB"** — a single
  video-engine aperture. Base = **`0x1E700000`**.
- **§10 interrupt table (p.99):** **"Video Engine = INT#7"**, sensitive-high-level.
- **§1.3.6 feature summary (ToC p.19):** **"Video Compression Engine (AST2050 only)"** —
  the sibling **AST1100 does not include the video compression engine**. A model tied
  to the `ast1100` SKU must gate it off.
- **§20 Video Engine (p.232–255):** JPEG + Vector-Quantization mixed compression; five
  DRAM buffers (2× video-source, CRC, block-change-detection flag, compressed stream);
  register access over AHB but pixel **data over the M-Bus** (direct DRAM); source =
  **internal VGA output** or external DVO; YUV420/YUV444; up to 1920×1200×32bpp; 12
  JPEG quality levels; **RC4 stream encryption** (256×8 key SRAM); mode-change watchdog.
- **§20.3 registers:** VR000 protection key (`0x1A03_8AA8` unlock), VR004 capture/
  compress trigger + status, VR008 source select (`[2]=0` internal VGA, `[5]=1` direct
  frame-buffer fetch — the standard KVM capture config), VR040–VR058 buffer bases,
  VR060 JPEG/VQ control, **VR304/VR308 interrupt enable/status** (frame/capture/
  compression-complete → INT#7).

### 1.1 Real-HW software evidence (Raptor 2.6.28 + KVM stack)

Raptor Engineering's working AST2050 Linux port and OpenBMC stack drove this same
block for KVM. The AST2050 vKVM is the classic Aspeed path: the video engine
JPEG-compresses the SoC's own **integrated VGA CRT output** (the graphics the x86
host draws through the AST2050's VGA controller), and the USB2.0 vhub presents the
virtual keyboard/mouse **back to that host**. Datasheet §2.7 confirms the vhub "can
easily emulate USB keyboard and USB mouse functions" — the HID injection path.

### 1.2 AST2050 vs AST2400/2500/2600 (what a faithful model must capture)

The AST2050 video register file **differs from the G4/G5/G6** the mainline
`aspeed-video` driver targets (DATASHEET-VIDEO.md §7): the AST2050 has the VR000 key,
VR004 trigger/status, VR008 source-select, VR060 compression control, VR304/VR308
interrupts, and the VR040–058 buffers as its minimum surface, plus an **RC4
stream-encryption engine** (VR060[5], VR300, VR400–4FC key SRAM) that later parts
change/drop. So mainline `aspeed-video` binds by *class* (the `aspeed,ast2400-video-
engine` compatible), programs the engine, and registers `/dev/video0`, but its
capture-format / JPEG-partial features assume the G4 layout — a dedicated G3 tuning
is future work, exactly analogous to the vhub UDC gap in F6.

---

## 2. Prior faithful QEMU state (the starting point F8 builds on)

The `kgpe-d16-bmc` QEMU machine **already models both KVM silicon blocks** (submodule
`a010d69`), each gated on `silicon_rev == AST2050_A1_SILICON_REV` in
`hw/arm/aspeed_ast2400.c` and register-accurate:

- **`aspeed.video-ast2050`** (`hw/misc/aspeed_video_ast2050.c`) at `0x1E700000`:
  VR000 is a **protection-key lock latch** (write `0x1A038AA8` → reads back `1`
  unlocked / `0` locked; writes to other regs dropped while locked, RW while
  unlocked). Replaces the AST2400 unimplemented stub for the G3. *(F8 originally
  left the INT#7 line unconnected pending the capture behaviour; the F8 video-
  datapath follow-up implemented the capture datapath and wired INT#7 — see §3.1.)*
  Verified by `qemu-model/peripherals/video/fwtest.c` +
  `integration/test_video.py`.
- **`aspeed.udc-ast2050`** (`hw/misc/aspeed_udc_ast2050.c`) at `0x1E6A0000`: the
  USB2.0 device/vhub register block (RW), sized so `0x1E6A1000` stays unmapped (the
  AST2050 has **no EHCI host** there). Verified by F6.

**F8 changes no QEMU source** — the hardware model is sufficient for the achievable
QEMU bar. F8 adds the entire **OpenBMC (software) side**: the DTS nodes, the kernel
drivers, and the demonstrations.

---

## 3. What F8 adds (OpenBMC-side wiring + demonstration)

1. **DTS** (`dts/aspeed-bmc-asus-kgpe-d16.dts`): enable `&video`
   (`aspeed,ast2400-video-engine`, `0x1e700000`, INT#7, VCLK+ECLK from the
   aspeed-g4.dtsi node) so `aspeed-video` binds; enable `&vhub` with the **faithful
   G3 counts** (7 downstream ports / 21-endpoint pool, vs the AST2400's 5/15).
2. **Kernel** (`kernel/kgpe-d16-kvm.config`): V4L2 core + `CONFIG_VIDEO_ASPEED`
   (video capture) and host-side `HID`/`INPUT_EVDEV` (so the in-guest dummy_hcd
   loopback can turn a gadget report into an observable input event). The USB gadget
   stack + configfs `f_hid` come from F6's `kernel/kgpe-d16-usb.config`.
3. **Demonstration** (`initramfs/init`, gated on the `f8kvm` cmdline; runner
   `scripts/kvm-test.py`):
   - **Video:** `aspeed-video` probes the AST2050 video engine → **`/dev/video0`**.
   - **HID:** build a **virtual keyboard+mouse** gadget via configfs (`f_hid`,
     boot-keyboard + boot-mouse report descriptors), bind it to the software UDC,
     then **send a keyboard event** (`press 'a'` → 8-byte HID report
     `00 00 04 00 00 00 00 00` written to `/dev/hidg0`) and show that report crossing
     the dummy_hcd loopback to a **host-side evdev** device as an `EV_KEY`/`KEY_A`
     input event, plus a mouse report on `/dev/hidg1`.
4. **CI** (`.github/workflows/d16-kvm.yml`) + integration test
   (`qemu-model/integration/test_video.py` already covers the video register model;
   `test_usb.py` covers the vhub).

### 3.1 Video datapath — ACTUAL PIXELS through the modelled engine (boundary closed)

The original F8 boundary was *"no host VGA source + no capture datapath in the
model"*. The video-datapath follow-up closed it with the key faithful insight: **on
the KGPE-D16 the AST2050 IS the host's VGA adapter** — the host framebuffer lives in
**BMC DRAM**, in the VGA carve-out at the top of the 64 MB (§9 p.98: VGA/graphics
memory at the top of the DRAM aperture, sized by SCU70[3:2]). The strap is
**hardware-verified 8 MB**: the live JTAG DDR2 init computed `MCR04 = 0x00000585`
from the real SCU70 (bits [5:4] = 00 = 8 MB; `JTAG-USAGE-GUIDE.md`), so the carve-out
is `0x43800000–0x43FFFFFF`. Datasheet §20's engine captures from that "internal VGA"
source (VR008[2]=0) — so a faithful capture demo needs **no host CPU**: anything that
writes that DRAM region *is* "the host rendered something" (on real HW the host GPU
path writes this same DRAM).

What was added (QEMU submodule + this repo):

- **QEMU model** (`aspeed_video_ast2050.c`): the full capture datapath — VR004[0]
  mode detection (640x480 internal-VGA read-back via VR090/094/098/09C/0A0),
  VR004[1]/[4] capture+compression triggers with [16]/[18] busy/idle status, source
  read from the strapped VGA carve-out, JPEG compression (quality from VR060[15:11]),
  stream written to the VR054 buffer (VR058-clamped; oversize = truncated JPEG like
  silicon), VR070/078/07C read-back counters, and **VR304/VR308 completion on INT#7,
  now wired to the G3 VIC** (irqmap 7, §10 p.99). Two documented modelling contracts
  (`qemu-model/peripherals/video/DOC.md` §2): the scanout is contractually a linear
  640x480 XRGB8888 frame at the carve-out base (no VGA-controller model), and the
  bitstream is a standard JFIF JPEG (the datasheet does not document the G3 bitstream
  format — real-silicon captures are the remaining oracle).
- **DTS**: `vga_memory` reserved-memory node (no-map, 8 MB @0x43800000) keeps the BMC
  kernel out of the host's framebuffer — same pattern as the C410X and mainline
  aspeed boards.
- **Demo** (`initramfs/f8video.c` + the `f8video` init gate + runner
  `scripts/video-capture-test.py`): the guest writes an **8-bar colour test pattern**
  into the carve-out via `/dev/mem`, then streams one frame from `/dev/video0`
  (mmap, 3 buffers). The mainline `aspeed-video` driver detects 640x480, programs the
  buffers, triggers VR004; the modelled engine reads the pattern out of DRAM,
  JPEG-compresses it into the driver's vb2 buffer and raises INT#7; the driver's IRQ
  thread completes the buffer; the dequeued JPEG is emitted as base64 and
  **decoded + pixel-verified against the pattern on the host** (all 8 bars match).
  That is "seeing the virtual VGA screen" in QEMU. Evidence:
  `evidence/video-datapath/` (captured `frame.jpg`/`frame.png` + serial log); CI job
  `boot-video-capture` in `d16-kvm.yml` re-captures and re-verifies on every push.
- **No kernel patch was needed**: the v6.6 `aspeed-video` register surface
  (VR000/004/008/030-058/060/078/090-0A0/304/308) is layout-compatible with the G3
  for everything the driver touches. The two G4-isms the driver emits (JPEG-header
  table address written to 0x040 = VR040 CRC-buffer base on the G3; VR004[8]
  "AST2400 JPEG mode", where the documented G3 pure-JPEG select is VR060[0]) are
  harmless register writes on the real G3 and are stored-not-interpreted by the
  model; they are documented as the residual G3-vs-G4 tension to check on silicon.

### Honest boundary of each layer (what QEMU cannot show)

- **Video — remaining boundary is silicon, not QEMU.** With the datapath modelled and
  a real frame dequeued (§3.1), what QEMU still cannot show: (a) **a real host GPU
  writing the framebuffer** — on silicon the x86 host renders through the AST2050 VGA
  controller into the same carve-out the demo writes by hand; (b) the **true G3
  compressed-bitstream format** (the datasheet documents buffers/triggers/IRQs, not
  the bit-level stream; the model emits standard JFIF, which is what the G4-class
  driver stack consumes — whether real G3 silicon does likewise needs a hardware
  capture); (c) real-HW mode-set variety (the model's source is contractually
  640x480x32).
- **HID — no real server host.** The AST2050 vhub presents the virtual keyboard/mouse
  to the *managed x86 host*, which QEMU's BMC-only machine does not emulate. The
  keypress is therefore demonstrated over **`dummy_hcd`** (a software UDC+host
  loopback) — this proves the exact HID report byte-stream a keypress produces and
  that a host HID stack turns it into an input event, but the real host-facing path
  (vhub → real host) needs a **dedicated G3 UDC driver + a functional QEMU vhub
  datapath** (the F6/F8 approximation).
- **obmc-ikvm — see §4.**

---

## 4. obmc-ikvm on the 64 MB AST2050 — assessment

The lean OpenBMC image (F0) **excludes `obmc-ikvm`**. Can it be added and does it fit?
Two separate questions — rootfs footprint vs runtime DRAM:

### 4.1 Rootfs / flash footprint (small — not the blocker)

`obmc-ikvm` is a small C++ daemon that reads `/dev/video0` (V4L2), serves the RFB
(VNC) protocol on a TCP port, and injects HID via `/dev/hidgN`. Its runtime deps are
modest: `libjpeg-turbo` (the aspeed-video JPEG passthrough) and OpenSSL (already in
the image for bmcweb/Redfish); the RFB service is advertised through **bmcweb's
Redfish `GraphicalConsole`** (also already present). The binary + `libjpeg-turbo`
adds well under ~1 MB to the rootfs — **that alone would fit**; F0 dropped it as part
of trimming the image to the smallest Redfish-only footprint, not because ~1 MB is
individually unaffordable.

### 4.2 Runtime DRAM — the real constraint (the 32 MB video carve-out)

The dominant cost of *functional* KVM is **the video-engine capture memory**, not the
daemon. Every mainline Aspeed BMC device tree reserves a large `video_engine_memory`
region for the JPEG/capture DMA buffers:

| Board DTS | `video_engine_memory` size |
|---|---|
| `aspeed-bmc-amd-daytonax`, `-ampere-mtjade`, `-opp-mowgli`, `-bytedance-g220a`, `-vegman-*` | **`0x02000000` = 32 MB** |
| `aspeed-bmc-inventec-starscream` | **`0x04000000` = 64 MB** |

On a board with 512 MB–1 GB (typical AST2500/2600) a 32 MB carve-out is trivial. On
the **AST2050 with 64 MB total DRAM (hardware-verified)** it is **half the RAM**. Add
the SoC VGA framebuffer the engine captures (8 MB on the C410X `vga_memory`, up to
32 MB elsewhere) and video alone wants **~40 MB of 64 MB**, leaving ~16–24 MB for the
kernel + all OpenBMC daemons. That does not leave room for a full-resolution vKVM
stream alongside bmcweb/Redfish.

**Conclusion (honest):** the `obmc-ikvm` *binary* fits a 64 MB image, but a *full*
capture pipeline (32 MB reserved buffers + framebuffer) does **not** comfortably
coexist with OpenBMC in 64 MB. A 64 MB AST2050 vKVM would need a **reduced buffer
budget** — a smaller `video_engine_memory` (e.g. 8–16 MB, trading max resolution/
frame-rate), on-demand allocation, and low-res/low-quality JPEG. That tuning is real
hardware work beyond QEMU. What F8 demonstrates is the **underlying `/dev/video0` +
HID-gadget capability a KVM client (obmc-ikvm) consumes**; whether the full daemon is
enabled is a memory-budget decision documented here, not a capability gap.

> Our KGPE-D16 DTS deliberately does **not** add a `video_engine_memory` reserved
> region: `aspeed-video` then falls back to the default DMA pool (fine for probe +
> `/dev/video0`; a small JPEG-header buffer is allocated at probe). Adding the 32 MB
> reservation is what a production capture config would do — and is exactly what
> collides with the 64 MB budget above.

---

## 5. Real-hardware status (honest QEMU-only vs HW-proven)

**Everything in §3 is QEMU-only.** Faithfulness rests on (a) the datasheet (§1: one
video engine at 0x1E700000/INT#7, one USB2.0 vhub at 0x1E6A0000/INT#5) and (b) the
mainline `aspeed-video` + `aspeed-vhub` drivers binding cleanly to the
datasheet-accurate QEMU register blocks.

**Not exercised on real hardware this session.** The shared AST2050 rig is contended
and every state-mutating operation must be coordinated on the Pi's
`HARDWARE-COORDINATION.md`; F-HWPASS owns the consolidated real-HW boot. No
state-mutating action was taken on the board.

**Available non-disruptive real-HW paths (for a future HW session):**
- Read VR000/VR008 of the video engine at `0x1E700000` and HUB00 of the vhub at
  `0x1E6A0000` via the proven P2A / JTAG AHB backdoors (same read path as SCU7C) to
  confirm both regions decode — no boot slot needed.
- Bringing up real capture on silicon (`/dev/video0` streaming a JPEG of the host
  screen): the QEMU-side datapath + INT#7 wiring now exist (§3.1), so the silicon
  session needs the host booted with its VGA mode set (the host GPU path then writes
  the same 0x43800000 carve-out the QEMU demo patterns by hand) and a capture of the
  real G3 bitstream to check the standard-JFIF contract. The host-facing HID
  keypress still needs the G3 UDC driver.

---

## 6. Deliverable status

| # | Layer | Deliverable | State |
|---|---|---|---|
| 1 | Video | datasheet ground truth (§1) + `DATASHEET-VIDEO.md` | ☑ |
| 1 | Video | DTS `&video` enabled; `CONFIG_VIDEO_ASPEED` | ☑ |
| 1 | Video | `aspeed-video` probes → `/dev/video0` in QEMU | ☑ (evidence §3) |
| 1 | Video | **capture datapath (VR004 → JPEG → INT#7) + real frame dequeued & pixel-verified** | ☑ (§3.1; `evidence/video-datapath/`; CI `boot-video-capture`) |
| 2 | HID | DTS `&vhub` (7 ports/21-EP); F6 gadget + `f_hid` | ☑ |
| 2 | HID | keyboard+mouse gadget + keypress byte-stream → host evdev | ☑ (evidence §3) |
| 3 | obmc-ikvm | 64 MB fit assessment (§4) | ☑ (documented; not built — one-Yocto-build rule) |
| — | Host-facing HID (vhub → real host) | — | ☐ needs G3 UDC driver + vhub datapath |
| — | Real-HW KVM | — | ☐ needs a real host GPU writing the carve-out (host boots + VGA mode-set) + G3 bitstream capture to check the JFIF contract |

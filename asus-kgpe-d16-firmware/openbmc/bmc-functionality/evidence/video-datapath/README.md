# F8 video-datapath evidence — a REAL FRAME through the modelled AST2050 video engine

Captured 2026-07-12 by `qemu-firmware/scripts/video-capture-test.py` on the
`kgpe-d16-bmc` QEMU machine (64 MB, the hardware-verified AST2050 DRAM size).
See `../../F8-KVM.md` §3.1 for the full path description.

What happened, end to end:

1. The guest (Linux 6.6.70 + mainline `aspeed-video`, initramfs `f8video` tool)
   wrote an **8-bar colour test pattern** (640x480 XRGB8888) into the VGA
   carve-out at `0x43800000` via `/dev/mem` — the region where, on real
   hardware, the x86 host's GPU path renders (the AST2050 IS the host's VGA
   adapter; carve-out = 8 MB per the hardware-verified SCU70[3:2] strap).
2. `v4l2` streaming on `/dev/video0`: the driver mode-detected 640x480,
   allocated buffers, and triggered the engine (VR004). The **modelled engine**
   read the pattern out of DRAM, JPEG-compressed it into the driver's vb2
   buffer (VR054), and raised **VIC INT#7**; the driver's IRQ thread completed
   the buffer.
3. The dequeued V4L2 buffer — `frame.jpg`, 10,696 bytes — was emitted over the
   serial console as base64 (`serial.log`) and decoded/verified on the host:
   **all 8 bars match the drawn pattern** (per-channel means within 3/255).

| File | What it is |
|---|---|
| `frame.jpg` | the raw dequeued V4L2 buffer (the JPEG the modelled engine wrote) |
| `frame.png` | the same frame decoded to PNG (view this) |
| `serial.log` | full guest transcript incl. the F8-FRAME-BEGIN/END emission |

Verification output (from the run):

```
  [PASS] aspeed-video probed the engine -> /dev/video0
  [PASS] V4L2 dequeued a JPEG frame (10696 bytes, 640x480)
  [PASS] frame decodes as 640x480 (expected 640x480)
  [PASS] bar white      mean=(255, 255, 255) want~(255, 255, 255)
  [PASS] bar yellow     mean=(254, 255, 0) want~(255, 255, 0)
  [PASS] bar cyan       mean=(0, 255, 252) want~(0, 255, 255)
  [PASS] bar green      mean=(0, 255, 0) want~(0, 255, 0)
  [PASS] bar magenta    mean=(255, 1, 255) want~(255, 0, 255)
  [PASS] bar red        mean=(254, 0, 0) want~(255, 0, 0)
  [PASS] bar blue       mean=(0, 0, 253) want~(0, 0, 255)
  [PASS] bar near-black mean=(16, 16, 16) want~(16, 16, 16)

F8 VIDEO-DATAPATH RESULT: PASS
```

CI re-captures and re-verifies this on every push: job `boot-video-capture`
in `.github/workflows/d16-kvm.yml` (frame uploaded as the `captured-frame`
artifact).

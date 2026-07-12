#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow"]
# ///
"""F8 video-datapath test: boot the KVM-enabled kernel on the kgpe-d16-bmc
(AST2050) QEMU machine and capture a REAL FRAME through the modelled video
engine — "see the virtual VGA screen" with actual pixels.

On the KGPE-D16 the AST2050 IS the host's VGA adapter: the host framebuffer
lives in BMC DRAM (the 8 MB vga_memory carve-out at 0x43800000, sized by the
hardware-verified SCU70[3:2] strap). Datasheet §20's video engine captures
from that "internal VGA" source. The in-guest f8video tool (see
initramfs/f8video.c and the 'f8video' init gate):

  1. writes an 8-bar colour test pattern into the carve-out via /dev/mem
     ("the host rendered something" — on real HW the host GPU path writes
     this same DRAM);
  2. streams one frame from /dev/video0: the aspeed-video V4L2 driver
     programs + triggers the engine (VR004), the modelled engine reads the
     VGA scanout, JPEG-compresses it into the driver's vb2 buffer and raises
     VIC INT#7, and the driver completes the buffer;
  3. emits the dequeued JPEG as base64 between F8-FRAME-BEGIN/END markers.

This harness decodes the frame (Pillow) and verifies each of the 8 bars'
mean colour matches the pattern the guest drew — pixels in, pixels out.

PASS = frame decoded AND all 8 bars match. Evidence (JPEG + PNG + log) is
written to --evidence-dir.
"""
import argparse
import base64
import io
import os
import re
import selectors
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

BEGIN_RE = re.compile(r"F8-FRAME-BEGIN size=(\d+) fmt=(\d+)x(\d+)")
END_MARK = "F8-FRAME-END"
DEMO_END = "=== F8-VIDEO-DEMO-END ==="

# The bars f8video.c draws, left to right (R, G, B).
BARS = [
    ("white",      (0xff, 0xff, 0xff)),
    ("yellow",     (0xff, 0xff, 0x00)),
    ("cyan",       (0x00, 0xff, 0xff)),
    ("green",      (0x00, 0xff, 0x00)),
    ("magenta",    (0xff, 0x00, 0xff)),
    ("red",        (0xff, 0x00, 0x00)),
    ("blue",       (0x00, 0x00, 0xff)),
    ("near-black", (0x10, 0x10, 0x10)),
]
TOLERANCE = 24  # per-channel mean tolerance (JPEG is lossy)


def stream_until(proc, markers, timeout):
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        if proc.poll() is not None:
            return buf
        for _ in sel.select(timeout=1.0):
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                continue
            sys.stdout.write(chunk.decode("utf-8", "replace"))
            sys.stdout.flush()
            buf += chunk
            for m in markers:
                if m.encode() in buf:
                    return buf
    return buf


def extract_frame(text):
    """Return (jpeg_bytes, width, height) from the serial transcript."""
    m = BEGIN_RE.search(text)
    if not m:
        return None, 0, 0
    size, width, height = int(m.group(1)), int(m.group(2)), int(m.group(3))
    tail = text[m.end():]
    end = tail.find(END_MARK)
    if end < 0:
        return None, 0, 0
    b64 = "".join(tail[:end].split())
    jpeg = base64.b64decode(b64)[:size]
    return jpeg, width, height


def verify_bars(img):
    """Sample each bar's centre region; return a list of (name, ok, mean)."""
    w, h = img.size
    bar_w = w // len(BARS)
    results = []
    for i, (name, want) in enumerate(BARS):
        # centre patch of the bar, away from bar edges and JPEG block edges
        x0 = i * bar_w + bar_w // 4
        x1 = (i + 1) * bar_w - bar_w // 4
        patch = img.crop((x0, h // 4, x1, 3 * h // 4))
        px = list(patch.getdata())
        n = len(px)
        mean = tuple(sum(c[j] for c in px) // n for j in range(3))
        ok = all(abs(mean[j] - want[j]) <= TOLERANCE for j in range(3))
        results.append((name, ok, mean, want))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--initrd", required=True)
    ap.add_argument("--dtb", required=True)
    # The real AST2050 has 64 MB DDR2 (hardware-verified); the top 8 MB is the
    # VGA carve-out the engine captures from (vga_memory @0x43800000).
    ap.add_argument("--mem", type=int, default=64)
    ap.add_argument("--boot-timeout", type=int, default=300)
    ap.add_argument("--evidence-dir",
                    help="write frame.jpg / frame.png / serial.log here")
    args = ap.parse_args()

    append = "console=ttyS4,115200n8 earlyprintk f8video"
    cmd = [args.qemu, "-M", "kgpe-d16-bmc", "-m", str(args.mem), "-nographic",
           "-monitor", "none", "-serial", "stdio",
           "-nic", "user,model=ftgmac100",
           "-kernel", args.kernel, "-initrd", args.initrd,
           "-dtb", args.dtb, "-append", append, "-no-reboot"]
    print("boot:", " ".join(cmd))
    qemu = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    try:
        buf = stream_until(qemu, [DEMO_END], args.boot_timeout)
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qemu.kill()
    text = buf.decode("utf-8", "replace")

    print("\n--- F8 video-datapath checks ---")
    probed = "F8-VIDEO: /dev/video0 present" in text
    print(f"  [{'PASS' if probed else 'FAIL'}] aspeed-video probed the engine "
          f"-> /dev/video0")

    jpeg, width, height = extract_frame(text)
    got_frame = jpeg is not None and jpeg[:2] == b"\xff\xd8"
    print(f"  [{'PASS' if got_frame else 'FAIL'}] V4L2 dequeued a JPEG frame "
          f"({len(jpeg) if jpeg else 0} bytes, {width}x{height})")
    if not got_frame:
        print("\nF8 VIDEO-DATAPATH RESULT: FAIL")
        return 1

    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    size_ok = img.size == (width, height) == (640, 480)
    print(f"  [{'PASS' if size_ok else 'FAIL'}] frame decodes as "
          f"{img.size[0]}x{img.size[1]} (expected 640x480)")

    results = verify_bars(img)
    bars_ok = all(ok for _, ok, _, _ in results)
    for name, ok, mean, want in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] bar {name:<10} mean={mean} "
              f"want~{want}")

    if args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        (ev / "frame.jpg").write_bytes(jpeg)
        img.save(ev / "frame.png")
        (ev / "serial.log").write_text(text)
        print(f"evidence written to {ev}/ (frame.jpg, frame.png, serial.log)")

    ok = probed and got_frame and size_ok and bars_ok
    print("\nF8 VIDEO-DATAPATH RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

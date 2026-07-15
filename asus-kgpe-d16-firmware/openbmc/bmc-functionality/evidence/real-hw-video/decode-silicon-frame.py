#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow"]
# ///
"""Extract the F8-FRAME base64 from a silicon boot log and decode it DIRECTLY --
no offline reconstruction. With the driver's in-kernel JFIF wrapping, the bytes
between F8-FRAME-BEGIN/END must already be a standards-compliant JPEG
(FFD8..FFD9, correct SOF0 dims). This is the on-silicon proof of the wrapping.
"""
import base64, io, re, sys
from PIL import Image

log = open(sys.argv[1], "r", errors="replace").read()
m = re.search(r"F8-FRAME-BEGIN\s*\n(.*?)\nF8-FRAME-END", log, re.S)
if not m:
    print("NO F8-FRAME block found in log")
    # surface capture diagnostics
    for line in log.splitlines():
        if any(k in line for k in ("F8-CAPTURE", "FMT:", "SIGNAL", "video0", "FAIL")):
            print("  |", line.strip())
    sys.exit(2)

b64 = "".join(m.group(1).split())          # strip serial noise/whitespace
data = base64.b64decode(b64)
out = sys.argv[1].replace(".log", "-silicon-direct.jpg")
open(out, "wb").write(data)

print(f"frame: {len(data)} bytes")
print(f"first 4: {data[:4].hex(' ')} (want ff d8 ff e0/e1)")
print(f"last  2: {data[-2:].hex(' ')} (want ff d9)")
soi = data[:2] == b"\xff\xd8"
eoi = data[-2:] == b"\xff\xd9"
print(f"SOI={soi} EOI={eoi}")

try:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = img.size
    px = img.resize((32, 32))
    vals = [sum(px.getpixel((x, y))) // 3 for y in range(32) for x in range(32)]
    spread = max(vals) - min(vals)
    img.save(out.replace(".jpg", ".png"))
    print(f"DECODED DIRECTLY {w}x{h}  spread={spread}  -> "
          f"{'REAL CONTENT — standards JPEG on silicon' if spread >= 8 else 'uniform'}")
    print(f"wrote {out} and .png")
except Exception as e:
    print(f"DIRECT DECODE FAILED: {e!r}  (wrapping bug — frame is not a valid JPEG)")
    sys.exit(1)

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow"]
# ///
"""Reproduce EXACTLY what the committed aspeed-video driver now does in
aspeed_video_build_jfif_header() + aspeed_video_wrap_jfif(), then run it on the
REAL AST2050 silicon entropy stream and decode the result. This validates the
driver's byte-for-byte algorithm against real hardware output.

Driver ops mirrored here:
  build:  hdr = jpeg_header ++ jpeg_dct[sel] ++ jpeg_quant   (LE u32 -> mem bytes)
          sel = min(jpeg_quality, 7)                          (G3 clamp)
          SOF0 at FIXED offset = sizeof(header)+sizeof(dct)-1 (= 175); assert FFC0
          patch h[+5..+9] = height(BE), width(BE)
  wrap:   payload = hdr ++ entropy ++ FF D9   (EOI); NO word-swap
"""
import base64, io, re, struct, sys
from PIL import Image

SRC = ("/home/tim/github/mithro/ai-shenanigans-for-bmcs/.worktrees/bmc-functionality/"
       "asus-kgpe-d16-firmware/qemu-firmware/kernel/linux/"
       "drivers/media/platform/aspeed/aspeed-video.c")

def parse_u32_array(text, name):
    m = re.search(name + r"\b[^=]*=\s*\{(.*?)\};", text, re.S)
    return [int(h, 16) for h in re.findall(r"0x[0-9a-fA-F]+", m.group(1))]

def build_header(src, sel, width, height):
    """Mirror aspeed_video_build_jfif_header()."""
    hdr   = parse_u32_array(src, "aspeed_video_jpeg_header")
    quant = parse_u32_array(src, "aspeed_video_jpeg_quant")
    dct_f = parse_u32_array(src, "aspeed_video_jpeg_dct")
    dct   = dct_f[sel*34:(sel+1)*34]
    assert len(hdr) == 10 and len(dct) == 34 and len(quant) == 116, "array sizes"

    h = bytearray(b"".join(struct.pack("<I", w) for w in (hdr + dct + quant)))
    assert len(h) == 640, f"header len {len(h)} != 640"

    # Deterministic SOF0 offset the driver uses: sizeof(header)+sizeof(dct)-1.
    sof = 10*4 + 34*4 - 1                       # == 175
    assert h[sof] == 0xff and h[sof+1] == 0xc0, \
        f"SOF0 not at {sof}: {h[sof]:02x} {h[sof+1]:02x}"
    h[sof+5] = height >> 8; h[sof+6] = height & 0xff   # height BE at +5
    h[sof+7] = width  >> 8; h[sof+8] = width  & 0xff   # width  BE at +7
    return bytes(h), sof

def main():
    b64, sel, width, height = sys.argv[1], 7, 1024, 768
    src = open(SRC).read()
    header, sof = build_header(src, sel, width, height)
    print(f"header: {len(header)} B, starts {header[:4].hex(' ')} (want ff d8 ff e0)")
    print(f"SOF0@{sof}: {header[sof:sof+11].hex(' ')} "
          f"(want ff c0 00 11 08 03 00 <hi> <lo> 04 00 03)")

    entropy = base64.b64decode(open(b64).read())
    # wrap: header ++ entropy ++ EOI, NO swap (exactly the driver).
    jpeg = header + entropy + b"\xff\xd9"
    out = b64.replace(".b64", "-driver.jpg")
    open(out, "wb").write(jpeg)
    print(f"payload: {len(jpeg)} B = 640 hdr + {len(entropy)} entropy + 2 EOI, "
          f"ends {jpeg[-2:].hex(' ')} (want ff d9)")

    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    w, h = img.size
    px = img.resize((32, 32))
    vals = [sum(px.getpixel((x, y)))//3 for y in range(32) for x in range(32)]
    mn, mx, mean = min(vals), max(vals), sum(vals)//len(vals)
    print(f"DECODED {w}x{h}  min={mn} max={mx} mean={mean} spread={mx-mn}  -> "
          f"{'REAL CONTENT (valid standards JPEG)' if mx-mn >= 8 else 'uniform'}")
    img.save(b64.replace(".b64", "-driver.png"))
    print(f"wrote {out} and {out.replace('.jpg', '.png')}")

if __name__ == "__main__":
    main()

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow"]
# ///
"""Wrap the raw ASPEED G3 entropy stream in the JFIF header the mainline
aspeed-video driver builds (jpeg_header + jpeg_dct[q] + jpeg_quant, little-endian
u32 words -- the exact header the G4 engine prepends). This reconstructs a standard
JPEG from the G3's headerless output so we can view the captured host VGA frame."""
import base64, io, re, struct, sys
from PIL import Image

SRC = "/home/tim/github/mithro/ai-shenanigans-for-bmcs/.worktrees/bmc-functionality/asus-kgpe-d16-firmware/qemu-firmware/kernel/linux/drivers/media/platform/aspeed/aspeed-video.c"

def parse_u32_array(text, name):
    """Return a flat list of u32 from `static const u32 name[...] = { ... };`."""
    m = re.search(name + r"\b[^=]*=\s*\{(.*?)\};", text, re.S)
    body = m.group(1)
    return [int(h, 16) for h in re.findall(r"0x[0-9a-fA-F]+", body)]

def main():
    q = int(sys.argv[2]) if len(sys.argv) > 2 else 7   # DCT table index used (clamped)
    src = open(SRC).read()
    hdr = parse_u32_array(src, "aspeed_video_jpeg_header")            # 10 words
    quant = parse_u32_array(src, "aspeed_video_jpeg_quant")           # 116 words
    dct_flat = parse_u32_array(src, "aspeed_video_jpeg_dct")          # 12*34 words
    dct = dct_flat[q*34:(q+1)*34]
    print(f"hdr={len(hdr)} dct[{q}]={len(dct)} quant={len(quant)} words")

    # header table entry = jpeg_header + jpeg_dct[q] + jpeg_quant, each u32 as LE bytes
    words = hdr + dct + quant
    header = bytearray(b"".join(struct.pack("<I", w) for w in words))
    print(f"JFIF header = {len(header)} bytes; starts {header[:4].hex(' ')} (want ff d8 ff e0)")

    # The static header ships SOF0 height/width = 0 (the G4 engine patches the real
    # dims in HW; the G3 engine doesn't). Patch SOF0 (FF C0): [+3..+5]=height BE,
    # [+5..+7]=width BE. Dims from the capture: 1024x768 (mode-detected on silicon).
    W, H = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1024, 768)
    sof = header.find(b"\xff\xc0")
    header[sof+5:sof+7] = struct.pack(">H", H)
    header[sof+7:sof+9] = struct.pack(">H", W)
    print(f"patched SOF0@{sof}: {W}x{H} -> {header[sof:sof+11].hex(' ')}")

    entropy = base64.b64decode(open(sys.argv[1]).read())
    swapped = bytearray(len(entropy))
    for i in range(0, len(entropy) - 3, 4):
        swapped[i:i+4] = entropy[i:i+4][::-1]

    for tag, ent in (("as-is", entropy), ("wordswap", bytes(swapped))):
        jpeg = header + ent + b"\xff\xd9"
        out = sys.argv[1].replace(".b64", f"-{tag}.jpg")
        open(out, "wb").write(jpeg)
        try:
            img = Image.open(io.BytesIO(jpeg)).convert("RGB")
            w, h = img.size
            px = img.resize((32, 32))
            vals = [sum(px.getpixel((x, y)))//3 for y in range(32) for x in range(32)]
            mn, mx, mean = min(vals), max(vals), sum(vals)//len(vals)
            print(f"[{tag}] DECODED {w}x{h}  min={mn} max={mx} mean={mean} spread={mx-mn}"
                  f"  -> {'REAL CONTENT' if mx-mn >= 8 else 'uniform'}")
            img.save(sys.argv[1].replace(".b64", f"-{tag}.png"))
        except Exception as e:
            print(f"[{tag}] decode failed: {e!r}")

if __name__ == "__main__":
    main()

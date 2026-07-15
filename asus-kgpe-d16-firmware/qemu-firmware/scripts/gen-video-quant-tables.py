#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Emit C for the 8 AST2050 ROM quant tables (luma+chroma, raster order),
extracted from the Linux driver's jpeg_dct[0..7] DQT segments. Pasted into the
QEMU model so its encoder quantizes exactly as the G3 ROM does -> the driver's
prepended header decodes the model's headerless entropy."""
import re, struct

DRV = ("/home/tim/github/mithro/ai-shenanigans-for-bmcs/.worktrees/bmc-functionality/"
       "asus-kgpe-d16-firmware/qemu-firmware/kernel/linux/"
       "drivers/media/platform/aspeed/aspeed-video.c")
ZIGZAG = [0,1,8,16,9,2,3,10,17,24,32,25,18,11,4,5,
          12,19,26,33,40,48,41,34,27,20,13,6,7,14,21,28,
          35,42,49,56,57,50,43,36,29,22,15,23,30,37,44,51,
          58,59,52,45,38,31,39,46,53,60,61,54,47,55,62,63]

def parse_u32_array(text, name):
    m = re.search(name + r"\b[^=]*=\s*\{(.*?)\};", text, re.S)
    return [int(h, 16) for h in re.findall(r"0x[0-9a-fA-F]+", m.group(1))]

def dqt_raster(src, sel):
    hdr = parse_u32_array(src, "aspeed_video_jpeg_header")
    dct = parse_u32_array(src, "aspeed_video_jpeg_dct")[sel*34:(sel+1)*34]
    s = b"".join(struct.pack("<I", w) for w in (hdr + dct))
    tables = {}; off = 0
    while True:                              # driver uses one DQT marker per table
        i = s.find(b"\xff\xdb", off)
        if i < 0:
            break
        ln = struct.unpack(">H", s[i+2:i+4])[0]
        seg = s[i+4:i+2+ln]; p = 0
        while p < len(seg):
            tq = seg[p] & 0x0f; p += 1
            zz = list(seg[p:p+64]); p += 64
            raster = [0]*64
            for k in range(64):
                raster[ZIGZAG[k]] = zz[k]
            tables[tq] = raster
        off = i + 2 + ln
    return tables[0], tables[1]

def fmt_table(rows, name):
    out = [f"static const uint8_t {name}[8][64] = {{"]
    for sel in range(8):
        t = rows[sel]
        out.append(f"    {{ /* sel {sel} */")
        for r in range(8):
            line = " ".join(f"{t[r*8+c]:3d}," for c in range(8))
            out.append(f"        {line}")
        out.append("    },")
    out.append("};")
    return "\n".join(out)

def main():
    src = open(DRV).read()
    luma = {}; chroma = {}
    for sel in range(8):
        l, c = dqt_raster(src, sel)
        luma[sel] = l; chroma[sel] = c
    print("/* AST2050 ROM quantization tables (raster order), extracted from the")
    print(" * Linux aspeed-video driver's jpeg_dct[0..7] DQT segments. These are the")
    print(" * engine's fixed ROM tables; the driver's software JFIF header carries the")
    print(" * same tables, so the headerless entropy this model emits decodes cleanly. */")
    print(fmt_table(luma, "ast2050_quant_luma"))
    print(fmt_table(chroma, "ast2050_quant_chroma"))

if __name__ == "__main__":
    main()

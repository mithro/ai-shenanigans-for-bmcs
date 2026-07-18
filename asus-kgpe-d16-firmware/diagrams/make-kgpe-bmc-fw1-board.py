# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Generate kgpe-d16-bmc-fw1-board.png — annotated board photo locating BMC_FW1.

Uses the high-resolution KGPE-D16 top photo from theretroweb.com. Board is kept
in its natural (standard) orientation to match the ASUS manual and the pinout
SVG: BMC_FW1 is a 2x7 socket with **pin 1 at the bottom-left** and **pin 14
keyed (top-right)**. Signals are in kgpe-d16-bmc-fw1-pinout.svg.

BMC_FW1 pixel coords (in the source photo) were read off zoomed crops.

Run:  uv run make-kgpe-bmc-fw1-board.py
"""

import io
import urllib.request

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

SRC = "https://theretroweb.com/motherboard/image/dsc-7778-615-687f6933e78c9140165335.jpg"
OUT = "kgpe-d16-bmc-fw1-board.png"

req = urllib.request.Request(SRC, headers={"User-Agent": "Mozilla/5.0"})
raw = urllib.request.urlopen(req).read()  # noqa: S310 (public asset)
img = Image.open(io.BytesIO(raw)).convert("RGB")

# crop the BMC_FW1 neighbourhood (source px), brighten a touch, upscale
CX0, CY0 = 250, 3070
crop = img.crop((CX0, CY0, 720, 3360))
crop = ImageEnhance.Brightness(crop).enhance(1.35)
S = 2.5
base = crop.resize((int(crop.width * S), int(crop.height * S)), Image.LANCZOS)
d = ImageDraw.Draw(base)


def font(sz, bold=True):
    n = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{n}", sz)
    except OSError:
        return ImageFont.load_default()


RED, BLUE, GREEN, ORANGE, BLACK, GREY, WHITE = (
    (205, 25, 25), (0, 70, 190), (0, 130, 50), (210, 120, 0),
    (10, 10, 10), (120, 120, 120), (255, 255, 255),
)
F_H, F_B, F_S = font(27), font(23), font(20)


def tw(t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0]


def src2px(sx, sy):
    return int((sx - CX0) * S), int((sy - CY0) * S)


# ---- BMC_FW1 header box (source coords ~347..490 x, 3173..3218 y) ----
hx0, hy0 = src2px(345, 3170)
hx1, hy1 = src2px(492, 3221)
d.rectangle((hx0, hy0, hx1, hy1), outline=RED, width=4)

# 7 columns, 2 rows: pin 1 bottom-left, key (pin 14) top-right
col_x = [src2px(347 + (c + 0.5) * (490 - 347) / 7, 0)[0] for c in range(7)]
y_top = src2px(0, 3184)[1]
y_bot = src2px(0, 3208)[1]

# pin 1 marker (bottom-left) + key marker (top-right = pin 14)
p1x, p1y = col_x[0], y_bot
kx, ky = col_x[6], y_top
d.ellipse((p1x - 11, p1y - 11, p1x + 11, p1y + 11), outline=RED, width=4)
d.rectangle((kx - 11, ky - 11, kx + 11, ky + 11), fill=BLACK, outline=WHITE, width=2)


def tag(x, y, txt, col, f=F_B, anchor="lt"):
    w = tw(txt, f)
    tx = x - w - 6 if anchor == "rt" else x
    d.rectangle((tx - 4, y - 3, tx + w + 4, y + f.size + 4), fill=WHITE, outline=col, width=2)
    d.text((tx, y), txt, fill=col, font=f)


tag(hx0 - 12, p1y - 14, "pin 1", RED, anchor="rt")
d.line((kx, hy0 - 6, kx, ky - 12), fill=BLACK, width=2)          # tag -> key marker
tag(kx - 68, hy0 - 38, "key = pin 14", BLACK, F_S, anchor="lt")

# ---- signal legend (right side), rows matching the SVG numbering ----
# bottom row L->R = pins 1..7 ; top row L->R = key,13,12,11,10,9,8
sig = {1: ("MOSI", RED), 2: ("+3V3", GREY), 3: ("IKVMEN#", ORANGE),
       4: ("CS2", BLACK), 5: ("NC", GREY), 6: ("MISO", RED), 7: ("PRESENT#", ORANGE),
       8: ("SCK", RED), 9: ("NC", GREY), 10: ("SOLEN#", ORANGE), 11: ("NC", GREY),
       12: ("CS0", RED), 13: ("GND", GREEN)}
lines = [("BMC_FW1 — pin signals", RED, F_H)]
lines += [(f"{n:>2} {sig[n][0]}", sig[n][1], F_B) for n in range(1, 14)]
lines.append(("pin 1 = square pad · pin 14 top-right keyed", BLACK, F_S))
lines.append(("full pinout: kgpe-d16-bmc-fw1-pinout.svg", GREY, F_S))
lw = max(tw(t, f) for t, _, f in lines)
lx, ly = base.width - lw - 34, 54
d.rectangle((lx - 14, ly - 8, lx + lw + 14, ly + sum(f.size + 8 for _, _, f in lines) + 8),
            fill=WHITE, outline=RED, width=3)
cy = ly
for t, c, f in lines:
    d.text((lx, cy), t, fill=c, font=f)
    cy += f.size + 8

# ---- title strip ----
d.rectangle((0, 0, base.width, 44), fill=WHITE)
d.text((12, 8), "ASUS KGPE-D16 — BMC_FW1 BMC SPI boot-flash socket",
       fill=BLACK, font=F_H)

base.save(OUT)
print("wrote", OUT, base.size)

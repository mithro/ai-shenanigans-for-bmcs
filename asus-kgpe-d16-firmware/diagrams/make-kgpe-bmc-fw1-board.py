# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Generate kgpe-d16-bmc-fw1-board.png — annotated board photo locating BMC_FW1.

Uses the high-resolution KGPE-D16 top photo from theretroweb.com. Board is kept
in its natural (standard) orientation to match the ASUS manual and the pinout
SVG: BMC_FW1 is a 2x7 socket with **pin 1 at the bottom-left** and **pin 14
keyed (top-right)**. Every pin is labelled directly on the connector; the full
schematic pinout is in schematic-wiring/diagrams/kgpe-d16-bmc-fw1.svg.

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

# 7 columns, 2 rows: odd pins bottom row, even pins top row; pin 14 = key top-right
col_x = [src2px(347 + (c + 0.5) * (490 - 347) / 7, 0)[0] for c in range(7)]
y_top = src2px(0, 3184)[1]
y_bot = src2px(0, 3208)[1]

# pin -> (signal, colour): SPI blue, power green, strap orange, NC/GND grey, key black
sig = {1: ("MOSI", BLUE), 2: ("+3V3", GREEN), 3: ("IKVMEN#", ORANGE),
       4: ("CS2", BLUE), 5: ("NC", GREY), 6: ("MISO", BLUE), 7: ("PRESENT#", ORANGE),
       8: ("SCK", BLUE), 9: ("NC", GREY), 10: ("SOLEN#", ORANGE), 11: ("NC", GREY),
       12: ("CS0", BLUE), 13: ("GND", GREY), 14: ("key", BLACK)}
F_L = font(21)


def vlabel(cx, edge_y, text, color, above):
    """A rotated, white-backed label centred on column `cx`, pin number toward
    the connector; placed above (`above=True`) or below the header edge."""
    pad = 6
    w = tw(text, F_L)
    timg = Image.new("RGBA", (w + 2 * pad, F_L.size + 2 * pad), (255, 255, 255, 235))
    ImageDraw.Draw(timg).text((pad, pad - 2), text, fill=color, font=F_L)
    rot = timg.rotate(90 if above else -90, expand=True)
    x = int(cx - rot.width / 2)
    y = int(edge_y - rot.height) if above else int(edge_y)
    base.paste(rot, (x, y), rot)


# label every pin directly on the connector
for c in range(7):
    odd, even = 2 * c + 1, 2 * c + 2                 # bottom row / top row
    d.line((col_x[c], y_bot, col_x[c], hy1 + 5), fill=GREY, width=2)
    vlabel(col_x[c], hy1 + 8, f"{odd} {sig[odd][0]}", sig[odd][1], above=False)
    d.line((col_x[c], y_top, col_x[c], hy0 - 5), fill=GREY, width=2)
    vlabel(col_x[c], hy0 - 8, f"{even} {sig[even][0]}", sig[even][1], above=True)

# pin 1 (red ring, bottom-left) + key / pin 14 (black square, top-right)
d.ellipse((col_x[0] - 11, y_bot - 11, col_x[0] + 11, y_bot + 11), outline=RED, width=4)
d.rectangle((col_x[6] - 11, y_top - 11, col_x[6] + 11, y_top + 11),
            fill=BLACK, outline=WHITE, width=2)

# ---- title strip + one-line key ----
d.rectangle((0, 0, base.width, 44), fill=WHITE)
d.text((12, 8), "ASUS KGPE-D16 — BMC_FW1 BMC SPI boot-flash socket",
       fill=BLACK, font=F_H)
notes = ["SPI = blue · power = green · strap = orange · NC / GND = grey",
         "pin 1 = bottom-left (red ring) · pin 14 = key, top-right (black square)"]
nw = max(tw(n, F_S) for n in notes)
d.rectangle((6, base.height - 68, 22 + nw, base.height - 6),
            fill=WHITE, outline=BLACK, width=2)
for i, n in enumerate(notes):
    d.text((14, base.height - 62 + i * (F_S.size + 6)), n, fill=BLACK, font=F_S)

base.save(OUT)
print("wrote", OUT, base.size)

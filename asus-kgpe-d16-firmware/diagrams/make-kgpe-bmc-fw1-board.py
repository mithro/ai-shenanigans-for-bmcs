# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Generate kgpe-d16-bmc-fw1-board.png — an annotated board photo of BMC_FW1.

Takes the ASUS KGPE-D16 top photo from the Vikings wiki, extracts the left/bottom
section, rotates it 90 deg CCW (so the PCIe/PCI slots stand vertical with the
board's rear/bracket edge along the bottom), and annotates the BMC_FW1 2x7 socket
with its per-pin signals. In this orientation pin 1 is bottom-left, odd pins are
the left column and even pins the right column (both bottom -> top) — matching
diagrams/kgpe-d16-bmc-fw1-vertical.svg.

BMC_FW1 pixel coords were read off zoomed crops of the source photo.

Run:  uv run make-kgpe-bmc-fw1-board.py
"""

import io
import urllib.request

from PIL import Image, ImageDraw, ImageFont

SRC = "https://wiki.vikings.net/_media/hardware:asus_kgpe-d16.jpg"
OUT = "kgpe-d16-bmc-fw1-board.png"

raw = urllib.request.urlopen(SRC).read()  # noqa: S310 (public wiki asset)
img = Image.open(io.BytesIO(raw)).convert("RGB")

# left/bottom crop -> 90 deg CCW -> 2.5x
crop = img.crop((0, 1500, 780, 2016))
base = crop.transpose(Image.ROTATE_90)
SCALE = 2.5
base = base.resize((int(base.width * SCALE), int(base.height * SCALE)), Image.LANCZOS)
d = ImageDraw.Draw(base)


def font(sz, bold=True):
    n = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{n}", sz)
    except OSError:
        return ImageFont.load_default()


RED, BLUE, GREEN, ORANGE, BLACK, GREY, WHITE = (
    (205, 25, 25), (0, 70, 190), (0, 130, 50), (210, 120, 0),
    (10, 10, 10), (110, 110, 110), (255, 255, 255),
)
F_H, F_B, F_S = font(26), font(23), font(20)


def tw(t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0]


# ---- BMC_FW1 header geometry (rotated+scaled frame) ----
HX0, HY0, HX1, HY1 = 663, 1345, 734, 1556
d.rectangle((HX0, HY0, HX1, HY1), outline=RED, width=4)
row_y = [1538 - i * 29.3 for i in range(7)]      # bottom (1/2) -> top (13/14)
odd_x = 682

sig = {
    1: ("MOSI", RED), 2: ("+3V3", GREY), 3: ("IKVMEN#", ORANGE), 4: ("CS2", BLACK),
    5: ("NC", GREY), 6: ("MISO", RED), 7: ("PRESENT#", ORANGE), 8: ("SCK", RED),
    9: ("NC", GREY), 10: ("SOLEN#", ORANGE), 11: ("NC", GREY), 12: ("CS0", RED),
    13: ("GND", GREEN), 14: ("NC", GREY),
}


def tag(x, y, txt, col, f=F_B):
    w = tw(txt, f)
    d.rectangle((x - 3, y - 3, x + w + 5, y + f.size + 3), fill=WHITE, outline=col, width=2)
    d.text((x + 1, y), txt, fill=col, font=f)


d.ellipse((odd_x - 9, row_y[0] - 9, odd_x + 9, row_y[0] + 9), outline=RED, width=4)
tag(HX0 - 44, int(row_y[0]) - 12, "1", RED)
tag(HX0 - 52, int(row_y[6]) - 12, "13", BLACK, F_S)

# ---- signal legend, rows aligned to the physical header rows ----
title = "BMC_FW1 — 2×7 socket"
foots = ["odd = left col · even = right", "pin 1 ● at bottom-left"]
rows = [(f"{2*i+1:>2} {sig[2*i+1][0]}", sig[2*i+1][1],
         f"{2*i+2:>2} {sig[2*i+2][0]}", sig[2*i+2][1]) for i in range(7)]
lx, pad, col2_dx = 812, 14, 172
content_w = max(tw(title, F_H),
                col2_dx + max(tw(r[2], F_B) for r in rows),
                max(tw(f, F_S) for f in foots))
title_y = int(row_y[6]) - 44
foot_y0 = int(row_y[0]) + 30
d.rectangle((lx - pad, title_y - 8, lx + content_w + pad, foot_y0 + 2 * (F_S.size + 6) + 6),
            fill=WHITE, outline=RED, width=3)
d.text((lx, title_y), title, fill=RED, font=F_H)
for (t1, c1, t2, c2), y in zip(rows, row_y):
    d.line((HX1 + 2, y, lx - pad, y), fill=GREY, width=2)
    d.text((lx, y - 14), t1, fill=c1, font=F_B)
    d.text((lx + col2_dx, y - 14), t2, fill=c2, font=F_B)
for k, f in enumerate(foots):
    d.text((lx, foot_y0 + k * (F_S.size + 6)), f, fill=BLACK, font=F_S)

# ---- orientation note + title strip ----
onote = "PCIe/PCI slots vertical · rear (bracket) edge along the bottom"
d.rectangle((30, base.height - 46, 40 + tw(onote, F_S) + 20, base.height - 8),
            fill=WHITE, outline=BLUE, width=2)
d.text((44, base.height - 42), onote, fill=BLUE, font=F_S)
d.rectangle((0, 0, base.width, 46), fill=WHITE)
d.text((12, 8), "ASUS KGPE-D16 — BMC_FW1 BMC SPI boot-flash socket (signals)",
       fill=BLACK, font=F_H)

base.save(OUT)
print("wrote", OUT, base.size)

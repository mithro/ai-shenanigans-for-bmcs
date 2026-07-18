# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Regenerate ulx3s-spispy-j1-annotated.png.

Annotates the ULX3S v3.0.3 top-view photo (from the open-source-hardware
emard/ulx3s repo) with the spispy BMC-flash-emulation pins on header J1:
GP7=CS#, GP8=SCK, GP9=MOSI, GP10=MISO, plus the adjacent GND pair (schematic
pins 21/22).

Every text label is drawn inside a white box that is *measured to fit the text*
(so nothing overflows and every label is readable even where it sits over the
board). Pin-row y-coordinates were read off a 5x grid overlay of the photo
(pin7 approx y635 ... pin10 approx y755; pad columns approx x256 / x296).

Run:  uv run make-ulx3s-spispy-annotated.py
"""

import io
import urllib.request

from PIL import Image, ImageDraw, ImageFont

BASE_URL = "https://raw.githubusercontent.com/emard/ulx3s/master/pic/ULX3S_v303_top.png"
OUT = "ulx3s-spispy-j1-annotated.png"

raw = urllib.request.urlopen(BASE_URL).read()  # noqa: S310 (trusted OSHW repo)
img = Image.open(io.BytesIO(raw)).convert("RGB")
d = ImageDraw.Draw(img)


def font(sz, bold=True):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", sz)
    except OSError:
        return ImageFont.load_default()


RED, BLUE, GREEN, BLACK, WHITE = (
    (200, 25, 25), (0, 70, 190), (0, 120, 45), (10, 10, 10), (255, 255, 255),
)
F_TITLE, F_H, F_BODY, F_SM = font(30), font(27), font(24), font(21)


def text_w(text, fnt):
    b = d.textbbox((0, 0), text, font=fnt)
    return b[2] - b[0]


def chip(x, y, lines, border, anchor="tl", pad=11, gap=8, lw=3):
    """Draw a white box sized to fit `lines` = [(text, font, color), ...].

    `anchor` places (x, y) at the top-left ('tl') or top-right ('tr') corner.
    Returns the box rect (x0, y0, x1, y1) so leader lines can attach.
    """
    w = max(text_w(t, f) for t, f, _ in lines) + 2 * pad
    h = sum(f.size for _, f, _ in lines) + gap * (len(lines) - 1) + 2 * pad
    x0 = x - w if anchor == "tr" else x
    d.rectangle((x0, y, x0 + w, y + h), fill=WHITE, outline=border, width=lw)
    cy = y + pad
    for t, f, c in lines:
        d.text((x0 + pad, cy), t, fill=c, font=f)
        cy += f.size + gap
    return (x0, y, x0 + w, y + h)


def arrow(p0, p1, color, width=4, head=14):
    """Line from p0 to p1 with a filled triangular arrowhead at p1."""
    import math

    d.line([p0, p1], fill=color, width=width)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    left = (p1[0] - head * math.cos(ang - 0.5), p1[1] - head * math.sin(ang - 0.5))
    right = (p1[0] - head * math.cos(ang + 0.5), p1[1] - head * math.sin(ang + 0.5))
    d.polygon([p1, left, right], fill=color)


# ---- highlight boxes on the pins (both pad columns) ----
spi_box = (238, 616, 318, 774)   # pins 7..10
gnd_box = (238, 582, 318, 615)   # GND pair 21/22 (square pads above pin 7)
d.rectangle(spi_box, outline=RED, width=5)
d.rectangle(gnd_box, outline=GREEN, width=4)

# ---- SPI callout chip (left margin) + arrow to the red box ----
spi_chip = chip(8, 596, [
    ("SPI → BMC_FW1", F_H, RED),
    ("GP7  = CS#", F_BODY, BLACK),
    ("GP8  = SCK", F_BODY, BLACK),
    ("GP9  = MOSI", F_BODY, BLACK),
    ("GP10 = MISO", F_BODY, BLACK),
], RED)
arrow((spi_chip[2], (spi_box[1] + spi_box[3]) // 2),
      (spi_box[0], (spi_box[1] + spi_box[3]) // 2), RED)

# ---- GND chip (left margin) + arrow to the green box ----
gnd_chip = chip(8, 520, [("GND", F_BODY, GREEN)], GREEN)
arrow((gnd_chip[2], (gnd_box[1] + gnd_box[3]) // 2),
      (gnd_box[0], (gnd_box[1] + gnd_box[3]) // 2), GREEN, width=3)

# ---- "wire the GP (+) column" note, below the SPI chip ----
chip(8, spi_chip[3] + 10, [("wire the GP (“+”) column", F_SM, BLACK)], BLACK, lw=2)

# ---- J1 / J2 header labels (margins) + arrows to the headers ----
j1 = chip(12, 300, [("J1", F_TITLE, BLUE), ("GP0–13", F_SM, BLUE)], BLUE)
arrow((j1[2], 330), (250, 345), BLUE, width=3)
j2 = chip(1844, 296, [("J2", F_TITLE, BLUE), ("GP14–27", F_SM, BLUE),
                      ("debug only", F_SM, BLUE)], BLUE, anchor="tr")
arrow((j2[0], 336), (1628, 348), BLUE, width=3)

# ---- USB port labels (top margin) + leader lines to the connectors ----
u1 = chip(360, 92, [("US1 · FTDI", F_SM, BLACK),
                    ("prog, ttyUSB0", F_SM, BLACK)], BLACK, lw=2)
arrow(((u1[0] + u1[2]) // 2, u1[3]), (486, 236), BLACK, width=3)
u2 = chip(1236, 92, [("US2 · FPGA USB", F_SM, BLACK),
                     ("ctrl, ttyACM", F_SM, BLACK)], BLACK, lw=2)
arrow(((u2[0] + u2[2]) // 2, u2[3]), (1380, 236), BLACK, width=3)

# ---- title strip ----
d.rectangle((0, 0, img.width, 46), fill=WHITE)
d.text((12, 8), "ULX3S (12F, v3.0x, top) — spispy BMC-flash-emulation pins on header J1",
       fill=BLACK, font=F_H)

img.save(OUT)
print("wrote", OUT, img.size)

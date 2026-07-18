# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Regenerate ulx3s-spispy-j1-annotated.png.

Annotates the ULX3S v3.0.3 top-view photo (from the open-source-hardware
emard/ulx3s repo) with the spispy BMC-flash-emulation pins on header J1:
GP7=CS#, GP8=SCK, GP9=MOSI, GP10=MISO, plus the adjacent GND pair (schematic
pins 21/22). Pin-row y-coordinates were read off a 5x grid overlay of the photo
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
    (210, 30, 30), (0, 80, 200), (0, 130, 55), (15, 15, 15), (255, 255, 255),
)
f_title, f_big, f_med, f_sm, f_tiny = (font(30), font(34), font(28), font(25), font(21))

spi_box = (240, 616, 316, 772)   # pins 7..10 (both pad columns)
gnd_box = (240, 583, 316, 615)   # GND pair 21/22 (square 'H' pads above pin 7)
d.rectangle(spi_box, outline=RED, width=5)
d.rectangle(gnd_box, outline=GREEN, width=4)

px0, py0, px1 = 6, 600, 232
d.rectangle((px0, py0, px1, py0 + 232), fill=WHITE, outline=RED, width=3)
d.text((px0 + 10, py0 + 6), "SPI → BMC_FW1", fill=RED, font=f_med)
for i, t in enumerate(["GP7  = CS#", "GP8  = SCK", "GP9  = MOSI", "GP10 = MISO"]):
    d.text((px0 + 14, py0 + 44 + i * 30), t, fill=BLACK, font=f_sm)
d.text((px0 + 10, py0 + 170), "wire the GP ('+') column", fill=BLACK, font=f_tiny)
d.text((px0 + 10, py0 + 200), "GND = green box", fill=GREEN, font=f_tiny)
ay = (spi_box[1] + spi_box[3]) // 2
d.line((px1, py0 + 60, spi_box[0], ay), fill=RED, width=4)
d.polygon([(spi_box[0], ay), (spi_box[0] - 15, ay - 9), (spi_box[0] - 15, ay + 9)], fill=RED)

d.text((238, 256), "J1", fill=BLUE, font=f_big)
d.text((238, 292), "GP0–13", fill=BLUE, font=f_tiny)
d.text((1690, 250), "J2", fill=BLUE, font=f_big)
d.text((1636, 288), "GP14–27", fill=BLUE, font=f_tiny)
d.text((1560, 314), "debug taps only", fill=BLUE, font=f_tiny)
d.text((402, 198), "US1 (FTDI/prog → ttyUSB0)", fill=BLACK, font=f_tiny)
d.text((1216, 198), "US2 (FPGA USB → ttyACM)", fill=BLACK, font=f_tiny)

d.rectangle((0, 0, img.width, 42), fill=WHITE)
d.text((10, 7), "ULX3S (12F, v3.0x, top) — spispy BMC-flash-emulation pins on header J1",
       fill=BLACK, font=f_title)

img.save(OUT)
print("wrote", OUT, img.size)

# /// script
# requires-python = ">=3.11"
# ///
"""Generate kgpe-d16-bmc-fw1.svg.

BMC_FW1 pinout drawn to match the ASUS KGPE-D16 manual (§2.7.2, "BMC header"):
a 2x7 socket with **pin 1 at the bottom-left** and **pin 14 keyed (filled) at the
top-right**. Standard column-pair numbering — odd pins on the bottom row, even on
the top:

    top row  (L->R):   2    4    6    8   10   12   14(key)
    bot row  (L->R):   1    3    5    7    9   11   13

Signals are the schematic nets (../BMC-CONNECTORS.md). Colour coding +
theme-aware styling preserved. This is the canonical BMC_FW1 pinout used by both
BMC-CONNECTORS.md and the ULX3S/spispy wiring doc; it replaces the earlier
version that had pin 1 top-left (vertically flipped from the manual).

Run:  uv run make-bmc-fw1-svg.py
"""

# Standard 2x7 column-pair numbering with pin 1 at the bottom-left (per the ASUS
# manual): odd pins on the BOTTOM row, even pins on the TOP row, pin 14 (top-right)
# is the keyed position. col 0 = left ... col 6 = right.
KEY = "KEY"
TOP = [(2, "+3V3", "green"), (4, "SPICS#2", "blue"), (6, "SPIDI", "blue"),
       (8, "SPICLK", "blue"), (10, "SOLEN#", "gold"), (12, "SPICS#0", "blue"),
       (KEY, "", "muted")]
BOT = [(1, "SPIDO", "blue"), (3, "IKVMEN#", "gold"), (5, "NC", "muted"),
       (7, "PRESENT#", "gold"), (9, "NC", "muted"), (11, "NC", "muted"),
       (13, "GND", "muted")]

X0, DX = 96, 60          # first column x, column pitch
Y_TOP, Y_BOT = 250, 298  # pin row y
LBL_TOP, LBL_BOT = 208, 340

def col_x(c):
    return X0 + c * DX

parts = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 560" role="img"'
    ' aria-label="BMC_FW1 — BMC SPI firmware socket (manual-accurate: pin 1 bottom-left)"'
    ' preserveAspectRatio="xMidYMid meet">',
    '  <title>BMC_FW1 — BMC SPI firmware socket (pin 1 bottom-left, top-left keyed)</title>',
    '  <style>',
    "    text{font-family:ui-monospace,'DejaVu Sans Mono',monospace;fill:var(--ink);}",
    '    svg{--ink:#1a1a1a;--muted:#666;--box:#f4f4f4;--panel:#ececec;',
    '        --blue:#2d6cdf;--green:#1a8a5a;--gold:#b8860b;--red:#c0392b;}',
    '    @media (prefers-color-scheme: dark){',
    '      svg{--ink:#e6e6e6;--muted:#a8a8a8;--box:#2a2a2a;--panel:#232323;',
    '          --blue:#5b9bff;--green:#3cc98a;--gold:#e0b050;--red:#e74c3c;}',
    '    }',
    '    .t{font-size:19px;font-weight:700;}',
    '    .st{font-size:12px;fill:var(--muted);}',
    '    .sig{font-size:12.5px;font-weight:600;}',
    '    .pn{font-size:11px;font-weight:700;}',
    '    .m{font-size:11px;fill:var(--muted);}',
    '    .leg{font-size:12px;}',
    '    .board{fill:var(--panel);stroke:var(--ink);stroke-width:2;}',
    '  </style>',
    '<text class="t" x="24" y="34">BMC_FW1 — BMC SPI firmware / ASMB4 slot</text>',
    '<text class="st" x="24" y="55">socketed SPI flash + straps · 2×7 · '
    'pin 1 = square pad (bottom-left) · pin 14 keyed (top-right)</text>',
    f'<rect class="board" x="{X0-30}" y="224" width="{6*DX+60}" height="100" rx="10"/>',
]

def pin(cx, cy, pinno, sig, col, label_y, anchor):
    c = f"var(--{col})"
    out = []
    if pinno == KEY:  # filled/keyed position (pin 14)
        out.append(
            f'<rect x="{cx-13}" y="{cy-13}" width="26" height="26" rx="3"'
            f' fill="var(--ink)" stroke="var(--ink)" stroke-width="2"/>'
            f'<text class="pn" x="{cx}" y="{cy}" text-anchor="middle"'
            f' dominant-baseline="central" fill="var(--box)">14</text>'
            f'<text class="m" transform="rotate(-90 {cx} {label_y})" x="{cx}"'
            f' y="{label_y}" text-anchor="{anchor}" dominant-baseline="central">key</text>')
        return "".join(out)
    if pinno == 1:    # square pad marks pin 1
        out.append(
            f'<rect x="{cx-13}" y="{cy-13}" width="26" height="26" rx="3"'
            f' fill="var(--box)" stroke="var(--red)" stroke-width="2.8"/>'
            f'<text class="pn" x="{cx}" y="{cy}" text-anchor="middle"'
            f' dominant-baseline="central" fill="var(--red)">1</text>')
        c = "var(--blue)"
    else:
        out.append(
            f'<circle cx="{cx}" cy="{cy}" r="12" fill="var(--box)" stroke="{c}"'
            f' stroke-width="2.4"/><text class="pn" x="{cx}" y="{cy}"'
            f' text-anchor="middle" dominant-baseline="central" fill="{c}">{pinno}</text>')
    out.append(
        f'<text class="sig" transform="rotate(-90 {cx} {label_y})" x="{cx}"'
        f' y="{label_y}" text-anchor="{anchor}" dominant-baseline="central"'
        f' fill="{c}">{sig}</text>')
    return "".join(out)

for c, (pn, sig, col) in enumerate(TOP):
    parts.append(pin(col_x(c), Y_TOP, pn, sig, col, LBL_TOP, "start"))
for c, (pn, sig, col) in enumerate(BOT):
    parts.append(pin(col_x(c), Y_BOT, pn, sig, col, LBL_BOT, "end"))

parts.append(
    '<circle cx="28" cy="512" r="7" fill="var(--box)" stroke="var(--blue)"'
    ' stroke-width="2.2"/><text class="leg" x="42" y="516">Signal / data</text>'
    '<circle cx="152" cy="512" r="7" fill="var(--box)" stroke="var(--green)"'
    ' stroke-width="2.2"/><text class="leg" x="166" y="516">Power</text>'
    '<circle cx="228" cy="512" r="7" fill="var(--box)" stroke="var(--gold)"'
    ' stroke-width="2.2"/><text class="leg" x="242" y="516">Strap</text>'
    '<circle cx="330" cy="512" r="7" fill="var(--box)" stroke="var(--muted)"'
    ' stroke-width="2.2"/><text class="leg" x="344" y="516">NC / GND</text>'
    '<rect x="452" y="505" width="14" height="14" fill="var(--ink)"/>'
    '<text class="leg" x="472" y="516">Keyed (no pin)</text>')
parts.append(
    '<text class="m" x="596" y="540" text-anchor="end">'
    'odd pins = bottom row (1→13) · even = top row (2→14) · pin 14 (top-right) keyed</text>')
parts.append('</svg>')

svg = "\n".join(parts) + "\n"
with open("kgpe-d16-bmc-fw1.svg", "w") as f:
    f.write(svg)
print("wrote kgpe-d16-bmc-fw1.svg")

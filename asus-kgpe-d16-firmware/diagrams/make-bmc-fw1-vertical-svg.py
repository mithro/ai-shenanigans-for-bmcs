# /// script
# requires-python = ">=3.11"
# ///
"""Generate kgpe-d16-bmc-fw1-vertical.svg.

A vertical rendering of the BMC_FW1 2x7 socket that matches the orientation of
the annotated board photo (kgpe-d16-bmc-fw1-board.png): the board is rotated so
pin 1 is at the BOTTOM-LEFT, the odd pins (1,3,..13) form the LEFT column and the
even pins (2,4,..14) the RIGHT column, both running bottom -> top.

This is the rotated companion to schematic-wiring/diagrams/kgpe-d16-bmc-fw1.svg
(the horizontal, pin-1-top-left version used by BMC-CONNECTORS.md); that file is
left unchanged. Colour coding and theme-aware styling are preserved.

Run:  uv run make-bmc-fw1-vertical-svg.py
"""

# pin -> (short signal, colour-var, is_square_pad)
PINS = {
    1: ("SPIDO", "blue"), 2: ("+3V3", "green"), 3: ("IKVMEN#", "gold"),
    4: ("SPICS#2", "blue"), 5: ("NC", "muted"), 6: ("SPIDI", "blue"),
    7: ("PRESENT#", "gold"), 8: ("SPICLK", "blue"), 9: ("NC", "muted"),
    10: ("SOLEN#", "gold"), 11: ("NC", "muted"), 12: ("SPICS#0", "blue"),
    13: ("GND", "muted"), 14: ("NC", "muted"),
}

ODD_X, EVEN_X = 208, 268          # left column = odd, right column = even
Y1 = 442                          # pin 1/2 row (bottom)
PITCH = 44                        # row spacing (bottom -> top)
LBL_L, LBL_R = 176, 300           # odd label (end-anchored) / even label (start)

def cvar(name):
    return f"var(--{name})"

def row_y(i):                     # i = 0 (pins 1/2, bottom) .. 6 (pins 13/14, top)
    return Y1 - i * PITCH

parts = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 560" role="img"'
    ' aria-label="BMC_FW1 — BMC SPI firmware socket (rotated to match board photo)"'
    ' preserveAspectRatio="xMidYMid meet">',
    '  <title>BMC_FW1 — BMC SPI firmware socket (pin 1 bottom-left)</title>',
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
    '<text class="st" x="24" y="55">socketed SPI flash + feature straps · 2×7</text>',
    '<text class="st" x="24" y="73">pin 1 = red square (bottom-left) ·'
    ' odd = left col / even = right</text>',
    # board body enclosing both columns / all rows
    f'<rect class="board" x="182" y="{row_y(6)-28}" width="112"'
    f' height="{Y1 - row_y(6) + 56}" rx="10"/>',
]

for pin, (sig, col) in PINS.items():
    i = (pin - 1) // 2
    y = row_y(i)
    is_odd = pin % 2 == 1
    x = ODD_X if is_odd else EVEN_X
    c = cvar(col)
    if pin == 1:  # square pad marks pin 1
        parts.append(
            f'<rect x="{x-13}" y="{y-13}" width="26" height="26" rx="3"'
            f' fill="var(--box)" stroke="var(--red)" stroke-width="2.8"/>'
            f'<text class="pn" x="{x}" y="{y}" text-anchor="middle"'
            f' dominant-baseline="central" fill="var(--red)">1</text>')
    else:
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="12" fill="var(--box)" stroke="{c}"'
            f' stroke-width="2.4"/><text class="pn" x="{x}" y="{y}"'
            f' text-anchor="middle" dominant-baseline="central" fill="{c}">{pin}</text>')
    if is_odd:
        parts.append(
            f'<text class="sig" x="{LBL_L}" y="{y}" text-anchor="end"'
            f' dominant-baseline="central" fill="{c}">{sig}</text>')
    else:
        parts.append(
            f'<text class="sig" x="{LBL_R}" y="{y}" text-anchor="start"'
            f' dominant-baseline="central" fill="{c}">{sig}</text>')

# legend (spaced to fit within the viewBox width)
parts.append(
    '<circle cx="28" cy="536" r="7" fill="var(--box)" stroke="var(--blue)"'
    ' stroke-width="2.2"/><text class="leg" x="42" y="540">Signal / data</text>'
    '<circle cx="152" cy="536" r="7" fill="var(--box)" stroke="var(--green)"'
    ' stroke-width="2.2"/><text class="leg" x="166" y="540">Power</text>'
    '<circle cx="232" cy="536" r="7" fill="var(--box)" stroke="var(--gold)"'
    ' stroke-width="2.2"/><text class="leg" x="246" y="540">Strap / config</text>'
    '<circle cx="366" cy="536" r="7" fill="var(--box)" stroke="var(--muted)"'
    ' stroke-width="2.2"/><text class="leg" x="380" y="540">No-connect / GND</text>')
parts.append('</svg>')

svg = "\n".join(parts) + "\n"
with open("kgpe-d16-bmc-fw1-vertical.svg", "w") as f:
    f.write(svg)
print("wrote kgpe-d16-bmc-fw1-vertical.svg")

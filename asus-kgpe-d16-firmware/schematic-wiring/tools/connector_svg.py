#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Generate SVG pinout diagrams for the BMC connectors/headers.

Emits one themed SVG per connector into ../diagrams/, in the same visual style
as the bmc-open-firmware-docs _static/diagrams set: CSS-variable light/dark
theming, a board rectangle, circular pads with a red square pin-1, function
colour-coding, a legend and notes.

Layouts:
  row   - a single horizontal row (1xN headers, jumpers)
  dual  - a two-row 0.1" header (odd pins top, even pins bottom, pin 1 top-left)
  vga   - a VGA HD-15 D-sub (3 offset rows of 5)

Pin numbers and signals are authoritative (from the netlist). The physical
row/column arrangement follows the connector's standard convention; verify pin 1
against the board silkscreen.

Usage:  uv run connector_svg.py            # writes all SVGs to ../diagrams/
"""
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "diagrams")

# ---- colour class per pin function ----
# cls -> (pad stroke var, text var, legend label)
CLASS = {
    "pwr":   ("--green",  "--green",  "Power"),
    "gnd":   ("--muted",  "--muted",  "Ground"),
    "data":  ("--blue",   "--blue",   "Signal / data"),
    "test":  ("--purple", "--purple", "JTAG / test"),
    "strap": ("--gold",   "--gold",   "Strap / config"),
    "nc":    ("--muted",  "--muted",  "No-connect"),
}

STYLE = """  <style>
    text{font-family:ui-monospace,'DejaVu Sans Mono',monospace;fill:var(--ink);}
    svg{--ink:#1a1a1a;--muted:#666;--box:#f4f4f4;--panel:#ececec;
        --blue:#2d6cdf;--green:#1a8a5a;--gold:#b8860b;--purple:#7d3cc0;--red:#c0392b;}
    @media (prefers-color-scheme: dark){
      svg{--ink:#e6e6e6;--muted:#a8a8a8;--box:#2a2a2a;--panel:#232323;
          --blue:#5b9bff;--green:#3cc98a;--gold:#e0b050;--purple:#b98cf0;--red:#e74c3c;}
    }
    .t{font-size:19px;font-weight:700;}
    .st{font-size:12px;fill:var(--muted);}
    .sig{font-size:12.5px;font-weight:600;}
    .m{font-size:11px;fill:var(--muted);}
    .pn{font-size:11px;font-weight:700;}
    .leg{font-size:12px;}
    .board{fill:var(--panel);stroke:var(--ink);stroke-width:2;}
  </style>"""


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pad(cx, cy, cls, num, r=13):
    col = CLASS[cls][0]
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="var(--box)" '
            f'stroke="var({col})" stroke-width="2.4"/>'
            f'<text class="pn" x="{cx}" y="{cy}" text-anchor="middle" '
            f'dominant-baseline="central" fill="var({col})">{num}</text>')


def pin1square(cx, cy, num, cls):
    col = CLASS[cls][0]
    return (f'<rect x="{cx-13}" y="{cy-13}" width="26" height="26" rx="3" '
            f'fill="var(--box)" stroke="var(--red)" stroke-width="2.8"/>'
            f'<text class="pn" x="{cx}" y="{cy}" text-anchor="middle" '
            f'dominant-baseline="central" fill="var(--red)">{num}</text>')


def label(cx, y, sig, sub, cls, anchor="middle"):
    tcol = CLASS[cls][1]
    out = (f'<text class="sig" x="{cx}" y="{y}" text-anchor="{anchor}" '
           f'fill="var({tcol})">{esc(sig)}</text>')
    if sub:
        out += (f'<text class="m" x="{cx}" y="{y+15}" text-anchor="{anchor}">'
                f'{esc(sub)}</text>')
    return out


def legend(x, y, classes):
    out = []
    for cls in classes:
        col, _, lab = CLASS[cls]
        out.append(f'<circle cx="{x}" cy="{y}" r="7" fill="var(--box)" '
                   f'stroke="var({col})" stroke-width="2.2"/>')
        out.append(f'<text class="leg" x="{x+14}" y="{y+4}">{lab}</text>')
        x += 22 + len(lab) * 7.5
    return "".join(out), x


def svg_open(w, h, title, sub):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(title)}" '
            f'preserveAspectRatio="xMidYMid meet">\n'
            f'  <title>{esc(title)}</title>\n{STYLE}\n'
            f'<text class="t" x="24" y="34">{esc(title)}</text>\n'
            f'<text class="st" x="24" y="55">{esc(sub)}</text>')


def render_row(spec):
    pins = spec["pins"]
    n = len(pins)
    step = 118
    x0 = 90
    w = max(560, x0 + step * (n - 1) + 90)
    h = 300
    parts = [svg_open(w, h, spec["title"], spec["sub"])]
    y = 150
    parts.append(f'<rect class="board" x="{x0-42}" y="{y-28}" '
                 f'width="{step*(n-1)+84}" height="56" rx="10"/>')
    used = []
    for i, p in enumerate(pins):
        cx = x0 + i * step
        cls = p["cls"]
        if cls not in used:
            used.append(cls)
        parts.append(pin1square(cx, y, p["n"], cls) if i == 0
                     else pad(cx, y, cls, p["n"]))
        parts.append(label(cx, y + 45, p["sig"], p.get("sub", ""), cls))
    leg, _ = legend(28, h - 30, used)
    parts.append(leg)
    parts.append('</svg>')
    return "\n".join(parts)


def vlabel(cx, y, sig, cls, up):
    """A signal label rotated to read vertically, so long names never collide."""
    tcol = CLASS[cls][1]
    anchor = "start" if up else "end"
    return (f'<text class="sig" transform="rotate(-90 {cx} {y})" x="{cx}" y="{y}" '
            f'text-anchor="{anchor}" dominant-baseline="central" '
            f'fill="var({tcol})">{esc(sig)}</text>')


def render_dual(spec):
    pins = {p["n"]: p for p in spec["pins"]}
    cols = (max(pins) + 1) // 2
    step = 60
    x0 = 96
    w = max(620, x0 + step * (cols - 1) + 130)
    ytop, ybot = 236, 284
    h = 500
    parts = [svg_open(w, h, spec["title"], spec["sub"])]
    parts.append(f'<rect class="board" x="{x0-30}" y="{ytop-26}" '
                 f'width="{step*(cols-1)+60}" height="{ybot-ytop+52}" rx="10"/>')
    used = []
    for c in range(cols):
        cx = x0 + c * step
        top, bot = 2 * c + 1, 2 * c + 2   # pin 1 top-left, 2 directly below
        for num, cy, up in ((top, ytop, True), (bot, ybot, False)):
            p = pins.get(num)
            if not p:
                continue
            cls = p["cls"]
            if cls not in used:
                used.append(cls)
            parts.append(pin1square(cx, cy, num, cls) if num == 1
                         else pad(cx, cy, cls, num, r=12))
            parts.append(vlabel(cx, ytop - 26 if up else ybot + 26, p["sig"], cls, up))
    leg, _ = legend(28, h - 44, used)
    parts.append(leg)
    parts.append(f'<text class="m" x="{w-24}" y="{h-20}" text-anchor="end">'
                 f'odd pins top row · even bottom · pin 1 = square pad</text>')
    parts.append('</svg>')
    return "\n".join(parts)


def render_vga(spec):
    pins = {p["n"]: p for p in spec["pins"]}
    w, h = 640, 360
    parts = [svg_open(w, h, spec["title"], spec["sub"])]
    # D-sub HD15 shell (trapezoid), 3 rows of 5, each row offset
    parts.append('<path class="board" d="M 150 120 L 520 120 L 500 250 '
                 'L 170 250 Z"/>')
    rows = [(range(1, 6), 150, 8), (range(6, 11), 178, 4), (range(11, 16), 206, 0)]
    xstep, x0 = 74, 195
    used = []
    for nums, cy, xoff in rows:
        for i, num in enumerate(nums):
            cx = x0 + i * xstep + (xoff if cy == 150 else (xoff if cy == 178 else 0))
            cx = x0 + i * xstep + xoff
            p = pins[num]
            cls = p["cls"]
            if cls not in used:
                used.append(cls)
            parts.append(pin1square(cx, cy, num, cls) if num == 1
                         else pad(cx, cy, cls, num, r=11))
    # signal labels in a two-column legend-ish list on the right/below
    ly = 292
    col_x = [24, 240, 456]
    order = list(range(1, 16))
    for idx, num in enumerate(order):
        p = pins[num]
        cx = col_x[idx % 3]
        row = idx // 3
        yy = ly + row * 15
        tcol = CLASS[p["cls"]][1]
        parts.append(f'<text class="m" x="{cx}" y="{yy}">'
                     f'<tspan fill="var({tcol})" font-weight="700">{num:>2} '
                     f'{esc(p["sig"])}</tspan> {esc(p.get("sub",""))}</text>')
    parts.append('</svg>')
    return "\n".join(parts)


RENDER = {"row": render_row, "dual": render_dual, "vga": render_vga}


# ---------------------------------------------------------------------------
# Connector specs (pin -> signal / sub-label / colour class). Data from the
# KGPE-D16 netlist; see BMC-CONNECTORS.md.
# ---------------------------------------------------------------------------
def P(n, sig, cls, sub=""):
    return {"n": n, "sig": sig, "cls": cls, "sub": sub}

CONNECTORS = {
"kgpe-d16-vga1": {"layout": "vga",
  "title": "VGA1 — VGA output (HD-15)",
  "sub": "AST2050 integrated video · RGB DAC + DDC I²C + H/V sync",
  "pins": [
    P(1,"RED","data","BMC E1"), P(2,"GREEN","data","BMC D1"), P(3,"BLUE","data","BMC C1"),
    P(4,"NC","nc","ID2"), P(5,"GND","gnd",""),
    P(6,"R-GND","gnd",""), P(7,"G-GND","gnd",""), P(8,"B-GND","gnd",""),
    P(9,"+5V","pwr","DDC pwr"), P(10,"GND","gnd","sync"),
    P(11,"NC","nc","ID0"), P(12,"DDC-DAT","data","BMC B2"),
    P(13,"HSYNC","data","BMC U2 · QU6"), P(14,"VSYNC","data","BMC R4 · QU6"),
    P(15,"DDC-CLK","data","BMC B1")]},

"kgpe-d16-ast-uart1": {"layout": "row",
  "title": "AST_UART1 — BMC serial console",
  "sub": "AST2050 UART2 · 1×4 · standby-powered",
  "pins": [P(1,"+5VSB","pwr","standby"), P(2,"BMC TXD","data","AST_TXD2 · U21"),
           P(3,"BMC RXD","data","AST_RXD2 · U20"), P(4,"GND","gnd","")]},

"kgpe-d16-psusmb1": {"layout": "row",
  "title": "PSUSMB1 — PSU SMBus",
  "sub": "BMC I²C1 · PSU telemetry (PMBus)",
  "pins": [P(1,"SCL","data","I2C1 · BMC B15"), P(2,"SDA","data","I2C1 · BMC A15"),
           P(3,"ALERT#","data","BMC B12"), P(4,"GND","gnd",""), P(5,"+3V3","pwr","")]},

"kgpe-d16-vga-sw1": {"layout": "row",
  "title": "VGA_SW1 — VGA reset-source jumper",
  "sub": "selects VGA/iKVM PCI reset source · 1×3",
  "pins": [P(1,"SB_PCI_RST#","data","chipset · BMC B10"),
           P(2,"AST_BRST#","data","BMC P21"), P(3,"GND","gnd","")]},

"kgpe-d16-ipmi-sel1": {"layout": "row",
  "title": "IPMI_SEL1 — IPMI enable jumper",
  "sub": "IPMI_SEL strap · 1×3",
  "pins": [P(1,"NC","nc","pull opt"), P(2,"IPMI_SEL","strap","BMC A8"),
           P(3,"opt","strap","")]},

"kgpe-d16-recovery1": {"layout": "row",
  "title": "RECOVERY1 — BIOS recovery jumper",
  "sub": "BIOS_RECOVERY# strap · 1×3",
  "pins": [P(1,"NC","nc","pull opt"), P(2,"BIOS_RECOVERY#","strap","BMC C9"),
           P(3,"GND","gnd","")]},

"kgpe-d16-ast-jtag1": {"layout": "dual",
  "title": "AST_JTAG1 — BMC ARM926 JTAG",
  "sub": "ARM 20-pin · odd = signal, even = GND",
  "pins": [P(1,"+3V3","pwr"), P(2,"+3V3","pwr"), P(3,"NTRST","test"), P(4,"GND","gnd"),
           P(5,"TDI","test"), P(6,"GND","gnd"), P(7,"TMS","test"), P(8,"GND","gnd"),
           P(9,"TCK","test"), P(10,"GND","gnd"), P(11,"RTCK","test"), P(12,"GND","gnd"),
           P(13,"TDO","test"), P(14,"GND","gnd"), P(15,"SRST#","test"), P(16,"GND","gnd"),
           P(17,"NC","nc"), P(18,"GND","gnd"), P(19,"NC","nc"), P(20,"GND","gnd")]},

"kgpe-d16-bmc-fw1": {"layout": "dual",
  "title": "BMC_FW1 — BMC SPI firmware / ASMB4 slot",
  "sub": "socketed SPI flash + feature straps · 2×7",
  "pins": [P(1,"SPIDO","data"), P(2,"+3V3","pwr"), P(3,"IKVMEN#","strap"),
           P(4,"SPICS#2","data"), P(5,"NC","nc"), P(6,"SPIDI","data"),
           P(7,"PRESENT#","strap"), P(8,"SPICLK","data"), P(9,"NC","nc"),
           P(10,"SOLEN#","strap"), P(11,"NC","nc"), P(12,"SPICS#0","data"),
           P(13,"GND","gnd")]},

"kgpe-d16-panel1": {"layout": "dual",
  "title": "PANEL1 — system front panel",
  "sub": "power/reset/LEDs · 2×10 (pin 5 keyed)",
  "pins": [P(1,"HDLED+","data"), P(2,"HDLED-","data"), P(3,"GND","gnd"), P(4,"NC","nc"),
           P(6,"PLED-","data"), P(7,"NMIBNT#","data"), P(8,"PLED+","data"),
           P(9,"GND","gnd"), P(10,"MLED","data"), P(11,"PWRBTN#","data"), P(12,"NC","nc"),
           P(13,"GND","gnd"), P(14,"+5V","pwr"), P(15,"NC","nc"), P(16,"GND","gnd"),
           P(17,"RESET#","data"), P(18,"GND","gnd"), P(19,"GND","gnd"), P(20,"SPKOUT","data")]},

"kgpe-d16-aux-panel1": {"layout": "dual",
  "title": "AUX_PANEL1 — auxiliary panel",
  "sub": "BMC locator LED/button · front I²C8 · LAN LEDs · 2×10",
  "pins": [P(1,"+5VSB","pwr"), P(2,"NC","nc"), P(3,"GND","gnd"), P(4,"I2C8SCL","data"),
           P(5,"CHASSIS#","data"), P(7,"GND","gnd"), P(8,"GND","gnd"),
           P(9,"LOCLED1","data"), P(10,"I2C8SDA","data"), P(11,"BMCLOC-LED#","data"),
           P(12,"NC","nc"), P(13,"BMCLOC-BTN#","data"), P(14,"LAN1LINK#","data"),
           P(15,"GND","gnd"), P(16,"LAN1ACT#","data"), P(17,"BMCLOC-LED#","data"),
           P(18,"LAN2ACT#","data"), P(19,"LOCLED2","data"), P(20,"LAN2LINK#","data")]},
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, spec in CONNECTORS.items():
        svg = RENDER[spec["layout"]](spec)
        path = os.path.join(OUT, name + ".svg")
        open(path, "w").write(svg + "\n")
        print("wrote", os.path.relpath(path, os.path.dirname(OUT)))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Generate I2C/SMBus/PMBus topology SVGs (one per bus + a board overview) in
the style of bmc-open-firmware-docs _static/diagrams/c410x-i2c-topology.svg.

A spec is a layered left-to-right tree:
  layers = [[node, ...], ...]   # columns, left = masters, right = leaf devices
  edges  = [(from_id, to_id), ...]
Each node = {"id","title","sub","cls"} with cls in CLASSES.
Layout is automatic (columns spaced left-to-right, nodes distributed vertically).

Usage:  uv run i2c_topology_svg.py     # writes all SVGs to ../diagrams/
"""
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "diagrams")

CLASSES = {  # cls -> stroke colour var, legend label
    "master": ("--ink",    "master (I2C controller)"),
    "sensor": ("--green",  "sensor"),
    "mux":    ("--gold",   "I2C mux / switch"),
    "gpio":   ("--purple", "GPIO expander"),
    "vr":     ("--blue",   "VR / PMBus"),
    "mem":    ("--ink",    "EEPROM / host / PSU"),
}

STYLE = """  <style>
    text{font-family:ui-monospace,'DejaVu Sans Mono',monospace;fill:var(--ink);}
    svg{--ink:#1a1a1a;--muted:#555;--box:#f4f4f4;--panel:#ececec;
        --blue:#2d6cdf;--green:#1a8a5a;--gold:#b8860b;--purple:#7d3cc0;--red:#c0392b;}
    @media (prefers-color-scheme: dark){
      svg{--ink:#e6e6e6;--muted:#a8a8a8;--box:#2a2a2a;--panel:#232323;
          --blue:#5b9bff;--green:#3cc98a;--gold:#e0b050;--purple:#b98cf0;--red:#e74c3c;}
    }
    .t{font-size:18px;font-weight:700;}
    .st{font-size:12px;fill:var(--muted);}
    .h{font-size:13px;font-weight:700;}
    .m{font-size:11.5px;fill:var(--muted);}
    .l{font-size:12px;}
    .box{fill:var(--box);stroke-width:1.8;}
    .wire{fill:none;stroke:var(--ink);stroke-width:1.4;}
    .fillink{fill:var(--ink);}
    .sw{stroke-width:1.8;fill:var(--box);}
  </style>
  <defs>
    <marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" class="fillink"/>
    </marker>
  </defs>"""


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(spec):
    layers = spec["layers"]
    edges = spec.get("edges", [])
    colw = spec.get("colw", [210] * len(layers))
    gap = 46
    top = 78
    boxh = 46
    vgap = 20
    # x of each column (left edge)
    xs = []
    x = 24
    for w in colw:
        xs.append(x)
        x += w + gap
    width = x - gap + 24
    # rows per column -> vertical positions (evenly distributed)
    maxn = max(len(c) for c in layers)
    height = top + maxn * (boxh + vgap) + 70
    pos = {}   # id -> (cx_left, cy_center, w)
    for ci, col in enumerate(layers):
        n = len(col)
        span = height - top - 60
        for ri, node in enumerate(col):
            cy = top + 20 + (span * (ri + 0.5) / n)
            pos[node["id"]] = (xs[ci], cy, colw[ci])
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           f'role="img" aria-label="{esc(spec["title"])}" preserveAspectRatio="xMidYMid meet">',
           f'  <title>{esc(spec["title"])}</title>', STYLE,
           f'<text class="t" x="24" y="34">{esc(spec["title"])}</text>',
           f'<text class="st" x="24" y="56">{esc(spec.get("sub",""))}</text>']
    # edges first (under boxes)
    for a, b in edges:
        ax, ay, aw = pos[a]
        bx, by, bw = pos[b]
        out.append(f'<line class="wire" x1="{ax+aw}" y1="{ay:.0f}" x2="{bx}" y2="{by:.0f}" marker-end="url(#arw)"/>')
    # boxes
    used = set()
    for col in layers:
        for node in col:
            cx, cy, w = pos[node["id"]]
            colvar = CLASSES[node["cls"]][0]
            used.add(node["cls"])
            y = cy - boxh / 2
            out.append(f'<rect class="box" stroke="var({colvar})" x="{cx}" y="{y:.0f}" width="{w}" height="{boxh}" rx="8"/>')
            out.append(f'<text class="h" x="{cx+12}" y="{cy-4:.0f}">{esc(node["title"])}</text>')
            if node.get("sub"):
                out.append(f'<text class="m" x="{cx+12}" y="{cy+13:.0f}">{esc(node["sub"])}</text>')
    # legend
    ly = height - 26
    out.append(f'<line class="wire" x1="24" y1="{ly-16}" x2="{width-24}" y2="{ly-16}"/>')
    lx = 24
    for cls in [c for c in CLASSES if c in used]:
        colvar, lab = CLASSES[cls]
        out.append(f'<rect class="sw" stroke="var({colvar})" x="{lx}" y="{ly-11}" width="16" height="13" rx="3"/>')
        out.append(f'<text class="l" x="{lx+22}" y="{ly}">{esc(lab)}</text>')
        lx += 40 + len(lab) * 7.2
    out.append('</svg>')
    return "\n".join(out)


def N(id, title, cls, sub=""):
    return {"id": id, "title": title, "cls": cls, "sub": sub}


# ---------------------------------------------------------------------------
# Per-bus specs (from the KGPE-D16 netlist; addresses are 7-bit datasheet defaults)
# ---------------------------------------------------------------------------
SPECS = {

"kgpe-d16-i2c-bus-psu": {
  "title": "BMC I2C1 — PSU SMBus (PMBus)",
  "sub": "AST2050 QU1 A15/B15 · alert on SALT1 (B12)",
  "colw": [180, 300],
  "layers": [[N("bmc","AST2050 BMC","master","I2C1 · A15/B15")],
             [N("psu","PSU SMBus · PSUSMB1","mem","PMBus telemetry + alert→SALT1")]],
  "edges": [("bmc","psu")]},

"kgpe-d16-i2c-bus-inventory": {
  "title": "BMC I2C5 — board inventory + DIMM error LEDs",
  "sub": "AST2050 QU1 A13/B13",
  "colw": [180, 320],
  "layers": [[N("bmc","AST2050 BMC","master","I2C5 · A13/B13")],
             [N("ee","HT24LC08 EEPROM · 0x50","mem","board FRU (U25)"),
              N("u27","W83601G · U27","gpio","DIMM A–F error LEDs (strap addr)"),
              N("u28","W83601G · U28","gpio","DIMM G/H error LEDs (strap addr)")]],
  "edges": [("bmc","ee"),("bmc","u27"),("bmc","u28")]},

"kgpe-d16-i2c-bus-cputemp": {
  "title": "BMC I2C4 / SB-TSI — CPU thermal",
  "sub": "AST2050 QU1 C13/D13 ↔ W83795G TSI ↔ CPU SB-TSI",
  "colw": [180, 230, 250],
  "layers": [[N("bmc","AST2050 BMC","master","I2C4 · C13/D13")],
             [N("hwm","W83795G · QU4","sensor","TSI pins 29/30")],
             [N("cpu","CPU0/1 SB-TSI · 0x4C/0x4D","sensor","processor die temp")]],
  "edges": [("bmc","hwm"),("hwm","cpu")]},

"kgpe-d16-i2c-bus-vr": {
  "title": "SP5100 SMBus0 — CPU/NB voltage regulators (SVI/PMBus)",
  "sub": "SP5100 SU1 AA18/W18 (SCL0/SDA0)",
  "colw": [200, 320],
  "layers": [[N("sb","SP5100 southbridge","master","SMBus0 · AA18/W18")],
             [N("pu2","PU2 · UPI ASP0902QGK","vr","CPU0 core VR PWM controller"),
              N("pu7","PU7 · UPI ASP0906QGK","vr","CPU1/NB VR PWM controller")]],
  "edges": [("sb","pu2"),("sb","pu7")]},

"kgpe-d16-i2c-bus-firewire": {
  "title": "FireWire config EEPROM (private bus)",
  "sub": "LSI FW322 1394a controller · self-programming from its EEPROM",
  "colw": [230, 250],
  "layers": [[N("fw","LSI FW322 · ZU1","master","ROM_CLK/ROM_AD")],
             [N("ee","HT24LC02 EEPROM · ZU2 · 0x50","mem","1394 GUID / config")]],
  "edges": [("fw","ee")]},

"kgpe-d16-i2c-bus-nbhotplug": {
  "title": "SR5690 northbridge — PCIe hot-plug SMBus",
  "sub": "NB debug/hot-plug I2C on DBG_GPIO1/2",
  "colw": [230, 260],
  "layers": [[N("nb","SR5690 northbridge · NU1","master","PCIE_HP_SCL/SDA (B22/B21)")],
             [N("hdr","NB_DEBUG_HEADER1","mem","PCIe hot-plug / debug header")]],
  "edges": [("nb","hdr")]},

"kgpe-d16-i2c-bus-sensor": {
  "title": "Shared platform sensor bus (multi-master)",
  "sub": "BMC (I2C2/3/6) and SP5100 (SMBus1/2) share the hardware monitor + DIMM-mux entry",
  "colw": [200, 300],
  "layers": [[N("bmc","AST2050 BMC","master","I2C2/I2C3/I2C6"),
              N("sb","SP5100 southbridge","master","SMBus1/SMBus2")],
             [N("hwm","W83795G hwmon · QU4 · 0x2F","sensor","11 voltages · 6 temps · 14 fans"),
              N("qu9","QU9 SN74CBTLV3125 switch","mux","→ QU5 → DIMM SPD (see below)")]],
  "edges": [("bmc","hwm"),("bmc","qu9"),("sb","hwm"),("sb","qu9")]},

"kgpe-d16-i2c-bus-dimm-spd": {
  "title": "DIMM SPD / TSOD buses (via QU5 mux)",
  "sub": "BMC I2C2 → QU9 switch → QU5 74HC4052 → the two DIMM banks",
  "colw": [170, 210, 190, 300],
  "layers": [[N("bmc","AST2050 BMC","master","I2C2 (or SP5100)")],
             [N("qu9","QU9 SN74CBTLV3125","mux","FET switch · I2CMUX_EN#")],
             [N("qu5","QU5 74HC4052","mux","1-of-4 · S1:S0")],
             [N("ad","DIMM A–D · I2C10 (S1:S0=10)","sensor","SPD 0x50–57 · TSOD 0x18–1F"),
              N("eh","DIMM E–H · I2C11 (S1:S0=11)","sensor","SPD 0x50–57 · TSOD 0x18–1F"),
              N("aux","AUX_PANEL1 · I2C8 (S1:S0=00)","mem","front-panel I2C")]],
  "edges": [("bmc","qu9"),("qu9","qu5"),("qu5","ad"),("qu5","eh"),("qu5","aux")]},
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, spec in SPECS.items():
        open(os.path.join(OUT, name + ".svg"), "w").write(render(spec) + "\n")
        print("wrote diagrams/" + name + ".svg")


if __name__ == "__main__":
    main()

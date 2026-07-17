#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Generate a per-pin connection map for one part of the KCMA-D8 board.

Reads board.json (produced by extract_fz.py --json) and, for the requested
reference designator, classifies every pin into a functional group, resolves
the far end of each net through series passives, and emits:
  * <refdes>_pins.json  - structured per-pin records
  * markdown to stdout  - grouped tables + power/ground/neighbour summaries

Usage:  uv run pinmap.py board.json QU1 > QU1_pins.md
"""
import json
import re
import sys
from collections import defaultdict

if len(sys.argv) < 3:
    sys.exit("usage: pinmap.py board.json <REFDES>")
BOARD, PART = sys.argv[1], sys.argv[2]
d = json.load(open(BOARD))
pins = d["pins"]
desc = d["refdes_desc"]

by_part = defaultdict(list)
nets = defaultdict(list)
for p in pins:
    by_part[p["part"]].append(p)
    nets[p["net"]].append(p)

# ---- passives we walk through when resolving a net end-to-end ----
PASSIVE = re.compile(r"^(QR|QRN|LR|SR|NR|OR|PR|KR|R|XR|HR|ER|FR|CR|AR|RN|"
                     r"C|QC|LC|SC|OC|PC|XC|EC|FC|CC|L|QL|LL|SL|FL|"
                     r"D|SD|LD|VD|QD|ND|OD|BD)\d")
POWER = re.compile(r"(GND|VSS|VDD|VCC|AVDD|VREF|VPP|_AUX|VBAT|VTT|VEE|"
                   r"\+\d|\+[0-9]V|1V0|1V1|1V2|1V5|1V8|2V5|3V3|3\.3|5V|12V|VSB|VDDR)", re.I)


NETWORK = re.compile(r"^(QRN|RN|ARN|QRN|PRN|ORN|NRN|SRN)\d")


def is_passive(part):
    return len(by_part[part]) <= 3 and bool(PASSIVE.match(part))


def network_sibling_pins(part, pnum):
    """For an isolated resistor/array network (adjacent-pair pinout: 1-2, 3-4,
    ...), return the pin(s) electrically paired with pnum. Falls back to 'all
    other pins' if the numbering isn't a clean integer."""
    try:
        k = int(pnum)
    except (TypeError, ValueError):
        return [p["pnum"] for p in by_part[part] if p["pnum"] != pnum]
    sib = k + 1 if k % 2 == 1 else k - 1
    return [str(sib)]


# A net touching more than this many pins is a shared bus / rail / daisy-chain,
# not a point-to-point trace. We record its name instead of walking into it,
# which prevents a single pull-up on a common net from exploding the fan-out.
SHARED_NET_PINS = 14


def resolve(net, seen=None, depth=0):
    """Endpoints reachable through series passives and isolated resistor
    networks (walked pin-pair aware). Returns a set of (part, pin, pinname)
    tuples; shared buses are returned as ("net", <netname>, "")."""
    if seen is None:
        seen = {net}
    out = set()
    for q in nets[net]:
        part = q["part"]
        if part == PART:
            continue
        walkable = (depth < 5 and NETWORK.match(part)) or (is_passive(part) and depth < 5)
        if not walkable:
            out.add((part, q["pnum"], q["pname"] or ""))
            continue
        # Determine the far-side net(s) reached through this passive.
        if NETWORK.match(part):
            far_pins = [r for r in by_part[part]
                        if r["pnum"] in network_sibling_pins(part, q["pnum"])]
        else:
            far_pins = [r for r in by_part[part] if r["pnum"] != q["pnum"]]
        for r in far_pins:
            fn = r["net"]
            if fn in seen or POWER.search(fn or ""):
                continue
            seen.add(fn)
            if len(nets[fn]) > SHARED_NET_PINS:
                out.add(("net", fn, ""))          # shared bus - name it, don't walk
            else:
                out |= resolve(fn, seen, depth + 1)
    return out


# ---- functional classification (net-name + pin-name heuristics) ----
def group_of(net, pname):
    n = (net or "").upper()
    pn = (pname or "").upper()
    if net in ("", "NC"):
        return "No-connect"
    if re.search(r"(^|_)(GND|VSS)$", n) or n == "GND":
        return "Ground"
    if POWER.search(n) and not re.search(r"(SENSE|THERM|VBCK|VBCS|VBDI|VBDO)", n):
        return "Power / decoupling"
    hay = n + " " + pn  # match against net name AND datasheet pin name
    # buses
    if re.search(r"(AST_MEM|MEMVREF|VREFSSTL|_DDR)", n) or pn.startswith(("DQ","MA","BA","DM","DQS")):
        return "DDR2 memory"
    if re.search(r"(SATA|SGPIO)", hay):
        return "SATA"
    if re.search(r"(USB_HSD|USB_FSD|USB_OC|USBP\d|USBN\d|\bUSB)", hay):
        return "USB"
    if re.search(r"(PCIE|PE_|_PE|PERST|PCI_E|PCIERX|PCIETX|SB_GPP|GPP|GFXRX|GFXTX)", hay):
        return "PCI Express"
    if re.search(r"(SB_PCI|PCI_AD|PCICLK|_PCIRST|PCIREQ|PCIGNT|C_PCI)", n) or re.search(r"^(AD\d|C/?BE|IRDY|TRDY|DEVSEL|FRAME#|STOP#|PAR|IDSEL)", pn):
        return "PCI (33MHz)"
    if re.search(r"(LPC|LAD|LFRAME|LDRQ|SERIRQ|LPCPD|ROMCS)", hay):
        return "LPC host bus"
    if re.search(r"(SPI|ROMA|ROMD|ROM_|SPIROM)", n) or pn.startswith(("ROMA","ROMD","SPI")):
        return "SPI / ROM flash"
    if re.search(r"(RMII|MIIMD|MII|NCSI|82574_|_LAN\d_REFCLK|MNG_)", n):
        return "Ethernet RMII / NC-SI"
    if re.search(r"(DAC|HSYNC|VSYNC|DDCA|DDCCLK|DDCDAT|VGA|CRT)", hay):
        return "VGA / video"
    if re.search(r"(I2C|SMB|SDA|SCL|SALT|TSI)", hay):
        return "I2C / SMBus"
    if re.search(r"(TXD|RXD|NRTS|NCTS|NDTR|NDSR|NDCD|NRI|SOL|UART|SIN|SOUT|SERIAL|SB_RI|SB_DCD|SB_DSR)", hay):
        return "Serial / SOL (UART)"
    if re.search(r"(TCK|TMS|TDI|TDO|TRST|RTCK|NTRST|ENTEST|JTAG)", hay):
        return "JTAG / test"
    # SP5100 embedded hardware-monitor / fan controller (IMC)
    if re.search(r"(IMC_PWM|IMC_TACH|FANIN|FANCTL|\bVIN\d|TEMPIN|TSENSE|THERMDA|THERMDC)", hay):
        return "Hardware monitor / fans (IMC)"
    if re.search(r"(PWRGD|PWROK|PWRBTN|ATXPSON|PSON|SYSRESET|RSMRST|PWRBNT|CLRTC|"
                 r"SYNCFLOOD|NMI|THERMTRIP|PROCHOT|DISABLE|BIOS|RECOVERY|PSONEN|"
                 r"DDR_THERM|SLP_|RESET|_RST|RST#|SUSCLK|SUS_|INTRUDER|SPKR|SPKOUT|BLINK|"
                 r"PWRON|S3_|S5_|STPCLK|PWRDN)", hay):
        return "Power / reset / platform control"
    if re.search(r"(LED|IDBNT|IDLED|BMCRDY|MLED)", hay):
        return "LEDs / indicators"
    if re.search(r"(CLKIN|24M|OSC|XTAL|REFCLK|RTCCLK|_32K|X1$|X2$|32K_X)", hay):
        return "Clocks"
    if re.search(r"(IKVMEN|SOLEN|IPMI_SEL|IDSEL|SEL$|_SEL|STRAP|PRESENT)", n):
        return "Strap / config"
    return "Other / GPIO"


records = []
for p in by_part[PART]:
    g = group_of(p["net"], p["pname"])
    eps = []
    if g not in ("Power / decoupling", "Ground", "No-connect"):
        pnet = p["net"]
        if pnet and len(nets[pnet]) > SHARED_NET_PINS:
            # Pin sits directly on a shared bus/rail; name it rather than list.
            others = sorted({q["part"] for q in nets[pnet] if q["part"] != PART})
            eps = [f"shared net `{pnet}` ({len(nets[pnet])} pins: "
                   f"{', '.join(others[:6])}{'…' if len(others) > 6 else ''})"]
        else:
            by_ep = defaultdict(set)
            shared = []
            for (part, pnum, pnm) in resolve(pnet):
                if part == "net":
                    shared.append(pnum)
                else:
                    by_ep[part].add(pnum)
            eps = [f"{part}[{','.join(sorted(v))}]" for part, v in sorted(by_ep.items())]
            eps += [f"→`{s}` (bus)" for s in sorted(set(shared)) if s]
    records.append({"pin": p["pnum"], "pname": p["pname"], "net": p["net"],
                    "group": g, "endpoints": eps})

json.dump(records, open(f"{PART}_pins.json", "w"), indent=1)

# ---- markdown ----
ORDER = ["DDR2 memory", "SPI / ROM flash", "LPC host bus", "PCI (33MHz)",
         "PCI Express", "SATA", "USB", "Ethernet RMII / NC-SI", "VGA / video",
         "I2C / SMBus", "Serial / SOL (UART)", "JTAG / test",
         "Hardware monitor / fans (IMC)",
         "Power / reset / platform control", "LEDs / indicators", "Clocks",
         "Strap / config", "Other / GPIO", "Power / decoupling", "Ground",
         "No-connect"]

groups = defaultdict(list)
for r in records:
    groups[r["group"]].append(r)


def ball_key(pn):
    m = re.match(r"^([A-Z]*)(\d+)$", pn or "")
    if m and m.group(1):
        v = 0
        for ch in m.group(1):
            v = v * 26 + ord(ch) - 64
        return (0, v, int(m.group(2)))
    if (pn or "").isdigit():
        return (1, 0, int(pn))
    return (2, 0, pn or "")


ENDPOINT_PART = re.compile(r"([A-Za-z][A-Za-z0-9_]*)\[")


def clean_desc(s):
    """Tidy a raw schematic part-description field for display: drop the ASUS
    BOM annotation markers like `<G>` (a "Green"/RoHS procurement tag, not an
    electrical property) and collapse the field-padding whitespace."""
    s = re.sub(r"<[^>]*>", "", s or "")     # strip <G> and any other <...> tags
    return re.sub(r"\s{2,}", " ", s).strip()


def connected_components(rows):
    """Distinct endpoint parts referenced in a group's rows, keyed by refdes,
    each with its description and how many of this group's nets reach it.
    Filters out two-/three-pin passives so only real chips/connectors surface."""
    hits = defaultdict(int)
    for r in rows:
        seen = set()
        for ep in r["endpoints"]:
            for refdes in ENDPOINT_PART.findall(ep):
                if refdes in seen:
                    continue
                seen.add(refdes)
                if len(by_part.get(refdes, [])) >= 4:   # skip discrete passives
                    hits[refdes] += 1
    return hits


print(f"# {PART} pin map  ({len(records)} pins)  {clean_desc(desc.get(PART,''))}\n")
for g in ORDER:
    rows = groups.get(g)
    if not rows:
        continue
    print(f"\n## {g} ({len(rows)})\n")
    if g in ("Power / decoupling", "Ground"):
        rails = defaultdict(list)
        for r in rows:
            rails[r["net"]].append(r["pin"])
        print("| Rail | Count | Balls |")
        print("|---|---|---|")
        for net, bs in sorted(rails.items()):
            print(f"| `{net or '(blank)'}` | {len(bs)} | {' '.join(sorted(bs, key=ball_key))} |")
        continue
    # Per-section summary of which other components these pins connect to.
    comps = connected_components(rows)
    if comps:
        print("**Connected components** (chips / connectors these pins reach):\n")
        for refdes, n in sorted(comps.items(), key=lambda kv: (-kv[1], kv[0])):
            dsc = clean_desc(desc.get(refdes, ""))
            dsc = f" — {dsc}" if dsc else ""
            print(f"- `{refdes}` ({len(by_part[refdes])} pins, {n} net"
                  f"{'s' if n != 1 else ''}){dsc}")
        print()
    print("| Ball | Pin name (function) | Net | Connects to |")
    print("|---|---|---|---|")
    for r in sorted(rows, key=lambda x: ball_key(x["pin"])):
        ep = ", ".join(r["endpoints"]) or "—"
        print(f"| {r['pin']} | `{r['pname'] or '-'}` | `{r['net']}` | {ep} |")

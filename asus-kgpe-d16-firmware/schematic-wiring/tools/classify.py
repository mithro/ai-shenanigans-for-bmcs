#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Classify every AST2050 (QU1) ball into a functional block, resolve series
resistor endpoints, and map I2C buses. Emits classified.json + a readable dump.
"""
import json
import re
from collections import defaultdict

BMC = "QU1"
d = json.load(open("board.json"))
pins = d["pins"]
desc = d["refdes_desc"]

by_part = defaultdict(list)
nets = defaultdict(list)
for p in pins:
    by_part[p["part"]].append(p)
    nets[p["net"]].append(p)

bmc = [p for p in pins if p["part"] == BMC]

PASSIVE = re.compile(r"^(QR|QRN|LR|SR|NR|OR|PR|R|XR|HR|ER|FR|C|QC|LC|SC|OC|PC|XC|EC|FC|L|QL|LL|SL|D|SD|Q|QQ|NQ|LQ|OQ|PQ)\d")

def is_passive_2pin(part):
    return len(by_part[part]) <= 3 and PASSIVE.match(part)

def resolve_endpoints(net, depth=0, seen=None):
    """Follow through 2/3-pin passive parts to reach non-passive endpoints."""
    if seen is None:
        seen = set()
    endpoints = set()
    for q in nets[net]:
        part = q["part"]
        if part == BMC:
            continue
        if is_passive_2pin(part):
            # hop to the other pins' nets
            for r in by_part[part]:
                if r["net"] != net and r["net"] not in seen and depth < 3:
                    seen.add(r["net"])
                    # ignore power/ground endpoints when hopping
                    if re.search(r"(GND|VSS|\+\d|_AUX|VCC|VDD|3V3|5V|1V8|1V2|1V5|2V5|1V0|VSB)", r["net"] or "", re.I):
                        continue
                    endpoints |= resolve_endpoints(r["net"], depth + 1, seen)
        else:
            endpoints.add((part, q["pnum"], q["pname"], desc.get(part, "")))
    return endpoints


def classify(net, pname):
    n = (net or "").upper()
    if net == "" or net == "NC":
        return "No-Connect"
    if re.search(r"(GND|VSS)", n):
        return "Ground"
    if re.search(r"(VDD|VCC|AVDD|VREF|VPP|_AUX|PLLV|USBV|DACAV|MPLLAV|HPLLAV|\+1V|\+1\.|\+2V|\+3V|\+5V|VBAT|1V2|1V8|2V5|3V3|5V)", n):
        return "Power"
    if n.startswith("AST_MEM") or "MEMVREF" in n:
        return "DDR2 memory (to QU2)"
    if n.startswith("AST_ROM") or n.startswith("AST_SPI") or "SPICS" in n or n.startswith("AST_ROMA"):
        return "SPI/ROM flash (BMC_FW1)"
    if "LPC" in n:
        return "LPC host bus"
    if re.search(r"(RMII|MIIMD|MII|NCSI|REFCLK.*(RMII|MNG))", n):
        return "Ethernet RMII / NC-SI"
    if re.search(r"(DAC|HSYNC|VSYNC|DDCCLK|DDCDAT|VGA|CRT)", n):
        return "VGA / video"
    if re.search(r"(USB)", n):
        return "USB"
    if re.search(r"(I2C|SMB|SDA|SCL)", n):
        return "I2C / SMBus"
    if re.search(r"(TXD|RXD|NRTS|NCTS|NDTR|NDSR|NDCD|NRI|SOL|UART|SERIAL)", n):
        return "Serial / SOL (UART)"
    if re.search(r"(TCK|TMS|TDI|TDO|TRST|RTCK|SRST|NTRST|ENTEST)", n):
        return "JTAG / test"
    if re.search(r"(PWRGD|PWRBTN|ATXPSON|PSON|SYSRESET|RESET|RST|PWRBNT|CLRTC|SYNCFLOOD|NMI|THERMTRIP|PROCHOT|CPU\dDISABLE|BIOS|RECOVERY|PSONEN|DDR_THERM)", n):
        return "Power/reset/platform control"
    if re.search(r"(LED|IDLED|BMCRDY|MLED|IDBNT)", n):
        return "LEDs / front panel"
    if re.search(r"(24M|CLKIN|CLK)", n):
        return "Clock"
    if re.search(r"(IKVMEN|SOLEN|IPMI_SEL|IDSEL|IDBNT|BRST|BMCRDY|SEL)", n):
        return "Strap / config"
    return "Other / GPIO"


groups = defaultdict(list)
for p in bmc:
    g = classify(p["net"], p["pname"])
    ep = ""
    if g not in ("Power", "Ground", "No-Connect"):
        eps = resolve_endpoints(p["net"])
        # compress to part:pin list, dedup by part
        by_ep = {}
        for (part, pnum, pn, dsc) in eps:
            by_ep.setdefault(part, []).append((pnum, pn))
        parts_fmt = []
        for part in sorted(by_ep):
            pinlist = ",".join(sorted({x[0] for x in by_ep[part]}))
            parts_fmt.append(f"{part}[{pinlist}]")
        ep = "; ".join(parts_fmt)
    groups[g].append({"ball": p["pnum"], "pname": p["pname"],
                      "net": p["net"], "endpoints": ep})

order = ["DDR2 memory (to QU2)", "SPI/ROM flash (BMC_FW1)", "LPC host bus",
         "Ethernet RMII / NC-SI", "VGA / video", "USB", "I2C / SMBus",
         "Serial / SOL (UART)", "JTAG / test", "Power/reset/platform control",
         "LEDs / front panel", "Clock", "Strap / config", "Other / GPIO",
         "Power", "Ground", "No-Connect"]

json.dump({g: groups[g] for g in order if g in groups},
          open("classified.json", "w"), indent=1)

print("=== AST2050 (QU1) ball classification ===\n")
for g in order:
    if g not in groups:
        continue
    rows = groups[g]
    print(f"### {g}  ({len(rows)} balls)")
    if g in ("Power", "Ground"):
        rails = defaultdict(list)
        for r in rows:
            rails[r["net"]].append(r["ball"])
        for net, balls in sorted(rails.items()):
            print(f"    {net or '(blank)':16s} x{len(balls):2d}: {' '.join(sorted(balls))}")
    else:
        for r in rows:
            print(f"    {r['ball']:4s} {r['pname'] or '-':22s} {r['net']:26s} -> {r['endpoints']}")
    print()

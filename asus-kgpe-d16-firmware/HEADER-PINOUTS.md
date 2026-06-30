# KGPE-D16 debug header pinout diagrams

Physical-layout diagrams for the populated debug/dev headers, for wiring to an
RPi4B (see [`RPI4-OPENOCD-JTAG-WIRING.md`](RPI4-OPENOCD-JTAG-WIRING.md)).

> **Read this first — confidence levels.** A wrong pin-1 assumption on a live
> board backfeeds the AST2050. Every diagram below is tagged:
> **✅ VERIFIED** (drawn from a cited source) · **🔶 STANDARD** (a documented
> standard the header is known to follow — confirm pin 1 by eye) ·
> **⚠️ TEMPLATE** (physical shape only; signals must be probed on *your* board —
> I will not invent pin assignments).

## Verification status of every header you listed

| Header | Layout known? | Source | What I can draw |
|---|---|---|---|
| `AST_JTAG1` | ✅ "Standard 20-pin ARM JTAG" | Raptor page + annotated photo | full pinout |
| `AST_UART1` | ✅ "4-pin 3.3V ARM UART" (1×4) | Raptor annotated photo | full pinout |
| `BMC_FW1`   | 🔶 location + pin 1 only | ASUS manual §2.7.2 p2-38 | outline; signals proprietary (ASMB4) |
| `NB_JTAG_HEADER` | ⚠️ none | — (AMD HDT, undocumented) | template + probe |
| `NB_DEBUG_HEADER` | ⚠️ none | — | template + probe |
| `TEST_CON1` / `TEST_CON2` | ⚠️ none | — (factory ICT) | template + probe |

> Both `AST_*` headers are **unpopulated footprints** sitting just above the
> ASPEED AST2050 (Raptor's photos `top_view_bmc_debug_headers.png` and
> `3_4_view_bmc_debug_headers.png`); you solder headers into them. Raptor's
> top-view marks **+3.3 V at one end, GND at the other** of the UART header.

Reference (documented, but **not** a BMC header): the ASUS manual also gives a
`Serial port connector (10-1 pin COM2)` at p2-37 — that's the **host Super-I/O**
serial port, *not* the BMC's `AST_UART1`. Don't confuse the two.

---

## AST_JTAG1 — ✅ ARM 20-pin (2×10, 0.1″)

Physical layout as it sits on the board. Pin 1 = **square pad** (top-left);
numbering goes down each column (1,2 top → 19,20 bottom). Odd column = signals,
even column = GND (except pins 1–2).

```
                 AST_JTAG1  (component side, pin 1 = ■)
                ┌─────────────────────┐
     VTref    1 │ ■               ○ │ 2   Vsupply (NC)
     nTRST    3 │ ○               ○ │ 4   GND
     TDI      5 │ ○               ○ │ 6   GND
     TMS      7 │ ○               ○ │ 8   GND
     TCK      9 │ ○               ○ │ 10  GND
     RTCK    11 │ ○               ○ │ 12  GND
     TDO     13 │ ○               ○ │ 14  GND
     nSRST   15 │ ○               ○ │ 16  GND
     DBGRQ   17 │ ○               ○ │ 18  GND  (DBGRQ = NC)
     (Vsup)  19 │ ○               ○ │ 20  GND  (pin 19 = NC)
                └─────────────────────┘
   ───────────────────────────────────────────────────────────
   Pin  Signal   ->  RPi4 BCM / phys     |  Pin  Signal  -> RPi4
     5  TDI       ->  GPIO23 / pin 16     |    9  TCK     -> GPIO25 / pin 22
     7  TMS       ->  GPIO24 / pin 18     |   13  TDO     -> GPIO22 / pin 15
     3  nTRST     ->  GPIO17 / pin 11     |   15  nSRST   -> GPIO18 / pin 12
     1  VTref     ->  meter only (~3.3 V, do NOT drive)
   4/6/8/10/12/14/16/18/20  GND -> any RPi4 GND (≥1, mandatory)
```

> ⚠️ Even though this is the ARM standard, **confirm pin 1 visually** (square
> pad / "1" silk) before trusting it — a mirrored connector swaps the whole map.

---

## BMC_FW1 — 🔶 documented location, proprietary signals

The ASUS manual (§2.7.2, "BMC header (BMC_FW1)") shows only the connector
position and **Pin 1 at the lower-left**, with the note *"The BMC connector on
the motherboard supports an ASUS Server Management Board 4 Series (ASMB4)."* No
per-pin signal names are published — it is the **ASMB4‑iKVM module** edge
connector (dedicated management NIC + KVM), a 2-row header.

```
        BMC_FW1   (2-row header; pin count NOT verified — count it on the board)
        ┌───────────────────────────────┐
   Pin1 ■ ○ ○ ○ ○ ○ ○ ○ ○ ○ ...         │   signals = PROPRIETARY (ASMB4)
        │ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ...       │   not published; do not probe-drive
        └───────────────────────────────┘
```

**Relevance to firmware dev:** low/uncertain. The AST2050 itself is **onboard**
(Raptor solders `AST_JTAG1` to the *mainboard*), so `BMC_FW1` is for the iKVM
*feature* module, not the BMC core. Its rumored role as a BMC-SPI-flash recovery
path is **unconfirmed** — only treat it as a flash header if continuity testing
proves SPI signals reach the AST2050 boot flash (see probing procedure below).

---

## AST_UART1 — ✅ 4-pin 3.3 V ARM UART (1×4)

Raptor's photo labels this footprint verbatim: *"4-pin 3.3V ARM UART —
Unpopulated. PCB ID 'AST_UART1'"*, and the top-view marks **+3.3 V** at one end
and **GND** at the other. So it's a 1×4 header just above the AST2050. BMC
console = **3.3 V TTL, 115200 8N1** (Raptor).

```
   AST_UART1   (1×4, immediately above the ASPEED AST2050)
   ┌─────────────────────────────────────┐
   │   [1]       [2]       [3]      [4]   │
   │  +3.3V    TXD/RXD   RXD/TXD    GND   │   ends = +3.3V & GND (Raptor top-view)
   └─────────────────────────────────────┘
       │          │         │        │
   leave NC   ─── the two middle pins are TX & RX ───   GND
   (BMC rail)     (confirm order by probing)            -> RPi4 GND (pin 6)

   Wire (after confirming TX vs RX):
     BMC TXD (out) -> RPi4 GPIO15 / RXD  (phys pin 10)
     BMC RXD (in)  -> RPi4 GPIO14 / TXD  (phys pin  8)
     BMC GND       -> RPi4 GND           (phys pin  6)
```

> The two **end** pins (+3.3 V, GND) are fixed by Raptor's photo. The two
> **middle** pins are TXD/RXD — confirm which is which by probing: the BMC's
> **TXD idles high (~3.3 V) and bursts at boot**; RXD floats/low. Find pin 1 by
> the square pad. **Do not wire the +3.3 V pin to the Pi** (it's the BMC rail,
> like VTref on the JTAG header).

---

## NB_JTAG_HEADER / NB_DEBUG_HEADER / TEST_CON1 / TEST_CON2 — ⚠️ unknown

No public layout for any of these. Reality check before you spend effort:

- **`NB_JTAG_HEADER`** — SR5690 / AMD CPU debug is **AMD HDT** (proprietary JTAG),
  **not OpenOCD**. Boundary-scan only with open tools. Likely a defined AMD HDT
  connector, but pin count/order unverified here.
- **`NB_DEBUG_HEADER`** — purpose unconfirmed (POST/Port-80 or LPC debug are the
  usual suspects). Identify before connecting anything driven.
- **`TEST_CON1` / `TEST_CON2`** — factory in-circuit-test pads. Treat as unknown;
  generally leave alone.

```
     <ANY UNKNOWN HEADER>   template — fill from probing
     ┌───────────────────────────┐
   ■ │ p1   p3   p5   p7  ...     │   ■ = locate pin 1 (square pad / dot / "1")
     │ p2   p4   p6   p8  ...     │
     └───────────────────────────┘
   pin │ continuity-to-GND? │ V (5VSB on) │ activity @ boot │ guess
   ────┼────────────────────┼─────────────┼─────────────────┼───────
    1  │                    │             │                 │
    2  │                    │             │                 │
   ... │                    │             │                 │
```

---

## Safely reverse-engineering an unknown header

Do this with a multimeter (and ideally a logic analyzer/scope) **before** wiring
anything to the Pi:

1. **Pin 1 + geometry.** Board OFF. Find pin 1 (square pad / silk dot / arrow /
   "1"). Record rows × columns and the numbering direction. Photograph it.
2. **Find grounds.** DMM in continuity mode: beep each pin against chassis / a
   known GND screw. Every beeping pin is GND.
3. **Find power rails.** Apply 5VSB only (PSU connected, system *not* booted).
   DC-volts each non-GND pin: ~3.3 V / ~5 V steady = a supply rail. **Never wire
   a supply rail to a Pi GPIO.**
4. **Find UART TX / idle-high lines.** At full boot, a UART **TXD** idles high
   (~3.3 V) and shows 115200 async bursts on a scope; **RXD** floats/low. JTAG
   **TCK/TMS/TDI** are quiet at idle (driven only by an adapter); **TDO** may
   float — distinguish by their pull resistors, not activity.
5. **Trace to the silicon.** Short tracks from `AST_*` headers should run to the
   AST2050; `NB_*` headers to the SR5690. Confirms function and voltage domain.
6. **Only then drive a pin** — and only ones proven to be inputs at 3.3 V.

Send me the filled-in tables (or annotated photos / the schematic) and I'll
render exact `matches-the-board` diagrams for `AST_UART1` and the `NB_*` /
`TEST_CON*` headers.

---

## Sources

- Raptor Engineering — KGPE-D16 BMC Port Status (AST_JTAG1 = "Standard 20-pin
  ARM JTAG"; AST_UART1 = "4-pin 3.3V ARM UART"; BMC console 3.3 V / 115200):
  <https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php>
- Raptor annotated board photos (header type + location + 3.3 V / GND ends):
  `.../kgpe-d16-bmc-port-files/top_view_bmc_debug_headers.png` and
  `.../3_4_view_bmc_debug_headers.png`
- Raptor OpenOCD configs (IDCODE 0x07926f0f, reset topology — GPLv3, cited not
  copied): `.../kgpe-d16-bmc-port-files/openocd/{ast2050,kgpe-d16-bmc,olimex-jtag-tiny}.cfg`
- ASUS KGPE-D16 User Manual E8847 — §2.2.4 Layout contents, §2.7.2 Internal
  connectors (BMC_FW1 p2-38, COM2 p2-37):
  <https://dlcdnets.asus.com/pub/ASUS/mb/SocketG34(1944)/KGPE-D16/Menual_QVL/E8847_KGPE-D16.pdf>
- 15h.org — KGPE-D16 (AST2050 BMC; BMC_FW1 = ASMB4/5 slot; SR5690 NB / SP5100 SB):
  <https://15h.org/index.php/KGPE-D16>

# KGPE-D16 debug header pinout diagrams

Physical-layout diagrams for the populated debug/dev headers, for wiring to an
RPi4B (see [`RPI4-OPENOCD-JTAG-WIRING.md`](RPI4-OPENOCD-JTAG-WIRING.md)). For the
**CPU-side** AMD HDT header and the JTAG scan chain, see
[`JTAG-HEADERS.md`](JTAG-HEADERS.md).

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
| `NB_JTAG_HEADER` | 🔶 AMD HDT (CPU debug) | [`JTAG-HEADERS.md`](JTAG-HEADERS.md) | HDT+ pinout there |
| `NB_DEBUG_HEADER` | ⚠️ 2nd HDT? / LPC? | [`JTAG-HEADERS.md`](JTAG-HEADERS.md) | see HDT notes |
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
        AST_JTAG1  -  20-pin ARM JTAG (2x10, 0.1")
        component side - pin 1 = square pad (top-left)
        left column = signal, right column = GND

          +---------+
 VTref  1 | @     o |  2  Vsupply (NC)
 nTRST  3 | o     o |  4  GND
   TDI  5 | o     o |  6  GND
   TMS  7 | o     o |  8  GND
   TCK  9 | o     o | 10  GND
  RTCK 11 | o     o | 12  GND
   TDO 13 | o     o | 14  GND
 nSRST 15 | o     o | 16  GND
 DBGRQ 17 | o     o | 18  GND
  (NC) 19 | o     o | 20  GND
          +---------+
        (@ = pin 1 / square pad)

   RPi4 map: TDI->GPIO23/p16   TMS->GPIO24/p18    TCK->GPIO25/p22
             TDO->GPIO22/p15   nTRST->GPIO17/p11  nSRST->GPIO18/p12
             RTCK->GPIO27/p13 (optional, Pi INPUT only - echo diagnostic)
             VTref-> meter only (~3.3V)   GND (even pins)-> any RPi GND (>=1)
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
        BMC_FW1  -  2-row header (ASMB4-iKVM); pin count = count on board
        +-----------------------------+
        |  o  o  o  o  o  o  o  o  ... |   signals = PROPRIETARY (ASMB4)
        |  @  o  o  o  o  o  o  o  ... |   not published; do NOT probe-drive
        +-----------------------------+
           ^ pin 1 (lower-left, per ASUS manual)
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
      AST_UART1  -  4-pin 3.3V ARM UART (1x4)
      pin 1 = square pad (left) - ends are +3.3V and GND (Raptor photo)

        +3.3V    TX/RX    RX/TX     GND
        +---+    +---+    +---+    +---+
        |@/o|    | o |    | o |    | o |
        +---+    +---+    +---+    +---+
        pin1     pin2     pin3     pin4

   Wire (after confirming TX vs RX by probing):
     BMC TX  -> RPi4 GPIO15 / RXD  (pin 10)   [middle pin 2 or 3]
     BMC RX  -> RPi4 GPIO14 / TXD  (pin  8)   [the other middle pin]
     BMC GND -> RPi4 GND           (pin  6)
     +3.3V   -> leave unconnected (BMC rail, like VTref on JTAG)
```

> The two **end** pins (+3.3 V, GND) are fixed by Raptor's photo. The two
> **middle** pins are TXD/RXD — confirm which is which by probing: the BMC's
> **TXD idles high (~3.3 V) and bursts at boot**; RXD floats/low. Find pin 1 by
> the square pad. **Do not wire the +3.3 V pin to the Pi** (it's the BMC rail,
> like VTref on the JTAG header).

---

## NB_JTAG_HEADER / NB_DEBUG_HEADER / TEST_CON1 / TEST_CON2

The CPU-side debug is now documented in [`JTAG-HEADERS.md`](JTAG-HEADERS.md) —
read that for the full picture:

- **`NB_JTAG_HEADER`** — almost certainly the **AMD HDT** attachment port (CPU /
  northbridge debug). `JTAG-HEADERS.md` has the **20-pin HDT+ pinout (1.27 mm
  pitch)**, the older 25-pin HDT variant, and the `CPU1→CPU2→SR5690→SP5100` scan
  chain. ⚠️ **Not OpenOCD / not RPi-drivable** — HDT needs a proprietary probe
  (ASSET InterTech / AMD HDT kit), and the 1.27 mm pitch rules out dupont wires.
  This is the x86 side, outside this guide.
- **`NB_DEBUG_HEADER`** — unconfirmed: possibly the *second* HDT port (KGPE-D16 is
  dual-socket; Raptor says "HDT Attachment Port**s**"), or an LPC / Port-80 debug
  header. Identify before connecting anything driven.
- **`TEST_CON1` / `TEST_CON2`** — factory in-circuit-test pads. Treat as unknown;
  generally leave alone.

```
   <ANY UNKNOWN HEADER>  -  fill in from probing (board OFF first)
   +-----------------------------+
   | p1  p3  p5  p7  ...         |   @ = pin 1 (square pad / dot / "1")
   | p2  p4  p6  p8  ...         |   (2-row shown; 1-row = p1 p2 p3 ...)
   +-----------------------------+

   For each pin, record:
     - GND?      continuity beep to chassis ground
     - V @5VSB?  DC volts, 5VSB present, system NOT booted (= power rail)
     - activity? at boot: UART TX bursts at 115200; JTAG TCK/TMS idle quiet
     - signal:   your conclusion (only drive proven 3.3 V inputs)
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

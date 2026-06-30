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
| `AST_JTAG1` | ✅ ARM 20-pin | Raptor (Olimex ARM-USB-TINY fits) | full pinout |
| `BMC_FW1`   | 🔶 location + pin 1 only | ASUS manual §2.7.2 p2-38 | outline; signals proprietary (ASMB4) |
| `AST_UART1` | ⚠️ signal set only | Raptor (BMC console, 3.3 V, 115200) | template + probe |
| `NB_JTAG_HEADER` | ⚠️ none | — (AMD HDT, undocumented) | template + probe |
| `NB_DEBUG_HEADER` | ⚠️ none | — | template + probe |
| `TEST_CON1` / `TEST_CON2` | ⚠️ none | — (factory ICT) | template + probe |

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

## AST_UART1 — ⚠️ signal set known, layout to be probed

Raptor confirms the BMC console is **3.3 V TTL, 115200 8N1** (✅). The AST2050
exposes a standard 16550-style UART, so the header carries at minimum:

```
     AST_UART1   (layout NOT verified — 1×3 / 1×4 / 2×5 are all common)
     ┌──────────────────────────────┐
     │  ?    ?    ?    ?    ...      │   known signals present:
     └──────────────────────────────┘     TXD (out, idles high ~3.3 V)
   pin 1 = ?  (probe to assign)            RXD (in)
                                           GND (continuity to chassis)
                                           [maybe VCC 3.3 V, RTS/CTS]
```

Fill it in with the probing procedure below, then wire per the UART section of
the wiring guide (target TXD → RPi GPIO15/pin10, RXD → GPIO14/pin8, GND → pin6).

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

- Raptor Engineering — KGPE-D16 BMC Port Status (AST_JTAG1 = ARM 20-pin via
  Olimex ARM-USB-TINY; BMC console 3.3 V / 115200):
  <https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php>
- ASUS KGPE-D16 User Manual E8847 — §2.2.4 Layout contents, §2.7.2 Internal
  connectors (BMC_FW1 p2-38, COM2 p2-37):
  <https://dlcdnets.asus.com/pub/ASUS/mb/SocketG34(1944)/KGPE-D16/Menual_QVL/E8847_KGPE-D16.pdf>
- 15h.org — KGPE-D16 (AST2050 BMC; BMC_FW1 = ASMB4/5 slot; SR5690 NB / SP5100 SB):
  <https://15h.org/index.php/KGPE-D16>

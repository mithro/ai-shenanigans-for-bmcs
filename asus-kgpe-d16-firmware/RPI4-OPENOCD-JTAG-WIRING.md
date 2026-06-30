# Wiring a Raspberry Pi 4B to the ASUS KGPE-D16 for BMC JTAG/UART debug

How to use a Raspberry Pi 4 Model B as an OpenOCD JTAG adapter (plus serial
console, plus SPI flashing) against the populated debug headers on the ASUS
KGPE-D16, for developing replacement firmware on the ASPEED **AST2050** BMC.

> **Status of facts below:** ✅ = verified against an external source (cited),
> 🔶 = strong inference (stated as such), ⚠️ = must be confirmed with a meter on
> *your* board before you trust it. Nothing here is a substitute for buzzing out
> pin 1 and continuity before applying power.

---

## 0. Scope — what this rig actually gives you

Three caveats decide what is and isn't worth wiring:

1. **OpenOCD debugs the BMC (ARM), not the x86 CPU.** The AST2050 is an
   ARM926EJ-S (ARMv5TE) — a first-class OpenOCD target. The AMD Opteron CPUs
   and the **SR5690** northbridge / **SP5100** southbridge ✅ are x86, and their
   on-die debug is **AMD HDT** (Hardware Debug Tool) — a proprietary JTAG
   dialect OpenOCD does **not** support. So `NB_JTAG_HEADER` / `NB_DEBUG_HEADER`
   give you boundary-scan visibility at best, **not** x86 single-stepping or
   "CPU bring-up" the way JTAG does on the ARM BMC. This is a *BMC* dev rig.

2. **Both sides are 3.3 V; the RPi4 is NOT 5 V tolerant.** AST2050 JTAG I/O is
   3.3 V and so is the Pi, so direct wiring is electrically compatible — *after*
   you confirm `AST_JTAG1` pin 1 (VTref) reads ~3.3 V. A 5 V line into a Pi GPIO
   kills the pin.

3. **`BMC_FW1` is a flash/module slot, not a JTAG or serial header.** 15h.org ✅
   describes it as the slot for the ASMB4/ASMB5 management module / BMC firmware
   carrier. That's a **flashrom (SPI)** concern, reached with the Pi's *hardware
   SPI*, not the bit-bang JTAG. Probe it before assuming anything (see §4).

---

## 1. The populated headers, grounded

| Header | What it is | Tool | Confidence |
|---|---|---|---|
| **AST_JTAG1** | AST2050 ARM926 JTAG, 20-pin ARM pinout | OpenOCD bit-bang (this guide) | ✅ Raptor |
| **AST_UART1** | BMC serial console, `ttyS1` internal, 115200 8N1 | USB-serial or Pi UART0 | ✅ Raptor |
| **BMC_FW1** | ASMB4/5 management-module / BMC firmware slot | flashrom (SPI) — verify | 🔶 / ⚠️ |
| **NB_JTAG_HEADER** | SR5690 northbridge TAP (boundary-scan) | OpenOCD scan only | ⚠️ no x86 debug |
| **NB_DEBUG_HEADER** | NB debug (likely POST/LPC or AMD-internal) | identify first | ⚠️ |
| **TEST_CON1 / TEST_CON2** | Factory test connectors | unknown | ⚠️ probe first |

Ground truth: Raptor Engineering soldered `AST_JTAG1` (an unpopulated **20-pin
ARM debug footprint**) and drove it with an **Olimex ARM-USB-TINY** + OpenOCD,
configs `ast2050.cfg` + `kgpe-d16-bmc.cfg`, "sufficient functionality to bring
up U-Boot." ✅ That an Olimex ARM-USB-TINY plugs straight in is why we treat
`AST_JTAG1` as the **standard ARM 20-pin JTAG pinout** below. 🔶

---

## 2. AST_JTAG1 (20-pin ARM) → RPi4B — the main event

Standard ARM 20-pin JTAG, 0.1″ (2.54 mm) 2×10. **Odd column = signals, even
column = GND**, except pins 1–2:

```
        AST_JTAG1 (target, top view, pin 1 = square pad)
         1  VTref    o o  2  Vsupply (NC)
         3  nTRST    o o  4  GND
         5  TDI      o o  6  GND
         7  TMS      o o  8  GND
         9  TCK      o o 10  GND
        11  RTCK     o o 12  GND
        13  TDO      o o 14  GND
        15  nSRST    o o 16  GND
        17  DBGRQ(NC)o o 18  GND
        19  Vsup(NC) o o 20  GND
```

### Wiring table (direct 3.3 V — your chosen scheme)

| Signal | AST_JTAG1 pin | RPi4 BCM | RPi4 phys pin |
|---|---|---|---|
| TCK  | 9  | GPIO25 | 22 |
| TMS  | 7  | GPIO24 | 18 |
| TDI  | 5  | GPIO23 | 16 |
| TDO  | 13 | GPIO22 | 15 |
| nTRST | 3 | GPIO17 | 11 |
| nSRST | 15 | GPIO18 | 12 |
| GND  | 4/6/8/10/12/14/16/18/20 (any, ≥1) | GND | 6, 9, 14, 20, 25, 30, 34, 39 |
| VTref | 1 | — | **measure only, do not connect** |

```
   RPi4 40-pin header                         AST_JTAG1 (ARM 20-pin)
   ┌───────────────────┐
   │ pin15 GPIO22 TDO  │────────────────────▶ pin13 TDO
   │ pin16 GPIO23 TDI  │────────────────────▶ pin5  TDI
   │ pin18 GPIO24 TMS  │────────────────────▶ pin7  TMS
   │ pin22 GPIO25 TCK  │────────────────────▶ pin9  TCK
   │ pin11 GPIO17 TRST │────────────────────▶ pin3  nTRST
   │ pin12 GPIO18 SRST │────────────────────▶ pin15 nSRST
   │ pin6  GND         │────────────────────▶ pin4  GND   (mandatory)
   └───────────────────┘        (meter)─────▶ pin1  VTref ≈ 3.3 V
```

### Rules that keep both boards alive (direct-wire edition)

You chose **no series resistors**, so the safety margin comes entirely from
discipline — these are not optional:

- **Verify pin 1 and VTref *before* connecting.** Buzz `AST_JTAG1` even pins to
  chassis ground to confirm orientation, and meter pin 1 = ~3.3 V. A mirrored
  connector (pin 1 at the wrong end) sends TCK into a GND pin.
- **Common ground first, removed last.** Wire at least one GND, ideally the one
  physically nearest your signal leads.
- **Short leads (<10 cm) and slow clock.** Start at `adapter speed 100` (kHz);
  raise only after the IDCODE scans cleanly. Direct bit-bang over long flying
  leads is the classic "scans intermittently" failure.
- **Power sequencing:** with direct wiring, avoid hot-plugging — connect the
  harness with both boards off, then power. (A driven Pi GPIO into an unpowered
  AST2050, or vice-versa, can back-feed through protection diodes. If you ever
  see flakiness here, this is the first thing to add 100–470 Ω series resistors
  for.)

> **Note:** `RTCK` (pin 11) = adaptive clocking; not used by bit-bang. `DBGRQ`
> (17) and the spare supply (2/19) are left unconnected.

---

## 3. AST_UART1 → console — wire this FIRST

UART proves the BMC is alive before you risk JTAG, and gives you the U-Boot
prompt. ✅ 3.3 V TTL, **115200 8N1**; press **Delete** within 3 s of U-Boot
start to drop to the bootloader. Cross TX↔RX:

| AST_UART1 | RPi4 |
|---|---|
| TXD | GPIO15 / RXD — phys pin 10 |
| RXD | GPIO14 / TXD — phys pin 8 |
| GND | GND — phys pin 6 |

```bash
# On the Pi (disable the Linux serial console on /dev/ttyAMA0 first):
sudo raspi-config   # Interface Options → Serial → login shell NO, hardware YES
screen /dev/ttyAMA0 115200      # or /dev/serial0
```

A standalone USB-3.3V-TTL adapter is cleaner (frees the Pi UART and isolates a
ground loop), but the Pi's UART0 works.

---

## 4. BMC_FW1 / BMC SPI flash — flashrom, not OpenOCD

Per 15h.org, `BMC_FW1` is the ASMB4/5 module slot. ✅ Whether it exposes the
AST2050's SPI **boot flash** depends on board revision, so **probe it**:

```
Board OFF. Continuity-test BMC_FW1 pins against the BMC SPI flash chip
(an SOIC-8 near the AST2050). If you find CS / CLK / MOSI / MISO mapping to
the flash, it's a flashrom target. If you only find power + strap/ID lines,
it's the management feature slot — not useful for firmware work.
```

If it *is* SPI, drive it from the Pi's **hardware SPI0** with `flashrom`
(`linux_spi` driver) — use Raptor's `ast2050-flashrom` fork, which knows the
AST2050's SPI controller:

| SPI | RPi4 BCM | RPi4 phys pin |
|---|---|---|
| MOSI | GPIO10 | 19 |
| MISO | GPIO9  | 21 |
| SCLK | GPIO11 | 23 |
| CE0  | GPIO8  | 24 |
| 3V3  | —      | 1 or 17 |
| GND  | —      | 25 |

These pins are **disjoint** from the JTAG pins (GPIO22–25) and the UART pins
(GPIO14/15), so one Pi can carry JTAG + SPI + UART harnesses simultaneously.

---

## 5. NB_JTAG_HEADER / NB_DEBUG_HEADER / TEST_CON1-2 — manage expectations

- **NB_JTAG_HEADER** — SR5690 TAP. OpenOCD can *scan* it (boundary-scan,
  IDCODE), useful for chain sanity / bring-up bus checks, but the AMD CPU debug
  you'd want for "CPU bring-up" runs over **AMD HDT**, which needs AMD's tooling
  (HDT / SimNow), not OpenOCD. Don't wire this expecting x86 halt/step.
- **NB_DEBUG_HEADER** — likely a POST/Port-80 or LPC debug header (or an
  AMD-internal connector). **Identify the signals before connecting** anything
  driven; a debug-card header is input-tolerant, an AMD-internal one may not be.
- **TEST_CON1 / TEST_CON2** — factory/ICT test pads. Treat as unknown; probe
  before use. Not part of the OpenOCD path.

---

## 6. OpenOCD software setup

Configs live in [`openocd/`](openocd/), split adapter / SoC / board:

```bash
# On the Pi:
sudo apt install openocd            # or build a recent (>=0.12) OpenOCD
cd asus-kgpe-d16-firmware/openocd

# First contact — discover the real IDCODE (board powered, BMC at reset):
sudo openocd -f rpi4-jtag.cfg -f ast2050.cfg -c "init; scan_chain; shutdown"
```

Then paste the printed IDCODE into `ast2050.cfg` (`-expected-id`), and run the
full stack:

```bash
sudo openocd -f rpi4-jtag.cfg -f ast2050.cfg -f kgpe-d16-bmc.cfg
# in another terminal:
telnet localhost 4444      # OpenOCD console → halt, reg, mdw, etc.
```

**Driver choice:** the configs use **`linuxgpiod`** (libgpiod char-dev) — the
robust choice on RPi4, no peripheral-base juggling. A `bcm2835gpio` fallback is
commented in `rpi4-jtag.cfg`; if you use it, the BCM2711 peripheral base is
**`0xFE000000`** (vs `0x3F000000` on Pi2/3).

**Do NOT** set `enable_jtag_gpio=1` in `/boot/config.txt` — that exposes the
*Pi's own* CPU JTAG on GPIO22–27 (Alt4) and is unrelated to using the Pi as an
adapter. It would also fight your bit-bang pins.

---

## 7. Pre-power checklist

Before applying power with everything wired:

- [ ] `AST_JTAG1` pin 1 located (square pad) and oriented correctly
- [ ] VTref (pin 1) measures ~3.3 V (board briefly powered, JTAG harness off)
- [ ] At least one GND wired Pi↔target
- [ ] TCK/TMS/TDI/TDO/TRST/SRST mapped exactly per §2 (re-buzz each lead)
- [ ] Leads short (<10 cm); no 5 V line anywhere near a Pi GPIO
- [ ] `adapter speed 100` for first bring-up
- [ ] UART console up first (§3) and showing the BMC boot log

---

## Sources

- Raptor Engineering — KGPE-D16 BMC Port Status (AST_JTAG1 = 20-pin ARM header,
  Olimex ARM-USB-TINY + OpenOCD, U-Boot bring-up, UART 115200):
  <https://www.raptorengineering.com/coreboot/kgpe-d16-bmc-port-status.php>
- 15h.org — ASUS KGPE-D16 (AST2050 BMC, SR5690 NB, SP5100 SB, BMC_FW1 = ASMB
  module slot): <https://15h.org/index.php/KGPE-D16>
- Raptor Engineering — `ast2050-flashrom` (AST2050 SPI flashing):
  <https://github.com/raptor-engineering/ast2050-flashrom>
- iosoft.blog — Raspberry Pi as OpenOCD bit-bang adapter (bcm2835gpio pin
  mapping, peripheral bases): <https://iosoft.blog/2019/01/28/raspberry-pi-openocd/>
- OpenOCD User's Guide — ARM926EJ-S target, `adapter gpio`, TAP declaration:
  <https://openocd.org/doc/html/>

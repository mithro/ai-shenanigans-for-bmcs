# Wiring a Raspberry Pi 4B to the ASUS KGPE-D16 for BMC JTAG/UART debug

How to use a Raspberry Pi 4 Model B as an OpenOCD JTAG adapter (plus serial
console, plus SPI flashing) against the populated debug headers on the ASUS
KGPE-D16, for developing replacement firmware on the ASPEED **AST2050** BMC.

> **Status of facts below:** ✅ = verified against an external source (cited),
> 🔶 = strong inference (stated as such), ⚠️ = must be confirmed with a meter on
> *your* board before you trust it. Nothing here is a substitute for buzzing out
> pin 1 and continuity before applying power.

> **See also (repo docs):** [`JTAG-USAGE-GUIDE.md`](JTAG-USAGE-GUIDE.md) — **how
> to actually drive the core once wired** (halt/step/reg/mem/GDB, verified on
> real hardware) ·
> [`JTAG-HEADERS.md`](JTAG-HEADERS.md) — both KGPE-D16
> JTAG headers (BMC + AMD HDT) with the HDT+ pinout & scan chain ·
> [`HEADER-PINOUTS.md`](HEADER-PINOUTS.md) — per-header diagrams ·
> [`RAPTOR-UBOOT-ANALYSIS.md`](RAPTOR-UBOOT-ANALYSIS.md) — AST2050 U-Boot ·
> [`../HARDWARE-ACCESS.md`](../HARDWARE-ACCESS.md) — the network/SSH side: the
> `rpi4-asus-aspeed2050-dev` bridge this rig runs on, and how to reach it ·
> [`../hpe-ipdu-firmware/HEADERS-J1-J6.md`](../hpe-ipdu-firmware/HEADERS-J1-J6.md)
> — JTAG adapter comparison (same ARM926EJ-S debug architecture).

---

## 0. Scope — what this rig actually gives you

Four caveats decide what is and isn't worth wiring:

1. **OpenOCD debugs the BMC (ARM), not the x86 CPU.** The AST2050 is an
   ARM926EJ-S (ARMv5TE) — a first-class OpenOCD target. The AMD Opteron CPUs
   and the **SR5690** northbridge / **SP5100** southbridge ✅ are x86, and their
   on-die debug is **AMD HDT** (Hardware Debug Tool) — a proprietary JTAG
   dialect OpenOCD does **not** support. HDT *can* do full CPU run-control
   (halt/step/registers), but only with a proprietary probe (ASSET InterTech /
   AMD HDT kit), never with OpenOCD or a Pi. So `NB_JTAG_HEADER` /
   `NB_DEBUG_HEADER` are **not** your route to x86 "CPU bring-up" here — see
   [`JTAG-HEADERS.md`](JTAG-HEADERS.md) for the HDT+ pinout & scan chain. This is
   a *BMC* dev rig.

2. **Both sides are 3.3 V; the RPi4 is NOT 5 V tolerant.** AST2050 JTAG I/O is
   3.3 V and so is the Pi, so direct wiring is electrically compatible — *after*
   you confirm `AST_JTAG1` pin 1 (VTref) reads ~3.3 V. A 5 V line into a Pi GPIO
   kills the pin.

3. **`BMC_FW1` is the socketed BMC SPI boot flash, not a JTAG or serial header.**
   Its pinout is fully documented from the schematic
   ([`schematic-wiring/BMC-CONNECTORS.md`](schematic-wiring/BMC-CONNECTORS.md)):
   a 2×7 DIP socket carrying the AST2050 SPI/ROM bus (CS0=pin12, CLK=pin8,
   MOSI=pin1, MISO=pin6) plus feature straps. That's a **flashrom (SPI)** concern
   (Pi *hardware SPI*) or a ULX3S/spispy emulation target
   ([`ULX3S-SPISPY-BMC-FLASH-WIRING.md`](ULX3S-SPISPY-BMC-FLASH-WIRING.md)), not
   the bit-bang JTAG (see §4).

4. **The AST2050 is EmbeddedICE-RT, not CoreSight — use a raw-JTAG adapter.**
   ARM926EJ-S debugs via **EmbeddedICE-RT over raw JTAG scan chains**, not the
   CoreSight DAP that Cortex cores use. So **CMSIS-DAP and SWD-only probes
   (ST-Link, Black Magic) cannot drive it** — they only speak CoreSight/ADIv5.
   The RPi4 GPIO bitbang does raw IR/DR scans, so it works; so do FTDI adapters
   (Olimex ARM-USB-TINY, TUMPA) and J-Link. Adapter trade-offs for this exact
   ARM926EJ-S debug architecture are tabulated in
   [`../hpe-ipdu-firmware/HEADERS-J1-J6.md`](../hpe-ipdu-firmware/HEADERS-J1-J6.md).

---

## 1. The populated headers, grounded

| Header | What it is | Tool | Confidence |
|---|---|---|---|
| **AST_JTAG1** | AST2050 ARM926 JTAG, 20-pin ARM pinout | OpenOCD bit-bang (this guide) | ✅ Raptor |
| **AST_UART1** | BMC console, 4-pin 3.3 V (+3.3V/TX/RX/GND), 115200 8N1 | USB-serial or Pi UART0 | ✅ Raptor |
| **BMC_FW1** | Socketed BMC SPI boot flash (2×7 DIP) + straps | flashrom (SPI) / ULX3S emulation | ✅ [schematic](schematic-wiring/BMC-CONNECTORS.md) |
| **NB_JTAG_HEADER** | SR5690 northbridge TAP (boundary-scan) | OpenOCD scan only | ⚠️ no x86 debug |
| **NB_DEBUG_HEADER** | NB debug (likely POST/LPC or AMD-internal) | identify first | ⚠️ |
| **TEST_CON1 / TEST_CON2** | Factory test connectors | unknown | ⚠️ probe first |

Ground truth: Raptor Engineering soldered `AST_JTAG1` (an unpopulated **20-pin
ARM debug footprint**) and drove it with an **Olimex ARM-USB-TINY** + OpenOCD,
configs `ast2050.cfg` + `kgpe-d16-bmc.cfg`, "sufficient functionality to bring
up U-Boot." Raptor's annotated board photos label the footprints verbatim —
`AST_JTAG1` = **"Standard 20-pin ARM JTAG"** and `AST_UART1` = **"4-pin 3.3V ARM
UART"** — so both pinouts below are ✅ verified, not inferred. See
[`HEADER-PINOUTS.md`](HEADER-PINOUTS.md) for the per-header diagrams.

---

## 2. AST_JTAG1 (20-pin ARM) → RPi4B — the main event

Standard ARM 20-pin JTAG, 0.1″ (2.54 mm) 2×10. **Odd column = signals, even
column = GND**, except pins 1–2:

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
| RTCK *(optional — Pi INPUT only)* | 11 | GPIO27 | 13 |
| GND  | 4/6/8/10/12/14/16/18/20 (any, ≥1) | GND | 6, 9, 14, 20, 25, 30, 34, 39 |
| VTref | 1 | — | **measure only, do not connect** |

```
   RPi4B 40-pin                         AST_JTAG1 (ARM 20-pin)
   ------------------------------      ----------------------
   GPIO25  pin22  TCK   -->  pin 9  TCK
   GPIO24  pin18  TMS   -->  pin 7  TMS
   GPIO23  pin16  TDI   -->  pin 5  TDI
   GPIO22  pin15  TDO   <--  pin13  TDO
   GPIO17  pin11  nTRST -->  pin 3  nTRST
   GPIO18  pin12  nSRST -->  pin15  nSRST
   GPIO27  pin13  RTCK  <--  pin11  RTCK  (optional; Pi INPUT-only monitor)
   GND     pin 6  GND   ---  pin 4  GND
   (meter)        VTref ...  pin 1  VTref (~3.3V, do NOT drive)

   Direct 3.3V wiring - keep leads <10cm, start at adapter speed 100 kHz.
```

### Which RPi4B header pins — the 40-pin GPIO header (J8)

The JTAG and UART wires above land on these physical pins. JTAG bit-bang
(GPIO22-25, plus GPIO17/18 for reset) and UART0 (GPIO14/15) sit on disjoint
pins, so both harnesses coexist on one Pi:

```
   Raspberry Pi 4B - 40-pin GPIO header (J8)
   pin 1 = square pad (nearest the SD-card/board corner)
   * = wire used by this guide

       use    name pin | pin name    use
   ------- ------- --- | --- ------- -------
               3V3  1  |  2  5V
             GPIO2  3  |  4  5V
             GPIO3  5  |  6  GND
             GPIO4  7  | *8  GPIO14  UART-TX
               GND  9  | *10 GPIO15  UART-RX
     nTRST  GPIO17 11* | *12 GPIO18  nSRST
      RTCK  GPIO27 13* | *14 GND     GND*
       TDO  GPIO22 15* | *16 GPIO23  TDI
               3V3 17  | *18 GPIO24  TMS
            GPIO10 19  |  20 GND
             GPIO9 21  | *22 GPIO25  TCK
            GPIO11 23  |  24 GPIO8
               GND 25  |  26 GPIO7
             GPIO0 27  |  28 GPIO1
             GPIO5 29  |  30 GND
             GPIO6 31  |  32 GPIO12
            GPIO13 33  |  34 GND
            GPIO19 35  |  36 GPIO16
            GPIO26 37  |  38 GPIO20
               GND 39  |  40 GPIO21

   JTAG : TCK GPIO25/p22  TMS GPIO24/p18  TDI GPIO23/p16  TDO GPIO22/p15
          nTRST GPIO17/p11  nSRST GPIO18/p12  GND* p14 (>=1 GND, mandatory)
          RTCK GPIO27/p13 (optional input-only monitor, see below)
   UART : TX GPIO14/p8 -> BMC RXD   RX GPIO15/p10 <- BMC TXD   GND p6
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

> **Note:** `RTCK` (pin 11) = adaptive clocking. OpenOCD's GPIO bit-bang
> drivers cannot consume it (`adapter gpio` has no `rtck` signal), and at
> bit-bang speeds TCK never approaches the ARM9 "TCK < core-clock/6" limit —
> so it is NOT part of the OpenOCD setup. It IS worth wiring to **GPIO27
> (phys pin 13, Pi INPUT only — the target drives it)** as a passive
> diagnostic: ARM926EJ-S RTCK is TCK echoed through the core-clock domain, so
> [`openocd/rtck-echo-test.py`](openocd/rtck-echo-test.py) can prove the chip
> is powered and clocked without attempting a scan (§6). `DBGRQ` (17) and the
> spare supply (2/19) are left unconnected — OpenOCD halts the ARM9 by
> scanning the DBGRQ bit into the EmbeddedICE-RT control register, not via
> the sideband pin.

---

## 3. AST_UART1 → console — wire this FIRST

UART proves the BMC is alive before you risk JTAG, and gives you the U-Boot
prompt. `AST_UART1` is a **4-pin 3.3 V header** (Raptor) just above the AST2050,
ordered **+3.3 V / TX / RX / GND** (ends fixed by Raptor's photo; confirm the two
middle TX/RX pins by probing — see [`HEADER-PINOUTS.md`](HEADER-PINOUTS.md)). ✅
3.3 V TTL, **115200 8N1**; press **Delete** within 3 s of U-Boot start to drop
to the bootloader. **Leave the +3.3 V pin unconnected**; cross TX↔RX:

| AST_UART1 | RPi4 |
|---|---|
| +3.3 V | — (do NOT connect) |
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

> This header is the AST2050's **UART1**, an NS16550 at `0x1e783000` (UART2 is
> `0x1e784000`) per Raptor's U-Boot `ast2050.h` — handy if you later poke the
> UART registers over JTAG.

---

## 4. BMC_FW1 / BMC SPI flash — flashrom, not OpenOCD

`BMC_FW1` **is** the AST2050's socketed SPI boot-flash socket — confirmed from
the schematic, not a guess. The pinout (2×7 DIP, SPI bus + straps) is documented
in [`schematic-wiring/BMC-CONNECTORS.md`](schematic-wiring/BMC-CONNECTORS.md):
CS0=pin12, CLK=pin8, MOSI=pin1, MISO=pin6, GND=pin13, `+3V3_AUX`=pin2. The
board-off continuity check is now only a sanity step to match the socket's
physical pin 1 to those nets before wiring.

Drive it from the Pi's **hardware SPI0** with `flashrom`
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

- **NB_JTAG_HEADER** — almost certainly the **AMD HDT** attachment port (CPU /
  northbridge debug chain). [`JTAG-HEADERS.md`](JTAG-HEADERS.md) documents the
  full **20-pin HDT+ pinout (1.27 mm pitch)** — or the older 25-pin HDT — and the
  `CPU1→CPU2→SR5690→SP5100` scan chain. ⚠️ HDT is **not OpenOCD / not
  RPi-drivable**, the 1.27 mm fine pitch won't take dupont wires, and full x86
  run-control needs a proprietary probe. Out of scope for this guide.
- **NB_DEBUG_HEADER** — unconfirmed: possibly the *second* HDT port (KGPE-D16 is
  dual-socket; Raptor says "HDT Attachment Port**s**"), or a POST/Port-80 / LPC
  debug header. **Identify the signals before connecting** anything driven.
- **TEST_CON1 / TEST_CON2** — factory/ICT test pads. Treat as unknown; probe
  before use. Not part of the OpenOCD path.

---

## 6. OpenOCD software setup

Configs live in [`openocd/`](openocd/), split adapter / SoC / board:

```bash
# On the Pi:
sudo apt install openocd            # or build a recent (>=0.12) OpenOCD
cd asus-kgpe-d16-firmware/openocd

# Step 0 (optional but cheap) — TCK->RTCK echo test, no scan involved:
# proves the AST2050 is powered + core-clocked via the RTCK monitor wire
# (GPIO27). PASS = 64/64 echoes; stuck-low = board off / RTCK unrouted /
# wire missing. Never run while OpenOCD is attached (exclusive GPIO claims).
python3 rtck-echo-test.py          # on the Pi (or: uv run rtck-echo-test.py)

# First contact — discover the real IDCODE (board powered, BMC at reset):
openocd -f rpi4-jtag.cfg -f ast2050.cfg -c "init; scan_chain; shutdown"
```

Expect IDCODE `0x07926f0f` (Raptor-confirmed on this AST2050). A scan of
**"all ones"** with IR capture `0x0f` means the harness/target is not
connected (TDO floating high) — that exact output on an *unwired* Pi is the
adapter-side smoke test passing. Then run the full board stack:

```bash
openocd -f rpi4-jtag.cfg -f kgpe-d16-bmc.cfg
# (kgpe-d16-bmc.cfg sources ast2050.cfg — do NOT also pass -f ast2050.cfg,
#  or OpenOCD aborts with "Command/target: ast2050.cpu Exists".)
# in another terminal:
telnet localhost 4444      # OpenOCD console → halt, reg, mdw, etc.
```

No `sudo` needed when the user is in the `gpio` group (the `claude`/`tim`
users on the bridge Pi are — verified: `linuxgpiod` claims the lines fine).

**Driver choice:** the configs use **`linuxgpiod`** (libgpiod char-dev) — the
robust choice on RPi4, no peripheral-base juggling. Note `linuxgpiod`
**ignores `adapter speed`** ("doesn't support configurable speed"); its
syscall-bound bit-bang is inherently slow, which is safe for bring-up. A
`bcm2835gpio` fallback is commented in `rpi4-jtag.cfg` (that one does honour
speed settings); if you use it, the BCM2711 peripheral base is
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
  module slot; page + all linked PDFs mirrored in-repo:
  [ASUS-KGPE-D16.md](ASUS-KGPE-D16.md),
  [datasheets/15H-ORG-MIRROR.md](datasheets/15H-ORG-MIRROR.md)):
  <https://15h.org/index.php/ASUS_KGPE-D16>
- 15h.org — ASUS KCMA-D8 (Socket-C32 sibling, same AST2050/ASMB module and
  chipset family; mirrored in-repo: [ASUS-KCMA-D8.md](ASUS-KCMA-D8.md)):
  <https://15h.org/index.php/ASUS_KCMA-D8>
- Raptor Engineering — `ast2050-flashrom` (AST2050 SPI flashing):
  <https://github.com/raptor-engineering/ast2050-flashrom>
- iosoft.blog — Raspberry Pi as OpenOCD bit-bang adapter (bcm2835gpio pin
  mapping, peripheral bases): <https://iosoft.blog/2019/01/28/raspberry-pi-openocd/>
- OpenOCD User's Guide — ARM926EJ-S target, `adapter gpio`, TAP declaration:
  <https://openocd.org/doc/html/>

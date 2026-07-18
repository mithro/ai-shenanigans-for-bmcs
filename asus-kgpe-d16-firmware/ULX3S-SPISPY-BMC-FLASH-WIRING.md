# Wiring the ULX3S (spispy) to emulate the AST2050 BMC boot flash

How to connect a **ULX3S ECP5** board running [spispy](https://github.com/osresearch/spispy)
to the ASUS KGPE-D16 so the FPGA *becomes* the SPI-NOR flash that the ASPEED
**AST2050** BMC boots from — replacing the socketed firmware flash in the
`BMC_FW1` socket. This lets us serve arbitrary BMC firmware images over USB
without erase/reflash cycles, and single-step the boot ROM's flash accesses.

> **The `BMC_FW1` pinout is fully documented** from the board schematic — see
> [`schematic-wiring/BMC-CONNECTORS.md`](schematic-wiring/BMC-CONNECTORS.md) and
> [`schematic-wiring/AST2050-BMC-WIRING.md` §4](schematic-wiring/AST2050-BMC-WIRING.md#4-spi-firmware-flash--bmc_fw1),
> which are the authoritative source for the socket pinout used below.

> **Status legend:** ✅ = verified against a cited primary source (schematic
> pinmap, datasheet figure, spispy source line); 🔶 = derived / to confirm on the
> bench during bring-up.

Companion docs:
[`schematic-wiring/BMC-CONNECTORS.md`](schematic-wiring/BMC-CONNECTORS.md) (the
`BMC_FW1` socket pinout) ·
[`schematic-wiring/AST2050-BMC-WIRING.md`](schematic-wiring/AST2050-BMC-WIRING.md)
(AST2050 SPI/ROM controller balls) ·
[`HARDWARE-ACCESS.md`](HARDWARE-ACCESS.md) (the ULX3S is already attached to the
ASUS Pi bridge) ·
[`datasheets/README.md`](datasheets/README.md) (flash part family).

---

## 1. Topology — `BMC_FW1` is the socketed boot flash

The AST2050 boots from a **socketed SPI flash carrier** in the `BMC_FW1` socket,
driven directly by the SoC's SPI/ROM controller. The chip is field-replaceable,
and the socket's pinout — SPI bus plus three feature-strap lines the BMC samples
— is documented from the schematic. ✅

```
        AST2050 SPI/ROM controller (QU1)          BMC_FW1 socket (2×7 DIP)
      ┌───────────────────────────────┐         ┌────────────────────────┐
      │ AST_SPICLK  (Y2 / ROMD0) ──────┼── pin 8 ┤ SCK                    │
      │ AST_SPIDO   (Y1 / ROMD1) ──────┼── pin 1 ┤ MOSI  (SoC → flash)    │
      │ AST_SPIDI   (AA4 / ROMD2)◄─────┼── pin 6 ┤ MISO  (flash → SoC)    │
      │ AST_SPICS#0 (AB9 / ROMCS0#)────┼── pin12 ┤ CS0   (main firmware)  │
      │ AST_SPICS#2 (W7 / ROMCS2#) ────┼── pin 4 ┤ CS2   (2nd / recovery) │
      └───────────────────────────────┘         │ +3V3_AUX  pin 2        │
        feature straps the BMC samples:          │ GND       pin13        │
          AST_IKVMEN#  (W1)  ── pin 3            └────────────────────────┘
          BMC_PRESENT# (…)   ── pin 7
          AST_SOLEN#   (W2)  ── pin10
```

**Emulation method:** power the board off, **remove the socketed flash carrier**,
and plug the ULX3S into the documented socket pins (via a DIP-adapter or flying
leads keyed to socket pin 1). The AST2050's boot SPI is present directly on the
socket — no continuity mapping, no clip, no desolder. Because the real flash is
physically removed, the emulator is the sole device on the bus.

---

## 2. `BMC_FW1` socket pinout (✅ from schematic-wiring)

Reproduced from [`schematic-wiring/BMC-CONNECTORS.md`](schematic-wiring/BMC-CONNECTORS.md)
(see [`diagrams/kgpe-d16-bmc-fw1.svg`](schematic-wiring/diagrams/kgpe-d16-bmc-fw1.svg)
for the physical 2×7 layout and pin-1 location):

| Pin | Net | Function | AST2050 ball |
|---|---|---|---|
| 1  | `AST_SPIDO`   | SPI **MOSI** (data out of SoC) | `Y1` (`ROMD1`) |
| 2  | `+3V3_AUX`    | Flash power (standby) | — |
| 3  | `AST_IKVMEN#` | Strap: enable iKVM | `W1` |
| 4  | `AST_SPICS#2` | SPI chip-select 2 (2nd device / recovery) | `W7` (`ROMCS2#`) |
| 6  | `AST_SPIDI`   | SPI **MISO** (data in to SoC) | `AA4` (`ROMD2`) |
| 7  | `BMC_PRESENT#`| Strap: BMC/carrier present (also SOL-mux select) | `A10`/`D11`/`AA9` |
| 8  | `AST_SPICLK`  | SPI **clock** | `Y2` (`ROMD0`) |
| 10 | `AST_SOLEN#`  | Strap: enable Serial-over-LAN | `W2` |
| 12 | `AST_SPICS#0` | SPI **chip-select 0** (main firmware) | `AB9` (`ROMCS0#`) |
| 5, 9, 11 | — | NC | — |
| 13 | `GND` | Ground | — |

The AST2050 boots the **main firmware over CS0** (pin 12). CS2 (pin 4) is a
second/recovery device and is left unconnected for main-boot emulation.

---

## 3. The ULX3S / spispy side (✅ verified from source)

spispy assigns the emulated-flash SPI to the ULX3S **left header J1**, pins
`gp[7]`–`gp[10]`. From `verilog/spispy.v` (the pin `wire` declarations) and
`verilog/ulx3s_v20.lpf` (the `LOCATE`/`IOBUF` constraints):

| spispy signal | net | FPGA ball | ULX3S J1 pin | Direction *(FPGA POV)* | IO standard |
|---|---|---|---|---|---|
| **CS#** (chip select in) | `gp[7]`  | `A6` | **J1 · GP7**  | input  (pull-up) | LVCMOS33 ✅ |
| **SCK** (clock in)       | `gp[8]`  | `A4` | **J1 · GP8**  | input  | LVCMOS33 ✅ |
| **MOSI** (data in)       | `gp[9]`  | `A2` | **J1 · GP9**  | input  | LVCMOS33 ✅ |
| **MISO** (data out)      | `gp[10]` | `C4` | **J1 · GP10** | **output** (FPGA drives) | LVCMOS33 ✅ |
| GND | — | — | J1 GND pin | — | — |

Pins are named by their **`GP` silkscreen label** (not a bare 1–40 number, which
differs between female-angled and male-vertical headers — see §3.1). Optional
debug taps (`verilog/spispy.v`): `gn[19]`=`SCK` echo (J2 · GN19), `gn[20]`=`CS#`
echo (J2 · GN20), `gn[15]`=asserted on any non-`0x03` read (J2 · GN15).

**All four wired connections are `GP7`–`GP10`, contiguous on header J1** — plus a
ground. The J2 pins are only optional scope/debug taps.

### 3.1 Complete J1 / J2 header map (physical layout)

Both `J1` and `J2` are `CONN_02X20` (**2×20, 40-pin**) 2.54 mm headers. Every net
and pin below is from the **v3.0.8 schematic** (`doc/schematics_v308.pdf`,
`gpio.sch`); FPGA balls from `ulx3s_v20.lpf`. `★` = spispy signal you wire; `◦` =
optional debug tap.

> **Wire by the `GP`/`GN` silkscreen label + FPGA ball — that is unambiguous.**
> The 1–40 pin numbers below are the schematic's **female 90° angled** numbering.
> The schematic warns: *"for a MALE VERTICAL header, SWAP EVEN and ODD pin
> numbers"* — so e.g. `GP7` prints as **pin 24** on a female-angled header but
> **pin 23** on a male-vertical one (which is what `ulx3s_v20.lpf`'s `J1_23`
> notation uses). Because of that ambiguity, match the **`GP7`/`GP8`/… label**,
> not a bare pin number, and confirm against the board silkscreen + a meter.

Layout: the **odd-pin row carries `GN`**, the **even-pin row carries `GP`**
(female-angled). Power/GND sit at both ends and the two mid-breaks.

![Annotated ULX3S top view — the spispy SPI pins GP7–GP10 on header J1](diagrams/ulx3s-spispy-j1-annotated.png)

*The four wired SPI pins (`GP7`=CS#, `GP8`=SCK, `GP9`=MOSI, `GP10`=MISO) are the
`7`–`10` block on the lower-left header `J1`, with a GND pair (schematic 21/22)
just above `GP7`. `J2` (right edge) carries only the optional debug taps. Wire the
`GP` ("+") column — see the table above and the board's own "+ −" legend by pin
`11`. Base photo: ULX3S v3.0.3 top from the open-source-hardware `emard/ulx3s`
repo (`pic/ULX3S_v303_top.png`); regenerate with
[`diagrams/make-ulx3s-spispy-annotated.py`](diagrams/make-ulx3s-spispy-annotated.py).*

**Header J1 — `GP`/`GN` 0–13 (carries all four wired spispy signals):**

| Odd pin | `GN` row | | Even pin | `GP` row |
|--:|---|---|--:|---|
| 1 | +3V3 | | 2 | +3V3 |
| 3 | GND | | 4 | GND |
| 5 | GN0 (C11) | | 6 | GP0 (B11) |
| 7 | GN1 (A11) | | 8 | GP1 (A10) |
| 9 | GN2 (B10) | | 10 | GP2 (A9) |
| 11 | GN3 (C10) | | 12 | GP3 (B9) |
| 13 | GN4 (A8) | | 14 | GP4 (A7) |
| 15 | GN5 (B8) | | 16 | GP5 (C8) |
| 17 | GN6 (C7) | | 18 | GP6 (C6) |
| 19 | +3V3 | | 20 | +3V3 |
| 21 | **GND** | | 22 | **GND** |
| 23 | GN7 (B6) | | 24 | **★ GP7 = CS# (A6)** |
| 25 | GN8 (A5) | | 26 | **★ GP8 = SCK (A4)** |
| 27 | GN9 (B1) | | 28 | **★ GP9 = MOSI (A2)** |
| 29 | GN10 (B4) | | 30 | **★ GP10 = MISO (C4)** |
| 31 | GN11 (E3) | | 32 | GP11 (F4) |
| 33 | GN12 (F3) | | 34 | GP12 (G3) |
| 35 | GN13 (G5) | | 36 | GP13 (H4) |
| 37 | **GND** | | 38 | **GND** |
| 39 | +3V3 | | 40 | +3V3 |

The SPI **ground return** goes to a J1 GND pin — **21/22** (adjacent to the SPI
block) or **37/38** are the handy ones.

**Header J2 — `GP`/`GN` 14–27 (only optional debug taps; also the 5 V pins):**

| Odd pin | `GN` row | | Even pin | `GP` row |
|--:|---|---|--:|---|
| 1 | +3V3 | | 2 | +3V3 |
| 3 | GND | | 4 | GND |
| 5 | GN14 (U17) | | 6 | GP14 (U18) |
| 7 | **◦ GN15 (P16) = read≠0x03** | | 8 | GP15 (N17) |
| 9 | GN16 (M17) | | 10 | GP16 (N16) *(TOCTOU, unused)* |
| 11 | GN17 (L17) | | 12 | GP17 (L16) |
| 13 | GN18 (H17) | | 14 | GP18 (H18) |
| 15 | **◦ GN19 (G18) = SCK echo** | | 16 | GP19 (F17) |
| 17 | **◦ GN20 (E17) = CS# echo** | | 18 | GP20 (D18) |
| 19 | +3V3 | | 20 | +3V3 |
| 21 | GND | | 22 | GND |
| 23 | GN21 (D17) | | 24 | GP21 (C18) |
| 25 | GN22 (C15) | | 26 | GP22 (B15) |
| 27 | GN23 (C17) | | 28 | GP23 (B17) |
| 29 | GN24 (D16) | | 30 | GP24 (C16) |
| 31 | GN25 (E14) | | 32 | GP25 (D14) |
| 33 | GN26 (C13) | | 34 | GP26 (B13) |
| 35 | GN27 (E13) | | 36 | GP27 (D13) |
| 37 | GND | | 38 | GND |
| 39 | **+5V** (IN5V) | | 40 | **+5V** (OUT5V) |

> **⚠️ Ground & power:** the `GN` (odd) row pins are FPGA **signals, not ground**.
> Only J2 pins **39/40 are 5 V** — the GPIO pins are **not** 5 V tolerant, so keep
> those clear of the signal jumpers (J1 has no 5 V; its 39/40 are +3V3). Take the
> SPI ground from a silkscreen-marked GND pin and meter-check it before wiring.

spispy defaults to pure **emulation** (`ENABLE_EMULATION=1`,
`ENABLE_TOCTOU=0`) — the FPGA is the only device on the bus, which is exactly our
"carrier removed" case, so the real-chip-reset / TOCTOU pins (`gp[11]`/`gp[16]`)
are unused. `wifi_gpio0` is tied high in the gateware so the board won't reboot.

Direction sanity check: the master (AST2050) **drives** CS#, SCK, MOSI and
**reads** MISO. So on the emulator, CS#/SCK/MOSI are **inputs** and MISO
(`gp[10]`) is the **only** output. Getting MISO backwards is the classic failure.

---

## 4. Wiring table — ULX3S ↔ `BMC_FW1` (✅ fully specified)

| Signal | ULX3S J1 pin (`gp[]`) | `BMC_FW1` pin | `BMC_FW1` net (AST ball) |
|---|---|---|---|
| MOSI (SoC → emu) | J1 · GP9 (`gp[9]`)  | **1**  | `AST_SPIDO` (`Y1`) |
| MISO (emu → SoC) | J1 · GP10 (`gp[10]`) | **6**  | `AST_SPIDI` (`AA4`) |
| SCK              | J1 · GP8 (`gp[8]`)  | **8**  | `AST_SPICLK` (`Y2`) |
| CS# (main)       | J1 · GP7 (`gp[7]`)  | **12** | `AST_SPICS#0` (`AB9`) |
| GND              | J1 GND pin          | **13** | `GND` |

Leave `BMC_FW1` pin 4 (`AST_SPICS#2`) unconnected for main-firmware emulation.
Do **not** drive pin 2 (`+3V3_AUX`) — see §5. Straps (pins 3/7/10) — see §5.

---

## 5. Feature straps & power — reproduce what the carrier asserted

Removing the flash carrier also removes whatever it tied on the three strap
pins. The AST2050 **samples these at boot**, so the ULX3S adapter must reproduce
the states the BMC needs:

| Pin | Net | Reproduce as | Effect |
|---|---|---|---|
| 7  | `BMC_PRESENT#` | tie **low** (to GND) | tells the BMC a firmware device is present; also selects the SOL mux 🔶 |
| 3  | `AST_IKVMEN#`  | low = enable iKVM (optional) | leave open if iKVM not wanted 🔶 |
| 10 | `AST_SOLEN#`   | low = enable Serial-over-LAN (optional) | leave open if SOL not wanted 🔶 |

All three are active-low (`#`). Start by tying **`BMC_PRESENT#` low** and leaving
`AST_IKVMEN#`/`AST_SOLEN#` open; add those only if you need the features. Confirm
against a known-good boot and adjust — the exact pull the OEM carrier applied is
the thing to match. 🔶

**Power:** `+3V3_AUX` (pin 2) is a mainboard-supplied standby rail feeding the
(now absent) flash. The emulator does **not** need it and must **not** back-drive
it — leave it unconnected to the ULX3S. Optionally sense it as a bank Vref only
if you remove ULX3S `RV3` (spispy's auto-voltage note); for this 3.3 V target you
can keep `RV3` and run the `gp[]` bank at its own 3.3 V.

---

## 6. Electrical rules — read before powering on

1. **Single MISO driver.** With the carrier removed the emulator is the only SO
   driver — good. Never leave the real flash carrier seated while the ULX3S also
   drives MISO (pin 6 / `gp[10]`): two drivers on one net risks damage.
2. **Voltage: 3.3 V, compatible.** AST2050 SPI I/O is 3.3 V; the ULX3S `gp[]`
   bank is `LVCMOS33`. No level shifting needed.
3. **Common ground first.** Bond ULX3S GND to `BMC_FW1` pin 13 **before** any
   signal, and keep it for the whole session. A floating ground corrupts every
   SPI edge.
4. **Do not source/back-drive `+3V3_AUX`** (pin 2). See §5.
5. **Keep leads short.** Flying-lead SPI is the weak link — use the shortest
   practical jumpers (≤10 cm), keep a ground return near the clock, and route
   CS#/SCK away from MOSI/MISO. If reads are flaky, lower the AST2050 SMC clock
   (SCU/SMC divisor) before blaming the gateware.
6. **Board OFF while (dis)connecting.** Power the KGPE-D16 down (Tasmota
   `au-plug-10`, [`HARDWARE-ACCESS.md`](HARDWARE-ACCESS.md)) before removing the
   carrier or connecting the ULX3S harness. Don't hot-plug SPI.

---

## 7. Bring-up / verification sequence

1. Board **OFF**. Remove the socketed flash carrier from `BMC_FW1`.
2. Wire ULX3S `GP7`/`GP8`/`GP9`/`GP10` + a J1 GND to `BMC_FW1` pins 12/8/1/6/13
   respectively (CS#/SCK/MOSI/MISO/GND per §4), and tie `BMC_PRESENT#` (pin 7) low
   per §5. Double-check MISO (`GP10` → pin 6) is the only emulator output.
3. Load the spispy bitstream onto the ULX3S (see `SPISPY-SETUP.md`, forthcoming)
   and preload a known-good BMC image into the emulator's RAM over USB.
4. Power the board ON. On the ULX3S scope taps (§3), confirm CS# toggles and SCK
   runs — proof the SMC is clocking the emulated flash.
5. Confirm the BMC boots the served image: BMC console on
   `/dev/serial-bmc-console` (1200 8N1) and/or P2A/JTAG
   ([`HARDWARE-ACCESS.md`](HARDWARE-ACCESS.md)). Booting our image from the
   emulator — with no physical reflash — is the success criterion.
6. If the SMC never reads (step 4), re-check `BMC_PRESENT#` and the strap states
   (§5) — the BMC may be gating boot on them.

---

## Evidence / sources

- **`BMC_FW1` socket pinout** (nets, functions, AST2050 balls) —
  [`schematic-wiring/BMC-CONNECTORS.md`](schematic-wiring/BMC-CONNECTORS.md)
  (`BMC_FW1 — BMC SPI firmware socket`) and
  [`schematic-wiring/AST2050-BMC-WIRING.md` §4](schematic-wiring/AST2050-BMC-WIRING.md#4-spi-firmware-flash--bmc_fw1),
  both schematic-derived (PR #29).
- **ULX3S spispy pins** — `osresearch/spispy` `verilog/spispy.v`
  (`spi_cs_pin=gp[7]` … `spi_miso_pin=gp[10]`) and `verilog/ulx3s_v20.lpf`
  (`LOCATE gp[7]→A6` … `gp[10]→C4`; all `IO_TYPE=LVCMOS33`).
- **ULX3S J1/J2 header layout, power/GND/5V pins, and the female-angled vs
  male-vertical pin-numbering caveat** — the ULX3S **v3.0.8 schematic**
  `emard/ulx3s` `doc/schematics_v308.pdf`, sheet `gpio.sch` (`J1`/`J2`
  `CONN_02X20`); board photos at <https://www.crowdsupply.com/radiona/ulx3s>.
- **Flash part family** (S25FL128P / M25P128 / MX25L12835F / … , 16 MB class) —
  [`datasheets/README.md`](datasheets/README.md); the AST2050 boot ROM
  autodetects the JEDEC ID, which spispy must present.
- **Rig / power / consoles** — [`HARDWARE-ACCESS.md`](HARDWARE-ACCESS.md).

# Wiring the ULX3S (spispy) to emulate the AST2050 BMC boot flash

How to connect a **ULX3S ECP5** board running [spispy](https://github.com/osresearch/spispy)
to the ASUS KGPE-D16 so the FPGA *becomes* the SPI-NOR flash that the ASPEED
**AST2050** BMC boots from — replacing the physical flash on the ASMB4/ASMB5
management module. This lets us serve arbitrary BMC firmware images over USB
without erase/reflash cycles, and single-step the boot ROM's flash accesses.

> **Status of facts below:** ✅ = verified against a cited primary source
> (datasheet figure, spispy source line, in-repo measurement); 🔶 = derived /
> partially confirmed; ⚠️ = **unverified — must be probed on the bench before
> wiring**. Read the whole "Open questions" section before connecting anything.

Companion docs:
[`HEADER-PINOUTS.md`](HEADER-PINOUTS.md) (BMC_FW1 connector, ASMB module, the
2.00 mm pitch finding) · [`HARDWARE-ACCESS.md`](HARDWARE-ACCESS.md) (the ULX3S
is already attached to the ASUS Pi bridge) ·
[`datasheets/S25FL128P_Datasheet.pdf`](datasheets/S25FL128P_Datasheet.pdf) (the
flash on the module) ·
[`datasheets/README.md`](datasheets/README.md) (SoC↔flash topology).

---

## 1. Topology — why the SPI bus crosses BMC_FW1

The AST2050 SoC is soldered to the **mainboard** (Raptor solders `AST_JTAG1` to
the mainboard, and 15h.org confirms the SoC is onboard). The BMC **boot flash is
on the ASMB module** — the ServeTheHome photo of the ASMB4-iKVM shows a Spansion
**S25FL128P** (marked `FL128P`) SO-16 on the module, and 15h.org states the
AST2050's management features "are only activated when a firmware module (ASMB4
or ASMB5) is attached." ✅

Therefore the SoC's SPI Master Controller (SMC, `0x16000000`, XIP-mapped at
`0x14000000` — see [`datasheets/README.md`](datasheets/README.md)) reaches its
boot flash **through the BMC_FW1 connector**:

```
   MAINBOARD                      BMC_FW1                ASMB4/5 MODULE
 ┌───────────────┐            (2×8, 2.00 mm)          ┌──────────────────┐
 │  AST2050 SMC  │  CS# ─────────●  ●───────────────► │ S25FL128P  CS# 7 │
 │  (SPI master) │  SCK ─────────●  ●───────────────► │ (SO-16)   SCK 16 │
 │               │  SI  ─────────●  ●───────────────► │           SI  15 │
 │               │  SO  ◄────────●  ●─────────────────│           SO   8 │
 │               │  VCC ─────────●  ●─── 3V3 rail ───►│           VCC  2 │
 │               │  GND ─────────●  ●───────────────► │           GND 10 │
 └───────────────┘            (other module pins:     └──────────────────┘
                              iKVM enable? straps?  ⚠️ — see §6)
```

**Consequence:** pulling the ASMB module exposes the SoC's boot-SPI at the
BMC_FW1 connector. That is the emulation tap point — the ULX3S plugs in where the
module's flash used to be, and the AST2050 can't tell the difference.

⚠️ The **exact BMC_FW1 pin assignment is NOT published** (ASUS documents only the
connector location and pin 1 — see [`HEADER-PINOUTS.md`](HEADER-PINOUTS.md)). §4
gives the bench procedure to derive it; do not guess it.

---

## 2. The ULX3S / spispy side (✅ verified from source)

spispy assigns the emulated-flash SPI to the ULX3S **left header J1**, pins
`gp[7]`–`gp[11]`. From `verilog/spispy.v` (the pin `wire` declarations) and
`verilog/ulx3s_v20.lpf` (the `LOCATE`/`IOBUF` constraints):

| spispy signal | net | FPGA ball | ULX3S J1 pin | Direction *(FPGA point of view)* | IO standard |
|---|---|---|---|---|---|
| **CS#** (chip select in) | `gp[7]`  | `A6` | **J1_23** | input  (pull-up, DRIVE=4) | LVCMOS33 ✅ |
| **SCK** (clock in)       | `gp[8]`  | `A4` | **J1_25** | input  | LVCMOS33 ✅ |
| **MOSI / SI** (data in)  | `gp[9]`  | `A2` | **J1_27** | input  | LVCMOS33 ✅ |
| **MISO / SO** (data out) | `gp[10]` | `C4` | **J1_29** | **output** (FPGA drives) | LVCMOS33 ✅ |
| real-flash reset (unused here) | `gp[11]` | `F4` | J1_31 | output (pull-up) | LVCMOS33 ✅ |
| GND | — | — | any board GND pin | — | — |

Optional debug taps (drive a scope/LA; `verilog/spispy.v`): `gn[19]`=`SCK` echo
(J2_15), `gn[20]`=`CS#` echo (J2_17), `gn[15]`=asserted on any non-`0x03` read
command (J2_7). Not required for operation.

Notes from `verilog/spispy.v`:
- Default mode is pure **emulation** (`ENABLE_EMULATION=1`, `ENABLE_TOCTOU=0`) —
  the FPGA is the *only* device on the bus. This is exactly our "module removed"
  case, so `gp[11]`/`gp[16]` (the real-chip reset / TOCTOU-CS pins) are unused.
- `wifi_gpio0` is tied high in the gateware so the board does not reboot; leave
  it be.

Direction sanity check (flash's frame of reference): the master **drives** CS#,
SCK, SI and **reads** SO. So MOSI/SI (`gp[9]`) and SCK (`gp[8]`) and CS#
(`gp[7]`) are **inputs** to the emulator, and MISO/SO (`gp[10]`) is the **only**
line the emulator drives. Getting MISO backwards is the classic failure mode.

---

## 3. The flash side — S25FL128P SO-16 (✅ verified from datasheet Fig. 2.1)

Serial-mode signals only (the `PO[7:0]` pins are parallel-mode and are **not**
used by the AST2050's serial boot):

```
             S25FL128P — 16-pin SO (top view, pin 1 dot top-left)
                        ┌────────┐
              HOLD#  1 ─┤        ├─ 16  SCK
                VCC  2 ─┤        ├─ 15  SI   (MOSI, master→flash)
                 NC  3 ─┤        ├─ 14  PO6
                PO2  4 ─┤        ├─ 13  PO5
                PO1  5 ─┤        ├─ 12  PO4
                PO0  6 ─┤        ├─ 11  PO3
                CS#  7 ─┤        ├─ 10  GND
            SO/PO7  8 ─┤        ├─  9  WP#/ACC
                        └────────┘
```

| Flash signal | SO-16 pin | Role in serial boot |
|---|---|---|
| **CS#** | **7**  | chip select (active low) ✅ |
| **SO** (MISO) | **8** | data out, flash → master ✅ |
| **WP#/ACC** | **9** | write-protect — hold **high** (see §5) ✅ |
| **GND** | **10** | ground ✅ |
| **SI** (MOSI) | **15** | data in, master → flash ✅ |
| **SCK** | **16** | serial clock ✅ |
| **HOLD#** | **1** | hold — must be **high** for normal operation ✅ |
| **VCC** | **2** | 3.0 V supply ✅ |
| NC / PO0..PO6 | 3,4,5,6,11,12,13,14 | not used in serial mode |

SPI mode: **Mode 0 or Mode 3**, data latched on SCK rising, output on SCK
falling; serial READ (`0x03`) up to 40 MHz, FAST_READ (`0x0B`) up to 104 MHz
(datasheet §6, §19). ✅ The AST2050 boots via `0x03`/`0x0B` at a much lower SMC
clock, well within range.

---

## 4. Wiring table + deriving the BMC_FW1 pinout

The four SPI signals map straight through: **ULX3S ↔ flash signal** is fixed
(§2 + §3); the middle column — **which BMC_FW1 pin** each signal appears on — is
what you must measure.

| Signal | ULX3S J1 pin (`gp[]`) | S25FL128P pin | **BMC_FW1 pin** |
|---|---|---|---|
| CS#  | J1_23 (`gp[7]`)  | 7  | ⚠️ TBD by continuity |
| SCK  | J1_25 (`gp[8]`)  | 16 | ⚠️ TBD by continuity |
| MOSI | J1_27 (`gp[9]`)  | 15 | ⚠️ TBD by continuity |
| MISO | J1_29 (`gp[10]`) | 8  | ⚠️ TBD by continuity |
| GND  | J1 GND           | 10 | ⚠️ TBD by continuity (verify ≥1 GND pin) |
| (VCC ref, optional) | — | 2 | ⚠️ TBD — do **not** drive; see §5 |

### Deriving the map (board OFF, module in hand)

The ASMB module is the Rosetta stone: it physically wires each BMC_FW1 contact
to a flash pad. With a multimeter in continuity mode:

1. Remove the ASMB module from the board. Work on the **module**, not the live
   mainboard.
2. Identify the S25FL128P pin 1 (package dot / bevel) and number pins per §3.
3. For each flash serial pin (7, 8, 15, 16, 2, 10, and 1/9), beep from the flash
   pad to every BMC_FW1 contact until you find the mating pin. Record it.
4. Cross-check: exactly one BMC_FW1 pin should ring out per flash pad; VCC (2)
   and GND (10) may ring to several (power/ground planes) — that's expected.
5. Fill the table above and **commit the measured pinout** back into this doc
   (promote the ⚠️ rows to ✅ with "measured YYYY-MM-DD").

This simultaneously gives us the evidence-backed BMC_FW1 pinout that
[`HEADER-PINOUTS.md`](HEADER-PINOUTS.md) currently lists as "signals
proprietary."

### Alternative tap: SOIC-16 clip on the module flash

If you prefer not to derive the connector map, clip a **SOIC-16 test clip**
(e.g. Pomona 5252) directly onto the S25FL128P on the module and wire per §3.
**But** then the real flash is still on the bus and will fight the emulator on
MISO — you must disable it (desolder it, lift its VCC pin, or hold CS# — spispy's
TOCTOU mode, `gp[16]`, exists for the no-pull-up case). The clean approach is the
BMC_FW1 tap with the module's flash absent; prefer it.

---

## 5. Electrical rules — read before powering on

1. **Only ONE device may drive MISO.** In the BMC_FW1-tap topology the module's
   flash is physically absent, so the emulator is the sole SO driver — good. If
   you instead clip onto a populated flash, you **must** disable that flash
   (§4) or both chips will drive J1_29 and you'll get bus contention (possible
   damage). ✅ spispy defaults to `ENABLE_TOCTOU=0` = "I am the only device."
2. **Voltage: 3.3 V, compatible.** The AST2050 SPI I/O is 3.3 V; the ULX3S
   `gp[]` bank is `LVCMOS33` (§2). No level shifting needed. spispy's header
   comment suggests desoldering **RV3** so the flash-side I/O bank auto-selects
   its voltage (and warns the LEDs on that bank then stay dark). For a **3.3 V**
   target you may keep RV3 and leave the bank at 3.3 V (LEDs work); only remove
   RV3 if you later target a 1.8 V flash rail. 🔶
3. **Common ground first.** Bond ULX3S GND to a BMC_FW1 GND pin **before**
   connecting any signal, and keep it connected the whole session. A floating
   ground between the two boards corrupts every SPI edge.
4. **Do not source VCC from the ULX3S.** The flash-rail VCC at BMC_FW1 is a
   mainboard-supplied 3V3 (likely standby). The emulator does not need it and
   must not back-drive it. Leave BMC_FW1 VCC unconnected to the ULX3S (optionally
   use it *only* as a bank Vref if RV3 is removed).
5. **HOLD# / WP#.** These are inputs to a *real* flash; the emulator has no such
   pins and simply doesn't implement them. With the module absent they are the
   SoC-side lines — if the AST2050 does not pull them high itself, tie the
   corresponding BMC_FW1 pins to 3V3 so a stray low can't wedge the (conceptual)
   bus. Verify with a scope during a boot attempt. 🔶
6. **Keep leads short.** Flying-lead SPI over a 2.00 mm header is the weak link.
   Use the shortest practical jumpers (≤10 cm), pair each signal with a ground
   return if you can, and route CS#/SCK away from MOSI/MISO. If reads are flaky,
   lower the AST2050 SMC clock (SCU/SMC divisor) before blaming the gateware.
7. **Board OFF while (dis)connecting.** Power the KGPE-D16 down (Tasmota
   `au-plug-10`, see [`HARDWARE-ACCESS.md`](HARDWARE-ACCESS.md)) before inserting
   or removing the ULX3S harness or the ASMB module. Hot-plugging SPI risks both
   boards.

---

## 6. Open questions — confirm on the bench (⚠️)

1. **Does BMC_FW1 carry a "BMC/ARM enable" or module-presence strap?** 15h.org
   says the AST2050 management core is *activated* by the module. If presenting
   valid SPI with the module absent is **not** sufficient to make the SoC boot
   its ARM core, the module must also be asserting an enable/strap/reset line.
   During bring-up, scope CS#/SCK at the connector after power-on: if the SMC
   never issues a `0x03`/`0x0B` read, a strap is missing — probe the remaining
   BMC_FW1 pins on the module for a static level tied to the AST2050's
   enable/reset and reproduce it.
2. **Full BMC_FW1 pinout beyond SPI.** We only need the 4 SPI + GND (+ maybe the
   enable from Q1). The rest (iKVM NIC, PS/2 passthrough, LEDs) are irrelevant to
   flash emulation and should be left unconnected.
3. **Which flash part / geometry the vendor firmware expects.** Raptor's U-Boot
   autodetects M25P64 / M25P128 / **S25FL128P** / MX25L12835F / W25X64
   ([`datasheets/README.md`](datasheets/README.md)). spispy must present the
   right SFDP/JEDEC ID and size (16 MB for the S25FL128P) — a gateware/host
   config concern, tracked separately from wiring.

---

## 7. Bring-up / verification sequence

1. Board **OFF**. Remove ASMB module. Derive + record the BMC_FW1 SPI map (§4).
2. Wire ULX3S J1_23/25/27/29 + GND to the mapped BMC_FW1 pins (§4). Double-check
   MISO (J1_29) is the *only* emulator output.
3. Load the spispy bitstream onto the ULX3S (see the separate spispy
   build/flash setup — `SPISPY-SETUP.md`, forthcoming) and preload a known-good
   BMC image into the emulator's RAM over USB.
4. Power the board ON. On the ULX3S scope taps (§2), confirm CS# toggles and SCK
   runs — proof the SMC is clocking the emulated flash.
5. Confirm the BMC actually boots the served image: BMC console on
   `/dev/serial-bmc-console` (1200 8N1) and/or P2A/JTAG (see
   [`HARDWARE-ACCESS.md`](HARDWARE-ACCESS.md)). Booting our image from the
   emulator — with no physical reflash — is the success criterion.
6. If the SMC never reads (step 4), revisit Open Question 1 (enable strap).

---

## Evidence / sources

- **ULX3S spispy pins** — `osresearch/spispy` `verilog/spispy.v`
  (`spi_cs_pin=gp[7]` … `spi_miso_pin=gp[10]`) and `verilog/ulx3s_v20.lpf`
  (`LOCATE gp[7]→A6 "J1_23"` … `gp[10]→C4 "J1_29"`; all `IO_TYPE=LVCMOS33`).
- **Flash pinout** — S25FL128P datasheet (Cypress 002-00646 Rev *M) Figure 2.1
  "16-pin SO", §3 I/O descriptions, §6 SPI modes, §19 AC characteristics —
  [`datasheets/S25FL128P_Datasheet.pdf`](datasheets/S25FL128P_Datasheet.pdf).
- **SoC↔module↔flash topology** — [`datasheets/README.md`](datasheets/README.md)
  (SMC `0x16000000` → BMC_FW1 → S25FL128P), 15h.org KGPE-D16 (module activates
  the BMC), ServeTheHome ASMB4-iKVM photo (S25FL128P on the module).
- **BMC_FW1 connector** (2×8, **2.00 mm pitch**, pin 1 only published, signals
  proprietary) — [`HEADER-PINOUTS.md`](HEADER-PINOUTS.md) and the pitch
  measurement recorded there.
- **Rig / power / consoles** — [`HARDWARE-ACCESS.md`](HARDWARE-ACCESS.md).

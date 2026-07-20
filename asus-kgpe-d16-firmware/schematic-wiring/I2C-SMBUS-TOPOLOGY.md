# ASUS KGPE-D16 — complete I²C / SMBus / PMBus topology

Every I²C / SMBus / PMBus connection on the board: all masters, muxes, sensors,
EEPROMs, GPIO expanders, voltage regulators and connectors, with 7-bit addresses
and a topology diagram per bus. Extracted from the schematic netlist by matching
every pin whose name carries `SCL`/`SDA` and tracing each wire (through series
resistors and analog switches) to its endpoints.

Related: the BMC's own view is in
[AST2050-BMC-WIRING.md §10](AST2050-BMC-WIRING.md#10-i²c--smbus-topology-traced-through-every-mux--expander);
the southbridge's is in [SP5100-SOUTHBRIDGE-WIRING.md §9](SP5100-SOUTHBRIDGE-WIRING.md#9-smbus--ic).
This document is the board-wide superset.

> **Addresses** are the standard 7-bit device addresses from each part's
> datasheet (or JEDEC for DIMM SPD/TSOD). The schematic fixes the *wiring* and
> the strap pins; where a device's address is set by address-strap pins that is
> noted. Treat specific hex values as datasheet-derived, not read from silicon.

---

## 1. Masters

Seven I²C/SMBus-capable controllers drive buses on this board:

| Master | Ref | Buses it drives | Role |
|---|---|---|---|
| ASPEED AST2050 BMC | `QU1` | `I2C1`–`I2C8` | Out-of-band management (sensors, SPD, FRU, PSU) |
| AMD SP5100 southbridge | `SU1` | `SMBus0`–`SMBus3` + IMC GPIO | Host SMBus: VR control, in-band sensors |
| AMD SR5690 northbridge | `NU1` | PCIe hot-plug SMBus | PCIe slot hot-plug / debug |
| Winbond W83795G hwmon | `QU4` | SB-TSI / PECI (master to CPUs) | Reads CPU die temperature |
| LSI FW322 1394a | `ZU1` | private serial-EEPROM bus | Loads its own 1394 GUID/config at power-up |
| _(Super-I/O `OU1`)_ | `OU1` | `GP37`/`GP50` straps | LAN-disable straps (GPIO, not a live bus) |
| _(SP5100 `DDC1`)_ | `SU1` | `FANCURVE0/1` straps | Fan-curve select straps (GPIO, not a live bus) |

## 2. Bus inventory

| # | Bus | Master(s) | Devices | §|
|---|---|---|---|---|
| 1 | PSU SMBus | BMC `I2C1` | PSU (PMBus) | [3.1](#31-bmc-i2c1--psu-smbus-pmbus) |
| 2 | Shared platform sensor bus | BMC `I2C2/3/6` + SP5100 `SMBus1/2` | W83795G hwmon; entry to DIMM mux | [3.2](#32-shared-platform-sensor-bus-multi-master) |
| 3 | DIMM SPD/TSOD A–D | via `QU9`→`QU5` (`I2C10`) | 8 DIMM SPD + TSOD | [3.3](#33-dimm-spd--tsod-buses-via-mux) |
| 4 | DIMM SPD/TSOD E–H | via `QU9`→`QU5` (`I2C11`) | 8 DIMM SPD + TSOD | [3.3](#33-dimm-spd--tsod-buses-via-mux) |
| 5 | CPU thermal (SB-TSI) | BMC `I2C4` + W83795G | CPU0/1 SB-TSI | [3.4](#34-cpu-thermal-sb-tsi) |
| 6 | Board inventory | BMC `I2C5` | HT24LC08 EEPROM + 2× W83601G | [3.5](#35-bmc-i2c5--board-inventory--dimm-led-expanders) |
| 7 | CPU/NB VR (SVI/PMBus) | SP5100 `SMBus0` | PU2 + PU7 VR controllers | [3.6](#36-sp5100-smbus0--cpunb-voltage-regulators) |
| 8 | SP5100 `SMBus3` (LV) | SP5100 | (reserved / unpopulated) | [3.7](#37-other-segments--straps) |
| 9 | NB PCIe hot-plug SMBus | SR5690 | NB debug/hot-plug header | [3.8](#38-sr5690-northbridge--pcie-hot-plug-smbus) |
| 10 | FireWire config EEPROM | LSI FW322 | HT24LC02 EEPROM | [3.9](#39-firewire-config-eeprom-private-bus) |
| — | Fan-curve / LAN-disable straps | SP5100 / Super-I/O | (GPIO straps) | [3.7](#37-other-segments--straps) |

### Devices, sensors & addresses (all buses)

| Device | Ref | Part | Addr (7-bit) | On bus |
|---|---|---|---|---|
| Hardware monitor | `QU4` | Winbond W83795G | `0x2F` (strap `ADDR0/1`) | shared sensor bus |
| Board FRU EEPROM | `U25` | Holtek HT24LC08 (8 Kbit) | `0x54`–`0x57` (A2=VCC; base `0x50`–`0x53`) | BMC `I2C5` |
| DIMM-LED GPIO exp | `U27` | Winbond W83601G | strap `A0/A1/A2` | BMC `I2C5` |
| DIMM-LED GPIO exp | `U28` | Winbond W83601G | strap `A0/A1/A2` | BMC `I2C5` |
| DIMM SPD ×16 | `DIMM_A1…H2` | JEDEC SPD EEPROM | `0x50`–`0x57` per bank | `I2C10` / `I2C11` |
| DIMM TSOD ×16 | `DIMM_A1…H2` | JEDEC temp sensor | `0x18`–`0x1F` per bank | `I2C10` / `I2C11` |
| CPU thermal | CPU0/1 | AMD SB-TSI | `0x4C` / `0x4D` | BMC `I2C4` (via `QU4` TSI) |
| CPU0 core VR | `PU2` | UPI ASP0902QGK | PMBus (VR) | SP5100 `SMBus0` |
| CPU1/NB VR | `PU7` | UPI ASP0906QGK | PMBus (VR) | SP5100 `SMBus0` |
| FireWire EEPROM | `ZU2` | Holtek HT24LC02 (2 Kbit) | `0x50` | FW322 private bus |
| PSU | `PSUSMB1` | PMBus header | PSU-specific | BMC `I2C1` |

### Muxes / switches / buffers

| Ref | Part | Function |
|---|---|---|
| `QU9` | TI SN74CBTLV3125 | Quad FET **bus switch** — gates `I2C2↔I2C7`, `I2C8↔I2C8_SW` (enable `I2CMUX_EN#`) |
| `QU5` | 74HC4052 | Dual 4-channel analog **mux** — fans the switched bus to the two DIMM SPD banks + aux |
| `U23` | 74LVC125 | Quad buffer **source-select** — drives `QU5` `S0/S1` from BMC or SP5100 |

---

## 3. Per-bus topology

### 3.1 BMC I2C1 — PSU SMBus (PMBus)

The BMC's dedicated link to the power supply's SMBus/PMBus, for PSU telemetry
(voltages, currents, fan, status). Alert is on the BMC's `SALT1` pin (`B12`).

![PSU SMBus topology](diagrams/kgpe-d16-i2c-bus-psu.svg)

| Device | Ref | Master pins | Address |
|---|---|---|---|
| PSU SMBus | `PSUSMB1` | BMC `A15` (SDA1) / `B15` (SCL1) | PSU/PMBus-specific |

### 3.2 Shared platform sensor bus (multi-master)

The core management bus. **Both** the BMC (controllers `I2C2`, `I2C3`, `I2C6`)
and the SP5100 (`SMBus1`, `SMBus2`) are tied to a common sensor bus that reaches
the **W83795G hardware monitor** (`QU4`, `0x2F`) and the entry to the DIMM-SPD mux
(`QU9`). Ownership is arbitrated by the `U23` source-select buffer (§3.3). In
practice the BMC owns it out-of-band (host off); the SP5100/host owns it during
runtime.

![Shared sensor bus topology](diagrams/kgpe-d16-i2c-bus-sensor.svg)

| Device | Ref | Address | Provides |
|---|---|---|---|
| W83795G hardware monitor | `QU4` | `0x2F` | 11 voltage inputs, 6 temperatures (+ PECI/TSI), up to 14 fan tachs / 8 PWM |

The W83795G's own I²C is the net `83795_I2C13SCL/SDA` (pins 33/34), tied into this
bus through series resistors.

### 3.3 DIMM SPD / TSOD buses (via mux)

16 DIMM slots would collide at SPD addresses `0x50`–`0x57`, so the board splits
them into two 8-slot banks behind a switch + mux, each bank its own bus:

- **`QU9`** (SN74CBTLV3125 FET switch) bridges the BMC's `I2C2` onto the mux
  common `I2C7` when `I2CMUX_EN#` is low.
- **`QU5`** (74HC4052) routes that common to one of four channels by `S1:S0`:
  **`I2C10` = DIMM A–D (S1:S0=10)**, **`I2C11` = DIMM E–H (S1:S0=11)**,
  `I2C8` = aux panel (`00`).
- **`U23`** drives `QU5`'s `S0/S1` from either the BMC (`AST_I2CS0/1`) or the
  SP5100 (`SB_I2CS0/1`) — this is the bus-ownership arbitration.

![DIMM SPD topology](diagrams/kgpe-d16-i2c-bus-dimm-spd.svg)

| Bank | Bus | Slots | SPD | TSOD |
|---|---|---|---|---|
| A–D | `I2C10` (`QU5` ch Y2) | DIMM_A1/A2/B1/B2/C1/C2/D1/D2 | `0x50`–`0x57` | `0x18`–`0x1F` |
| E–H | `I2C11` (`QU5` ch Y3) | DIMM_E1/E2/F1/F2/G1/G2/H1/H2 | `0x50`–`0x57` | `0x18`–`0x1F` |

**To read DIMM C1 SPD:** enable `U23` BMC buffers → assert `I2CMUX_EN#` low →
set `AST_I2CS1:AST_I2CS0 = 1:0` (channel `I2C10`) → address `0x50 + slot` on
`I2C2`.

### 3.4 CPU thermal (SB-TSI)

The BMC's `I2C4` reaches the W83795G's TSI pins; the hwmon in turn masters the
**AMD SB-TSI** interface to each processor for die temperature (through
level-shift FETs).

![CPU thermal topology](diagrams/kgpe-d16-i2c-bus-cputemp.svg)

| Device | Address | Note |
|---|---|---|
| CPU0 SB-TSI | `0x4C` | processor die temp |
| CPU1 SB-TSI | `0x4D` | processor die temp |

### 3.5 BMC I2C5 — board inventory + DIMM-LED expanders

The BMC's private inventory/indicator bus: the board FRU EEPROM and the two GPIO
expanders that drive the 16 per-DIMM error LEDs.

![Inventory bus topology](diagrams/kgpe-d16-i2c-bus-inventory.svg)

| Device | Ref | Address | Drives |
|---|---|---|---|
| HT24LC08 EEPROM | `U25` | `0x54`–`0x57` (A2=VCC strap; base `0x50`–`0x53`) | board FRU (serial/part) |
| W83601G | `U27` | strap `A0/A1/A2` | DIMM A–F error LEDs |
| W83601G | `U28` | strap `A0/A1/A2` | DIMM G/H error LEDs + spare GPIO |

### 3.6 SP5100 SMBus0 — CPU/NB voltage regulators

The southbridge's private SVI/PMBus link to the two UPI multi-phase PWM
controllers that make the CPU and northbridge core rails — VID set and
voltage/current/temperature telemetry.

![VR PMBus topology](diagrams/kgpe-d16-i2c-bus-vr.svg)

| Device | Ref | Part | Rail |
|---|---|---|---|
| VR PWM controller | `PU2` | UPI ASP0902QGK | CPU0 core (VDD) |
| VR PWM controller | `PU7` | UPI ASP0906QGK | CPU1 core / northbridge |

Supporting: `PU1` (ASP0910 analog SVI switch); `PU4`/`PU9`/`PU10` (UP6282 bucks)
for lower rails.

### 3.7 Other segments & straps

- **SP5100 `SMBus3` (level-shifted)** — `SCL3_LV`/`SDA3_LV` (SU1 `E20`/`E21`). A
  low-voltage SMBus segment brought out but **unpopulated** on this board.
- **Fan-curve straps** — SP5100 `DDC1_SCL/SDA` (`AA20`/`Y18`) are repurposed as
  GPIO strap inputs `FANCURVE1/0` (fan-profile select), not a live bus.
- **LAN-disable straps** — Super-I/O `GP50`/`GP37` (`SIO_LAN2/1DISABLE#`) gate the
  two 82574L NICs via the `LAN_SW1/2` jumpers, not a live bus.

### 3.8 SR5690 northbridge — PCIe hot-plug SMBus

The northbridge exposes a PCIe hot-plug / debug SMBus on its `DBG_GPIO1/2` pins
(`PCIE_HP_SCL/SDA`), brought to the `NB_DEBUG_HEADER1`.

![NB hot-plug SMBus topology](diagrams/kgpe-d16-i2c-bus-nbhotplug.svg)

### 3.9 FireWire config EEPROM (private bus)

The LSI **FW322** 1394a controller has a private 2-wire link to its own serial
EEPROM, from which it loads its 1394 GUID and configuration at power-up. This bus
is independent of the management fabric.

![FireWire EEPROM topology](diagrams/kgpe-d16-i2c-bus-firewire.svg)

| Device | Ref | Address |
|---|---|---|
| Config EEPROM | `ZU2` | Holtek HT24LC02 · `0x50` |

---

## 4. Regenerating

The bus map is extracted from the netlist, and the topology SVGs are generated:

```sh
uv run tools/i2c_topology_svg.py     # writes diagrams/kgpe-d16-i2c-bus-*.svg
```

See [README.md](README.md) for the `.FZ` extraction step. The board-wide BMC view
(`diagrams/kgpe-d16-bmc-i2c-topology.svg`) is embedded in
[AST2050-BMC-WIRING.md §10](AST2050-BMC-WIRING.md#10-i²c--smbus-topology-traced-through-every-mux--expander).

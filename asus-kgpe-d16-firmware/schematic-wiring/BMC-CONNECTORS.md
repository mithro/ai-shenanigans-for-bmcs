# ASUS KGPE-D16 — connectors & headers wired to the AST2050 BMC

Physical pinout diagrams and full signal tables for the board connectors,
headers, sockets and jumpers that connect to the ASPEED AST2050 BMC (`QU1`).
Companion to [AST2050-BMC-WIRING.md](AST2050-BMC-WIRING.md); every net traces to
a BMC ball there.

Pin numbers and nets are authoritative — read from the schematic netlist. The
physical row/column layout in each ASCII diagram follows the connector's standard
convention (dual-row 0.1″ headers: **odd pins on the top row, even on the
bottom**, pin 1 marked `▛`; VGA is the standard HD-15). "NC" = no-connect.

## Connectors at a glance

| Connector | Type | Pins | What it is | BMC involvement |
|---|---|---|---|---|
| [`VGA1`](#vga1--vga-output-hd-15) | VGA HD-15 (female) | 15+shield | On-board VGA output | BMC integrated video (RGB DAC, DDC, sync) |
| [`AST_UART1`](#ast_uart1--bmc-serial-console) | 1×4 header | 4 | BMC serial console | BMC UART2 (`AST_TXD2/RXD2`) |
| [`AST_JTAG1`](#ast_jtag1--bmc-arm-jtag-debug) | 2×10 header | 20 | BMC ARM926 JTAG debug | Full JTAG (TCK/TMS/TDI/TDO/…) |
| [`BMC_FW1`](#bmc_fw1--bmc-spi-firmware-socket) | 2×7 DIP socket | 13 | BMC firmware flash (socketed) + straps | SPI bus + feature straps |
| [`PANEL1`](#panel1--system-front-panel) | 2×10 header | 20 | System front-panel (power/reset/LEDs) | Power btn, reset, msg LED, NMI btn |
| [`AUX_PANEL1`](#aux_panel1--auxiliary-panel-q-connector) | 2×10 header | 20 | ASUS auxiliary panel | BMC locator LED/button, I²C8, LAN LEDs |
| [`PSUSMB1`](#psusmb1--psu-smbus) | 1×5 header | 5 | PSU SMBus/PMBus | BMC I²C1 (`SDA1/SCL1` + alert) |
| [`VGA_SW1`](#vga_sw1--vga-reset-source-jumper) | 1×3 jumper | 3 | VGA reset-source select | `AST_BRST#` vs `SB_PCI_RST#` |
| [`IPMI_SEL1`](#ipmi_sel1--ipmi-enable-jumper) | 1×3 jumper | 3 | IPMI enable/route | `IPMI_SEL` (BMC A8) |
| [`RECOVERY1`](#recovery1--bios-recovery-jumper) | 1×3 jumper | 3 | BIOS recovery | `BIOS_RECOVERY#` (BMC C9) |

---

## `VGA1` — VGA output (HD-15)

The on-board VGA connector, driven by the AST2050's integrated video: analog RGB
from the on-chip DAC (via buffer transistors `QD3/4/5`), the DDC/EDID I²C, and
the H/V sync buffered by `QU6` (Toshiba TC74VHCT125AF). See
[BMC §8](AST2050-BMC-WIRING.md#8-vga--video-output--vga1).

```
        VGA HD-15 female — front (mating) view
        ┌─────────────────────────────────┐
         \   (1)  (2)  (3)  (4)  (5)      /     1=RED  2=GREEN 3=BLUE 4=NC 5=GND
          \   (6)  (7)  (8)  (9) (10)    /      6=RGND 7=GGND 8=BGND 9=+5V 10=GND
           \  (11) (12) (13) (14) (15)  /       11=NC 12=DDC-DAT 13=HSYNC 14=VSYNC 15=DDC-CLK
            └───────────────────────────┘
```

| Pin | Net | Function | Connects to |
|---|---|---|---|
| 1 | `L_AST_DACR` | Red analog | **BMC `E1`** (`DACR`) via `QD3` |
| 2 | `L_AST_DACG` | Green analog | **BMC `D1`** (`DACG`) via `QD4` |
| 3 | `L_AST_DACB` | Blue analog | **BMC `C1`** (`DACB`) via `QD5` |
| 4 | — | NC (monitor ID2) | — |
| 5,6,7,8,10 | `GND` | Grounds (signal + RGB returns) | — |
| 9 | `+VGA_5V_F` | +5 V (DDC power) | fused +5 V |
| 11 | — | NC (monitor ID0) | — |
| 12 | `AST_DDCDAT_R_T` | DDC data (SDA) | **BMC `B2`** (`DDCADAT`) |
| 13 | `AST_HSYNC_R_B` | H-sync | **BMC `U2`** via `QU6.8` |
| 14 | `AST_VSYNC_R_B` | V-sync | **BMC `R4`** via `QU6.11` |
| 15 | `AST_DDCCLK_R_T` | DDC clock (SCL) | **BMC `B1`** (`DDCACLK`) |
| 16,17 | `GND` | Shell / side grounds | — |

---

## `AST_UART1` — BMC serial console

A dedicated 4-pin header for the **BMC's own serial console** (AST2050 UART2),
powered from standby so it works with the host off. This is separate from the
host Serial-over-LAN path ([BMC §12](AST2050-BMC-WIRING.md#12-serial--serial-over-lan-sol)).

```
   AST_UART1 (1×4)
   ▛1  2  3  4
   │  │  │  │
  +5V TX RX GND
```

| Pin | Net | Function | Connects to |
|---|---|---|---|
| 1 | `+5VSB` | +5 V standby | standby rail |
| 2 | `AST_TXD2_R` | BMC transmit | **BMC `U21`** (`TXD2`) |
| 3 | `AST_RXD2_R` | BMC receive | **BMC `U20`** (`RXD2`) |
| 4 | `GND` | Ground | — |

---

## `AST_JTAG1` — BMC ARM JTAG debug

Standard 20-pin ARM JTAG header for the AST2050's ARM926EJ-S core (used by the
`culvert`/OpenOCD work elsewhere in this repo). Odd pins carry the signals; even
pins are ground.

```
   AST_JTAG1 (2×10, ARM 20-pin)
        top (odd)                         bottom (even)
   ▛1  +3V3_AUX          2  +3V3_AUX
    3  NTRST             4  GND
    5  TDI               6  GND
    7  TMS               8  GND
    9  TCK              10  GND
   11  RTCK            12  GND
   13  TDO             14  GND
   15  SRST#           16  GND
   17  NC              18  GND
   19  NC              20  GND
```

| Pin | Net | Function | BMC ball |
|---|---|---|---|
| 1, 2 | `+3V3_AUX` | Vref / target power sense | — |
| 3 | `AST_NTRST` | JTAG TAP reset | `T20` (`NTRST`) |
| 5 | `AST_TDI` | Test data in | `T21` (`TDI`) |
| 7 | `AST_TMS` | Test mode select | `T19` (`TMS`) |
| 9 | `AST_TCK` | Test clock | `U22` (`TCK`) |
| 11 | `AST_RTCK` | Return test clock | `T22` (`RTCK`) |
| 13 | `AST_TDO` | Test data out | `R19` (`TDO`) |
| 15 | `AST_SRST#` | System reset | `R20` (`SRST#`) |
| 17, 19 | — | NC | — |
| 4,6,8,10,12,14,16,18,20 | `GND` | Ground | — |

---

## `BMC_FW1` — BMC SPI firmware socket

A **socketed** 2×7 DIP holding the BMC's SPI firmware flash, so the chip is
field-replaceable. Beyond the SPI bus it also carries three feature-strap lines
the BMC samples. See [BMC §4](AST2050-BMC-WIRING.md#4-spi-firmware-flash--bmc_fw1).

```
   BMC_FW1 (2×7 socket)
        odd                     even
   ▛1  AST_SPIDO (MOSI)    2  +3V3_AUX
    3  AST_IKVMEN# strap   4  AST_SPICS#2
    5  NC                  6  AST_SPIDI (MISO)
    7  BMC_PRESENT# strap  8  AST_SPICLK
    9  NC                 10  AST_SOLEN# strap
   11  NC                 12  AST_SPICS#0
   13  GND               (14 keyed / absent)
```

| Pin | Net | Function | BMC ball |
|---|---|---|---|
| 1 | `AST_SPIDO` | SPI MOSI (data out) | `Y1` (`ROMD1`) |
| 2 | `+3V3_AUX` | Flash power (standby) | — |
| 3 | `AST_IKVMEN#` | Strap: enable iKVM | `W1` |
| 4 | `AST_SPICS#2` | SPI chip-select 2 | `W7` (`ROMCS2#`) |
| 6 | `AST_SPIDI` | SPI MISO (data in) | `AA4` (`ROMD2`) |
| 7 | `BMC_PRESENT#` | Strap: BMC present (also SOL-mux select) | `A10`/`D11`/`AA9` |
| 8 | `AST_SPICLK` | SPI clock | `Y2` (`ROMD0`) |
| 10 | `AST_SOLEN#` | Strap: enable Serial-over-LAN | `W2` |
| 12 | `AST_SPICS#0` | SPI chip-select 0 (main firmware) | `AB9` (`ROMCS0#`) |
| 5, 9, 11 | — | NC | — |
| 13 | `GND` | Ground | — |

---

## `PANEL1` — system front panel

The main front-panel header (power/reset switches, status LEDs, NMI button,
speaker). Several signals reach the BMC so it can drive the message LED and see
the power/reset/NMI buttons; power/HDD LEDs go to the chipset. Pin 5 is the
keyed/absent slot.

```
   PANEL1 (2×10)
        odd                      even
   ▛1  FP_HDLED+           2  (HDLED-)
    3  GND                 4  NC
    5  (keyed)             6  FP_PLED-
    7  FP_NMIBNT#          8  (PLED+)
    9  GND                10  FP_MLED
   11  R_FP_PWRBTN#       12  NC
   13  GND                14  +5V
   15  NC                 16  GND
   17  FP_RESET#          18  GND
   19  GND                20  SPKOUT
```

| Pin | Net | Function | Connects to |
|---|---|---|---|
| 1 | `FP_HDLED+` | HDD-activity LED anode | chipset |
| 6 | `FP_PLED-` | Power LED cathode | chipset |
| 7 | `FP_NMIBNT#` | NMI button | **BMC `T1`/`U1`** |
| 10 | `FP_MLED` | Message / heartbeat LED | **BMC `R3`** (`AST_MLED`) |
| 11 | `R_FP_PWRBTN#` | Power button | **BMC `A11`/`C11`** |
| 17 | `FP_RESET#` | Reset button | **BMC `C10`/`D10`** |
| 20 | `SPKOUT` | Chassis speaker | `BUZZ1.2` |
| 14 | `+5V` | +5 V | — |
| 3,9,13,16,18,19 | `GND` | Ground | — |
| 4,12,15 | — | NC | — |

---

## `AUX_PANEL1` — auxiliary panel (Q-connector)

ASUS auxiliary front-panel header. Carries the **BMC chassis-locator LED and
button**, the front I²C8 bus (SPD/aux, via the muxes), and LAN link/activity
LEDs.

```
   AUX_PANEL1 (2×10)
        odd                      even
   ▛1  +5VSB              2  NC
    3  (GND)              4  I2C8SCL
    5  AUX_CHASSIS#       6  (—)
    7  GND                8  GND
    9  AUX_LOCLED1       10  I2C8SDA
   11  AUX_BMCLOCLED#    12  NC
   13  AUX_BMCLOCBNT#    14  AUX_LAN1LINK#
   15  GND               16  AUX_LAN1ACT#
   17  AUX_BMCLOCLED#    18  AUX_LAN2ACT#
   19  AUX_LOCLED2       20  AUX_LAN2LINK#
```

| Pin | Net | Function | Connects to |
|---|---|---|---|
| 1 | `+5VSB` | +5 V standby | — |
| 4 | `I2C8SCL` | Front I²C8 clock | `QU5.12`, `QU9.11` (mux fabric) |
| 10 | `I2C8SDA` | Front I²C8 data | `QU5.1`, `QU9.14` |
| 11, 17 | `AUX_BMCLOCLED#` | BMC locator LED | **BMC `Y4`** (`AST_IDLEDSTATUS`) |
| 13 | `AUX_BMCLOCBNT#` | BMC locator button | **BMC `Y3`** (`AST_IDBNT#`) |
| 14 | `AUX_LAN1LINK#` | LAN1 link LED | `LQ3.3` |
| 20 | `AUX_LAN2LINK#` | LAN2 link LED | `LQ5.3` |
| 5 | `AUX_CHASSIS#` | Chassis intrusion | — |
| 9,16,18,19 | LEDs | Locator / LAN-activity LEDs | — |
| 3,7,8,15 | `GND` | Ground | — |

---

## `PSUSMB1` — PSU SMBus

The power-supply SMBus/PMBus header, on the BMC's **I²C1** so the BMC can read
PSU telemetry. See [BMC §10.4](AST2050-BMC-WIRING.md#104-bmc-ic-bus-assignments-quick-reference).

```
   PSUSMB1 (1×5)
   ▛1   2    3    4    5
   SCL SDA  ALERT GND +3V3
```

| Pin | Net | Function | Connects to |
|---|---|---|---|
| 1 | `I2C1SCL` | SMBus clock | **BMC `B15`** (`SCL1`) |
| 2 | `I2C1SDA` | SMBus data | **BMC `A15`** (`SDA1`) |
| 3 | `N37658829` | SMBus alert | **BMC `B12`** (`SCL7/SALT1`) |
| 4 | `GND` | Ground | — |
| 5 | `+3V3` | +3.3 V | — |

---

## `VGA_SW1` — VGA reset-source jumper

A 3-pin jumper selecting which reset drives the VGA/iKVM PCI function — the BMC's
own `AST_BRST#` or the chipset's `SB_PCI_RST#`.

```
   VGA_SW1 (1×3)
   [1]──[2]──[3]
    │    │    │
 SB_PCI AST_ GND
 _RST#  BRST#
```

| Pin | Net | Function | Connects to |
|---|---|---|---|
| 1 | `SB_PCI_RST#` | Chipset PCI reset | **BMC `B10`**, southbridge |
| 2 | `AST_BRST#` | BMC PCI/VGA reset | **BMC `P21`** (`BRST#`) |
| 3 | `GND` | Ground | — |

---

## `IPMI_SEL1` — IPMI enable jumper

3-pin jumper that sets the `IPMI_SEL` strap read by the BMC (`A8`,
`GPIOC5/PWM4`).

| Pin | Net | Function | Connects to |
|---|---|---|---|
| 1 | — | NC / pull option | — |
| 2 | `IPMI_SEL` | IPMI-enable strap | **BMC `A8`** |
| 3 | `N39526076` | strap option | — |

---

## `RECOVERY1` — BIOS recovery jumper

3-pin jumper asserting `BIOS_RECOVERY#`, sensed by the BMC (`C9`,
`GPIOB7/VBDI/EXTRST#`) to trigger BIOS recovery.

| Pin | Net | Function | Connects to |
|---|---|---|---|
| 1 | — | NC / pull option | — |
| 2 | `BIOS_RECOVERY#` | Recovery request | **BMC `C9`** |
| 3 | `GND` | Ground | — |

---

## See also

- [AST2050-BMC-WIRING.md](AST2050-BMC-WIRING.md) — the BMC itself (every ball).
- [pinmaps/QU1_pins.md](pinmaps/QU1_pins.md) — exhaustive BMC per-pin table; each
  section lists these connectors under "Connected components".

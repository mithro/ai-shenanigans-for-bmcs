# Schematic ↔ DEVICE-MATRIX reconciliation

**Purpose.** The authoritative source for *what exists on the board* is
[`schematic-wiring/AST2050-BMC-WIRING.md`](../schematic-wiring/AST2050-BMC-WIRING.md)
(traced from the RC6-decrypted `.FZ` netlist — part numbers read, not inferred).
This doc cross-checks **every device that doc describes** against a row in
[`DEVICE-MATRIX.md`](DEVICE-MATRIX.md), so we can assert — and let independent
sub-agents falsify — that (1) nothing on the board is missing a matrix row, and
(2) no device is *falsely* claimed absent / unconnected / impossible when the
schematic says otherwise.

Last full read-through + reconciliation: **2026-07-21**.

## 1. Every schematic device has a matrix row

| Schematic § | Device / interface (BMC-side) | Ref | Matrix row |
|---|---|---|---|
| §3 | DDR2 SDRAM (Hynix HY5PS121621, 64 MB) | QU2 | 1 (SDMC) |
| §4 | SPI firmware flash (socketed), CS0/CS2 | BMC_FW1 | 2 (SMC) |
| §5 | LPC KCS / IPMI | → SU1 | 3 |
| §5 | LPC mailbox | → SU1 | 4 |
| §5 | LPC port-80h POST snoop | → SU1 | 5 |
| §5 | LPC vUART | → SU1 | 6 |
| §5/§15 | TPM header (LPC pass-through) | TPM1 | 7 |
| §6 | PCI-33 / iKVM video-capture | → SU1 | 8 |
| §9 | USB **device** port (virtual KB/mouse/CD) | → SU1 | 9 |
| §7 | Eth MAC ch1 MII → mgmt PHY | U5 (RTL8201N) | 10 |
| §7 | Eth MAC ch2 RMII2 / **NC-SI** → host NICs | LU1/LU2 (82574L) | 11 |
| §8 | VGA DAC output | VGA1 | 12 |
| §8 | VGA HSYNC/VSYNC buffer | QU6 (TC74VHCT125AF) | 13 |
| §8 | DDC / EDID I²C to monitor | VGA1 | 14 |
| §10 | AST2050 I²C controllers (8 engines) | QU1 | 15 |
| §10 | Hardware monitor | QU4 (W83795G) | 16 |
| §10 | I²C mux fabric (FET switch + analog mux + source-select) | QU9/QU5/U23 | 17 |
| §10 | DIMM SPD ×16 (via QU5 Y2/Y3) | DIMM_x | 18 |
| §10 | DIMM TSOD ×16 | DIMM_x | 19 |
| §10 | Board FRU EEPROM | U25 (HT24LC08) | 20 |
| §10 | DIMM-LED expander (A–F) | U27 (W83601G) | 21 |
| §10 | DIMM-LED expander (G/H) | U28 (W83601G) | 22 |
| §10 | CPU thermal (SB-TSI / PECI-TSI) | via QU4 | 23 |
| §10 | PSU management | PSUSMB1 | 24 |
| §10 | SMBus ALERT (SALT1/2) | I2C7 | 25 |
| §10/§15 | Aux front panel (I²C8) | AUX_PANEL1 | 26 |
| §11 | Power control (ATXPSON#/PWRBTN#/SYSRESET#/SYS_PWRGD) | GPIO | 27 |
| §11 | Platform monitors (THERMTRIP#/PROCHOT#/DDR_THERM#/NMI#) | GPIO | 28 |
| §11 | Platform control (CLRTC#/BIOSREVRY#/CPU1-2DISABLE#/PCIRST#) | GPIO | 29 |
| §12/§15 | UART console (UART2, AST_UART1) | — | 30 |
| §12 | UART1 / SOL via 2:1 mux → Super-I/O | QU8 (PI5C3257) | 31 |
| §13 | LEDs (BMCRDY/MLED/CPUERR/chassis-ID) + locator button | GPIO/LED | 32 |
| §13 | Straps (IKVMEN#/SOLEN#/IPMI_SEL) | — | 33 |
| §13 | 24 MHz clock input | QOSC1 | 34 |

SoC-internal engines the schematic implies but does not itemise (register blocks
inside QU1) are also each a row: SCU 35, VIC 36, timers 37, WDT 38, RTC 39, PWM
40, ADC 41 (**absent on G3** — phantom removed), PECI 42, HACE 43, MIC 44, MDMA
45, 2D-BitBLT 46, PUART 47, PCI-arbiter 48, AHBC 49, A2P 50.

**Result: all 50 matrix rows are accounted for; every BMC-side schematic device
maps to exactly one row, and no schematic device lacks a row.**

### Schematic items intentionally without a row (with rationale)

- **Power LDOs** `PU22`/`PU28` (UP7706U8), aux 3.3 V reg, PLL filter rails (§2):
  fixed analog power delivery — no register/programmable interface, nothing to
  emulate or drive.
- **Reset/power glue** `U8`/`U6`/`U7` (74LVC14A/07A/TC74LCX74), `U23` source-
  select, `AZ75232` RS-232 xceivers: combinational buffers/inverters in the
  GPIO/UART signal paths — covered *functionally* by the rows whose signals pass
  through them (27–29 power/reset, 31 SOL, 17 I²C source-select).
- **Host-side peer chips** `SU1` (SP5100), `NU1` (SR5690), `OU1` (W83667HG
  Super-I/O), `LU1/LU2` (82574L): these are the far ends the BMC talks *to*, not
  BMC peripherals. The standalone-BMC QEMU machine models the BMC-side interface
  (LPC/PCI/I²C/NC-SI); the host chipset is deliberately out of scope. (Where a
  far-end responder is needed for validation — e.g. an NC-SI responder, a PMBus
  PSU, EEPROMs — it is modeled as an I²C/bus slave in the machine.)

## 2. Corrections to false "impossible / not-connected" claims

The schematic is authoritative. These prior summary claims are **contradicted by
it** and are corrected here (the DEVICE-MATRIX rows themselves are already
faithful — the errors live only in summary prose / memory):

| Prior claim | Schematic reality | Status |
|---|---|---|
| "true NC-SI **impossible**" | §7: `AST_RMII2*` bus wired to **both** 82574L NICs (LU1/LU2); MAC pin-mux runs ch1 MII **and** ch2 RMII2/NC-SI at once | **FALSE** — NC-SI is wired. Row 11 QE✅/LQ✅; remaining = US/LS/Zephyr + a QEMU NC-SI responder. #132 (D07) is the faithful line of work. |
| "DIMM inventory **impossible**" | §10: DIMM SPD ×16 reachable via `QU9` FET switch + `QU5` 74HC4052 (Y2=A–D, Y3=E–H) with the exact select sequence documented | **FALSE** — DIMM SPD is wired + modeled. Row 18 QE✅/LQ✅/ZQ✅; remaining = ZS + TSOD (row 19). |
| "USB-host impossible" | §9: the BMC USB is a **device** port (virtual KB/mouse/CD) to SU1 — the BMC is a USB *device*, not a host | **MISLEADING** — USB-host is genuinely not a BMC role, but the real capability (USB device / vhub) exists and is row 9. |
| "host-BIOS-flash impossible" | §5: BMC is an LPC peripheral on SU1's bus; whether it can issue LPC firmware cycles to the host BIOS flash is unproven, not disproven | **UNSETTLED** — tracked by #134 (D03), not "impossible". |

## 3. Coverage state (per the 8-stack matrix) and the remaining task list

"Complete" per the program goal = for every device: **QE** full QEMU emulation;
**U-Boot** driver validated in QEMU (UQ) + silicon (US); **Linux** driver
validated in QEMU (LQ) + silicon (LS) + userspace (LU); **Zephyr** driver
validated in QEMU (ZQ) + silicon (ZS). `Ⓝ` = legitimately not-applicable for
that stack (documented per row); it counts as done.

The remaining open cells (🔶 partial / ⬜ absent, excluding Ⓝ) are the task list.
Grouped by the biggest gaps:

- **U-Boot silicon (US) + Linux silicon (LS):** the driver-on-real-hardware
  columns are the thinnest. Silicon access is JTAG + netboot only (no BMC SPI
  flash populated). Open across many rows (2, 3/5/6 LPC-LS, 8, 9, 11, 12/14, 16,
  24 NC-SI/PSU-LS, 27–29, 31, 32, 42–50).
- **Zephyr silicon (ZS):** open on most rows beyond the 6 silicon-proven drivers
  (GPIO/timer/VIC/WDT/I2C/W83795). Rows 17/18/23/24/27/32 ZS + breadth.
- **QE 🔶 to finish:** 8 (PCI-target), 12/14 (CRT + DDC/EDID, #178), 25 (SMBus-
  ALERT), 26 (aux panel), 28/29 (GPIO monitors/control breadth), 31 (SOL end-to-
  end), 42 (PECI), 43 (HACE), 47 (PUART), 49 (AHBC), 50 (A2P forwarding).
- **QE ⬜ to start:** 4 (LPC mailbox), 46 (2D BitBLT), 48 (PCI-arbiter).

These map to the existing per-row tasks in [`FULL-TASK-LIST.md`](FULL-TASK-LIST.md)
and the tracker (#132/#133/#134/#137/#138/#178/#198/etc.). No *device* is
missing; the remaining work is **driver breadth + silicon/userspace validation**,
not undiscovered hardware.

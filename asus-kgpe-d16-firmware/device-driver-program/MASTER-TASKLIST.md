# Master task list — every BMC device × every stack × every validation

**Derived directly from an end-to-end read of the authoritative schematic**
[`schematic-wiring/AST2050-BMC-WIRING.md`](../schematic-wiring/AST2050-BMC-WIRING.md)
(§1–16), 2026-07-19, cross-checked against
[`pinmaps/QU1_pins.md`](../schematic-wiring/pinmaps/QU1_pins.md) (all 355 balls),
[`I2C-SMBUS-TOPOLOGY.md`](../schematic-wiring/I2C-SMBUS-TOPOLOGY.md) and
[`I2C-MUX-FABRIC-ARBITRATION.md`](../schematic-wiring/I2C-MUX-FABRIC-ARBITRATION.md).

This is the **enumeration + task backbone** the program's goal asks for: for *every*
device the schematic wires to the AST2050 BMC (`QU1`), the four driver stacks and
their validations. It is the human-readable index; the authoritative per-cell status
grid is [`DEVICE-MATRIX.md`](DEVICE-MATRIX.md) (rows referenced as `[row N]`) and the
per-box detail is [`FULL-TASK-LIST.md`](FULL-TASK-LIST.md). Where they disagree, the
more-recently-dated evidence-cited entry wins and is reconciled (see DEVICE-MATRIX
header). Running history is [`LOG.md`](LOG.md).

## The task template (applied to every device below)

Per the goal, each device carries up to these tasks (✅ done · 🔶 partial · ⬜ open ·
Ⓝ not-applicable-with-reason · 🔷 rig-blocked):

- **QEMU**: full model of all functionality.
- **U-Boot**: driver → validate in QEMU → validate on silicon.
- **Linux**: driver → validate in QEMU → validate on silicon → validate userspace ABI.
- **Zephyr**: driver → validate in QEMU → validate on silicon.

"Silicon" = JTAG + netboot only (the BMC SPI flash is unpopulated on this rig); power
via the `au-plug` Tasmota. Column key maps to DEVICE-MATRIX: QE / UQ·US / LQ·LS·LU /
ZQ·ZS.

---

## A. SoC core (the AST2050 itself — needed before any device)

| Device (schematic) | Matrix | QEMU | U-Boot Q/Si | Linux Q/Si/US | Zephyr Q/Si | Next action |
|---|---|---|---|---|---|---|
| DDR2 SDRAM ctrl → QU2 (§3) | [1] | ✅ | ✅ / ✅ | ✅ / ✅ / Ⓝ | 🔶 / ⬜ | Zephyr uses loader-init'd DRAM; a Zephyr SDMC-init driver is optional |
| SPI/ROM flash ctrl → BMC_FW1 (§4) | [2] | ✅ | ✅ / 🔷 | 🔶 / 🔷 / ⬜(MTD-write) | ⬜ / ⬜ | US/LS rig-blocked (socket empty by design); add MTD write path (#140/D02) |
| SCU (clock/pinmux/reset) (§13 clk) | [35] | ✅ | ✅ / ✅ | ✅ / ✅ / Ⓝ | ⬜ / ⬜ | Zephyr SCU clock driver + rate test (#142/#55) |
| VIC interrupt controller (§impl) | [36] | ✅ | ✅ / ✅ | ✅ / ✅ / Ⓝ | 🔶 / **✅** | Zephyr ZS DONE this session (storm-free) |
| Timers (§impl) | [37] | ✅ | ✅ / ✅ | ✅ / ✅ / Ⓝ | 🔶 / **✅** | Zephyr ZS DONE (steady ticks) |
| Watchdog (§impl) | [38] | ✅ | 🔶 / ⬜ | ✅ / 🔶 / ⬜ | ✅ / **✅** | Zephyr ZS DONE (true reset); U-Boot/Linux WDT silicon + /dev/watchdog |
| RTC (§impl) | [39] | ✅ | Ⓝ / Ⓝ | ✅ / ⬜ / ⬜ | **🔶** / ⬜ | Zephyr RTC driver QEMU-DONE (rtc_aspeed_g3.c, set/get PASS); Linux RTC silicon + Zephyr ZS remain |
| PWM (§13, VP*/TACH* repurposed) | [40] | ✅ | Ⓝ | Ⓝ (board: PWM pins = CPUnDISABLE# GPIO, fans on W83795) | Ⓝ | Board-disposition Ⓝ — §11-confirmed repurposed |
| ADC | [41] | Ⓝ | Ⓝ | Ⓝ | Ⓝ | **ABSENT on G3** per datasheet §9 p97 (#146); no device |
| PECI (A9/B9 = PECIO/PECII) | — (#145) | Ⓝ | Ⓝ | Ⓝ | Ⓝ | §11-confirmed: PECI pins repurposed as ATXPSON#/CLRTC# GPIO |

## B. Host-interface buses

| Device (schematic) | Matrix | QEMU | U-Boot Q/Si | Linux Q/Si/US | Zephyr Q/Si | Next action |
|---|---|---|---|---|---|---|
| LPC → SP5100 + Super-I/O + TPM (§5): KCS/IPMI | [B row] | ✅ | Ⓝ | ✅ / ✅ / ✅(ipmi) | ⬜ | Zephyr KCS driver (low priority) |
| LPC mailbox sub-block (§5) | [⬜] | ⬜ | Ⓝ | ⬜ / ⬜ / ⬜ | ⬜ | **QEMU ⬜** — model the LPC mailbox (#134) |
| LPC virtual-UART / SuperIO pass (§5) | [B] | 🔶 | Ⓝ | 🔶 / ⬜ / ⬜ | ⬜ | Complete LPC sub-blocks (#134) |
| TPM header (LPC side) (§5/§15) | [7] | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Board TPM is host-owned LPC pass-through |
| PCI 33 MHz (VGA/iKVM) → SP5100+slots (§6) | [PCI] | ✅ | Ⓝ | ✅ / 🔶 / — | ⬜ | Complete PCI/video-capture silicon (D04) |
| USB device port → SP5100 (§9) | [USB] | ✅ | Ⓝ | 🔶 / 🔷 / — | Ⓝ | USB-device silicon rig-blocked; Zephyr N |

## C. Network (§7)

| Device (schematic) | Matrix | QEMU | U-Boot Q/Si | Linux Q/Si/US | Zephyr Q/Si | Next action |
|---|---|---|---|---|---|---|
| MAC (ftgmac100) + RTL8201N mgmt PHY, ch1 MII → U5 | [C] | ✅ | ✅ / ✅ | ✅ / ✅ / ✅ | ⬜ / ⬜ | Zephyr ethernet driver (large) |
| NC-SI sideband ch2 (RMII2 → 2× 82574L) (§7) | [11] | ✅ | Ⓝ | ✅(QEMU ncsi) / ⬜ / ⬜ | ⬜ | **NC-SI silicon** (#132, D07) — G3 RMII2 pinmux |

## D. Video (§8)

| Device (schematic) | Matrix | QEMU | U-Boot Q/Si | Linux Q/Si/US | Zephyr Q/Si | Next action |
|---|---|---|---|---|---|---|
| VGA controller + DAC + sync (§8) | [video] | ✅ | Ⓝ | ✅ / 🔶(capture) / — | ⬜ | Complete video-capture (D04) |
| DDC / EDID I²C to VGA1 (§8) | [14] | ⬜ | Ⓝ | ⬜ / ⬜ / ⬜ | ⬜ | **QEMU ⬜** — model the VGA DDC master (#140/D12) |

## E. I²C / SMBus devices (§10)

| Device (schematic) | Bus | Matrix | QEMU | Linux Q/Si/US | Zephyr Q/Si | Next action |
|---|---|---|---|---|---|---|
| PSU PMBus (PSUSMB1) | I2C1 @0x58 | [24] | **✅** | ⬜/⬜/⬜ | ⬜ | **QEMU DONE 2026-07-19** (pmbus_psu.c, fwtest); Linux/Zephyr pmbus-hwmon bind |
| SMBus-ALERT (SALT1/2) | I2C7/B12 | [25] | ⬜ | ⬜ | ⬜ | **QEMU ⬜** — model the ALERT# response (#135) |
| W83795G hwmon (QU4) | I2C2 @0x2F | [16] | ✅ | ✅/✅/✅ | 🔶 / **✅** | Zephyr ZS DONE (real fan/temp read) |
| I²C mux fabric QU9/QU5/U23 | I2C2/7 | [17] | ✅ | 🔶/🔶/🔶 | ⬜ | Zephyr mux driver; complete arbitration silicon |
| DIMM SPD ×16 (QU5 Y2/Y3) | I2C10/11 | [18] | ✅ | ✅/🔶/🔶 | ⬜ | BMC-autonomous SPD inventory silicon |
| DIMM TSOD ×16 (jc42) | I2C10/11 | [19] | ✅(not-inst) | ✅/Ⓝ/Ⓝ | ⬜/Ⓝ | This rig's DIMM has no TSOD (faithful absence) |
| FRU EEPROM (U25, HT24LC08) | I2C5 @0x54 | [20] | ✅ | ✅/✅/✅ | **🔶** | Zephyr FRU DONE via in-tree at2x on engine 4 (fru_smoke PASS, blank 0xff); ZS remains |
| W83601G DIMM-LED exp U27 | I2C5 @0x18 | [21] | ✅ | ✅/✅/✅(us) | ⬜ | Zephyr client (optional) |
| W83601G DIMM-LED exp U28 | I2C5 @0x19 | [22] | ✅ | ✅/✅/✅(us) | ⬜ | Zephyr client (optional) |
| SB-TSI CPU thermal (via QU4 FETs) | I2C4 @0x4C/4D | [23] | ✅ | ✅/✅/✅ | 🔶 / ⬜ | **Zephyr SB-TSI silicon** — needs host CPU powered (#150) |
| Aux front panel (AUX_PANEL1) | I2C8/Y0 | [26] | 🔶 | ⬜ | ⬜ | Model/validate the aux-panel end |
| PCIe-slot 1–5 SMBus + TPM-hdr I²C | I2C8_SW | [26b] | 🔶 | ⬜ | ⬜ | Host-on segment (#151-resolved as segments, not fixed devices) |

## F. GPIO / platform control (§11) + serial + JTAG/LEDs/straps (§12/§13)

| Device (schematic) | Matrix | QEMU | U-Boot Q/Si | Linux Q/Si/US | Zephyr Q/Si | Next action |
|---|---|---|---|---|---|---|
| Power ctrl (ATXPSON#/PWRBTN#/SYSRESET#/PWRGD) §11 | [27] | ✅ | 🔶/🔶 | ✅/✅/✅ | 🔶(driver runs)/⬜ | Zephyr GPIO drives real power line on silicon |
| Platform monitors (THERMTRIP#/PROCHOT#/DDR_THERM#/NMI#) §11 | [28] | 🔶 | ⬜ | 🔶/⬜/⬜ | 🔶/⬜ | DTS gpio-line-names + silicon read (#136) |
| Platform ctrl (CLRTC#/BIOSREVRY#/CPUnDISABLE#/PCIRST#) §11 | [29] | 🔶 | ⬜ | 🔶/⬜/⬜ | 🔶/⬜ | Same (#136) |
| UART console (UART2/AST_UART1) §12 | [30] | ✅ | ✅/✅ | ✅/✅/✅ | 🔶(M0 console)/⬜ | Zephyr ns16550 console (arm_mmu z_phys_map gap) |
| UART1 / SOL via QU8 mux → SuperIO §12 | [31] | 🔶 | Ⓝ | 🔶/⬜/⬜ | ⬜ | **SOL-mux QEMU** + Linux SOL (#133/D10) |
| JTAG (ARM debug) §13 | [G1] | ✅ | Ⓝ | Ⓝ | Ⓝ | HW debug path (used for all silicon tests) |
| LEDs (BMCRDY/CPUnERR/MLED/chassis-ID) §13 | [32] | 🔶 | Ⓝ/Ⓝ | 🔶/✅/✅ | 🔶/⬜ | Zephyr LED-GPIO silicon |
| Straps (IKVMEN#/SOLEN#/IPMI_SEL) §13 | [33] | ✅ | ✅/✅ | ✅/✅/Ⓝ | 🔶/⬜ | Zephyr strap-read silicon |
| 24 MHz clock in (QOSC1) §13 | [35-SCU] | ✅ | ✅ | ✅ | 🔶 | Folds into SCU clock (#142) |

---

## Rolled-up open frontiers (what "not complete" means, concretely)

1. **QEMU ⬜ (4):** DDC/EDID [14], LPC-mailbox [B], SOL-mux [31], SMBus-ALERT [25].
   (PSU-PMBus [24] closed 2026-07-19.)
2. **Zephyr breadth:** ZS done for GPIO/timer/VIC/WDT/I2C/W83795; SB-TSI ZS needs host
   power; the many optional Zephyr I²C-client + ethernet + console drivers remain ⬜.
3. **Silicon breadth:** NC-SI silicon [11]; the §11 GPIO monitors/control silicon
   [28/29]; MTD-write [2]; SOL silicon [31]; PCI/video-capture completeness [D04].
4. **Open tasks:** #132 NC-SI, #133 SOL, #134 LPC, #136 GPIO map, #137 modern U-Boot,
   #140 sub-blocks, #142 SCU rate, #143 musl CI, #144 phantom cleanup, #150 Zephyr
   silicon breadth, #153 doc-hygiene, #154 Kconfig family rename.

**No device in the schematic (§1–16) is un-enumerated here.** Every §-section device
maps to a matrix row + a stack-task line above; the only "not a driver target"
entries are the power rails (§2), ground/decoupling, and the passive series-R/mux
glue chips (QRNx/QU9/QU5/U23/QU6/QU8 — modeled as behaviour on the buses they gate,
not as addressable devices).

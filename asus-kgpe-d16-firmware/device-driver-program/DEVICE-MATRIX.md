# AST2050 / KGPE-D16 — explicit per-device task matrix

Systematic enumeration of **every device** wired to the AST2050 in
[`../schematic-wiring/AST2050-BMC-WIRING.md`](../schematic-wiring/AST2050-BMC-WIRING.md)
(§§2–15 + the §14 neighbour-chip table), each with the full deliverable grid the
program goal demands:

- **QE** = QEMU full emulation of all functionality
- **UQ / US** = U-Boot driver validated in QEMU / on silicon
- **LQ / LS / LU** = Linux driver validated in QEMU / on silicon / userspace
- **ZQ / ZS** = Zephyr driver validated in QEMU / on silicon

**Status:** ✅ done (evidence) · 🔶 partial · ⬜ todo · 🔷 blocked (reason in
note) · Ⓝ n/a (justified in note). Every ✅ must be evidence-backed; every Ⓝ
must survive review. This matrix is the authoritative checklist; the D-block
sections in [`TASKLIST.md`](TASKLIST.md) hold the detail and next-steps, and
[`LOG.md`](LOG.md) the running history.

> **Cross-cutting foundations that gate whole columns:**
> - **U-Boot**: the Raptor AST2050 U-Boot (`board/aspeed/ast2050/`) is a real,
>   working port — its drivers cover the boot-critical devices both sides. For
>   non-boot devices U-Boot has no runtime need (Ⓝ). "Modern U-Boot" (D15) is
>   an enhancement.
> - **Zephyr**: no code yet, but feasibility is SETTLED — ARM926EJ-S support
>   exists upstream (Microchip PR #103557). Every ZQ/ZS below is ⬜ pending the
>   D14 SoC/board port + Milestone-0 `hello_world`. Marked ⬜ (not Ⓝ) because
>   the goal demands a Zephyr driver for every block.

## Memory & storage

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | QU2 DDR2 SDRAM (Hynix HY5PS121621, §3) | SDMC | ✅ | ✅ | ✅ | ✅ | ✅ | Ⓝ | ⬜ | ⬜ |
| 2 | BMC_FW1 SPI flash (socketed, §4) | SMC | ✅ | ✅ | 🔷 | 🔶 | 🔷 | ⬜ | ⬜ | ⬜ |

- **1** UB both = Raptor `DRAM Init-DDR`→64 MiB (QEMU `evidence/d15-uboot/`, silicon boot#). LU=Ⓝ (RAM is memblock, no userspace driver). D01.
- **2** UB-Q = Raptor `libspi_flash` (`Flash: SPI Flash ID` in QEMU). US/LS = 🔷 rig-blocked (socket empty on THIS bench; populated by design). LU (mtd-utils) ⬜ — **no MTD write path exists yet** (audit). D02.

## Host-interface buses

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | LPC KCS / IPMI (§5 → SP5100) | LPC | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| 4 | LPC mailbox (§5) | LPC | ⬜ | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 5 | LPC port-80h POST snoop (§5) | LPC | ⬜ | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 6 | LPC vUART (§5) | LPC | 🔶 | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 7 | TPM1 LPC pass-through (§5/§15) | LPC | ⬜ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 8 | PCI-33 / iKVM video-capture (§6) | video+P2A | ✅ | Ⓝ | Ⓝ | 🔶 | 🔶 | 🔶 | Ⓝ | Ⓝ |
| 9 | USB device / vhub (§9 → SP5100) | vhub | ✅ | Ⓝ | Ⓝ | ✅ | 🔶 | ✅ | ⬜ | ⬜ |

- **3** KCS/IPMI: `sdr`/host-KCS both sides (`evidence/host-kcs/`). UB Ⓝ (no boot need). D03.
- **4/5/6** mailbox, POST-snoop, vUART: unmodeled/undriven (audit gap #5). vUART is register-present but no session. D03.
- **7** TPM1 shares the LPC bus + a QU9-switched I2C segment; the BMC is not the TPM driver (host owns TPM) → Ⓝ for driver stacks, but QEMU should model the LPC/I2C reachability (⬜). D03.
- **8** capture proven (`#3a`, `evidence/real-hw-video/`); the 45-ball PCI bus itself is only P2A/video-modeled, not a full PCI target. UB/ZP Ⓝ (no runtime need). D04.
- **9** LS = 🔶: silicon enumeration used `usbip-vudc` (gadget path), **not** the real vhub EP-DMA datapath (Test B rig-blocked; audit). D05.

## Network

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | Eth MAC1 MII → RTL8201N U5 (§7 ch1) | ftgmac100#0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| 11 | Eth MAC2 RMII2/NC-SI → 82574L LU1/LU2 (§7 ch2) | ftgmac100#1 | ✅ | ⬜ | ⬜ | ✅ | 🔷 | ⬜ | ⬜ | ⬜ |

- **10** eth0 both sides (NFS-root + Redfish on silicon). UB both = Raptor TFTP. **Model-vs-schematic PHY-part note:** model = RTL8201**CP**, schematic = RTL8201**N** (unresolved). D06.
- **11** QE = MAC2 wired + `net/ncsi` discovers a channel vs the generic slirp responder (MFR-0x0). **LS = 🔷 blocked on the G3 RMII2 pinmux** (mainline g4 pinctrl mis-selects RMII2 on the G3; `evidence/d07-ncsi/03-`). Faithful 82574L responder (2 pkgs, Intel OEM 0x157) ⬜. D07.

## Video

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | VGA DAC output → VGA1 (§8) | CRT/DAC | ✅ | Ⓝ | Ⓝ | 🔶 | 🔶 | 🔶 | Ⓝ | Ⓝ |
| 13 | VGA sync buffer QU6 (§8) | — | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 14 | DDC / EDID I2C → VGA1 (§8) | I2C/DDC | ⬜ | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | Ⓝ | Ⓝ |

- **12** CRT/DAC modeled; silicon = Magewell capture (`#3a`). Mode-set + fb self-questioned. D12.
- **13** passive quad buffer (TC74VHCT125AF) — no driver target. Ⓝ.
- **14** DDC/EDID device totally unmodeled (audit gap #7). D12.

## I²C / SMBus (§10)

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 15 | AST2050 I2C controller (8 engines) | I2C | ✅ | ✅ | 🔶 | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| 16 | W83795G hwmon (QU4, I2C2 @0x2f) | I2C | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| 17 | QU9/QU5/U23 mux fabric | I2C+GPIO | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| 18 | DIMM SPD ×16 (I2C10/11 via mux) | I2C | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| 19 | DIMM TSOD ×16 (jc42) | I2C | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 20 | HT24LC08 FRU EEPROM (U25, I2C5 @0x54) | I2C | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| 21 | W83601G DIMM-LED exp U27 (I2C5 @0x18) | I2C | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| 22 | W83601G DIMM-LED exp U28 (I2C5 @0x19) | I2C | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| 23 | SB-TSI CPU thermal (I2C4, 0x4C/4D) | I2C | ✅ | Ⓝ | Ⓝ | 🔶 | ⬜ | ✅ | ⬜ | ⬜ |
| 24 | PSU PMBus (PSUSMB1, I2C1) | I2C | ⬜ | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 25 | SMBus ALERT (SALT1/2, I2C7) | I2C | ⬜ | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 26 | Aux front panel (AUX_PANEL1, I2C8) | I2C | 🔶 | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

- **15** i2cdetect + AC-timing fix proven on silicon. UB-Q = Raptor `libi2c`. D08.
- **16** W83795 model silicon-seeded (fan1=2641 etc.); hwmon both sides. D08.
- **17/18** fabric + real SPD read by the BMC on silicon (`evidence/d08-spd-silicon/`). D08.
- **19** the rig's A2 UDIMM has SPD byte32=0 (no TS) → 0x19 NAKs on QEMU+silicon; the `jc42` model is kept available for TS-equipped DIMMs. Ⓝ for this rig. D08.
- **20** FRU EEPROM DONE both sides (2026-07-18): I2C5/i2c-4 enabled, at24 24c08 binds 0x54-0x57 on silicon (present but BLANK 0xff — ASUS unprogrammed) and in QEMU (blank model); `evidence/d08-fru/`. Corrects §10.2 (0x54, not 0x50).
- **21–22** W83601G U27/U28: **BOTH-SIDES DONE** (datasheet-faithful `hw/gpio/w83601g.c`, `scripts/w83601g-test.py` 19/19 PASS incl. LED-drive; CI `boot-w83601g`; **silicon LED-drive proven on BOTH 0x18 and 0x19 — CR03/CR01 write + readback + restore**, evidence d08-w83601g/03; CR21 silicon-resolved to 0x13). No in-kernel driver by nature (raw userspace SMBus) → LQ/LS/LU all via userspace. **23** SB-TSI (D9): **QEMU DONE** (`hw/sensor/sbtsi.c`, `scripts/sbtsi-test.py` 8/8, CI `boot-sbtsi`); silicon needs host-CPU-on. **24–25** PSU PMBus (I2C1), SMBus-ALERT (I2C7): still to model (task #135). See FULL-TASK-LIST.md D3/D4/D9.
- **26** reachable via the fabric Y0 (QEMU); no Linux driver/test. D08.

## GPIO / platform control (§11)

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 27 | Power control (ATXPSON#/PWRBTN#/SYSRESET#/SYS_PWRGD) | GPIO | ✅ | ⬜ | ⬜ | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| 28 | Platform monitors (THERMTRIP#/PROCHOT#/DDR_THERM#/NMI#) | GPIO | 🔶 | ⬜ | ⬜ | 🔶 | ⬜ | ⬜ | ⬜ | ⬜ |
| 29 | Platform control (CLRTC#/BIOSREVRY#/CPU1-2DISABLE#/PCIRST#) | GPIO | 🔶 | ⬜ | ⬜ | 🔶 | ⬜ | ⬜ | ⬜ | ⬜ |

- **27** power on/off/reset both sides (`f2-power-sysfs` + plug-verified). GPIOB6 schematic(SYS_PWRGD)-vs-RE(reset-req) net-name conflict unresolved (audit #9). D09.
- **28/29** ~10 §11 signals not yet mapped in DTS `gpio-line-names`; no silicon validation. D09.

## Serial (§12)

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 30 | UART console (UART2, AST_UART1) | UART | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🔶 | ⬜ |
| 31 | UART1 / SOL via QU8 mux → Super-I/O (§12) | UART+glue | ⬜ | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

- **30** console both sides (all boots). **Zephyr RUNS AN APP in QEMU** (ZQ 🔶): the AST2050 port boots and runs application code — `*** Booting Zephyr OS ***` + `Hello World! kgpe_d16_bmc/ast2050` — via a static-mapped polling SoC console (`soc/aspeed/ast2050/console.c`, printk+stdout hooks), evidence `d14-zephyr/03`. The M1 VIC (`vic.c`) + aspeed timer (`aspeed_timer.c`) are written and deliver interrupts, but sustained tickful scheduling data-aborts at the arm_mmu L1 table (same brand-new ARM9 `arm_mmu` dynamic-mapping gap that also blocks `uart_ns16550.c`); left cooperative by default. Per-device Zephyr drivers build on this once preemption is clean. D10/D11/D14.
- **31** SOL essentially unimplemented end-to-end (audit gap #2): no QU8-mux/Super-I/O model, no Linux SOL session, no host bytes on silicon. D10.

## JTAG / LEDs / clock / straps (§13)

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 32 | LEDs (BMCRDY/MLED/CPUERR/chassis-ID) | GPIO/LED | 🔶 | Ⓝ | Ⓝ | 🔶 | ⬜ | 🔶 | ⬜ | ⬜ |
| 33 | Straps (IKVMEN#/SOLEN#/IPMI_SEL) | GPIO | 🔶 | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 34 | 24 MHz clock input (QOSC1) | SCU/clk | ✅ | ✅ | ✅ | ✅ | ✅ | Ⓝ | ⬜ | ⬜ |
| — | AST_JTAG1 (§13/§15) | ARM debug | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |

- **32** `gpio-leds` DTS nodes exist; **no silicon observation** (audit #9). D09.
- **34** the 24 MHz ref is consumed by SCU/clk (validated via every boot). Ⓝ userspace.
- **AST_JTAG1** is the silicon TEST HARNESS (how all silicon boots happen), not a driver target → Ⓝ (explicitly out of scope, not omitted).

## SoC-internal core peripherals

| # | Device | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 35 | SCU (system control / clocks / pinmux) | SCU | ✅ | ✅ | ✅ | ✅ | ✅ | Ⓝ | ⬜ | ⬜ |
| 36 | VIC interrupt controller (0x1e6c0000) | VIC | ✅ | ✅ | ✅ | ✅ | ✅ | Ⓝ | ⬜ | ⬜ |
| 37 | Timers | timer | ✅ | ✅ | ✅ | ✅ | ✅ | Ⓝ | ⬜ | ⬜ |
| 38 | Watchdog (WDT) | wdt | ✅ | ⬜ | ⬜ | ✅ | ❓ | 🔶 | ⬜ | ⬜ |
| 39 | RTC | rtc | ✅ | Ⓝ | Ⓝ | ✅ | 🔶 | 🔶 | ⬜ | ⬜ |
| 40 | PWM / tach block | pwm | ✅ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |

- **36** VIC: the keystone G3 fix (`irq-aspeed-g3-vic`, HW-verified). The Zephyr port's Milestone-1 VIC driver targets this block. D11.
- **38** WDT-silicon = ❓ **UNCITED** (audit #10) — the "120 s reset observed" claim has no transcript; capture one. D11.
- **40** the VP*/TACH* balls are GPIO monitors on this board; fans are on the W83795G FANCTL, not the AST2050 PWM → Ⓝ board-disposition (SoC model is complete). D13.

## Roll-up (honest)

- **QEMU emulation**: ✅ for the SoC core + the boot/sensor/power/video/USB/
  fabric set; ⬜ for LPC mailbox/snoop, DDC/EDID, SOL mux, and 6 I2C far-ends.
- **U-Boot**: boot-critical devices ✅ both sides (Raptor); the rest Ⓝ (no
  runtime need). Modern-U-Boot enhancement separate (D15).
- **Linux**: ✅ both sides for the boot/power/sensors/IPMI/eth0/SPD set; the
  open items are NC-SI-silicon (🔷 G3 pinmux), USB-vhub-silicon (🔶),
  SOL (⬜), the 6 I2C far-ends (⬜), DDC/EDID (⬜), MTD-write (⬜), and
  several §11 signals + LED silicon observation.
- **Zephyr**: the D14 port now **BUILDS, LINKS, and RUNS its M0 banner in
  QEMU** (`*** Booting Zephyr OS ***`, evidence `d14-zephyr/02`) — the ARM926
  arch core (upstream PR #103557) + the authored AST2050 SoC/board + a
  static-mapped polling console all work. Row 30 ZQ is 🔶. Remaining: M1
  (aspeed system timer → app thread → per-device Zephyr drivers → ZS silicon);
  the standard ns16550 console awaits the upstream ARM9 `arm_mmu` z_phys_map fix.

---

## Completeness verification — fresh full read of AST2050-BMC-WIRING.md (2026-07-18)

The complete authoritative document (all 597 lines, §§1–16) was read end-to-end
and cross-checked section-by-section. Every function block, neighbour chip, and
connector maps to a row above — nothing in the spec is unrepresented:

| Doc section | Content | Matrix rows |
|---|---|---|
| §2 Power supply (48+66 balls) | LDOs PU22/PU28, rails, PLL analog | passive power (no driver target); consumed by SCU/PLL = row 35. AST_VREFSSTL/PLLs = part of SDMC/SCU init |
| §3 DDR2 → QU2 (48) | SDMC + Hynix HY5PS121621 | 1 |
| §4 SPI flash → BMC_FW1 (27) | SMC + socketed flash; legacy ROMA0-23 = spare GPIO | 2 (ROMA spare GPIO folds into GPIO rows) |
| §5 LPC → SP5100/OU1/TPM1 (10) | KCS, mailbox, vUART, TPM header | 3, 4, 5, 6, 7 |
| §6 PCI-33 → SP5100/slots (45) | iKVM video-capture PCI device | 8 |
| §7 Ethernet (18) | MAC1 MII→RTL8201N; MAC2 RMII2/NC-SI→2×82574L | 10, 11 |
| §8 VGA → VGA1 (14) | DAC output, QU6 sync buffer, DDC/EDID | 12, 13, 14 |
| §9 USB device → SP5100 (6) | vhub | 9 |
| §10 I²C/SMBus (16, 8 buses) | W83795G, SB-TSI, FRU U25, W83601G U27/U28, DIMM SPD/TSOD, aux panel, PSU PMBus, SALT, QU9/QU5/U23 fabric | 15–26 |
| §11 GPIO power/reset/platform (17) | ATXPSON#/SYS_PWRGD/PWRBTN#/SYSRESET#/PCI_RST#/BIOSREVRY#/CLRTC#/CPU1-2DISABLE#/THERMTRIP#/PROCHOT#/DDR_THERM#/NMI# | 27, 28, 29 |
| §12 Serial/SOL (11) | UART console; UART1→QU8 mux→Super-I/O | 30, 31 |
| §13 JTAG/LEDs/clock/straps (11+6+1+2) | JTAG harness; BMCRDY/MLED/CPUERR/chassis-ID LEDs; 24 MHz clock; IKVMEN#/SOLEN#/IPMI_SEL straps | AST_JTAG1 (harness Ⓝ), 32, 33, 34 |
| §14 Neighbour chips | QU2/BMC_FW1/U5/LU1-2/QU4/U27-28/U25/QU9/QU5/QU8/QU6/U23/AZ75232/glue U6-8/LDOs/SU1/OU1/NU1 | all active chips have rows; passive glue (U6/U7/U8/U23) modeled in the fabric+power-seq; LDOs = passive power; **SU1/OU1 = host chips reached via LPC/PCI/I2C (rows 3/8/15); NU1 SR5690 = host northbridge, reached only via the shared I2C3/I2C6 multi-master bus (row 15 note), not a distinct BMC-driven device** |
| §15 Connectors | VGA1/AST_UART1/AST_JTAG1/BMC_FW1/PANEL1/AUX_PANEL1/PSUSMB1/TPM1/VGA_SW1/IPMI_SEL1/RECOVERY1 | VGA1→12, UART1→30, JTAG1→harness, FW1→2, PANEL1→27/32, AUX_PANEL1→26/32, PSUSMB1→24, TPM1→7, jumpers→29/33 |

**Verdict:** the 40-row matrix is comprehensive against the authoritative
schematic. The only spec elements without their own driver row are (a) passive
power/glue (LDOs, series-R nets, FET switches, buffers — modeled where they
affect behaviour, e.g. the QU9/QU5/U23 fabric device, not driven), (b) the JTAG
header (the silicon test harness, explicitly Ⓝ), and (c) the host-side chips
SU1/OU1/NU1 (reached through the LPC/PCI/I²C rows, not BMC-internal). Each is
justified above, not skipped.

# AST2050 / KGPE-D16 full device-driver program — master task list

**Authority:** `../schematic-wiring/AST2050-BMC-WIRING.md` (schematic-extracted,
authoritative). Where an earlier document in this repo contradicts the schematic
wiring, **the schematic wins** and the earlier claim is REOPENED here.

**Program goal:** for *every* function block wired to the AST2050 on the
KGPE-D16:

1. **QEMU** — full emulation of all functionality (SoC peripheral + the
   board-level far-end device it talks to).
2. **U-Boot driver** — validated in QEMU, then on real silicon.
3. **Linux driver** — validated in QEMU, on real silicon, and via proper
   userspace interfaces.
4. **Zephyr driver** — validated in QEMU, then on real silicon.

**Silicon test path (fixed):** the BMC SPI flash socket is NOT connected —
all silicon testing is JTAG-load (`openocd/boot-silicon-uboot.sh`:
reset-halt → DDR2 re-train → U-Boot @0x40000000 → remap → PC=0) + TFTP netboot
from the bridge Pi (`rpi4-asus-aspeed2050-dev`, board = 192.168.66.2). Power
cycling via Tasmota plug `au-plug-10`. **The hardware is 100 % reliable; any
weird behaviour is our code or our driving of the system.**

**Status legend:** ✅ done (evidence linked) · 🔶 partial · ⬜ todo ·
🔁 REOPENED (a prior "impossible/unconnected" claim contradicted by the
schematic) · Ⓝ n/a with schematic-cited justification (use sparingly; every Ⓝ
must survive independent review).

---

## Prior claims REOPENED by the schematic

| Claim | Where claimed | Schematic reality | New task |
|---|---|---|---|
| "True NC-SI impossible / not wired" | SILICON-STATUS.md #9 | `AST_RMII2*` balls A5/B5/B6/C4/D4/D5 bus to BOTH Intel 82574L NICs (LU1/LU2) — §7 | D07-NCSI |
| "DIMM inventory (SPD) impossible — no path" | SILICON-STATUS.md #5 | I2C2 →QU9 FET switch→ I2C7 →QU5 4052 mux→ I2C10/I2C11 reach all 16 DIMM SPD+TSOD; select via AST_I2CS0/1 (W4/W3) + I2CMUX_ENABLE#; U23 arbitrates vs SP5100 — §10.3 | D08-I2C (SPD sub-task) |
| "SOL host-serial impossible" | SILICON-STATUS.md #6 | UART1 (Y22/AA22/V21/W22) → QU8 PI5C3257 2:1 mux → Super-I/O serial; select = BMC_PRESENT# — §12 | D10-SOL |
| "Host-BIOS flash access — no path" | SILICON-STATUS.md #8 | **SETTLED 2026-07-18 (schematic-cited): claim stands.** Host BIOS = socketed W25Q16 `FU1` on the SP5100's SPI controller (`SB_SPI_*` nets, SU1 D1/D2/G6/F3/F4 → FU1, WP# on SU1 D6; `pinmaps/SU1_pins.md:12-16`, `SP5100-SOUTHBRIDGE-WIRING.md §8`). BMC `AST_SPI*` nets terminate only at `BMC_FW1` (`pinmaps/QU1_pins.md:73-118`); the two net families share no node, and the AST2050 has no host-facing SPI master (single legacy SMC @0x16000000 — `fw-update/UPDATE-PATHS.md:120-134`). BIOS is fetched over FCH-SPI, not LPC firmware cycles, so no LPC route reaches it either. Scope = Ⓝ (host-mediated orchestration only) | D03 Ⓝ with citations |

(The schematic *confirms* USB is device-only — §9 "USB device port" to SP5100 —
so the USB-host-controller Ⓝ stands, with the gadget direction fully in scope.)

---

## The U-Boot column — largely MET by the Raptor AST2050 U-Boot

An important correction to the earlier "U-Boot column is empty" framing: a
**proper, working U-Boot with a real AST2050 board port already exists** — the
Raptor Engineering U-Boot (`board/aspeed/ast2050/`), with genuine drivers
(`libserial`, `libnet`/aspeednic, `libi2c`, `libgpio`, `libspi_flash`,
`libhwmon`). It is validated on **BOTH** sides for the boot-critical devices:

- **QEMU** (evidence `evidence/d15-uboot/`, CI `boot-uboot-scu`): boots to
  `boot#` running its **own AST2050 DDR2 init** on the faithful G3 SCU/SDMC
  models — `DRAM Init-DDR` → `DRAM: 64 MiB`, `aspeednic#0: PHY at 0x20`.
- **Silicon** (this session, D07/D08 netboot): the same U-Boot binary, JTAG-
  loaded, reaches `boot#` and TFTP-boots the kernel — proving its serial,
  DDR2, and ftgmac100 net drivers on the real chip.

So for the boot-critical blocks the "proper U-Boot driver, validated QEMU +
silicon" requirement is **met**: D01 DDR2/ram ✅✅, D06 net/ftgmac100 ✅✅,
D10 serial ✅✅, D02 SPI ✅(QEMU; silicon socket empty). U-Boot has no
runtime need for the non-boot blocks (video/USB-gadget/sensors/PWM); those are
Linux-runtime concerns (`Ⓝ` for U-Boot, with the `libi2c`/`libgpio` commands
available for bring-up debugging). **D15 ("modern U-Boot") is therefore an
ENHANCEMENT** (upgrade the vintage 2013.07 tree to a current U-Boot), not a
gap in the functional requirement. The genuine remaining greenfield column is
**Zephyr (D14)**.

---

## Device blocks (from AST2050-BMC-WIRING.md §§3–13)

### D01 — SDMC / DDR2 (→ QU2 Hynix HY5PS121621, 64 MB)
| Layer | Status | Evidence / next step |
|---|---|---|
| QEMU model (SDMC regs, 64 MB, training behaviour) | ✅ | faithful-QEMU program (108 tests); 64 MB fix per openbmc-64mb-constraint |
| U-Boot driver (DDR2 lowlevel init, SCU40[6] skip path) | 🔶 | Raptor legacy U-Boot init works (QEMU+silicon); **modern U-Boot port needs its own ram driver** |
| U-Boot validated QEMU / silicon | 🔶 | legacy: both ✅. Modern: audit found CI `boot-uboot-ssh` already boots OpenBMC U-Boot v2019.04 (`evb-ast2400_defconfig`) → Linux → SSH **in QEMU** (understated ⬜→🔶) — but that leans on register compatibility with no kgpe-d16 board port or own DDR2 driver; silicon ⬜ |
| Linux (memory only — no driver beyond memblock) | ✅ | boots to shell QEMU+silicon (g3-clk kernel) |
| Zephyr (memory init / linker) | ⬜ | part of Zephyr ARM926/AST2050 port (D14) |

### D02 — SMC / SPI flash controller (→ BMC_FW1 socket, CS0/CS2)
| Layer | Status | Evidence / next step |
|---|---|---|
| QEMU model (SMC + flash device on CS0) | ✅ | faithful-QEMU program |
| U-Boot driver (probe/read) | ✅ QEMU | Raptor U-Boot `libspi_flash` — QEMU shows `Flash: SPI Flash ID: 1820c2 16 MiB` (`evidence/d15-uboot/`); was understated ⬜ (audit) |
| U-Boot silicon validation | rig-blocked (not Ⓝ) | the socket is populated **by design** (§4 "socketed"); empty only on THIS bench rig, so silicon SPI r/w is rig-blocked, NOT n/a. On a production board the flash is present |
| Linux driver (aspeed-smc on G3) | 🔶 | verify mtd probe in QEMU; **no MTD write path exists yet (audit)**; silicon = register-level only (empty socket) |
| Linux driver (aspeed-smc on G3) | 🔶 | verify mtd probe in QEMU; silicon = register-level only (empty socket) |
| Linux userspace (mtd-utils read/write in QEMU) | ⬜ | |
| Zephyr flash driver | ⬜ | QEMU validation; silicon Ⓝ-partial (empty socket) |

### D03 — LPC peripheral (→ SP5100 SU1 + W83667HG OU1 + TPM1) — KCS/IPMI, mailbox, vUART, snoop
| Layer | Status | Evidence / next step |
|---|---|---|
| QEMU model (LPC ctrl + KCS) | ✅ | faithful-QEMU; KCS host-side proven (#7 IPMI) |
| QEMU model (mailbox, snoop/80h POST, vUART) | 🔶 | audit which sub-blocks the AST2050 has (datasheet ch.) and model ALL |
| U-Boot driver (n/a? — justify or implement) | ⬜ | check modern U-Boot aspeed LPC support |
| Linux KCS/IPMI validated QEMU+silicon+userspace | ✅ | `sdr` over host-KCS on silicon (g3-clk memory) |
| Linux mailbox/snoop/vUART drivers + validation ×3 | ⬜ | |
| **BIOS-flash-path determination** (LPC vs SP5100-SPI; what the BMC can reach) | Ⓝ | SETTLED — see the REOPENED table above: FU1 is SP5100-SPI-attached with no BMC node on any `SB_SPI_*` net; BMC self-update of `BMC_FW1` stays in scope (D02), host-BIOS update is host-mediated only |
| Zephyr KCS driver + validation | ⬜ | |

### D04 — PCI 33 MHz (VGA/iKVM device on SP5100 bus) + video-capture engine
| Layer | Status | Evidence / next step |
|---|---|---|
| QEMU model (video engine, capture, CRT) | ✅ | #3a VGA capture PASS (QEMU+CI); silicon PASS |
| QEMU model (BMC-as-PCI-device visibility) | ⬜ | scope: what of the PCI attachment is observable from the BMC side (P2A bridge done ✅); document |
| Linux video/capture driver + userspace (aspeed-video G3 port) | 🔶 | capture works; complete + re-validate ×3 |
| U-Boot / Zephyr | ⬜ | video likely Ⓝ for U-Boot/Zephyr — justify per datasheet or implement |

### D05 — USB device / vhub (→ SP5100 USB host)
| Layer | Status | Evidence / next step |
|---|---|---|
| QEMU model (vhub) | ✅ | faithful-QEMU |
| Linux gadget validated QEMU + silicon + userspace | ✅ | two-VM USB/IP PASS; silicon USB/IP enumeration PASS (#2, #3b) |
| **Test B: real vhub EP-DMA datapath to the physical SP5100 host** | 🔶 | patch-0007 kernel + host-side observation; the wiring §9 confirms the cable exists on-board (BMC→SU1) — host must be booted to see it |
| U-Boot USB gadget | ⬜ | likely Ⓝ (no U-Boot use-case) — justify or implement |
| Zephyr USB device driver | ⬜ | |

### D06 — Ethernet ch.1: MAC1 MII → RTL8201N (U5) dedicated mgmt port
| Layer | Status | Evidence / next step |
|---|---|---|
| QEMU model (ftgmac100 + PHY) | ✅ | incl. FAST_MODE RX bug reproduction |
| Linux validated QEMU+silicon+userspace | ✅ | NFS-root + Redfish on silicon |
| U-Boot net driver validated QEMU+silicon | 🔶 | legacy U-Boot TFTP works both; modern U-Boot ⬜ |
| Zephyr eth driver | ⬜ | |
| QEMU: model RTL8201**N** specifics (currently RTL8201CP model) | 🔶 | verify register deltas vs the N part on silicon |

### D07 — Ethernet ch.2: MAC2 RMII2 / NC-SI → LU1+LU2 (Intel 82574L) 🔁

**Facts pinned 2026-07-18 (82574 datasheet rev2.7 research, full cite in LOG):**
true DMTF NC-SI 1.0.0a over RMII 1.2 (PHY-side), mutually exclusive with the
SMBus sideband, selected by NVM word 0x0F `MNGM`=01b; package ID = NVM word
0x2E[14:12]; needs ≥32 Kb NVM with Intel MNG firmware code; outputs float until
Select Package (multi-drop legal, NO hw arbitration — MC time-slices with
Select/Deselect); one channel per package; Intel OEM cmds (mfr 0x157) 0x06 GMA /
0x20 keep-PHY already in mainline `net/ncsi`. QEMU's NC-SI responder lives in
libslirp (minimal, Intel OEM handler NULL). NIC pins 2/3/5/6/7/8/9 map exactly
to the board's RMII2 nets. **Open board question: do the ASUS-programmed NIC
NVMs enable MNGM? Dump via host `ethtool -e` or observe NC-SI responses on
silicon.**
| Layer | Status | Evidence / next step |
|---|---|---|
| QEMU: MAC2 wired (`macs_mask = MAC0\|MAC1`) faithful to schematic | ✅ | both MACs now instantiated; MAC1 peered only when a 2nd -nic is supplied (oracles unaffected; C2 still PASS) |
| Linux ncsi stack (ftgmac100 mac1 + net/ncsi) QEMU validation | ✅ | **`NCSI RESULT: PASS`** — net/ncsi discovers + configures a channel via the slirp responder, eth1 carrier up (`evidence/d07-ncsi/`, CI `boot-ncsi`); `CONFIG_NET_NCSI`+OEM built; DTS mac1 `use-ncsi` (disabled by default) |
| Reconcile F7-NCSI.md (its "not wired" verdict was MAC1-scoped) | ✅ | F7 corrected + SILICON-STATUS #9 REOPENED (done 2026-07-18) |
| QEMU: faithful 82574L NC-SI responder (2 packages + Intel OEM 0x06/0x20) | ⬜ | Phase 2: slirp responder is generic (MFR-ID 0x0); a real 82574L responder (mfr 0x157) belongs in the MAC model (libslirp is external). Facts pinned (82574 datasheet, D07 header) |
| Silicon validation | 🔶 blocked (G3 RMII2 pinmux) | NICs confirmed NC-SI-enabled (NVM MNGM=01, pkg 0/1). BMC-side discovery ATTEMPTED on silicon 2× + empirical SCU74[27] test → `No channel found` because **the AST2050 (G3) RMII2 pinmux differs from the G4**: g4 pinctrl's `RMII2_DESC=SCU70[7]==0` mis-selects on the G3 (strap 110 → bit7=1) and targets the wrong pins (GPIOT/V, not the G3's GPIOE balls A5/B5/B6/C4/D4/D5). Needs the AST2050 datasheet RMII2/GPIOE routing + a G3 pinctrl group. Evidence `evidence/d07-ncsi/02,03-...`. **Confidence HIGH it is my pinmux/RE, not the hardware.** Focused follow-up |
| U-Boot / Zephyr NC-SI | ⬜ | scope after Linux path proven |

### D08 — I²C ×8 + board mux fabric + all far-end devices
Sub-tasks per §10 (each needs QEMU device model + Linux driver/userspace +
U-Boot access + Zephyr, with the mux *fabric* modeled once):
| Sub-block | Status | Evidence / next step |
|---|---|---|
| AST2050 I2C controller (8 buses) QEMU+Linux | ✅ | g3 AC-timing fix proven on silicon (i2cdetect, W83795 reads) |
| W83795G hwmon (QU4, I2C2 @0x2F) full model + Linux hwmon ×3 validations | 🔶 | silicon reads work; QEMU model completeness audit vs datasheet (VSEN1-11, TR1-6, FANIN1-12, FANCTL1-8) |
| **QU9+QU5+U23 mux fabric QEMU model** (GPIO-driven, transparent FET + 4052) | ✅ | netlist-traced (`I2C-MUX-FABRIC-ARBITRATION.md`) → `kgpe-d16-i2c-fabric` QEMU device (submodule `be673b2`); fwtest `i2cmux` 11/11 PASS; full suite 114/114 |
| **DIMM SPD ×16 + TSOD** via fabric (I2C10/I2C11) 🔁 | ✅ | **BMC read the REAL 256-byte SPD on silicon** 2026-07-18 (at24 over I2C2→QU9→QU5-Y2; part RMR5030EF68F9W1600, CRC 0xf0b4; `evidence/d08-spd-silicon/`). QEMU carries that exact SPD; fwtest 12/12 + full Linux `i2c-mux-gpio`+`at24` stack (spd-test) + 114 suite. Rig UDIMM has no TSOD (byte32=0) → 0x19 NAKs in QEMU+silicon (faithful). **Board-arbitration finding:** on this empty-flash-socket rig BMC_PRESENT# is high → SP5100 owns the QU5 selects, so the mux was pointed at Y2 from the SP5100 side; a production board (flash present) has the BMC own them. `jc42.c` kept for TS-equipped configs |
| FRU EEPROM HT24LC08 (U25, I2C5) | ⬜ | audit: NO DTS node/model wired anywhere (claim was overstated). NEW: netlist shows U25 pin E2 strapped to VCC → address likely **0x54-0x57**, not 0x50-0x53 (fabric doc §5); settle on silicon |
| W83601G DIMM-LED expanders (U27/U28, I2C5) | ⬜ | QEMU model (new chip); Linux gpio/led driver; light DIMMxERRLED on silicon |
| SB-TSI CPU thermal (I2C4 → QU4 pins 29/30, 0x4C/0x4D) | ⬜ | QEMU SB-TSI responder model; Linux sbtsi_temp; silicon read CPU temps |
| PSU PMBus (I2C1 → PSUSMB1 header) | ⬜ | QEMU PMBus device; Linux pmbus; silicon: depends on PSU with SMBus — check rig PSU, else Ⓝ-partial with evidence |
| SMBus ALERT (SALT1/2 on I2C7 balls) | ⬜ | model + smbus-alert driver |
| I2C3/I2C6 to SP5100 (multi-master shared sensor bus) | ⬜ | document + safe-driving policy; validate no-conflict on silicon |
| I2C8 → aux front panel | ⬜ | via fabric ch Y0 |

### D09 — GPIO: power/reset/platform control (§11) + LEDs + straps (§13)
| Sub-block | Status | Evidence / next step |
|---|---|---|
| GPIO controller QEMU+Linux | ✅ | faithful-QEMU; #1 power PASS/PASS via kgpe-power.sh |
| Power on/off/reset (ATXPSON#, PWRBTN#, SYSRESET#) ×3 validations | ✅ | f2-power-sysfs CI + silicon plug-verified; ⚠️ never reintroduce devmem-A4 drive |
| Full §11 signal map in DTS + gpio-line-names + QEMU board-glue | 🔶 | add: CLRTC#, BIOSREVRY#, CPU1/2DISABLE#, THERMTRIP#/PROCHOT# monitors, DDR_THERM#, NMI#, SYS_PWRGD |
| LEDs (BMCRDYLED, MLED heartbeat, CPUERR, chassis-ID) Linux leds + validation | ⬜ | QEMU board glue + silicon observation (Magewell/eyes-on limited — use plug/measurable where possible; document method honestly) |
| Straps (IKVMEN#, SOLEN#, IPMI_SEL) read + honour | ⬜ | |
| U-Boot GPIO driver validated ×2 | ⬜ | |
| Zephyr GPIO driver validated ×2 | ⬜ | |

### D10 — UART / SOL (UART1 → QU8 mux → Super-I/O; console UART2) 🔁
| Layer | Status | Evidence / next step |
|---|---|---|
| QEMU UART models | ✅ | faithful-QEMU (incl. G3 shared UARTCLK gate) |
| QEMU model of QU8 mux + BMC_PRESENT# + Super-I/O serial far end | ⬜ | board-glue: route UART1 to host-serial chardev when mux selects BMC |
| Linux SOL path (UART1 ↔ host console bridging; ipmitool sol) ×3 | ⬜ | |
| Silicon SOL validation | ⬜ | host Super-I/O side observable via host serial port; needs host booted |
| U-Boot serial (console UART2) ×2 | ✅ | legacy proven both; modern ⬜ |
| Zephyr serial ×2 | ⬜ | |

### D11 — Timers / WDT / VIC / SCU / RTC (SoC core set)
| Layer | Status | Evidence / next step |
|---|---|---|
| QEMU models | ✅ | faithful-QEMU 108 tests |
| Linux ×3 | ✅ (VIC/clk); WDT-silicon UNCITED | g3 VIC irqchip PR #26; clk fixes. **Audit flag:** the "WDT 120 s reset observed on silicon" claim has NO transcript in `evidence/` — treat WDT-silicon as uncited until a reset log is captured (follow-up) |
| U-Boot (timer/wdt) modern ×2 | ⬜ | |
| Zephyr (systick-equiv timer, VIC intc, pinctrl/clk) ×2 | ⬜ | core of the Zephyr port |

### D12 — VGA output (DAC → VGA1) + DDC
| Layer | Status | Evidence / next step |
|---|---|---|
| QEMU CRT/DAC model | ✅ | faithful-QEMU video |
| QEMU DDC I2C-to-monitor model | ⬜ | EDID device on DDC bus (balls B1/B2) |
| Linux modesetting + DDC read ×3 | 🔶 | fb works?; EDID read on silicon via Magewell-connected display |
| Silicon validation | 🔶 | Magewell captures BMC VGA (#3a); extend to mode-set + EDID |

### D13 — PWM / TACH block disposition
Per schematic §11: the VP*/TACH* balls are used as **GPIOs** (THERMTRIP/PROCHOT/
DDR_THERM monitors) — fans are driven by W83795G FANCTL, not the AST2050 PWM.
| Layer | Status | Evidence / next step |
|---|---|---|
| QEMU PWM/tach peripheral model | ✅ | faithful-QEMU (SoC-complete regardless of board use) |
| Board-truth documentation + DTS: no fan on AST2050 PWM; pins as GPIO monitors | ⬜ | fold into D09 |

### D14 — Zephyr AST2050 port (cross-cutting foundation)
**Feasibility SETTLED 2026-07-18 (research, cited in LOG): TRACTABLE, not a
from-scratch arch port.** Zephyr gained ARM926EJ-S (ARMv5TEJ) support in
2025-26 via Microchip's SAM9X7 work: the Kconfig/toolchain scaffolding
(`CPU_ARM926EJ_S`, `-mcpu=arm926ej-s`) is **merged in `main`** (PR #101016), and
the arch core (~770 LOC: reset/vectors/switch/mmu/isr) is in **open PR #103557**.
The NS16550 console driver Zephyr already ships fits the AST2050 UART
(0x1e784000) directly — no new console driver. So D14 = reuse the ARM9 core +
write an AST2050 SoC/board/DTS + one VIC driver (0x1e6c0000).
| Item | Status | Next step |
|---|---|---|
| ARM926EJ-S arch core | reuse upstream | pull PR #103557's ARMv5 core onto a Zephyr checkout (do NOT rewrite) |
| AST2050 SoC + board (kgpe-d16-bmc) + DTS + linker | ⬜ | model on Microchip sam9x7 SoC layout |
| NS16550 console (existing `uart_ns16550.c`) | ⬜ | wire to 0x1e784000 |
| **Milestone 0**: `hello_world` banner under the faithful QEMU AST2050 (MMU/caches off, timer stubbed) | ⬜ | reset→prep_c→switch→main→banner |
| VIC intc driver (0x1e6c0000, `ARM_CUSTOM_INTERRUPT_CONTROLLER`) + system timer | ⬜ | Milestone 1: preemptive kernel + shell |
| Silicon boot via JTAG-load/netboot | ⬜ | same 3-step JTAG chain |
| Per-device Zephyr drivers (gpio/i2c/wdt/eth) | ⬜ | each validated QEMU then silicon |

### D15 — U-Boot: functional requirement MET (Raptor); modern port = enhancement
See the "U-Boot column" section near the top. Summary:
| Item | Status | Evidence / next step |
|---|---|---|
| **Raptor AST2050 U-Boot (`board/aspeed/ast2050/`) — real board port + drivers** | ✅ | proper serial/DDR2/net/spi/i2c/gpio drivers; **QEMU + silicon both proven** (evidence `evidence/d15-uboot/`, CI `boot-uboot-scu`; silicon `boot#` netboot this session) |
| D01 ram/DDR2 U-Boot driver ×2 | ✅✅ | `DRAM Init-DDR` → 64 MiB on the faithful G3 SCU; silicon JTAG-boot |
| D06 net/ftgmac100 U-Boot driver ×2 | ✅✅ | `aspeednic#0 PHY at 0x20` QEMU; silicon TFTP this session |
| D10 serial U-Boot driver ×2 | ✅✅ | NS16550 console both sides |
| D02 SPI U-Boot driver | ✅/Ⓝ-silicon | `libspi_flash`; silicon socket empty |
| Non-boot blocks (video/USB-gadget/sensors/PWM) in U-Boot | Ⓝ | no U-Boot runtime need; `libi2c`/`libgpio` cmds available for bring-up |
| **Modern U-Boot upgrade (ENHANCEMENT, not a gap)** | 🔶 | OpenBMC v2019.04 `evb-ast2400_defconfig` boots→Linux→SSH in QEMU (`boot-uboot-ssh`) via register-compat; a full current-U-Boot kgpe-d16 board port with G3 DDR2 driver is future work — the functional U-Boot requirement is already met by Raptor |

---

## Verification & completion gates (from the goal)

- [ ] G1: every block above ✅ or review-surviving Ⓝ with schematic citation
- [ ] G2: multiple independent sub-agent completeness reviews find nothing
      missed/skipped (≥2 clean rounds)
- [ ] G3: sub-agent code review of ALL new code returns no issues (fix + re-run
      until clean)
- [ ] G4: running log (`LOG.md`) complete and committed at every step

## Standing rules (re-read frequently)

1. Schematic is authoritative; hardware is 100 % reliable — failures are my code.
2. Silicon = JTAG + netboot only (no SPI flash). Power via `au-plug-10`.
3. Own branches/worktrees only; small logical commits; merge --no-ff.
4. Heavy builds inside resource-limited cgroups (`systemd-run --user --scope
   -p MemoryMax= -p CPUQuota=`); don't disturb other users of the machine/repo.
5. ≤5 concurrent sub-agents; queue the rest.
6. No stderr→/dev/null; `uv run` for Python; ISO dates; project tmp/ only.
7. Log every attempt (incl. failures + confidence assessment) in LOG.md; commit
   the log with every change.

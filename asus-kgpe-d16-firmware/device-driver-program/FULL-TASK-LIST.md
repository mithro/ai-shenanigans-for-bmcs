# Full task list — every AST2050/KGPE-D16 device × QEMU + U-Boot + Linux + Zephyr

Created **2026-07-18** from a complete end-to-end read of the authoritative
schematic `schematic-wiring/AST2050-BMC-WIRING.md` (all 597 lines, §§1–16). This
is the formal, per-device task list the program is measured against. It is the
same coverage as [`DEVICE-MATRIX.md`](DEVICE-MATRIX.md) (the compact grid) but
expanded into the explicit required structure: for **every** device/function
block, a task for each of —

- **QEMU**: full functional emulation of the device.
- **U-Boot driver** → validate (a) in QEMU, (b) on real silicon.
- **Linux driver** → validate (a) in QEMU, (b) on real silicon, (c) userspace.
- **Zephyr driver** → validate (a) in QEMU, (b) on real silicon.

Status legend: `[x]` done + evidenced · `[~]` partial/in-progress · `[ ]` not
started · `[N]` not-applicable **with the reason stated** (never a silent skip)
· `[B]` blocked **with the blocker + confidence stated** (never "impossible").

Silicon is reached **only via JTAG + TFTP netboot** (the SPI flash is not wired
to the BMC on this rig); power-cycle via the `au-plug` Tasmota. The schematic is
authoritative; any "device absent / unconnected" reading is treated as my
bug/mis-driving, not a hardware fault.

U-Boot scope note: the working reference bootloader is **Raptor Engineering's
AST2050 U-Boot** (boots to `boot#`, hardware-proven), which drives the boot-path
SoC blocks (SCU/PLL, SDMC/DDR2, SMC, UART, MAC, timer, WDT, I2C). U-Boot does
**not** carry drivers for board-level sensors/expanders (those are Linux-
userspace or Zephyr) — such rows are `[N]` for U-Boot with that reason.

---

## A. Core SoC blocks (the AST2050 silicon itself)

### A1. SCU — clock / PLL / reset / straps (§2 power PLLs, §13 clock+straps)
- [x] QEMU: SCU/PLL/reset-table/strap model (faithful G3; P2A SCU7C=0x0202 == silicon)
- U-Boot: [x] QEMU (Raptor programs SCU/PLL) · [x] silicon (Raptor `boot#`, SCU70 freeze)
- Linux: [x] QEMU (clk driver, g3-clk patch) · [x] silicon (console survives clk gating) · [N] userspace (clocks are not a userspace ABI beyond debugfs)
- Zephyr: [~] QEMU (SoC pre-init assumes loader-configured SCU; no re-init needed) · [ ] silicon

### A2. SDMC — DDR2 controller → QU2 (§3)
- [x] QEMU: SDMC/DDR2 model (64 MB, MCR04=0x585, DLL)
- U-Boot: [x] QEMU (Raptor DDR2 init) · [x] silicon (JTAG DDR2 re-train MCR04=0x585 boots)
- Linux: [x] QEMU (RAM usable) · [x] silicon (kernel runs from 64 MB DDR2) · [N] userspace (RAM, not a device ABI)
- Zephyr: [x] QEMU (runs from DDR2 — Hello World) · [ ] silicon

### A3. SMC — SPI / ROM flash controller → BMC_FW1 (§4)
- [x] QEMU: SMC model (SPI CS0/CS2, m25p80)
- U-Boot: [x] QEMU (Raptor SMC) · [B] silicon (**rig limitation, NOT N/A: the SMC/SPI *is* the board's boot device by design, but the socketed flash is not populated/wired on this rig, so boot is JTAG+TFTP and the SMC read path is untestable here. Confidence: driver is correct in QEMU; blocker is the rig's missing flash, fixable by populating BMC_FW1**)
- Linux: [x] QEMU (spi-nor/MTD) · [B] silicon (same rig limitation — no BMC-attached flash to bind spi-nor to) · [ ] userspace MTD write path (`/dev/mtd*`) — QEMU-side TODO
- Zephyr: [ ] QEMU (spi-nor) · [B] silicon (same rig limitation)

### A4. VIC — interrupt controller 0x1e6c0000 (§ implied; datasheet §16)
- [x] QEMU: faithful G3 VIC (TYPE_ASPEED_2050_VIC, single-bank, sense/dual/event)
- U-Boot: [x] QEMU · [x] silicon (Raptor + our kernel take IRQs)
- Linux: [x] QEMU · [x] silicon (`irq-aspeed-g3-vic`, HW-verified) · [N] userspace (IRQs not a userspace ABI)
- Zephyr: [x] QEMU (`vic.c` delivers IRQs, storm-free after the edge-ack-at-claim fix) · [x] silicon (VIC delivers the timer IRQ storm-free on the real AST2050; commits b84ef58/78f5569, LOG 2026-07-19)

### A5. Timer (0x1e782000; §implied)
- [x] QEMU: aspeed timer model (G3 one-pulse-per-expiry)
- U-Boot: [x] QEMU · [x] silicon (Raptor timekeeping)
- Linux: [x] QEMU · [x] silicon (clocksource) · [N] userspace (POSIX time, not device ABI)
- Zephyr: [x] QEMU (tickful `aspeed_timer.c`, app runs to main) · [x] silicon (steady tickful scheduling on the real AST2050 — the earlier "sustained-tick data-abort" was the missing cache/TLB invalidate + the VIC edge-storm, both now fixed; commits 918bc7e/b84ef58/78f5569, LOG 2026-07-19)

### A6. WDT — watchdog (§implied)
- [x] QEMU: WDT model (aspeed 120 s reset behaviour)
- U-Boot: [~] QEMU · [ ] silicon
- Linux: [x] QEMU (aspeed_wdt) · [~] silicon · [ ] userspace (`/dev/watchdog`)
- Zephyr: [x] QEMU (`wdt_aspeed_g3` reset fires + reboots) · [x] silicon (armed→fed→timeout→true SoC reset, JTAG-proven MMU/caches-off; #149, LOG 2026-07-19)

### A7. RTC (§implied)
- [x] QEMU: RTC model
- U-Boot: [N] QEMU/silicon (Raptor U-Boot does not use the SoC RTC)
- Linux: [x] QEMU (rtc-aspeed) · [ ] silicon · [ ] userspace (`hwclock`/`/dev/rtc`)
- Zephyr: [ ] QEMU · [ ] silicon

### A8. AHB / P2A + LPC-to-AHB back-doors (§implied; datasheet)
- [x] QEMU: P2A window (SCU7C readback == silicon)
- U-Boot: [N] (debug back-door, not a boot driver) — used by culvert
- Linux: [x] QEMU · [x] silicon (culvert in-band devmem bridge) · [x] userspace (culvert probe EXIT 0)
- Zephyr: [N] (debug back-door)

### A9. ADC — voltage-monitor ADC 0x1E6E9000, IRQ 22 (RAPTOR-PORTING-GUIDE §"Change 16"; needs `aspeed,ast2050-adc`)  [added by gate-(d) audit 2026-07-18]
- [~] QEMU: VERIFIED the aspeed ADC IS modeled (`hw/adc/aspeed_adc.c`) and wired into the SoC at 0x1E6E9000 (aspeed_ast2400.c:41/574-580). One G3 faithfulness gap: the shared ast2400 irqmap gives the ADC **IRQ 31 (G4)**, but the AST2050 ADC is **IRQ 22** (Raptor guide). Moot for this board (ADC unused — VP pins are GPIO), so left as a small documented faithfulness note rather than forking the shared irqmap.
- U-Boot: [N] (voltage-monitor ADC is an OS/runtime function, not a boot driver)
- Linux: [ ] QEMU (`aspeed_adc` IIO driver + a G3 `aspeed,ast2050-adc` compatible) · [N] silicon (**board disposition: the ADC's VP0–VP17 analog inputs are repurposed on the KGPE-D16 as GPIOE/F digital lines — THERMTRIP#/PROCHOT#/DDR_THERM# (§11) — and board voltage monitoring is done by the W83795 (D2), so the SoC ADC is not wired to analog rails here; faithfully board-N/A**) · [ ] userspace (`/sys/bus/iio`, only if QEMU model exercised)
- Zephyr: [ ] QEMU · [N] silicon (board-N/A as above)

---

## B. Host-interface controllers

### B1a. LPC — KCS/IPMI channel → SP5100 (§5)
- [x] QEMU: LPC model with KCS state machine (datasheet §30, DEVICE-MATRIX row 3)
- U-Boot: [N] (host-IPMI is an OS-level function; U-Boot has no LPC-peripheral driver)
- Linux: [x] QEMU (`aspeed-kcs-bmc`, /dev/ipmi-kcs) · [x] silicon (phosphor-ipmi-kcs bound, host `mc info` answered) · [x] userspace (ipmitool over KCS)
- Zephyr: [ ] QEMU · [ ] silicon

### B1b. LPC — iBT/mailbox (host↔BMC message registers) (§5)  [split per gate-(d) audit]
- [ ] QEMU: `aspeed-lpc-mbox` register block not modeled (DEVICE-MATRIX row 4)
- U-Boot: [N]
- Linux: [ ] QEMU (`aspeed-lpc-mbox`) · [ ] silicon · [ ] userspace (`/dev/aspeed-lpc-mbox`)
- Zephyr: [ ] QEMU · [ ] silicon

### B1c. LPC — port-80h POST-code snoop (§5)  [split per gate-(d) audit]  ✅ QEMU BMC-side this session
- [x] QEMU: the G3 LPC model (`aspeed_lpc_ast2050.c`) services the snoop registers; enabled `&lpc_snoop { snoop-ports=<0x80> }` in the DTS → **the `aspeed-lpc-snoop` driver binds (`1e789090.lpc-snoop`) and creates `/dev/aspeed-lpc-snoop0`** (`scripts/lpc-test.py` PASS)
- U-Boot: [N]
- Linux: [x] QEMU (driver binds + snoop configured for port 0x80; `/dev/aspeed-lpc-snoop0` created) · [ ] silicon (**needs a host mid-POST to capture codes — the KGPE-D16's SP5100 IS the host LPC master, but the running board is booted past POST; catch a host reset**) · [~] userspace (`/dev/aspeed-lpc-snoop0` present; a captured byte needs host POST I/O)
- Zephyr: [ ] QEMU · [ ] silicon
- NB: full POST-code CAPTURE (not just driver bind) needs a host LPC master writing I/O port 0x80 — the BMC-only QEMU machine has none; silicon has the SP5100.

### B1d. LPC — vUART (host-visible virtual UART) (§5)  [split per gate-(d) audit]  ✅ QEMU BMC-side this session
- [x] QEMU: `&vuart` enabled → **the `8250_aspeed_vuart` driver binds the G3 vUART @0x1e787000 as `ttyS5` ("ASPEED VUART")** (`scripts/lpc-test.py` PASS; boot dmesg confirms)
- U-Boot: [N]
- Linux: [x] QEMU (vUART bound = ttyS5; obmc-console binds it as /dev/ttyVUART0 on the full OpenBMC image) · [ ] silicon (needs the vuart node in the realhw DTS + a host consumer) · [~] userspace (ttyS5 is a real tty; a host-visible session needs the host LPC side)
- Zephyr: [ ] QEMU · [ ] silicon

### B1e. LPC — TPM header pass-through → TPM1 (§5, §15)  [split per gate-(d) audit]
- [N] QEMU/U-Boot/Linux/Zephyr: TPM1 shares the *host's* LPC bus; the BMC is a peer LPC peripheral, it does not drive the TPM. No BMC driver — the TPM is a host device on the shared bus (DEVICE-MATRIX row 7). Documented, not a BMC deliverable.

### B1f. LPC — LPCPD# power-down / clock-run handshake (§5, ball D15 net N39511964)  [added: gate-(d) round-2 enumeration audit 2026-07-18]
- [ ] QEMU: model the G3 LPC `LPCPD#` (LPC power-down / clock-run) so a host sleep/resume drives the handshake faithfully (the one §5 LPC signal not covered by B1a–e's KCS/mailbox/snoop/vUART/TPM).
- U-Boot: [N] (host-driven low-power handshake, not a U-Boot function)
- Linux: [~] QEMU · [~] silicon — the mainline aspeed-lpc handles LPCPD internally; verify/state explicitly rather than omit · [N] userspace
- Zephyr: [ ] QEMU · [ ] silicon

### B1g. PIKE2 storage-mezzanine connector — LPC-bus peer (§15, shares LPCPD# net)  [added: gate-(d) round-2]
- [N] QEMU/U-Boot/Linux/Zephyr: PIKE2[A11] shares only the `LPCPD#` net with the BMC; the BMC does not drive PIKE2 (analogous to the TPM1/B1e disposition). Documented for completeness, not a BMC deliverable.

### B2. PCI 33 MHz bus (VGA-as-PCI / video-capture attach) → SP5100 (§6)
- [~] QEMU: video engine appears; full PCI-target config-space model partial
- [ ] QEMU: PCI `INTA#` / GPIOB0 interrupt output (ball B11, net N36033607 → PCI6[B8], SU1[AC4]) — a real PCI target asserts INTA#; model it or record [N] if the capture path never raises it  [added: gate-(d) round-2]
- U-Boot: [N] (BMC is a PCI target for host video capture, not a U-Boot function)
- Linux: [~] QEMU (video path uses it) · [~] silicon · [ ] userspace (covered via video below)
- Zephyr: [ ] QEMU · [ ] silicon

### B3. Video / iKVM CAPTURE → VGA1 (§6 capture) — the JPEG capture path
- [x] QEMU: `aspeed.video-ast2050` faithful G3 model (headerless entropy + 8 ROM quant tables)
- U-Boot: [N] (video capture is an OS/runtime function)
- Linux: [x] QEMU (v4l2 `/dev/video0`, JFIF pixel-verified) · [x] silicon (patch 0006, `bytesused=28418`, real host frame — both-sides PASS) · [x] userspace (V4L2 DQBUF → decodable JPEG)
- Zephyr: [ ] QEMU · [ ] silicon

### B3b. VGA DAC analog output + mode-set + PCI-target config → VGA1 (§8 output, §6 PCI)
- [~] QEMU: DAC/mode-set present but the analog-output + PCI-target config-space paths are partial (DEVICE-MATRIX rows 8/12 self-question mode-set/fb)
- U-Boot: [N] (analog VGA output is an OS/runtime function)
- Linux: [~] QEMU (mode-set/fb self-questioned) · [~] silicon (host VGA visible via capture, but the BMC's *own* DAC output as a framebuffer is not independently validated) · [ ] userspace (`/dev/fb0` / DRM)
- Zephyr: [ ] QEMU · [ ] silicon

### B4. VGA DDC / EDID I²C → VGA1 (§8)
- [ ] QEMU: DDC/EDID I²C slave on the video connector (D12)
- U-Boot: [N] (monitor EDID is an OS/runtime concern)
- Linux: [ ] QEMU · [ ] silicon · [ ] userspace (`/sys/class/drm/.../edid`)
- Zephyr: [ ] QEMU · [ ] silicon

### B5. USB 2.0 device / vhub → SP5100 (§9)
- [x] QEMU: USB2.0 device/vhub model (F6 probe-safe)
- U-Boot: [N] (USB gadget is an OS/runtime function)
- Linux: [x] QEMU (vhub gadget enumerates) · [B] silicon (**patch 0007 compile-clean + QEMU-verified; silicon RIG-BLOCKED — P2A siphon degrades after ~15 boot cycles; did not power-cycle to avoid host CMOS-halt strand. Confidence: my model/patch correct, blocker is rig access, not the driver**) · [ ] userspace (host-side HID enumeration)
- Zephyr: [ ] QEMU · [ ] silicon

---

## C. Ethernet (§7)

### C1. MAC (ftgmac100) + RTL8201N mgmt PHY — MII channel 1 → U5 (§7)
- [x] QEMU: ftgmac100 + RTL8201CP/8201N PHY model (FAST_MODE fix modeled)
- U-Boot: [x] QEMU · [x] silicon (Raptor TFTP netboot over this MAC)
- Linux: [x] QEMU (eth0 up) · [x] silicon (OpenBMC NFS-root + curl Redfish; FAST_MODE rx-fix) · [x] userspace (sockets, curl)
- Zephyr: [ ] QEMU · [ ] silicon

### C2. NC-SI sideband — RMII2 channel 2 → 2× 82574L (§7)
- [x] QEMU: RMII2/NC-SI model + faithful responder (MAC2 channel discovery)
- U-Boot: [N] (NC-SI sideband is an OS-level function)
- Linux: [x] QEMU (ncsi channel discovery) · [ ] silicon (**not blocked externally — this is HARD, undone authoring work: "No channel found" is the deeper G3 RMII2 pinmux group divergence (strap 110 RMII2 routing differs from G4's SCU70[7]). Needs the AST2050 RMII2/GPIOE routing RE + a G3 pinctrl group written. My kernel patch 0008 fixed the strap-phantom class; this distinct, deeper pinmux gap is precisely diagnosed and is my code to write, not a hardware fault**) · [ ] userspace
- Zephyr: [ ] QEMU · [ ] silicon

---

## D. I²C controllers + on-bus devices (§10)

### D1. I²C controllers ×8 (SDA1/SCL1…SDA7/SCL7 + muxed 8th) — MASTER mode (§10, §10.4)
- [x] QEMU: aspeed I²C engine model (G3 AC-timing fix modeled)
- U-Boot: [x] QEMU · [x] silicon (Raptor I2C)
- Linux: [x] QEMU · [x] silicon (i2cdetect completes; g3-i2c patch 0005) · [x] userspace (`/dev/i2c-*`, i2cget/i2cset)
- Zephyr: [x] QEMU (`i2c_aspeed_g3` + w83795_smoke PASS) · [x] silicon (drove engine 1 = schematic I2C2, SCU04 reset-release, read the real W83795 @0x2f; #148, LOG 2026-07-19)

### D1b. I²C — SLAVE/target mode + multi-master arbitration (§10.3, I2C-SMBUS-TOPOLOGY §3.2)  [added by gate-(d) audit]
(the shared sensor bus I2C2/3/6 is genuinely multi-master with the SP5100 SMBus1/2, arbitrated by U23 + the D27/QQ9/QQ10 hardware ownership mutex; and the BMC can be *addressed as a target* — IPMB/SSIF-style inbound)
- [~] QEMU: the aspeed_i2c model supports master + basic slave; the KGPE-D16 multi-master arbitration (U23 source-select + the ownership mutex) is modeled at the fabric level (D6, `kgpe_d16_i2c_fabric.c` gates on ownership) but lost-arbitration/target-addressing of the BMC is not exercised
- U-Boot: [N] (slave/multi-master is an OS-runtime concern)
- Linux: [ ] QEMU (i2c slave backend `i2c-slave-*` bound to an engine + a multi-master contention test) · [ ] silicon (drive a bus contention with the SP5100 as co-master) · [ ] userspace
- Zephyr: [ ] QEMU · [ ] silicon
- NB: if the KGPE-D16 never addresses the BMC as an I²C target (no IPMB/SSIF wired to the BMC), the target-mode boxes become `[N]`-with-reason once confirmed from the netlist — currently `[ ]` pending that confirmation.

### D2. W83795G hardware monitor — QU4, I2C2 0x2F (§10.2)
- [x] QEMU: `w83795` model seeded from silicon captures
- U-Boot: [N] (hwmon is an OS function)
- Linux: [x] QEMU (w83795 hwmon binds, fan RPM) · [x] silicon (fan1=2657 rpm, real V/temp) · [x] userspace (`/sys/class/hwmon`, sensors, IPMI SDR)
- Zephyr: [x] QEMU (`w83795` client: fan1=2641/temp0=50.5 PASS) · [x] silicon (read the REAL W83795: fan1=2631/2611 rpm + temp0=58.5/59.0 C, live drift; #148, LOG 2026-07-19)

### D3. W83601G DIMM-LED expander U27 — I2C5 0x18 (§10.2)  ✅ both-sides this session
- [x] QEMU: `hw/gpio/w83601g.c` datasheet-faithful (Nuvoton V1.31; CI `boot-w83601g`)
- U-Boot: [N] (DIMM-error-LED drive is an OS/runtime function)
- Linux: [x] QEMU (`scripts/w83601g-test.py` 19/19) · [x] silicon (LED-drive via i2c-4, readback) · [x] userspace (raw SMBus i2cset/i2cget)
- Zephyr: [ ] QEMU · [ ] silicon

### D4. W83601G DIMM-LED expander U28 — I2C5 0x19 (§10.2)  ✅ both-sides this session
- [x] QEMU: same model, seeded input 0xb5
- U-Boot: [N] (as D3)
- Linux: [x] QEMU · [x] silicon (LED-drive on 0x19, readback+restore) · [x] userspace (raw SMBus)
- Zephyr: [ ] QEMU · [ ] silicon

### D5. HT24LC08 FRU EEPROM — U25, I2C5 0x50–0x53 (§10.2)  ✅ both-sides this session
- [x] QEMU: 4× smbus-eeprom at 0x54–0x57 (blank 0xff, matching silicon)
- U-Boot: [N] (FRU is an OS/IPMI function)
- Linux: [x] QEMU (at24 binds) · [x] silicon (at24 read, blank as shipped) · [x] userspace (`/sys/.../eeprom`, IPMI FRU)
- Zephyr: [ ] QEMU · [ ] silicon

### D6. QU9/QU5/U23 I²C mux fabric (§10.1, §10.3)  ✅ both-sides
- [x] QEMU: `hw/i2c/kgpe_d16_i2c_fabric.c` (GPIO-selected mux, sys-pwrgd gate)
- U-Boot: [N] (mux fabric is used by the OS to reach DIMM SPD)
- Linux: [x] QEMU (i2c-mux-gpio child adapters) · [x] silicon (SPD read through Y2) · [x] userspace (mux-selected i2c bus)
- Zephyr: [ ] QEMU · [ ] silicon

### D7. DIMM A–D / E–H SPD EEPROMs — I2C10/I2C11 0x50–0x57 (§10.2)  ✅ both-sides
- [x] QEMU: real 256-byte DIMM_A2 SPD (RMR5030EF68F9W1600) behind the fabric
- U-Boot: [N] (SPD read for the OS)
- Linux: [x] QEMU (at24 SPD header 92 11 0b) · [x] silicon (real SPD read via fabric) · [x] userspace (`/sys/.../eeprom`, decode-dimms)
- Zephyr: [ ] QEMU · [ ] silicon

### D8. DIMM A–D / E–H TSOD thermal — I2C10/I2C11 0x18–0x1F (§10.2)
- [x] QEMU: `hw/sensor/jc42.c` JC-42.4 TSOD model is COMPLETE + correct (MCP98244 IDs, word-swapped regs); deliberately NOT instantiated on this machine — the rig's DIMM_A2 SPD byte32=0 = no TSOD, so placing one would be un-faithful. The model is wired-in on demand for a TS-equipped DIMM config.
- U-Boot: [N]
- Linux: [x] QEMU (jc42 model exists) · [N] silicon (**this rig's DIMM_A2 SPD byte32=0 = NO thermal sensor; 0x19 NAKs — faithfully absent, not a gap**) · [N] userspace (no TSOD present)
- Zephyr: [ ] QEMU · [N] silicon (no TSOD on this rig's DIMM)

### D9. SB-TSI CPU thermal — I2C4 0x4C/0x4D via QU4 FETs (§10.2)  ✅ BOTH-SIDES DONE
- [x] QEMU: `hw/sensor/sbtsi.c` datasheet/driver-faithful (P0@0x4c, P1@0x4d on i2c3); `scripts/sbtsi-test.py` 8/8 PASS (evidence d09-sbtsi/00)
- U-Boot: [N] (CPU thermal is an OS function)
- Linux: [x] QEMU (in-kernel `sbtsi_temp` hwmon driver binds amd,sbtsi on i2c3 and reads the model: `3-004c/hwmon/.../temp1_input`=45500, `3-004d`=43000; CONFIG_SENSORS_SBTSI; CI `boot-sbtsi`) · [x] **silicon (DID IT — netbooted the i2c3-enabled real-HW kernel with the host powered; the sbtsi_temp driver bound the REAL AMD CPU SB-TSI @0x4c, temp1_input=14375, raw regs 0x0e/0x60 confirm 14.375°C; P1@0x4d NAKs = socket-2 CPU absent. Host stayed on through the BMC reset. Evidence d09-sbtsi/01-silicon-pass.txt)** · [x] userspace (`/sys/class/hwmon` temp1_input)
- Zephyr: [ ] QEMU · [ ] silicon

### D10. PSU PMBus — PSUSMB1, I2C1 (§10.2)
- [ ] QEMU: PMBus device model on I2C1 (task #135)
- U-Boot: [N] (PSU monitoring is an OS function)
- Linux: [ ] QEMU (`pmbus`) · [B] silicon (**needs a PMBus-capable PSU present + I2C1 engine enabled; PSU-hardware-dependent**) · [ ] userspace (hwmon)
- Zephyr: [ ] QEMU · [ ] silicon

### D11. SMBus ALERT — SALT1/2, I2C7 B12 (§10.2, §10.4)
- [ ] QEMU: SMBALERT# line model on I2C7 (task #135)
- U-Boot: [N]
- Linux: [ ] QEMU (smbus-alert) · [B] silicon (**needs an alerting device + I2C7 enabled; depends on D9/D10 devices being present**) · [ ] userspace
- Zephyr: [ ] QEMU · [ ] silicon

### D12. Aux front panel — AUX_PANEL1, I2C8 via QU5 Y0 (§10.2)
- [ ] QEMU: aux-panel I²C target on the Y0 mux channel
- U-Boot: [N]
- Linux: [ ] QEMU · [ ] silicon · [ ] userspace
- Zephyr: [ ] QEMU · [ ] silicon

### D13. Unidentified 0x69 responder on the sensor mux (found on silicon 2026-07-18)
- [ ] Identify (not in schematic §10 table; reg0=0x08, NAKs others) then model
- Note: open completeness item — logged in LOG.md; low-priority weak responder

---

## E. GPIO / platform control (§11) + LEDs/straps (§13)

### E1. GPIO controller + power/reset sequencing (§11)
- [x] QEMU: `aspeed_gpio.c` + kgpe_d16_pwrseq (GPIOA4 lockout, B1/B6/F0 pulse, H2 latch)
- U-Boot: [~] QEMU · [~] silicon (Raptor drives some GPIO)
- Linux: [x] QEMU (F2 power on/off/reset PASS via kgpe-power.sh) · [x] silicon (plug 3W→103W, host PXE, eth0 survives) · [x] userspace (sysfs gpio, kgpe-power.sh, Redfish)
- Zephyr: [ ] QEMU · [ ] silicon

### E2. Platform-monitor GPIO INPUTS — THERMTRIP/PROCHOT/DDR_THERM/NMI + POST-complete/sync-flood/NMI-button (§11 + per-pin netlist)
(full input set from `pinmaps/QU1_pins.md`: `TTL_P1/P2_THERMTRIP#` V4/V3, `TTL_P1/P2_PROCHOT#` V2/V1, `AST_P0/P1_DDR_THERM#` T3/T2, `AST_NMI#` T1; **plus gate-(d)-found inputs: `AST_BIOS_POST_COMPLT#` A10/GPIOB5 (host POST-complete monitor), `AST_SYNCFLOODIN#` B8/GPIOC4 (HyperTransport fatal-error monitor), `FP_NMIBNT#` U1/GPIOH6 (front-panel NMI-button sense)**)
- [~] QEMU: aspeed GPIO inputs modeled; the full §11 signal-map wiring (incl. the three added inputs) is incomplete — needs DTS `gpio-line-names` + input nodes
- U-Boot: [N] (platform-event monitoring is an OS function)
- Linux: [~] QEMU · [ ] silicon (**needs DTS `gpio-line-names` exposing these balls as GPIO inputs + a reboot; on 2026-07-18 a `/sys/kernel/debug/gpio` dump on silicon showed only `bmc-ctl-lockout-n` named — the §11 monitor pins are not yet line-named/exported, several are in TACH alt-mode**) · [ ] userspace (gpio sysfs / gpio-keys)
- Zephyr: [ ] QEMU · [ ] silicon

### E3. LEDs — BMCRDY/CPUERR/MLED/ID (§13)  ✅ silicon+userspace this session
- [~] QEMU: LED GPIOs present; DTS `gpio-leds` nodes (a QEMU toggle-observe test would confirm ✅)
- U-Boot: [N] (front-panel LEDs are an OS/runtime function)
- Linux: [~] QEMU · [x] **silicon (`echo 1 > /sys/class/leds/identify/brightness` flips the real GPIO led-id-n out hi→lo, `echo 0` back; the leds-gpio driver drives the real AST2050 GPIO — evidence e-gpio-leds/00)** · [x] userspace (`/sys/class/leds/*/brightness`)
- Zephyr: [ ] QEMU · [ ] silicon

### E4. Straps — IPMI_SEL/IKVMEN#/SOLEN# + SCU70 measured (§13)
- [x] QEMU: measured HW_STRAP1 = 0x00819582; pinctrl G3 strap-phantom patch 0008
- U-Boot: [x] QEMU · [x] silicon (SCU70 read == 0x00819582)
- Linux: [x] QEMU · [x] silicon (pinctrl binds, mux selects work) · [N] userspace (straps not a userspace ABI)
- Zephyr: [ ] QEMU · [ ] silicon

### E5. Platform-control OUTPUT lines — CLRTC#/BIOSREVRY#/CPU1-2DISABLE#/PCI_RST#/ATXPSON#/SYSRESET# + RESETDIS#/PWRBNTDIS#/BRST# (§11 + per-pin netlist)
(the discrete BMC-driven control signals beyond the E1 power-latch: `AST_CLRTC#`
B9, `AST_BIOSREVRY#` C9, `AST_CPU1DISABLE#` D8, `AST_CPU2DISABLE#` C8,
`SB_PCI_RST#` B10, `AST_ATXPSON#` A9, `AST_SYSRESET#` D10 — DEVICE-MATRIX row 29;
**plus gate-(d)-found outputs: `AST_RESETDIS#` C10/GPIOB3 (reset-disable),
`AST_PWRBNTDIS#` C11/GPIOA5 (power-button-disable; alt-fn PHYPD# overlaps the C1
MAC/PHY power-down — note the dual role), and `AST_BRST#` P21 (the BMC's OWN
dedicated PCI/VGA reset OUTPUT to the VGA_SW1 jumper — not a GPIO, a hard reset
pin the B2/B3b PCI-target model must generate)**)
- [~] QEMU: driven as aspeed GPIOs by the model (the power-latch ones are in the
  kgpe_d16_pwrseq path; CLRTC#/BIOSREVRY#/CPUxDISABLE# are plain GPIO outputs,
  togglable but not yet each behaviour-verified)
- U-Boot: [N] (discrete platform control is an OS/runtime function)
- Linux: [~] QEMU (sysfs GPIO toggles) · [ ] silicon (**not done: each line needs an
  observed effect — CLRTC# clears CMOS, CPUxDISABLE# gates a socket, PCI_RST#
  resets the SB PCI. Achievable via sysfs GPIO on silicon + a host to observe;
  undone, not blocked**) · [ ] userspace (`/sys/class/gpio` per-line)
- Zephyr: [ ] QEMU · [ ] silicon

### E6. Unidentified + test/reset pins (§13 + per-pin netlist)  [added: gate-(d) round-2 enumeration audit 2026-07-18]
- [ ] **GPIOE6/GPIOE7 ↔ SP5100** (balls U4/U3, nets N85607608/N85622904 → NQ5/NQ6/SR137/SR157/SU1[AE18,B8]): two unidentified BMC↔southbridge GPIO handshake signals. RE the function from the netlist (sibling of the D13 unidentified-responder open item), then model or dispose. Currently untracked.
- [N] **ENTEST** (ball R21, net AST_ENTEST): SoC manufacturing test-mode enable — not an in-guest device (like the JTAG/G1 harness). Disposition [N]; recorded so the pin is accounted for.
- [~] **AST_SRST#** (ball R20): the BMC's OWN global reset OUTPUT, tied to JTAG SRST# and wired to reset the RTL8201N PHY (U5[38]). Implicit in A1 (SoC reset) + G1 (JTAG), but a faithful QEMU model should PROPAGATE SRST# → PHY reset (affects the C1 MAC/PHY). QEMU: [ ] propagate to PHY · silicon: [x] JTAG SRST# works (G1). Add the board-effect note to the A1/C1 models.

## F. Serial / SOL (§12)

### F1. UART console — UART2 / AST_UART1 (§12, §15)
- [x] QEMU: SERIAL_MM UART5 @0x1e784000 (serial_hd(0))
- U-Boot: [x] QEMU · [x] silicon (Raptor `boot#` @115200, our serial-bmc-console)
- Linux: [x] QEMU (ttyS4 console) · [x] silicon (login shell) · [x] userspace (getty/dropbear)
- Zephyr: [~] QEMU (static-mapped polling SoC console — banner + Hello World; ns16550 blocked by upstream arm_mmu z_phys_map) · [ ] silicon

### F2. UART1 → SOL via QU8 mux → Super-I/O (§12)
- [~] QEMU: VUART byte-flow model; QU8 2:1 mux (BMC_PRESENT# select) not modeled (D10)
- U-Boot: [N] (SOL is an OS/IPMI function)
- Linux: [~] QEMU (obmc-console byte-flow PASS) · [ ] silicon (**mostly HARD/undone authoring work, not an external block: (a) the QU8 2:1 mux select (BMC_PRESENT#) is unmodelled — my code to write; (b) `sol activate` fails at netipmid `registerSOLService` — a phosphor-net-ipmid binding gap, my code to fix; the only genuine rig aspect is that the host serial console is not VUART-wired on this bench. Byte-flow (obmc-console-client) already works**) · [ ] userspace (ipmitool sol)
- Zephyr: [ ] QEMU · [ ] silicon

---

## G. Debug / test harness (§13)

### G1. JTAG (ARM926 debug) → AST_JTAG1 (§13, §15)
- [N] QEMU (JTAG is a silicon debug transport, not an emulated in-guest device)
- [x] silicon: JTAG run-control WORKS (IDCODE 0x07926f0f, halt, AHB mdw SCU7C=0x202) — this is the silicon *test harness*, not a driver row.

---

## Coverage assertion (verified against the complete schematic read)

Every §2–§15 function block and every §14 neighbour chip maps to a row above:
§2→A1; §3→A2; §4→A3; §5→B1; §6→B2/B3/B3b; §7→C1/C2; §8→B3b/B4; §9→B5;
§10→D1–D13; §11→E1/E2/E5; §12→F1/F2; §13→A1/A4/A5/E3/E4/G1; §14 chips→the bus rows
that reach them (W83795→D2, W83601G→D3/D4, HT24LC08→D5, RTL8201N→C1, 82574L→C2,
SB-TSI→D9, QU9/QU5→D6, QU8→F2, muxes/glue→passive). **CU2 (ICS9112AM-16LFT
clock generator)** supplies the 50 MHz RMII1/2 reference clocks to the MAC — an
active support chip absent from §14; it is load-bearing for a faithful RMII/NC-SI
model (folded into C1/C2, tracked here so it is not a silent omission). The three
**host chips**
`SU1` (SP5100 southbridge), `OU1` (W83667HG Super-I/O), `NU1` (SR5690 northbridge)
are not BMC-internal devices — the BMC reaches them **through** the LPC (B1), PCI
(B2), USB (B5) and I²C (D1) controller rows; their own register maps are host-
side (documented in the SP5100/Super-I/O docs), not a BMC driver. Likewise `ZU1`
(LSI FW322 1394a FireWire controller) and the `PCI6` expansion slots are PEERS on
the shared 33 MHz PCI bus — the BMC is a video-capture **target**, not their host
or driver → `[N]`, exactly parallel to the TPM1/PIKE2 LPC-peer disposition (added
for prose parity per the gate-(d) round-3 convergence audit). §15 connectors→
the functional rows (VGA1→B3/B3b/B4, AST_UART1→F1, JTAG1→G1, BMC_FW1→A3,
PANEL1/AUX_PANEL1→E1/E3/E5/D12, PSUSMB1→D10, TPM1→B1, jumpers→E4). Passive parts
(LDOs UP7706U8, series-R nets QRN*, sync buffer QU6, RS-232 AZ75232, glue 74LVCxx)
carry no driver by nature and are modeled only where behaviour-relevant (the
QU9/QU5/U23 fabric = D6).

**Explicit disposition of the remaining per-pin/netlist items (gate-(d) audit 2026-07-18):**
- `VGA_HDR1` (secondary internal VGA pin-header): carries the same DAC/DDC/sync
  nets as VGA1 in parallel → covered by B3b/B4; noted here as an unlisted §15
  connector so it is not a silent skip.
- `ROMA0–ROMA23` (24 balls W5–AB8): legacy parallel-ROM address pins, series-
  terminated only, act as SPARE GPIO in SPI-boot mode (§4). Disposition: `[N]`
  no dedicated driver — unused spare GPIO on this board; togglable via the aspeed
  GPIO model + sysfs if ever needed (folds into E1's GPIO controller).
- The A9 ADC, the three E2 monitor inputs (BIOS_POST_COMPLT#/SYNCFLOODIN#/
  FP_NMIBNT#), the three E5 outputs (RESETDIS#/PWRBNTDIS#/BRST#), the B1a–e LPC
  split, the D1b I²C slave/multi-master, and CU2 were all ADDED by the gate-(d)
  task-discovery audit (2026-07-18) — the prior coverage assertion had overstated
  completeness; these are now explicit rows/items, honestly `[ ]`/`[~]`/`[N]`.

**Gate-(d) round-2 (independent sub-agent per-pin sweep, 2026-07-18):** a second
completeness audit against the 355-ball pinmap found 6 more individual signals the
round-1 sweep had not reached — now folded in above: **B1f** `LPCPD#` (D15, the one
uncovered §5 LPC signal), **B1g** `PIKE2` LPC-bus peer `[N]`, **B2** PCI `INTA#`/
GPIOB0 (B11) interrupt output, **E6** the unidentified `GPIOE6/E7↔SP5100` handshake
(U4/U3, sibling of the D13 open item), **E6** `ENTEST` test-mode pin `[N]`, and
**E6** `AST_SRST#` (R20) BMC reset-output → PHY reset (a board effect a faithful
model must propagate). The audit judged the enumeration otherwise ~95% complete and
rigorously self-audited; these are missing rows, not missing stack-columns.

**Nothing in the schematic is skipped.** Items marked `[N]` state why they are
not-applicable for that stack; `[B]` items state the precise blocker and my
confidence that it is rig/host/upstream-scoped, not a hardware fault or a
hand-wave. The open work is the un-`[x]` boxes — principally the Zephyr per-
device column (gated on the upstream arm_mmu sustained-tick fix, task #141), the
host/PSU-dependent I²C far-ends (D9/D10/D11), DDC/EDID (B4), the LPC mailbox/
vUART sub-blocks (B1), SOL end-to-end (F2), MTD write (A3), and the §11 signal-
map/LED silicon observation (E2/E3).

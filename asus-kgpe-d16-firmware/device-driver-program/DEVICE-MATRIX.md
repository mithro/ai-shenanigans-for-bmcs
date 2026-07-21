# AST2050 / KGPE-D16 — explicit per-device task matrix

> **This is the compact SUMMARY grid. [`FULL-TASK-LIST.md`](FULL-TASK-LIST.md) holds
> the per-stack/per-validation DETAIL** (explicit `[x]/[~]/[ ]/[N]-with-reason/
> `[B]-with-blocker` boxes + the §-by-§ coverage assertion). **The two are kept in
> sync and must AGREE. On any divergence, the more-recently-dated entry that carries
> cited evidence wins, and the divergence must be RECONCILED (not left standing) —
> do NOT apply a blanket "one doc always wins" rule, which historically pointed at
> whichever doc was staler.** (Cross-syncs: 2026-07-18 second completeness audit
> [NC-SI/USB/WDT/RTC/SOL/straps/PCI/VGA-DAC]; 2026-07-19 [ADC row 41, Zephyr-silicon
> rows 15/16/36/37/38, TSOD row 19, FRU address] — see LOG. The row groupings here
> differ slightly from FULL-TASK-LIST's A/B/C/D/E/F rows.)

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

## Coverage snapshot (this table IS the enumerated per-stack task list)

**Every device is one row below** (51 rows: the §§2–15 schematic devices + the SoC-INTERNAL
engines from the datasheet §9 memory map). **COMPLETENESS — TWO DIMENSIONS:** (1) EXTERNAL
schematic devices (2026-07-20 gate-a): an independent sub-agent enumerated every
device/peripheral/interface/connector in the authoritative schematic §§2–15 (+ §14/§15) and cross-checked
each against these rows — **no missing device found** (only unrowed narrative items are reset-output *nets*
`AST_SRST#`/R20, `AST_BRST#`/P21, tracked in FULL-TASK-LIST E6; the CU2/PIKE2 pinmap parts are
dispositioned at the end of this file). **RE-AUDITED 2026-07-21 (gate-a #2): still no structural device
missed**, with 3 open IDENTITIES (not missed enumeration) now explicitly flagged: (a) the 0x69 I²C
responder found on real silicon — NOT in the schematic — still unidentified (FULL-TASK-LIST D13 / #160);
(b) the GPIOE6/E7↔SP5100 handshake nets `N85607608`/`N85622904` — function un-RE'd (E6 / #161); (c)
`AUX_CHASSIS#` on AUX_PANEL1 pin 5 — untraced, almost certainly the W83795 CASEOPEN input (#183). (2) SoC-INTERNAL engines (2026-07-20 gate-d, #173): the
schematic-scoped audit STRUCTURALLY could not reach internal blocks with no external pins — two gate-d
passes found 8 real ones the matrix omitted (HACE/MIC/MDMA/2D/PUART/PCI-arbiter + AHBC/A2P, all "Yes" in
the memory map §9); **rows 43–50 now add them** (see their notes; the 2nd gate-d pass caught that the 1st
enumeration itself missed AHBC/A2P — #175/#176). Two G4 phantoms (XDMA/SDHCI) that WERE realized on the G3
machine are now gated off (#172). So both the external-device and internal-engine dimensions are now
enumerated. **Every column is a task**: QE = full QEMU emulation; UQ/US =
U-Boot driver validated in QEMU / on silicon; LQ/LS/LU = Linux driver validated in QEMU /
on silicon / from userspace; ZQ/ZS = Zephyr driver validated in QEMU / on silicon. So the
grid is 51 × 8 = 408 explicit per-device-per-stack tasks. Machine-counted status
(regenerate with `uv run tally.py`, 2026-07-21):

| Stack × env | ✅ done | 🔶 partial | 🔷 blocked | ⬜ todo | Ⓝ n/a (justified) |
|---|---|---|---|---|---|
| QEMU emulation | 27 | 15 | 0 | 6 | 3 |
| U-Boot @ QEMU | 10 | 4 | 0 | 3 | 34 |
| U-Boot @ silicon | 8 | 5 | 1 | 3 | 34 |
| Linux @ QEMU | 22 | 10 | 0 | 8 | 11 |
| Linux @ silicon | 20 | 3 | 2 | 15 | 11 |
| Linux userspace | 15 | 6 | 0 | 12 | 18 |
| Zephyr @ QEMU | 17 | 5 | 0 | 18 | 11 |
| Zephyr @ silicon | 11 | 4 | 0 | 25 | 11 |

**Reading it honestly:** U-Boot (Raptor) + Linux (OpenBMC) ARE substantially validated
BOTH sides (not "none" — 8/18 silicon-✅ respectively, CI-gated); the many U-Boot Ⓝ are
justified board-dispositions (no boot-time need). **Zephyr now RUNS ON SILICON** — 11 rows
ZS ✅ (machine-counted, reconciled 2026-07-20 gate-c): DDR2/SDMC (1, runs-from) + I2C master (15) + W83795
hwmon (16) + FRU EEPROM (20) + both W83601G expanders (21/22) + 24 MHz clock (34, consumed) + SCU (35) + VIC
(36) + system timer (37) + WDT (38) — all boot/read on the real AST2050 over JTAG. (Rows 1 + 34 rest on the
"the Zephyr stack demonstrably runs from the 64 MB DDR2 / at the 24 MHz-derived rate on silicon" basis — the
same standard the U-Boot/Linux ✅ use on those rows — not a dedicated DDR/clock Zephyr driver.)
JTAG. Getting there fixed silicon-only bugs QEMU had hidden (cache/TLB invalidate, VIC
ack-at-entry, enable-glitch tick, entry staleness — commits 918bc7e/b84ef58/78f5569; and the
**SCU74[12] I2C5 pin-mux** #156 that the FRU/W83601G engine-4 devices need — see LOG.md).
**Remaining frontiers:** RTC (39) — **LS now ✅ on real silicon (2026-07-21): Linux set/get +
wakealarm PASS** once the driver was fixed to CLEAR SCU08[16] (bit16=0/32.768kHz source is what
runs under U-Boot's clock config; forcing bit16=1 was MY regression that froze the counter) and to
poll CONTROL[5] restart-busy in set_time (evidence 30). **RATE CLAIM CORRECTED (evidence 31): with
bit16=0 the RTC keeps EXACT real time (silicon 20 s window = 1.00x) — the "732x can't do real-time"
line (#158/#186) was a bit16=1 test-tap artifact; the board IS a real-time clock.** ZS stays 🔶 only
because the Zephyr driver still forces bit16=1 (732x) — a bit16=0 retest may make ZS real-time.
host power-control (27) works in QEMU + the force-OFF drives real silicon but the
GPIOH2 feedback read needs work (#162); SB-TSI (23) needs the host CPU powered (#150); the
**4 QEMU ⬜** (DDC/EDID, LPC-mailbox, SOL-mux, SMBus-ALERT); and the broad Zephyr breadth gap
(ZS 27 ⬜). Open faithfulness notes: GPIO-input-readback silicon-vs-QEMU (IJKL floating; and
the #162 GPIOH2 read); QEMU I2C should gate engine 5/6/7 on SCU74 (#157). This snapshot is
regenerated by `uv run tally.py`; per-row detail + evidence in [`FULL-TASK-LIST.md`](FULL-TASK-LIST.md).

## Memory & storage

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | QU2 DDR2 SDRAM (Hynix HY5PS121621, §3) | SDMC | ✅ | ✅ | ✅ | ✅ | ✅ | Ⓝ | ✅ | ✅ |
| 2 | BMC_FW1 SPI flash (socketed, §4) | SMC | ✅ | ✅ | 🔷 | 🔶 | 🔷 | ⬜ | ⬜ | ⬜ |

- **1** UB both = Raptor `DRAM Init-DDR`→64 MiB (QEMU `evidence/d15-uboot/`, silicon boot#). LU=Ⓝ (RAM is memblock, no userspace driver). **Zephyr ZQ/ZS ⬜→✅ (2026-07-20):** the ✅ standard for this
  row is "the stack runs from the 64 MB DDR2" (same basis as Linux LQ/LS ✅ "RAM usable") — the loader
  trains the SDMC (U-Boot in QEMU / the JTAG `ddr2-init.tcl` on silicon), and the payload uses it. The
  Zephyr port demonstrably runs from `0x40000000` DDR2 on BOTH sides: QEMU (`Hello World`, evidence
  `d14-zephyr/02`/`03`/`05`) and REAL silicon (EVERY Zephyr silicon smoke — `14`-`20` — is JTAG-loaded
  to `0x40000000` after DDR2 train and runs). Leaving it ⬜ was the row-30 class of understatement. D01.
- **2** UB-Q = Raptor `libspi_flash` (`Flash: SPI Flash ID` in QEMU). US/LS = 🔷 rig-blocked (socket empty on THIS bench; populated by design). LU (mtd-utils) ⬜ — **no MTD write path exists yet** (audit). D02.
  **QQ11/ROMA0 disposition (#152, 2026-07-19 from my schematic read):** the pinmap
  (`QU1_pins.md:88`) shows AA9 `ROMA0`→`QQ11[3]` is the ONLY connected legacy-ROM address
  pin (all other `ROMA*` are `—`). Schematic §4 states the whole `AST_ROMA0–23` bus is
  "only series-terminated … spare GPIO" (the BMC boots SPI, not parallel ROM), so this net
  is **board-N/A for BMC function** and needs no driver/model. `QQ11`'s exact part identity
  is NOT in the extracted netlist docs (only the one pin-map reference; the `.FZ`
  part-description wasn't captured) — a netlist re-extract (schematic-wiring/tools/) would
  name it, but the disposition (unused spare-GPIO series/glue on ROMA0) stands regardless.

## Host-interface buses

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | LPC KCS / IPMI (§5 → SP5100) | LPC | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| 4 | LPC mailbox (§5) | LPC | ⬜ | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 5 | LPC port-80h POST snoop (§5) | LPC | 🔶 | Ⓝ | Ⓝ | 🔶 | ⬜ | 🔶 | ⬜ | ⬜ |
| 6 | LPC vUART (§5) | LPC | ✅ | Ⓝ | Ⓝ | 🔶 | ⬜ | 🔶 | ⬜ | ⬜ |
| 7 | TPM1 LPC pass-through (§5/§15) | LPC | ⬜ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 8 | PCI-33 / iKVM video-capture (§6) | video+P2A | 🔶 | Ⓝ | Ⓝ | 🔶 | 🔶 | 🔶 | ⬜ | ⬜ |
| 9 | USB device / vhub (§9 → SP5100) | vhub | 🔶 | Ⓝ | Ⓝ | 🔶 | 🔷 | 🔶 | ⬜ | ⬜ |

- **3** KCS/IPMI: `sdr`/host-KCS both sides. Real-silicon host `mc info` over KCS (ASUSTek/Product 0xD16)
  in `evidence/real-hw-hwpass/host-kcs-mc-info-fru.txt`; QEMU KCS state-machine run under `evidence/host-kcs*/`.
  UB Ⓝ (no boot need). D03.
- **5/6** POST-snoop + vUART: **QEMU BMC-side DONE (2026-07-18)** — enabled `&lpc_snoop {snoop-ports=<0x80>}` + `&vuart` in the DTS; `scripts/lpc-test.py` (CI `boot-lpc`) confirms the `aspeed-lpc-snoop` driver binds (`1e789090.lpc-snoop`, `/dev/aspeed-lpc-snoop0`) and the `8250_aspeed_vuart` driver binds the G3 vUART as ttyS5, against the faithful G3 LPC model. Full POST-code CAPTURE / host-visible vUART session needs a host LPC master (the SP5100 on silicon; the BMC-only QEMU has none) — LS ⬜ (catch a host mid-POST), LU 🔶. **LQ ✅→🔶 (2026-07-21 over-claim audit):** the LQ ✅ rested on the drivers BINDING + the char-devices being created (`/dev/aspeed-lpc-snoop0`, ttyS5), NOT on a functional POST-byte/vUART-byte transfer — which the host-less QEMU machine structurally can't do. So LQ is honestly 🔶 (BMC-side driver bind done; data transaction needs a host peer), matching the self-disclosed `scripts/lpc-test.py` scope. **QE ✅→🔶 (2026-07-21 over-claim audit #2):** the port-80h SNOOP FUNCTION itself is not modeled — `hw/misc/aspeed_lpc.c` backs HICR5/HICR6 (0x80/0x84) as plain register storage but has NO SNPWADR/SNPWDR (0x90/0x94) or port-80h capture datapath, and the host-less machine emits no port-80h cycles. So QE is 🔶 (the KCS+vUART register model is real — row 6 vUART is a genuine SerialMM — but snoop-capture is not emulated), not "full emulation". **4** mailbox (iBT) still unmodeled — needs a separate `aspeed-lpc-mbox` node + a host peer. D03.
- **7** TPM1 shares the LPC bus + a QU9-switched I2C segment; the BMC is not the TPM driver (host owns TPM) → Ⓝ for driver stacks, but QEMU should model the LPC/I2C reachability (⬜). D03.
- **8** capture proven (`#3a`, `evidence/real-hw-video/`); the 45-ball PCI bus itself is only P2A/video-modeled, not a full PCI target. UB/ZP Ⓝ (no runtime need). **QE ✅→🔶 (2026-07-21 completeness-audit honesty fix):** under "QE = full emulation of ALL functionality" the QE cell must match the same aggregate reality the LS 🔶 already reflects — the video-CAPTURE + P2A back-door path IS modeled (B3 done), but the full PCI-33 bus + PCI-target (B2/B3b) is NOT, so QE is 🔶 not ✅. Completing it = model the A2P/AHB→PCI bridge (row 50 QE) + a PCI-target aperture. D04. **Granularity note (reconciles a gate-c doc divergence, 2026-07-21):** this ONE aggregate row folds together what FULL-TASK-LIST splits into three items — B2 (PCI-33 bus, `[~]` silicon), B3 (video CAPTURE→JPEG, `[x]` silicon, the 28418-byte real-host frame), and B3b (VGA-DAC/PCI-target, partial). So the row's LS **🔶** is the AGGREGATE (capture done on silicon, PCI-target incomplete) and is NOT in conflict with B3's `[x]` (which scopes only the capture sub-part); the two docs agree once the aggregate↔split mapping is applied.
- **9** LS = 🔷 (blocked): the real vhub EP-DMA datapath on silicon is rig-blocked (patch 0007 is QEMU-verified + compile-clean, but the P2A siphon degrades after ~15 boot cycles; Test B not run to avoid a host-CMOS-halt strand). Earlier `usbip-vudc` gadget-path enumeration is a different, non-vhub route. LU = 🔶 (BMC-side gadget configured; host-side HID enumeration not validated). **§9 "virtual keyboard/mouse/CD" — CORRECTION (#182, 2026-07-20): the gate-d flag "virtual-media un-validated" was a MIS-FLAG (it only inspected the f8-kvm HID transcript). The virtual-MEDIA mass-storage gadget IS validated: QEMU (`evidence/f6-usb/03-gadget-enumeration-demo.txt` — `Mass Storage Function` enumerates as idProduct 0x0104 over dummy_hcd) AND REAL SILICON (`evidence/real-hw-usb/02-SILICON-USB-ENUMERATION-PASS.txt` — a real Linux host over the JTAG+TFTP+USB/IP chain shows `usb-storage ... USB Mass Storage device detected` and reads `/dev/sda offset512 = [KGPE-D16-USBIP-VMEDIA-OK]`). So the virtual-media capability exists + works both sides. The ONLY genuine remaining delta is the §9 "CD" SCSI-type: today it presents a removable DISK (`mass_storage lun.0`), not a CD-ROM (`lun.0/cdrom=1`) — #182 re-scoped to just adding cdrom=1 + one USB-harness re-validation. The vhub-to-real-host EP-DMA datapath remains the row-9 LS 🔷 rig-block (USB/IP is the transport used to reach a real host).** **QE ✅→🔶 + LQ ✅→🔶 (2026-07-21 over-claim audit #2):** the QEMU vhub model `hw/misc/aspeed_udc_ast2050.c` is a register+IRQ model (its functional content is the HUB0C[18] deadlock-IRQ hazard that kernel patch 0007 exercises) with NO USB datapath — no `USBPort`/`usb_packet`/EP-DMA. The `f6-usb/03` mass-storage enumeration runs over Linux's `dummy_hcd`/`dummy_udc.0` LOOPBACK controller, NOT through the modeled aspeed vhub, and `f6-usb/02` only shows the driver PROBE. So QE is 🔶 (register+IRQ model, no emulated enumeration/EP-DMA) and LQ is 🔶 (aspeed-vhub driver binds but never carries a gadget through the modeled UDC in QEMU). The silicon virtual-media proof uses USB/IP to a real host — real + valuable, but orthogonal to vhub *emulation* fidelity. D05 / FULL-TASK-LIST B5.

## Network

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | Eth MAC1 MII → RTL8201N U5 (§7 ch1) | ftgmac100#0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| 11 | Eth MAC2 RMII2/NC-SI → 82574L LU1/LU2 (§7 ch2) | ftgmac100#1 | ✅ | ⬜ | ⬜ | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

- **10** eth0 both sides (NFS-root + Redfish on silicon). UB both = Raptor TFTP. **PHY-part naming RESOLVED
  (#181, 2026-07-20 — NOT a divergence):** the model (`hw/net/ftgmac100.c`) returns the legacy Realtek
  RTL8201-family MDIO PHY-ID `0x0000_8201`, which Linux `realtek.c` names "RTL8201CP"; the schematic §14
  labels U5 "RTL8201N-GR". Same PHY at the register level — proven FAITHFUL by SILICON: the real AST2050
  Linux attaches "RTL8201CP" identically to QEMU (`evidence/.../real-hw-g3clk/boot-noclkignore-console.log`
  :137, a TFTP-netbooted silicon boot). The model reproduces exactly what the silicon puts on MDIO; RTL8201N
  and the 0x8201-id "RTL8201CP" are the same legacy family / 10/100 RMII surface (a naming artifact, not a
  model bug). Reconciled the ftgmac100.c comment (submodule 65e7d9235e). #181 CLOSED. D06.
- **11** QE = MAC2 wired + `net/ncsi` discovers a channel vs the generic slirp responder (MFR-0x0). **LS = ⬜ (HARD undone authoring work, NOT externally blocked):** "No channel found" is the deeper G3 RMII2 pinmux group divergence (mainline g4 pinctrl mis-selects RMII2 on the G3; `evidence/d07-ncsi/03-`) — needs the AST2050 RMII2/GPIOE routing RE + a G3 pinctrl group *written* (my code), plus a faithful 82574L responder (2 pkgs, Intel OEM 0x157). D07 / FULL-TASK-LIST C2.

## Video

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | VGA DAC output → VGA1 (§8) | CRT/DAC | 🔶 | Ⓝ | Ⓝ | 🔶 | 🔶 | 🔶 | ⬜ | ⬜ |
| 13 | VGA sync buffer QU6 (§8) | — | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 14 | DDC / EDID I2C → VGA1 (§8) | I2C/DDC | ⬜ | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

- **12** QE 🔶: the video CAPTURE engine is modeled (used by `#3a`); the CRT/DAC *display* controller
  (CRTC / VGACRB7 register block, DAC mode-set + framebuffer scanout) is NOT modeled — this resolves the
  apparent row-12↔row-14 contradiction (row 14 correctly says "the CRT display controller is not modeled
  at all"; row 12's older "CRT/DAC modeled" wording meant the capture engine). Silicon display = Magewell
  capture (`#3a`). Full DAC mode-set/framebuffer needs the CRTC block modeled first (task #197). D12.
- **13** passive quad buffer (TC74VHCT125AF) — no driver target. Ⓝ.
  **QD3/QD4/QD5 (§8 VGA RGB-DAC output-buffer transistors)** are the same category — passive analog
  buffers directly on the "VGA DAC → VGA1" signal path that **row 12** covers by title, with no
  driver/model target. Disposed here (passive analog glue), like QU6; not a separate row (gate-a
  2026-07-20 borderline finding, #159f).
- **14** DDC/EDID: unmodeled (audit gap #7), but now FAITHFULLY SCOPED (2026-07-20, #178). **The
  DDC is CRT-controller hardware, NOT a general I²C engine — do NOT model it by bolting an EDID EEPROM
  onto an I2C engine bus (that would be unfaithful).** Datasheet evidence (`datasheets/aspeed/
  AST2050_V1.05.txt`): the pins are dedicated `DDCACLK`(B1)/`DDCADAT`(B2) (l.3045/3052) muxed with
  GPIOD7/GPIOD6, enabled as "primary DDC pins" by **SCU74[18]** (l.6086-6087, l.16851 "18 RW Enable
  primary DDC pins"; SCU2C[1] alt-routes OSCCLK onto DDCACLK); the controller is the CRT block's
  **VGACRB7 "DDC Control Register"** (l.29699, "DDC Control" l.29231); the SoC also has a KVM **Virtual
  EDID** function (l.16587-16617: "Use Virtual EDID as EDID"). VESA-DDC support is a headline feature
  (l.1313/28279). **Why unmodeled in QEMU:** the G3 machine models the VIDEO *capture* engine
  (0x1E700000, for `aspeed-video` KVM screen-grab — aspeed_ast2400.c:360-433) but **NOT the CRT
  *display* controller at all**, and DDC lives in the CRT controller — so there is no register block to
  attach DDC to yet. **Exact register decode (datasheet §34.5, l.29699, Init=00h) — VGACRB7 is a software
  BIT-BANG I²C master, not a hw I²C engine:** bit0=enable-SCL-out-buf, bit1=SCL-out, bit4=SCL-**in**;
  bit2=enable-SDA-out-buf, bit3=SDA-out, bit5=SDA-**in** (bits7/6 = unrelated CRC-signature ctrl). Maps
  1:1 onto QEMU's in-tree `hw/i2c/bitbang_i2c.c` (bit-bang master) → `hw/display/i2c-ddc.c` (EDID slave
  @0x50) — the faithful model is "wire CRB7 bits0-5 to bitbang_i2c → i2c-ddc," reusing existing pieces,
  not inventing a protocol. **DEPENDENCY (datasheet §36 l.19634, decisive):** CRB7 is a CRTC register
  reached from the BMC ARM ONLY via the **A2P AHB→P-bus bridge @0x1E720000 (row 50 / #176)** — "AHB to
  P-bus bridge control registers address = 0x1E720000+OFFSET", OFFSET 0x00000-0x0007F = relocated legacy
  VGA I/O (index/data 3B4/3D4→3B5/3D5), 0x10000-0x1FFFF = P-bus MMIO (CRTC `MMIOBASE+B7`); auto-enabled
  by SCU70[4] (PCI-master mode). The G3 QEMU models neither the A2P bridge nor the PCI "internal VGA"
  graphics function, so **#178 blocks on #176** (the CRTC aperture must exist before DDC is reachable).
  **UNRESOLVED CONFLICT (2026-07-21 gate-a #2): row 50's note explicitly OVERRIDES this** — it states
  "DDC/EDID (row 14) does NOT depend on A2P … the earlier '#178 blocks on #176' note conflated the two."
  So the two rows disagree on whether the DDC bit-bang register (CRTC CRB7) is reached through the A2P
  P-bus window or via a separate CRTC aperture. This must be settled from the datasheet before #178
  starts (does CRB7 live behind 0x1E720000, or a distinct CRTC MMIO base?) — see task #197.
  Oracle-note: this is the VGA path the C4 vendor firmware drives for its web/KVM console, so it is
  oracle-sensitive — build as self-contained regions + re-boot both oracles. QE stays ⬜ (real work,
  correctly located + dependency-mapped; NOT Ⓝ — VESA DDC to VGA1 is genuine board function). D12 / #178.

## I²C / SMBus (§10)

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 15 | AST2050 I2C controller (8 engines) | I2C | ✅ | ✅ | 🔶 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 16 | W83795G hwmon (QU4, I2C2 @0x2f) | I2C | 🔶 | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 17 | QU9/QU5/U23 mux fabric | I2C+GPIO | ✅ | Ⓝ | Ⓝ | ✅ | 🔶 | 🔶 | ✅ | ⬜ |
| 18 | DIMM SPD ×16 (I2C10/11 via mux) | I2C | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ✅ | ⬜ |
| 19 | DIMM TSOD ×16 (jc42) | I2C | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 20 | HT24LC08 FRU EEPROM (U25, I2C5 @0x54) | I2C | ✅ | 🔶 | 🔶 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 21 | W83601G DIMM-LED exp U27 (I2C5 @0x18) | I2C | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 22 | W83601G DIMM-LED exp U28 (I2C5 @0x19) | I2C | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 23 | SB-TSI CPU thermal (I2C4, 0x4C/4D) | I2C | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ✅ | ⬜ |
| 24 | PSU PMBus (PSUSMB1, I2C1) | I2C | ✅ | Ⓝ | Ⓝ | ✅ | ⬜ | ✅ | ✅ | ⬜ |
| 25 | SMBus ALERT (SALT1/2, I2C7) | I2C | ⬜ | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 26 | Aux front panel (AUX_PANEL1, I2C8) | I2C | 🔶 | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 26b | PCIe-slot 1–5 SMBus + TPM-hdr I²C (I2C8_SW far-ends, host-on) | I2C | 🔶 | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

- **15** i2cdetect + AC-timing fix proven on silicon. UB-Q = Raptor `libi2c`. D08.
  **ZQ = 🔶 (2026-07-19): the Zephyr I2C master driver (`i2c_aspeed_g3.c`, #148) is
  QEMU-VALIDATED** — it reads the modeled W83795 @0x2F CHIP_ID (0xFE=0x79) over the full
  START/write/repeated-START/read/STOP path, incl. the G3 SCU reset-release + AC-timing +
  INTR_CTRL gotchas (evidence `d14-zephyr/07`). This makes rows 16-23 (all the on-bus
  devices) REACHABLE from Zephyr. **UPDATE 2026-07-19: the I2C
  master + W83795 hwmon client are now SILICON-validated (ZS ✅) — w83795_smoke read the
  real W83795 @0x2f on the live AST2050 (fan1≈2631 rpm, temp0≈58.5 C, live drift). The other
  devices' per-device Zephyr drivers on this bus remain to be written. UPDATE 2026-07-20:
  row 15 ZQ 🔶→✅ — the QEMU I2C transaction (evidence `07`) is a COMPLETE
  START/write/rSTART/read/STOP pass, and ZS is already ✅, so ZQ cannot be merely partial
  (silicon-done implies QEMU-done). Slave/target mode is a separate capability tracked as #164.**
- **16** W83795 model silicon-seeded (fan1=2641 etc.); hwmon both sides. D08. **ZQ 🔶→✅
  (2026-07-20):** evidence `09` shows QEMU `W83795 fan1=2641 rpm temp0=50.500 C … PASS`, and ZS is
  already ✅ (silicon read) — a complete QEMU pass, so ZQ = ✅. **FAN-CONTROL capability now modeled +
  validated (#174, 2026-07-20, evidence `d14-zephyr/23-w83795-fanctl-qemu.txt`):** the gate-d pass flagged
  that row 16 validated only the READ side; the BMC's fan-DRIVING function (schematic §10.2 "write
  FANCTL1-8 PWM") was unmet (the QEMU model only STORED PWM writes). Fixed the model (submodule 463833bed1)
  so a PWM-duty write drives the fan tach (RPM=duty*27); `samples/w83795_fanctl_smoke` PASSes in QEMU —
  baseline 2641, PWM 0x80→3461 rpm, PWM 0x40→1728 rpm (tach TRACKS duty); the Zephyr fan-control path is
  ZQ-validated. **QE = 🔶 (2026-07-20 gate-d/#183, honest scope of "all functionality"):** the model covers
  register reads + the linear PWM→tach DRIVE + now **CASEOPEN (chassis-intrusion latch) + VID_CTRL** — added
  2026-07-20 (submodule 2d135ec3f9), register-validated in QEMU via raw i2c (`evidence/d08-w83795-caseopen/
  00`: ALARM(5)=0x46 bit6 latched=1 → CLR_CHASSIS[7] write → 0; VID_CTRL=0x6A reads 0x01). STILL missing for
  ✅: the SmartFan automatic thermal→fan-curve control mode, and the alarm/limit comparison + SMBALERT#
  assertion (SMBALERT ties into the shared aspeed_i2c ALERT work #135/#157). So 🔶 remains honest (consistent
  with row 42 PECI's "not complete functionality → 🔶"); #183 now scoped to SmartFan+alarm only.
  **CASEOPEN LU (userspace) VALIDATED (#184 DONE, 2026-07-20):** extended the modern-hwmon w83795 driver
  patch (0003) to expose the intrusion latch as the standard `intrusion0_alarm` hwmon attr (channel
  HWMON_INTRUSION_ALARM; read=ALARM(5) bit6, write 0=CLR_CHASSIS[7]); incrementally rebuilt the C2 kernel +
  re-ran through `/sys/class/hwmon` — `intrusion0_alarm before=1, echo 0, after=0`, PASS (evidence
  `d08-w83795-caseopen/00`). Full userspace→driver→i2c→fabric→model path proven. (cpu0_vid still not
  surfaced — modern hwmon has no VID channel type; a devattr for VID is a separate small follow-on.)
  **ALARM-STATUS both sides (2026-07-20, #183):** the model previously reported NO voltage/fan alarms —
  ALARM(0..4) (0x41..0x45) fell through to the zeroed scratch store — contradicting the very silicon it
  copied its readings from. QE: seeded ALARM(0..4) to the EXACT silicon capture (host-w83795-sensors.txt):
  in1/3/5/7→0x41=0xAA, in10→0x42=0x04, in15/16→0x43=0x03, fan2..8→0x45=0xFE (submodule 3d5df467ca); each
  bit self-consistent with the modelled measurement+limit. Register-validated over raw i2c (evidence
  `01`: 0xaa/0x04/0x03/0xfe PASS). LU: extended patch 0003 to expose inN_alarm/fanN_alarm (HWMON_I_ALARM/
  HWMON_F_ALARM, read = alarms[idx>>3] bit idx&7); userspace-validated (evidence `02`:
  `in0=0 in1=1 in7=1 fan1=0 fan2=1` PASS). **#183 now scoped to SmartFan auto-mode + LIVE
  limit-vs-measurement recompute + SMBALERT# only** (the static alarm STATUS is done; no legacy oracle
  reprograms these limits so the static seed is faithful for every real boot).
  **23** SB-TSI ZQ 🔶→✅ (2026-07-20):
  evidence `10` `SBTSI temp=45.500 C (expect 45) PASS` in QEMU (validates i2c_aspeed_g3 on a 2nd
  engine); ZS stays ⬜ (host-CPU-gated).
- **17/18** fabric DATA PATH proven on silicon (real 256-byte SPD read, CRC 0xf0b4,
  part matches host dmidecode; `evidence/d08-spd-silicon/`). **HONESTY CORRECTION
  (2026-07-18 audit):** row 17 LS/LU dropped ✅→🔶 — on THIS rig the BMC flash socket is
  empty → `BMC_PRESENT#` pulls high → U23 hands QU5 select-ownership to the SP5100
  PERMANENTLY, so the BMC's OWN QU5 select (the defining function of the fabric) is
  BLOCKED; the SPD read only worked because the HOST steered the mux (`setpci` on the
  SP5100), per the evidence README's own "board-arbitration reality". BMC-autonomous
  select is validated in QEMU (LQ ✅, model drives it) but NOT on this silicon rig
  (LS/LU 🔶, data-path only, channel-select host-assisted). Row 18 SPD read is genuine
  but carries the same U23 caveat (BMC-autonomous SPD inventory not silicon-demonstrated). D08.
  **Zephyr ZQ 17+18 ⬜→✅ (2026-07-20, `evidence/d14-zephyr/22-spd-mux-qemu.txt`):** `samples/spd_smoke`
  drives the WHOLE fabric from Zephyr — it powers the host on (closing QU9; `STA_LINE_POWER`=1), then
  routes the QU5 selects to Y2 (GPIOF4/F5 = gpio1 p12/13, S1:S0=10) and reads the DIMM-A2 SPD @0x51 on
  i2c1 → byte2=0x0B (DDR3), byte3=0x02 (UDIMM), `SPD RESULT: PASS`. Note: the first attempt NAKed and I
  root-caused it to the faithful QU9/SYS_PWRGD host-gating (fabric unreachable while host off) — powering
  the host on is the proper fix, not a workaround. Exercises the gpio + i2c drivers together. ZS stays ⬜
  for both — needs the real host powered + a populated DIMM on the bench (#150/#165, host/rig gates).
- **19** the rig's A2 UDIMM has SPD byte32=0 (no TS) → 0x19 NAKs on QEMU+silicon; the `jc42` model is kept available for TS-equipped DIMMs. Ⓝ for this rig. **LQ ✅→Ⓝ (2026-07-21 over-claim audit):** the LQ ✅ rested on "the jc42 model file exists", but the machine deliberately does NOT instantiate a jc42 on this rig (0x19 NAKs faithfully), so the Linux jc42 driver has no device to bind/read — LS/LU/ZS are already Ⓝ, so LQ must be Ⓝ too (a near-exact twin of the row-39 RTC over-claim: ✅-resting-on-model-exists rather than a functional read). **QE ✅→Ⓝ + ZQ ⬜→Ⓝ (2026-07-21 over-claim audit #2):** the SAME defect for the remaining cells — the machine deliberately instantiates NO jc42 (`hw/arm/aspeed.c:663-665,714-715` "the model deliberately does NOT place a jc42 here"), so the QE "emulation" rested only on "the jc42.c model file is available", and the Zephyr-QEMU cell (ZQ) likewise has no device to bind. All 8 cells are now Ⓝ for this rig (TS-less A2 DIMM). D08.
- **20** FRU EEPROM DONE both sides (2026-07-18): I2C5/i2c-4 enabled, at24 24c08 binds 0x54-0x57 on silicon (present but BLANK 0xff — ASUS unprogrammed) and in QEMU (blank model); `evidence/d08-fru/`. Corrects §10.2 (0x54, not 0x50). **Zephyr ZQ+ZS ✅ (2026-07-19):** `samples/fru_smoke` reads the FRU via the at2x driver over `i2c_aspeed_g3` on engine 4 — QEMU `ff ff ff ff` PASS and REAL SILICON `FRU RESULT: PASS` after the SCU74[12] I2C5 pin-mux fix (commit 355a9c7; see LOG 2026-07-19).
- **21–22** W83601G U27/U28: **BOTH-SIDES DONE** (datasheet-faithful `hw/gpio/w83601g.c`, `scripts/w83601g-test.py` 19/19 PASS incl. LED-drive; CI `boot-w83601g`; **silicon LED-drive proven on BOTH 0x18 and 0x19 — CR03/CR01 write + readback + restore**, evidence d08-w83601g/03; CR21 silicon-resolved to 0x13). No in-kernel driver by nature (raw userspace SMBus) → LQ/LS/LU all via userspace. **Zephyr ZS ✅ (2026-07-19):** the proper `drivers/gpio/gpio_w83601g.c` + `samples/w83601g_smoke` validated on REAL SILICON for BOTH U27 (0x18, port_get=0x0807) and U28 (0x19, port_get=0x61b5) — input read ACKs + pin-3 HIGH→LOW output round-trips in CR01, after the SCU74[12] I2C5 pin-mux fix (commit 355a9c7). Smoke PASS gate made platform-agnostic (input-value differs QEMU↔silicon). **23** SB-TSI (D9): **QEMU DONE** (`hw/sensor/sbtsi.c`, `scripts/sbtsi-test.py` 8/8, CI `boot-sbtsi`); silicon needs host-CPU-on. **24** PSU PMBus (I2C1): **QEMU DONE 2026-07-19** — `hw/sensor/pmbus_psu.c` (generic PMBus-1.2
supply @0x58 on bus 0 = schematic I2C1/PSUSMB1, seeded 230V-in/12V-8A-out/30C/4000RPM,
PMBUS_REVISION 0x98=0x22), wired in `kgpe_d16_bmc_i2c_init`; validated by the bare-metal
fwtest (`test_psu_pmbus_probe`: 0x58 ACKs on bus 0 only, `4 passed`) + the prior
`i2cget 0x58 0x98 → 0x22`. QE ✅ (submodule 8320c07f3f). **Zephyr ZQ ⬜→✅ (2026-07-20):**
`samples/pmbus_smoke` reads the PSU over the G3 I2C master on the NEW i2c0 node (engine 0 = I2C1) —
`VOUT_MODE=0x17 exp=-9`, `READ_VOUT raw=0x1800 → 12000 mV`, `REVISION=0x22`, all matching the model;
`PMBUS RESULT: PASS` (evidence `d14-zephyr/21-pmbus-qemu.txt`). ZS stays ⬜ — the real bench presents no
PMBus PSU on PSUSMB1 (rig-hardware gate #165, NOT a code gap; the i2c0 engine+driver path is the same
one proven on silicon for engines 1/3/4). **LQ ⬜→✅ + LU ⬜→✅ (2026-07-21):** the mainline generic
`pmbus` hwmon driver (CONFIG_SENSORS_PMBUS) binds + **identifies** the modeled PSU on the new `&i2c0`
node and userspace reads live telemetry (`hwmon3 name=pmbus dev=0-0058`: VIN 230 V, VOUT 12 V, temp 30 C,
IIN 1 A, IOUT 8 A) — evidence `d08-pmbus/01-pmbus-linux-qemu-PASS.txt`, initramfs `pmbustest` gate.
ROOT CAUSE of the first attempt's `PMBus status register not found`: a self-inflicted DT mis-nesting —
`psu@58` was placed under the mux-child node also written `i2c@0` (`i2c-parent=<&i2c1>`, QU5 Y0) instead
of the engine-0 controller `&i2c0`, so the client landed on a mux child where nothing answered and every
identify read NAK'd. Fixed by attaching to the controller label `&i2c0` (matching QEMU
`aspeed_i2c_get_bus(&soc->i2c,0)`). The model + hardware model were faithful throughout — it was my
wiring ("the hardware is 100% reliable; it's your code"). LS stays ⬜ (same rig-hardware gate #165 as ZS).
**25** SMBus-ALERT (SALT1/2): **scoped 2026-07-19** — the aspeed I2C register header
(`include/hw/i2c/aspeed_i2c.h:101`) DEFINES `SMBUS_ALERT` (intr-status bit 12, "Bus
[0-3] only") but `hw/i2c/aspeed_i2c.c` never DRIVES it; no bus device asserts SMBALERT#
and there is no ARA (0x0C) response path. Faithfulness subtlety to settle from the
datasheet first: the schematic routes SALT1 to **I2C7/B12** (§10.2/§10.4, "alert on
SCL7/SALT1 B12") yet the intr bit is buses 0-3 only — so SALT may be a standalone
SMBALERT# monitored input, not the per-engine intr. Closing it edits the SHARED
`aspeed_i2c.c` (all C2/C4 I2C oracles depend on it) → do it carefully in a fresh pass,
datasheet-first, with an oracle re-boot; NOT rushed. Task #135. See FULL-TASK-LIST.md D3/D4/D9. **26b** (#151, added 2026-07-19 from my independent schematic read): per `I2C-MUX-FABRIC-ARBITRATION.md §4`, with the host ON (QU9 closed) the `I2C8_SW` segment reached via QU5 `Y0` bridges through 0 Ω `QR160/QR161` → nets `I2C13SDA/SCL` → **TPM1 header pins 13/14** (0 Ω `RN13`) **and PCIe slots 1–5 SMBus** (`PCIE<n>_I2C13` via `ER21…ER57`). These are **BMC-masterable I²C SEGMENTS, not fixed on-board devices** — what answers depends on the plugged PCIe cards / TPM module (an empty slot / absent TPM = no target). QE = 🔶 (the QU5 `Y0` mux path itself is modeled at the fabric level, row 17; there is no fixed far-end device to instantiate — a host-on bus-reach test would exercise it). Distinct from the aux-panel end (row 26) on the same channel.
- **26** reachable via the fabric Y0 (QEMU); no Linux driver/test. D08.

## GPIO / platform control (§11)

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 27 | Power control (ATXPSON#/PWRBTN#/SYSRESET#/SYS_PWRGD) | GPIO | ✅ | 🔶 | 🔶 | ✅ | ✅ | ✅ | ✅ | ⬜ |
| 28 | Platform monitors (THERMTRIP#/PROCHOT#/DDR_THERM#/NMI#) | GPIO | 🔶 | ⬜ | ⬜ | 🔶 | ⬜ | ⬜ | 🔶 | 🔶 |
| 29 | Platform control (CLRTC#/BIOSREVRY#/CPU1-2DISABLE#/PCIRST#) | GPIO | 🔶 | ⬜ | ⬜ | 🔶 | ⬜ | ⬜ | 🔶 | ⬜ |

- **27** power control both sides. **HONESTY CORRECTION (2026-07-18 audit):** power
  ON/OFF are silicon-proven (`evidence/real-hw-f2sta/power-on-A4-fix.txt`: BMC drove the
  plug 3W→103W ON, 46W→3W OFF, A4-lockout fix); **RESET is QEMU-proven only** — the
  `f2-power-sysfs-onoffreset-PASS.txt` transcript is the QEMU run (`evidence/qemu/`), no
  separate silicon reset transcript (same GPIO-pulse mechanism, so low-risk, but capture
  one for a clean silicon reset ✅). U-Boot UQ/US ⬜ UNDERSTATES Raptor (commit 323b3ac
  drives bank-A power/reset GPIO at boot_init) → should be 🔶. GPIOB6 schematic(SYS_PWRGD)
  -vs-RE(reset-req) net-name conflict unresolved (audit #9). D09.
  **Zephyr ZS = ⬜ (2026-07-20 gate-d honesty correction, was 🔶):** the `power_smoke`
  silicon RESULT is **FAIL** — only the OUTPUT actuation is demonstrated on silicon (Zephyr
  GPIO drives the real board power 4W↔97W), but the automated smoke does not pass because the
  GPIOH2 feedback read is a mis-modeled standby-rail sense (#162). A FAILing smoke is not a
  partial-✅, so ⬜ is the honest floor until #162 makes the smoke pass. Zephyr ZQ = ✅ (QEMU
  full 0→1→0 trajectory PASS — now EVIDENCE-BACKED by `evidence/d14-zephyr/20-power-qemu.txt`:
  `POWER RESULT: PASS`, H2 0→1→0; captured 2026-07-20 after an audit flagged the ✅ as
  assertion-only).
- **28/29** ~10 §11 signals not yet mapped in DTS `gpio-line-names` — the §16 per-pin table names the
  specific ones the §11 prose omits (gate-a audit 2026-07-20): `AST_BIOS_POST_COMPLT#` (A10),
  `AST_SYNCFLOODIN#` (B8), `AST_PSONEN` (D11), `FP_NMIBNT#` (U1), `AST_RESETDIS#` (C10), `AST_PWRBNTDIS#`
  (C11) — these are GPIO line FUNCTIONS on the rows-27-29 controller, not separate devices (fold into the
  DTS line-names when completed; do not need their own rows). **ZS update (2026-07-20):
  row 28 (platform MONITORS — THERMTRIP#/PROCHOT#/DDR_THERM#/NMI#, all INPUT reads) ⬜→🔶** on the
  SAME convention ZQ uses: evidence `d14-zephyr/15` proves the Zephyr GPIO driver READS a real
  bonded input pin on live silicon (GPIOH2, PASS), so the generic silicon input-read path is proven;
  the specific row-28 pins are not yet individually read (hence 🔶 not ✅). **Row 29 (platform
  CONTROL — CLRTC#/PCIRST# etc., OUTPUT drives) stays ⬜:** evidence `15` is read-only, so the Zephyr
  output-drive-on-silicon path is not captured for these (same reason row 32 LEDs ZS stays ⬜). D09.
  **Naming note (C6):** the §11 *narrative* labels the two CPU sockets CPU1/CPU2 (P1/P2), but
  the authoritative 355-ball pinmap (`QU1_pins.md`) uses 0-indexed CPU0/CPU1 (P0/P1) — e.g.
  `AST_CPU0DISABLE#`=D8, `TTL_P0_THERMTRIP#`=V4. These are the SAME two sockets:
  CPUn(narrative) = CPU(n−1)(pinmap). BOTH sockets are covered here; the net-name strings in
  rows 28/29 follow the schematic narrative. A full rename to the pinmap convention is tracked
  in #153.

## Serial (§12)

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 30 | UART console (UART2, AST_UART1) | UART | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🔶 | 🔶 |
| 31 | UART1 / SOL via QU8 mux → Super-I/O (§12) | UART+glue | 🔶 | Ⓝ | Ⓝ | 🔶 | ⬜ | ⬜ | ⬜ | ⬜ |

- **30** console both sides (all boots). **Zephyr RUNS AN APP in QEMU** (ZQ 🔶): the
  AST2050 port boots and runs application code — `*** Booting Zephyr OS ***` +
  `Hello World! kgpe_d16_bmc/ast2050` — via a static-mapped polling SoC console
  (`soc/aspeed_g3/ast2050/console.c`, printk+stdout hooks). The M1 VIC (`vic.c`) + aspeed
  timer (`aspeed_timer.c`) deliver interrupts and now run **SUSTAINED tickful scheduling**.
  **HONESTY CORRECTION (2026-07-18 audit): the earlier "sustained tick data-aborts at the
  upstream ARM9 arm_mmu L1 table" attribution was WRONG** — per the newer evidence
  `d14-zephyr/05-m1-tick-validated`, the root cause was `CONFIG_HW_STACK_PROTECTION` (OUR
  config: the per-thread stack-guard MMU reconfig removed write access from the static
  `l1_page_table`'s own page), NOT an upstream bug. Fix = `HW_STACK_PROTECTION=n` +
  `SYS_CLOCK_EXISTS=y`; the app then runs the FULL 12 s with 0 data-aborts (task #141
  DONE — for the SHORT-run tickful case). **HONESTY CLARIFICATION (2026-07-20 gate-d):** #141 "DONE"
  covers the HW_STACK_PROTECTION short-run fix ONLY; there is a SEPARATE, still-OPEN **QEMU-only**
  arm_mmu sustained-ticking corruption at ~2264 ticks (evidence `d14-zephyr/17`/`03`) that longer runs
  hit — do not read "#141 DONE" as "all Zephyr tick issues closed". That sustained-tick QEMU limit is
  why the silicon smokes are kept short; it does NOT affect real silicon (no such limit there). Do NOT
  blame upstream. (The standard `uart_ns16550.c` console IS still blocked
  by the separate `z_phys_map` device-VA gap — that one is real + open.) Per-device Zephyr
  drivers (GPIO #147, I2C #148, WDT #149) build on this now-clean tick. **ZS = 🔶 (not ⬜):
  corrected 2026-07-20** — the static-mapped polling console is PROVEN on real silicon: EVERY Zephyr
  silicon smoke this program prints through it on `/dev/serial-bmc-console` (evidence `d14-zephyr/17`
  heartbeat, `/18` WDT, `/19` SCU, `/14` RTC, `/15` GPIO). ZS mirrors ZQ (🔶): the polling backend
  works both sides; only the *proper* ns16550 driver stays blocked (same `z_phys_map` device-VA gap)
  on QEMU **and** silicon. Leaving it ⬜ understated real, evidenced functionality. D10/D11/D14.
- **31** SOL essentially unimplemented end-to-end (audit gap #2): no QU8-mux/Super-I/O model, no Linux SOL session, no host bytes on silicon. D10.

## JTAG / LEDs / clock / straps (§13)

| # | Device (schematic) | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 32 | LEDs (BMCRDY/MLED/CPUERR/chassis-ID) + chassis-locator button in (AST_IDBNT#/Y3) | GPIO/LED | ✅ | Ⓝ | Ⓝ | 🔶 | ✅ | ✅ | 🔶 | ⬜ |
| 33 | Straps (IKVMEN#/SOLEN#/IPMI_SEL) | GPIO | ✅ | ✅ | ✅ | ✅ | ✅ | Ⓝ | 🔶 | 🔶 |

- **27-29/32-33 ZQ = 🔶 (2026-07-18):** the enabling **Zephyr GPIO driver
  (`gpio_aspeed_g3.c`, #147) is QEMU-VALIDATED** — configure/set/clear/read a pin works
  (evidence `d14-zephyr/06`). 🔶 not ✅ because that proves the GENERIC GPIO port, not each
  row's SPECIFIC pins (power A4, the THERMTRIP/PROCHOT inputs, the LED/strap lines) driven
  from a Zephyr app; those per-function Zephyr validations remain. **ZS silicon (JTAG-load)
  update 2026-07-20: the INPUT-read rows 28 + 33 are now 🔶** (evidence `15` proves the generic
  Zephyr GPIO silicon input-read); the OUTPUT-drive rows 29 + 32 stay ⬜ (evidence `15` is read-only);
  row 27 ZS stays ⬜ (smoke FAILs, #162).
| 34 | 24 MHz clock input (QOSC1) | SCU/clk | ✅ | ✅ | ✅ | ✅ | ✅ | Ⓝ | ✅ | ✅ |
| — | AST_JTAG1 (§13/§15) | ARM debug | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |

- **32** LS/LU=✅: **silicon LED-drive DONE (2026-07-18, host on)** — `echo 1 > /sys/class/leds/identify/brightness` flips the real GPIO `led-id-n out hi→out lo` (LED ON) and `echo 0` flips it back; the `/sys/class/leds` userspace → aspeed-GPIO path drives the real hardware. Evidence `evidence/e-gpio-leds/00`. The same debug-gpio dump also confirmed the BMC driving `led-bmc-status-n` (ON) + `led-cpu1/2-err-n` (no faults), the E1 power/reset GPIO map, and the D6 QU5 mux selects on silicon. **QE 🔶→✅ (2026-07-20, `evidence/e-gpio-leds/01-qemu-led-drive-observe.txt`):** a QEMU C2-Linux boot with a new `ledtest` init gate drives `echo 1/0 > /sys/class/leds/identify/brightness` and observes `/sys/kernel/debug/gpio` (= the aspeed-gpio driver reading the QEMU model's data register) — `gpio-560 (led-id-n |identify) out hi → out lo → out hi`, `LED-TEST RESULT: PASS`. IDENTICAL to the silicon dump (same gpio-560, same label, same hi↔lo), so QEMU emulates the LED-drive path end-to-end (userspace→gpio-leds→aspeed-gpio→model), not just "nodes present". First boot FAILED honestly (repack left `/init` non-exec → EACCES → BusyBox fallback; fixed via chmod 0755 per build.py:183 — see LOG).
- **34** the 24 MHz ref is consumed by SCU/clk (validated via every boot). Ⓝ userspace. **Zephyr
  ZQ/ZS ⬜→✅ (2026-07-20):** the 24 MHz QOSC1 input is consumed by EVERY Zephyr boot exactly as for
  U-Boot/Linux (which are ✅) — the SCU/PLL lock onto it (the SCU smoke #169 read SCU registers clocked
  from it, evidence `19`) and the system timer runs at the derived rate (the heartbeat ran 10 sustained
  ticks in real time, evidence `17`). Same "consumed via every boot" basis as the other stacks; ⬜ was
  an understatement.
- **AST_JTAG1** is the silicon TEST HARNESS (how all silicon boots happen), not a driver target → Ⓝ (explicitly out of scope, not omitted).

## SoC-internal core peripherals

| # | Device | SoC block | QE | UQ | US | LQ | LS | LU | ZQ | ZS |
|---|---|---|---|---|---|---|---|---|---|---|
| 35 | SCU (system control / clocks / pinmux) | SCU | ✅ | ✅ | ✅ | ✅ | ✅ | Ⓝ | ✅ | ✅ |
| 36 | VIC interrupt controller (0x1e6c0000) | VIC | ✅ | ✅ | ✅ | ✅ | ✅ | Ⓝ | ✅ | ✅ |
| 37 | Timers | timer | ✅ | ✅ | ✅ | ✅ | ✅ | Ⓝ | ✅ | ✅ |
| 38 | Watchdog (WDT) | wdt | ✅ | 🔶 | 🔶 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 39 | RTC | rtc | ✅ | Ⓝ | Ⓝ | ✅ | ✅ | ✅ | ✅ | 🔶 |
| 40 | PWM / tach block | pwm | ✅ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 41 | ADC — **ABSENT on G3** (phantom REMOVED ✅) | adc | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 42 | PECI engine (0x1E78B000, IRQ15; balls A9/B9) | peci | 🔶 | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 43 | HACE hash/crypto engine (0x1E6E3000, IRQ4) | HACE | 🔶 | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 44 | MIC memory-integrity check (0x1E640000, IRQ1) | MIC | ✅ | Ⓝ | Ⓝ | ⬜ | ⬜ | Ⓝ | ⬜ | ⬜ |
| 45 | MDMA memory-DMA engine (0x1E740000, IRQ6) | MDMA | ✅ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 46 | 2D BitBLT graphics accel (§35, via PCI/VGA) | 2D | ⬜ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 47 | PUART LPC pass-through UART (0x1E788000) | PUART | 🔶 | Ⓝ | Ⓝ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 48 | PCI arbiter (0x1E78C000) | PCI-arb | ⬜ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 49 | AHBC AHB-bus controller (0x1E600000, IRQ31) | AHBC | 🔶 | 🔶 | 🔶 | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |
| 50 | A2P AHB→PCI bridge (0x1E720000) | A2P | 🔶 | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ | Ⓝ |

- **35** SCU: exercised by every stack's init (QE/UQ/US/LQ/LS ✅). **Zephyr ZQ+ZS ✅ now
  (2026-07-20, `evidence/d14-zephyr/19-scu-silicon.txt`):** `samples/scu_smoke` reads the SCU
  silicon-revision register `SCU7C` via the flat-mapped SCU page — `0x00000202` on BOTH QEMU and
  real silicon, matching the value independently confirmed via culvert-P2A and JTAG-AHB (four access
  paths agree). `SCU70` hw-strap also matches bit-for-bit (`0x00819582`), confirming the QEMU
  machine's strapping was modeled from the board. Read-only cross-check; the SCU clock-rate program
  (H-PLL/CLKIN) validation is tracked separately as #142. D11.
- **36–37** VIC (keystone G3 fix `irq-aspeed-g3-vic`, HW-verified) + Timers: the Zephyr port's
  Milestone-1 `vic.c`/`aspeed_timer.c` drive these blocks. **ZS ✅ now EVIDENCE-BACKED
  (2026-07-20, `evidence/d14-zephyr/17-heartbeat-vic-timer-silicon.txt`):** the `heartbeat_smoke`
  sample did 10×`k_msleep(100 ms)` on real silicon with uptime advancing monotonically
  130→1120 ms — each returned sleep = one proof the Timer1 tick IRQ fired AND the VIC routed+acked
  it (a dead timer/VIC hangs the first sleep). Was LOG-prose only per the gate-d audit. D11.
- **38** WDT: **Zephyr ZS ✅ now EVIDENCE-BACKED (2026-07-20, `evidence/d14-zephyr/18-wdt-silicon.txt`):**
  `wdt_smoke` on real silicon armed a 500 ms RESET_SOC watchdog, fed 3×, then stopped — the console
  showed one cycle then went silent at the timeout and a JTAG halt confirmed the SoC reset
  (Undefined-instr mode, PC in the flash-mapped low region not `0x40xxxxxx` DRAM, stale Zephyr
  `sp_und`); QEMU both-sides = 6 reboots. **LS = ✅ (Linux, 2026-07-21, `evidence/f-wdt-userspace/01-silicon-dev-watchdog.txt`):**
  the DEDICATED `/dev/watchdog` transcript on real AST2050 silicon is now captured — the `wdttest`
  gate over the working static-IP netboot showed `identity=aspeed_wdt`, both WDTs enumerated
  (`/dev/watchdog0`+`1` = WDT1+WDT2), userspace `busybox watchdog -T 30` → `timeout` reads back 30
  (WDIOC_SETTIMEOUT reached the driver→hardware), `state` inactive→active (armed): `WDT-USERSPACE
  RESULT: PASS`. Combined with the already-silicon-proven WDT RESET (ZS below + the g3-clk 120 s
  reset), the Linux WDT is validated on silicon (userspace API+arm here, real reset via ZS). **LU ⬜→✅ (2026-07-20,
  `evidence/f-wdt-userspace/00-qemu-dev-watchdog.txt`):** the userspace `/dev/watchdog` interface is now
  FULLY exercised in QEMU. (1) API: a `wdttest` gate runs `busybox watchdog -T 30` → `identity=aspeed_wdt`,
  `timeout` reads back 30 (WDIOC_SETTIMEOUT reached the driver→model reload reg), `state` inactive→active
  (armed): `WDT-USERSPACE RESULT: PASS`. (2) Real effect: a `wdtreset` gate runs `busybox watchdog -T 3
  -t 60` (arm 3 s, don't re-pet for 60 s) → the WDT fires at ~3 s and RESETS the SoC — proven by 6/6
  consecutive `WDT-RESET-ARMED → [0.000000] Booting Linux on physical CPU 0x0` reboot cycles, 0 "STILL
  ALIVE". So userspace open→SETTIMEOUT→arm→keepalive AND stop-feeding→real SoC reset all work = the full
  LU (userspace-interface) deliverable. **Platform note:** the QEMU-userspace deliverable
  (matching the LQ platform); the LS (Linux-SILICON) /dev/watchdog transcript is now ALSO captured on
  real AST2050 (see the LS ✅ above); the userspace-ARMED real reset on silicon (wdtreset gate) stays a
  separate destructive test (flash-less board → a WDT reset halts the CPU, needs a JTAG re-boot) but the
  reset capability itself is already silicon-proven via ZS ✅ + the g3-clk 120 s reset. Honest findings:
  aspeed_wdt doesn't expose `/sys/.../timeleft` (first API run FAILed on my over-strict criteria that
  required it — a test bug, fixed, not a driver issue); busybox watchdog here doesn't magic-close on
  SIGTERM; board exposes TWO WDTs (watchdog0+watchdog1 = AST2050 WDT1/WDT2).
  **Zephyr TIMEOUT-INTERRUPT mode added (2026-07-21, #189, `d14-zephyr/27`):** the Zephyr driver did
  RESET mode only and rejected callbacks; it now also does the one-stage interrupt mode
  (WDT_FLAG_RESET_NONE + callback → WDT_CTRL[2]=WDT_INTR → VIC-27 → callback, NO reset), consuming
  the QE WDT-interrupt model (submodule 46cee5fe6a). Validated in QEMU deterministically (3/3
  `WDT-INTR RESULT: PASS`, console ran past the timeout = no reset), reset-mode wdt_smoke unregressed
  (8 boots). So Zephyr ZQ covers reset AND interrupt.
  **SILICON-VALIDATED (2026-07-21, #189, `d14-zephyr/27`):** the interrupt mode now fires on the real
  AST2050 over JTAG — `wdt intr fires=1` → `WDT-INTR RESULT: PASS (timeout -> VIC-27 -> callback, no
  reset)`; the console ran past the 200 ms timeout (no reset) and the gate-(b) disable+reinstall fix
  also held (`disable=0 reinstall=0`). A proactive VIC raw-status diagnostic CONFIRMED **VIC source
  27 is correct on silicon** for the WDT timeout-interrupt (unlike the RTC alarm's wrong source 26 —
  each model IRQ assumption is now verified, not assumed). So row 38 ZS covers BOTH reset (already
  proven) AND interrupt mode. Linux #189 stays scoped separately (mainline aspeed_wdt is a 2-stage
  pretimeout, a different semantic than the G3 one-stage interrupt-instead-of-reset). D11.
- **39** RTC (0x1E781000, counter-style, datasheet §24). **QE counter-ADVANCE now modeled
  (2026-07-21, #158, submodule f93addb7e0, `evidence/d14-zephyr/15-qemu-rtc-rate.txt`):** the model
  latched RELOAD→COUNTER but the counter never ticked (a frozen RTC, while silicon's counts). The
  KGPE-D16 has NO 32.768 kHz crystal, so the firmware clocks the RTC from the 24 MHz source
  (SCU08[16]=1; datasheet §2.19 "not necessary to include an external 32 KHz oscillator" + §24
  "clock source from 24MHz"); the RTC's fixed /32768 tick divider (datasheet §24:
  12MHz*128/46875 = 32768.0 Hz) then yields **24e6/32768 = 732.42 "RTC seconds"/real second** — the
  fast rate silicon showed (evidence 14). The model now advances the counter at clk_hz/32768 while
  CONTROL[0] is enabled (clk_hz = device property, default 24 MHz), anchored on RESTART/enable and
  frozen on disable. INERT AT RESET (CONTROL[0]=0 → frozen, bit-identical to before), so no
  legacy-oracle boot changes (C2 boots to BMC-READY; the enabled behaviour matches silicon).
  Register-validated (`rtcrate` /dev/mem gate): load 00:00:00, enable, sleep 1 s → +768 RTC-seconds
  (fast, not ~1). **LQ ✅→⬜ — OVER-CLAIM CORRECTED (2026-07-21):** the board Linux dts is based on
  `aspeed-g4.dtsi` (`rtc@1e781000` = `aspeed,ast2400-rtc`, BCD layout), but the real G3 RTC is
  counter-style — register-incompatible. Empirically (rtclinux gate) the C2 kernel creates NO `/dev/rtc0`
  / `/sys/class/rtc/rtc0`, so there is NO working Linux RTC on the G3; the prior "LQ ✅ (rtc-aspeed)" was a
  bind/assumption over-claim. **LQ/LU ⬜→✅ — NOW REAL (2026-07-21, kernel patch 0009, evidence
  `d14-zephyr/17`):** implemented the `aspeed,ast2050-rtc` counter-style variant in `rtc-aspeed.c` (read
  COUNTER byte-packed; set via RELOAD+RESTART=0x5A+enable; fixed calendar base since the counter has no
  year/month) + the `&rtc` dts override. Validated QEMU + userspace: `aspeed-rtc 1e781000.rtc: registered
  as rtc0`; `date -s 12:45:30` → `hwclock -w` → `hwclock -r` reads `12:45:40` (hour:min round-trip, sec
  advancing ~732x) + `/sys/class/rtc/rtc0/time` works. The over-claim is now genuine functionality.
  **WAKEALARM also done (RTC04+IRQ26):** the driver gained read/set_alarm + alarm_irq_enable + an IRQ
  handler + device_init_wakeup, and the dts `&rtc` gains `interrupts = <26>`; validated —
  `echo +5 > /sys/class/rtc/rtc0/wakealarm` arms it, the fast counter reaches it, QEMU raises VIC-26, the
  handler delivers RTC_AF and the core clears the one-shot (readback empty). Consumes the #187 QE alarm
  model. **LS stays ⬜** (silicon RTC via JTAG not yet run).
  **ZEPHYR ALARM also done (2026-07-21, #187, `d14-zephyr/26`):** the ZQ ✅ (which had covered
  set/get only) now also includes the Zephyr `rtc_driver_api` alarm ops in `rtc_aspeed_g3.c`
  (alarm_get_supported_fields=sec/min/hour, alarm_set_time→RTC04+CONTROL[1:3], alarm_get_time,
  alarm_is_pending, alarm_set_callback) + a VIC-26 ISR (recurring, per the Zephyr contract — NOT
  the Linux one-shot) + a k_spinlock guarding the CONTROL RMW. Validated in QEMU (rtc_smoke,
  CONFIG_RTC_ALARM): armed 12:00:05 mask=0x07 → the ~732x counter reached it → VIC-26 → callback
  (`alarm fires=1`) → `RTC-ALARM RESULT: PASS`.
  **SILICON-PROVEN + two model-hidden bugs FIXED (2026-07-21, #192, `d14-zephyr/28`):** the FIRST
  silicon JTAG run FAILED and exposed two real bugs the QEMU model hid — exactly the goal's "it's
  your code" mandate. (1) **RTC04 is FIELD-packed** (datasheet §24 hour[16:12]/min[11:6]/sec[5:0]),
  not byte-packed: a byte-packed hour write read back 0 on silicon; #186 ANSWERED for RTC04. Fixed in
  Zephyr+Linux drivers + the model's alarm compare. (2) **the alarm fires on VIC source 22** (the
  RTC's single IRQ), NOT the assumed separate source 26: a register-dump diagnostic showed source-26
  left VIC bit 22 latched-unserviced (fires=0), source-22 serviced it (fires=1). Fixed: driver IRQ
  26→22, model pulses s->irq/VIC22 (phantom source-26 alarm_irq removed), machine rewired, Linux dts
  interrupts=<22>. **Both fixes make the model FAITHFUL** — a byte-packed or source-26 alarm now FAILS
  in QEMU too. RE-VALIDATED: SILICON Zephyr alarm `fires=1` PASS; QEMU Zephyr alarm + Linux wakealarm
  + dev/mem rtcalarm all PASS on VIC 22. **So the RTC alarm now fires end-to-end on real silicon —
  the Zephyr-alarm ZS deliverable is DONE**.
  **LS ✅ + RATE-CLAIM CORRECTED (2026-07-21, `evidence/d14-zephyr/30`+`31`):** the Linux RTC now
  PASSES on real silicon — `set 12:45:30 → read 12:45:41` set/get + wakealarm (VIC22) both PASS —
  after fixing the driver to CLEAR SCU08[16] and poll CONTROL[5] restart-busy (an earlier driver
  revision forcing bit16=1 was MY regression that froze the counter). **And the "732x / can't do
  real time" claim (#158/#186) is WRONG:** a clean 20 s register-level silicon measurement with
  **bit16=0** gave **delta=21 over 21.0 s = 1.00x = EXACT REAL TIME** (evidence 31). The internal
  32.768 kHz source works; 732x only applies to bit16=1 (the "test only" 24 MHz tap Zephyr forces).
  So the board IS a real-time clock for HH:MM:SS + a day counter (the ONLY real HW limit is the
  absent month/year register — a register-map limit, not a clock-rate one). **ZS stays 🔶** only
  because the Zephyr driver still uses bit16=1 (732x) — a retest with bit16=0 + the CONTROL[5]
  load-wait (the bare-metal "bit16=0 → no clock" was likely the same async-load misread) may reach
  a real-time ZS ✅. RTC04-layout RESOLVED (field-packed, silicon); COUNTER minute-wrap still #186.
  QEMU-rate-tracks-bit16 faithfulness = #194-adjacent follow-up. D11.
- **40** the VP*/TACH* balls are GPIO monitors on this board; fans are on the W83795G FANCTL, not the AST2050 PWM → Ⓝ board-disposition (SoC model is complete). D13.
- **41** ADC — **CORRECTED (2026-07-18 honesty/faithfulness audit): the AST2050 (G3) has
  NO ADC block at all.** The repo's own authoritative datasheet extract `qemu-model/
  AST2050-MEMORY-MAP.md:96` states: "ADC (10-bit analog-to-digital) — **Absent** — No ADC
  chapter and no ADC entry in the §9 map (p97). ADC (0x1E6E9000 on G4) was introduced with
  the AST2400." **PRIMARY-datasheet double-check (#153, 2026-07-20):** confirmed against
  `datasheets/aspeed/AST2050_V1.05.txt` — the §1.3 peripheral table-of-contents has NO ADC
  controller entry (it lists Video-Compression/GPIO/WDT/PECI etc.), and every "ADC" occurrence in
  the datasheet refers to an *external video-source ADC* feeding the video engine (§ timing
  generator), not an on-SoC ADC block. So "Absent" is confirmed at the primary source, not just the
  extract. Yet the SoC model (`hw/arm/aspeed_ast2400.c:230,574-580`) UNCONDITIONALLY
  creates + maps an `aspeed.adc` at 0x1E6E9000 (IRQ 31 in the model, not even the IRQ 22
  the earlier note claimed — which the datasheet gives to the RTC-second). So the prior
  "QE=🔶, model+wire an ADC" was itself a faithfulness violation (a G4 device on the G3).
  Honest disposition: **all stacks Ⓝ (the device does not exist on this SoC)**. **DONE
  (2026-07-18, submodule 9eedd27540):** the phantom `aspeed.adc` create/realize/map is now
  gated on `sc->silicon_rev != AST2050_A1_SILICON_REV`, so the G3 machine presents NO ADC
  (verified: `tmp/check-adc.py` qtree shows aspeed.adc ABSENT on kgpe-d16-bmc, still PRESENT
  on ast2500-evb — no regression; a G3 access to 0x1E6E9000 now reads unassigned like the
  silicon). First increment of the #144 phantom-removal set landed. This supersedes the
  earlier gate-(d) "add an ADC row" call (which was itself the faithfulness error).
- **42** PECI engine — **ADDED (2026-07-19, closes #145 audit gap):** unlike the ADC, the
  G3 DOES have a PECI controller. AST2050-MEMORY-MAP.md:68 (datasheet §9 p97 / §32.3 p357):
  "PECI Controller | 0x1E78_B000 | ... | **Yes** | PECI 1.1/2.0", IRQ 15. The QEMU G3 SoC
  models it (`TYPE_ASPEED_PECI` @0x1E78B000, IRQ 15; aspeed_ast2400.c:52/128/246/628-635) → QE=🔶.
  **QE stays 🔶 (verified 2026-07-20, #145):** hw/misc/aspeed_peci.c is a FUNCTIONAL register/
  interrupt model (PECI_CMD FIRE → returns CC_RSP_SUCCESS 0x40 in RD/WR_DATA0 + raises the
  CMD_DONE IRQ) but NOT the full PECI 1.1/2.0 wire protocol (no CPU-temperature transactions) —
  a canned-response stub, adequate for register/IRQ exercise, not "complete functionality". Since
  PECI is UNWIRED on this board (below), that partiality is moot for the KGPE-D16; a full-protocol
  model would be pure upstream-aspeed work with no board consumer. **All driver stacks = Ⓝ (board
  disposition, parallel to row 40 PWM):** on the
  KGPE-D16 the PECI pins A9/B9 are strapped to GPIO (AST_ATXPSON#/AST_CLRTC#, §11) and CPU
  thermal is done over SB-TSI (I2C4, row 23) — the PECI engine is NOT wired to the CPUs
  here, so no U-Boot/Linux/Zephyr PECI driver has a target. The SoC block exists + is
  modeled; its board *function* is repurposed. **The remaining #145-audit sub-gaps are now
  DISPOSITIONED (2026-07-20):** GAP2 (WDTRST) — the WDT external reset-output pin (ball D9 =
  `GPIOB6/VBDO/WDTRST`, §11) is repurposed as **GPIOB6/SYS_PWRGD**, so the WDT's external reset is
  NOT routed out on this board; the WDT still resets the SoC internally (row 38, silicon-proven).
  GAP3 (AST_ROMA0→QQ11) — closed via #152 (QQ11 identified + given row/disposition). GAP4
  (UART1 modem lines) — UART1 = the SOL console; it wires TXD1/RXD1/**`NRTS1`(V21)/`NCTS1`(W22) → QU8
  2:1 mux → SOL** (row 33 / D10 / #133), i.e. 4-wire with RTS/CTS flow control; the remaining
  full-modem lines (DTR/DSR/DCD/RI) are NC (SOL does not use them). #145 enumeration complete.
- **43–48 SoC-internal engines (ADDED 2026-07-20, #173 — the gate-d structural blind-spot closure):**
  the schematic-scoped completeness audits (external wiring §§2–15) STRUCTURALLY could not reach SoC
  engines with no external pins. A gate-d pass found 6 real ones (all "**Yes**" in `AST2050-MEMORY-MAP.md`
  §9) that the matrix had omitted. Honest first-pass dispositions:
  - **43 HACE** (hash/crypto, 0x1E6E3000/IRQ4, 11 regs MD5/SHA/AES/RC4): **QE=🔶** — `aspeed.hace` IS
    modeled+mapped+IRQ-wired (aspeed_ast2400.c:355/862), but whether the generic G4 model matches the
    AST2050 11-reg variant is unverified. UQ/US=Ⓝ (crypto not boot-critical). LQ/LS/LU=⬜ (mainline
    `aspeed-hace` crypto driver exists but is NOT G3-validated; a full BMC secure-boot/TLS could use it).
    ZQ/ZS=⬜ (no Zephyr crypto driver). *Real work, honestly ⬜.*
  - **44 MIC** (memory-integrity, 0x1E640000/IRQ1): **QE=✅ (2026-07-21)** — `hw/misc/aspeed_mic_ast2050.c`
    wired into the G3 SoC (VIC INT#1): the §13 register block + the continuous-scanner semantics (per-page
    2-bit control words skip/ECC/debug/MIC-mode, checksum buffer, first/secondary/lost page-error flags +
    W1C, level IRQ1 gated by MIC14[17:16]). The Fletcher-32 is **bit-exact** — copied from the Raptor SLT
    `mictest.c do_chksum()` that byte-compares against real silicon; the model reaches DRAM via the AHBC
    boot-remap low aperture (rows 45/49) and includes the MDMA-review re-entrancy guard. Validated (evidence
    `soc-mic/01`, devmem gate): a zero page checksums to exactly 0xFFFFFFFF (independently computed), and
    corrupting the page flags MIC18 first-page-error + the correct page number 0x2000. **🎉 SILICON
    CROSS-VALIDATED (2026-07-21, evidence `soc-mic/02`):** the model was checked against the REAL AST2050 MIC
    over JTAG — the hardware computes the IDENTICAL bit-exact 0xFFFFFFFF zero-page Fletcher-32, tracks scan
    progress (MIC14=page), and sets MIC18 first-page-error + the correct page number on a mismatch. The model
    is faithful to real silicon bit-for-bit. (Lesson: the real MIC first "didn't scan" until I added the SLT's
    vInitSCU MIC reset-release SCU04&=0xbffff — the hardware was reliable, my JTAG driving was incomplete.)
    The AHBC key+remap (rows 45/49) are confirmed on silicon by the same run. **Disclosed
    simplifications (gate-(a) audit):** (1) the scan runs synchronously on enable (models the first pass the
    SLT relies on), not the continuous MIC08-rate loop; (2) MIC10 stop-page — the observable **TAG write-back**
    (`{TAG,16'b0}` → checksum-buffer[page]) IS modeled, but the stop-scan-AT-page function is moot under the
    synchronous scan (a scan completes atomically). Neither is exercised by any firmware here; the core
    integrity-check (bit-exact checksum → mismatch → error → IRQ1) is complete, so ✅ holds. LQ/LS=⬜ (an
    EDAC-style error reporter could exist); UQ/US Ⓝ (init-time; the SLT is a diagnostic, not the boot path);
    LU=Ⓝ; ZQ/ZS=⬜ (matching LQ/LS).
  - **45 MDMA** (memory-DMA, 0x1E740000/IRQ6): **QE=✅ (2026-07-21)** — `hw/misc/aspeed_mdma_ast2050.c` wired
    into the G3 SoC: register R/W with the faithful 28-bit src/dst address mask, MDMA0C-write-fires-command
    (copy/fill via address_space_memory with the raw 28-bit address — NO 0x40000000 fudge), per-ID done
    status (W1C) + level-high IRQ6 gated by MDMA10 mask + wired to VIC-6. Validated in two steps: (a) control
    path via `devmem` (evidence `soc-mdma/01`): 28-bit mask (0x12345678→0x02345678), command sets MDMA14[16],
    W1C clears; (b) end-to-end DATA MOVEMENT (evidence `soc-mdma/02`): with the AHBC boot-remap (row 49)
    aliasing SDRAM to 0x0, an MDMA copy src→dst through the low aperture round-trips 0xDEADC0DE. IRQ6 is
    modeled (level) + wired to VIC-6 + its status-set is validated; observing IRQ6-delivery-to-a-handler would
    need a bare-metal handler (Linux binds none — it would be spurious), a test-harness limit not a model gap.
    Oracle-safe: C2 + C-UBOOT boot with the AHBC/MDMA present. #172 SDHCI phantom used to squat here.
    Autonomous DMA; no BMC runtime driver → driver stacks Ⓝ. **Disclosed simplification (gate-(a) audit):**
    copy+fill+per-ID-done+IRQ6 are the modeled functionality; the 16-deep command QUEUE and the dynamic
    MDMA14 IDLE[3]/busy[0]/overflow[1] status progression are NOT dynamically asserted (the constants exist
    for W1C only) — moot in practice because execution is synchronous (queue stays empty/idle steady-state)
    and the datasheet's "poll IDLE" is conditional on odd MCLK/H-PLL ratios that this model does not stress;
    ✅ holds on the driven data-path functionality.
  - **46 2D BitBLT** (§35, graphics accel via PCI/VGA): **QE=⬜** (real, unmodeled). Host-side display
    accel reached via the PCI/VGA path (parallel to the VGA-DAC row 12) → drivers Ⓝ.
  - **47 PUART** (LPC pass-through UART, 0x1E788000): **QE=🔶 (2026-07-21; corrected ✅→🔶 by a gate-(a)
    faithfulness audit).** Modeled as a `TYPE_SERIAL_MM` 16550 in the G3 SoC (hw/arm/aspeed_ast2400.c, no IRQ
    per datasheet §10), replacing the iomem catch-all — the 16550 register file responds (scratch-register
    round-trip, evidence `soc-puart/01`). **Why 🔶 not ✅ (honest, per the audit):** it is a register-presence
    model, not full functionality — it has **no chardev backend** (so it cannot move a byte on either side,
    unlike the VUART which bridges to SOL via serial_hd(1)), and the **8 extended LPC-control registers
    PUART20–PUART3C** (§29.4: enable / SerIRQ / address-decode / UART1-2-select) sit outside the 0x20 SerialMM
    window and fall through to RAZ/WI, undecoded. Defensible only because no KGPE-D16 firmware drives PUART
    (drivers ⬜, not a runtime need). Completing it = decode PUART20–3C + a chardev/pass-through datapath (needs
    an LPC host peer, absent). UQ/US Ⓝ.
  - **48 PCI arbiter** (0x1E78C000): **QE=⬜** (real, unmodeled). Autonomous bus arbiter, init-configured,
    no runtime driver → all Ⓝ.
  These are first-pass dispositions to CLOSE the completeness gap (they were silently missing); the QE=⬜
  items are genuine QEMU-faithfulness todos (the real silicon has these blocks) and HACE's model-fidelity
  + the ⬜ driver cells are tracked follow-on work under #173.
- **49–50 (ADDED 2026-07-20, #175/#176 — a 2ND gate-d pass caught the 1st enumeration itself missed these):**
  - **49 AHBC** (AHB Bus Controller, 0x1E600000/IRQ31; regs 0x00 key/0x80 priority/0x88 IRQ/**0x8C
    Address-Remap** = boot remap of 0x0→SDRAM): **QE=🔶 (2026-07-21; corrected ✅→🔶 by a gate-(a)
    faithfulness audit).** Modeled as `hw/misc/aspeed_ahbc_ast2050.c`: the **AHBC00 write-protection key** is
    now modeled (§12.3: writes to 0x80–0x8C are dropped until `0xAEED1A03` is written to 0x00; read 0x00 = 1
    when unlocked) — the audit correctly flagged that the earlier model let a bare `devmem 0x8C` enable the
    remap without the key, which real silicon rejects; both the model AND the mdmacopy/mictest gates now write
    the key first (still PASS). The AHBC8C[0] **boot-remap** toggles a SoC-created SDRAM alias
    (`dram_low_alias`) at 0x0, **DEFAULT-DISABLED** (reset = static memory), priority above the
    spi_boot_container — this is the path the 28-bit MDMA/MIC engines use to reach DRAM (evidence
    `soc-mdma/02`). Oracle-safe: C2 + C-UBOOT (DRAM Init-DDR → 64 MiB → boot#) both still boot (alias default
    off). **Why 🔶 not ✅ (honest, per the audit):** of the 4 registers, only key + boot-remap are functional;
    AHBC80 priority-arbitration is a no-op in QEMU's flat memory, AHBC88 bus-error IRQ31 is storage-only
    (QEMU emits no AHB bus errors), and AHBC8C[4:5] PCI-host-window remap is stored-only (no PCI host in this
    BMC-only machine) — so it is a partial (boot-remap-focused) model, not full functionality. UQ/US=🔶 (the
    loader drives the remap during DRAM init + boots); L/Z=Ⓝ. C4 vendor oracle re-verify tracked (#200).
  - **50 A2P** (AHB→PCI bridge, 0x1E720000): **QE=🔶 (2026-07-21, #176 — A2P window now modeled).**
    **SRAM/A2P discrepancy RESOLVED (2026-07-20, submodule 4de9aa40c7):** QEMU used to map
    `ASPEED_DEV_SRAM` (a G4 RAM block) at 0x1E720000, but §9 assigns that address to the A2P bridge on the
    G3 — the SRAM phantom is GATED off the G3 (like xdma/sdhci #172). **A2P now EXPLICITLY MODELLED
    (2026-07-21):** read the datasheet §21.2 — A2P is NOT a config-register block but a one-way
    passthrough WINDOW forwarding ARM(AHB) accesses to P-Bus/PCI space (+0x00000..7F relocated I/O,
    +0x10000..0x1FFFF MMIO), auto-enabled by SCU70[4]. In the standalone BMC machine there is NO host/PCI
    on the P-Bus, so the faithful behaviour is a window that reads back 0 / drops writes (forwarding to an
    empty P-Bus). Replaced the accidental IOMEM fall-through with an explicit named
    `aspeed.a2p-pbus-window` unimplemented region (128 KB @0x1E720000), so accesses are logged and the
    address is a correctly-labelled A2P device. **Oracle-revalidated: C2 Linux still boots to userspace
    (rtc0 registered, RTC-LINUX + wakealarm PASS) — no regression.** QE is **🔶 not ✅** because (a) the
    SCU70[4] auto-enable gating is not modelled (window is always present) and (b) forwarding to real
    P-Bus/PCI targets is not exercised (none exist in the BMC-only machine — that would need a modelled
    host). Full ✅ would require the SCU70[4] gate + a P-Bus target for the video-capture read path.
    (C4/C-UBOOT oracles NOT re-run this session — honest limitation; the change is RAZ/WI, minimal risk.)
    **DDC/EDID (row 14) does NOT depend on this** — that is CRTC/VGACRB7 bit-bang in the video register
    space, a separate aperture; the earlier "#178 blocks on #176" note conflated the two. All driver
    stacks Ⓝ (no runtime BMC A2P driver — it is an aperture, not a device with a driver). **Consistency fix (2026-07-20):** row 44 MIC ZQ/ZS Ⓝ→⬜ to match its LQ/LS=⬜ (an
    error-reporter driver is equally plausible/absent on every runtime stack).
    **DOWNSTREAM DEPENDENT (2026-07-20, #178):** this A2P bridge is the aperture through which the BMC
    ARM reaches the PCI "internal VGA" CRTC registers — datasheet §36 l.19634: "AHB to P-bus bridge
    control registers address = 0x1E720000+OFFSET", OFFSET 0x00000-0x0007F = relocated legacy VGA I/O
    (index/data 3B4/3D4→3B5/3D5), 0x10000-0x1FFFF = P-bus MMIO (CRTC MMIOBASE). So **row 14 DDC/EDID
    (VGACRB7) blocks on this A2P model** — the CRTC/DDC registers cannot be reached until the A2P
    forward path exists. Modeling A2P thus unlocks BOTH the P2A backdoor completeness AND the DDC path.

## Roll-up (honest)

- **QEMU emulation**: ✅ for the SoC core + the boot/sensor/power/video/USB/
  fabric set; ⬜ for LPC mailbox/snoop, DDC/EDID, SOL mux, and 6 I2C far-ends.
- **U-Boot**: boot-critical devices ✅ both sides (Raptor); the rest Ⓝ (no
  runtime need). Modern-U-Boot enhancement separate (D15). **Honesty correction
  (2026-07-18 audit): rows 20/27/38 UQ/US Ⓝ/⬜→🔶** — Raptor U-Boot DOES touch the FRU
  EEPROM (I2C ch5 `eeprom=y`), power/reset GPIO (bank-A init, commit 323b3ac), and the
  WDT (`reset.c` reload/restart 0x4755) at boot; those cells understated it. 🔶 not ✅
  because the driver's PRESENCE ≠ device-specific boot-time validation (mark ✅ only with
  a transcript exercising that device under Raptor U-Boot).
- **Linux**: ✅ both sides for the boot/power/sensors/IPMI/eth0/SPD set; the
  open items are NC-SI-silicon (⬜ undone authoring work, NOT externally blocked — matches row 11 LS ⬜), USB-vhub-silicon (🔶),
  SOL (⬜), the 6 I2C far-ends (⬜), DDC/EDID (⬜), MTD-write (⬜), and
  several §11 signals + LED silicon observation.
- **Zephyr**: the D14 port RUNS in QEMU (banner, evidence `d14-zephyr/02`) on the ARM926
  arch core (upstream PR #103557) + authored AST2050 SoC/board + static-mapped console.
  **M1 tickful scheduling VALIDATED (#141, evidence `05`)** — the fix was OUR
  `HW_STACK_PROTECTION`, not upstream. **First per-device driver DONE: AST2050 GPIO
  (#147, `gpio_aspeed_g3.c`) QEMU-VALIDATED** — configure/set/clear/read a pin works
  (evidence `06`); rows 27-29/32-33 ZQ → 🔶. **UPDATE 2026-07-19: Z2 I2C (#148) + Z3 WDT
  (#149) DONE, and 6 Zephyr drivers now boot on the REAL AST2050 silicon over JTAG —
  GPIO/timer/VIC/WDT/I2C/W83795 (w83795_smoke read the real hwmon: fan1≈2631 rpm / temp0≈58.5
  C, live drift). Fixed 4 silicon-only bugs QEMU hid: cache/TLB invalidate, VIC edge-ack +
  level-mask, spurious enable-glitch tick, entry-addr staleness (commits 918bc7e..4cf848d,
  LOG).** Remaining: SB-TSI silicon (needs the host CPU powered); GPIO interrupts (per-bank
  INT regs → VIC); the standard ns16550 console still awaits the separate ARM9 `arm_mmu`
  z_phys_map fix (real, open — unrelated to the tick/cache fixes).

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
| §14 Neighbour chips | QU2/BMC_FW1/U5/LU1-2/QU4/U27-28/U25/QU9/QU5/QU8/QU6/U23/AZ75232/glue U6-8/LDOs/SU1/OU1/NU1 | all active chips have rows; passive glue (U6/U7/U8/U23) modeled in the fabric+power-seq; LDOs = passive power; **SU1/OU1 = host chips reached via LPC/PCI/I2C (rows 3/8/15); NU1 SR5690 = host northbridge — NOT a distinct BMC-driven device and NOT on any BMC I²C bus: its only I²C is a separate SR5690-mastered PCIe-hot-plug SMBus (`DBG_GPIO1/2` → `NB_DEBUG_HEADER1`), which the BMC does not touch (I2C-SMBUS-TOPOLOGY.md §3.8). The BMC's shared I2C3/I2C6 sensor bus reaches only SP5100 + W83795G + the DIMM mux, not the SR5690** |
| §15 Connectors | VGA1/AST_UART1/AST_JTAG1/BMC_FW1/PANEL1/AUX_PANEL1/PSUSMB1/TPM1/VGA_SW1/IPMI_SEL1/RECOVERY1 | VGA1→12, UART1→30, JTAG1→harness, FW1→2, PANEL1→27/32, AUX_PANEL1→26/32, PSUSMB1→24, TPM1→7, jumpers→29/33 |

**Verdict:** the matrix is comprehensive against the authoritative schematic. The
only spec elements without their own driver row are (a) passive power/glue (LDOs,
series-R nets, FET switches, buffers — modeled where they affect behaviour, e.g.
the QU9/QU5/U23 fabric device, not driven), (b) the JTAG header (the silicon test
harness, explicitly Ⓝ), and (c) the host-side chips SU1/OU1/NU1 (reached through
the LPC/PCI/I²C rows, not BMC-internal). Each is justified above, not skipped.

**Gate-(d) round-2 correction (independent sub-agent per-pin sweep, 2026-07-18):**
the audit against the 355-ball pinmap found 6 individual signals the section-level
read had missed, now folded into FULL-TASK-LIST (the authoritative doc): **B1f**
`LPCPD#` (D15), **B1g** `PIKE2` LPC peer `[N]`, **B2** PCI `INTA#`/GPIOB0 (B11),
**E6** unidentified `GPIOE6/E7↔SP5100` (U4/U3), **E6** `ENTEST` (R21) `[N]`, **E6**
`AST_SRST#` (R20) reset-output→PHY. So the "nothing skipped" claim was ~95% true
at the section level but not at the per-pin level — these 6 rows are now explicit
(honestly `[ ]`/`[~]`/`[N]`). See FULL-TASK-LIST B1f/B1g/B2/E6 for the stack cells.

**Support-component completeness (2026-07-20 independent schematic audit).** The audit that
verified device-level completeness (top of file) flagged one schematic-named part not previously
dispositioned anywhere:
- **`CU2` — ICS9112AM-16LFT clock generator** (`pinmaps/QU1_pins.md:198`; 8 pins, 2 nets). It supplies
  the 50 MHz RMII RX reference clocks `C_MNG_50M_AST_RMII1RXCLK`/`RMII2RXCLK` to the BMC MAC RX paths
  (balls A7/B7). **Disposition: folded into rows 10/11 (Ethernet), no dedicated row — justified.** It is
  a fixed-function passive clock source with NO BMC control/configuration interface (the BMC cannot
  program the ICS9112AM; it only receives the clock), so there is no driver to write or emulate for it
  beyond the MAC rows it feeds — exactly like the §2 LDOs (folded into SCU/SDMC). It differs from QOSC1
  (row 34, which *did* get a row) because QOSC1 is the BMC's OWN primary reference consumed by the SCU
  on every boot of every stack, whereas CU2 feeds only the Ethernet interface, so its status is
  subordinate to rows 10/11. If those rows are ever built out, CU2 is validated implicitly (the PHY RX
  path won't work without its clock).
The audit's other flagged items are already dispositioned: **`PIKE2`** (host LPC/SATA mezzanine peer) =
FULL-TASK-LIST **B1g** `[N]`; **`AST_SRST#`/R20** + **`AST_BRST#`/P21** = reset-output nets, FULL-TASK-LIST
**E6**; `ZU1`/FW322, `VGA_HDR1`, glue `U3/U4/NU2` = signals/peers folded into rows 8/12/E6. So every part
the schematic (and the finer pinmap) names now has an explicit home — device rows for devices, FULL-TASK-LIST
per-pin entries for nets/peers, and this note for the one passive clock-gen.

**Non-BMC I²C buses in the board-wide superset (explicitly OUT of this matrix's scope, 2026-07-21
gate-a audit).** `I2C-SMBUS-TOPOLOGY.md` documents three I²C/SMBus/PMBus buses the AST2050 BMC does NOT
electrically touch — they have no `AST_SDA*/SCL*` net and live on other masters, so they are correctly
absent from this BMC device matrix (which scopes to "every device wired to the AST2050", per
`AST2050-BMC-WIRING.md §14`): (a) the **CPU/NB VR PMBus** (`PU2`/`PU7`) on the SP5100's SMBus0 (SVI); (b)
the SP5100 **SMBus3** (unpopulated); and (c) the **FireWire config EEPROM** `ZU2`/HT24LC02 on the FW322
private bus. Recorded here so a reader cross-referencing the topology superset sees them dispositioned,
not silently missing. (The SR5690 PCIe-hot-plug SMBus to `NB_DEBUG_HEADER1` is likewise non-BMC — see the
§14 row.)

**Known register-level sub-block gaps inside ✅ QE cells (gate-d, 2026-07-21).** The device+stack
enumeration is complete (every schematic device has a row), but an independent gate-(d) new-task sweep
found five datasheet-level functional sub-blocks that a "complete emulation of ALL functionality" demands
and that are NOT yet modeled inside otherwise-✅ QE cells. Now tracked as tasks so they are not silently
absent — these keep the affected rows from being TRULY 100% until dispositioned:
- **#187 — RTC alarm (RTC04) + alarm IRQ 26** (row 39): **QE DONE (2026-07-21, submodule 31ea873582,
  evidence `d14-zephyr/16`):** modeled RTC04 + RTC0C[1:4] alarm-enables + a periodic match-check that pulses
  a dedicated alarm IRQ wired to VIC 26; validated (VIC raw bit26 latches when the counter reaches the
  alarm). Linux (rtc-aspeed wakealarm) + Zephyr (rtc alarm API) validation remain. Ties to #158/#186.
- **#188 — I²C SDA bus-lock recovery (§31.5.11)** (row 15): **verified real gap 2026-07-21.** The
  recovery register FIELDS exist in the QEMU model header (`I2CD_INTR_STS.BUS_RECOVER_DONE` bit13, engine
  state `I2CD_RECOVER=0x3`, `FUN_CTRL.M_SDA_LOCK_EN`/`M_SCL_DRIVE_EN`, `SDA_OE`/`SCL_OE`/`SDA_LINE_STS`/
  `SCL_LINE_STS`) but are NEVER processed in `hw/i2c/aspeed_i2c.c` — nothing sets `BUS_RECOVER_DONE`, so a
  driver that runs §31.5.11 SCL-toggle recovery (after a stuck-SDA timeout) would never see completion.
  SCOPE: on a recovery trigger set `BUS_RECOVER_DONE` (QEMU has no real stuck SDA → recovery always
  "succeeds") + drive `SDA/SCL_LINE_STS` idle-high. NOTE: shared upstream code (AST2400/2500/2600 must stay
  unaffected) on an I²C ERROR PATH (mainline `i2c-aspeed` only calls recover_bus on a timeout, which the
  clean QEMU bus never hits) — so firmware-rarely-exercised, validate SYNTHETICALLY via devmem (trigger
  recover, read BUS_RECOVER_DONE). A careful standalone item, not a rushed context-tail change.
- **#189 — WDT timeout-INTERRUPT mode (WDT0C[2]/WDT18)** (row 38): **QE DONE (2026-07-21, submodule
  46cee5fe6a, evidence `f-wdt-userspace/01`):** added an IRQ to the WDT model; at expiry, if WDT_CTRL[2]
  is set the WDT PULSES its IRQ (wired to VIC 27) instead of resetting; reset path UNCHANGED when the bit
  is clear (proven — wdtreset still resets). Validated (VIC raw bit27 latches in interrupt mode). Remaining:
  WDT18 reset-assert-WIDTH + Linux/Zephyr exercising interrupt mode (both use reset mode today, low-pri).
- **#190 — I²C buffer-pool/DMA-buffer transfer modes (§31.5.2/3/9)** (row 15): **verified + rescoped
  2026-07-21.** BUFFER-POOL is ALREADY MODELED (the gate-d "byte-only" premise was wrong): the G3
  aspeed_i2c class sets `has_share_pool=true`/`pool_size=0x800` and the model does functional pool TX/RX
  (`hw/i2c/aspeed_i2c.c`, pool_tx_count/pool_rx_count send+recv) — row 15 QE covers byte AND buffer-pool.
  DMA-buffer is a genuine but firmware-UNEXERCISED gap: §31.5.9 "DMA Buffer Mode" + the REQ21 "I2C DMA
  buffer mode" line confirm the AST2050 I²C HAS DMA, but the G3 model has `has_dma=false` (DMA regs log
  "No DMA support") and NO board firmware uses it (U-Boot/Linux-mainline/Zephyr are all byte/pool). #190
  stays OPEN, narrowed to: RE the AST2050 I²C-DMA register mechanism (the modeled AST2500 has_dma path, or
  an older one?), model it, validate with a synthetic DMA test. LOW priority (unexercised) but NOT Ⓝ.
- **#191 — SCU freq-counter (SCU10/14/28) + int ctrl/status (SCU18) + 32.768 kHz error-correction (SCU1C)**
  (row 35): **verified + dispositioned 2026-07-21.** SCU1C is ALREADY MODELED (the gate-d flag was a
  header-name mis-read): the G3 SCU reset table `ast2050_a3_resets` (hw/misc/aspeed_scu.c:228) seeds it
  0x1B with the datasheet citation "SCU1C = 32.768kHz err-correct p211" — the faithful G3 value + meaning,
  distinct from the header's AST2400 `D2PLL_PARAM` name. The freq-counter (SCU10/14/28) + IRQ_CTRL (SCU18)
  are register-level BACKING STORE (read-only EVAL returns the reset seed); their FUNCTIONAL behaviour
  (a live clock-measurement count; SCU interrupt generation) is unmodeled but FIRMWARE-UNEXERCISED — the
  freq counter is a PLL-lock diagnostic and SCU interrupts are unused at boot by U-Boot/Linux/Zephyr on
  this board. Dispositioned like PECI/HACE (present, modeled-but-unused-fn → reasoned): the boot-exercised
  SCU functionality (clock/reset/pinmux/PLL/silicon-rev/strap, row 35 QE/ZS ✅) is complete; functional
  freq-counter/SCU-IRQ modelling is an OPTIONAL low-value "all-functionality" follow-on, not a boot gap.
These are register-level completeness items, not device-enumeration gaps; the schematic→device coverage
above is unaffected.

# BMC functionality — honest QEMU vs real-silicon status

Last updated 2026-07-18 (D07/D08 landed; see banners), reconciled against FOUR **independent skeptical reviews** of
branch `claude/bmc-functionality` (the second re-ran the USB F6 test both ways and
confirmed the vhub QEMU verification live; the third traced the feature-1 power
fixes down to the `gpio-aspeed.c` dcache/bank mechanics and confirmed the QEMU
`F2 RESULT: PASS` is substantiated + silicon-safe). The **fourth was a comprehensive
completion audit**: it re-verified all four PASS/PASS features against the committed
evidence and adversarially challenged the four "impossible" determinations against
the datasheet — and CORRECTING
#8's reasoning (the AST2050 SoC *does* have host-flash-master paths — LPC-Master/FWH
+ a spare SMC CE; the real blocker is KGPE-D16 board wiring, not a SoC absence).
> **2026-07-16 UPDATE — the count is now 6/9, not 4/9.** #2 (connect USB devices) and
> #3b (send keyboard events) are **BOTH-sides PASS**. The USB/IP host-enumeration
> harness closed the "QEMU can't model the host" gap (two-VM `USBIP-HOST RESULT: PASS`),
> and the **real AST2050** was brought up over JTAG (reset halt → DDR2 train → U-Boot →
> netboot the `USBIP_VUDC` kernel) so a **real physical host (the RPi4 bridge)
> enumerated the real board's virtual keyboard + disk** — reading the mass-storage
> magic off `/dev/sda` and receiving `EV_KEY KEY_A` on its evdev
> (`evidence/real-hw-usb/02-SILICON-USB-ENUMERATION-PASS.txt`). The earlier
> "#2 is USB-host-impossible" framing was wrong twice over: the feature is the
> *gadget* direction (the AST2050 has exactly the right silicon for it), and the
> enumeration gap was a software-harness problem, not a hardware limit.

> **2026-07-18 UPDATE — #5 DIMM inventory is now demonstrated on silicon.**
> The BMC read the real DIMM's 256-byte SPD over its own I2C2 engine through
> the QU9/QU5 mux fabric (`at24 15-0051`, part `RMR5030EF68F9W1600`, CRC
> 0xf0b4 == host `dmidecode`; `evidence/d08-spd-silicon/`). The old "SPDs on
> the host SMBus, not a BMC bus" verdict was wrong: the BMC's I2C2 reaches the
> DIMM SPD through the netlist-traced QU9/QU5/U23 fabric. On this
> flash-socket-empty rig the SP5100 owns the mux selects (BMC_PRESENT# high),
> so the mux was pointed at bank Y2 from the SP5100 side; the BMC's SPD data
> path is identical to a production board where the BMC (BMC_PRESENT# low)
> drives the selects itself. QEMU carries the exact SPD and models the full
> fabric (see `device-driver-program/` D08).

Those corrections are folded in below. This is the candid ground
truth, not a summary of claims. Legend: ✅ demonstrated · ◐ partial/scoped · ✋ architecturally
bounded (cannot be fully delivered on this board) · ✗ not yet on this target.

**Bottom line (independent-review verdict):** strictly "demonstrated in BOTH QEMU
AND on real silicon", the full PASS/PASS features are **#1 power on/off (host
power on/off/reset via the `kgpe-power.sh` GPIO path — QEMU `F2 RESULT: PASS`,
silicon plug-verified; the fully-automated Redfish→op-pwrctl loop is the only
open sub-case, #95), #4 sensors, #7 IPMI (local KCS + remote LAN), and #3a VGA
screen capture**. The rest are partial,
rig-blocked, or architecturally impossible on this SoC/board (see per-row notes):
**four features can never be fully delivered here** — #8 host-BIOS flash (**not
wired on the KGPE-D16**: the board's BIOS SPI hangs off the AMD SB, not on any
BMC-mastered bus — see the #8 row for the datasheet correction; the AST2050 is
*not* categorically without a host-flash path; schematic-confirmed 2026-07-18:
FU1 is on the SP5100 SPI controller with no shared node with any `AST_SPI*`
net), ~~#9 true NC-SI~~ (**REOPENED 2026-07-18 as D07** — the earlier "not
wired" verdict was MAC1-scoped; schematic §7 shows MAC2's RMII2 is a multi-drop
NC-SI sideband to BOTH 82574L NICs, aux-powered; see the #9 row and F7-NCSI.md's
correction), #2's USB-*host* side (device-only controller — no EHCI/OHCI on the
SoC), and ~~#5's DIMM/memory inventory~~ (**REOPENED and now IMPLEMENTED as
D08** — the SPDs are reachable from BMC I2C2 through the QU9/QU5/U23 fabric
while host power is on; QEMU full-stack PASS 2026-07-18, silicon run pending;
see `schematic-wiring/I2C-MUX-FABRIC-ARBITRATION.md`).
So "all nine on both QEMU and silicon" is not achievable on this hardware; this
doc is the honest map of what is, what's pending, and what cannot be delivered on
this board (with the reason stated per row — a board-wiring limit vs a SoC limit).

| # | Requested feature | QEMU | Silicon | Honest note |
|---|---|---|---|---|
| 1 | Power on/off | ✅\* | ✅ | **Host power on/off/reset demonstrated on BOTH sides via the same BMC power script `kgpe-power.sh`** (the one hardware-proven on silicon 2026-07-13: `on` → plug 3W→103W + GPIOH2=1 + host PXE-boots; `off` → 103W→4W). **QEMU now PASSES all of init/on/off/on/reset** (`f2-power-control-test.py --driver sysfs`): the guest's in-band GPIOH2 devmem read and the modeled QMP `gpioH2` agree on every step (`F2 RESULT: PASS`; evidence `evidence/qemu/f2-power-sysfs-onoffreset-PASS.txt`). The earlier "QEMU power-ON doesn't latch" was a **phantom — three non-model causes** (all fixed 2026-07-16): (1) the `--driver sysfs` test ran `kgpe-power.sh` *without stopping op-pwrctl*, which held B1/F0/B6 via libgpiod → the script's sysfs export EBUSY'd → the B1 pulse was skipped (the real `obmc-power-{start,stop}@` drop-ins stop op-pwrctl around each pulse; the test now does too); (2) a harness console-sync bug (laggy 256 MB console + TTY-echoed end-marker) lagged the QMP read by a step; (3) a real latent glitch — `setup_lines` drove GPIOF0 (active-low force-off) momentarily low via `direction=out;value 1`, clearing the latch on warm reset (fixed with atomic `direction=high`). The model (`hw/gpio/aspeed_gpio.c` `kgpe_d16_pwrseq`) was correct all along and the `test_power` pytest already validated the latch. **The fully-automated Redfish path also now CONTROLS power in QEMU** (`--driver redfish`, `evidence/qemu/f2-power-redfish-integrated-README.md`): a Redfish `ComputerSystem.Reset` → phosphor-state-manager → `obmc-power-start@0` → the board **drop-in** → `kgpe-power.sh` → GPIO, with the modeled `gpioH2` tracking all four actions (On→True, ForceOff→False, On→True, ForceRestart→True). The #95 "op-pwrctl doesn't drive A4" framing was superseded: power-on rides the `obmc-power-{start,stop}@.service.d/kgpe.conf` drop-ins (installed by the recipe; a stale test export had lacked them), NOT op-pwrctl's held-level drive. **Remaining (telemetry only):** on a hard `ForceOff` the Redfish *Systems* `PowerState` string lingers at `PoweringOff` (host TransitioningToOff) though the hardware is off (gpioH2=False) — an artifact of no real host in QEMU, not a control failure. The Redfish **PowerState readback** null bug is also FIXED (64 MB bmcweb OOM; `evidence/qemu/f2-power-256mb-readback.txt`). |
| 2 | Connect USB devices | ✅ | ✅ **SILICON PASS** | QEMU: the faithful udc model now **reproduces the silicon hang** — the unfixed mainline driver **livelocks** (F6 FAIL), and the G3-ported driver (**patch 0007**: PHY-ready gate + ISR[18] de-livelock + `ast2050-usb-vhub`) **probes cleanly** (7 ports, gadget enumerates, F6 PASS). So the vhub hang is root-caused and the fix is verified against a hang-reproducing model (`VHUB-G3-PORT-PLAN.md`). Silicon: enabling the vhub hangs the mainline driver (`usb-vhub-silicon-boundary.txt`); the fixed-kernel retest is **rig-blocked** (P2A load degrades after ~15 boot cycles). **🎉 BOTH SIDES PASS (2026-07-16, `F6-USB-HOST.md` + `USB-REAL-HW-VERIFICATION.md`).** The "enumeration needs a host QEMU can't model" gap is CLOSED with USB/IP — the BMC exports its configfs gadget (HID keyboard + mass-storage) via `usbip-vudc`, and an independent host imports it with `vhci-hcd`. **QEMU:** two-VM test `USBIP-HOST RESULT: PASS` — a second qemu-system-x86_64 host enumerates it, reads `/dev/sda` offset 512 = `KGPE-D16-USBIP-VMEDIA-OK`, and receives `EV_KEY KEY_A` (`evidence/f6-usb-host/03-…`; CI job `boot-usbip-host`). **SILICON:** brought the real AST2050 up over JTAG (reset halt → DDR2 trained, MCR04 0x585 → U-Boot @`boot#` → TFTP my `USBIP_VUDC` kernel → Linux 6.6.70), and the **real RPi4 bridge enumerated the real board's gadget**: `usb 3-1: Product: AST2050 vKVM export (usbip)`, `hid-generic: USB HID v1.01 Keyboard`, `usb-storage: Mass Storage device detected`; **`/dev/sda` offset512 = `KGPE-D16-USBIP-VMEDIA-OK`** and **`/dev/input/event4` = `01 00 1e 00` (EV_KEY KEY_A)** (`evidence/real-hw-usb/02-SILICON-USB-ENUMERATION-PASS.txt`). Honest scope: the gadget binds the `usbip-vudc` UDC, so this proves the gadget/descriptor/enumeration + data + HID path on real silicon against a real host; it does **not** exercise the AST2050 vhub's own EP-DMA datapath (patch-0007's separate job — Test B, needs the board's USB port cabled to a host). |
| 3a | See virtual VGA screen | ✅ | ✅ | QEMU: real frame → `/dev/video0` → JPEG, 8 bars pixel-verified. Silicon: `/dev/video0` frame `bytesused=28418` (kernel-wrapped) decodes directly to the host's live screen. Evidence: `evidence/real-hw-video/silicon-f8capture-transcript.txt` + `silicon-direct-jpeg.png`. |
| 3b | Send keyboard events | ✅ | ✅ **SILICON PASS** | Rides the #2 USB/IP gadget path (the export gadget includes the HID boot keyboard). **QEMU:** a BMC `/dev/hidg0` write arrives on the second x86 guest's evdev as `EV_KEY KEY_A` (`01 00 1e 00 01 00 00 00`). **SILICON:** the real AST2050's keypress loop is delivered to the **real RPi4 host**: `hid-generic ... USB HID v1.01 Keyboard [ASUS-KGPE-D16-BMC AST2050 vKVM export]`, `/dev/input/event4` → `01 00 1e 00 ..` = `EV_KEY KEY_A` (`evidence/real-hw-usb/02-…`). Same honest scope as #2 (usbip-vudc UDC, not the vhub datapath). |
| 4 | Full sensors | ✅ | ✅ | QEMU: W83795G model → 23 sensors over IPMI. Silicon: 18 live sensors over LAN **and** host-KCS — FAN1 2700 RPM, CPU_DIODE 52.12 °C, P12V 13.76 V, rails, VBAT (`evidence/real-hw-consolidated/`). Confirms the G3 i2c-timing (0005) + W83795 hwmon (0003) patches on silicon. |
| 5 | System identification | ✅ | ✅ | Unique IDs + board FRU proven both sides (mc info 2623 / 0x0d16; FRU ASUSTeK KGPE-D16, serial, PN). **DIMM inventory now DEMONSTRATED (2026-07-18, D08):** the earlier "no DIMM SPDs at 0x50-0x57 → unreachable by the BMC" conclusion was WRONG — it scanned only bus 1 and missed the QU9/QU5 mux fabric. The BMC read the real DIMM's 256-byte SPD over its own I2C2 through the fabric (`at24`, part RMR5030EF68F9W1600, CRC 0xf0b4; `evidence/d08-spd-silicon/`). **Honest scope of the silicon read:** the mux was pointed at bank Y2 from the SP5100 side because this flash-socket-empty rig holds `BMC_PRESENT#` high (U23 gives the SP5100 select-ownership) — the BMC's SPD **data path** is proven; on a production board (BMC_PRESENT# low) the BMC drives the selects itself. QEMU carries the exact SPD and models the fabric. |
| 6 | Serial-over-LAN | ✅\* | ◐ | QEMU: faithful VUART, host serial **byte-flow** captured (via `obmc-console-client` reading the VUART). `ipmitool sol activate` is not a full SOL-session capture — but the **provider gap is now RESOLVED**: on the recipe-built image the `xyz.openbmc_project.Ipmi.SOL` object IS present (busctl `GetObject` rc=0, owned by `xyz.openbmc_project.Settings`; `evidence/qemu-sol/sol-provider-present-recipe-image.txt`), delivered by the settings SOL recipe (now wired into the asset build). The `sol activate` blocker has since been walked down: RMCP+ RAKP session-auth is now reliable (`-N 5 -R 3`, `sol payload status` rc=0 enabled), the provider is present, and the *current* residual is netipmid **"Failed to get service path in registerSOLService"** — a netipmid↔obmc-console service-registration binding issue, not RAKP/provider/data-path (the harness auto-detects a TRUE SOL session once it's closed). Silicon: SOL is *configured + enabled* (`sol info` rc=0) but no host serial **bytes** carried. **CORRECTION (2026-07-21 schematic audit): this is NOT a board-wiring limit** — schematic `../../schematic-wiring/AST2050-BMC-WIRING.md` §12 shows the host serial IS wired to the BMC: AST2050 **UART1** → **QU8** (Pericom PI5C3257 2:1 mux) → Super-I/O UART-B, gated by `AST_SOLEN#`, selected by `BMC_PRESENT#`. Two real constraints, neither a wiring absence: (a) the board's SOL path is **UART1+QU8**, not the LPC VUART this OpenBMC image models; (b) on this flash-socket-empty rig `BMC_PRESENT#` is held HIGH, so QU8 hands the console to the host RS-232 side instead of the BMC's UART1 (a rig-population/strap condition — same `BMC_PRESENT#`-high cause as the DIMM #5 note). |
| 7a | IPMI over LAN (remote) | ✅ | ✅ | Full `ipmitool -I lanplus` suite rc=0 both sides; silicon real MAC + populated IDs (`evidence/real-hw-consolidated/`). **QEMU IDs now also verified POPULATED on the kgpe-d16 image** (`openbmc-img2`): `mc info` → Manufacturer 2623/ASUSTek, Product 0x0d16, FRU KGPE-D16 — matching silicon (`evidence/qemu-ipmi-kgpe-image/`), closing the audit's "QEMU LAN answers with zeros" soft-spot (the zeros were the generic-asset artifact). Also hardened the LAN test against RMCP+ RAKP slowness (`-N 5 -R 3`) so it no longer flakes. |
| 7b | IPMI host-local (KCS) | ✅\* | ✅ | Silicon: **x86 host** `ipmitool -I open` over real LPC KCS → `Found new BMC (0x0d16)`, mc info + FRU rc=0. QEMU: host Get Device ID answered through the modeled KCS state machine. |
| 8 | Update firmware / BIOS | ◐ | ✗ | QEMU: Redfish `UpdateService` ingest surface (POST → HTTP 202 async Task + phosphor-software-manager). No activation / MTD write / BIOS path. **BIOS update is not achievable on the KGPE-D16 — a BOARD-wiring limit, corrected 2026-07-16 (audit).** The earlier "AST2050 has no host-SPI master (that's AST2400+)" reasoning was **wrong at the SoC level**: the AST2050 datasheet documents (a) an **LPC Master mode explicitly for host-BIOS/FWH flash update** (§2.20 p34; regs `LHCR0–LHCRB`, `HICR5[10] ENFWH` — see `qemu-model/peripherals/lpc/DATASHEET-LPC.md` §7) and (b) a **write-capable SMC SPI master with a spare chip-select** (§2.8; `SMC00` per-CE write-enable, `SMC04` user-mode writes). So the SoC *has* host-flash-master paths; what the AST2400+ adds is a *dedicated* host-SPI master + flash-mux (turnkey). The real blocker is that the **KGPE-D16's BIOS SPI hangs off the AMD SB**, not on any BMC-mastered LPC/FWH bus or spare SMC CE, so the BMC cannot reach it on THIS board. **BMC self-update** (the in-scope half) is architecturally possible via the SMC writing the BMC's own SPI, but is **not yet demonstrated** (only the Redfish upload endpoint exists — no MTD write). |
| 9 | Piggyback host NIC | ◐ | ◐ | **REOPENED (D07), 2026-07-18** — the earlier "true NC-SI host-NIC sharing is architecturally ABSENT" verdict was **MAC1-scoped and is superseded**: the schematic netlist (`../../schematic-wiring/AST2050-BMC-WIRING.md` §7) confirms **MAC channel 2's RMII2 (balls A5/B5/B6/C4/D4/D5) IS wired as a multi-drop NC-SI sideband to BOTH Intel 82574L NICs (LU1/LU2)**, 50 MHz REF from clockgen CU2, NICs on +3V3_AUX (fabric doc §5 — so testable with the host off). **Progress (D07):** QEMU MAC2 wired + Linux `net/ncsi` discovers a channel in emulation (`NCSI RESULT: PASS`, `evidence/d07-ncsi/00-...`); the real 82574L NVMs are confirmed **NC-SI-enabled** (MNGM=01, packages 0/1; `evidence/d07-ncsi/01-silicon-82574L-nvm-...` — a HOST-side `ethtool -e` dump, NOT a BMC-side discovery). **Still to do:** the faithful 82574L responder (2 packages, Intel OEM mfr 0x157) and **BMC-side NC-SI discovery ON SILICON has not yet been run**. Still true: MAC1 uses a dedicated RTL8201-family PHY, and the BMC is reachable on the shared physical network (both sides). |

`\*` = passes on the faithful/honest interpretation with the scoping caveat noted.

## Solidly on silicon (this program's real wins)
- Remote IPMI over LAN; host-local IPMI over real LPC KCS from the x86 host.
- 18 live sensors (fan RPM / temps / voltage rails) over both LAN and KCS.
- Video capture: host VGA → `/dev/video0` → **kernel-wrapped, directly-decodable JPEG**
  (this session's patch 0006; `bytesused=28418` transcript-proven).
- Board FRU / unique-ID identification; BMC reachable on the shared network.

## Genuinely open, in priority order (simplest first)
1. **SOL host byte-flow on silicon** — the host serial IS wired to the BMC (UART1→QU8→Super-I/O,
   schematic §12); the work is (a) drive SOL over the board's UART1+QU8 path (not the LPC VUART the
   image models) and (b) get QU8 to select the BMC — which needs `BMC_PRESENT#` low (a populated
   flash socket), since the empty-socket rig holds it high and hands the console to the host RS-232 side.
2. **Integrated power-ON via Redfish** — DONE in QEMU (the `obmc-power-start@` drop-in →
   `kgpe-power.sh` makes Redfish On/ForceOff/On/ForceRestart drive `gpioH2` correctly;
   `evidence/qemu/f2-power-redfish-integrated-README.md`). Only follow-up: the Redfish
   Systems `PowerState` *string* settling to `Off` on a hard OFF (host-state telemetry,
   needs a real host to observe host-down — not observable BMC-only in QEMU).
3. **Host-facing USB (device + HID keyboard) on silicon** — drive the aspeed-vhub UDC to
   present a gadget to the host and confirm host enumeration / keystroke delivery.
4. **Memory/hardware inventory** — needs **host SMBIOS ingestion** (host → BMC over IPMI):
   `i2cdetect` on silicon (bus 1 only, so far) shows the DIMM SPDs are NOT on that BMC
   I2C bus, so this cannot be a BMC-side I2C read on the KGPE-D16. Follow-ups: scan all 7
   BMC I2C engines to firm up the claim; add `smbios-mdr` to the image (absent today).

### Audit-surfaced QEMU-only advances (deepen a demo; do NOT create new both-sides passes)
5. **True SOL session in QEMU** — the `xyz.openbmc_project.Ipmi.SOL` provider recipe already
   EXISTS and IS present on the recipe-built image (busctl-confirmed 2026-07-16), so this is
   NOT a missing-provider gap. The residual is RMCP+ **RAKP session-auth reliability** on the
   slow 256 MB board (same as the lanplus suite); a streaming `sol activate` test would be
   flaky and is intentionally not added. QEMU already proves the SOL byte-flow via
   `obmc-console-client`. (Silicon SOL stays rig-blocked — the host serial IS wired to the BMC via
   UART1/QU8 per §12, but the empty-socket `BMC_PRESENT#`-high strap makes QU8 select the host RS-232
   side, not the BMC's UART1; not a board-wiring absence.)
6. **BMC self-firmware-update in QEMU** — architecturally possible (the SMC SPI master can
   write the BMC's own flash: `SMC00` write-enable + `SMC04` user-mode writes) but today only
   the Redfish upload endpoint exists (no MTD write/activation). Would need the QEMU SMC model
   to accept flash writes + phosphor-software-manager activation. (Silicon needs a flash-resident
   BMC; the rig boots over NFS, so this is a QEMU-side deepening only.)

## Architecturally bounded (cannot be fully delivered on the AST2050 / KGPE-D16)
- **Host BIOS flashing** — not wired on the KGPE-D16 (its BIOS SPI is on the AMD SB,
  not on a BMC-mastered bus). NB: the AST2050 SoC *does* have host-flash-master paths
  (LPC Master/FWH update §2.20; write-capable SMC with a spare CE) — this is a
  board-wiring limit, not a SoC absence (corrected per the 2026-07-16 audit).
- ~~**True NC-SI host-NIC sharing** — board wires a dedicated PHY and straps MII/RMII
  only; the SoC MAC can do NC-SI but this board does not route it.~~
  **⚠️ WITHDRAWN 2026-07-18 — no longer architecturally bounded.** That verdict
  only examined MAC1 (the RTL8201 dedicated PHY). The schematic
  (`schematic-wiring/AST2050-BMC-WIRING.md` §7) shows MAC2's RMII2 balls are a
  multi-drop NC-SI sideband to BOTH Intel 82574L NICs (LU1/LU2, on +3V3_AUX,
  50 MHz REF from clockgen CU2), and the 82574L datasheet confirms DMTF NC-SI
  1.0.0a over RMII (NVM-selected). Now task **D07** in
  `device-driver-program/TASKLIST.md`.
- **USB host** — the AST2050 has only a USB *device/gadget* controller (no EHCI/OHCI;
  datasheet feature table lists "USB 1.1 Controller = No").

## Rig-fidelity caveat
All silicon results run on a BMC booted into volatile DRAM over P2A (no boot flash), whose
DRAM is shared with the host VGA framebuffer — so the bench BMC can wedge ~1 min after host
POST and the P2A boot degrades after many cycles. The results are genuine but on a fragile
bench setup; a flash-resident BMC would be immune. See `evidence/real-hw-consolidated/README.md`.

# BMC functionality — honest QEMU vs real-silicon status

Last updated 2026-07-16, reconciled against FOUR **independent skeptical reviews** of
branch `claude/bmc-functionality` (the second re-ran the USB F6 test both ways and
confirmed the vhub QEMU verification live; the third traced the feature-1 power
fixes down to the `gpio-aspeed.c` dcache/bank mechanics and confirmed the QEMU
`F2 RESULT: PASS` is substantiated + silicon-safe). The **fourth was a comprehensive
completion audit**: it re-verified all four PASS/PASS features against the committed
evidence and adversarially challenged the four "impossible" determinations against
the datasheet — confirming the 4/9 count and that #2/#9/#5 are sound, and CORRECTING
#8's reasoning (the AST2050 SoC *does* have host-flash-master paths — LPC-Master/FWH
+ a spare SMC CE; the real blocker is KGPE-D16 board wiring, not a SoC absence).
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
*not* categorically without a host-flash path), #9 true NC-SI (**not wired on this
board** — dedicated RTL8201CP PHY; the SoC MAC can do NC-SI but the board straps
MII/RMII only), #2's USB-*host* side (device-only controller — no EHCI/OHCI on the
SoC), and #5's DIMM/memory inventory (SPDs on the host SMBus, not a BMC I2C bus).
So "all nine on both QEMU and silicon" is not achievable on this hardware; this
doc is the honest map of what is, what's pending, and what cannot be delivered on
this board (with the reason stated per row — a board-wiring limit vs a SoC limit).

| # | Requested feature | QEMU | Silicon | Honest note |
|---|---|---|---|---|
| 1 | Power on/off | ✅\* | ✅ | **Host power on/off/reset demonstrated on BOTH sides via the same BMC power script `kgpe-power.sh`** (the one hardware-proven on silicon 2026-07-13: `on` → plug 3W→103W + GPIOH2=1 + host PXE-boots; `off` → 103W→4W). **QEMU now PASSES all of init/on/off/on/reset** (`f2-power-control-test.py --driver sysfs`): the guest's in-band GPIOH2 devmem read and the modeled QMP `gpioH2` agree on every step (`F2 RESULT: PASS`; evidence `evidence/qemu/f2-power-sysfs-onoffreset-PASS.txt`). The earlier "QEMU power-ON doesn't latch" was a **phantom — three non-model causes** (all fixed 2026-07-16): (1) the `--driver sysfs` test ran `kgpe-power.sh` *without stopping op-pwrctl*, which held B1/F0/B6 via libgpiod → the script's sysfs export EBUSY'd → the B1 pulse was skipped (the real `obmc-power-{start,stop}@` drop-ins stop op-pwrctl around each pulse; the test now does too); (2) a harness console-sync bug (laggy 256 MB console + TTY-echoed end-marker) lagged the QMP read by a step; (3) a real latent glitch — `setup_lines` drove GPIOF0 (active-low force-off) momentarily low via `direction=out;value 1`, clearing the latch on warm reset (fixed with atomic `direction=high`). The model (`hw/gpio/aspeed_gpio.c` `kgpe_d16_pwrseq`) was correct all along and the `test_power` pytest already validated the latch. **The fully-automated Redfish path also now CONTROLS power in QEMU** (`--driver redfish`, `evidence/qemu/f2-power-redfish-integrated-README.md`): a Redfish `ComputerSystem.Reset` → phosphor-state-manager → `obmc-power-start@0` → the board **drop-in** → `kgpe-power.sh` → GPIO, with the modeled `gpioH2` tracking all four actions (On→True, ForceOff→False, On→True, ForceRestart→True). The #95 "op-pwrctl doesn't drive A4" framing was superseded: power-on rides the `obmc-power-{start,stop}@.service.d/kgpe.conf` drop-ins (installed by the recipe; a stale test export had lacked them), NOT op-pwrctl's held-level drive. **Remaining (telemetry only):** on a hard `ForceOff` the Redfish *Systems* `PowerState` string lingers at `PoweringOff` (host TransitioningToOff) though the hardware is off (gpioH2=False) — an artifact of no real host in QEMU, not a control failure. The Redfish **PowerState readback** null bug is also FIXED (64 MB bmcweb OOM; `evidence/qemu/f2-power-256mb-readback.txt`). |
| 2 | Connect USB devices | ✅ (fix QEMU-proven) | ✗ working / ◐ hang-only | QEMU: the faithful udc model now **reproduces the silicon hang** — the unfixed mainline driver **livelocks** (F6 FAIL), and the G3-ported driver (**patch 0007**: PHY-ready gate + ISR[18] de-livelock + `ast2050-usb-vhub`) **probes cleanly** (7 ports, gadget enumerates, F6 PASS). So the vhub hang is root-caused and the fix is verified against a hang-reproducing model (`VHUB-G3-PORT-PLAN.md`). Silicon: enabling the vhub hangs the mainline driver (`usb-vhub-silicon-boundary.txt`); the fixed-kernel retest is **rig-blocked** (P2A load degrades after ~15 boot cycles). **Host-enumeration harness (NEW 2026-07-16, `F6-USB-HOST.md`):** the "enumeration needs a host QEMU can't model" gap is being closed with USB/IP — the BMC exports its configfs gadget via `usbip-vudc` to a second qemu-system-x86_64 guest. BMC-export half is **runtime-PASS in QEMU** (`usbiphost` gate: gadget binds `usbip-vudc.0`, static-ARM `usbipd` listens :3240, LUN medium attached — `evidence/f6-usb-host/01-…`); the static-libudev cross-build crux is solved (`00-…`) and the x86 client blocks build (`02-…`). This is the UDC-agnostic function/enumeration test, **complementary** to the patch-0007 faithful-vhub probe (a gadget binds one UDC at a time). Remaining: x86-guest initramfs + two-VM runner + CI (QEMU); fresh-boot silicon retest of patch 0007 + physical host wiring (silicon). |
| 3a | See virtual VGA screen | ✅ | ✅ | QEMU: real frame → `/dev/video0` → JPEG, 8 bars pixel-verified. Silicon: `/dev/video0` frame `bytesused=28418` (kernel-wrapped) decodes directly to the host's live screen. Evidence: `evidence/real-hw-video/silicon-f8capture-transcript.txt` + `silicon-direct-jpeg.png`. |
| 3b | Send keyboard events | ◐ | ✗ | QEMU: the `dummy_hcd` loopback delivers `EV_KEY/KEY_A` to the BMC's *own* evdev (not a foreign host). The **USB/IP host-enumeration harness (#2, `F6-USB-HOST.md`)** rides the same gadget path — the export gadget includes the HID keyboard, so once the x86-guest client lands, a `/dev/hidg0` write is delivered to an *independent* host's evdev. BMC-export half is runtime-PASS; x86 client de-risked. Silicon: none (same host-facing path as #2). |
| 4 | Full sensors | ✅ | ✅ | QEMU: W83795G model → 23 sensors over IPMI. Silicon: 18 live sensors over LAN **and** host-KCS — FAN1 2700 RPM, CPU_DIODE 52.12 °C, P12V 13.76 V, rails, VBAT (`evidence/real-hw-consolidated/`). Confirms the G3 i2c-timing (0005) + W83795 hwmon (0003) patches on silicon. |
| 5 | System identification | ◐ | ◐ | Unique IDs + board FRU proven both sides (mc info 2623 / 0x0d16; FRU ASUSTeK KGPE-D16, serial, PN). **Gap:** no DIMM / CPU / memory-config inventory. `i2cdetect` on silicon (`evidence/real-hw-consolidated/bmc-i2c-topology-silicon.txt`) shows the BMC bus has the W83795 (0x2f) but **no DIMM SPDs at 0x50-0x57** — the SPDs are on the host memory SMBus, unreachable by the BMC. Memory inventory would need host SMBIOS ingestion, not a BMC I2C read. **Evidence caveat (audit 2026-07-16):** that `i2cdetect` scanned only **bus 1** of the AST2050's **7 I2C engines**; the "no SPDs on a BMC bus" conclusion is plausible for this board but under-evidenced — a firmer claim would scan all reachable engines (follow-up). Also note the OpenBMC image ships **no `smbios-mdr` service**, so even the host-SMBIOS path isn't in the current build. |
| 6 | Serial-over-LAN | ✅\* | ◐ | QEMU: faithful VUART, host serial **byte-flow** captured (via `obmc-console-client` reading the VUART). `ipmitool sol activate` is not a full SOL-session capture — but the **provider gap is now RESOLVED**: on the recipe-built image the `xyz.openbmc_project.Ipmi.SOL` object IS present (busctl `GetObject` rc=0, owned by `xyz.openbmc_project.Settings`; `evidence/qemu-sol/sol-provider-present-recipe-image.txt`), delivered by the settings SOL recipe (now wired into the asset build). The `sol activate` blocker has since been walked down: RMCP+ RAKP session-auth is now reliable (`-N 5 -R 3`, `sol payload status` rc=0 enabled), the provider is present, and the *current* residual is netipmid **"Failed to get service path in registerSOLService"** — a netipmid↔obmc-console service-registration binding issue, not RAKP/provider/data-path (the harness auto-detects a TRUE SOL session once it's closed). Silicon: SOL is *configured + enabled* (`sol info` rc=0) but no host serial **bytes** carried — the host COM console is not wired to the AST2050 VUART on this board (a board-wiring limit). |
| 7a | IPMI over LAN (remote) | ✅ | ✅ | Full `ipmitool -I lanplus` suite rc=0 both sides; silicon real MAC + populated IDs (`evidence/real-hw-consolidated/`). **QEMU IDs now also verified POPULATED on the kgpe-d16 image** (`openbmc-img2`): `mc info` → Manufacturer 2623/ASUSTek, Product 0x0d16, FRU KGPE-D16 — matching silicon (`evidence/qemu-ipmi-kgpe-image/`), closing the audit's "QEMU LAN answers with zeros" soft-spot (the zeros were the generic-asset artifact). Also hardened the LAN test against RMCP+ RAKP slowness (`-N 5 -R 3`) so it no longer flakes. |
| 7b | IPMI host-local (KCS) | ✅\* | ✅ | Silicon: **x86 host** `ipmitool -I open` over real LPC KCS → `Found new BMC (0x0d16)`, mc info + FRU rc=0. QEMU: host Get Device ID answered through the modeled KCS state machine. |
| 8 | Update firmware / BIOS | ◐ | ✗ | QEMU: Redfish `UpdateService` ingest surface (POST → HTTP 202 async Task + phosphor-software-manager). No activation / MTD write / BIOS path. **BIOS update is not achievable on the KGPE-D16 — a BOARD-wiring limit, corrected 2026-07-16 (audit).** The earlier "AST2050 has no host-SPI master (that's AST2400+)" reasoning was **wrong at the SoC level**: the AST2050 datasheet documents (a) an **LPC Master mode explicitly for host-BIOS/FWH flash update** (§2.20 p34; regs `LHCR0–LHCRB`, `HICR5[10] ENFWH` — see `qemu-model/peripherals/lpc/DATASHEET-LPC.md` §7) and (b) a **write-capable SMC SPI master with a spare chip-select** (§2.8; `SMC00` per-CE write-enable, `SMC04` user-mode writes). So the SoC *has* host-flash-master paths; what the AST2400+ adds is a *dedicated* host-SPI master + flash-mux (turnkey). The real blocker is that the **KGPE-D16's BIOS SPI hangs off the AMD SB**, not on any BMC-mastered LPC/FWH bus or spare SMC CE, so the BMC cannot reach it on THIS board. **BMC self-update** (the in-scope half) is architecturally possible via the SMC writing the BMC's own SPI, but is **not yet demonstrated** (only the Redfish upload endpoint exists — no MTD write). |
| 9 | Piggyback host NIC | ◐ ✋ | ◐ ✋ | Faithful finding: the board uses a **dedicated RTL8201CP PHY, not NC-SI** (SCU40[15:14] is a software hint, not the strap), so **true NC-SI host-NIC sharing is architecturally ABSENT on this board**. What IS shown (both sides): the BMC is reachable on the shared physical network. The literal feature (NC-SI sideband) cannot be delivered here. |

`\*` = passes on the faithful/honest interpretation with the scoping caveat noted.

## Solidly on silicon (this program's real wins)
- Remote IPMI over LAN; host-local IPMI over real LPC KCS from the x86 host.
- 18 live sensors (fan RPM / temps / voltage rails) over both LAN and KCS.
- Video capture: host VGA → `/dev/video0` → **kernel-wrapped, directly-decodable JPEG**
  (this session's patch 0006; `bytesused=28418` transcript-proven).
- Board FRU / unique-ID identification; BMC reachable on the shared network.

## Genuinely open, in priority order (simplest first)
1. **SOL host byte-flow on silicon** — route the host serial console to the port wired to
   the AST2050 VUART (host console-redirect config), then carry it over an SOL session.
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
   `obmc-console-client`. (Silicon SOL stays rig-blocked — host console not wired to the VUART.)
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
- **True NC-SI host-NIC sharing** — board wires a dedicated PHY and straps MII/RMII
  only; the SoC MAC can do NC-SI but this board does not route it.
- **USB host** — the AST2050 has only a USB *device/gadget* controller (no EHCI/OHCI;
  datasheet feature table lists "USB 1.1 Controller = No").

## Rig-fidelity caveat
All silicon results run on a BMC booted into volatile DRAM over P2A (no boot flash), whose
DRAM is shared with the host VGA framebuffer — so the bench BMC can wedge ~1 min after host
POST and the P2A boot degrades after many cycles. The results are genuine but on a fragile
bench setup; a flash-resident BMC would be immune. See `evidence/real-hw-consolidated/README.md`.

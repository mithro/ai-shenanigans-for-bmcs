# BMC functionality — honest QEMU vs real-silicon status

Last updated 2026-07-16, reconciled against THREE **independent skeptical reviews** of
branch `claude/bmc-functionality` (the second re-ran the USB F6 test both ways and
confirmed the vhub QEMU verification live; the third traced the feature-1 power
fixes down to the `gpio-aspeed.c` dcache/bank mechanics and confirmed the QEMU
`F2 RESULT: PASS` is substantiated + silicon-safe). This is the candid ground
truth, not a summary of claims. Legend: ✅ demonstrated · ◐ partial/scoped · ✋ architecturally
bounded (cannot be fully delivered on this board) · ✗ not yet on this target.

**Bottom line (independent-review verdict):** strictly "demonstrated in BOTH QEMU
AND on real silicon", the full PASS/PASS features are **#1 power on/off (host
power on/off/reset via the `kgpe-power.sh` GPIO path — QEMU `F2 RESULT: PASS`,
silicon plug-verified; the fully-automated Redfish→op-pwrctl loop is the only
open sub-case, #95), #4 sensors, #7 IPMI (local KCS + remote LAN), and #3a VGA
screen capture**. The rest are partial,
rig-blocked, or architecturally impossible on this SoC/board (see per-row notes):
**four features can never be fully delivered here** — #8 host-BIOS flash (no
BMC→host-SPI master), #9 true NC-SI (dedicated PHY), #2's USB-*host* side
(device-only controller), and #5's DIMM/memory inventory (SPDs on the host SMBus).
So "all nine on both QEMU and silicon" is not achievable on this hardware; this
doc is the honest map of what is, what's pending, and what's impossible.

| # | Requested feature | QEMU | Silicon | Honest note |
|---|---|---|---|---|
| 1 | Power on/off | ✅\* | ✅ | **Host power on/off/reset demonstrated on BOTH sides via the same BMC power script `kgpe-power.sh`** (the one hardware-proven on silicon 2026-07-13: `on` → plug 3W→103W + GPIOH2=1 + host PXE-boots; `off` → 103W→4W). **QEMU now PASSES all of init/on/off/on/reset** (`f2-power-control-test.py --driver sysfs`): the guest's in-band GPIOH2 devmem read and the modeled QMP `gpioH2` agree on every step (`F2 RESULT: PASS`; evidence `evidence/qemu/f2-power-sysfs-onoffreset-PASS.txt`). The earlier "QEMU power-ON doesn't latch" was a **phantom — three non-model causes** (all fixed 2026-07-16): (1) the `--driver sysfs` test ran `kgpe-power.sh` *without stopping op-pwrctl*, which held B1/F0/B6 via libgpiod → the script's sysfs export EBUSY'd → the B1 pulse was skipped (the real `obmc-power-{start,stop}@` drop-ins stop op-pwrctl around each pulse; the test now does too); (2) a harness console-sync bug (laggy 256 MB console + TTY-echoed end-marker) lagged the QMP read by a step; (3) a real latent glitch — `setup_lines` drove GPIOF0 (active-low force-off) momentarily low via `direction=out;value 1`, clearing the latch on warm reset (fixed with atomic `direction=high`). The model (`hw/gpio/aspeed_gpio.c` `kgpe_d16_pwrseq`) was correct all along and the `test_power` pytest already validated the latch. **The fully-automated Redfish path also now CONTROLS power in QEMU** (`--driver redfish`, `evidence/qemu/f2-power-redfish-integrated-README.md`): a Redfish `ComputerSystem.Reset` → phosphor-state-manager → `obmc-power-start@0` → the board **drop-in** → `kgpe-power.sh` → GPIO, with the modeled `gpioH2` tracking all four actions (On→True, ForceOff→False, On→True, ForceRestart→True). The #95 "op-pwrctl doesn't drive A4" framing was superseded: power-on rides the `obmc-power-{start,stop}@.service.d/kgpe.conf` drop-ins (installed by the recipe; a stale test export had lacked them), NOT op-pwrctl's held-level drive. **Remaining (telemetry only):** on a hard `ForceOff` the Redfish *Systems* `PowerState` string lingers at `PoweringOff` (host TransitioningToOff) though the hardware is off (gpioH2=False) — an artifact of no real host in QEMU, not a control failure. The Redfish **PowerState readback** null bug is also FIXED (64 MB bmcweb OOM; `evidence/qemu/f2-power-256mb-readback.txt`). |
| 2 | Connect USB devices | ✅ (fix QEMU-proven) | ✗ working / ◐ hang-only | QEMU: the faithful udc model now **reproduces the silicon hang** — the unfixed mainline driver **livelocks** (F6 FAIL), and the G3-ported driver (**patch 0007**: PHY-ready gate + ISR[18] de-livelock + `ast2050-usb-vhub`) **probes cleanly** (7 ports, gadget enumerates, F6 PASS). So the vhub hang is root-caused and the fix is verified against a hang-reproducing model (`VHUB-G3-PORT-PLAN.md`). Silicon: enabling the vhub hangs the mainline driver (`usb-vhub-silicon-boundary.txt`); the fixed-kernel retest is **rig-blocked** (P2A load degrades after ~15 boot cycles). Remaining: fresh-boot silicon retest of patch 0007; and host *enumeration* needs USB-host emulation (QEMU) / physical wiring (silicon). |
| 3a | See virtual VGA screen | ✅ | ✅ | QEMU: real frame → `/dev/video0` → JPEG, 8 bars pixel-verified. Silicon: `/dev/video0` frame `bytesused=28418` (kernel-wrapped) decodes directly to the host's live screen. Evidence: `evidence/real-hw-video/silicon-f8capture-transcript.txt` + `silicon-direct-jpeg.png`. |
| 3b | Send keyboard events | ◐ | ✗ | QEMU only, and a `dummy_hcd` loopback to the BMC's *own* evdev (`EV_KEY/KEY_A`), not delivered to a real host. Silicon: none. Depends on the same host-facing USB gadget path as #2. |
| 4 | Full sensors | ✅ | ✅ | QEMU: W83795G model → 23 sensors over IPMI. Silicon: 18 live sensors over LAN **and** host-KCS — FAN1 2700 RPM, CPU_DIODE 52.12 °C, P12V 13.76 V, rails, VBAT (`evidence/real-hw-consolidated/`). Confirms the G3 i2c-timing (0005) + W83795 hwmon (0003) patches on silicon. |
| 5 | System identification | ◐ | ◐ | Unique IDs + board FRU proven both sides (mc info 2623 / 0x0d16; FRU ASUSTeK KGPE-D16, serial, PN). **Gap:** no DIMM / CPU / memory-config inventory. `i2cdetect` on silicon (`evidence/real-hw-consolidated/bmc-i2c-topology-silicon.txt`) shows the BMC bus has the W83795 (0x2f) but **no DIMM SPDs at 0x50-0x57** — the SPDs are on the host memory SMBus, unreachable by the BMC. Memory inventory would need host SMBIOS ingestion, not a BMC I2C read. |
| 6 | Serial-over-LAN | ✅\* | ◐ | QEMU: faithful VUART, host serial **byte-flow** captured (via `obmc-console-client` reading the VUART; `ipmitool sol activate` over LAN sometimes loses the RMCP+ race, so it's console/VUART byte-flow, not strictly an SOL-session capture). Silicon: SOL is *configured + enabled* (`sol info` rc=0) but no host serial **bytes** carried — the host COM console is not wired to the AST2050 VUART on this board. |
| 7a | IPMI over LAN (remote) | ✅ | ✅ | Full `ipmitool -I lanplus` suite rc=0 both sides; silicon real MAC + populated IDs (`evidence/real-hw-consolidated/`). Strongest result. |
| 7b | IPMI host-local (KCS) | ✅\* | ✅ | Silicon: **x86 host** `ipmitool -I open` over real LPC KCS → `Found new BMC (0x0d16)`, mc info + FRU rc=0. QEMU: host Get Device ID answered through the modeled KCS state machine. |
| 8 | Update firmware / BIOS | ◐ | ✗ | QEMU: Redfish `UpdateService` ingest surface (POST → HTTP 202 async Task + phosphor-software-manager). No activation / MTD write / BIOS path. **BIOS update is architecturally impossible here** — the AST2050 has no host-SPI master to reach the host BIOS flash (that is AST2400+). BMC self-update is the only in-scope half. |
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
   `i2cdetect` on silicon confirms the DIMM SPDs are NOT on a BMC I2C bus, so this cannot
   be a BMC-side I2C read on the KGPE-D16.

## Architecturally bounded (cannot be fully delivered on the AST2050 / KGPE-D16)
- **Host BIOS flashing** — no BMC→host-SPI master on the AST2050.
- **True NC-SI host-NIC sharing** — board wires a dedicated PHY, not NC-SI.
- **USB host** — the AST2050 has only a USB *device/gadget* controller.

## Rig-fidelity caveat
All silicon results run on a BMC booted into volatile DRAM over P2A (no boot flash), whose
DRAM is shared with the host VGA framebuffer — so the bench BMC can wedge ~1 min after host
POST and the P2A boot degrades after many cycles. The results are genuine but on a fragile
bench setup; a flash-resident BMC would be immune. See `evidence/real-hw-consolidated/README.md`.

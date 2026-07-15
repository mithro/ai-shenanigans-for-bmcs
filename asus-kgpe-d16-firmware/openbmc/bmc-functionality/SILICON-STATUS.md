# BMC functionality — honest QEMU vs real-silicon status

Last updated 2026-07-15, reconciled against an **independent skeptical review** of
branch `claude/bmc-functionality`. This is the candid ground truth, not a summary
of claims. Legend: ✅ demonstrated · ◐ partial/scoped · ✋ architecturally bounded
(cannot be fully delivered on this board) · ✗ not yet on this target.

| # | Requested feature | QEMU | Silicon | Honest note |
|---|---|---|---|---|
| 1 | Power on/off | ◐ | ◐ | Silicon OFF fully proven (op-pwrctl, 3 signals). Silicon ON works only via a manual GPIOA4-lockout reclaim + devmem pulse — the *integrated* op-pwrctl ON path deadlocks on held-level reset (open issue #95). QEMU models the GPIO latch (`test_power` PASS) but Redfish PowerState readback is null. |
| 2 | Connect USB devices | ✅\* | ✗ | QEMU: `aspeed-vhub` 7-port + mass-storage/HID gadget enumerate over `dummy_hcd`. Faithful HW fact: AST2050 has **no USB host**, only a device/gadget controller — "connect USB" means the BMC *presents* virtual devices to the host. Not yet exercised on silicon (needs the BMC UDC wired to a host USB port + host enumeration). |
| 3a | See virtual VGA screen | ✅ | ✅ | QEMU: real frame → `/dev/video0` → JPEG, 8 bars pixel-verified. Silicon: `/dev/video0` frame `bytesused=28418` (kernel-wrapped) decodes directly to the host's live screen. Evidence: `evidence/real-hw-video/silicon-f8capture-transcript.txt` + `silicon-direct-jpeg.png`. |
| 3b | Send keyboard events | ◐ | ✗ | QEMU only, and a `dummy_hcd` loopback to the BMC's *own* evdev (`EV_KEY/KEY_A`), not delivered to a real host. Silicon: none. Depends on the same host-facing USB gadget path as #2. |
| 4 | Full sensors | ✅ | ✅ | QEMU: W83795G model → 23 sensors over IPMI. Silicon: 18 live sensors over LAN **and** host-KCS — FAN1 2700 RPM, CPU_DIODE 52.12 °C, P12V 13.76 V, rails, VBAT (`evidence/real-hw-consolidated/`). Confirms the G3 i2c-timing (0005) + W83795 hwmon (0003) patches on silicon. |
| 5 | System identification | ◐ | ◐ | Unique IDs + board FRU proven both sides (mc info 2623 / 0x0d16; FRU ASUSTeK KGPE-D16, serial, PN). **Gap:** no DIMM / CPU / memory-config inventory. `i2cdetect` on silicon (`evidence/real-hw-consolidated/bmc-i2c-topology-silicon.txt`) shows the BMC bus has the W83795 (0x2f) but **no DIMM SPDs at 0x50-0x57** — the SPDs are on the host memory SMBus, unreachable by the BMC. Memory inventory would need host SMBIOS ingestion, not a BMC I2C read. |
| 6 | Serial-over-LAN | ✅\* | ◐ | QEMU: faithful VUART, host serial bytes captured over an SOL session. Silicon: SOL is *configured + enabled* (`sol info` rc=0) but no host serial **bytes** carried — the host COM console is not wired to the AST2050 VUART on this board. |
| 7a | IPMI over LAN (remote) | ✅ | ✅ | Full `ipmitool -I lanplus` suite rc=0 both sides; silicon real MAC + populated IDs (`evidence/real-hw-consolidated/`). Strongest result. |
| 7b | IPMI host-local (KCS) | ✅\* | ✅ | Silicon: **x86 host** `ipmitool -I open` over real LPC KCS → `Found new BMC (0x0d16)`, mc info + FRU rc=0. QEMU: host Get Device ID answered through the modeled KCS state machine. |
| 8 | Update firmware / BIOS | ◐ | ✗ | QEMU: Redfish `UpdateService` ingest surface (POST → HTTP 202 async Task + phosphor-software-manager). No activation / MTD write / BIOS path. **BIOS update is architecturally impossible here** — the AST2050 has no host-SPI master to reach the host BIOS flash (that is AST2400+). BMC self-update is the only in-scope half. |
| 9 | Piggyback host NIC | ✅\* | ✅\* | Faithful finding: the board uses a **dedicated RTL8201CP PHY, not NC-SI** (SCU40[15:14] is a software hint, not the strap). BMC is reachable on the shared physical network both sides; true NC-SI host-NIC sharing is architecturally absent on this board. |

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
2. **Integrated power-ON** — fix the op-pwrctl held-level-reset deadlock (#95) so ON works
   through the OpenBMC path, not a manual devmem pulse.
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

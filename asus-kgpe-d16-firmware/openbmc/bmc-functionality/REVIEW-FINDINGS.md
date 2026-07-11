# F-REVIEW — independent audit of `claude/bmc-functionality`

**Reviewer:** F-REVIEW sub-agent (independent, skeptical). **Date:** 2026-07-12.
**Target:** consolidated branch `claude/bmc-functionality` @ `ca5caa3`.
**Method:** read every per-feature doc + its committed evidence, judged whether the
evidence substantiates the claim, re-ran three of the lighter QEMU demos myself
(not trusting the committed logs), audited the CI wiring, and checked the
faithfulness findings against the datasheet cites + the QEMU model. Read-only
except this doc + my re-run logs. Did **not** touch the real-HW rig (F-HWPASS owns
it) and did **not** start a Yocto build (F-HWPASS owns that slot).

> **Bottom line up front:** the work is **substantially honest and well-evidenced**.
> Every doc cleanly separates PROVEN-IN-QEMU from real-HW and from deferred gaps,
> and the faithfulness findings (no USB host, dedicated-PHY-not-NC-SI, KCS-only /
> BT-not-G3-drivable, no BMC→BIOS path) are datasheet-cited, not asserted. The
> genuine caveats are about **coverage, not fabrication**: only **2 of 9**
> capabilities are presently proven on *silicon* (remote IPMI-over-LAN, and the
> board's network reachability); the rest are QEMU-proven with real-HW **deferred**
> (rig contention / safety / physical wiring) — honestly labelled as such. Three
> CI jobs (F4/F5/F9) are latent (gated behind `workflow_dispatch` + a rootfs
> artifact that isn't published), so several features are **not** exercised in
> automatic CI. One minor summary-line overclaim in F2 (Redfish `PowerState`).

---

## 1. Independent spot-check re-runs (I ran these myself, at `nice -n 15`)

I re-ran three demos from prebuilt QEMU/kernel/initramfs artifacts in sibling
worktrees + the consolidated QEMU (`qemu-system-arm 10.0.7`, gitlink `a010d6963a`,
machine `kgpe-d16-bmc`), rather than trusting the committed logs.

| Demo | What it asserts | My result |
|---|---|---|
| **F7 NC-SI guard** (`f7-ncsi-evidence.py --boot-log …`, buildless) | 11 invariants: DTS RMII/no-`use-ncsi`, Raptor `MAC1_PHY_SETTING=0`, datasheet no-NCSI, kernel no `CONFIG_NET_NCSI`, boot-log dedicated-PHY eth0+DHCP with ZERO NC-SI | **11 passed, 0 failed** (QEMU submodule model-check SKIP — not checked out in review worktree; expected) |
| **F8 KVM** (`kvm-test.py`, 64 MB boot) | `aspeed-video` probes engine → `/dev/video0`; vhub inits; HID kbd+mouse gadget enumerates; keypress report → host evdev `EV_KEY KEY_A` | **PASS** — confirmed `aspeed-video 1e700000.video: irq 24` → `/dev/video0`, `aspeed_vhub 1e6a0000.usb-vhub: Initialized virtual hub`, and the keypress byte-stream `01 00 1e 00 01 00 00 00` (type EV_KEY, code 0x1e KEY_A, value 1) crossing dummy_hcd to `/dev/input/event1` |
| **F5b host-KCS** (`f5b-host-kcs-test.py`, 64 MB boot) | `/dev/ipmi-kcs3` created; `ast-kcs-bmc` bound to `kcs@2c`; the driver drove the faithful LPC model (HICR0.LPC3E, HICR4.KCSENBL, LADR3=0x0CA2, STR3 RO=0); BMC-side ODR3 poke reads back | **PASS** — reproduced every register value in the committed evidence (HICR0=0x80, HICR4=0x04, LADR3=0x0CA2, ODR3 poke→0x5A), at 64 MB |

All three reproduced the committed claims exactly. This raises my confidence that
the other committed QEMU logs (which I read but did not re-execute) are genuine.

---

## 2. Scorecard (capability × status)

Legend: **QEMU** = proven in the faithful QEMU machine; **HW** = proven on the real
AST2050 (192.168.66.2); *deferred* = honestly not-yet-run, justification noted.

| # | Capability | QEMU status | Real-HW status | Evidence pointer | Verdict |
|---|---|---|---|---|---|
| 1 | **Power on/off** (F2) | GPIO power-latch model proven (CI fwtest `test_power.py`; GPIOH2 via QMP flips on/off/reset); Redfish `Reset` accepted (HTTP 204) | **partial** — IPMI `chassis power status`=off reads back (rc=0); actual on/off **drive** deferred | `evidence/qemu/f2-power-results.json`, `evidence/qemu/F2-README.md`; `evidence/real-hw/chassis-*.txt` | **QEMU-proven; HW deferred** (safety: the request lines really power the host; rig held) |
| 2 | **Connect USB** (F6) | vhub probe + gadget (mass-storage) enumeration over dummy_hcd | none (QEMU-only) | `evidence/f6-usb/*.txt`; `F6-USB.md` | **QEMU-only to the faithful bar**; "attach a USB stick to the BMC" is **N/A by silicon** (no USB host) — correctly reframed as the gadget/vKVM path |
| 3 | **VGA screen + keyboard** (F8) | `/dev/video0` probe + HID keypress→host evdev (**I reproduced**) | none (QEMU-only) | `evidence/f8-kvm/*.txt`; `F8-KVM.md` | **QEMU-only to honest bar**; no host VGA source (no real pixels), HID over dummy_hcd not a real host — clearly stated |
| 4 | **Full sensors** (F3) | 23 sensors real values via W83795G model → D-Bus + IPMI `sdr` | **deferred** — live board shows `disabled` baseline (runs non-W83795 kernel) | `evidence/qemu-sensors/*`; `evidence/real-hw-sensors/*` | **QEMU-proven; HW deferred** (rig contention; needs F3-kernel reboot; tool `f3-realhw-sensors.py` ready) |
| 5 | **System identification** (F1/F5/F-IMG2) | Redfish system-id (F1); IPMI `mc info`/`lan`/`fru` (F5); populated IDs+FRU+Chassis after img2 fixes | **partial** — IPMI enumerates on real board (real MAC `96:0e:ce:b9:5d:8d`); IDs **zeroed** + FRU **empty** (img2 data fixes not deployed to HW) | `evidence/qemu/*`, `evidence/img2/*`; `evidence/real-hw/*` | **QEMU-proven; HW mechanism proven, DATA unpopulated** (img2 recipe not on the live image) |
| 6 | **Full SOL** (F4) | VUART model + `obmc-console` capture (836 B/19 markers); raw `/dev/ttyVUART0` 360 B | **partial** — SOL channel established (`sol payload status`=enabled, rc=0); **no byte capture** | `evidence/qemu-sol/*`; `evidence/real-hw-sol/*`; `F4-SOL-STATUS.md` | **QEMU-proven; HW = channel only** (host COM1 is FTDI-tapped, not wired to the VUART — physical rig limit; VUART DTB staged, not booted) |
| 7 | **Full IPMI local + remote** (F5 LAN, F5b KCS) | LAN: full suite rc=0 over RMCP+; local: `/dev/ipmi-kcs3` channel M1 (**I reproduced**) | **LAN: PROVEN on silicon** (mc info/chassis/lan/sel/sdr/user all rc=0); **local KCS: deferred** | `evidence/qemu/*`, `evidence/host-kcs/*`; `evidence/real-hw/*` | **Remote IPMI = QEMU+HW ✅ (strongest result)**; Local IPMI = QEMU M1 channel proven, HW deferred + full host↔BMC round-trip needs a host peer (honest boundary) |
| 8 | **Update firmware + BIOS** (F9) | Redfish `UpdateService` live (POST→202+Task), phosphor-software-manager running, FirmwareInventory | **read-only characterization** (JTAG/P2A/flashrom read paths); **no writes** (safety) | `../../fw-update/evidence/qemu/*`; `../../fw-update/REAL-HW-CHARACTERIZATION.md` | **BMC-update SURFACE proven in QEMU** (no real flash write, by the safety rule; MTD write target masked on NFS = honest gap); **BIOS-via-BMC absent by hardware** (faithful finding) |
| 9 | **Piggyback host network** (F7) | dedicated-PHY eth0 + DHCP, ZERO NC-SI (**I reproduced**) | **✅** — OpenBMC/IPMI already served over the shared physical net at 192.168.66.2 | `evidence/qemu-ncsi/*`; `F7-NCSI.md`; all real-HW IPMI captures | **QEMU + HW ✅**; faithful finding (dedicated RTL8201CP PHY on RMII, **not** NC-SI) is datasheet+Raptor+DTS-backed |

---

## 3. Faithfulness findings — do they hold up?

All four headline "the AST2050 can't do X the generic way" findings are **backed by
datasheet page cites + the QEMU model**, not merely asserted:

- **No USB host, only the vhub** — datasheet §9 (single USB region `1E6A:0000`),
  §10 (only "USB 2.0 interrupt" INT#5), §15 (device/virtual-hub only). The QEMU
  machine **omits the phantom AST2400 EHCI** for the G3 (`0x1E6A1000` reads 0). The
  Raptor `astuhci` UHCI *host* driver is correctly diagnosed as dead BSP code.
  **Holds.**
- **Dedicated PHY, not NC-SI** — DTS `phy-mode="rmii"` + no `use-ncsi`; Raptor
  `CONFIG_MAC1_PHY_SETTING=0`; datasheet SCU70[8:6] MII/RMII-only. My F7 guard
  re-run confirmed all 11 invariants including ZERO NC-SI in a real boot. **Holds.**
- **KCS-only host IPMI (BT not G3-drivable)** — mainline `bt-bmc` hardcodes the
  AST2400 `0x140` offset, which is beyond the G3 LPC window (`ASPEED_LPC_AST2050_NR_REGS
  = 0xA0/4`); the AST2050 BT is at `0x48–0x68`. So KCS ch3 (`0xca2`) is the only
  mainline-drivable channel — and the KCS register offsets are byte-identical to the
  G4 driver, which the M1 demo exploits. **Holds.**
- **No BMC→host-BIOS path** — the host BIOS (2 MB W25Q16) is on the AMD SP5100 FCH
  SPI bus; the AST2050 has only the single legacy SMC at `0x16000000` driving
  BMC-side flash. "Update BIOS via BMC" is an AST2400+/board-wiring feature absent
  here. **Holds** — and this correctly bounds capability #8.

Crucially, **nothing fakes a capability the silicon lacks**: F6 refuses to model an
EHCI host, F7 refuses an NC-SI responder, F5b refuses to fabricate a host KCS
transaction (the LPC model has no OBF/IBF state machine, so a from-AHB poke can't
carry a fake KCS message — explicitly called out in F5B §5). This is the
"QEMU must model REAL hardware" rule being followed. The legacy-boot faithfulness
guard is also intact: the CI keeps the C2 (new stack→SSH), C3 (Raptor 2.6.28), and
C4 (Dell vendor→BMC web) boot jobs, so a model change that breaks a legacy boot
would fail CI. (I did not re-run those heavy jobs.)

---

## 4. CI coverage — the real gap

Jobs that run on **every push** (I confirmed the triggers + `if:` conditions in
`.github/workflows/d16-qemu-stack.yml` and `d16-kvm.yml`):

- ✅ `power-control-test` (F2 fwtest / `test_power.py`), `host-kcs` (F5b),
  `boot-usb` (F6), `f7-ncsi-dedicated-phy` (F7), `boot-kvm` (F8, in d16-kvm.yml),
  plus the base boots `boot-ssh`/`boot-nfsroot`/C3/C4/U-Boot.

Jobs that are **latent** (gated `if: github.event_name == 'workflow_dispatch'`
**and** depend on a `openbmc-full-rootfs` artifact that is *not* built/published):

- ⚠️ `f5-ipmi-lan` (F5), `f4-sol` (F4), `fw-update` (F9).

**Consequence:** the IPMI-over-LAN, SOL, and firmware-update features — including
the one capability actually proven on silicon (remote IPMI) — are **not exercised
in automatic CI**. PROGRESS itself lists "CI job needs the rootfs artifact
published" as remaining, so this is disclosed, but it means the scorecard's
strongest real-HW result has **no reproducible CI guard**. This is the single most
important coverage gap to close (publish the fuller-image rootfs as a release
artifact so those three jobs run).

---

## 5. Overclaims, under-credited work, and honest gaps

### (a) Overclaim (minor, self-mitigated)
- **F2 Redfish `PowerState`.** `OPENBMC-POWER-INTEGRATION.md` and `evidence/qemu/F2-README.md`
  describe "the full Redfish → … → PowerState loop, confirmed end to end." The
  committed `f2-power-results.json` shows `PowerState: null` for **every** action
  (and one transient HTTP 500), with only `gpioH2` (read via QMP) tracking. So the
  **forward** path (Redfish action → GPIO latch) is proven, but the **return** path
  to the Redfish `PowerState` *property* is **not** closed. To F2's credit, the
  README adds an explicit caveat naming this (bmcweb 64 MB memory pressure) and
  correctly designates GPIOH2/QMP + the CI fwtest as authoritative. Net: the summary
  sentence overreaches by one clause; the evidence and caveat are honest. Recommend
  softening the prose to match the caveat.
- **PROGRESS "carries F2 (power) on REAL HW via IPMI"** (log 2026-07-12): on real HW
  only `chassis power status` (read) is shown; no on/off **drive** was performed.
  Reads slightly stronger than the evidence; other PROGRESS/F2 text correctly says
  the real drive is deferred.

### (b) Under-credited
- **F5b host-KCS** is a genuinely solid, honest result that's easy to undervalue: a
  real `/dev/ipmi-kcs3` channel driven end-to-end against a datasheet-accurate LPC
  model at 64 MB, with a principled refusal to fake the host side. Strong work.
- **F7's "it isn't NC-SI" finding** is real reverse-engineering value, not a dodge —
  it corrects the task's own framing with evidence.
- **F9's BIOS analysis** correctly turns "update the BIOS" into a faithful hardware
  finding (no BMC datapath) rather than pretending.

### (c) Honest gaps — justified vs. real holes
- **Justified (physical / rig / safety):** F2 real drive (would really power the
  host; rig held) · F3 real read (needs a state-mutating reboot onto the F3 kernel;
  displaces F5's live evidence) · F4 real byte capture (host COM1 FTDI-tapped, not
  VUART-wired — a board/BIOS wiring fact) · F9 no real flash write (explicit safety
  rule) · F5b real KCS (needs the host powered + `kcsbridge` in the image) · F6/F8
  real (rig unreachable from the build env). All are well-argued and non-fabricated.
- **Real (not physical, just not done):** the img2 data fixes (mc-info IDs, FRU,
  Chassis, SOL config object, KGPE-D16 SDR names) are **QEMU-only at `mem=256`** and
  were **never deployed to the live board**, so on silicon `mc info`/`fru` still show
  zeros/empty (capability #5 data). The SOL config-object provider and `kcsbridge`
  image switch are likewise QEMU/staged only. These are image-recipe follow-ups that
  *could* be closed without new hardware findings.

---

## 6. Bottom line vs. the 9-capability checklist

**Fully demonstrated on BOTH QEMU and real silicon (2 of 9):**
- **#7 remote IPMI-over-LAN** — the standout: identical `ipmitool -I lanplus` suite
  passes in QEMU *and* on the real AST2050 at 64 MB (real MAC, cipher 17, root=ADMIN).
- **#9 host-network piggyback** — dedicated-PHY faithful finding proven in QEMU, and
  the board is genuinely reachable (OpenBMC/IPMI) on the shared physical net.

**QEMU-proven with real-HW DEFERRED (justified) — the majority (6 of 9):**
- **#1 power** (model + forward path proven; real drive is a safety-gated deferral),
  **#3 VGA+keyboard** (device + HID byte-stream to honest bar),
  **#4 sensors** (full W83795G read chain; real read needs a reboot slot),
  **#5 system-id** (mechanism proven both sides; real *data* unpopulated),
  **#6 SOL** (bytes flow in QEMU; real = channel only, host wiring limit),
  **#7 local/host KCS half** (BMC-side channel M1; full round-trip needs a host peer).

**QEMU-only by design + honest scope reframe (part of the set):**
- **#2 USB** — the only faithful meaning on this SoC is the gadget/vKVM path (no USB
  host in silicon); demonstrated to that bar in QEMU, real HW not run.
- **#8 firmware/BIOS** — BMC firmware-update *surface* proven in QEMU (no real write
  by safety rule; MTD write target is a genuine open gap); BIOS-via-BMC is correctly
  **out of scope by hardware**.

**Not credibly demonstrated / would be an overclaim if asserted:** none outright —
but be precise in any external summary that (a) only remote-IPMI and net-reachability
are on silicon today, (b) F2 does not close the Redfish `PowerState` round-trip, and
(c) F4/F5/F9 have no automatic CI guard yet. F-HWPASS's forthcoming
`evidence/real-hw-hwpass/` (power/sensors/SOL/host-KCS on silicon) is what would move
#1/#3?/#4/#6/#7-local into the "both" column; that directory was **not present** at
review time, so those real-HW items are **in-flight (F-HWPASS)**, not failed.

**Overall:** a credible, unusually honest body of work. The claims match the
evidence with one minor prose overreach (F2 PowerState). The distance from "done" is
**real-HW coverage + CI reproducibility for the fuller-image features**, not
truthfulness of what's claimed.

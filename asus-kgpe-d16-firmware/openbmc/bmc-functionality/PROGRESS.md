# OpenBMC full-BMC-functionality build-out — progress log

**Goal (user, 2026-07-11):** enable all normal BMC functionality on OpenBMC/AST2050
(ASUS KGPE-D16), demonstrated in **QEMU** *and* on **real silicon**, simplest-first.
Branch `claude/bmc-functionality` (worktree `.worktrees/bmc-functionality`), off
`claude/ast2050-qemu-faithful` @ 24cd80b (which has the faithful G3 QEMU + the
ftgmac100 FAST_MODE RX fix + OpenBMC-over-NFS Redfish, proven on silicon).

Constraints: small commits + commit this log after every change; ≤4 concurrent
sub-agents; don't overload RAM; code review + CI(GH Actions/QEMU) + real-HW tests;
push regularly to all repos; **no PRs**; no unrecoverable changes (no real BIOS
flash); demonstrate every feature in QEMU AND on hardware; 5-min progress updates.
**Always work against LATEST UPSTREAM** of everything (Linux kernel, QEMU, OpenBMC,
…) — the OpenBMC image builds on latest master; kernel + QEMU faithful model get
rebased onto latest upstream (tracked as F-UPSTREAM; done incrementally so as not
to break the proven faithful boot).

## Starting point (recon 2026-07-11)
Running OpenBMC image (`obmc-phosphor-image-ast2050-redfish`, NFS root
`/export/openbmc-kgpe-d16` = board `192.168.66.2`) has ONLY: bmcweb (Redfish),
phosphor-{inventory,network,user,settings,log,certificate}-manager,
fan-presence-tach. **Missing:** IPMI (host KCS + LAN), SOL/obmc-console, sensors
(dbus-sensors/hwmon), power/state-manager (host+chassis), KVM/video, NC-SI.
NFS root = unlimited size; the real limit is **64 MB runtime RAM** (pick a
runnable set of daemons).

## Feature plan (simplest-first) — each: OpenBMC feature + QEMU model/DTS + demo(QEMU+HW) + tests/CI
1. System identification (Redfish/inventory: BMC + system + network info)  — F1
2. Power control (host on/off/reset: state-manager + power GPIO)           — F2
3. Sensors (fan/voltage/temp: dbus-sensors/hwmon + I2C devices)            — F3
4. Serial-over-LAN (obmc-console on the host UART, already wired)          — F4
5. IPMI local + remote (phosphor-ipmi-host KCS + phosphor-ipmi-net RMCP+)  — F5
6. USB devices                                                            — F6
7. Host network piggybacking (NC-SI)                                       — F7
8. Virtual VGA + keyboard (video engine + USB HID + obmc-ikvm)             — F8
9. Firmware/BIOS update path (no real flash)                              — F9

Strategy: batch the OpenBMC feature packages into ONE fuller image build (amortise
the multi-hour Yocto build), then enable/demonstrate features one-by-one on it.
QEMU HW models + DTS wiring proceed in parallel.

## Resource limits (user-directed)
Run all heavy builds at reduced nice + capped memory so they can't OOM the box
(31 GB RAM / 12 cores). Recipe: `nice -n 15 ionice -c3` + `systemd-run --user
--scope -p MemoryMax=20G -p MemoryHigh=18G` + low `BB_NUMBER_THREADS=4`/`PARALLEL_MAKE=-j4`.
Leave ≥8 GB headroom; watch `free -g`.

## Log
- 2026-07-11: worktree+branch created; recon done (above).
- 2026-07-11: F0 OpenBMC fuller-image build dispatched to a sub-agent (branch
  `claude/bmc-f0-openbmc-image`, latest-upstream master, capped resources). Long
  pole (hours). Adds IPMI/SOL/sensors/state-mgmt; staged to /export/openbmc-full +
  Pi /srv/nfs/openbmc-full (keeps the proven redfish image as fallback).
- 2026-07-11: F2/F3-PREP DONE + merged — `HW-WIRING-power-sensors.md`: power via a
  3-request-line GPIO protocol (ON=GPIOB1, OFF=GPIOF0, RST=GPIOB6, state-in=GPIOH2,
  lockout=GPIOA4; from Raptor's real AST2050 OpenBMC port); sensors = one W83795G
  hwmon on BMC I2C bus1 @0x2f (8 fan-tach+8 PWM, dual-Vcore, rails, temps). Caveats:
  SCU polarity + bus-index + PMBus addr need HW confirm; w83795.c needs special
  instantiation. Feeds F2 + F3.
- 2026-07-11: F0 fuller-image build ~93% (bitbake 5588/5985), RAM healthy, no errors.
  NEXT once F0 stages: F1 (system-id — software-only, reuses the already-built
  faithful QEMU + g3vic kernel + the new fuller rootfs), then F2 power (DTS gpio +
  QEMU GPIO model + state-mgmt), then F3 sensors, F4 SOL, F5 IPMI. Serialize heavy
  builds (one at a time) to respect the RAM cap.
- 2026-07-11: F0 DONE + merged. Fuller image (obmc-phosphor-image-ast2050-full,
  OpenBMC master fc5c298, 20MB squashfs) staged to /export/openbmc-full + Pi
  /srv/nfs/openbmc-full; auth root/0penBmc. QEMU (583ad3db74) rebuilt; kernel/DTB
  rebuilt to the REAL-PHY DTB (the stale fixed-link DTB in kernel/out was the first
  F1 boot failure — DHCP/NFS timed out; real-PHY DTB fixed it: DHCP OK, NFS root
  mounted, systemd up).
- 2026-07-11: **KEY 64MB finding** — booting the fuller image at mem=64 with ALL
  daemons makes bmcweb CRASH-LOOP (SSL handshake resets = memory starvation). The
  real AST2050 is 64MB, so each feature must run only the daemons it needs
  (per-feature daemon masking). Maskable non-F1 units identified: IPMI
  (org.openbmc.HostIpmi, phosphor-ipmi-host, xyz...Ipmi.*, ...Logging.IPMI,
  netipmid), sensors (adc/fan/hwmontemp, phosphor-hwmon), EntityManager, lpcsnoop,
  sel-logger, host/chassis state-mgrs. This masked-set pattern is reused by F2-F9.
- 2026-07-11: F1 (system-id) delegated to sub-agent claude/bmc-f1-system-id: mask
  non-F1 daemons -> bmcweb serves -> demonstrate Redfish Managers/bmc + Systems +
  Chassis + EthernetInterfaces in QEMU AND on the real board; add a CI test.
  (F-UPSTREAM kernel/QEMU bump deferred — OpenBMC already latest master; features
  proceed on the proven 6.6.70+faithful-QEMU stack first, simplest-first.)
- 2026-07-11: **F1 QEMU PASS.** Finalised the 64MB mask set (14 units, single
  source `f1_masked_daemons.py`; rendered as kernel `systemd.mask=` tokens, 693
  chars, fits the 1024 ARM cmdline). Boot of the fuller image at mem=64 with the
  masks -> bmcweb serves Redfish STABLY (was crash-looping with all daemons).
  Captured authenticated (root/0penBmc) system-id evidence (evidence/qemu/):
  RedfishVersion 1.17.0; Managers/bmc UUID 50f94dce-8314-4d35-bc4c-00274d6fcb2f,
  Model OpenBmc, ServiceEntryPointUUID present, FirmwareVersion="none" (F0 build
  didn't stamp a version — field present, cosmetic); eth0 MAC 52:54:00:12:34:56,
  IPv4 10.0.2.15, LinkUp/100Mbps. Host ComputerSystem UUID/Serial legitimately
  empty (entity-manager/FRU inventory masked + no powered host) -> captured but
  not gated. Deliverables: `f1-system-id-test.py` (CI-ready, boots+asserts, with
  per-request retry for bmcweb's under-64MB connection drops), `MASKED-DAEMONS.md`
  (reusable pattern + per-feature adaptation table), `f1-realhw-capture.py`.
  NOTE for downstream: the F0 build's Manager FirmwareVersion is the literal
  "none" — a version-stamp gap in the recipe, worth fixing for a nicer demo.
- 2026-07-11: F1 real-HW: board 192.168.66.2 is up serving the OLDER lean redfish
  image (root LOCKED -> authenticated Redfish = HTTP 401), so authenticated
  system-id needs the fuller image (root/0penBmc). Real-HW plan = P2A cold-boot
  the fuller image over NFS (/srv/nfs/openbmc-full) with the g3vic RX-fixed kernel
  + real-PHY DTB (already staged in Pi TFTP) + rootfs-symlink masking (U-Boot
  cmdline can't carry the 693-char mask fragment reliably). Host culvert + Pi
  bridge confirmed reachable. Attempt logged to HARDWARE-COORDINATION.md.
- 2026-07-11: **F1 real-HW OUTCOME — fuller image does NOT fit real 64MB over
  NFS-root.** Two escalating P2A cold-boots (rig claimed + released via
  HARDWARE-COORDINATION.md; board reset only, flash untouched, fully recoverable):
  BOTH reached kernel-up + eth0 100Mbps (RX-fix) + IP-Config .2 + **NFS root
  mounted** (rmtab confirms /srv/nfs/openbmc-full) + systemd reading ~135MB, then
  attempt-1 (14 masks) hard-FROZE at networkd's eth0 takeover (eth0 down, NFS
  flat, silent console) and attempt-2 (27 masks) kept the static IP but THRASHED
  (NFS reads ~250KB/min, no listener). The wall is RAM: the fuller image can't
  make progress in the real board's effective 64MB with NFS-root memory demands
  (QEMU's clean 64MB tolerates it — QEMU PASS). This matches the program-level
  "modern full OpenBMC won't fit 64MB" constraint -> the real-HW path is the lean
  redfish image / a stripped Redfish-only image, not the fuller image.
  **Real-HW Redfish IS live** on the lean image (unauth ServiceRoot 200,
  RedfishVersion) — captured to evidence/real-hw/; authenticated system-id on
  real HW stays blocked (fuller image doesn't fit; lean image root deliberately
  locked, must not be force-unlocked). Rig RESTORED to the lean image (as found)
  + fuller export masks reverted to pristine F0. Deliverable `f1-realhw-capture.py`
  is ready to grab the full authenticated set the moment a fitting image
  (stripped Redfish-only, root set) boots on real HW.

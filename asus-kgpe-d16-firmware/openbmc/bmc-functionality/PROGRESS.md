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
- 2026-07-11: **USER GUIDANCE — only the API + IPMI functionality is needed, NOT
  the web interface.** Combined with F1's real-HW finding (the fuller image with
  bmcweb doesn't fit real 64MB): strategy pivot ->
  * **IPMI is the lean, real-HW path** (ipmid host KCS/BT + netipmid LAN are far
    lighter than bmcweb's Boost/SSL). Real-HW feature demos go IPMI-first
    (ipmitool over LAN + from the host) so they fit 64MB.
  * **Redfish API (bmcweb)** = demonstrated in QEMU (RAM headroom) and on real HW
    only where it fits alone; it's the "API" the user wants (webui-vue already
    excluded from F0).
  * So for the tight real-HW 64MB demos: **mask bmcweb**, run the IPMI stack +
    backends (state-mgr/sensors/inventory). This is the key 64MB unlock.
  This reprioritizes F5 (IPMI, esp. netipmid LAN which needs no KCS hardware) as
  the backbone; system-id/power/sensors/SOL/FRU are all exposed via IPMI on HW.
- 2026-07-12: **F5 IPMI backbone DONE — LAN IPMI PASSES in QEMU AND on the real
  AST2050 at 64MB** (bmcweb-masked lean image). Identical ipmitool -I lanplus rc=0
  for: mc info, chassis status/power status, lan print (real MAC on HW), sel
  info/list, sdr list (28 SDRs), user list. fru print enumerates 12 devices but
  data absent (no I2C EEPROM). Evidence under bmc-functionality/evidence/{qemu,real-hw}/.
  This carries F1 (system-id: mc info/lan print/fru), F2 (power: chassis power/status),
  F3 (sensors: sdr list) on REAL HW via IPMI — the strategy the user's API+IPMI
  guidance enabled. realhw mask profile (24 masks) documented. Board left ON serving
  IPMI @192.168.66.2; NFS export reverted pristine; rig released.
  REMAINING: (a) host-side KCS/BT IPMI (DTB has no kcs/bt child node; QEMU G3 LPC
  model exists — needs M1 DTS node + M2 emulated LPC host peer) = "IPMI local on the
  motherboard"; (b) DATA population — mc info IDs zeroed (dev_id.json) + FRU empty
  (populate in recipe/HW); (c) actual host power on/off via the GPIO (F2 config) on
  real HW (status works; drive-loop to verify); (d) F4 SOL; (e) CI job needs the
  rootfs artifact published.
- 2026-07-12: **F-IMG2 started** (branch `claude/bmc-f-img2` off `claude/bmc-functionality`).
  Batches the four IMAGE-RECIPE gaps F1-F5 found into ONE rebuild, as bbappends /
  small config recipes under `asus-kgpe-d16-firmware/openbmc/recipes/` (synced into
  the OpenBMC tree by `recipes/sync-to-openbmc-tree.sh`, additive to F2's in-tree
  image edits):
  * (a) SOL: `phosphor-settings-defaults-native.bbappend` + `sol-template.yaml` --
    settingsd now owns `/xyz/openbmc_project/ipmi/sol/eth0` (xyz.openbmc_project.Ipmi.SOL),
    the object netipmid's Activate-Payload read (was ResourceNotFound -> sol activate failed).
  * (b) SDR: `q71l-ipmi-sensor-map-native.bbappend` + `kgpe-d16-sensor.yaml` swap the
    static SDR map to board rail names (VCORE0/1, P12V/P5V/P3V3/P1V5/P1V1/P0V9/VBAT,
    CPU diode + CPU0/1 DTS); `kgpe-d16-hwmon-config.bb` ships the matching phosphor-hwmon
    channel map so the names resolve to real W83795G readings.
  * (c) Redfish: `entity-manager_%.bbappend` + `kgpe-d16.json` (Probe:TRUE) publishes an
    Inventory.Item.Chassis + board Asset -> non-empty /redfish/v1/Chassis.
  * (d) IDs/FRU: `phosphor-ipmi-config.bbappend` real `dev_id.json` (ASUSTeK PEN 2623,
    prod 0x0D16); `kgpe-d16-fru-populate.bb` ships an IPMI FRU blob (`gen_fru.py`,
    checksums verified) loaded into the motherboard inventory via phosphor-read-eeprom.
  Capped rebuild launched (systemd-run MemoryMax=20G + nice/ionice + BB -j4); recipes
  parse clean, build progressing, RAM healthy. QEMU demos next.

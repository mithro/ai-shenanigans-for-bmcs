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
7. Host network piggybacking (NC-SI)                                       — F7 ✅ (finding: NOT NC-SI — dedicated PHY; see F7-NCSI.md)
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
- 2026-07-11: **F2 (host power control) — QEMU DONE** (branch claude/bmc-f2-power).
  * **QEMU model:** faithful KGPE-D16 power-sequencer in the Aspeed GPIO model
    (`aspeed_gpio_kgpe_d16_pwrseq`, QEMU submodule branch claude/bmc-f2-power):
    a set/reset host-power latch driven by the 3 active-low request lines
    (GPIOB1 power-up sets, GPIOF0 power-down clears, GPIOB6 reset = no change),
    reflected on the GPIOH2 power-state input. Gated behind the `kgpe-d16-pwrseq`
    qdev property, which only the AST2050 SoC (ast2400.c, keyed on
    AST2050_A1_SILICON_REV) enables — every other Aspeed board is unchanged, so
    the legacy C2/C4 boots do not regress.
  * **fwtest + CI test:** `qemu-model/peripherals/power/fwtest.c` (4 checks:
    off@reset / on after power-up pulse / on across reset pulse / off after
    power-down pulse) + `qemu-model/integration/test_power.py` (pytest, 6 cases,
    all PASS) — the CI-suitable QEMU test asserting the power-control loop.
  * **DTS:** gpio-line-names (power-up/-down/reset-req-n, power-state-in, lockout,
    spd-mux) + gpio-leds (bmc-status/identify/cpu1/2-err) + gpio-keys id-button
    added to aspeed-bmc-asus-kgpe-d16.dts (real-PHY mac0 kept). Boots: kernel
    logs "input: gpio-keys".
  * **OpenBMC:** F2 masked-daemon set (`f2_masked_daemons.py`) KEEPs the host +
    chassis state managers + `org.openbmc.control.Power@0` (op-pwrctl), masks
    IPMI/sensors/EM/lpcsnoop. op-pwrctl (phosphor-skeleton-control-power) added
    to the -full image + `gpio_defs.json` (power_up_outs=[B1 pol0, F0 pol1] so its
    held-level drive maps onto the modeled latch; power_good_in=H2). Staged to
    /export/openbmc-f2power.
  * **Demos:** (a) sysfs — kgpe-power.sh drives the request lines through the real
    gpio-aspeed driver, GPIOH2 confirmed via QMP qom-get; (b) redfish — the
    automated Redfish `ComputerSystem.Reset` -> phosphor-state-manager -> op-pwrctl
    -> GPIO request line -> modeled latch -> GPIOH2 **forward path**
    (`f2-power-control-test.py`): each action returns HTTP 204 and GPIOH2 tracks it
    over QMP. The Redfish `PowerState` *readback* is NOT proven (it read back
    `null` under the 64 MB bmcweb pressure); GPIOH2/QMP + the CI fwtest are the
    authoritative signal. See OPENBMC-POWER-INTEGRATION.md. Real-hardware demo deferred (rig held by another
    agent); the request lines drive the real board's power — bring up board-OFF,
    verify GPIOH2 read-only first, validate SCU pinmux over P2A/JTAG.
- 2026-07-12: **F5 (IPMI backbone) — LAN IPMI PASS in QEMU *and* on the real
  AST2050 in 64 MB.** Branch `claude/bmc-f5-ipmi`. The F5 mask set flips F1's
  polarity: **mask bmcweb** (F1's RAM hog) + sensors + entity-manager + LPC snoop
  + desktop extras; **keep** the lightweight IPMI stack (`ipmid` router +
  `netipmid` RMCP+ LAN + `sel-logger` + FRU + inventory + host/chassis state
  managers). `f5_masked_daemons.py` profiles: `lan` (14 masks, QEMU), `host`
  (keep the BT bridge), `realhw` (24 masks — `lan` + RAM-hog extras
  timesyncd/resolved/Time/Software/cert@{authority,nslcd}/4x eeprom-read).
  * **QEMU (`f5-ipmi-test.py`, CI-suitable, exit-coded):** boots the fuller image
    over NFS at `mem=64`, forwards guest UDP/623 via slirp, drives the real
    `ipmitool -I lanplus` client. PASS — `mc info`, `chassis status`, `chassis
    power status`, `lan print 1`, `sel info/list`, `sdr list`, `user list 1` all
    rc=0 over RMCP+ (cipher 17, root=ADMINISTRATOR); `fru print` enumerates 12
    FRU devices (data absent = no I2C EEPROM in QEMU). Evidence
    `evidence/qemu/*.txt`.
  * **Real AST2050 (`f5-realhw-capture.py` from the Pi -> 192.168.66.2):** the
    **KEY F5 result** — the bmcweb-masked fuller image **boots stably over NFS in
    the real 64 MB** (where F1's bmcweb-kept image froze) and the SAME IPMI suite
    answers over RMCP+: `mc info`/`chassis status`/`chassis power status`/`lan
    print 1` (real MAC 96:0e:ce:b9:5d:8d, gw 192.168.66.1, cipher 17, root=ADMIN)
    /`sel info/list`/`sdr list`/`user list` all rc=0; `fru print` enumerates
    devices. Evidence `evidence/real-hw/*.txt`. **Validates the user's 64 MB
    hypothesis: IPMI is the real-HW path.**
  * **netipmid socket-activation race (real HW):** the q71l image enables BOTH the
    standalone `phosphor-ipmi-net@eth0.service` (multi-user.target.wants) AND the
    `.socket`. On the slow real board the standalone service starts `netipmid`
    *before* the network settles, so it runs but never binds UDP/623 and
    socket-activation then never re-triggers (service already "active"). Fix in
    `f5-realhw-mask.py apply`: remove the standalone `.service` enablement, leaving
    pure socket-activation (first RMCP+ packet cleanly spawns a bound netipmid;
    the capture warms it up + retries). QEMU booted fast enough to bind either way.
    **Verified:** a second fresh P2A boot with the fix auto-activated netipmid with
    **no** manual restart — the full suite PASSED from the warmup probe alone.
  * **Data gaps (not mechanism):** `mc info` shows all-zero IDs because the image
    ships a zeroed `/usr/share/ipmi-providers/dev_id.json`; `fru print` is empty
    (no populated I2C FRU EEPROMs). The IPMI *command paths* all work; populating
    dev_id (set manuf/prod/rev) + real FRU EEPROMs is data, done in the image
    recipe / on real HW, not a daemon fix.
  * **Host-side KCS/BT (goal 2) — remaining:** the boot DTB has `lpc@1e789000`
    (lpc-ctrl + lpc-snoop) but **no `kcs`/`bt` child nodes**, so the kernel
    creates no `/dev/ipmi-kcs*` or `/dev/ipmi-bt`; `btbridged`
    (`org.openbmc.HostIpmi`) has no device to bind (masked in the lan profile).
    Enabling it needs (a) a `kcs`/`bt` node in the DTS + (b) the QEMU aspeed LPC
    model to service those registers. LAN IPMI needs none of this and is the
    real-HW path, so host-KCS is documented as the follow-up (see
    `HOST-KCS-BT-STATUS.md`).
- 2026-07-12: **F3 SENSORS DONE in QEMU — real fan/voltage/temp values over IPMI
  from a faithful W83795G model** (branch `claude/bmc-f3-sensors`; QEMU submodule
  branch `claude/w83795-sensor`). Chain proven end-to-end in QEMU:
  * **QEMU model** — `hw/sensor/w83795.c` (new) on `kgpe-d16-bmc` i2c1@0x2f:
    faithful bank-switched W83795G (Bank-Select, vendor/chip/device id, coreboot
    channel-enable regs, measurement regs, the shared VRLSB LSB latch). The
    mainline `w83795` driver binds (`w83795 1-002f`) and reads the modelled values
    exactly via sysfs: fan1-6 = 4963/5113/4804/3600/3750/3901 RPM, VCORE 1.00 V,
    3V3/3VSB 3.30 V, VBAT 3.04 V, CPU diode 42.25 °C, 2 SB-TSI DTS 45/47 °C.
  * **DTS + kernel** — `&i2c1` `hwmon@2f` node + `CONFIG_SENSORS_W83795[_FANCTRL]`.
  * **The blocker + fix** — mainline `drivers/hwmon/w83795.c` uses the LEGACY
    `hwmon_device_register()`, so the sensor files land on the i2c client
    (`hwmonN/device/`), `hwmonN` is nameless, and phosphor-hwmon (reads
    `hwmonN/<type>N_input` + `hwmonN/name`) shows every sensor `disabled`. Kernel
    patch `0003` converts it to `hwmon_device_register_with_info()` exposing the
    `*_input` channels — the fix applies identically to real HW.
  * **OpenBMC → IPMI** — `w83795-hwmon.conf` (installed at the OF path
    `.../i2c-bus@80/hwmon@2f.conf`) maps the channels onto the image's SDR names;
    phosphor-hwmon then publishes them on D-Bus and **`ipmitool -I lanplus sdr`
    over LAN reads 23 sensors `ok`** with real values (fan1=4900 RPM …
    p3v3=3.26 V, p5v=4.99 V, p12v=11.97 V, pvcc_cpu0=0.96 V, vbat=3.01 V,
    temp1=41.9 °C, temp2_inlet=44.97 °C) vs the committed baseline where all were
    `disabled`. Evidence: `evidence/qemu-sensors/`.
  * **Redfish** — sensors are on D-Bus but `/redfish/v1/Chassis` is empty (bmcweb
    surfaces sensors only via a Chassis inventory, which the q71l-based image does
    not provide for this board — an entity-manager gap; IPMI is the working path).
  * **Real HW** — the live board (F5 image, no w83795 node) shows the same
    `disabled` baseline (`evidence/real-hw-sensors/`); the real W83795G is present
    (hardware inventory). Full real-HW read = the proven QEMU flow on the F3
    kernel; **deferred** (rig in active non-disruptive use by F4; reboot would
    displace F5 evidence). Tool `f3-realhw-sensors.py` ready (deploy/capture/revert).
  Tests: `f3-sensor-test.py` (CI QEMU). Doc: `F3-SENSORS.md`. Naming caveat: SDR
  names are the q71l build defaults; kgpe-d16-proper names need an image rebuild.
  ALL 23 sensor values are CORRECT on D-Bus (`evidence/.../dbus-sensor-values.txt`:
  fans 4963-3901 RPM, temps 42.25/45/47 °C, volts 12/5/3.3/3.036/1/1.5/1.1 V) —
  the few `sdr` entries that print 0 are just the q71l static-SDR M/B scaling
  formulas not matching our rails (an image-build artifact, not a read error).
  REMAINING: (a) real-HW W83795 read once the rig is free; (b) upstream the
  hwmon-modernisation patch; (c) Redfish sensors need entity-manager Chassis
  inventory; (d) a kgpe-d16 sensor YAML (image rebuild) for exact SDR names/scaling.
- 2026-07-12: **F4 (Serial-over-LAN) DONE in QEMU + SOL channel verified on real
  HW.** Branch `claude/bmc-f4-sol` (off F5's backbone). Built on the lean 64-MB
  image (F4/`sol` mask profile = F5 `realhw`, console stack KEPT).
  * **Faithful QEMU VUART model** (the real HW contribution): the AST2050 host
    **VUART @0x1E787000** (datasheet §29; Raptor's SOL block) is now modelled —
    `aspeed_ast2400.c` SerialMM 16550, `has_vuart` (G3 only), wired to
    `serial_hd(1)`. Pushed to `mithro/qemu` branch `ast2050-vuart-sol`; submodule
    bumped. DTS enables `&vuart`.
  * **QEMU demo (`f4-sol-test.py`, CI-suitable, PASS):** on the fuller image over
    NFS at mem=64 the kernel binds the VUART ("ttyS5 … is a ASPEED VUART"), the
    udev rule symlinks `/dev/ttyVUART0` + starts `obmc-console@ttyVUART0`
    (`@obmc-console.default`), and host bytes fed into the QEMU VUART chardev are
    **captured over SOL** — 836 bytes / 19 `HOSTLINE` markers via
    `obmc-console-client`. Raw datapath: 360 bytes off `/dev/ttyVUART0`.
    **Redfish SerialConsole advertised** (`/redfish/v1/Systems/system`: IPMI +
    SSH:2200, both ServiceEnabled). Evidence `evidence/qemu-sol/`.
  * **Real AST2050 (from the Pi, non-disruptive, no reboot):** SOL channel
    established — `ipmitool -I lanplus mc info` rc=0 + `sol payload status 1 1` =
    "enabled"; staged `/srv/tftp-bmc/kgpe-g3vic-vuart.dtb` (vuart status=okay),
    ready for a one-step F4 vuart boot. Evidence `evidence/real-hw-sol/`.
  * **GAP — `ipmitool sol activate`** (QEMU + real HW): SOL payload is *enabled*
    but the image ships **no `xyz.openbmc_project.Ipmi.SOL` config-object
    provider**, so netipmid's Activate-Payload D-Bus read of
    `/xyz/openbmc_project/ipmi/sol/eth0` returns `ResourceNotFound`. The SOL
    *bytes* flow regardless (obmc-console-client). Image-recipe follow-up; no
    model/DTS/kernel change needed. Real host-byte capture is separately bounded
    by the FTDI-tapped host COM1 (not VUART-wired). See `F4-SOL-STATUS.md`.
- 2026-07-12: **CONSOLIDATION — all feature branches integrated into
  `claude/bmc-functionality` via real (`--no-ff`) merge commits.** Merge order
  (true dependency order): F1 system-id, F2 power, F5 IPMI backbone, F3 sensors,
  F4 SOL. F5 was merged before F3/F4 because both F3 and F4 branches already
  contained F5 (each had merged it), so merging F5 first keeps it a distinct,
  traceable merge point instead of arriving transitively. F0 (image) and
  research-wiring were already integrated (0 commits ahead) — idempotent no-ops.
  * **DTS union** (`aspeed-bmc-asus-kgpe-d16.dts`): the three features touch
    disjoint regions and auto-merged (ort) — F2 power gpio-line-names + gpio-leds
    + id-button, F3 `&i2c1 hwmon@2f` W83795G node, F4 `&vuart` enable are ALL
    present in the final file.
  * **QEMU submodule union:** F2/F3/F4 each advanced `mithro/qemu` on its own
    single-commit branch off base 583ad3d (power-seq GPIO `8f93ce1`, W83795G
    `46cb5c4`, VUART/SOL `5283f65`). Merged all three (`--no-ff`) into a single
    `claude/bmc-functionality` submodule branch = `a010d69`, which unions the
    three hw/ files on top of the base (ftgmac100 FAST_MODE fix + G3 VIC already
    present). Built `qemu-system-arm` (arm-softmmu) clean; `kgpe-d16-bmc` machine
    + `w83795` device register. Pushed to `mithro/qemu`. Superproject gitlink
    resolved: F2→8f93ce1, F3→7dd9fa6 (F2+F3), F4→a010d69 (full union).
  * **CI workflow union** (`d16-qemu-stack.yml`): auto-merged — jobs
    power-control-test (F2), f5-ipmi-lan (F5), f4-sol (F4) all present.
  * **PROGRESS log:** unioned at every merge (kept all feature entries; dropped
    two redundant "F5 detail is in branch X" pointers from F3/F4 whose target is
    now inlined). No PRs opened.
- 2026-07-12: **F6 USB DONE in QEMU (branch claude/bmc-f6-usb).** KEY FAITHFULNESS
  FINDING: the AST2050 has exactly ONE USB block — the USB2.0 *device / virtual-hub*
  controller @0x1E6A0000 (VIC INT#5); it has NO USB *host* controller (datasheet §9
  memory map p.97 = one USB region; §10 = only "USB2.0 interrupt" INT#5; §15 = only a
  device/vhub). So "connect USB devices" here = the USB *gadget* path (present virtual
  media / HID to the server host during KVM), NOT a host stack; Raptor's astuhci/
  dev-uhci UHCI *host* driver is dead BSP code (no HW backing). F6 = F8-KVM groundwork.
  Wrote F6-USB.md (datasheet + Raptor evidence). The kernel had CONFIG_USB_SUPPORT=n;
  re-enabled USB + the gadget stack (kgpe-d16-usb.config: aspeed-vhub + dummy_hcd +
  configfs mass-storage/HID) + a &vhub DTS node (0x1e6a0000/IRQ5, faithful 7 ports /
  21-EP pool). **No QEMU source change needed** — the existing aspeed.udc-ast2050
  register block already satisfies the driver. DEMO (QEMU, PASS): Linux 6.6.70
  `aspeed_vhub 1e6a0000.usb-vhub: Initialized virtual hub in USB2 mode`, /sys/class/udc
  shows the vhub with 7 downstream ports p1-p7 + dummy_udc.0; a virtual mass-storage
  gadget enumerates in-guest over dummy_hcd (Product 'AST2050 vKVM virtual-media' at
  /sys/bus/usb/devices/1-1/). Deepened the bare-metal fwtest to the §15.4 HUB/DEV/EPP
  init map (6 checks) + integration test (8 pass) + CI boot-usb job + scripts/usb-test.py.
  Evidence under evidence/f6-usb/. REAL-HW: rig unreachable from this build env (not
  exercised; nothing state-mutating done) — everything is QEMU-only, honest in F6-USB.md
  §5. REMAINING (F8-KVM): functional vhub datapath (enumeration/EP DMA/media transport
  presenting a device to the *server host*, not just the dummy_hcd loopback) + likely a
  dedicated G3 UDC driver (AST2050 vhub register file differs from the ast2400 layout).

## F8 — KVM-over-IP: "see the virtual VGA screen and send keyboard events" (2026-07-12)

Branch `claude/bmc-f8-kvm` off `claude/bmc-functionality` @ ca62eba (QEMU submodule
a010d69). Full write-up + datasheet ground truth: **`F8-KVM.md`**.

- **Ground truth (faithfulness-first):** KVM on the AST2050 = three silicon blocks:
  the **Video Engine** @`0x1E700000`/INT#7 (datasheet §20 p.232-255; AST2050-only,
  §1.3.6 p.19) for VGA screen-capture, and the **USB2.0 vhub** @`0x1E6A0000`/INT#5
  (§15) for the virtual HID keyboard/mouse — both already modelled register-accurately
  in QEMU submodule a010d69 (`aspeed.video-ast2050` VR000 key latch + RW regs;
  `aspeed.udc-ast2050`). F8 changed **no QEMU source** — it wired the entire OpenBMC
  (software) side and demonstrated it.
- **What F8 wired:** DTS `&video` enabled (`aspeed,ast2400-video-engine`) + `&vhub`
  enabled with faithful G3 counts (7 ports / 21-EP); kernel `kgpe-d16-kvm.config`
  (V4L2 + `CONFIG_VIDEO_ASPEED` + host-side HID/input) merged with F6's
  `kgpe-d16-usb.config` (gadget stack + `f_hid`); `initramfs/init` `f8kvm` demo;
  runner `scripts/kvm-test.py`; CI `.github/workflows/d16-kvm.yml`.
- **QEMU demonstration (PASS, `-M kgpe-d16-bmc`, 64 MB; evidence/f8-kvm/):**
  * **VIDEO:** `aspeed-video 1e700000.video: irq 24` → **`/dev/video0`** (name
    `aspeed-video`). The mainline V4L2 driver probes the modelled AST2050 engine.
  * **HID:** `aspeed_vhub 1e6a0000.usb-vhub: Initialized virtual hub` (7 G3 ports);
    a **keyboard+mouse gadget** (configfs `f_hid`) enumerates host-side as a real
    **USB HID Keyboard + Mouse**; `/dev/hidg0`+`/dev/hidg1` created; a **keypress
    ('a') report** written to `/dev/hidg0` crosses `dummy_hcd` to the host evdev as
    **`EV_KEY` / `KEY_A`(0x1e) / value=1** (`01 00 1e 00 01 00 00 00`) — the keyboard
    event the user asked to send.
  * Register-model integration tests: `test_video.py` + `test_usb.py` — **5 passed**.
- **obmc-ikvm 64 MB assessment (F8-KVM.md §4):** the daemon+libjpeg footprint fits
  (<1 MB rootfs), but the real constraint is the **32 MB `video_engine_memory`
  carve-out** (every mainline Aspeed BMC DTS reserves 32 MB; inventec uses 64 MB) —
  half the AST2050's 64 MB DRAM. A full capture pipeline (32 MB buffers + VGA
  framebuffer) does **not** comfortably coexist with OpenBMC in 64 MB; a 64 MB vKVM
  needs a reduced buffer budget (smaller region + low-res/quality). Not built (the
  one-Yocto-build rule; F-IMG2 held the slot).
- **Honest boundary:** BMC-only QEMU has **no host VGA source** (video probes + opens
  the device; real capture needs a host emitting VGA + the deferred VR004→JPEG→INT#7
  datapath) and **no real server host** (the keypress is shown over `dummy_hcd`; the
  host-facing vhub path needs a dedicated G3 UDC driver + a functional QEMU vhub
  datapath — the F6/F8 gap). **All QEMU-only; nothing run on the shared AST2050 rig.**
- 2026-07-12: **F7 (host network "piggyback" / NC-SI) DONE — honest finding: the
  KGPE-D16 does NOT use NC-SI** (branch `claude/bmc-f7-ncsi`, off `bmc-functionality`).
  Faithfulness-first ground truth from datasheet + Raptor + DTS: the BMC has its own
  **dedicated RTL8201CP PHY on RMII** (DTS `phy-mode="rmii"`, no `use-ncsi`; Raptor
  `CONFIG_MAC1_PHY_SETTING=0` = "Dedicated PHY (not NC-SI)"), on the same physical
  Ethernet as the host. The G3 MAC has **no NC-SI hardware/register block** (SCU70[8:6]
  is MII/RMII-only); NC-SI on this SoC is pure software over RMII gated by the
  **SCU40[15:14] scratch hint** and is only used by a *different* board (Dell C410X).
  Our faithful QEMU G3 MAC correctly exposes no NC-SI mode and QEMU has **no NC-SI
  responder**, so an "NC-SI comes up" demo would be unfaithful AND unsupported — not
  done, by design. Deliverables: `F7-NCSI.md` (full citations + two-register analysis +
  the honest path), `evidence/qemu-ncsi/` (QEMU boot log of the REAL path: dedicated-PHY
  eth0 up + DHCP over slirp, ZERO NC-SI in dmesg), `f7-ncsi-evidence.py` (buildless
  12-invariant guard + self-contained boot mode; 12/12 pass), and CI job
  `d16-qemu-stack.yml :: f7-ncsi-dedicated-phy`. "Piggyback" for this board = a dedicated
  BMC NIC sharing the host's physical net (already proven: OpenBMC Redfish over
  192.168.66.2). No PR.
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
- 2026-07-12: **F-IMG2 built + DEMONSTRATED in QEMU.** Rebuilt image (OpenBMC master,
  22.7MB squashfs) staged to a NEW export `/export/openbmc-img2` (does NOT touch F5's
  live `/export/openbmc-full`). Booted on the faithful kgpe-d16-bmc QEMU (F3's
  W83795G QEMU + g3vic kernel + vuart DTB, mem=256). Evidence under
  bmc-functionality/evidence/img2/:
  * (a) SOL: busctl -> settingsd owns /xyz/openbmc_project/ipmi/sol/eth0 (full
    Ipmi.SOL property set); `ipmitool sol info 1` rc=0 reads it end-to-end
    (Privilege ADMINISTRATOR, RetryCount 7, Payload Port 623) -- the ResourceNotFound
    cause is fixed. (sol *activate* intermittently hits netipmid's socket-activation
    RMCP+ race, F5's pre-existing issue, not the config-object fix.)  **PASS**
  * (b) SDR: `ipmitool sdr elist` -> all 18 KGPE-D16 rails w/ correct W83795G values
    (CPU_DIODE 41.9C, CPU0/1_DTS, VCORE0/1 0.96V, P12V 11.97V, P5V 4.99V, P3V3 3.26V,
    P1V5/P1V1/P0V9, VBAT 3.01V, FAN1-6).  **PASS**
  * (c) Redfish: `/redfish/v1/Chassis` -> 1 member ASUS_KGPE_D16 w/ Manufacturer=
    ASUSTeK, Model=KGPE-D16, Part/Serial/AssetTag (was empty).  **PASS**
  * (d) mc info: Manufacturer 2623 (ASUSTek Computer Inc.), Product 0x0d16.  **PASS**
  * (d) FRU: motherboard inventory populated (ASUSTeK/KGPE-D16/Part/Serial) via
    phosphor-read-eeprom loading a shipped IPMI FRU blob; two follow-on recipe
    fixes (0x0 inventory-map device-0 mapping + Item.Present=true extra-property)
    to surface it in `ipmitool fru print`.  (3 incremental rebuilds total.)
  Branch pushed; no PRs. Coordination: new NFS export documented; F5's live export
  untouched.
- 2026-07-12: **WAVE-2 CONSOLIDATION — F6/F8/F5b/F7/F9/F-IMG2 integrated into
  `claude/bmc-functionality`** via six real `--no-ff` merge commits (order:
  F6-usb, F8-kvm, F5b-hostkcs, F7-ncsi, F9-fwupdate, F-IMG2). Conflicts were all
  additive-feature UNIONs:
  * **DTS** (`aspeed-bmc-asus-kgpe-d16.dts`): F6 and F8 both enabled `&vhub` — kept
    ONE (F8's fuller comment; identical 7-port/21-EP body); added F8 `&video` and
    F5b `&lpc/kcs@2c`. Final DTS carries all six node-sets (power gpio-line-names +
    gpio-keys, w83795 hwmon@2f, vuart, vhub, video, kcs@2c) and **compiles clean**
    (cpp + dtc 1.7.2 against linux v6.6.70 aspeed dtsi → valid dtb; the only dtc
    warning is the pre-existing G3-VIC `@1e6c0080` unit-address note).
  * **Kernel config**: F6 `kgpe-d16-usb.config` + F8 `kgpe-d16-kvm.config` (separate
    fragments) both wired into `build-kernel.sh` merge_config; F5b's KCS lines
    (`CONFIG_IPMI_KCS_BMC_CDEV_IPMI` + core/aspeed) unioned into shared
    `kgpe-d16.config`.
  * **CI**: `d16-qemu-stack.yml` unions jobs boot-usb (F6), host-kcs (F5b),
    f7-ncsi-dedicated-phy (F7), fw-update (F9) alongside the existing
    f5-ipmi-lan/f4-sol/…; F8's `d16-kvm.yml` kept as its own workflow. YAML parses.
  * **initramfs/init**: both the `f6usb` and `f8kvm` demo blocks kept (distinct
    cmdline gates). **PROGRESS.md**: every feature's entries unioned.
  * **QEMU submodule**: stays at **a010d69** — F6/F8/F5b/F7/F9 needed no QEMU source
    change (they use the existing aspeed.udc-ast2050 / aspeed.video-ast2050 /
    aspeed_lpc_ast2050 models). F6 and F-IMG2 predated the a010d69 bump (gitlink
    583ad3d = a010d69's ancestor), so the 3-way merge kept a010d69 (theirs==base);
    no submodule rebuild needed. Working tree clean; no conflict markers. No PRs.
- 2026-07-12: **F-REVIEW-FIX** (branch `claude/bmc-review-fix` off
  `claude/bmc-functionality`) — closed two F-REVIEW audit findings.
  * **Finding 1 (CI coverage gap):** `f5-ipmi-lan` / `f4-sol` / `fw-update` were
    latent — gated behind `if: workflow_dispatch` **and** downloading an
    `openbmc-full-rootfs` artifact that was never published, so IPMI-over-LAN (the
    only silicon-proven capability), SOL, and fw-update had **no** automatic CI
    guard. Decoupled the multi-hour Yocto rootfs build from the per-push tests:
    the staged fuller rootfs is published out-of-band as the durable Release asset
    `openbmc-full-rootfs.tar` (tag `openbmc-rootfs`) by the new
    `build-openbmc-rootfs.yml` (self-hosted `openbmc-builder`) or by hand
    (`gh release upload`, documented in `.github/workflows/CI-README.md`). The
    three jobs now run on **every push/PR**: a `gh release download` fetch step
    (id=rootfs) runs the test when the asset exists (`::notice::`) or SKIPS with a
    `::warning::` annotation + `$GITHUB_STEP_SUMMARY` block when it doesn't — green
    but visibly SKIPPED, never a faked/silent pass. All workflow YAML validated.
  * **Finding 2 (F2 overclaim):** `f2-power-results.json` shows `PowerState: null`
    for every action, so only the **forward** path (Redfish action → op-pwrctl →
    GPIO latch, HTTP 204 + GPIOH2 over QMP) is proven, not the Redfish `PowerState`
    readback. Softened the "confirmed end to end" summary in `evidence/qemu/
    F2-README.md`, the "-> pgood -> PowerState loop" line here (above), and added a
    proven-vs-designed caveat to `OPENBMC-POWER-INTEGRATION.md` §(b). GPIOH2/QMP +
    the CI fwtest are named as the authoritative signal. Forward path left intact
    (it IS proven). No PRs.
- 2026-07-12: **Final consolidation** — merged the three remaining completed
  branches into `claude/bmc-functionality` with real `--no-ff` merge commits
  (no PRs, no force-push), in least- to most-conflicting order. All three touch
  **disjoint file sets**, so every merge was clean (no conflict markers):
  * `claude/bmc-review` (merge `2a58516`) — additive audit docs only:
    `REVIEW-FINDINGS.md` + `evidence/review-rerun/` spot-check logs.
  * `claude/bmc-review-fix` (merge `aa0814b`) — CI: ungate `f5-ipmi-lan` /
    `f4-sol` / `fw-update` (drop the per-job `workflow_dispatch` gate) + fetch the
    staged rootfs from the GitHub Release asset `openbmc-full-rootfs.tar` with an
    honest run-vs-SKIP guard; new `build-openbmc-rootfs.yml` + `CI-README.md`. The
    other feature jobs (boot-usb / host-kcs / f7-ncsi-dedicated-phy / boot-nfsroot
    / …) are untouched. Also the F2 prose softening (forward-path-only) here, in
    `evidence/qemu/F2-README.md`, and `OPENBMC-POWER-INTEGRATION.md` §(b).
  * `claude/bmc-hwpass` (merge `67b9a2d`) — image ships **kcsbridge** (host-IPMI
    KCS), not btbridged: `obmc-phosphor-image-ast2050-full.bb` installs
    `phosphor-ipmi-kcs` and `IMAGE_INSTALL:remove = "phosphor-ipmi-bt"`, the
    authoritative host-IPMI provider choice (supersedes/completes F-IMG3). Plus
    real-HW evidence under `evidence/real-hw-hwpass/`, `hwpass-boot-and-demo.sh`,
    `hwpass-realhw-capture.py`, and `HWPASS-PROGRESS.md`.
  * Verified: working tree clean, no conflict markers; the image config selects
    `phosphor-ipmi-kcs` (bt dropped); all 6 workflow YAML files parse; the QEMU
    gitlink stays `a010d69` (none of the three touch QEMU source). No PRs.

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

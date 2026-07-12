# F-HWPASS — consolidated real-silicon demonstration (progress log)

Branch `claude/bmc-hwpass` off `claude/bmc-functionality` (ca5caa3). Goal: close
the deferred real-HW sides of F1-F5b on the real ASUS KGPE-D16 / AST2050 in ONE
coordinated session. **No unrecoverable changes; no real flash write.**

## Rig reachability (established 2026-07-12)
- **Pi bridge `ssh asus-bmc` (user claude): REACHABLE.** `rpi4-asus-aspeed2050-dev`,
  eth-bmc 192.168.66.1, eth-host 192.168.77.1 both up; dnsmasq TFTP
  (`/srv/tftp-bmc`) + NFS (`/srv/nfs/openbmc{,-full}`) live.
- **Board BMC 192.168.66.2: UP.** Pingable; `ipmitool -I lanplus … mc info` rc=0
  (after the F5 netipmid socket-activation warmup). It is running **F5's image**
  (all-zero dev IDs = F5's data gap, confirming it is NOT yet the F-IMG2/F-HWPASS
  data-populated image).
- **PXE x86 host root@192.168.77.138 (the KGPE-D16 host, runs culvert for P2A):**
  ping + tcp/22 OPEN, but interactive SSH via the Pi hop is **flaky/hangs** from
  this environment (the sshpass hop stalls; `sshpass -p …` typed directly is also
  hook-blocked). This is the machine that must run `culvert` to drive the P2A
  cold-boot, so an unattended fresh P2A reboot of a new image is at risk (see
  "Phase B decision").

## Phase A — new 64 MB image + artifacts (DONE / in progress)

### KCS host-IPMI bridge swap (F-IMG3 / task #88) — DONE
- **Root cause found:** `meta-quanta/meta-q71l/conf/machine/quanta-q71l.conf`
  hardcoded `PREFERRED_PROVIDER_virtual/obmc-host-ipmi-hw = "phosphor-ipmi-bt"`.
  The machine conf is parsed **after** `local.conf`, so the F0/IMG2 local.conf
  KCS knob never won and every prior build shipped **btbridged** — and BT is not
  drivable on the G3 (block at 0x48 vs the mainline ast2400 0x140). btbridged
  also can never bind, so host-side KCS never worked.
- **Fix (build tree `/home/tim/openbmc`):**
  1. machine conf → `PREFERRED_PROVIDER_virtual/obmc-host-ipmi-hw = "phosphor-ipmi-kcs"`.
  2. image recipe `obmc-phosphor-image-ast2050-full.bb`: explicit
     `OBMC_IMAGE_EXTRA_INSTALL += phosphor-ipmi-kcs` + `IMAGE_INSTALL:remove =
     "phosphor-ipmi-bt"`.
  kcsbridge's own `SYSTEMD_SERVICE = phosphor-ipmi-kcs@ipmi-kcs3.service`
  (`KCS_DEVICE=ipmi-kcs3`) already targets **/dev/ipmi-kcs3** — the F5b DTS
  `kcs@2c` channel. No further wiring needed.
- **Rebuilt (capped: systemd-run MemoryMax=20G + nice/ionice + BB -j4; fully
  sstate-cached except do_rootfs). New image build 20260711192615, ~21.7 MB.**
  Manifest now has **`phosphor-ipmi-kcs`** and **no `phosphor-ipmi-bt`**, plus
  ipmid/netipmid/fru/sel + `kgpe-d16-fru-populate` + `kgpe-d16-hwmon-config` +
  `phosphor-skeleton-control-power` (op-pwrctl) + the F-IMG2 dev_id/SOL/Chassis
  recipes.

### Combined real-HW DTB + rootfs staging — see following commits.

### Combined real-HW kernel + DTB — BUILT
- `qemu-firmware/scripts/build-kernel.sh` built the full-featured kernel
  (`uImage-kgpe-d16`, 3.45 MB) + the **combined DTB**
  (`aspeed-bmc-asus-kgpe-d16.dtb`, 23 645 B) with **all** feature nodes verified
  present: `kcs@2c` (aspeed,ast2400-kcs-bmc-v2), `winbond,w83795g` hwmon@2f,
  `serial@1e787000` vuart, power `power-up-req-n` gpio-line-names. Kernel config
  includes `CONFIG_IPMI_KCS_BMC_CDEV_IPMI` (→ /dev/ipmi-kcs3), `CONFIG_SENSORS_W83795`
  + the modern-hwmon patch 0003, ftgmac100 rxfix (0002), ast2050 clk (0001),
  g3-vic. Copied to `tmp/uImage-kgpe-d16-hwpass` + `tmp/kgpe-hwpass-combined.dtb`.

### Host state — KGPE-D16 x86 host is POWERED ON
- `192.168.77.138` = the KGPE-D16 x86 host, reachable through the Pi, running
  **`Linux 6.18.34-1-lts` (SystemRescue), uptime ~31 h**. It is the culvert P2A
  peer (so P2A boot is viable) AND — being powered — means the W83795 rails/fans
  are LIVE (sensors demo viable) and there is a live host-side KCS peer (host-KCS
  demo viable). (The earlier "host unreachable" impression was a helper stdin/ssh
  bug, not the host.)

### New rootfs staged to the Pi (NEW export, non-disruptive) — DONE
- `stage-openbmc-nfsroot.sh` unpacked build 20260711192615 to `/export/openbmc-hwpass`
  locally (flash units neutralised), tar'd + pushed to **Pi `/srv/nfs/openbmc-hwpass`**
  (a NEW export — **F5's `/srv/nfs/openbmc-full` untouched**). Verified on the Pi:
  `phosphor-ipmi-kcs@ipmi-kcs3.service` enabled in multi-user.target.wants;
  `dev_id.json` = **manuf_id 2623 (ASUSTeK) / prod_id 3350 (0x0D16 KGPE-D16)**;
  86 MB rootfs; NFS export added + `exportfs -ra` live. squashfs also at
  `Pi:/srv/tftp-bmc/openbmc-hwpass.squashfs-xz`.

### Live-board IPMI evidence (F5's running image) — CAPTURED
`evidence/real-hw-hwpass/board-*.txt` (from the Pi, RMCP+ cipher 17):
`mc info` rc=0 (all-zero IDs = F5's un-populated image), `lan print 1` rc=0
(real MAC **96:0e:ce:b9:5d:8d**, gw 192.168.66.1), `chassis status` /
`chassis power status` rc=0 (reports "off" — but F5's kgpe-g3vic.dtb has no
power-state GPIO wired, so this is a default, not a real STA_LINE_POWER read;
the combined DTB fixes that).

## Rig-access outage (2026-07-12, mid-session) — the boot blocker
The rig is reached over a **WireGuard tunnel** (`wg-desktop`, workstation
10.98.5.2/30 → peer 10.98.5.1; WG endpoint `87.121.95.37:51821`). It worked for
the first ~part of the session (live-board mc-info/lan-print capture, the 22 MB
squashfs + 29 MB rootfs push, the Pi-side untar/exportfs/mask staging all
succeeded over it). Then the tunnel went **stale/flapping**: `sudo wg show`
reported *"latest handshake: 18 minutes ago"* (WG re-handshakes every ~2 min
under traffic, so ≥18 min = the rig-side WG endpoint stopped answering). Symptoms:
`ssh asus-bmc` hangs; the FQDN's public A/AAAA (`87.121.95.37`, `2404:e80:…::222/3`)
are firewalled/unreachable on :22; the WG peer `10.98.5.1` = 100% packet loss;
brief up-windows appear then drop. This is a **rig-side infrastructure outage**,
not a workstation problem (8.8.8.8 + the local gateway are up).

**Decision (safety):** a clean P2A NFS-root boot drives ~20 sequential Pi ssh
calls over ~4 min in `linux-boot.py`; over a flapping tunnel a mid-sequence drop
could leave the **shared board hung mid-boot with no recovery channel**. Per the
task's hard safety rule ("STOP if unsure; nothing unrecoverable") the
state-mutating P2A boot was **NOT attempted** over the unstable link. Everything
is staged so it is a single command once the tunnel is stable again:

    bash asus-kgpe-d16-firmware/openbmc/bmc-functionality/hwpass-boot-and-demo.sh

That runbook: stages the kernel+DTB to Pi TFTP, (idempotently) applies the realhw
masks, logs intent to the Pi coordination log, P2A-boots the new stack (retry ×3),
then captures system-id (populated), sensors (host on → live W83795), host-KCS
(host at an OS → `ipmitool -I open`), power status, and SOL — and documents the
F5-config fallback if the boot doesn't come up.

## What was proven on real silicon this session (honest)
* **Rig reached** (`ssh asus-bmc`, board `192.168.66.2` over RMCP+, KGPE-D16 x86
  host `192.168.77.138` powered ON) — real, captured.
* **Live board IPMI** (F5's image): `mc info` (all-zero IDs), `lan print` (real
  MAC 96:0e:ce:b9:5d:8d), `chassis (power) status` — `evidence/real-hw-hwpass/`.
* **New image built + staged on the rig**: kcsbridge wired to /dev/ipmi-kcs3 +
  populated ASUSTeK 2623 / 0x0D16 IDs, at `Pi:/srv/nfs/openbmc-hwpass` (verified
  on the Pi; F5's export untouched).
NOT proven on silicon this session (tunnel outage, honest): booting the new image
→ so populated-`mc info`, `sdr elist` W83795 values, host-KCS round-trip, SOL, and
any host-power action remain STAGED-but-unbooted. Host-power *drive* is separately
bounded by the SCU-pinmux-on-shared-pins hazard (and moot: the host is already on
and is the P2A peer, so turning it off would strand the boot channel).

## Phase B (2026-07-12, tunnel recovered ~05:52Z) — boot attempts + freeze bisect

State re-verified first: Pi up 2d21h (no site power event), board still serving
F5's image (mc info rc=0), x86 host still up (42h RAM-resident SystemRescue),
staged export + TFTP artifacts intact. Rig claimed in the Pi coordination log.

**Boot attempts (all P2A + TFTP + NFS-root):**
| # | kernel | DTB | rootfs | outcome |
|---|--------|-----|--------|---------|
| 1 | uImage-kgpe-d16-hwpass (full) | combined (kcs+vuart+w83795+gpio+vhub+video) | openbmc-hwpass (new) | kernel up, eth0 100M, IP OK, NFS root mounted (rmtab) → **hard froze** minutes into systemd (NFS io flat, ping dead, serial silent) |
| 2 | same | **safe DTB** (vhub+video disabled — never-HW-tested blocks) + seeded 00-bmc-eth0.network | openbmc-hwpass | ~90 s of systemd alive (10/10 pings) → **froze** |
| 3 | **rxfix (F5's proven)** | **kgpe-g3vic.dtb (F5's proven)** | openbmc-hwpass (+ kcsbridge/op-pwrctl masked) | kernel up, ~12+ pings → **froze** |
| 4 | rxfix | kgpe-g3vic.dtb | **openbmc-full (F5's proven, re-masked per F5's doc)** | CONTROL — kernel up, 13/13 then 10/12 pings (~4 min alive) → **froze** |
| 5 | rxfix | kgpe-g3vic.dtb | RAM-only culvert initramfs (raw gzip verified, `initrd=addr,size`) | serial soak 0 bytes on 4/4 pokes (suggestive board-level; culvert-init console-on-ttyS4 behavior unproven → not conclusive) |
| 6 | rxfix | kgpe-g3vic.dtb | openbmc-full (restoration attempt) | final attempt to restore the as-found state |

**CONTROL VERDICT (attempt 4): F5's fully-proven stack — which had run for days
on this exact board — now freezes the same way. The post-outage environment (most
plausibly board-level: marginal DDR2/SoC state; chassis at 59 °C with only fan1
spinning, per the live W83795G read) cannot sustain the boot. The new F-HWPASS
image is exonerated as the freeze cause.** Supporting: Pi dmesg clean (no USB
resets/OOM/NFS errors today), nfsd read counters advanced ~7 MB per attempt then
went flat at each freeze, eth-bmc 0 errors.

**Diagnostics:** attempt-1 console shows the video engine probing real silicon
(`aspeed-video 1e700000.video: irq 24`, jpeg-header alloc) pre-freeze; serial
poke at freeze = **0 bytes** (no getty → hard freeze, not IP loss); Pi dmesg =
**no eth-bmc carrier flaps, 0 link errors** across all attempts (link exonerated);
board did mount the new export. Attempt 3 freezing on F5's exact kernel+DTB means
the freeze follows the **new image** (or a post-outage environment change —
attempt 4 splits that). NB: the F-IMG2-derived image was only ever QEMU-proven at
**mem=256**, never 64 — this exposed that validation gap. x86 host verified
unharmed after each attempt (uptime advancing).

## Phase B decision (safety-bounded)
Key hardware fact (from `HW-WIRING-power-sensors.md` §1.4 + the DTS): the power
request lines B1/F0/B6/H2 are only **named** (`gpio-line-names`) — there is **no
pinctrl/SCU-mux node**, so booting is safe, but *driving* host power needs SCU
pinmux on pins shared with **SPI-flash-busy / I2C7 / video-port**, rated
Medium-confidence and warned to "disturb boot flash or the NIC". Also **all**
remaining host-side demos (sensors-with-host-on, host-KCS, SOL host bytes) are
gated on the host being powered and on a fresh kernel (w83795 patch / kcs-cdev
not in the proven `uImage-kgpe-d16-rxfix`). Per the task's hard safety rule
("STOP if unsure; power on/off only, recoverable"), an unattended first-ever
SCU-pinmux host-power drive + multi-stage P2A reboot driven through a flaky
PXE-host SSH is **not** something to force. Plan: stage everything for a
one-step supervised boot, and capture all reliably-reachable real-HW IPMI
evidence against the live board now.

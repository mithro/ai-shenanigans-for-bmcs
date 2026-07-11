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

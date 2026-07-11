# F0 — fuller OpenBMC image (`obmc-phosphor-image-ast2050-full`) build notes

Task F0 of the "full BMC functionality on the AST2050" program. Builds a fuller
OpenBMC image on **latest upstream master** that adds the features later tasks
(F2–F5…) need, on top of the proven lean Redfish-only image
(`obmc-phosphor-image-ast2050-redfish`). Staged over NFS for the faithful
`kgpe-d16-bmc` QEMU machine; it is **not** flashed to real hardware here.

## OpenBMC version built

- Tree: `/home/tim/openbmc` (Yocto/bitbake, `origin = github.com/openbmc/openbmc`).
- Updated to **latest upstream master** on 2026-07-11:
  `git fetch origin master` then `git merge --ff-only origin/master`.
- **Built commit: `fc5c29842ed99fa1d0a0e43a05fa0dac853e279c`**
  ("meta-facebook: sanmiguel: support dynamic NIC sensor discovery", 2026-07-09) —
  the tip of `origin/master` at build time. No stable-release fallback was needed;
  master parsed and built cleanly for the ARMv5 `quanta-q71l` target.
- Machine: `quanta-q71l` (ast2400, **ARM926EJ-S / ARMv5TE** — the same CPU class as
  the AST2050; the AST2500 `romulus` image is ARMv6 and will not run on the AST2050).

## What the image adds over the Redfish-only image

The recipe `obmc-phosphor-image-ast2050-full.bb` `inherit`s `obmc-phosphor-image`
and keeps the redfish image's features
(`obmc-bmcweb obmc-user-mgmt obmc-network-mgmt obmc-settings-mgmt obmc-inventory
ssh-server-dropbear`), then adds:

| Area | IMAGE_FEATURE / package | Pulls in |
|------|-------------------------|----------|
| IPMI host (KCS) | `obmc-host-ipmi` | `virtual-obmc-host-ipmi-hw` → `phosphor-ipmi-kcs` (kcsbridge), which RRECOMMENDS `phosphor-ipmi-host` (ipmid router) |
| IPMI LAN (RMCP+) | `obmc-net-ipmi` | `phosphor-ipmi-net` |
| IPMI FRU | `phosphor-ipmi-fru` (explicit) | FRU inventory reader / ipmid provider |
| IPMI SEL | `phosphor-sel-logger` (explicit) | system event log |
| SOL / console | `obmc-console` | `obmc-console-server` + `obmc-console-client` |
| Sensors | `obmc-sensors` + `dbus-sensors` + `entity-manager` (explicit) | `phosphor-hwmon` + D-Bus sensor daemons + runtime HW config |
| State mgmt | `obmc-host-state-mgmt` + `obmc-chassis-state-mgmt` | `phosphor-state-manager-{host,chassis,discover}` + `obmc-phosphor-power` |
| POST codes | `phosphor-host-postd` (explicit) | LPC port-80 snoop |

**Excluded on purpose** (RAM/build cost): `obmc-ikvm` (vKVM), `obmc-webui`
(webui-vue/Node.js), telemetry, TPM, DMTF PMCI/SPDM, debug/dev tools.

### Why the explicit packages

`obmc-sensors` only pulls `phosphor-hwmon` (via
`VIRTUAL-RUNTIME_obmc-sensors-hwmon`); the modern D-Bus sensor stack
(`dbus-sensors`, `entity-manager`) and `phosphor-ipmi-fru` / `phosphor-sel-logger`
/ `phosphor-host-postd` are not in any of the enabled packagegroups, so they are
added directly via `OBMC_IMAGE_EXTRA_INSTALL`.

## Required build-config (`build/quanta-q71l/conf/local.conf`)

`local.conf` lives in the OpenBMC tree (outside this git repo); the exact lines are
recorded here so the build is reproducible. On top of the two lines the redfish
README already requires:

```sh
# (redfish image, already present)
DISTROOVERRIDES .= ":df-phosphor-no-webui"      # empties webui RDEPENDS (no Node.js/V8)
INSANE_SKIP:boost-context += "textrel"           # ARMv5 boost::context text relocations

# (F0 full image additions)
BB_NUMBER_THREADS = "4"                           # resource cap (host: 31 GB / 12 cores)
PARALLEL_MAKE = "-j 4"                             # resource cap
PREFERRED_PROVIDER_virtual/obmc-host-ipmi-hw = "phosphor-ipmi-kcs"   # host IPMI = KCS (q71l default is BT)
PACKAGECONFIG:pn-dbus-sensors = "adcsensor fansensor hwmontempsensor" # trim dbus-sensors to this board's sensors
```

The recipe itself adds `MACHINE_FEATURES += "obmc-host-ipmi"` (quanta-q71l leaves
it commented out, so `COMBINED_FEATURES` would otherwise not contain it and the
host-IPMI feature packages would resolve to nothing). `obmc-host-ipmi` is already
in the phosphor `DISTRO_FEATURES`, and `base.bbclass` recomputes `COMBINED_FEATURES`
after the recipe body is parsed, so enabling it in-recipe is sufficient and keeps
the change scoped to this image (the redfish image is untouched).

## Build + stage commands

```sh
cd /home/tim/openbmc
. setup quanta-q71l build/quanta-q71l
# memory-capped, low-priority (see tmp/bb.sh in the F0 worktree):
systemd-run --user --scope -p MemoryMax=20G -p MemoryHigh=18G \
    nice -n 15 ionice -c3 bitbake obmc-phosphor-image-ast2050-full
# -> build/quanta-q71l/tmp/deploy/images/quanta-q71l/
#      obmc-phosphor-image-ast2050-full-quanta-q71l.squashfs-xz

# stage to a NEW local NFS export (does NOT clobber the working redfish export):
asus-kgpe-d16-firmware/qemu-firmware/scripts/stage-openbmc-nfsroot.sh \
    <image>.squashfs-xz /export/openbmc-full
# and mirror to the Pi (asus-bmc:/srv/nfs/openbmc-full) + exportfs -ra
```

## Results

(Filled in as the build/stage completes — see the checklist below and PROGRESS.md.)

- Image size (squashfs-xz):  _TBD_
- IPMI/console/sensor/state binaries present in rootfs:  _TBD_
- Staged at `/export/openbmc-full` and `asus-bmc:/srv/nfs/openbmc-full`:  _TBD_
- Features dropped to fit 64 MB runtime RAM:  _TBD (runtime-mask decisions belong
  to the boot/HW tasks; the image ships all the binaries above)._

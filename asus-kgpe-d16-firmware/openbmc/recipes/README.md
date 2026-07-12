# F-IMG2 board-specific OpenBMC recipes/bbappends

Canonical copies of the KGPE-D16 (AST2050) OpenBMC image customisations that
close the four gaps F1-F5 found (all image-recipe, not model/DTS/kernel). As the
image `README.md` documents, OpenBMC's meta layers live outside this repo, so
these are **copied into** an OpenBMC checkout before building with
`sync-to-openbmc-tree.sh` (idempotent). Each is a bbappend or a small config
recipe so upstream is not patched.

| Gap | Problem | Files | Copied into (OpenBMC tree) | Mechanism |
|-----|---------|-------|----------------------------|-----------|
| **(a) SOL** | `ipmitool sol activate` -> ResourceNotFound: no owner of `/xyz/openbmc_project/ipmi/sol/eth0` (`xyz.openbmc_project.Ipmi.SOL`) | `settings/phosphor-settings-defaults-native.bbappend`, `settings/files/sol-template.yaml` | `meta-phosphor/recipes-phosphor/settings/` | settingsd hosts the SOL config object via a BMC settings template (`SETTINGS_BMC_TEMPLATES`); PDI's `Ipmi/SOL.interface.yaml` says it "will be implemented in phosphor-settings" |
| **(b) SDR** | `ipmitool sdr` shows quanta-q71l names (pvcc_cpu*, p3v3_scaled) not the board rails | `ipmi/q71l-ipmi-sensor-map-native.bbappend`, `ipmi/files/kgpe-d16-sensor.yaml`, `hwmon/kgpe-d16-hwmon-config.bb`, `hwmon/files/hwmon@2f.conf` | `meta-quanta/meta-q71l/recipes-phosphor/ipmi/`, `meta-phosphor/recipes-phosphor/hwmon/` | swap the static-SDR sensor.yaml (`virtual/phosphor-ipmi-sensor-inventory`) to KGPE-D16 rail names + a matching phosphor-hwmon channel map so the names resolve to real W83795G readings |
| **(c) Redfish** | `/redfish/v1/Chassis` empty: no inventory Chassis object | `entity-manager/entity-manager_%.bbappend`, `entity-manager/files/kgpe-d16.json` | `meta-phosphor/recipes-phosphor/configuration/` | entity-manager publishes an `Inventory.Item.Chassis` (Probe:TRUE) + board Asset that bmcweb surfaces as a Chassis |
| **(d) IDs/FRU** | `mc info` IDs zeroed; `fru print` empty | `ipmi/phosphor-ipmi-config.bbappend`, `ipmi/files/dev_id.json`, `ipmi/kgpe-d16-fru-populate.bb`, `ipmi/gen_fru.py`, `ipmi/files/motherboard-fru.bin`, `ipmi/files/kgpe-d16-fru-populate.service` | `meta-phosphor/recipes-phosphor/ipmi/` | real ASUS/KGPE-D16 `dev_id.json` (ASUSTeK IANA PEN 2623); a shipped IPMI FRU blob loaded into the motherboard inventory via `phosphor-read-eeprom` (no emulated EEPROM needed) |

`gen_fru.py` regenerates `files/motherboard-fru.bin` (standard IPMI FRU v1.0,
checksums verified). `sync-to-openbmc-tree.sh` adds the two new packages
(`kgpe-d16-hwmon-config`, `kgpe-d16-fru-populate`) to the image's
`OBMC_IMAGE_EXTRA_INSTALL` **additively**, preserving other agents' in-tree edits.

## Build

```sh
asus-kgpe-d16-firmware/openbmc/recipes/sync-to-openbmc-tree.sh /home/tim/openbmc
cd /home/tim/openbmc && . setup quanta-q71l build/quanta-q71l
systemd-run --user --scope -p MemoryMax=20G -p MemoryHigh=18G \
    nice -n 15 ionice -c3 bitbake obmc-phosphor-image-ast2050-full
```

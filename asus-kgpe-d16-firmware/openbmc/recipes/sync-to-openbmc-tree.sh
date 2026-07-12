#!/bin/bash
# F-IMG2: sync the board-specific OpenBMC recipes/bbappends into an OpenBMC
# checkout's meta layers so `bitbake obmc-phosphor-image-ast2050-full` picks them
# up. The canonical copies live in this repo (recipes/); OpenBMC's meta layers
# live outside the repo, so -- exactly as the image .bb README documents -- we
# copy the files in. Idempotent; run before building.
#
#   ./sync-to-openbmc-tree.sh [OPENBMC_DIR]     (default: /home/tim/openbmc)
set -euo pipefail

OPENBMC="${1:-/home/tim/openbmc}"
HERE="$(cd "$(dirname "$0")" && pwd)"

PH_IPMI="$OPENBMC/meta-phosphor/recipes-phosphor/ipmi"
PH_SET="$OPENBMC/meta-phosphor/recipes-phosphor/settings"
PH_EM="$OPENBMC/meta-phosphor/recipes-phosphor/configuration"
PH_HWMON="$OPENBMC/meta-phosphor/recipes-phosphor/hwmon"
PH_SKEL="$OPENBMC/meta-phosphor/recipes-phosphor/skeleton"
Q71L_IPMI="$OPENBMC/meta-quanta/meta-q71l/recipes-phosphor/ipmi"
PH_IMG="$OPENBMC/meta-phosphor/recipes-phosphor/images"

echo "[sync] OpenBMC tree: $OPENBMC"

# (a) SOL config object -> settingsd BMC template
install -D -m0644 "$HERE/settings/files/sol-template.yaml" \
    "$PH_SET/files/sol-template.yaml"
install -D -m0644 "$HERE/settings/phosphor-settings-defaults-native.bbappend" \
    "$PH_SET/phosphor-settings-defaults-native.bbappend"

# (d) real Device ID -> phosphor-ipmi-config override
install -D -m0644 "$HERE/ipmi/files/dev_id.json" \
    "$PH_IPMI/files/dev_id.json"
install -D -m0644 "$HERE/ipmi/phosphor-ipmi-config.bbappend" \
    "$PH_IPMI/phosphor-ipmi-config.bbappend"

# (d) motherboard FRU present -> ipmi-fru-parser extra-properties
install -D -m0644 "$HERE/ipmi/files/extra-properties.yaml" \
    "$PH_IPMI/files/extra-properties.yaml"
install -D -m0644 "$HERE/ipmi/phosphor-ipmi-fru-properties-native.bbappend" \
    "$PH_IPMI/phosphor-ipmi-fru-properties-native.bbappend"

# (d) motherboard FRU blob + loader service
install -D -m0644 "$HERE/ipmi/files/motherboard-fru.bin" \
    "$PH_IPMI/files/motherboard-fru.bin"
install -D -m0644 "$HERE/ipmi/files/kgpe-d16-fru-populate.service" \
    "$PH_IPMI/files/kgpe-d16-fru-populate.service"
install -D -m0644 "$HERE/ipmi/kgpe-d16-fru-populate.bb" \
    "$PH_IPMI/kgpe-d16-fru-populate.bb"

# (b) kgpe-d16 IPMI SDR sensor map -> q71l sensor-map bbappend
install -D -m0644 "$HERE/ipmi/files/kgpe-d16-sensor.yaml" \
    "$Q71L_IPMI/files/kgpe-d16-sensor.yaml"
install -D -m0644 "$HERE/ipmi/q71l-ipmi-sensor-map-native.bbappend" \
    "$Q71L_IPMI/q71l-ipmi-sensor-map-native.bbappend"

# (d) IPMI FRU device 0 -> motherboard (q71l inventory-map bbappend)
install -D -m0644 "$HERE/ipmi/files/kgpe-d16-fru0.yaml" \
    "$Q71L_IPMI/files/kgpe-d16-fru0.yaml"
install -D -m0644 "$HERE/ipmi/q71l-ipmi-inventory-map-native.bbappend" \
    "$Q71L_IPMI/q71l-ipmi-inventory-map-native.bbappend"

# (b) matching phosphor-hwmon config recipe
install -D -m0644 "$HERE/hwmon/files/hwmon@2f.conf" \
    "$PH_HWMON/files/hwmon@2f.conf"
install -D -m0644 "$HERE/hwmon/kgpe-d16-hwmon-config.bb" \
    "$PH_HWMON/kgpe-d16-hwmon-config.bb"

# (c) entity-manager Chassis config -> entity-manager bbappend
install -D -m0644 "$HERE/entity-manager/files/kgpe-d16.json" \
    "$PH_EM/files/kgpe-d16.json"
install -D -m0644 "$HERE/entity-manager/entity-manager_%.bbappend" \
    "$PH_EM/entity-manager_%.bbappend"

# (F2-STA #95) host-power GPIO map for op-pwrctl -> obmc-libobmc-intf bbappend.
# The upstream recipe ships an empty stub gpio_defs.json, which makes op-pwrctl
# (org.openbmc.control.Power) crash at gpio_configs.c:195 (read_gpios assert) so
# nothing publishes `pgood` and chassis power always reports Off. This override
# installs the real KGPE-D16 map (PGOOD=GPIOH2 in / B1,F0,B6 out) instead.
install -D -m0644 "$HERE/power/files/gpio_defs.json" \
    "$PH_SKEL/files/gpio_defs.json"
install -D -m0644 "$HERE/power/obmc-libobmc-intf_%.bbappend" \
    "$PH_SKEL/obmc-libobmc-intf_%.bbappend"

# image .bb: add our two config packages ADDITIVELY (do not clobber other
# agents' in-tree edits, e.g. F2's phosphor-skeleton-control-power). Insert the
# two package lines after entity-manager if they are not already present.
IMG="$PH_IMG/obmc-phosphor-image-ast2050-full.bb"
if [ -f "$IMG" ]; then
    for pkg in kgpe-d16-hwmon-config kgpe-d16-fru-populate; do
        if ! grep -q "$pkg" "$IMG"; then
            sed -i "s|^\( *\)entity-manager \\\\|\1entity-manager \\\\\n\1$pkg \\\\|" "$IMG"
            echo "[sync] image .bb: added $pkg"
        else
            echo "[sync] image .bb: $pkg already present"
        fi
    done
else
    echo "[sync] WARNING: image recipe not found at $IMG"
fi

echo "[sync] done."

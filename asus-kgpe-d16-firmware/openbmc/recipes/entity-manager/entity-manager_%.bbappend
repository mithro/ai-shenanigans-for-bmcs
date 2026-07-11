# F-IMG2 (c): entity-manager Chassis inventory for the ASUS KGPE-D16.
#
# /redfish/v1/Chassis was an empty collection because no D-Bus object implemented
# an inventory Chassis interface. bmcweb's chassis handler enumerates objects
# implementing xyz.openbmc_project.Inventory.Item.Chassis (or
# Inventory.Item.Board.Motherboard). entity-manager publishes exactly such an
# object from a configuration whose Probe matches; ours uses "Probe":"TRUE" so it
# always instantiates on this board (no host FRU EEPROM to probe in QEMU).
#
# The config also carries the board FRU/identity via the Inventory.Decorator.Asset
# interface (Manufacturer=ASUSTeK, Model=KGPE-D16, Serial, Part) so bmcweb surfaces
# it under the Chassis and the data lands on the D-Bus inventory (feeds gap (d)).
# It declares the W83795G under Exposes for documentation/topology; the sensor
# *values* are surfaced over IPMI via phosphor-hwmon + the kgpe-d16 SDR map
# (gap (b)) -- dbus-sensors has no W83795G backend.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI += "file://kgpe-d16.json"

do_install:append() {
    install -d ${D}${datadir}/entity-manager/configurations
    install -m 0644 ${UNPACKDIR}/kgpe-d16.json \
        ${D}${datadir}/entity-manager/configurations/kgpe-d16.json
}

FILES:${PN}:append = " ${datadir}/entity-manager/configurations/kgpe-d16.json"

# F-IMG2 (d): make `ipmitool fru print` return the motherboard identity.
#
# q71l-ipmi-inventory-map-native provides virtual/phosphor-ipmi-fru-inventory
# (config.yaml), which phosphor-ipmi-host compiles into its FRU handler and
# phosphor-read-eeprom uses to know which inventory path each fruid maps to. The
# q71l map has no 0x0 entry, so IPMI FRU device 0 ("Builtin FRU Device", which
# `ipmitool fru print` always probes) had no data even though the motherboard
# inventory is populated. Append a 0x0 -> /system/chassis/motherboard mapping (the
# same path kgpe-d16-fru-populate fills via fruid 0x56) so device 0 shows the
# board FRU. Appending keeps every existing q71l FRU device intact.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI += "file://kgpe-d16-fru0.yaml"

do_install:append() {
    cat ${UNPACKDIR}/kgpe-d16-fru0.yaml >> ${D}${config_datadir}/config.yaml
}

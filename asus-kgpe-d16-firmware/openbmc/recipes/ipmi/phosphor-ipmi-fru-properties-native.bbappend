# F-IMG2 (d): set Inventory.Item Present=true for the motherboard FRU so
# `ipmitool fru print` (which gates on isFruPresent) returns the board areas.
# phosphor-ipmi-fru-properties-native provides virtual/phosphor-ipmi-fru-properties
# (extra-properties.yaml), compiled into phosphor-read-eeprom's inventory update.
# Prepend our files/ dir so our extra-properties.yaml (with the motherboard
# Present=true) replaces the example one.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

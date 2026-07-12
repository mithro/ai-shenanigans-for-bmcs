# F-IMG2 (d): populate the IPMI Get-Device-ID block for `ipmitool mc info`.
#
# The upstream phosphor-ipmi-config ships dev_id.json with every field zeroed,
# so `ipmitool mc info` reports Manufacturer ID 0 / Product ID 0. Override it
# with the real ASUS KGPE-D16 identity by prepending our files/ dir (the recipe
# already has `file://dev_id.json` in SRC_URI, so bitbake picks ours first).
#
# Field values (files/dev_id.json):
#   id               1     Device ID (vendor-chosen controller id)
#   revision         1     Device Revision; bit7=0 => static SDR repo (our model)
#   addn_dev_support 143   0x8F = Chassis(0x80)+FRU(0x08)+SEL(0x04)+SDR(0x02)+Sensor(0x01)
#   manuf_id         2623  IANA Private Enterprise Number of ASUSTeK Computer Inc.
#   prod_id          3350  0x0D16 -- project product id, mnemonic for "KGPE-D16"
#   aux              0     Auxiliary firmware revision (unused)
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

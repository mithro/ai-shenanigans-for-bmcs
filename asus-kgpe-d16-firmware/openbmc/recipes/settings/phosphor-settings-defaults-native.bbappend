# F-IMG2 (a): SOL config object provider for the KGPE-D16 AST2050 image.
#
# phosphor-settings-defaults-native generates settingsd's compiled-in defaults
# (defaults.yaml -> settings_manager.hpp). Its do_install concatenates every
# file named in SETTINGS_BMC_TEMPLATES onto defaults.yaml, so settingsd
# (xyz.openbmc_project.Settings) will own /xyz/openbmc_project/ipmi/sol/eth0
# with interface xyz.openbmc_project.Ipmi.SOL.
#
# This is the missing piece for `ipmitool -I lanplus sol activate`: netipmid's
# Activate-Payload resolves the object's service via the ObjectMapper and reads
# its properties; with no owner it returned ResourceNotFound. See
# files/sol-template.yaml for the property set and the mechanism.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI += "file://sol-template.yaml"
SETTINGS_BMC_TEMPLATES:append = " sol-template.yaml"

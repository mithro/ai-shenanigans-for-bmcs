DESCRIPTION = "Stripped OpenBMC image for the ASUS KGPE-D16 AST2050 BMC \
(ARM926EJ-S, 64 MB DDR2): the Redfish API (bmcweb) only. Deliberately omits the \
web UI (webui-vue/Node.js), vKVM (obmc-ikvm), IPMI, host/chassis management, \
sensors, fan control, telemetry, TPM, DMTF PMCI/SPDM, dev/debug tools and \
logging extras, so the running system fits in the AST2050's real 64 MB and boots \
over NFS on the faithful kgpe-d16-bmc QEMU machine. Full phosphor stays on the \
AST2500 romulus demo; this board gets the lean Redfish image."
LICENSE = "Apache-2.0"

inherit obmc-phosphor-image

# The /etc/version file is misleading and not useful; rely on /etc/os-release.
ROOTFS_POSTPROCESS_COMMAND += "remove_etc_version"

IMAGE_LINGUAS = ""

# Minimal feature set: the Redfish web server (bmcweb) plus only what it needs to
# boot and answer -- user management (Redfish auth), network + settings, a basic
# inventory/object-mapper, and an SSH console. Everything memory-heavy that the
# full obmc-phosphor-image pulls in is intentionally left out (see DESCRIPTION).
# Dropping obmc-webui also removes the multi-hour nodejs-native/V8 build.
IMAGE_FEATURES += " \
        obmc-bmcweb \
        obmc-user-mgmt \
        obmc-network-mgmt \
        obmc-settings-mgmt \
        obmc-inventory \
        ssh-server-dropbear \
        "

# shadow provides useradd/usermod needed by phosphor-user-manager.
ROOTFS_RO_UNNEEDED:remove = "shadow"

DESCRIPTION = "Fuller OpenBMC image for the ASUS KGPE-D16 AST2050 BMC (ARM926EJ-S, \
64 MB DDR2). Extends the lean Redfish-only image \
(obmc-phosphor-image-ast2050-redfish) with the BMC-management features that later \
bring-up tasks need: host + LAN IPMI (phosphor-ipmi-host / -kcs / -net / -fru plus \
phosphor-sel-logger), serial-over-LAN (obmc-console), sensors (dbus-sensors + \
phosphor-hwmon + entity-manager) and host/chassis state management \
(phosphor-state-manager + phosphor-host-postd). It deliberately still omits the web \
UI (webui-vue/Node.js) and vKVM (obmc-ikvm) so the running system stays bootable in \
the AST2050's real 64 MB over NFS on the faithful kgpe-d16-bmc QEMU machine. Build \
for the ast2400 quanta-q71l machine (ARM926EJ-S/ARMv5TE = the AST2050 CPU); the \
AST2500 romulus image is ARMv6 and will not run on the AST2050."
LICENSE = "Apache-2.0"

inherit obmc-phosphor-image

# The /etc/version file is misleading and not useful; rely on /etc/os-release.
ROOTFS_POSTPROCESS_COMMAND += "remove_etc_version"

IMAGE_LINGUAS = ""

# This image is NFS-root only (staged with stage-openbmc-nfsroot.sh and served to
# the faithful kgpe-d16-bmc QEMU machine); it is never flashed to the board's 32 MB
# NOR. The quanta-q71l machine default IMAGE_FSTYPES is the static NOR flash layout
# ("mtd-static mtd-static-tar mtd-static-alltar"), whose do_generate_static packs a
# shared kernel+initramfs fitImage into a fixed flash partition. On latest OpenBMC
# master that fitImage is ~91 KB over the quanta-q71l flash-kernel partition, so the
# static-NOR assembly fails -- an artefact of that board's small flash, irrelevant
# to our unlimited NFS root. Emit only the read-only squashfs-xz rootfs that the NFS
# staging needs; this also skips the multi-artefact NOR packaging entirely.
IMAGE_FSTYPES = "squashfs-xz"

# quanta-q71l does NOT enable obmc-host-ipmi in MACHINE_FEATURES (it is commented
# out in meta-quanta/meta-q71l/conf/machine/quanta-q71l.conf), so COMBINED_FEATURES
# (= DISTRO_FEATURES INTERSECT MACHINE_FEATURES) lacks it and FEATURE_PACKAGES_
# obmc-host-ipmi / -net-ipmi would otherwise resolve to nothing. Add it here:
# obmc-host-ipmi is already in the phosphor DISTRO_FEATURES (phosphor-base.inc), and
# base.bbclass recomputes COMBINED_FEATURES after this recipe body is parsed, so this
# is sufficient to turn the host-IPMI feature packages on for this image only.
# The KCS-vs-BT host-IPMI channel provider is selected in build/<machine>/conf/
# local.conf via PREFERRED_PROVIDER_virtual/obmc-host-ipmi-hw = "phosphor-ipmi-kcs"
# (documented in bmc-functionality/BUILD-NOTES.md).
MACHINE_FEATURES += "obmc-host-ipmi"

# Redfish + management feature set. On top of the redfish-only image's
# bmcweb/user/network/settings/inventory/ssh, this adds:
#   obmc-host-ipmi            -> virtual-obmc-host-ipmi-hw (phosphor-ipmi-kcs, which
#                               RRECOMMENDS phosphor-ipmi-host = the ipmid router) --
#                               host-side KCS IPMI
#   obmc-net-ipmi             -> phosphor-ipmi-net -- IPMI over LAN (RMCP+)
#   obmc-console              -> obmc-console (server + client) -- serial-over-LAN
#   obmc-sensors              -> phosphor-hwmon -- hwmon/I2C sensors
#   obmc-host-state-mgmt      -> phosphor-state-manager-host + -discover
#   obmc-chassis-state-mgmt   -> phosphor-state-manager-chassis + obmc-phosphor-power
IMAGE_FEATURES += " \
        obmc-bmcweb \
        obmc-user-mgmt \
        obmc-network-mgmt \
        obmc-settings-mgmt \
        obmc-inventory \
        obmc-host-ipmi \
        obmc-net-ipmi \
        obmc-console \
        obmc-sensors \
        obmc-host-state-mgmt \
        obmc-chassis-state-mgmt \
        ssh-server-dropbear \
        "

# Packages the feature packagegroups above do not pull in but the task requires:
#   phosphor-ipmi-fru   - IPMI FRU inventory reader (also the default ipmid provider
#                         via VIRTUAL-RUNTIME_phosphor-ipmi-providers)
#   phosphor-sel-logger - IPMI SEL / system event log
#   phosphor-host-postd - LPC port-80 POST-code snoop
#   dbus-sensors        - modern D-Bus sensor daemons (entity-manager driven);
#                         PACKAGECONFIG trimmed in local.conf to the daemons this
#                         board actually uses (adc/fan/hwmon-temp) to save RAM
#   entity-manager      - runtime hardware configuration provider for dbus-sensors
OBMC_IMAGE_EXTRA_INSTALL:append = " \
        phosphor-ipmi-fru \
        phosphor-sel-logger \
        phosphor-host-postd \
        dbus-sensors \
        entity-manager \
        "

# shadow provides useradd/usermod needed by phosphor-user-manager.
ROOTFS_RO_UNNEEDED:remove = "shadow"

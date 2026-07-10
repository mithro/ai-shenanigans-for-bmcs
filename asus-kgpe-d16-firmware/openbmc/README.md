# Stripped Redfish-only OpenBMC for the AST2050 (64 MB)

The ASUS KGPE-D16 AST2050 BMC has **64 MB of DDR2** (hardware-verified: the DDR2
chip is 4-bank/64 MB, `MCR04=0x585`, and reads alias mod 64 MB — see
`../DDR2-INIT-REVERSE-ENGINEERING.md`, `../ast2050.h` `PHYS_SDRAM_1_SIZE`, and the
culvert P2A results). Modern *full* OpenBMC (phosphor + bmcweb + **webui-vue** +
IPMI + vKVM + telemetry + …) does not fit in 64 MB, so booting it at 128/256 MB
would misrepresent the hardware.

This directory holds a **stripped image that fits the real 64 MB**: the Redfish
API (`bmcweb`) plus only the phosphor services it needs to boot and answer —
nothing else.

## `obmc-phosphor-image-ast2050-redfish.bb`

A minimal `obmc-phosphor-image` variant. It `inherit obmc-phosphor-image` (the
class, so it gets the OpenBMC systemd/dbus base) but sets a tiny `IMAGE_FEATURES`:
`obmc-bmcweb` + `obmc-user-mgmt` + `obmc-network-mgmt` + `obmc-settings-mgmt` +
`obmc-inventory` + `ssh-server-dropbear`. It omits `obmc-webui` (which pulls
`webui-vue` and a multi-hour `nodejs-native`/V8 build), `obmc-ikvm`, all IPMI,
host/chassis management, sensors, fan control, telemetry, TPM, DMTF PMCI/SPDM,
dev/debug tools and logging extras.

## Build (ARMv5, on the OpenBMC build host)

`bmcweb` and the phosphor stack are built for the ast2400 `quanta-q71l` machine —
an **ARM926EJ-S / ARMv5TE** BMC, the same CPU as the AST2050 (the AST2500
`romulus` image is ARMv6 and will *not* run on the AST2050). Copy this recipe into
`meta-phosphor/recipes-phosphor/images/` of an OpenBMC checkout, then:

```sh
cd ~/openbmc
. setup quanta-q71l build/quanta-q71l

# Two required build-config lines (build/quanta-q71l/conf/local.conf):

# (1) Redfish-only, no web UI. The base packagegroup-obmc-apps still RDEPENDS
#     webui-vue via its -webui subpackage even when obmc-webui isn't a feature;
#     webui-vue drags in a multi-hour nodejs-native/V8 build. OpenBMC's
#     df-phosphor-no-webui override empties that RDEPENDS. (NB: it's driven by
#     DISTROOVERRIDES, not DISTRO_FEATURES.)
echo 'DISTROOVERRIDES .= ":df-phosphor-no-webui"' >> build/quanta-q71l/conf/local.conf

# (2) ARMv5 prerequisite: boost::context's context-switch asm is position-
#     dependent on ARM926, so libboost_context.so has text relocations that
#     Yocto's QA fails on. Harmless for bmcweb, so skip that one QA check.
echo 'INSANE_SKIP:boost-context += "textrel"' >> build/quanta-q71l/conf/local.conf

bitbake obmc-phosphor-image-ast2050-redfish
# -> build/quanta-q71l/tmp/deploy/images/quanta-q71l/
#      obmc-phosphor-image-ast2050-redfish-quanta-q71l.squashfs-xz
```

## Boot it over NFS on the faithful QEMU machine

```sh
# stage the ARMv5 rootfs into a local NFS export (masks the MTD rofs/rwfs overlay)
../qemu-firmware/scripts/stage-openbmc-nfsroot.sh <image>.squashfs-xz /export/openbmc-kgpe-d16
# boot -M kgpe-d16-bmc with our modern kernel + this rootfs over NFS at 64 MB,
# then assert Redfish answers
../qemu-firmware/scripts/openbmc-nfsroot-test.py \
    --qemu ../qemu-firmware/qemu/build/qemu-system-arm \
    --kernel <zImage-kgpe-d16> --dtb <aspeed-bmc-asus-kgpe-d16.dtb> \
    --nfsroot 10.0.2.2:/export/openbmc-kgpe-d16 --mem 64
# PASS = GET https://.../redfish/v1 returns a RedfishVersion
```

This is the faithful "open BMC over TFTP+NFS" for this board: the exact netboot +
NFSv3 transport proven in Phase 6a (C5), now serving real Redfish from a rootfs
that fits the AST2050's 64 MB. For RAM/flash-limited boards the project also
tracks u-bmc/Zephyr (WallaBMC) as even-leaner options.

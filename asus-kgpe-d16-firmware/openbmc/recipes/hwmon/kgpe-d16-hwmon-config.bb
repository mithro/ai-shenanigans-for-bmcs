SUMMARY = "KGPE-D16 W83795G phosphor-hwmon channel->sensor configuration"
DESCRIPTION = "Ships the phosphor-hwmon config for the ASUS KGPE-D16's Nuvoton \
W83795G hardware monitor (BMC I2C bus 1 @0x2f) at the OF full-path where \
70-hwmon.rules looks for it. Maps the W83795G fan/voltage/temperature channels \
onto KGPE-D16-proper D-Bus sensor names (VCORE0/1, P12V, P5V, P3V3, P1V5, P1V1, \
P0V9, VBAT, CPU diode + per-socket DTS) so the kgpe-d16 IPMI static-SDR map \
(kgpe-d16-sensor.yaml) surfaces real readings in ipmitool sdr/sensor."
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COREBASE}/meta/files/common-licenses/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"
PR = "r1"

inherit allarch

SRC_URI = "file://hwmon@2f.conf"
S = "${UNPACKDIR}"

do_install() {
    # OF full-path of the W83795G node in aspeed-bmc-asus-kgpe-d16.dts:
    #   &i2c1 (i2c-bus@80 under bus@1e78a000) -> hwmon@2f
    install -d ${D}${sysconfdir}/default/obmc/hwmon/ahb/apb/bus@1e78a000/i2c-bus@80
    install -m 0644 ${UNPACKDIR}/hwmon@2f.conf \
        ${D}${sysconfdir}/default/obmc/hwmon/ahb/apb/bus@1e78a000/i2c-bus@80/hwmon@2f.conf
}

FILES:${PN} = "${sysconfdir}/default/obmc/hwmon"

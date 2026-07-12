# F-IMG2 (b): replace the quanta-q71l IPMI static-SDR sensor map with the
# KGPE-D16 W83795G map so `ipmitool sdr`/`sensor` report board-proper rail names
# (VCORE0/1, P12V, P5V, P3V3, P1V5, P1V1, P0V9, VBAT, CPU diode + per-socket DTS)
# instead of the q71l defaults (pvcc_cpu*, p3v3_scaled, temp2_inlet ...).
#
# q71l-ipmi-sensor-map-native PROVIDES virtual/phosphor-ipmi-sensor-inventory,
# whose sensor.yaml phosphor-ipmi-host compiles into its static SDR repository.
# We are (deliberately) building the ARMv5 image on the quanta-q71l machine as the
# AST2050 CPU vehicle, so bbappending this recipe is the least-disruptive way to
# swap the map without adding a second provider of the virtual. The SDR name shown
# is the leaf of each `path`; the paths match the phosphor-hwmon LABELs shipped by
# kgpe-d16-hwmon-config. See files/kgpe-d16-sensor.yaml + F3-SENSORS.md.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI += "file://kgpe-d16-sensor.yaml"

do_install() {
    DEST=${D}${sensor_datadir}
    install -d ${DEST}
    install ${UNPACKDIR}/kgpe-d16-sensor.yaml ${DEST}/sensor.yaml
}

# F2-STA (#95): install the KGPE-D16 host-power GPIO map for op-pwrctl.
#
# ROOT CAUSE of "ipmitool chassis status -> System Power: off while the host is
# ON": the upstream obmc-libobmc-intf recipe ships an EMPTY stub gpio_defs.json
# ({"_comments":"This file should be overridden ..."}) to
# /etc/default/obmc/gpio/gpio_defs.json. op-pwrctl (org.openbmc.control.Power,
# power_control.exe) reads that file at startup and asserts on the missing
# gpio_configs:
#     ERROR:gpio_configs.c:195:read_gpios: assertion failed: (configs != NULL)
# so it core-dumps and crash-loops. With no op-pwrctl there is no
# org.openbmc.control.Power `pgood` property, so phosphor-chassis-state-manager
# leaves CurrentPowerState = Off regardless of the real host power -> IPMI/Redfish
# report the host as off. Verified on the real AST2050 (openbmc-hwpass, 2026-07-12):
# with the host ON, GPIOH2 raw data reads 1 (devmem 0x1E780020 bit26=1, dir=input),
# i.e. the state-in line + polarity are CORRECT; the only defect is the missing
# config that op-pwrctl needs to read that line.
#
# FIX: the base recipe already has `file://gpio_defs.json` in SRC_URI and installs
# ${UNPACKDIR}/gpio_defs.json to ${sysconfdir}/default/obmc/gpio/. Prepending our
# files/ dir to the fetch search path makes bitbake pick OUR board gpio_defs.json
# (PGOOD=GPIOH2 in, POWER_UP=B1 / POWER_DOWN=F0 / RESET_OUT=B6 out) instead of the
# stub, so op-pwrctl starts, reads GPIOH2 as active-high pgood, and publishes it.
#
# The board GPIO map is the one documented in
# asus-kgpe-d16-firmware/openbmc/bmc-functionality/{gpio_defs.json,
# HW-WIRING-power-sensors.md,OPENBMC-POWER-INTEGRATION.md}; files/gpio_defs.json
# here is a byte-identical build copy of that reference.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

# ---------------------------------------------------------------------------
# F2 power-DRIVE fix (2026-07-13): the board only grants the BMC power-ON control
# when the control-lockout line GPIOA4 (ASUS_BMC_CTL_LOCKOUT_N) is a real GPIO
# output driven HIGH. Its pad defaults to PHYLINK (SCU74[25]=1), so a stock image
# left it un-controllable -> the board ignored CTL_REQ_POWERUP_N and the host
# could only be force-OFF, never powered ON. And op-pwrctl's held-level drive
# DEADLOCKS the power-on (asserts RESET_OUT until pgood, which never arrives).
#
# FIX (hardware-verified on the real AST2050): reclaim A4 (clear SCU74[25]) + drive
# it high at boot, and drive host power with the board-faithful Raptor PULSE
# sequences (kgpe-power.sh) instead of op-pwrctl's held level.
#   - kgpe-power-gpio-init.service : oneshot; reclaims A4 + de-asserts the request
#                                    lines before any power transition.
#   - kgpe-power.sh                : the on/off/reset PULSE driver (setup() reclaims
#                                    A4 every op).
#   - obmc-power-{start,stop}@.service.d drop-ins : route the phosphor-state-manager
#                                    chassis power transitions through kgpe-power.sh.
# op-pwrctl is kept only for the pgood READ (CurrentPowerState). See
# OPENBMC-POWER-INTEGRATION.md and evidence/real-hw-f2sta/power-on-A4-fix.txt.

SRC_URI:append = " \
    file://kgpe-power.sh \
    file://kgpe-power-gpio-init.service \
    file://obmc-power-start-kgpe.conf \
    file://obmc-power-stop-kgpe.conf \
"

SYSTEMD_SERVICE:${PN}:append = " kgpe-power-gpio-init.service"

do_install:append() {
    install -d ${D}${bindir}
    install -m 0755 ${UNPACKDIR}/kgpe-power.sh ${D}${bindir}/kgpe-power.sh

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${UNPACKDIR}/kgpe-power-gpio-init.service ${D}${systemd_system_unitdir}/

    # systemd drop-ins overriding the phosphor-state-manager power transitions to
    # use the board-faithful PULSE driver instead of op-pwrctl's held level.
    install -d ${D}${systemd_system_unitdir}/obmc-power-start@.service.d
    install -m 0644 ${UNPACKDIR}/obmc-power-start-kgpe.conf \
        ${D}${systemd_system_unitdir}/obmc-power-start@.service.d/kgpe.conf
    install -d ${D}${systemd_system_unitdir}/obmc-power-stop@.service.d
    install -m 0644 ${UNPACKDIR}/obmc-power-stop-kgpe.conf \
        ${D}${systemd_system_unitdir}/obmc-power-stop@.service.d/kgpe.conf
}

FILES:${PN}:append = " \
    ${bindir}/kgpe-power.sh \
    ${systemd_system_unitdir}/kgpe-power-gpio-init.service \
    ${systemd_system_unitdir}/obmc-power-start@.service.d/kgpe.conf \
    ${systemd_system_unitdir}/obmc-power-stop@.service.d/kgpe.conf \
"

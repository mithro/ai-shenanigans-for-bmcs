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

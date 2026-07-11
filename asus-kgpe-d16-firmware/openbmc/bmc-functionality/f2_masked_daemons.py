# /// script
# requires-python = ">=3.9"
# ///
"""Single source of truth for the F2 (host power control) 64-MB daemon-mask set.

Same masked-set pattern as F1 (see ``f1_masked_daemons.py``): the fuller image
ships every BMC daemon, but the real AST2050 has only 64 MB of DDR, so we boot
with the daemons a feature needs and **mask** the rest so ``bmcweb`` stays up.

For **F2 (power control)** we KEEP what F1 masked away — the host + chassis
**state managers** (they own ``xyz.openbmc_project.State.Host`` /
``.State.Chassis`` and drive the ``obmc-chassis-poweron@0`` / ``poweroff@0``
targets) and ``phosphor-discover-system-state@0`` — plus the
``org.openbmc.control.Power@0`` power-control provider (op-pwrctl) that drives
the KGPE-D16 GPIO request lines and senses GPIOH2.  We still mask the big
non-power RAM users: IPMI, dbus-sensors, entity-manager, and LPC snoop.

Mask mechanism (unchanged from F1): one ``systemd.mask=<unit>`` token per unit on
the kernel command line — per-boot, does not mutate the shared NFS rootfs.
"""

# --- daemons MASKED for F2 (not needed for host power control) -----------------
MASK_UNITS = [
    # -- IPMI (host KCS/BT bridge, LAN RMCP+, SEL logger) -- biggest RAM users
    "org.openbmc.HostIpmi.service",              # btbridged (host IPMI bridge)
    "phosphor-ipmi-host.service",                # ipmid (IPMI command router)
    "phosphor-ipmi-net@eth0.service",            # netipmid (IPMI-over-LAN)
    "xyz.openbmc_project.Logging.IPMI.service",  # sel-logger (IPMI SEL)
    # -- Sensors (dbus-sensors) + their config source (entity-manager) --
    "xyz.openbmc_project.EntityManager.service",    # runtime HW config (C++/boost)
    "xyz.openbmc_project.adcsensor.service",        # ADC voltage rails
    "xyz.openbmc_project.fansensor.service",        # fan tach
    "xyz.openbmc_project.hwmontempsensor.service",  # hwmon temperatures
    "xyz.openbmc_project.FruDevice.service",        # I2C FRU EEPROM scanner
    "xyz.openbmc_project.gpiopresence.service",     # gpio-presence-sensor
    # -- POST-code / LPC snoop (host debug) --
    "lpcsnoop.service",
]

# --- daemons KEPT for F2 (host power control needs these) ----------------------
# Documentation only; these are default-enabled (the boot does not touch them).
KEEP_UNITS = [
    # everything F1 keeps for a stable authenticated Redfish in 64 MB ...
    "bmcweb.service / bmcweb.socket",                 # Redfish HTTPS
    "xyz.openbmc_project.ObjectMapper.service",       # D-Bus object mapper
    "xyz.openbmc_project.Settings.service",           # settings manager
    "xyz.openbmc_project.User.Manager.service",       # PAM users -> auth
    "xyz.openbmc_project.Network.service",            # phosphor-network
    "xyz.openbmc_project.State.BMC.service",          # BMC state
    "xyz.openbmc_project.Logging.service",            # phosphor-logging
    # ... plus the power-control stack F2 adds back (masked in F1):
    "xyz.openbmc_project.State.Host@0.service",       # host state manager
    "xyz.openbmc_project.State.Chassis@0.service",    # chassis state manager (pgood)
    "phosphor-discover-system-state@0.service",       # power-on discovery
    "org.openbmc.control.Power@0.service",            # op-pwrctl: GPIO power control
]


def mask_cmdline():
    """Return the `systemd.mask=...` tokens as one space-joined string."""
    return " ".join(f"systemd.mask={u}" for u in MASK_UNITS)


if __name__ == "__main__":
    frag = mask_cmdline()
    print(f"# {len(MASK_UNITS)} masked units, cmdline fragment = {len(frag)} chars")
    print(frag)

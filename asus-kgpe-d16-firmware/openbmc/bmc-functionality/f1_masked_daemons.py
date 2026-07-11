# /// script
# requires-python = ">=3.9"
# ///
"""Single source of truth for the 64-MB daemon-mask set.

The fuller OpenBMC image (`obmc-phosphor-image-ast2050-full`, F0) ships every
BMC daemon (IPMI, sensors, entity-manager, state-managers, ...).  On the real
AST2050 there is only **64 MB of DDR**, and booting that image with *all*
daemons starves `bmcweb` of RAM: its TLS handshakes reset mid-negotiation and it
crash-loops, so Redfish never comes up stably.

For a given feature we therefore boot with only the daemons that feature needs
and **mask** the rest, freeing RAM for `bmcweb`.  This module is that mask set
for **F1 (system identification)** — the minimum that leaves authenticated
Redfish system-id endpoints answering in 64 MB.

Mask mechanism: kernel command line.  systemd honours one `systemd.mask=<unit>`
token per unit; masking on the cmdline is per-boot and does **not** mutate the
(shared, NFS) rootfs — so later features (F2 power, F3 sensors, ...) can unmask
exactly what they need without fighting over the image.  `mask_cmdline()`
renders the tokens.

This is the reusable "masked-set pattern" referenced by the program plan:
later features start from KEEP + this MASK and move units between the two lists.
"""

# --- daemons MASKED for F1 (not needed for system identification) -------------
# Grouped by subsystem; every entry is a real unit in the F0 fuller rootfs
# (enabled via multi-user.target.wants).  Instance units (`@0`, `@eth0`) are
# given with their concrete instance so systemd masks the exact enabled unit.
MASK_UNITS = [
    # -- IPMI (host KCS/BT bridge, LAN RMCP+, SEL logger) -- biggest RAM users
    "org.openbmc.HostIpmi.service",            # btbridged (host IPMI bridge)
    "phosphor-ipmi-host.service",              # ipmid (IPMI command router)
    "phosphor-ipmi-net@eth0.service",          # netipmid (IPMI-over-LAN)
    "xyz.openbmc_project.Logging.IPMI.service",  # sel-logger (IPMI SEL)
    # -- Sensors (dbus-sensors) + their config source (entity-manager) --
    "xyz.openbmc_project.EntityManager.service",   # runtime HW config (C++/boost)
    "xyz.openbmc_project.adcsensor.service",       # ADC voltage rails
    "xyz.openbmc_project.fansensor.service",       # fan tach
    "xyz.openbmc_project.hwmontempsensor.service", # hwmon temperatures
    "xyz.openbmc_project.FruDevice.service",       # I2C FRU EEPROM scanner
    "xyz.openbmc_project.gpiopresence.service",    # gpio-presence-sensor
    # -- POST-code / LPC snoop (host debug, no host running on the BMC alone) --
    "lpcsnoop.service",
    # -- Host + chassis state managers (power control = feature F2, not F1) --
    "xyz.openbmc_project.State.Host@0.service",
    "xyz.openbmc_project.State.Chassis@0.service",
    "phosphor-discover-system-state@0.service",
]

# --- daemons KEPT for F1 (system identification needs these) ------------------
# Documentation only; the boot does not touch these (default-enabled).
KEEP_UNITS = [
    "bmcweb.service / bmcweb.socket",              # Redfish HTTPS (the whole point)
    "xyz.openbmc_project.ObjectMapper.service",    # D-Bus object mapper (bmcweb dep)
    "xyz.openbmc_project.Inventory.Manager.service",  # system/BMC inventory
    "xyz.openbmc_project.Settings.service",        # settings manager (bmcweb dep)
    "xyz.openbmc_project.User.Manager.service",    # PAM users -> Redfish/SSH auth
    "xyz.openbmc_project.Network.service",         # phosphor-network (IP/MAC)
    "systemd-networkd.service",                    #   + kernel network config
    "xyz.openbmc_project.State.BMC.service",       # BMC state (Manager status)
    "xyz.openbmc_project.Software.Manager.service",  # BMC firmware version objects
    "xyz.openbmc_project.Logging.service",         # phosphor-logging (bmcweb LogService)
    "xyz.openbmc_project.Time.Manager.service",    # time sync manager
    "phosphor-certificate-manager@bmcweb.service", # bmcweb TLS cert
    "dropbear / dropbearkey",                       # SSH (evidence pull / debugging)
]


def mask_cmdline():
    """Return the `systemd.mask=...` tokens as one space-joined string."""
    return " ".join(f"systemd.mask={u}" for u in MASK_UNITS)


if __name__ == "__main__":
    frag = mask_cmdline()
    print(f"# {len(MASK_UNITS)} masked units, cmdline fragment = {len(frag)} chars")
    print(frag)

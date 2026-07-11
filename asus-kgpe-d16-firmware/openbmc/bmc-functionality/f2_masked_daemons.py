# /// script
# requires-python = ">=3.9"
# ///
"""F2 (host power control) 64-MB daemon-mask profiles.

Same masked-set pattern as F1 (see ``f1_masked_daemons.py``): the fuller image
ships every BMC daemon, but the real AST2050 has only 64 MB of DDR, so we boot
with the daemons a feature needs and **mask** the rest.

The **backend is identical** for both power-control front-ends: Redfish
``ComputerSystem.Reset`` (bmcweb) and IPMI ``chassis power on/off/cycle/reset``
(phosphor-ipmi-host / netipmid) both set the same
``xyz.openbmc_project.State.Host`` / ``.State.Chassis`` transition, which drives
``obmc-power-start@0`` / ``obmc-power-stop@0`` -> ``org.openbmc.control.Power``
(op-pwrctl) -> the AST2050 GPIO request lines -> the modeled power latch ->
GPIOH2/pgood. Only the front-end daemon differs, so we keep two profiles:

* **qemu** — the *API/Redfish* demo. Keep bmcweb + the host/chassis state
  managers + op-pwrctl; mask IPMI, sensors, entity-manager, LPC snoop. bmcweb is
  the RAM hog, but in QEMU slirp this fits and gives the Redfish loop.

* **realhw** — the *real 64-MB board*. F1 found the fuller image with **bmcweb
  does not fit in the real 64 MB** (its TLS handshakes reset / it crash-loops), so
  on hardware we **drop bmcweb** and drive power over **IPMI** (netipmid is
  lightweight and fits): ``ipmitool -I lanplus -H <bmc> chassis power on|off|
  cycle|reset``. Keep the IPMI host + LAN stack + SEL + the state managers +
  op-pwrctl; mask bmcweb, sensors, entity-manager, LPC snoop.

Mask mechanism (unchanged from F1): one ``systemd.mask=<unit>`` token per unit on
the kernel command line — per-boot, does not mutate the shared NFS rootfs.
"""

# Units that BOTH profiles mask (never needed for power control): sensors +
# entity-manager + LPC snoop.
_MASK_COMMON = [
    "xyz.openbmc_project.EntityManager.service",    # runtime HW config (C++/boost)
    "xyz.openbmc_project.adcsensor.service",        # ADC voltage rails
    "xyz.openbmc_project.fansensor.service",        # fan tach
    "xyz.openbmc_project.hwmontempsensor.service",  # hwmon temperatures
    "xyz.openbmc_project.FruDevice.service",        # I2C FRU EEPROM scanner
    "xyz.openbmc_project.gpiopresence.service",     # gpio-presence-sensor
    "lpcsnoop.service",                             # LPC port-80 POST snoop
]

# IPMI stack (host KCS/BT bridge, LAN RMCP+, SEL logger).
_IPMI_UNITS = [
    "org.openbmc.HostIpmi.service",              # btbridged (host IPMI bridge)
    "phosphor-ipmi-host.service",                # ipmid (IPMI command router)
    "phosphor-ipmi-net@eth0.service",            # netipmid (IPMI-over-LAN)
    "xyz.openbmc_project.Logging.IPMI.service",  # sel-logger (IPMI SEL)
]

# bmcweb (Redfish HTTPS) + its TLS cert manager.
_BMCWEB_UNITS = [
    "bmcweb.service",
    "phosphor-certificate-manager@bmcweb.service",
]

# Profile: qemu (Redfish API path) -- mask IPMI, keep bmcweb.
MASK_UNITS = _MASK_COMMON + _IPMI_UNITS

# Profile: realhw (IPMI path on the tight 64 MB board) -- mask bmcweb, keep IPMI.
MASK_UNITS_REALHW = _MASK_COMMON + _BMCWEB_UNITS

# Kept by BOTH profiles (documentation only; default-enabled):
#   xyz.openbmc_project.State.Host@0 / .State.Chassis@0 / phosphor-discover-
#   system-state@0            -- host + chassis state managers (power targets)
#   org.openbmc.control.Power@0                 -- op-pwrctl: GPIO power control
#   xyz.openbmc_project.ObjectMapper / Settings / User.Manager / Network /
#   State.BMC / Logging                         -- core D-Bus + auth + net

_PROFILES = {"qemu": MASK_UNITS, "realhw": MASK_UNITS_REALHW}


def mask_cmdline(profile="qemu"):
    """Return the `systemd.mask=...` tokens for the given profile."""
    units = _PROFILES[profile]
    return " ".join(f"systemd.mask={u}" for u in units)


if __name__ == "__main__":
    import sys
    prof = sys.argv[1] if len(sys.argv) > 1 else "qemu"
    frag = mask_cmdline(prof)
    units = _PROFILES[prof]
    print(f"# profile={prof}: {len(units)} masked units, "
          f"cmdline fragment = {len(frag)} chars")
    print(frag)

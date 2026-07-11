# /// script
# requires-python = ">=3.9"
# ///
"""F5 (IPMI backbone) 64-MB daemon-mask profiles.

Same masked-set pattern as F1/F2 (see ``f1_masked_daemons.py``): the fuller
OpenBMC image ships every BMC daemon, but the real AST2050 has only **64 MB of
DDR**, so we boot with the daemons a feature needs and **mask** the rest.

F5 is the *IPMI* feature, and per the program's user-guidance pivot IPMI is the
**real-hardware path**: F1 proved the fuller image with ``bmcweb`` does not fit
the real 64 MB (its TLS handshakes reset / it crash-loops), whereas the IPMI
stack (``ipmid`` command router + ``netipmid`` RMCP+ LAN + ``sel-logger`` + FRU)
is far lighter and *does* fit.  So the F5 mask set is essentially F1's but with
the polarity flipped: **mask bmcweb, keep the IPMI stack**.

Two IPMI channels, two profiles:

* **lan** — IPMI-over-LAN (RMCP+), the priority.  Needs **no extra hardware**:
  ``netipmid`` listens on UDP/623.  Keep ``ipmid`` + ``netipmid`` + SEL + FRU +
  inventory + the host/chassis state managers (so ``chassis power`` /
  ``chassis status`` answer); mask ``bmcweb`` (RAM), the host **BT** bridge
  (``org.openbmc.HostIpmi`` / ``btbridged`` — LAN does not use it), sensors,
  entity-manager, LPC snoop, avahi, rsyslog.  This is the set demonstrated in
  QEMU (client = local ``ipmitool`` -> slirp udp/623) and on the real board
  (client = ``ipmitool`` on the Pi -> 192.168.66.2).

* **host** — additionally keep the host IPMI bridge (``org.openbmc.HostIpmi``,
  i.e. ``btbridged``) so a host OS can talk IPMI to the BMC over the LPC BT/KCS
  channel.  NB: this only becomes live once QEMU + the DTS model the AST2050 LPC
  BT/KCS device node (``/dev/ipmi-bt`` or ``/dev/ipmi-kcs*``); until then the
  bridge starts but has no device to bind (documented gap, goal 2).

Mask mechanism (unchanged from F1/F2): one ``systemd.mask=<unit>`` token per unit
on the kernel command line — per-boot, does not mutate the shared NFS rootfs.
"""

# Units masked by BOTH F5 profiles (never needed for IPMI): bmcweb + its TLS
# cert, sensors + entity-manager (F3's job; no I2C/hwmon HW in QEMU anyway),
# LPC POST snoop, and the desktop-y extras (avahi/rsyslog/srvcfg) that just cost
# RAM on the tight board.
_MASK_COMMON = [
    # -- bmcweb (Redfish HTTPS) — the RAM hog F1 proved does not fit 64 MB ------
    "bmcweb.service",
    "bmcweb.socket",
    "phosphor-certificate-manager@bmcweb.service",
    # -- sensors + their runtime config (feature F3; needs real I2C/hwmon HW) ---
    "xyz.openbmc_project.EntityManager.service",    # runtime HW config (C++/boost)
    "xyz.openbmc_project.adcsensor.service",        # ADC voltage rails
    "xyz.openbmc_project.fansensor.service",        # fan tach
    "xyz.openbmc_project.hwmontempsensor.service",  # hwmon temperatures
    "xyz.openbmc_project.gpiopresence.service",     # gpio-presence-sensor
    # -- POST/LPC snoop + desktop extras (pure RAM savings) --------------------
    "lpcsnoop.service",
    "avahi-daemon.service",
    "avahi-daemon.socket",
    "rsyslog.service",
    "srvcfg-manager.service",
]

# The host IPMI bridge (btbridged): host<->BMC IPMI over the LPC BT channel.
# LAN IPMI does not use it, and QEMU/DTS does not model the LPC BT device, so the
# lan profile masks it; the host profile keeps it (goal 2).
_HOST_BRIDGE = [
    "org.openbmc.HostIpmi.service",
]

# Profile: lan (IPMI-over-LAN, the priority) — mask the host BT bridge too.
MASK_UNITS = _MASK_COMMON + _HOST_BRIDGE

# Profile: host (also expose host-side KCS/BT) — keep the host bridge.
MASK_UNITS_HOST = list(_MASK_COMMON)

# --- daemons KEPT for F5 (documentation only; default-enabled) ----------------
# The IPMI stack + the backends the standard ipmitool commands read from:
KEEP_UNITS = [
    "phosphor-ipmi-host.service",                  # ipmid — IPMI command router (D-Bus handlers)
    "phosphor-ipmi-net@eth0.service",              # netipmid — IPMI-over-LAN (RMCP+, UDP/623)
    "xyz.openbmc_project.Logging.IPMI.service",    # sel-logger — IPMI SEL (`sel list`)
    "xyz.openbmc_project.FruDevice.service",       # FRU EEPROM scanner (`fru print`)
    "xyz.openbmc_project.Inventory.Manager.service",  # inventory backend (FRU/`sdr`)
    "xyz.openbmc_project.State.Host@0.service",    # host power state  (`chassis power status`)
    "xyz.openbmc_project.State.Chassis@0.service", # chassis state     (`chassis status`)
    "phosphor-discover-system-state@0.service",    # restores power state on boot
    # core D-Bus + auth + net (shared with every feature)
    "xyz.openbmc_project.ObjectMapper.service",    # D-Bus object mapper
    "xyz.openbmc_project.Settings.service",        # settings manager
    "xyz.openbmc_project.User.Manager.service",    # PAM/IPMI users -> RMCP+ auth
    "xyz.openbmc_project.Network.service",         # phosphor-network (IP/MAC -> `lan print`)
    "systemd-networkd.service",                    #   + kernel network config
    "xyz.openbmc_project.State.BMC.service",       # BMC state
    "xyz.openbmc_project.Software.Manager.service",  # BMC firmware version
    "xyz.openbmc_project.Logging.service",         # phosphor-logging (SEL backend)
    "xyz.openbmc_project.Time.Manager.service",    # time manager
    "dropbearkey.service / dropbear.socket",       # SSH (evidence pull / debugging)
]

_PROFILES = {"lan": MASK_UNITS, "host": MASK_UNITS_HOST}


def mask_cmdline(profile="lan"):
    """Return the `systemd.mask=...` tokens for the given profile."""
    units = _PROFILES[profile]
    return " ".join(f"systemd.mask={u}" for u in units)


if __name__ == "__main__":
    import sys
    prof = sys.argv[1] if len(sys.argv) > 1 else "lan"
    frag = mask_cmdline(prof)
    units = _PROFILES[prof]
    print(f"# profile={prof}: {len(units)} masked units, "
          f"cmdline fragment = {len(frag)} chars")
    print(frag)

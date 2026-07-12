# /// script
# requires-python = ">=3.9"
# ///
"""F4 (Serial-over-LAN) 64-MB daemon-mask profile.

SOL builds directly on the F5 IPMI backbone: the same lean 64-MB masked set, but
we must **keep the console stack** so the host UART is bridged.

The F5 ``realhw`` profile already masks the RAM hogs (bmcweb + sensors +
entity-manager + LPC snoop + timesync/resolved/certs/eeprom reads) and — crucially
— does **not** mask ``obmc-console`` or ``netipmid``.  So the F4 ``sol`` profile is
exactly F5's ``realhw`` set; this module re-exports it and *asserts* the console
daemons are kept, so a future change to the F5 list that accidentally masked the
console would fail loudly here.

Console/SOL plumbing that must stay up (none of these are in the mask list):

* ``obmc-console@ttyVUART0.service`` — obmc-console-server; binds ``/dev/ttyVUART0``
  (the AST2050 VUART @0x1E787000, udev-symlinked by iomem_base) and publishes the
  host console on the abstract socket ``@obmc-console.default`` +
  ``xyz.openbmc_project.Console.default``.  Started by the shipped udev rule
  ``80-obmc-console-uart.rules`` when the VUART tty appears — no unit enable needed.
* ``phosphor-ipmi-net@eth0.service`` — netipmid; its ``sol::Manager`` connects to
  ``@obmc-console.default`` (compile-time ``CONSOLE_SOCKET_PATH``) and exposes SOL
  over RMCP+ (``ipmitool sol``).  Kept by F5.
* ``obmc-console-ssh.socket`` — network console (SSH :2200), the direct client path.

The VUART itself is provided by the DTS (``&vuart`` enabled) + the faithful QEMU
G3 model (``aspeed: model the AST2050 host VUART``); it does not need a daemon.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f5_masked_daemons import mask_units, mask_cmdline as _f5_cmdline  # noqa: E402

# Daemons the SOL feature depends on — must never be masked.
KEEP_FOR_SOL = [
    "obmc-console@ttyVUART0.service",     # obmc-console-server on the host VUART
    "phosphor-ipmi-net@eth0.service",     # netipmid — IPMI SOL over RMCP+
    "obmc-console-ssh.socket",            # network console client path (:2200)
]


def _assert_console_kept(profile="realhw"):
    """Fail loud if the F5 mask set ever grows to mask the console stack."""
    masked = set(mask_units(profile))
    clash = [u for u in KEEP_FOR_SOL if u in masked]
    if clash:
        raise SystemExit(
            f"F4/SOL: the '{profile}' mask set masks console daemons {clash}; "
            "SOL needs them kept. Remove them from f5_masked_daemons.")


def mask_cmdline(profile="realhw"):
    """systemd.mask=... fragment for the SOL profile (= F5 realhw, console kept)."""
    _assert_console_kept(profile)
    return _f5_cmdline(profile)


if __name__ == "__main__":
    prof = sys.argv[1] if len(sys.argv) > 1 else "realhw"
    frag = mask_cmdline(prof)
    print(f"# F4/SOL profile={prof}: {len(mask_units(prof))} masked units "
          f"(console stack KEPT: {', '.join(KEEP_FOR_SOL)})")
    print(frag)

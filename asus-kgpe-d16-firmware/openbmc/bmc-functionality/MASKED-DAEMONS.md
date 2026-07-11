# The 64 MB daemon-mask pattern (reused by every feature F1..F5)

The real ASUS KGPE-D16 AST2050 BMC has **64 MB of DDR2** (hardware-verified).
The fuller OpenBMC image (`obmc-phosphor-image-ast2050-full`, task F0) ships
*every* BMC daemon — IPMI (host + LAN + SEL), the full `dbus-sensors` +
`entity-manager` stack, host/chassis state managers, LPC POST snoop, etc. Booting
that image in 64 MB with **all** daemons running starves `bmcweb`: its TLS
handshakes reset mid-negotiation (`Connection reset by peer` /
`handshake operation timed out`) and it crash-loops, so Redfish never stabilises.

**Pattern:** for a given feature, boot the fuller image but **mask the daemons
that feature does not need**, so `bmcweb` (and the feature's own daemons) have
enough RAM. Each feature starts from the F1 mask set below and moves the units
*it* needs from MASK to KEEP.

## Mechanism — kernel command line (per-boot, non-destructive)

systemd reads one `systemd.mask=<unit>` token per unit from the kernel command
line and masks that unit for the boot (symlink to `/dev/null` in `/run`). This is
preferred over pre-masking symlinks in the rootfs because:

- the rootfs is a **shared NFS export** (QEMU `/export/openbmc-full`, real HW
  `asus-bmc:/srv/nfs/openbmc-full`); editing it would affect every board/agent
  that mounts it, and later features need different masks;
- it is **per-boot and reversible** — nothing on disk changes, so a different
  feature just boots with a different mask list;
- it is auditable — the full set is visible in `dmesg`'s "Kernel command line".

The token list is generated from a single source of truth,
[`f1_masked_daemons.py`](f1_masked_daemons.py) (`mask_cmdline()`), so the QEMU
harness and the real-HW boot use exactly the same set. The 14-unit F1 fragment is
**693 chars**; with the base boot args (~110 chars) the total command line is
~805 chars, under the ARM `COMMAND_LINE_SIZE` limit (1024). If a future feature's
mask list would overflow 1024 chars, fall back to rootfs symlink masking on a
*feature-private* copy of the export.

> Note: masking a `*.service` leaves its companion `*.socket` (e.g.
> `phosphor-ipmi-net@eth0.socket`) with nothing to activate, so systemd logs a
> harmless `Failed to listen on ...socket`. That is expected and does not affect
> `bmcweb`.

## F1 mask set (system identification)

**MASK (14 units)** — not needed to identify the system over Redfish:

| Subsystem | Units | Why maskable for F1 |
|---|---|---|
| IPMI | `org.openbmc.HostIpmi`, `phosphor-ipmi-host`, `phosphor-ipmi-net@eth0`, `xyz.openbmc_project.Logging.IPMI` | IPMI host/LAN/SEL are feature F5, not identity; `ipmid`/`netipmid` are the biggest RAM users |
| Sensors + config | `xyz.openbmc_project.{adcsensor,fansensor,hwmontempsensor,FruDevice,gpiopresence}`, `xyz.openbmc_project.EntityManager` | sensor read-out is F3; `entity-manager` (C++/boost) is heavy |
| POST/LPC | `lpcsnoop` | host POST-code snoop; no x86 host is required to identify the BMC |
| State mgmt | `xyz.openbmc_project.State.Host@0`, `xyz.openbmc_project.State.Chassis@0`, `phosphor-discover-system-state@0` | power/host state is F2 |

**KEEP** — required for authenticated Redfish system identification:

`bmcweb` (+ `bmcweb.socket`), `xyz.openbmc_project.ObjectMapper`,
`…Inventory.Manager`, `…Settings`, `…User.Manager` (auth!),
`…Network` + `systemd-networkd` (IP/MAC), `…State.BMC` (Manager status),
`…Software.Manager` (BMC firmware version), `…Logging`, `…Time.Manager`,
`phosphor-certificate-manager@bmcweb` (TLS), `dropbear`/`dropbearkey` (SSH).

## How each later feature adapts this set

| Feature | Un-mask (move MASK→KEEP) | Keep masked |
|---|---|---|
| F2 power control | `State.Host@0`, `State.Chassis@0`, `phosphor-discover-system-state@0` | IPMI, sensors, lpcsnoop |
| F3 sensors | `adcsensor`/`fansensor`/`hwmontempsensor`, `EntityManager`, `FruDevice` | IPMI, state, lpcsnoop |
| F4 SOL | (obmc-console; already lightweight) | IPMI, sensors, state |
| F5 IPMI | all IPMI units + `Logging.IPMI` (SEL) | sensors, state (unless also demoing) |

Enabling *all* of these at once is exactly the configuration that does not fit
64 MB — which is why the program demonstrates features one at a time on the real
board, masking the rest.

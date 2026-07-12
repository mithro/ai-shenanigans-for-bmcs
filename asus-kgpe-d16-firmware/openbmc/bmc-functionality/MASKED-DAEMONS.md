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

## Reproducing F1

**QEMU** (the CI-shaped test — boots the fuller image at `mem=64` with the mask
set, then asserts the authenticated system-id fields):

```sh
Q=asus-kgpe-d16-firmware/qemu-firmware
uv run asus-kgpe-d16-firmware/openbmc/bmc-functionality/f1-system-id-test.py \
    --qemu   $Q/qemu/build/qemu-system-arm \
    --kernel $Q/kernel/out/uImage-kgpe-d16 \
    --dtb    $Q/kernel/out/aspeed-bmc-asus-kgpe-d16.dtb \
    --nfsroot 10.0.2.2:/export/openbmc-full --mem 64 \
    --evidence-dir asus-kgpe-d16-firmware/openbmc/bmc-functionality/evidence/qemu
```

`/export/openbmc-full` must be NFS-exported to the QEMU slirp gateway `10.0.2.2`
with `insecure,no_root_squash,vers3` (see the C5 `boot-nfsroot` job in
`.github/workflows/d16-qemu-stack.yml` for the exact `exportfs` incantation).

**Real hardware** (read-only capture off the already-booted board):

```sh
uv run asus-kgpe-d16-firmware/openbmc/bmc-functionality/f1-realhw-capture.py \
    --pi asus-bmc --board 192.168.66.2 \
    --evidence-dir asus-kgpe-d16-firmware/openbmc/bmc-functionality/evidence/real-hw
```

The board must be booted on the **fuller** image (`/srv/nfs/openbmc-full`, which
has `root:0penBmc`) with the mask set applied — on real HW the masks are applied
as rootfs symlinks in the export (U-Boot's command line cannot reliably carry the
693-char `systemd.mask=` fragment over the serial-driven `setenv bootargs`):

```sh
# on the Pi, for each unit in f1_masked_daemons.MASK_UNITS:
sudo ln -sf /dev/null /srv/nfs/openbmc-full/etc/systemd/system/<unit>
# ... boot via the culvert P2A recipe (linux-boot.py) ..., then revert:
sudo rm -f /srv/nfs/openbmc-full/etc/systemd/system/<unit>   # restore pristine F0
```

## Real-hardware finding: the fuller image does NOT fit 64 MB over NFS-root

QEMU's `mem=64` gives a clean 64 MB; the **real** AST2050 loses some of its 64 MB
to the video framebuffer and SoC-reserved regions, so its *effective* free RAM is
smaller — and NFS-root needs a working set of free memory for socket buffers and
write-back that competes with the daemons. Two escalating real-HW attempts:

- **Attempt 1 (14-unit `MASK_UNITS`):** cold-boots via P2A, kernel up (`ASPEED
  rev 0x202`), eth0 link-up 100 Mbps, `IP-Config: Complete` at 192.168.66.2,
  **NFS root mounts** (`rmtab` shows `/srv/nfs/openbmc-full`), systemd reads
  ~135 MB — then **hard-freezes** as networkd takes over eth0: NFS-server read
  counter goes flat, eth0 goes **down** (100 % ping loss), console silent, no
  listeners.
- **Attempt 2 (+`MASK_UNITS_REALHW_EXTRA`, 27 units masked):** boots the same way
  but this time eth0 keeps its kernel-static IP (board keeps pinging .2) — yet
  userspace **thrashes**: NFS reads crawl at ~250 KB/min and never reach a
  listener (no 22/80/443). Classic memory-pressure / NFS-reclaim thrash: the
  image simply cannot make progress in the effective RAM.

**Conclusion:** modern OpenBMC's *fuller* image (`obmc-phosphor-image-ast2050-
full`) does not run on the real AST2050's 64 MB over NFS-root, even with 27
daemons masked. This confirms the program-level "64 MB constraint" note — the
path for real silicon is the **lean redfish image** (which boots and serves
Redfish on this board) or a purpose-built stripped image, not the fuller image.
`MASK_UNITS_REALHW_EXTRA` is retained as documentation of how far masking was
pushed; masking alone was **not** sufficient to fit the fuller image on real HW.

The mask set *is* validated to work in QEMU's 64 MB (F1 QEMU PASS) — the fuller
image + masks is a good demonstration vehicle there; it just does not fit the
real board. See `evidence/real-hw/` for the captured real-HW Redfish surface.

**CI wiring:** `f1-system-id-test.py` is exit-coded (0=PASS) and fully
parameterised, so it drops into a job modelled on C5 `boot-nfsroot` — build QEMU,
`exportfs` the rootfs, run the script. The one missing CI input is the **fuller
OpenBMC rootfs** (F0's ~20 MB squashfs): its Yocto build is multi-hour, so it
must be published as a release/artifact and `download-artifact`ed into
`/export/openbmc-full` rather than rebuilt per push. Until that artifact exists,
run the test against the locally staged export.

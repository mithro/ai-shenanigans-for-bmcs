# QEMU demonstration — BMC firmware-update mechanism (results)

Booted the **full OpenBMC** rootfs (`obmc-phosphor-image-ast2050-full`, ARMv5,
bmcweb + ipmid + phosphor-code-mgmt) over NFS on the **faithful `-M kgpe-d16-bmc`
(AST2050)** QEMU machine and characterized the on-board firmware-update surface.
Driver: [`fw-update-demo.py`](fw-update-demo.py). Raw evidence: [`evidence/qemu/`](evidence/qemu/).

**No real flash was written.** The BMC SPI flash is an *emulated* 16 MB image
(disposable QEMU model); the real board was not touched.

- QEMU: `.../qemu-firmware/qemu/build/qemu-system-arm` (submodule `a010d69`, the
  faithful G3 machine), `-M kgpe-d16-bmc`.
- Kernel/DTB: `zImage-kgpe-d16` + `aspeed-bmc-asus-kgpe-d16.dtb` (Linux 6.6.70
  `armv5tejl`, with the ftgmac100 RX fix so slirp DHCP/NFS works).
- Rootfs: `/export/openbmc-full` over NFSv3; `mem=128M`.
  - *Why 128 MB here:* the **fuller** daemon set (bmcweb **and** the full IPMI
    stack **and** phosphor-code-mgmt **and** entity-manager/sensors) plus
    concurrent authenticated Redfish/SSH/IPMI probing is heavier than the lean
    Redfish image. 128 MB gives the interactive probes headroom; the **64 MB fit**
    is a separate, already-validated claim for the *lean* Redfish image
    (`../openbmc/README.md`). This demo is about the update *mechanism*, not the
    memory budget.

## What was proven (all PASS)

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Redfish ServiceRoot answers, advertises UpdateService | `RedfishVersion 1.17.0`; `"UpdateService":{"@odata.id":"/redfish/v1/UpdateService"}` | `redfish-serviceroot.json` |
| 2 | **UpdateService endpoint live** | `@odata.type #UpdateService.v1_11_1`, **`ServiceEnabled:true`**, `HttpPushUri=/redfish/v1/UpdateService/update`, `MultipartHttpPushUri=/redfish/v1/UpdateService/update-multipart`, `MaxImageSizeBytes=31457280` (30 MB) | `redfish-updateservice.json` |
| 3 | **FirmwareInventory has a Software.Version** | 1 member: `/redfish/v1/UpdateService/FirmwareInventory/039d44e1` | `redfish-firmwareinventory.json` |
| 4 | **Image POST accepted → async Task** (simple push URI) | **HTTP 202**, `TaskService/Tasks/0`, `TaskState:Running`, `TaskStatus:OK`, `"The task with Id '0' has started."` | `redfish-post-simple.txt` |
| 5 | **Image POST accepted → async Task** (multipart push URI) | **HTTP 202**, Task 0, `TargetUri=/redfish/v1/UpdateService/update-multipart` | `redfish-post-multipart.txt` |
| 6 | **Staging backend running** | `xyz.openbmc_project.Software.Manager` (pid 165, `/usr/libexec/phosphor-code-mgmt/phosphor-software-manager`); backend binaries: `phosphor-software-manager`, `phosphor-image-updater`, `phosphor-version-software-manager` | `in-bmc-inspection.txt` |
| 7 | **D-Bus Software objects present** | `busctl tree xyz.openbmc_project.Software.Manager` → `/xyz/openbmc_project/software/039d44e1` (the inventory `Software.Version`, = the FirmwareInventory member) and `/xyz/openbmc_project/software/bmc` | `in-bmc-inspection.txt` |
| 8 | **IPMI firmware info over LAN** | `ipmitool mc info` **rc=0**: IPMI 2.0, `Firmware Revision 0.00` (unpersonalized build; identical to the real-HW capture) | `ipmi-mc-info.txt` |
| 9 | BMC firmware version via Redfish | `Managers/bmc` `FirmwareVersion:"none"`, `Model:"OpenBmc"` (matches os-release `VERSION="None"`) | `redfish-managers-bmc.json` |

### The mechanism, end to end (as observed)
`POST <image>` to the push URI → **bmcweb returns HTTP 202** and creates a Redfish
**Task** (`Tasks/0`, `Running`) → hands the image to **phosphor-software-manager**
(running on D-Bus as `xyz.openbmc_project.Software.Manager`), which owns the
`/xyz/openbmc_project/software/*` objects that Redfish surfaces as
`FirmwareInventory`. This is the complete BMC self-update ingest + staging
mechanism, exercised live. A reboot into a new image is **not** needed to prove it.

## Honest boundaries (what the demo does *not* do)

1. **No successful activation.** The POSTed blob is a 4 KB dummy
   (`F9-DUMMY-FIRMWARE-IMAGE…`), so the software-manager's manifest/signature check
   rejects it — correct behaviour. Proving *ingest + Task + backend* does not
   require a valid signed image.
2. **No MTD write target on this boot.** `/proc/mtd` is **empty** and `/dev/mtd*`
   is **absent**: the NFS-root bring-up masks the `obmc-flash-bmc-*` overlay
   services and the emulated SPI flash is not bound to a Linux MTD (the DTS has no
   flash node). So even a *valid* image could not be written to a flash bank on
   this path. Closing this needs a real MTD boot layout (F-IMG2 follow-up), **not**
   a code change — the backend is already present and running.
3. **HPM.1 not supported.** `ipmitool hpm capabilities` → `compcode = d4` (the OEM
   HPM.1 command group is not implemented by this ipmid). Redfish UpdateService is
   the working transfer path; HPM.1 would be an added ipmid provider
   (`ipmi-hpm-capabilities.txt`).
4. **Host BIOS is not reachable from the BMC** on this board (see
   `UPDATE-PATHS.md` §2–§3), so there is no "BMC flashes the BIOS" datapath to
   demonstrate — that is a hardware fact of the KGPE-D16, not a gap in the demo.

## Reproduce

```sh
uv run asus-kgpe-d16-firmware/fw-update/fw-update-demo.py \
  --qemu  .../qemu-firmware/qemu/build/qemu-system-arm \
  --kernel .../kernel/out/zImage-kgpe-d16 \
  --dtb    .../kernel/out/aspeed-bmc-asus-kgpe-d16.dtb \
  --nfsroot 10.0.2.2:/export/openbmc-full --mem 128 \
  --out asus-kgpe-d16-firmware/fw-update/evidence/qemu
```

(The CI `fw-update` job in `.github/workflows/d16-qemu-stack.yml` runs the same
thing with `--mem 128`, gated on the `openbmc-full-rootfs` artifact.)

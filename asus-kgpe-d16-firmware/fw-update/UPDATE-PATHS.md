# Firmware & BIOS update paths — KGPE-D16 / AST2050 (ground truth)

> Goal (user): **"Able to update firmware and BIOS."** This document is the
> update-path ground truth for the ASUS KGPE-D16 board and its Aspeed **AST2050**
> BMC: what flash lives where, on which bus, which side (BMC vs host x86) can
> reach it, what the faithful `kgpe-d16-bmc` QEMU machine models, and how each
> maps to an OpenBMC update mechanism.
>
> **HARD SAFETY RULE for this whole task: no real flash writes, nothing
> unrecoverable.** On real silicon every operation here is READ-ONLY / dry-run.
> Writes to the *emulated* flash in QEMU are fine — that model is disposable.

## TL;DR — two flashes, two buses, two different owners

| | **BMC firmware flash** | **Host BIOS flash** |
|---|---|---|
| Chip | SPI-NOR (SOIC-8 near the AST2050); Raptor U-Boot supports STM25P64/128, S25FL128P, MX25L128D, W25X64 | socketed **2 MB Winbond W25Q16** |
| Controller / bus | **AST2050 legacy SMC** (SPI), control regs `0x16000000`, data `0x14000000` (CE2 boot) | **AMD SP5100 FCH** SPI, host x86 side |
| Who can write it | the **BMC itself** (in-band: OpenBMC → mtd), or an external SPI programmer on the BMC bus | the **host x86** via `flashrom` (behind the SP5100 **IMC** write-guard), or an external SPI clip |
| BMC → this flash? | **yes** — it is the BMC's own boot device | **no** — not wired to the AST2050 on this board |
| Update mechanism | OpenBMC UpdateService / phosphor-bmc-code-mgmt → `/dev/mtdX`; IPMI HPM.1 / OEM | host-side `flashrom` (needs `amd_imc_force`); **not** a BMC operation on KGPE-D16 |

The headline faithfulness finding is the bottom-right cell: **on the KGPE-D16 the
BMC does not have a hardware path to the host BIOS flash.** "BIOS update driven by
the BMC" is a real pattern on *some* server designs (a dedicated host-SPI master +
a BIOS flash mux the BMC can steal), but that is an **AST2400/AST2500-generation /
board-wiring** feature, and the AST2050 does not have it (see §3). So on this board
"update the BIOS" means a **host-side** `flashrom` operation, not a BMC one.

---

## 1. BMC firmware flash — the AST2050 legacy SMC (SPI-only)

**Source of truth:** ASPEED AST2050/AST1100 A3 Datasheet (in-repo:
`dell-c410x-firmware/datasheets/AST2050_AST1100_A3_Datasheet_V1.02.pdf`; the
V1.05 extraction is in `../qemu-model/peripherals/smc/DATASHEET-SMC.md`), plus
`../hwreg.h` and `../ast2050.h`.

- The AST2050 has a single **Static Memory Controller (SMC)**: 8 control registers
  at **`0x16000000`** (`AST_SMC_BASE`, `hwreg.h:25`) and a flash **data** window at
  **`0x10000000`** (96 MB = three 32 MB chip-select segments CE0/CE1/CE2)
  (datasheet §11.1 p100; §9 memory map p97).
- **SPI-only silicon.** The register set is a NOR/NAND/SPI superset, but
  "**For AST2050/AST1100 chip, only SPI flash type interface is supported**"
  (datasheet §11.1 p100, red text). Feature tables §1.4/§1.5 (p27–28) list the
  AST2050/AST1100 "Flash Memory Controller = SPI Flash".
- **Chip selects & boot.** CE0=`0x10000000`, CE1=`0x12000000`, CE2=`0x14000000`
  under the default 32 MB segment size (`SMC00[1:0]=00`). Exactly **one** CE is
  strapped (external trapping resistors) as the CPU boot device and is aliased to
  `0x00000000` until the AHBC address-remap at `0x1E60008C` flips `0x0` to SDRAM
  (datasheet §11.1 p100; §9 p97).
- **Raptor U-Boot confirms the boot layout** (`ast2050.h`): boot SPI on **CS2**,
  `PHYS_FLASH_1 = 0x14000000`, `CONFIG_FLASH_SPI`, environment at offset
  `0x7F0000`. It also carries a **`CONFIG_2SPIFLASH`** option — *"Boot SPI: CS2,
  2nd SPI: CS0"* (`PHYS_FLASH_2_BASE = 0x10000000`) — but it is **commented out /
  `#undef`, marked "Not ready"** (`ast2050.h:46-47,118-136`). So the silicon *can*
  address a second SPI flash on CE0, but Raptor's shipping firmware uses a single
  boot flash on CE2. Either way both CEs are **BMC-side** flash on the BMC's own
  SMC — there is no host flash here.
- **Raptor flashrom fork.** Out-of-band programming of this BMC flash uses
  Raptor Engineering's `ast2050-flashrom`, which knows the AST2050 SPI controller
  (`../RPI4-OPENOCD-JTAG-WIRING.md` §4; supports STM25P64/128, S25FL128P,
  MX25L128D, W25X64 — `../RAPTOR-PORTING-GUIDE.md:431`).
- **`BMC_FW1` header is NOT the flash.** Per `../HEADER-PINOUTS.md` and
  `../RPI4-OPENOCD-JTAG-WIRING.md`, `BMC_FW1` is the **ASMB4/5 management-module
  slot** (proprietary signals), not a debug tap onto the SPI flash. The BMC boot
  flash is a discrete SOIC-8 near the AST2050.

**Flash size in our model:** 8 MB (`../qemu-firmware/scripts/mkflash.py` assembles
an 8 MB SPI image: U-Boot + kernel + initrd + dtb). The Dell C410X AST2050 sibling
uses 8–16 MB SPI (`dell-c410x-firmware/ANALYSIS.md:56`).

### What QEMU models for the BMC flash
- The faithful `kgpe-d16-bmc` machine backs the BMC SPI flash with a
  `-drive file=<img>,format=raw,if=mtd` block device
  (`../qemu-firmware/scripts/{run-qemu,ssh-test}.py`).
- A **G3-only `aspeed.smc-ast2050` device** presents the **legacy SMC control
  registers at `0x16000000`** (created when `silicon_rev == AST2050_A1_SILICON_REV`):
  `SMC00` returns its `0x00000240` reset value and `SMC04` CE0-control is writable;
  both fwtest checks (`smc00.reset`, `smc04.rw`) PASS
  (`../qemu-model/peripherals/smc/DOC.md`).
- **Deferred:** the flash **data windows** (`0x10000000`/`0x12000000`/`0x14000000`)
  and the boot alias to `0x0` are not yet mapped through the legacy SMC. Today's
  boots reach the mtd image through mainline QEMU's **AST2400 FMC** model
  (`hw/ssi/aspeed_smc.c`, data window `0x20000000`), which is independent of the
  `0x16000000` legacy block. This is a documented, oracle-gated follow-up (SMC #58).

---

## 2. Host BIOS flash — separate, host-owned, NOT BMC-reachable

**Source of truth:** `../BIOS-CONFIG-WITHOUT-MENU.md` (verified 2026-07-08), which
analyses `backup/kgpe-d16-ami-bios-3309.bin` dumped **in-system with flashrom**.

- The host BIOS is a **socketed 2 MB Winbond W25Q16** holding legacy **AMIBIOS8**
  (`AMI95 Version 0800`, `sha256 671e62ca…`) — *not* UEFI/Aptio, so there is no
  EFI-variable path.
- It sits on the **AMD SP5100 (SB700-family) FCH** SPI bus, i.e. the **host x86**
  firmware bus. `flashrom` running on the host **reads** it in-system, but
  **write is blocked by the SP5100 IMC** (Integrated Micro Controller) guard —
  it needs `flashrom -p internal:amd_imc_force=yes`, and the doc explicitly calls
  **external flashing the safe route** (`BIOS-CONFIG-WITHOUT-MENU.md:20`).
- **The AST2050 BMC is not on this bus.** The BMC's only reach toward host
  firmware is **`LPC2AHB`** — "BMC-controlled mapping of LPC *firmware cycles*
  onto AHB" (`../CULVERT-UART-JTAG-DEBUG.md:50`), the culvert `ilpc` backdoor.
  That maps host LPC memory/firmware *cycles* into the BMC's AHB for
  read/poke of host memory; it is **not** a write path to the SPI BIOS chip, and
  in any case the KGPE-D16 host BIOS is fetched over **SPI via the FCH**, not over
  LPC firmware-hub cycles. So there is no BMC→BIOS-flash datapath to model.

**Consequence for "update BIOS":** on the KGPE-D16 this is a **host-side**
operation (`flashrom` on the running x86, or an external SPI programmer on the
socketed chip) — deliberately kept out of scope for a BMC firmware-update task,
and out of scope for any real write under the safety rule. Our repo already treats
this chip as **read-only** (it is dumped, analysed for BIOS settings, and written
only by external programmer if at all).

---

## 3. Why there is no BMC→BIOS mux on the AST2050 (generation gap)

The "BMC flashes the host BIOS" capability that exists on later BMC platforms needs
a **second, host-facing SPI master** in the BMC SoC plus a board-level **flash mux**
that lets the BMC steal the host BIOS bus. On Aspeed parts that host-SPI master
first appears with the **AST2400+ FMC generation**: FMC control at `0x1E620000`
with **separate SPI masters at `0x1E630000` / `0x1E631000`** and flash windows at
`0x20000000` / `0x30000000` (`../qemu-model/peripherals/smc/DATASHEET-SMC.md` §7).

The **AST2050 has none of that** — it has only the single legacy SMC of §1
(`0x16000000` control / `0x10000000` data), whose chip selects drive **BMC-side**
flash. There is no `0x1E630000` SPI master in the AST2050 register map
(`hwreg.h`/`ast2050.h` define only `AST_SMC_BASE 0x16000000`). Mainline QEMU's
`aspeed_smc` models the AST2400 FMC, **not** this legacy block, which is exactly
why the faithful G3 model needs the new `aspeed.smc-ast2050` device.

**Net:** faithful to the real AST2050, the BMC-update path is real and the
BIOS-update-via-BMC path is **absent by design** on this SoC/board.

---

## 4. OpenBMC update mechanism mapping (what each image exposes)

Two AST2050 OpenBMC images exist (`../openbmc/`), both built for the ARMv5
`quanta-q71l` machine (ARM926EJ-S = the AST2050 CPU) and booted **over NFS** on
`kgpe-d16-bmc`:

| Feature | `-redfish.bb` (lean, 64 MB) | `-full.bb` |
|---|---|---|
| bmcweb / Redfish `UpdateService` endpoint | ✅ (compiled into bmcweb) | ✅ |
| IPMI (`mc info`, host KCS + LAN RMCP+, FRU, SEL) | ❌ | ✅ |
| **phosphor-bmc-code-mgmt / phosphor-software-manager** (the staging backend) | ❌ | ❌ |
| `obmc-flash-bmc-*` MTD overlay services | **masked** on NFS boot | **masked** on NFS boot |

Two consequences, stated honestly:

1. **The Redfish `UpdateService` object is present** (bmcweb ships it whenever
   Redfish is built), so `GET /redfish/v1/UpdateService` answers and a
   `POST` is *accepted* by the HTTP layer. But because
   **phosphor-software-manager is not installed** and the flash overlay services
   are masked (there is no MTD on the NFS-root boot path —
   `../qemu-firmware/scripts/stage-openbmc-nfsroot.sh:29-35`), there is currently
   **no backend to validate the image and create a `xyz.openbmc_project.Software.*`
   D-Bus object** on the AST2050 image. Adding
   `obmc-bmc-code-mgmt`/`phosphor-software-manager` to the image is an **F-IMG2
   image-content follow-up** (see §6).
2. **The full image exposes the IPMI path** (`ipmitool mc info`, and the transport
   for HPM.1 / OEM firmware transfer). Real-HW `mc info` evidence already exists
   (`../openbmc/bmc-functionality/evidence/real-hw/mc-info.txt`).

### How the mechanism works when the backend is present (reference)
`POST /redfish/v1/UpdateService` (multipart form, or the legacy
`.../UpdateService/update` simple-update) hands the image to
**phosphor-software-manager**, which:
1. unpacks + verifies the image (manifest / signature),
2. creates a `xyz.openbmc_project.Software.Version` object (a new *Software
   inventory* item) and an associated `…Software.Activation` object at
   `Activation = Ready`, and
3. on `Activation = Active` (Redfish `Apply`), writes the image to the alternate
   BMC flash bank via the MTD device and arms it for the next boot.

The **image is STAGED** at step 2 — the evidence for "the BMC accepted a firmware
update" is the `Software.Version` + `Software.Activation` D-Bus objects; a reboot
into the new image is *not* required to prove the mechanism.

---

## 5. IPMI firmware info & HPM.1

- `ipmitool -I lanplus … mc info` returns the BMC's **Firmware Revision** (IPMI
  "Get Device ID"). Current real-HW capture shows the defaults (`Firmware Revision
  0.00`, Manufacturer/Product 0) — the OpenBMC bring-up has not yet populated the
  IPMI FRU/Device-ID board strings (`evidence/real-hw/mc-info.txt`). This is the
  IPMI *firmware-info* surface; it is present in the **full** image (IPMI enabled),
  absent in the lean image.
- **HPM.1** (`ipmitool hpm`) is the PICMG firmware-transfer-over-IPMI mechanism.
  OpenBMC can expose it via a HPM.1-capable ipmid provider, but the current AST2050
  images do not include one, so `ipmitool hpm capabilities` would report none. HPM.1
  is the IPMI counterpart to the Redfish UpdateService path and is a candidate for
  the same F-IMG2 follow-up.

---

## 6. Honest boundary — what a full end-to-end update still needs

- **BMC self-update, end-to-end:** add `phosphor-bmc-code-mgmt`
  (phosphor-software-manager) to the AST2050 image **and** boot from a real MTD
  layout (squashfs-on-NOR + UBI rwfs), not NFS root — because the update writes
  `/dev/mtdX`. On the NFS-root bring-up path the flash overlay services are
  deliberately masked. Both are **image-content / boot-layout** changes owned by
  the image task (F-IMG2), not QEMU-model changes.
- **Faithful flash-window model:** map the legacy SMC data windows
  (`0x10000000`/`0x14000000`) so the BMC-side flash is reachable through the *G3*
  controller rather than the AST2400 FMC stand-in (SMC #58 follow-up). Not required
  to demonstrate the mechanism (the mtd block device already carries the data), but
  required for full G3 faithfulness.
- **Host BIOS update:** **out of scope by hardware** — the AST2050 BMC cannot reach
  the host BIOS flash on this board (§2–§3). Updating the BIOS is a host-side
  `flashrom` / external-programmer operation and, under the safety rule, is **not
  performed** here.

---

## 7. Safety statement

Everything in this task is demonstrated **in QEMU against emulated flash** or as a
**read-only characterization**. **No write was performed to the real board's BMC
SPI flash or to the real host BIOS W25Q16.** The host BIOS chip is treated as
read-only throughout the repo; the real board's BMC flash is never written by this
task.

# Real-hardware firmware-update characterization (READ-ONLY)

> **SAFETY — read first.** This task (F9) performed **no write to any real flash**
> — not the BMC SPI-NOR, not the host BIOS W25Q16. Everything below is a
> **read-only characterization** built from *already-existing* read-only evidence
> in this repo plus **documented-but-not-executed** write procedures. F9 did not
> initiate new rig access (the AST2050 rig is shared; the consolidated hardware
> boot is owned by a separate task), so as not to disturb it. The write procedures
> are recorded for completeness and are explicitly **not** run here.

## What the real board exposes for firmware update

| Target | Real-HW READ path (proven, read-only) | WRITE path (documented, NOT executed) |
|---|---|---|
| **BMC firmware** (AST2050 SPI-NOR) | (a) **JTAG** run-control: IDCODE `0x07926f0f`, AHB `mdw` reads e.g. `SCU7C = 0x202`; (b) **P2A / culvert** in-band `devmem` reads the same `SCU7C = 0x202`; (c) **flashrom** SPI read of the boot flash via the Pi's SPI0 (Raptor `ast2050-flashrom`) | in-band OpenBMC `UpdateService`/`phosphor-bmc-code-mgmt` → `/dev/mtdX`; or external `flashrom -w` on the BMC SPI bus |
| **Host BIOS** (2 MB W25Q16) | **flashrom** in-system read → `backup/kgpe-d16-ami-bios-3309.bin` (2 097 152 bytes, `sha256 671e62ca…`) — a real dump that identifies the chip | host-side `flashrom -p internal:amd_imc_force=yes -w` (SP5100 IMC guard), or external SPI programmer. **Not a BMC operation on this board.** |
| **IPMI firmware info** | `ipmitool -I lanplus … mc info` → Firmware Revision (real-HW capture `../openbmc/bmc-functionality/evidence/real-hw/mc-info.txt`) | — |

### Evidence already in the repo (all read-only)
- **Host BIOS chip identity via a real read:** `asus-kgpe-d16-firmware/backup/kgpe-d16-ami-bios-3309.bin` is a **2 MB flashrom dump of the W25Q16**, taken in-system on the real KGPE-D16 (`../BIOS-CONFIG-WITHOUT-MENU.md`, verified 2026-07-08). This *is* the real-HW read that identifies the host BIOS flash chip — no further read was needed or performed.
- **BMC AHB read paths, two independent, proven on silicon:**
  - **JTAG** (RPi4 bit-bang, OpenOCD): IDCODE `0x07926f0f`, RTCK echo, halt, and AHB `mdw` over JTAG returning `SCU7C = 0x202` (`../JTAG-USAGE-GUIDE.md`, project memory `jtag-bringup-status`).
  - **P2A / culvert** in-band: `devmem` bridge reads `SCU7C = 0x202` independently (project memory `culvert-g3-port-status`). Two paths agreeing on the same register is the cross-check.
  These prove the BMC's AHB (hence its SPI-flash controller registers at `0x16000000`) is reachable read-only on the real chip; they are **not** flash writes.
- **BMC SPI read tooling:** Raptor Engineering `ast2050-flashrom` drives the AST2050 SPI controller; on the rig it is wired to the Pi's hardware SPI0 (`../RPI4-OPENOCD-JTAG-WIRING.md` §4). Available as a **read** path; a write is the documented-not-executed procedure.
- **IPMI firmware revision:** `../openbmc/bmc-functionality/evidence/real-hw/mc-info.txt` — real `ipmitool … mc info` over LAN (currently shows the un-personalized defaults, `Firmware Revision 0.00`).

## Documented (NOT executed) write procedures

For completeness only — **none of these was run**:

1. **BMC self-update, in-band (the normal path):** on an OpenBMC image that
   includes `phosphor-bmc-code-mgmt`, `POST /redfish/v1/UpdateService` (or
   `ipmitool hpm upgrade`) stages the image; activation writes the alternate BMC
   flash bank via `/dev/mtdX`. Requires the software-manager backend + an MTD boot
   layout (see `UPDATE-PATHS.md` §6) — not present on the current NFS-root images.
2. **BMC flash, external:** `flashrom -p linux_spi:dev=/dev/spidev0.0 -w <img>` from
   the Pi against the BMC SPI-NOR (board OFF). Recoverable, but a write — not run.
3. **Host BIOS, host-side:** `flashrom -p internal:amd_imc_force=yes -w <bios>` on
   the running x86; or an external SPI clip on the socketed W25Q16. The BMC cannot
   do this on the KGPE-D16 (no BMC↔BIOS datapath). Not run.

## Bottom line
The real board's firmware-update **interfaces are characterized read-only**: the
host BIOS chip is identified from an existing 2 MB dump, the BMC AHB/SPI access is
proven reachable via JTAG and P2A (both reading, agreeing on `SCU7C=0x202`), and
the IPMI firmware-info surface is captured. **No real flash was written by F9.**

# ASUS KGPE-D16 - Component Datasheets

Datasheets for the ICs relevant to the **ASUS KGPE-D16** BMC firmware
reverse-engineering / open-firmware port. The KGPE-D16 is a dual Socket-G34
AMD Opteron 6000-series server board; its BMC is an **Aspeed AST2050** on the
ASUS **ASMB4-iKVM / ASMB5** management module. This project replicates and
modernises Raptor Engineering's abandoned AST2050 Linux port (see
`../RAPTOR-PORTING-GUIDE.md`).

Most files are downloaded from manufacturer / archive sites by
[`download_datasheets.py`](download_datasheets.py). Several are **byte-identical
copies from [`../../dell-c410x-firmware/datasheets/`](../../dell-c410x-firmware/datasheets/)**,
because the C410X uses the *same AST2050 SoC* and the *same SPI-NOR flash family*
as this board — see [Provenance](#provenance--evidence).

> **Scope.** This directory is BMC-focused. Datasheets are split into
> **BMC-facing** parts (silicon the AST2050 firmware actually drives) and
> **host-side board context** parts (x86 platform silicon managed by coreboot,
> included because this directory's JTAG/HDT scan-chain analysis references
> them). See [Still missing](#still-missing--nda-restricted) for confirmed
> parts with no public datasheet.

---

## I2C / bus topology (BMC-facing)

Unlike the C410X (a 48-IC sensor fan-out), the KGPE-D16 BMC drives very few
devices. Raptor's reconstructed device tree
(`../RAPTOR_ENGINEERING_AST2050_ANALYSIS.md:1500`) and U-Boot config model only:

```
Aspeed AST2050 BMC (ASMB4/ASMB5 module)
│
├── SPI (SMC @ 0x16000000, mapped 0x14000000)
│     └── BMC_FW1  ── one of: M25P64 / M25P128 / S25FL128P / MX25L12835F / W25X64
│
├── DDR2  (64 MB @ 0x40000000)  ── on-module SDRAM (part unidentified)
│
├── MAC0 (RMII)  ── external 10/100 Ethernet PHY (part UNIDENTIFIED, see below)
│
└── I2C
      ├── i2c0 @ 0x48 ── LM75 temperature sensor  (compatible = "ti,lm75")
      └── ch. 5  @ 0x50 ── "ASUS EEPROM" (FRU), 2-byte addressing (>=24C32 class)
```

**Host-side I2C/LPC (coreboot-managed, NOT on the BMC bus)** — from coreboot
`4.11 src/mainboard/asus/kgpe-d16/devicetree.cb`:

```
AMD SP5100 southbridge (SB700 family)  ── SMBus + LPC
  ├── SMBus 0x2f ── W83795G  hardware monitor (8 fans / 8 voltages / temps)
  ├── SMBus 0x50-0x57 ── DIMM SPD / thermal (on-DIMM, not board silicon)
  ├── LPC ── W83667HG-A  Super I/O   +   TPM (pnp 4e.0)
  └── A-Link Express II ── AMD SR5690 northbridge / IOMMU (RD890)
```

---

## Datasheets by component

### BMC SoC

| Datasheet | Part | Qty | Manufacturer | Notes |
|-----------|------|-----|--------------|-------|
| [AST2050_AST1100_Datasheet.pdf](AST2050_AST1100_Datasheet.pdf) | AST2050 / AST1100 | 1 | Aspeed | ARM926EJ-S @ 266 MHz BMC SoC. This PDF is the **AST1100 Software Programming Guide (397 pp)** — the register-programming manual; the *full* AST2050 datasheet is NDA (see [Still missing](#still-missing--nda-restricted)). |

### SPI NOR flash (BMC boot / BMC_FW1)

The BMC boots from SPI NOR. Raptor's U-Boot autodetects any of these five chips
(`../RAPTOR-PORTING-GUIDE.md:431`). The actual part varies by board / ASMB
revision; all are 64 or 128 Mbit.

| Datasheet | Part | Manufacturer | Capacity | Notes |
|-----------|------|-------------|----------|-------|
| [M25P64_Datasheet.pdf](M25P64_Datasheet.pdf) | M25P64 (STM25P64) | STMicro / Micron | 64 Mbit | 55 pp, full datasheet |
| [M25P128_Datasheet.pdf](M25P128_Datasheet.pdf) | M25P128 (STM25P128) | STMicro / Micron | 128 Mbit | 47 pp, full datasheet |
| [S25FL128P_Datasheet.pdf](S25FL128P_Datasheet.pdf) | S25FL128P | Spansion / Infineon | 128 Mbit | 44 pp, full datasheet |
| [MX25L12835F_Datasheet.pdf](MX25L12835F_Datasheet.pdf) | MX25L12835F (MX25L128D) | Macronix | 128 Mbit | full datasheet |
| [W25X64_Datasheet.pdf](W25X64_Datasheet.pdf) | W25X64 | Winbond | 64 Mbit | **product brief only** (2 pp SpiFlash flyer) — full W25X64 datasheet is registration-gated |

### BMC I2C — sensors & EEPROM

| Datasheet | Part | Bus / Addr | Notes |
|-----------|------|-----------|-------|
| [LM75_Datasheet.pdf](LM75_Datasheet.pdf) | LM75 | i2c0 @ 0x48 | Digital temperature sensor (TI); Raptor DT binds it as `ti,lm75` |
| [AT24C256_Datasheet.pdf](AT24C256_Datasheet.pdf) | AT24C256 | ch.5 @ 0x50 | **Class reference** for the "ASUS EEPROM" (FRU) the AST2050 U-Boot reads; exact density/vendor on the ASMB module is unread (`ast2050.h:213-214` → ≥24C32 class) |

### Host-side board context (coreboot-managed)

Included because the directory's JTAG/HDT analysis (`../JTAG-HEADERS.md`,
`../RPI4-OPENOCD-JTAG-WIRING.md`) references the AMD chipset, and the coreboot
port shares this repo's SoC bring-up goal. **These are not on the BMC's I2C bus.**

| Datasheet | Part | Role | coreboot driver |
|-----------|------|------|-----------------|
| [W83795G_W83795ADG_Datasheet.pdf](W83795G_W83795ADG_Datasheet.pdf) | Nuvoton/Winbond W83795G/ADG | Hardware monitor, host SMBus 0x2f (fans/voltages/temps) | `drivers/i2c/w83795` |
| [AMD_SR5690_Register_Reference_Guide_43871.pdf](AMD_SR5690_Register_Reference_Guide_43871.pdf) | AMD SR5690 (RD890) | Northbridge / IOMMU; HyperTransport→PCIe. 282 pp register guide (pub 43871, rev 3.04) | `southbridge/amd/sr5650` |
| [AMD_SP5100_Register_Reference_Guide_44413.pdf](AMD_SP5100_Register_Reference_Guide_44413.pdf) | AMD SP5100 | Southbridge (SB700 family), embedded 8051 SMBus core, LPC. 317 pp register guide (pub 44413) | `southbridge/amd/sb700` |

---

## Summary

| Category | ICs | Files |
|----------|-----|-------|
| BMC SoC | AST2050 / AST1100 | 1 |
| SPI NOR flash (BMC boot) | M25P64 / M25P128 / S25FL128P / MX25L12835F / W25X64 | 5 |
| BMC I2C sensor / EEPROM | LM75, AT24C256 | 2 |
| Host-side board context | W83795G, AMD SR5690, AMD SP5100 | 3 |
| **Total committed** | **11 documents** | **~66 MiB** |

Files shared byte-for-byte with the C410X collection: **AST2050, the 5 SPI-NOR
flash chips, LM75, AT24C256** (8 of 11). KGPE-D16-specific additions: **W83795G,
AMD SR5690, AMD SP5100** (3 of 11).

---

## Provenance / evidence

Every part traces to in-repo analysis or the coreboot devicetree, per this
repo's evidence standard:

| Part | Evidence |
|------|----------|
| AST2050 / AST1100 | Whole directory; SoC is the AST2050 (`../RAPTOR_AST2050_SUMMARY.md`) |
| 5× SPI flash | `../RAPTOR-PORTING-GUIDE.md:431` — "Supports chips: STM25P64, STM25P128, S25FL128P, MX25L128D, W25X64" |
| LM75 @ 0x48 | `../RAPTOR_ENGINEERING_AST2050_ANALYSIS.md:1532` — `temp-sensor@48 { compatible = "ti,lm75"; }` |
| FRU EEPROM @ 0x50 | `../ast2050.h:213-214` (`CONFIG_SYS_I2C_EEPROM_ADDR 0xa0`, 2-byte len) + `../RAPTOR-UBOOT-ANALYSIS.md:134` ("Channel 5 for AST2050 (ASUS EEPROM)") |
| W83795G, W83667HG-A, SR5690, SP5100, TPM | coreboot `4.11 src/mainboard/asus/kgpe-d16/devicetree.cb` (`chip drivers/i2c/w83795`, `superio/winbond/w83667hg-a`, `southbridge/amd/sr5650`, `southbridge/amd/sb700`) |
| SR5690 / SP5100 JTAG relevance | `../JTAG-HEADERS.md:378-415` (HDT scan chain, embedded microcontrollers) |

---

## Still missing / NDA-restricted

Parts **confirmed present** on the KGPE-D16 for which no clean, redistributable
public datasheet was found. `download_datasheets.py` prints this list on every
run so the gaps stay visible.

| Part | Status | Best available |
|------|--------|----------------|
| **Aspeed AST2050 (full datasheet)** | NDA | Committed `AST2050_AST1100_Datasheet.pdf` (AST1100 SW Programming Guide, 397 pp) is the public substitute. AST2500 (`ast2520a2gp_datasheet.pdf`) / AST2600 (`ast2600_datasheet.pdf`) on vgamuseum.info are register-compatible references for newer G-series parts. |
| **Winbond W83667HG-A (host Super I/O)** | Registration/NDA-gated | Distributor mirrors 403; alldatasheet serves a truncated ~19 pp preview only. Open reference: coreboot `src/superio/winbond/w83667hg-a/`. |
| **BMC Ethernet PHY** (ASMB4/5, RMII) | **Unidentified** | `../RAPTOR-PORTING-GUIDE.md:958` flags it as an open question. RTL8201EL/RTL8211BN/RTL8201N in the analysis are the AST2050 driver's *supported* PHY list, **not** a board ID. Needs a board photo / ASMB schematic. Candidate if later confirmed as an RTL8201-class part: `http://realtek.info/pdf/rtl8201.pdf`. |
| **BMC FRU EEPROM (exact part)** | Class ref committed | Present per `ast2050.h` / U-Boot but density/vendor unread; `AT24C256_Datasheet.pdf` stands in until the marking is read off the chip. |
| **AST2050 on-module DDR2 SDRAM** (64 MB) | Part unidentified | Generic behaviour covered by JEDEC **JESD79-2**; specific SDRAM part unknown (needs a package marking). JEDEC standards are free but not redistributable here. |

**Additional public AMD docs** (not committed, but useful for coreboot bring-up),
same `amd.com/content/dam/amd/en/documents/archived-tech-docs/programmer-references/`
base:

- SR5690 BIOS Developer's Guide — `43366.pdf`; Register Programming Requirements — `43872.pdf`
- SP5100 BIOS Developer's Guide — `44415.pdf`; SB800-series Register Reference — `45482.pdf`

---

## Re-downloading

```sh
uv run download_datasheets.py
```

The script skips files that already exist and validates the `%PDF` magic byte on
each download. Delete a PDF to force re-download. Note AMD's legacy
`www.amd.com/system/files/TechDocs/<n>.pdf` links now serve an HTML portal page;
the live pattern (used here) is
`www.amd.com/content/dam/amd/en/documents/archived-tech-docs/programmer-references/<n>.pdf`.

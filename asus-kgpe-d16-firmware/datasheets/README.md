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
>
> **15h.org mirror.** This directory also holds a committed copy of every
> PDF linked from the 15h.org **ASUS KGPE-D16** wiki page (this board) and
> its **ASUS KCMA-D8** sibling-board page (Socket-C32, same chipset, Super
> I/O, hwmon, and the same AST2050 BMC on an ASMB4/ASMB5 module): the ASUS
> board manual (E8847), AMD fam10h/fam15h BKDGs and Opteron data sheets, the
> full SR56x0/SP5100 doc sets (BIOS developer's guides, databooks, errata),
> the AMD IOMMU spec, two x86-microcode research papers, and the
> previously-missing **W83667HG-A full Data Book**. Link→file provenance
> maps: [`15H-ORG-MIRROR.md`](15H-ORG-MIRROR.md); page content:
> [`../ASUS-KGPE-D16.md`](../ASUS-KGPE-D16.md) /
> [`../ASUS-KCMA-D8.md`](../ASUS-KCMA-D8.md).

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
| [AST2050_AST1100_A3_Datasheet_V1.02.pdf](AST2050_AST1100_A3_Datasheet_V1.02.pdf) | AST2050 / AST1100 | 1 | Aspeed | ARM926EJ-S @ 266 MHz BMC SoC. Full Aspeed **A3 Datasheet V1.02** (Sep 2008, 397 pp, "ASPEED Confidential"). |
| [AST2050_AST1100_A3_Datasheet_V1.05.pdf](AST2050_AST1100_A3_Datasheet_V1.05.pdf) | AST2050 / AST1100 | — | Aspeed | Newer **A3 Datasheet V1.05** (May 2010, 403 pp) — same SoC, later revision. |

> Both PDFs' internal `/Title` metadata reads "AST1100 Software Programming
> Guide" — an Aspeed LaTeX-template artifact; the **content is the A3 Datasheet**
> (page 1: "Integrated Remote Management Processor — A3 Datasheet"). Aspeed does
> not officially distribute it, so these are publicly-circulated copies. The
> register-compatible successors (AST2400/AST2500/AST2600) are vendored in-repo
> at [`../../datasheets/aspeed/`](../../datasheets/aspeed/) — the shared Aspeed
> SoC datasheet collection, which also mirrors these two AST2050 revisions.

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
| [W25X64_Datasheet.pdf](W25X64_Datasheet.pdf) | W25X64 | Winbond | 64 Mbit | 50 pp full datasheet (covers W25X16/16A/32/64, Rev I) |

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
| [Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf](Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf) | Nuvoton/Winbond W83795G/ADG | Same V1.43 datasheet, 15h.org copy (different PDF build — kept to complete the [15h.org mirror](15H-ORG-MIRROR.md)) | `drivers/i2c/w83795` |
| [W83667hg-a-datasheet-v1-2.pdf](W83667hg-a-datasheet-v1-2.pdf) | Winbond W83667HG-A | Host LPC Super I/O. **Full 319 pp Data Book v1.2** (via 15h.org — previously listed below as NDA-gated/unavailable) | `superio/winbond/w83667hg-a` |
| [AMD_SR5690_Register_Reference_Guide_43871.pdf](AMD_SR5690_Register_Reference_Guide_43871.pdf) | AMD SR5690 (RD890) | Northbridge / IOMMU; HyperTransport→PCIe. 282 pp register guide (pub 43871, rev 3.04) | `southbridge/amd/sr5650` |
| [AMD_SR5690_5670_5650_BIOS_Developers_Guide.pdf](AMD_SR5690_5670_5650_BIOS_Developers_Guide.pdf) | AMD SR5690/5670/5650 | BIOS Developer's Guide, 44 pp (pub 43870, rev 3.00) | `southbridge/amd/sr5650` |
| [AMD_SR5690_5670_5650_Register_Programming_Requirements.pdf](AMD_SR5690_5670_5650_Register_Programming_Requirements.pdf) | AMD SR5690/5670/5650 | Register Programming Requirements, 192 pp (pub 43872, rev 3.05) | `southbridge/amd/sr5650` |
| [AMD_SR5690_Databook.pdf](AMD_SR5690_Databook.pdf) | AMD SR5690 | Databook, 80 pp (pub 43869, rev 2.20) — **this board's northbridge** | `southbridge/amd/sr5650` |
| [AMD_SR5670_Databook.pdf](AMD_SR5670_Databook.pdf) | AMD SR5670 | Databook, 80 pp (pub 44549, rev 2.20) — the KCMA-D8's northbridge; same RD890 family as the KGPE-D16's SR5690 | `southbridge/amd/sr5650` |
| [SR56x0_Product_Errata.pdf](SR56x0_Product_Errata.pdf) | AMD SR5690/5670/5650 | Silicon errata, 33 pp (pub 46303, rev 3.10) | `southbridge/amd/sr5650` |
| [AMD_IOMMU_Spec_48882_v2.62.pdf](AMD_IOMMU_Spec_48882_v2.62.pdf) | AMD IOMMU | I/O Virtualization Technology (IOMMU) Specification rev 2.62, 266 pp (pub 48882) — the SR56x0's IOMMU programming model | `southbridge/amd/sr5650` |
| [AMD_SP5100_Register_Reference_Guide_44413.pdf](AMD_SP5100_Register_Reference_Guide_44413.pdf) | AMD SP5100 | Southbridge (SB700 family), embedded 8051 SMBus core, LPC. 317 pp register guide (pub 44413) | `southbridge/amd/sb700` |
| [AMD_SP5100_BIOS_Developers_Guide.pdf](AMD_SP5100_BIOS_Developers_Guide.pdf) | AMD SP5100 | BIOS Developer's Guide, 114 pp (pub 44415, rev 3.01) | `southbridge/amd/sb700` |
| [AMD_SP5100_Register_Programming_Requirements.pdf](AMD_SP5100_Register_Programming_Requirements.pdf) | AMD SP5100 | Register Programming Requirements, 74 pp (pub 44414, rev 3.02) | `southbridge/amd/sb700` |
| [AMD_SP5100_Databook.pdf](AMD_SP5100_Databook.pdf) | AMD SP5100 | Databook, 90 pp (pub 44409, rev 1.70; AES-encrypted with empty user password) | `southbridge/amd/sb700` |
| [SP5100_Product_Errata.pdf](SP5100_Product_Errata.pdf) | AMD SP5100 | Silicon errata, 32 pp (pub 46836, rev 3.00) | `southbridge/amd/sb700` |

### Host CPUs (Opteron, via the 15h.org mirror)

The KGPE-D16 takes Socket-G34 Opteron 6100/6200/6300 (fam10h/fam15h); the
KCMA-D8 takes Socket-C32 Opteron 4100/4200/4300 (same silicon families in a
different package). The fam10h/fam15h programming docs therefore cover both
boards' host CPUs.

| Datasheet | Family | Notes |
|-----------|--------|-------|
| [44065_Arch2008.pdf](44065_Arch2008.pdf) | fam10h+fam15h | AGESA Interface Specification for Arch2008 (pub 44065), 368 pp |
| [AMD_Family_10h_BKDG_31116.pdf](AMD_Family_10h_BKDG_31116.pdf) | fam10h | BIOS and Kernel Developer's Guide (pub 31116), 475 pp |
| [AMD_Family_10h_Opteron_PDS_40036.pdf](AMD_Family_10h_Opteron_PDS_40036.pdf) | fam10h | Opteron Product Data Sheet (pub 40036), 8 pp |
| [AMD_Family_10h_Power_Thermal_Data_Sheet_43374.pdf](AMD_Family_10h_Power_Thermal_Data_Sheet_43374.pdf) | fam10h | Server/Workstation Power and Thermal Data Sheet (pub 43374), 98 pp |
| [42301_15h_Mod_00h-0Fh_BKDG.pdf](42301_15h_Mod_00h-0Fh_BKDG.pdf) | fam15h 00h-0Fh | BIOS and Kernel Developer's Guide (pub 42301), 639 pp |
| [49687_15h_Mod_00h-0Fh_Opteron_PDS.pdf](49687_15h_Mod_00h-0Fh_Opteron_PDS.pdf) | fam15h 00h-0Fh | Opteron Product Data Sheet (pub 49687), 7 pp |
| [47414_15h_sw_opt_guide.pdf](47414_15h_sw_opt_guide.pdf) | fam15h | Software Optimization Guide (pub 47414), 396 pp |
| [Sec17_Koppe_Reverse_Engineering_x86_Processor_Microcode.pdf](Sec17_Koppe_Reverse_Engineering_x86_Processor_Microcode.pdf) | fam10h/K8 | Koppe et al., USENIX Security 2017 — x86 microcode RE paper linked from the KGPE-D16 page's Opteron section |
| [2014_Chen_Ahn_Security_Analysis_of_x86_Processor_Microcode.pdf](2014_Chen_Ahn_Security_Analysis_of_x86_Processor_Microcode.pdf) | x86 | Chen & Ahn 2014 — x86 microcode security analysis, ditto |

### Board documentation

| Document | Notes |
|----------|-------|
| [KGPE-D16_Manual.pdf](KGPE-D16_Manual.pdf) | ASUS KGPE-D16 User Manual (ASUS pub E8847), 158 pp — byte-identical to the asus.com-circulated E8847 manual |

---

## Summary

| Category | ICs / docs | Files |
|----------|-----------|-------|
| BMC SoC | AST2050 / AST1100 (A3 Datasheet V1.02 + V1.05) | 2 |
| SPI NOR flash (BMC boot) | M25P64 / M25P128 / S25FL128P / MX25L12835F / W25X64 | 5 |
| BMC I2C sensor / EEPROM | LM75, AT24C256 | 2 |
| Host-side board context | W83795G (×2 builds), W83667HG-A, SR56x0 doc set (6, incl. both SR5690+SR5670 databooks) + IOMMU spec, SP5100 doc set (5) | 15 |
| Host CPUs (fam10h/fam15h Opteron) | AGESA spec, 2 BKDGs, 2 PDS, power/thermal, sw-opt guide, 2 microcode papers | 9 |
| Board documentation | ASUS KGPE-D16 User Manual (E8847) | 1 |
| **Total committed** | **34 documents** | **~112 MiB** |

Files shared byte-for-byte with the C410X collection: **both AST2050 A3 Datasheet
revisions, the 5 SPI-NOR flash chips, LM75, AT24C256** (9 of 34). 22 of the 34
were mirrored from the 15h.org board pages — the **ASUS KGPE-D16** page (this
board, the primary source) and its **ASUS KCMA-D8** sibling page (see
[`15H-ORG-MIRROR.md`](15H-ORG-MIRROR.md)); 4 further links on those pages proved
byte-identical to files already here (AST2050 A3 V1.05, S25FL128P, and both
register reference guides), independently cross-validating both copies.

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
| 22× 15h.org mirror docs (board manual, Opteron + microcode papers, SR56x0/SP5100 sets, W83667HG-A, W83795G) | Linked from the 15h.org ASUS KGPE-D16 page (primary; `../ASUS-KGPE-D16.md`) and its ASUS KCMA-D8 sibling page (`../ASUS-KCMA-D8.md`); per-file provenance, page counts, and SHA-256 cross-checks in [`15H-ORG-MIRROR.md`](15H-ORG-MIRROR.md) |

---

## Still missing / NDA-restricted

Parts **confirmed present** on the KGPE-D16 for which no clean, redistributable
public datasheet was found. `download_datasheets.py` prints this list on every
run so the gaps stay visible.

| Part | Status | Best available |
|------|--------|----------------|
| **Winbond W83667HG-A (host Super I/O)** | ~~Registration/NDA-gated~~ **GAP CLOSED (2026-07-16)** | Full 319 pp Data Book v1.2 is committed as [`W83667hg-a-datasheet-v1-2.pdf`](W83667hg-a-datasheet-v1-2.pdf), mirrored from the CC BY-SA 15h.org board pages (linked from both the KGPE-D16 and KCMA-D8 pages). (Distributor mirrors still 403; alldatasheet still serves a truncated ~19 pp preview. Open reference: coreboot `src/superio/winbond/w83667hg-a/`.) |
| **BMC Ethernet PHY** (ASMB4/5, RMII) | **Unidentified** | `../RAPTOR-PORTING-GUIDE.md:958` flags it as an open question. RTL8201EL/RTL8211BN/RTL8201N in the analysis are the AST2050 driver's *supported* PHY list, **not** a board ID. Needs a board photo / ASMB schematic. Candidate if later confirmed as an RTL8201-class part: `http://realtek.info/pdf/rtl8201.pdf`. |
| **BMC FRU EEPROM (exact part)** | Class ref committed | Present per `ast2050.h` / U-Boot but density/vendor unread; `AT24C256_Datasheet.pdf` stands in until the marking is read off the chip. |
| **AST2050 on-module DDR2 SDRAM** (64 MB) | Part unidentified | Generic behaviour covered by JEDEC **JESD79-2**; specific SDRAM part unknown (needs a package marking). JEDEC standards are free but not redistributable here. |

**Additional public AMD docs** — this list previously named four uncommitted
docs. Three are now committed via the 15h.org mirror: the SR56x0 BIOS
Developer's Guide (actual pub number **43870**, not 43366 as guessed here
before — verified from the cover page), the SR56x0 Register Programming
Requirements (43872), and the SP5100 BIOS Developer's Guide (44415). Still
not committed:

- SB800-series Register Reference — `45482.pdf`, same
  `amd.com/content/dam/amd/en/documents/archived-tech-docs/programmer-references/`
  base (the SP5100's SB700-family docs above cover this board; the SB800 doc
  is only occasionally useful for cross-reference).

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

# 15h.org board pages — PDF provenance

Every PDF linked from the 15h.org wiki pages for this board family has a
committed copy in this directory:

- **[ASUS KGPE-D16](https://15h.org/index.php/ASUS_KGPE-D16)** (permanent
  link: [`oldid=2924`](https://15h.org/index.php?title=ASUS_KGPE-D16&oldid=2924),
  retrieved 2026-07-16) — **the primary source**; this directory's board.
  Page content mirrored in [`../ASUS-KGPE-D16.md`](../ASUS-KGPE-D16.md).
  25 PDF links.
- **[ASUS KCMA-D8](https://15h.org/index.php/ASUS_KCMA-D8)** (permanent
  link: [`oldid=2941`](https://15h.org/index.php?title=ASUS_KCMA-D8&oldid=2941),
  retrieved 2026-07-16) — the Socket-C32 sibling board (same SR56x0/SP5100
  chipset family, same W83667HG-A Super I/O, same W83795G hwmon, and the same
  **AST2050 BMC on a removable ASMB4/ASMB5 module**). Page content mirrored
  in [`../ASUS-KCMA-D8.md`](../ASUS-KCMA-D8.md). 22 PDF links, of which 21
  are the *same URLs* as on the KGPE-D16 page; 1 is unique (the SR5670
  Databook).

15h.org publishes under **CC BY-SA 4.0**; the PDFs themselves are vendor
documents (AMD / Aspeed / ASUS / Infineon / Winbond / Nuvoton) and academic
papers that 15h.org redistributes.

All files were verified on 2026-07-16: `%PDF` magic + `pypdf` parse (page
counts below), publication numbers read from the documents' cover pages, and
SHA-256 comparison against the datasheets this directory had already fetched
independently from vendor sites. **Four links are byte-identical to files
that were already committed** — for those the existing file *is* the
committed copy (no duplicate is kept), and the match also cross-validates the
15h.org mirror against the vendor originals.

Re-download / verify everything (15h.org URLs are included as sources or
fallbacks in the shared downloader):

```sh
uv run download_datasheets.py
```

## ASUS KGPE-D16 page — link → file map (25 PDF links)

### Board documentation — wiki References section

| Wiki link (15h.org/images/…) | Committed file | Pages | Document |
|------------------------------|----------------|-------|----------|
| [`4/48/KGPE-D16_Manual.pdf`](https://15h.org/images/4/48/KGPE-D16_Manual.pdf) | [KGPE-D16_Manual.pdf](KGPE-D16_Manual.pdf) | 158 | ASUS KGPE-D16 User Manual — byte-identical (SHA-256) to the ASUS "E8847" manual circulating from asus.com mirrors |

### AMD Opteron 6100 series (K10 / fam10h) — wiki section 4.1.1

The same four fam10h docs are linked from the KCMA-D8 page's Opteron 4100
section (same silicon family, different package).

| Wiki link | Committed file | Pages | Document |
|-----------|----------------|-------|----------|
| [`f/f7/44065_Arch2008.pdf`](https://15h.org/images/f/f7/44065_Arch2008.pdf) | [44065_Arch2008.pdf](44065_Arch2008.pdf) | 368 | AMD AGESA Interface Specification for Arch2008 (pub 44065) — linked for both the 6100 and 6200/6300 series |
| [`6/63/31116.pdf`](https://15h.org/images/6/63/31116.pdf) | [AMD_Family_10h_BKDG_31116.pdf](AMD_Family_10h_BKDG_31116.pdf) | 475 | BIOS and Kernel Developer's Guide (BKDG) for AMD Family 10h Processors (pub 31116) |
| [`1/15/40036.pdf`](https://15h.org/images/1/15/40036.pdf) | [AMD_Family_10h_Opteron_PDS_40036.pdf](AMD_Family_10h_Opteron_PDS_40036.pdf) | 8 | Family 10h AMD Opteron Processor Product Data Sheet (pub 40036) |
| [`2/2b/43374.pdf`](https://15h.org/images/2/2b/43374.pdf) — **stale link** | [AMD_Family_10h_Power_Thermal_Data_Sheet_43374.pdf](AMD_Family_10h_Power_Thermal_Data_Sheet_43374.pdf) | 98 | AMD Family 10h Server and Workstation Processor Power and Thermal Data Sheet (pub 43374). The direct link (used identically on both board pages) redirects to the wiki Home page — the upload was renamed on the wiki; fetched via the renamed upload path (see `download_datasheets.py`) |

Reverse engineering and analysis (CPU microcode):

| Wiki link | Committed file | Pages | Document |
|-----------|----------------|-------|----------|
| [`a/a3/Sec17-koppe.pdf`](https://15h.org/images/a/a3/Sec17-koppe.pdf) | [Sec17_Koppe_Reverse_Engineering_x86_Processor_Microcode.pdf](Sec17_Koppe_Reverse_Engineering_x86_Processor_Microcode.pdf) | 19 | Koppe, Kollenda, Fyrbiak, Kison et al., "Reverse Engineering x86 Processor Microcode", USENIX Security 2017 |
| [`a/ab/2014_paper_microcode.pdf`](https://15h.org/images/a/ab/2014_paper_microcode.pdf) | [2014_Chen_Ahn_Security_Analysis_of_x86_Processor_Microcode.pdf](2014_Chen_Ahn_Security_Analysis_of_x86_Processor_Microcode.pdf) | 23 | Daming D. Chen & Gail-Joon Ahn (Arizona State University), "Security Analysis of x86 Processor Microcode", 11 December 2014 — also linked from the page's Opteron 6200/6300 section |

### AMD Opteron 6200/6300 series (Bulldozer/Piledriver, fam15h) — wiki section 4.1.2

Same three docs linked from the KCMA-D8 page's Opteron 4200/4300 section.

| Wiki link | Committed file | Pages | Document |
|-----------|----------------|-------|----------|
| [`b/be/42301_15h_Mod_00h-0Fh_BKDG.pdf`](https://15h.org/images/b/be/42301_15h_Mod_00h-0Fh_BKDG.pdf) | [42301_15h_Mod_00h-0Fh_BKDG.pdf](42301_15h_Mod_00h-0Fh_BKDG.pdf) | 639 | BKDG for AMD Family 15h Models 00h-0Fh Processors (pub 42301) |
| [`e/ee/49687_15h_Mod_00h-0Fh_Opteron_PDS.pdf`](https://15h.org/images/e/ee/49687_15h_Mod_00h-0Fh_Opteron_PDS.pdf) | [49687_15h_Mod_00h-0Fh_Opteron_PDS.pdf](49687_15h_Mod_00h-0Fh_Opteron_PDS.pdf) | 7 | Family 15h Models 00h-0Fh AMD Opteron Processor Product Data Sheet (pub 49687) |
| [`a/af/47414_15h_sw_opt_guide.pdf`](https://15h.org/images/a/af/47414_15h_sw_opt_guide.pdf) | [47414_15h_sw_opt_guide.pdf](47414_15h_sw_opt_guide.pdf) | 396 | Software Optimization Guide for AMD Family 15h Processors (pub 47414) |

### Aspeed AST2050 (the BMC) — wiki section 4.6

Same two links on the KCMA-D8 page.

| Wiki link | Committed file | Pages | Document |
|-----------|----------------|-------|----------|
| [`1/18/AST2050_Data_Sheet.pdf`](https://15h.org/images/1/18/AST2050_Data_Sheet.pdf) | [AST2050_AST1100_A3_Datasheet_V1.05.pdf](AST2050_AST1100_A3_Datasheet_V1.05.pdf) — **byte-identical (SHA-256)** | 403 | Aspeed AST2050/AST1100 A3 Datasheet V1.05 (May 2010) — 15h.org circulates exactly the copy this repo already relies on, independently confirming its provenance |
| [`6/64/Infineon-s25fl128p-…-datasheet-en.pdf`](https://15h.org/images/6/64/Infineon-s25fl128p-128-mbit-3.0-v-flash-memory-datasheet-en.pdf) | [S25FL128P_Datasheet.pdf](S25FL128P_Datasheet.pdf) — **byte-identical** | 44 | S25FL128P 128 Mbit SPI-NOR flash (the BMC module's boot flash); matches the infineon.com copy |

### AMD SR5690 northbridge (SR5690/5670/5650 family docs) — wiki section 4.7

The five family docs are also linked from the KCMA-D8 page's SR5670 section;
the SR5690 Databook is KGPE-D16-page-only (the KCMA-D8 page links the SR5670
Databook instead — see below).

| Wiki link | Committed file | Pages | Document |
|-----------|----------------|-------|----------|
| [`c/c3/AMD_SR5690_5670_5650_BIOS_Developers_Guide.pdf`](https://15h.org/images/c/c3/AMD_SR5690_5670_5650_BIOS_Developers_Guide.pdf) | [AMD_SR5690_5670_5650_BIOS_Developers_Guide.pdf](AMD_SR5690_5670_5650_BIOS_Developers_Guide.pdf) | 44 | SR5690/5670/5650 BIOS Developer's Guide (cover: "P/N: 43870_sr56xx_bdg_pub_3.00", rev 3.00, 2010) |
| [`2/24/48882-2.62.pdf`](https://15h.org/images/2/24/48882-2.62.pdf) | [AMD_IOMMU_Spec_48882_v2.62.pdf](AMD_IOMMU_Spec_48882_v2.62.pdf) | 266 | AMD I/O Virtualization Technology (IOMMU) Specification rev 2.62 (pub 48882) |
| [`9/9a/AMD_SR5690_5670_5650_Register_Reference_Guide.pdf`](https://15h.org/images/9/9a/AMD_SR5690_5670_5650_Register_Reference_Guide.pdf) | [AMD_SR5690_Register_Reference_Guide_43871.pdf](AMD_SR5690_Register_Reference_Guide_43871.pdf) — **byte-identical** | 282 | SR5690/5670/5650 Register Reference Guide (pub 43871); matches the amd.com copy |
| [`b/b0/AMD_SR5690_5670_5650_Register_Programming_Requirements.pdf`](https://15h.org/images/b/b0/AMD_SR5690_5670_5650_Register_Programming_Requirements.pdf) | [AMD_SR5690_5670_5650_Register_Programming_Requirements.pdf](AMD_SR5690_5670_5650_Register_Programming_Requirements.pdf) | 192 | SR5690/5670/5650 Register Programming Requirements (pub 43872, rev 3.05, August 2012) |
| [`4/4c/AMD_SR5690_Databook.pdf`](https://15h.org/images/4/4c/AMD_SR5690_Databook.pdf) | [AMD_SR5690_Databook.pdf](AMD_SR5690_Databook.pdf) | 80 | SR5690 Databook (cover: "P/N: 43869_sr5690_ds_pub", rev 2.20, 2012) — the KGPE-D16's northbridge |
| [`5/5d/SR56x0_Product_Errata.pdf`](https://15h.org/images/5/5d/SR56x0_Product_Errata.pdf) | [SR56x0_Product_Errata.pdf](SR56x0_Product_Errata.pdf) | 33 | SR56x0 Product Errata — silicon errata for SR5690/SR5670/SR5650 (pub 46303, rev 3.10, August 2012) |

### AMD SP5100 southbridge — wiki section 4.8

All five links identical on the KCMA-D8 page.

| Wiki link | Committed file | Pages | Document |
|-----------|----------------|-------|----------|
| [`a/ad/AMD_SP5100_BIOS_Developer%27s_Guide.pdf`](https://15h.org/images/a/ad/AMD_SP5100_BIOS_Developer%27s_Guide.pdf) | [AMD_SP5100_BIOS_Developers_Guide.pdf](AMD_SP5100_BIOS_Developers_Guide.pdf) | 114 | SP5100 BIOS Developer's Guide (cover: "PN: 44415_SP5100_bdg_pub_3.01", rev 3.01, 2011; wiki filename's apostrophe removed locally) |
| [`7/78/AMD_SP5100_Register_Reference_Guide.pdf`](https://15h.org/images/7/78/AMD_SP5100_Register_Reference_Guide.pdf) | [AMD_SP5100_Register_Reference_Guide_44413.pdf](AMD_SP5100_Register_Reference_Guide_44413.pdf) — **byte-identical** | 317 | SP5100 Register Reference Guide (pub 44413); matches the amd.com copy |
| [`7/7b/AMD_SP5100_Register_Programming_Requirements.pdf`](https://15h.org/images/7/7b/AMD_SP5100_Register_Programming_Requirements.pdf) | [AMD_SP5100_Register_Programming_Requirements.pdf](AMD_SP5100_Register_Programming_Requirements.pdf) | 74 | SP5100 Register Programming Requirements (cover: "P/N: 44414_sp5100_rpr_pub_3.02", rev 3.02, 2012) |
| [`d/df/AMD_SP5100_Databook.pdf`](https://15h.org/images/d/df/AMD_SP5100_Databook.pdf) | [AMD_SP5100_Databook.pdf](AMD_SP5100_Databook.pdf) | 90 | SP5100 Databook (cover: "P/N: 44409_sp5100_ds_pub", rev 1.70, 2010). AES-encrypted with an empty user password — viewers open it transparently; `pypdf` needs the `cryptography` package |
| [`e/ec/SP5100_Product_Errata.pdf`](https://15h.org/images/e/ec/SP5100_Product_Errata.pdf) | [SP5100_Product_Errata.pdf](SP5100_Product_Errata.pdf) | 32 | SP5100 Product Errata — silicon errata for SP5100 (pub 46836, rev 3.00, June 2012) |

### Winbond / Nuvoton — wiki sections 4.9 / 4.10

Both links identical on the KCMA-D8 page.

| Wiki link | Committed file | Pages | Document |
|-----------|----------------|-------|----------|
| [`3/34/W83667hg-a-datasheet-v1-2-67dd6c3d7aef5611225428.pdf`](https://15h.org/images/3/34/W83667hg-a-datasheet-v1-2-67dd6c3d7aef5611225428.pdf) | [W83667hg-a-datasheet-v1-2.pdf](W83667hg-a-datasheet-v1-2.pdf) | 319 | **Winbond W83667HG-A LPC Super I/O Data Book v1.2** — the full datasheet this directory previously recorded as NDA-gated with no public copy; this closes that gap. (Upload-hash suffix removed locally.) |
| [`3/31/Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf`](https://15h.org/images/3/31/Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf) | [Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf](Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf) | 152 | Nuvoton W83795G/ADG Hardware Monitor Datasheet V1.43. Same document as [W83795G_W83795ADG_Datasheet.pdf](W83795G_W83795ADG_Datasheet.pdf) (the nuvoton.com copy) but **not byte-identical** (a different PDF build of the same V1.43 datasheet), so this copy is kept to complete the mirror |

## ASUS KCMA-D8 page — link → file map (22 PDF links)

21 of the sibling page's 22 PDF links are the **same URLs** already mapped
above (fam10h docs appear under its Opteron 4100 section, fam15h docs under
its Opteron 4200/4300 section, the SR56x0 family docs under its SR5670
section, and the AST2050/SP5100/Winbond/Nuvoton links are identical —
including the same stale `2/2b/43374.pdf` link). The one KCMA-D8-only link:

| Wiki link | Committed file | Pages | Document |
|-----------|----------------|-------|----------|
| [`2/23/AMD_SR5670_Databook.pdf`](https://15h.org/images/2/23/AMD_SR5670_Databook.pdf) | [AMD_SR5670_Databook.pdf](AMD_SR5670_Databook.pdf) | 80 | SR5670 Databook (cover: "P/N: 44549_sr5670_ds_pub", rev 2.20, 2012) — the KCMA-D8's northbridge; same RD890 family as the KGPE-D16's SR5690 |

> **PDF `/Title` metadata is unreliable** in several of these vendor files
> (the W83667HG-A book claims "W83627DHG Data Sheet", both errata claim
> "RS600 DDR2 Memory Interface Tuning Guide", the AST2050 datasheet claims
> "AST1100 Software Programming Guide") — vendor authoring-template
> artifacts, as already noted for the AST2050 PDFs in `README.md`.
> Identification above is from the documents' cover pages / content and the
> wiki pages' link labels.

## Not mirrored (not PDFs)

The board pages also link non-PDF artifacts, intentionally not committed:

- coreboot-15h release tarballs (`*.tar.gz`; 19 on the KGPE-D16 page across
  seven releases, 12 on the KCMA-D8 page across four) — see the release
  tables in `../ASUS-KGPE-D16.md` / `../ASUS-KCMA-D8.md`
- Board-view schematics:
  [`ASUS_KGPE-D16_Rev_1.04_-_Schematics.zip`](https://15h.org/images/f/f0/ASUS_KGPE-D16_Rev_1.04_-_Schematics.zip)
  and [`Asus KCMA-D8 1.02 Schematics.zip`](https://15h.org/index.php/File:Asus_KCMA-D8_1.02_Schematics.zip)
  (OpenBoardView)
- 3D-printable fan mounts (KGPE-D16 page): `KGPE-D16_Chipsetfan_40mm.stl/.blend`,
  `KGPE-D16_Ramfan_80mm.stl/.blend`
- Motherboard diagram / jumper / photo images (wiki `File:` pages, CC BY-SA 4.0)

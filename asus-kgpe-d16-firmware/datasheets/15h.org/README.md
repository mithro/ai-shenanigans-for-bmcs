# 15h.org ASUS KCMA-D8 page — PDF mirror

A committed copy of **every PDF linked from the 15h.org wiki page
[ASUS KCMA-D8](https://15h.org/index.php/ASUS_KCMA-D8)** (permanent link:
[`oldid=2941`](https://15h.org/index.php?title=ASUS_KCMA-D8&oldid=2941), last
edited 8 July 2026, retrieved 2026-07-16). The page content itself is mirrored
in [`../../ASUS-KCMA-D8.md`](../../ASUS-KCMA-D8.md).

15h.org publishes its content under **CC BY-SA 4.0**; the PDFs themselves are
vendor documents (AMD / Aspeed / Infineon / Winbond / Nuvoton) that 15h.org
redistributes.

The KCMA-D8 is the Socket-C32 sibling of the KGPE-D16 — same SR5670/SP5100
chipset, same W83667HG-A Super I/O, same W83795G hardware monitor, and the
same **Aspeed AST2050 BMC on a removable ASMB4/ASMB5 module** — so this
documentation set applies almost verbatim to the parent directory's board.

Re-download / verify:

```sh
uv run download_datasheets.py
```

## Files (22 PDFs, ~42 MiB)

Verified 2026-07-16: every file carries the `%PDF` magic; page counts and
byte-identity below were produced with `pypdf` + SHA-256 against the PDFs
already committed in [`../`](../) (which were fetched independently from
AMD / Infineon / Nuvoton — so a byte-identical match also cross-validates the
15h.org mirror).

### AMD Opteron 4100 series (K10) — wiki section 4.1.1

| File | Pages | What it is |
|------|-------|------------|
| [44065_Arch2008.pdf](44065_Arch2008.pdf) | 368 | AGESA Interface Specification for Arch2008 (pub 44065) — linked for both the 4100 and 4200/4300 series |
| [31116.pdf](31116.pdf) | 475 | BIOS and Kernel Developer's Guide (BKDG) for AMD Family 10h Processors (pub 31116) |
| [40036.pdf](40036.pdf) | 8 | Family 10h AMD Opteron Processor Product Data Sheet (pub 40036) |
| [43374.pdf](43374.pdf) | 98 | AMD Family 10h Server and Workstation Processor Power and Thermal Data Sheet (pub 43374) — **the page's direct link is stale**; fetched via the wiki's renamed upload (see `download_datasheets.py`) |

### AMD Opteron 4200/4300 series (Bulldozer/Piledriver) — wiki section 4.1.2

| File | Pages | What it is |
|------|-------|------------|
| [42301_15h_Mod_00h-0Fh_BKDG.pdf](42301_15h_Mod_00h-0Fh_BKDG.pdf) | 639 | BKDG for AMD Family 15h Models 00h-0Fh Processors (pub 42301) |
| [49687_15h_Mod_00h-0Fh_Opteron_PDS.pdf](49687_15h_Mod_00h-0Fh_Opteron_PDS.pdf) | 7 | Family 15h Models 00h-0Fh AMD Opteron Processor Product Data Sheet (pub 49687) |
| [47414_15h_sw_opt_guide.pdf](47414_15h_sw_opt_guide.pdf) | 396 | Software Optimization Guide for AMD Family 15h Processors (pub 47414) |

### Aspeed AST2050 (the BMC) — wiki section 4.6

| File | Pages | What it is |
|------|-------|------------|
| [AST2050_Data_Sheet.pdf](AST2050_Data_Sheet.pdf) | 403 | Aspeed AST2050/AST1100 datasheet — **byte-identical (SHA-256) to [`../AST2050_AST1100_A3_Datasheet_V1.05.pdf`](../AST2050_AST1100_A3_Datasheet_V1.05.pdf)**, i.e. the A3 Datasheet V1.05 (May 2010) this repo already relies on |
| [Infineon-s25fl128p-128-mbit-3.0-v-flash-memory-datasheet-en.pdf](Infineon-s25fl128p-128-mbit-3.0-v-flash-memory-datasheet-en.pdf) | 44 | S25FL128P 128 Mbit SPI-NOR flash (BMC module flash) — **byte-identical to [`../S25FL128P_Datasheet.pdf`](../S25FL128P_Datasheet.pdf)** |

### AMD SR5670 northbridge (SR5690/5670/5650 family) — wiki section 4.7

| File | Pages | What it is |
|------|-------|------------|
| [AMD_SR5690_5670_5650_BIOS_Developers_Guide.pdf](AMD_SR5690_5670_5650_BIOS_Developers_Guide.pdf) | 44 | BIOS Developer's Guide |
| [48882-2.62.pdf](48882-2.62.pdf) | 266 | AMD I/O Virtualization Technology (IOMMU) Specification rev 2.62 (pub 48882) |
| [AMD_SR5690_5670_5650_Register_Reference_Guide.pdf](AMD_SR5690_5670_5650_Register_Reference_Guide.pdf) | 282 | Register Reference Guide — **byte-identical to [`../AMD_SR5690_Register_Reference_Guide_43871.pdf`](../AMD_SR5690_Register_Reference_Guide_43871.pdf)** (pub 43871) |
| [AMD_SR5690_5670_5650_Register_Programming_Requirements.pdf](AMD_SR5690_5670_5650_Register_Programming_Requirements.pdf) | 192 | Register Programming Requirements |
| [AMD_SR5670_Databook.pdf](AMD_SR5670_Databook.pdf) | 80 | SR5670 Product Databook |
| [SR56x0_Product_Errata.pdf](SR56x0_Product_Errata.pdf) | 33 | SR56x0 Product Errata |

### AMD SP5100 southbridge — wiki section 4.8

| File | Pages | What it is |
|------|-------|------------|
| [AMD_SP5100_BIOS_Developers_Guide.pdf](AMD_SP5100_BIOS_Developers_Guide.pdf) | 114 | BIOS Developer's Guide (wiki filename `AMD_SP5100_BIOS_Developer's_Guide.pdf`; apostrophe removed locally) |
| [AMD_SP5100_Register_Reference_Guide.pdf](AMD_SP5100_Register_Reference_Guide.pdf) | 317 | Register Reference Guide — **byte-identical to [`../AMD_SP5100_Register_Reference_Guide_44413.pdf`](../AMD_SP5100_Register_Reference_Guide_44413.pdf)** (pub 44413) |
| [AMD_SP5100_Register_Programming_Requirements.pdf](AMD_SP5100_Register_Programming_Requirements.pdf) | 74 | Register Programming Requirements |
| [AMD_SP5100_Databook.pdf](AMD_SP5100_Databook.pdf) | — | SP5100 Product Databook (AES-encrypted PDF — opens fine in viewers, but `pypdf` needs the `cryptography` package to count pages) |
| [SP5100_Product_Errata.pdf](SP5100_Product_Errata.pdf) | 32 | SP5100 Product Errata |

### Winbond / Nuvoton — wiki sections 4.9 / 4.10

| File | Pages | What it is |
|------|-------|------------|
| [W83667hg-a-datasheet-v1-2.pdf](W83667hg-a-datasheet-v1-2.pdf) | 319 | **Winbond W83667HG-A LPC Super I/O Data Book v1.2** — the full datasheet [`../README.md`](../README.md) previously recorded as NDA-gated with no public copy; this closes that gap. (Wiki filename carries an upload-hash suffix, removed locally.) |
| [Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf](Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf) | 152 | Nuvoton W83795G/ADG Hardware Monitor Datasheet V1.43 — same document as [`../W83795G_W83795ADG_Datasheet.pdf`](../W83795G_W83795ADG_Datasheet.pdf) (nuvoton.com copy) but **not** byte-identical (different PDF build of the same V1.43 datasheet) |

> **PDF `/Title` metadata is unreliable** in several of these vendor files
> (the W83667HG-A book claims "W83627DHG Data Sheet", both errata claim
> "RS600 DDR2 Memory Interface Tuning Guide", the AST2050 datasheet claims
> "AST1100 Software Programming Guide") — vendor authoring-template
> artifacts, as already noted for the AST2050 PDFs in `../README.md`.
> Identification above is from the documents' cover pages / content and the
> wiki page's link labels.

## Not mirrored (not PDFs)

The KCMA-D8 page also links non-PDF artifacts, intentionally not committed:

- coreboot-15h release tarballs (12 `*.tar.gz`, four releases × three build
  flavours) — see the release table in `../../ASUS-KCMA-D8.md`
- `Asus KCMA-D8 1.02 Schematics.zip` (OpenBoardView board views) —
  <https://15h.org/index.php/File:Asus_KCMA-D8_1.02_Schematics.zip>
- Motherboard diagram / photo PNGs+JPG (wiki `File:` pages, CC BY-SA 4.0)

# Aspeed SoC datasheets (shared reference)

The complete set of register-level datasheets for the Aspeed BMC SoC
generations, kept locally because they are the primary source of truth for the
whole reverse-engineering effort (the project standard is that every factual
claim carries a datasheet/firmware citation — see the top-level `CLAUDE.md`).
These span every Aspeed board in the repo, so they live here rather than under
any one board directory.

> **Why committed, not just linked:** Aspeed datasheets are semi-NDA and the
> public mirrors are the only reliable source; URLs rot. Committing the exact
> PDFs (with checksums below) makes the analysis reproducible. This matches how
> the board-specific datasheets are already vendored (see *Related*).

## Contents — `aspeed/`

| File | Document | Gen | Pages | Size | SHA-256 (first 16) |
|---|---|---|---:|---:|---|
| `AST2050_AST1100_A3_Datasheet_V1.02.pdf` | AST2050/AST1100 **A3** Datasheet V1.02 (Sep 2008) | G3 | 397 | 2.5 MB | `48e2ec3202fbfea9` |
| `AST2050_AST1100_A3_Datasheet_V1.05.pdf` | AST2050/AST1100 **A3** Datasheet V1.05 (May 2010) | G3 | 403 | 2.4 MB | `6dde868ba2499046` |
| `AST2400_Datasheet.pdf` | AST2400/AST1250 **A1** Datasheet V1.4 (Dec 2015) | G4 | 702 | 39 MB | `c229cec162e12d2d` |
| `AST2500_Datasheet.pdf` | AST2500/AST2520 **A2** Datasheet V1.6 (May 2017) | G5 | 833 | 5.5 MB | `757f13ac745c3d07` |
| `AST2600_Datasheet.pdf` | AST2600 **A3** Datasheet V1.2 | G6 | 1580 | 12 MB | `5205848143aeecb7` |

Verify with `sha256sum aspeed/*.pdf` (full digests are checked in `download.py`).
Re-fetch from the upstream mirrors with:

```sh
uv run datasheets/download.py
```

> **AST2050 `/Title` caveat:** both AST2050 PDFs' internal `/Title` metadata reads
> *"AST1100 Software Programming Guide"* — a bogus Aspeed LaTeX-template artifact.
> The **content is the A3 Datasheet** (page 1: "Integrated Remote Management
> Processor — A3 Datasheet"). Trust the page content, not the metadata title.

## The AST2050 is our boards' SoC

The **AST2050/AST1100** (G3) is the actual BMC on both the Dell C410X and the
ASUS KGPE-D16. V1.05 is the newer revision (same A3 silicon, 6 more pages). The
AST2400/2500/2600 are included because they are the register-compatible
successors that mainline Linux / OpenBMC / QEMU / culvert actually support, so
the AST2050 port work constantly cross-references them.

## On "programming manuals"

For these parts, Aspeed's **datasheet *is* the programming manual** — the AST2500
PDF is internally titled *"AST2500 Software Programming Guide"*, and the AST2600
datasheet (1580 pp) is a full register-programming reference.

The separate **Aspeed BMC SDK User Guide** (historically
`SDK_User_Guide_v09.01.pdf`, the published source of the Debug-UART password) is
**no longer public**: the AspeedTech-BMC/openbmc release asset is now a stub
reading *"please contact your ASPEED contact person for getting SDK user guide."*
It is therefore not vendored here. The debug-UART command grammar it documented
is reproduced (from culvert, and cross-checked against the AST2500 datasheet §11)
in [`../asus-kgpe-d16-firmware/CULVERT-UART-JTAG-DEBUG.md`](../asus-kgpe-d16-firmware/CULVERT-UART-JTAG-DEBUG.md).

## Why the whole set is here (Debug-UART / AHB back-doors)

These datasheets were collected to settle whether the AST2050 has the
Debug-UART / AHB back-door bridges culvert uses. Cross-referencing the whole
generation range established:

- **Hardware UART debug is AST2500-only.** The AST2500 §1.4 feature table lists
  it as **AST2500 = Yes, AST2400 = No, AST2300 = No** (§11 documents the
  `SCU70[29]`/`SCU2C[10]` strap + password shell). The AST2400 datasheet has no
  such interface — so the older AST2050 certainly lacks it.
- The **P2A (P-Bus→AHB)** and **LPC-to-AHB** back-doors culvert *can* use on the
  AST2050 are documented in the AST2050 datasheet (§36 / HICR5–8).

Full write-up:
[`../docs/plans/2026-07-07-culvert-ast2050-g3-support.md`](../docs/plans/2026-07-07-culvert-ast2050-g3-support.md)
§3.

## Related (board-specific datasheet collections)

The AST2050 datasheets here are **byte-identical copies** of the ones vendored in
the two board directories, where they sit alongside that board's component
datasheets (sensors, flash, chipset):

- [`../dell-c410x-firmware/datasheets/`](../dell-c410x-firmware/datasheets/) —
  C410X: AST2050 + PEX switch briefs + the 48-IC sensor fan-out.
- [`../asus-kgpe-d16-firmware/datasheets/`](../asus-kgpe-d16-firmware/datasheets/) —
  KGPE-D16: AST2050 + SPI-NOR flash + AMD SR5690/SP5100 chipset + W83795G.

Digi **NS9360** (HP iPDU, non-Aspeed) datasheets: `../hpe-ipdu-firmware/datasheets/`.

## Provenance / sources

| Document | Source |
|---|---|
| AST2050 V1.02 | `https://www.verical.com/datasheet/aspeed-technology-inc-interface-misc-ast2050a3-gp-4078885.pdf` (+ Wayback fallback) |
| AST2050 V1.05 | GitHub mirror `erik-smit/oohhh-what-does-this-ipmi-doooo-no-deedee-nooooo` → `…/ASPEED/AST2050 iRMC A3 Datasheet (1.05).pdf` |
| AST2400 | `https://www.vgamuseum.info/images/doc/aspeed/ast2400_datasheet.zip` (ZIP → `AST2400 - datasheet.pdf`) |
| AST2500 | `https://vgamuseum.info/images/doc/aspeed/ast2520a2gp_datasheet.pdf` |
| AST2600 | `https://www2.vgamuseum.info/images/doc/aspeed/ast2600_datasheet.pdf` |

AST2400/2500/2600 are mirrored by the [VGA Legacy MKIII museum](https://www.vgamuseum.info/).
License: Aspeed retains copyright; these are vendored for reference/research use only.

# Aspeed SoC datasheets (shared reference)

Register-level datasheets for the Aspeed BMC SoCs, kept locally because they are
the primary source of truth for the whole reverse-engineering effort (the
project standard is that every factual claim carries a datasheet/firmware
citation — see the top-level `CLAUDE.md`). These span all Aspeed boards in the
repo, so they live here rather than under any one board directory.

> **Why committed, not just linked:** Aspeed datasheets are semi-NDA and the
> public mirrors (vgamuseum) are the only reliable source; URLs rot. Committing
> the exact PDFs (with checksums below) makes the analysis reproducible. This
> matches how the board-specific datasheets are already vendored (see *Related*).

## Contents — `aspeed/`

| File | Document | Gen | Pages | Size | SHA-256 (first 16) |
|---|---|---|---:|---:|---|
| `AST2400_Datasheet.pdf` | AST2400/AST1250 **A1** Datasheet V1.4 (11 Dec 2015) | G4 | 702 | 39 MB | `c229cec162e12d2d` |
| `AST2500_Datasheet.pdf` | AST2500/AST2520 **A2** Datasheet V1.6 (12 May 2017) | G5 | 833 | 5.5 MB | `757f13ac745c3d07` |
| `AST2600_Datasheet.pdf` | AST2600 **A3** Datasheet V1.2 | G6 | 1580 | 12 MB | `5205848143aeecb7` |

Verify with `sha256sum aspeed/*.pdf` (full digests are checked in `download.py`).

Re-fetch from the upstream mirrors with:

```sh
uv run datasheets/download.py
```

## On "programming manuals"

For these parts, Aspeed's **datasheet *is* the programming manual** — the
AST2500 PDF is internally titled *"AST2500 Software Programming Guide"*, and the
AST2600 datasheet (1580 pp) is a full register-programming reference.

The separate **Aspeed BMC SDK User Guide** (historically
`SDK_User_Guide_v09.01.pdf`, the published source of the Debug-UART password) is
**no longer public**: the AspeedTech-BMC/openbmc release asset is now a stub
reading *"please contact your ASPEED contact person for getting SDK user guide."*
It is therefore not vendored here. The debug-UART command grammar it documented
is reproduced (from culvert) in
[`../asus-kgpe-d16-firmware/CULVERT-UART-JTAG-DEBUG.md`](../asus-kgpe-d16-firmware/CULVERT-UART-JTAG-DEBUG.md).

## Why these three matter here (Debug-UART / AHB back-doors)

These datasheets were collected to settle whether the **AST2050** (our boards'
SoC) has the Debug-UART / AHB back-door bridges culvert uses. Cross-referencing
them established:

- **Hardware UART debug** is **AST2500-only.** The AST2500 §1.4 feature table
  lists it as **AST2500 = Yes, AST2400 = No, AST2300 = No** (§11 documents the
  `SCU70[29]`/`SCU2C[10]` strap + password shell). The AST2400 datasheet has no
  such interface — so the older AST2050 certainly lacks it.
- The **P2A (P-Bus→AHB)** and **LPC-to-AHB** back-doors culvert *can* use on the
  AST2050 are documented in the AST2050 datasheet (see the analysis docs).

Full write-up:
[`../docs/plans/2026-07-07-culvert-ast2050-g3-support.md`](../docs/plans/2026-07-07-culvert-ast2050-g3-support.md)
§3.

## Related datasheets elsewhere in the repo

- **AST2050/AST1100 A3 Datasheet V1.02 (2008)** — the SoC on our actual boards —
  is at [`../dell-c410x-firmware/datasheets/AST2050_AST1100_Datasheet.pdf`](../dell-c410x-firmware/datasheets/AST2050_AST1100_Datasheet.pdf)
  (alongside the C410X board component datasheets).
- Digi **NS9360** (HP iPDU) datasheets: `../hpe-ipdu-firmware/datasheets/`.

## Provenance / sources

- AST2400: `https://www.vgamuseum.info/images/doc/aspeed/ast2400_datasheet.zip`
  (a ZIP containing `AST2400 - datasheet.pdf`).
- AST2500: `https://vgamuseum.info/images/doc/aspeed/ast2520a2gp_datasheet.pdf`
- AST2600: `https://www2.vgamuseum.info/images/doc/aspeed/ast2600_datasheet.pdf`

All three are hosted by the [VGA Legacy MKIII museum](https://www.vgamuseum.info/),
which mirrors the Aspeed documentation. License: Aspeed retains copyright; these
are vendored for reference/research use only.

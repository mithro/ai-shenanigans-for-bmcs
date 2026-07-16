#!/usr/bin/env python3
"""Mirror every PDF linked from the 15h.org "ASUS KCMA-D8" wiki page.

Source page: https://15h.org/index.php/ASUS_KCMA-D8
(permanent link: https://15h.org/index.php?title=ASUS_KCMA-D8&oldid=2941,
retrieved 2026-07-16). The page — and the files it hosts — are published
under CC BY-SA 4.0 by 15h.org.

The KCMA-D8 is the Socket-C32 sibling of the KGPE-D16 (same SR5670/SP5100
chipset, same W83667HG-A Super I/O, same W83795G hardware monitor, and the
same Aspeed AST2050 BMC on a removable ASMB4/ASMB5 module), so its
documentation set applies almost verbatim to this directory's board. See
../../ASUS-KCMA-D8.md for the full mirrored page content and
README.md (this directory) for the file-by-file mapping.

Local filenames match the wiki's basenames except two cleaned for shell
friendliness (apostrophe / upload-hash suffix removed):

  AMD_SP5100_BIOS_Developer's_Guide.pdf
      -> AMD_SP5100_BIOS_Developers_Guide.pdf
  W83667hg-a-datasheet-v1-2-67dd6c3d7aef5611225428.pdf
      -> W83667hg-a-datasheet-v1-2.pdf

Run with `uv` (no third-party deps, stdlib only):

    uv run download_datasheets.py

The script skips files that already exist and validates the %PDF magic on
each download. Delete a PDF to force re-download.
"""

import os
import sys
import time
import urllib.error
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Each entry: (local filename, url, description).
# Grouped by the wiki page section that links them.
PDFS = [
    # ============================================================
    # AMD Opteron 4100 Series (K10, Socket C32)
    # ============================================================
    (
        "44065_Arch2008.pdf",
        "https://15h.org/images/f/f7/44065_Arch2008.pdf",
        "AMD AGESA Interface Specification (pub 44065, Arch2008) - "
        "linked for both Opteron 4100 and 4200/4300 series",
    ),
    (
        "31116.pdf",
        "https://15h.org/images/6/63/31116.pdf",
        "AMD Family 10h BIOS and Kernel Developer's Guide (pub 31116) - "
        "Opteron 4100 series",
    ),
    (
        "40036.pdf",
        "https://15h.org/images/1/15/40036.pdf",
        "AMD Opteron 4100 Series Product Data Sheet (pub 40036)",
    ),
    # NOTE: the KCMA-D8 page links https://15h.org/images/2/2b/43374.pdf, but
    # that direct link is STALE (redirects to the wiki Home page). The file
    # was renamed on the wiki; File:43374.pdf redirects to the long name
    # below, whose current upload path is used here.
    (
        "43374.pdf",
        "https://15h.org/images/9/94/43374_-_AMD_Family_10h_Server_and_Workstation_Processor_Power_and_Thermal_Data_Sheet_%2843374%29.pdf",
        "AMD Family 10h Server and Workstation Processor Power and Thermal "
        "Data Sheet (pub 43374) - Opteron 4100 series",
    ),

    # ============================================================
    # AMD Opteron 4200/4300 Series (Bulldozer / Piledriver)
    # ============================================================
    (
        "42301_15h_Mod_00h-0Fh_BKDG.pdf",
        "https://15h.org/images/b/be/42301_15h_Mod_00h-0Fh_BKDG.pdf",
        "AMD Family 15h Models 00h-0Fh BIOS and Kernel Developer's Guide "
        "(pub 42301) - Opteron 4200/4300 series",
    ),
    (
        "49687_15h_Mod_00h-0Fh_Opteron_PDS.pdf",
        "https://15h.org/images/e/ee/49687_15h_Mod_00h-0Fh_Opteron_PDS.pdf",
        "AMD Family 15h Models 00h-0Fh Opteron Product Data Sheet (pub 49687)",
    ),
    (
        "47414_15h_sw_opt_guide.pdf",
        "https://15h.org/images/a/af/47414_15h_sw_opt_guide.pdf",
        "AMD Family 15h Software Optimization Guide (pub 47414)",
    ),

    # ============================================================
    # ASPEED AST2050 (the BMC this repository targets)
    # ============================================================
    (
        "AST2050_Data_Sheet.pdf",
        "https://15h.org/images/1/18/AST2050_Data_Sheet.pdf",
        "Aspeed AST2050 Datasheet (15h.org copy) - compare the two A3 "
        "datasheet revisions committed in ../",
    ),
    (
        "Infineon-s25fl128p-128-mbit-3.0-v-flash-memory-datasheet-en.pdf",
        "https://15h.org/images/6/64/Infineon-s25fl128p-128-mbit-3.0-v-flash-memory-datasheet-en.pdf",
        "S25FL128P 128Mbit SPI NOR flash datasheet (Infineon) - BMC module "
        "flash; also committed in ../ from infineon.com",
    ),

    # ============================================================
    # AMD SR5670 northbridge (SR5690/5670/5650 family docs)
    # ============================================================
    (
        "AMD_SR5690_5670_5650_BIOS_Developers_Guide.pdf",
        "https://15h.org/images/c/c3/AMD_SR5690_5670_5650_BIOS_Developers_Guide.pdf",
        "AMD SR5690/5670/5650 BIOS Developer's Guide",
    ),
    (
        "48882-2.62.pdf",
        "https://15h.org/images/2/24/48882-2.62.pdf",
        "AMD IOMMU Architectural Specification rev 2.62 (pub 48882)",
    ),
    (
        "AMD_SR5690_5670_5650_Register_Reference_Guide.pdf",
        "https://15h.org/images/9/9a/AMD_SR5690_5670_5650_Register_Reference_Guide.pdf",
        "AMD SR5690/5670/5650 Register Reference Guide - same doc family as "
        "../AMD_SR5690_Register_Reference_Guide_43871.pdf",
    ),
    (
        "AMD_SR5690_5670_5650_Register_Programming_Requirements.pdf",
        "https://15h.org/images/b/b0/AMD_SR5690_5670_5650_Register_Programming_Requirements.pdf",
        "AMD SR5690/5670/5650 Register Programming Requirements",
    ),
    (
        "AMD_SR5670_Databook.pdf",
        "https://15h.org/images/2/23/AMD_SR5670_Databook.pdf",
        "AMD SR5670 Product Databook",
    ),
    (
        "SR56x0_Product_Errata.pdf",
        "https://15h.org/images/5/5d/SR56x0_Product_Errata.pdf",
        "AMD SR56x0 Product Errata",
    ),

    # ============================================================
    # AMD SP5100 southbridge
    # ============================================================
    (
        "AMD_SP5100_BIOS_Developers_Guide.pdf",
        "https://15h.org/images/a/ad/AMD_SP5100_BIOS_Developer%27s_Guide.pdf",
        "AMD SP5100 BIOS Developer's Guide (wiki filename has an apostrophe; "
        "cleaned locally)",
    ),
    (
        "AMD_SP5100_Register_Reference_Guide.pdf",
        "https://15h.org/images/7/78/AMD_SP5100_Register_Reference_Guide.pdf",
        "AMD SP5100 Register Reference Guide - same doc family as "
        "../AMD_SP5100_Register_Reference_Guide_44413.pdf",
    ),
    (
        "AMD_SP5100_Register_Programming_Requirements.pdf",
        "https://15h.org/images/7/7b/AMD_SP5100_Register_Programming_Requirements.pdf",
        "AMD SP5100 Register Programming Requirements",
    ),
    (
        "AMD_SP5100_Databook.pdf",
        "https://15h.org/images/d/df/AMD_SP5100_Databook.pdf",
        "AMD SP5100 Product Databook",
    ),
    (
        "SP5100_Product_Errata.pdf",
        "https://15h.org/images/e/ec/SP5100_Product_Errata.pdf",
        "AMD SP5100 Product Errata",
    ),

    # ============================================================
    # Winbond / Nuvoton (host Super I/O + hardware monitor)
    # ============================================================
    (
        "W83667hg-a-datasheet-v1-2.pdf",
        "https://15h.org/images/3/34/W83667hg-a-datasheet-v1-2-67dd6c3d7aef5611225428.pdf",
        "Winbond W83667HG-A LPC Super I/O Data Book v1.2 - fills the "
        "'NDA-gated, no public copy' gap recorded in ../README.md",
    ),
    (
        "Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf",
        "https://15h.org/images/3/31/Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf",
        "Nuvoton W83795G/ADG Hardware Monitor Datasheet V1.43 - same doc as "
        "../W83795G_W83795ADG_Datasheet.pdf (nuvoton.com copy)",
    ),
]


def download_file(url, filepath, description, timeout=120):
    """Download one URL to filepath. Returns True on success/already-present."""
    print(f"  Downloading: {description}")
    print(f"  -> {os.path.basename(filepath)}")

    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        if size > 1000:
            print(f"  SKIP: Already exists ({size:,} bytes)")
            return True

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) "
        "Gecko/20100101 Firefox/128.0",
        "Accept": "application/pdf,*/*",
    }
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
    except urllib.error.HTTPError as e:
        print(f"    FAIL: HTTP {e.code} - {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"    FAIL: {e.reason}")
        return False

    if len(data) < 1000:
        print(f"    FAIL: Very small ({len(data)} bytes), not saving")
        return False
    if not data[:5].startswith(b"%PDF"):
        print(f"    FAIL: Not a PDF file (starts with {data[:20]!r}), not saving")
        return False

    with open(filepath, "wb") as f:
        f.write(data)
    print(f"    OK: {len(data):,} bytes")
    return True


def main():
    print("=" * 70)
    print("15h.org ASUS KCMA-D8 wiki page - PDF mirror downloader")
    print("=" * 70)

    failed = []
    for filename, url, description in PDFS:
        filepath = os.path.join(SCRIPT_DIR, filename)
        print()
        if not download_file(url, filepath, description):
            failed.append((filename, url))
        # Be polite - small delay between downloads
        time.sleep(0.5)

    print()
    print("=" * 70)
    print(f"Results: {len(PDFS) - len(failed)}/{len(PDFS)} present")
    print("=" * 70)
    if failed:
        print("\nFailed downloads:")
        for filename, url in failed:
            print(f"  {filename}\n    URL: {url}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

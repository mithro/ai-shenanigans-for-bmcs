#!/usr/bin/env python3
"""Download datasheets for the ASUS KGPE-D16 BMC-relevant hardware.

The ASUS KGPE-D16 is a dual Socket-G34 AMD Opteron server board whose BMC is an
Aspeed AST2050 (on the ASUS ASMB4-iKVM / ASMB5 module). This project reverse
engineers Raptor Engineering's abandoned AST2050 Linux port; the chips below are
the ones that port and the board's debug/JTAG analysis actually touch.

Several entries are the *same silicon* as the Dell C410X (which uses the same
AST2050 SoC and the same SPI-NOR flash family), so they reuse the URLs proven in
`dell-c410x-firmware/datasheets/download_datasheets.py`. The KGPE-D16-specific
additions are the host-side AMD chipset (SR5690 / SP5100) and the board's
hardware monitor.

Run with `uv` (no third-party deps, stdlib only):

    uv run download_datasheets.py

The script skips files that already exist. Delete a PDF to force re-download.
"""

import os
import ssl
import sys
import time
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Each entry: (filename, [urls...], description)
DATASHEETS = [
    # ============================================================
    # BMC SoC  --  shared with dell-c410x-firmware (same AST2050)
    # ============================================================
    # Aspeed's full datasheet is NDA-only. This is the AST2050/AST1100 (A3)
    # datasheet that circulates via aggregators / the Wayback Machine.
    (
        "AST2050_AST1100_A3_Datasheet_V1.02.pdf",
        [
            "https://www.verical.com/datasheet/aspeed-technology-inc-interface-misc-ast2050a3-gp-4078885.pdf",
            "https://web.archive.org/web/2id_/https://www.verical.com/datasheet/aspeed-technology-inc-interface-misc-ast2050a3-gp-4078885.pdf",
        ],
        "Aspeed AST2050/AST1100 A3 Datasheet V1.02 (Sep 2008) - BMC SoC (ARM926EJ-S @ 266 MHz)",
    ),
    (
        "AST2050_AST1100_A3_Datasheet_V1.05.pdf",
        ["https://raw.githubusercontent.com/erik-smit/oohhh-what-does-this-ipmi-doooo-no-deedee-nooooo/master/1-discovering/beetje-poepe-daan/ASPEED/AST2050%20iRMC%20A3%20Datasheet%20(1.05).pdf"],
        "Aspeed AST2050/AST1100 A3 Datasheet V1.05 (May 2010) - newer revision of the same datasheet",
    ),

    # ============================================================
    # SPI NOR flash  --  shared with dell-c410x-firmware
    # These are exactly the chips Raptor's AST2050 U-Boot autodetects
    # (RAPTOR-PORTING-GUIDE.md:431 lists STM25P64, STM25P128, S25FL128P,
    # MX25L128D, W25X64). BMC_FW1 on the KGPE-D16 holds one of them.
    # ============================================================
    (
        "M25P64_Datasheet.pdf",
        [
            "https://media.digikey.com/pdf/Data%20Sheets/Micron%20Technology%20Inc%20PDFs/M25P64_Rev_12.pdf",
            "https://www.micron.com/-/media/client/global/documents/products/data-sheet/nor-flash/serial-nor/m25p/m25p64.pdf",
        ],
        "M25P64 (STM25P64) - 64Mbit SPI NOR Flash (STMicro/Micron)",
    ),
    (
        "M25P128_Datasheet.pdf",
        [
            "https://www.micron.com/-/media/client/global/documents/products/data-sheet/nor-flash/serial-nor/m25p/m25p128.pdf",
            "http://www.applelogic.org/files/M25P128.pdf",
        ],
        "M25P128 (STM25P128) - 128Mbit SPI NOR Flash (STMicro/Micron)",
    ),
    (
        "S25FL128P_Datasheet.pdf",
        ["https://www.infineon.com/dgdl/Infineon-S25FL128P_128_MBIT_3.0_V_FLASH_MEMORY-DataSheet-v14_00-EN.pdf?fileId=8ac78c8c7d0d8da4017d0ed4d9135357"],
        "S25FL128P - 128Mbit 3.0V SPI Flash (Spansion/Cypress/Infineon)",
    ),
    (
        "MX25L12835F_Datasheet.pdf",
        [
            "https://datasheet.octopart.com/MX25L12835FZ2I-10G-Macronix-datasheet-14372549.pdf",
            "https://www.mxic.com.tw/Lists/Datasheet/Attachments/9173/MX25L12835F,%203V,%20128Mb,%20v1.7.pdf",
        ],
        "MX25L12835F (MX25L128D) - 128Mbit 3V SPI Flash (Macronix)",
    ),
    (
        "W25X64_Datasheet.pdf",
        [
            "https://media.digikey.com/pdf/data%20sheets/winbond%20pdfs/w25x16,16a,32,64.pdf",
            "https://web.archive.org/web/2id_/https://media.digikey.com/pdf/data%20sheets/winbond%20pdfs/w25x16,16a,32,64.pdf",
        ],
        "W25X64 - 64Mbit SPI NOR Flash, Dual Output (Winbond) - full datasheet (W25X16/16A/32/64, Rev I, 50pp)",
    ),

    # ============================================================
    # Temperature sensor  --  shared with dell-c410x-firmware
    # Raptor's reconstructed device tree binds one LM75 as
    # 'ti,lm75' @ I2C 0x48 (RAPTOR_ENGINEERING_AST2050_ANALYSIS.md:1532).
    # ============================================================
    (
        "LM75_Datasheet.pdf",
        ["https://www.ti.com/lit/ds/symlink/lm75b.pdf"],
        "LM75 - Digital Temperature Sensor (Texas Instruments) - BMC I2C0 @ 0x48",
    ),

    # ============================================================
    # FRU / board EEPROM  --  shared with dell-c410x-firmware.
    # Class reference for the "ASUS EEPROM" the AST2050 U-Boot accesses on
    # I2C channel 5 (RAPTOR-UBOOT-ANALYSIS.md:134) at 7-bit 0x50 with 2-byte
    # internal addressing (ast2050.h:213-214 -> >=24C32-class). The exact
    # density/vendor on the ASMB4/5 module is unread; AT24C256 stands in.
    # ============================================================
    (
        "AT24C256_Datasheet.pdf",
        ["https://ww1.microchip.com/downloads/en/DeviceDoc/doc0670.pdf"],
        "AT24C256 - 256Kbit I2C EEPROM (Atmel/Microchip) - class ref for BMC FRU EEPROM @ 0x50",
    ),

    # ============================================================
    # KGPE-D16-specific additions -- host-side board context.
    # These chips are NOT on the BMC's own I2C bus; they are the x86
    # host platform silicon, managed by coreboot. They are included
    # because this directory's JTAG/HDT scan-chain analysis
    # (JTAG-HEADERS.md, RPI4-OPENOCD-JTAG-WIRING.md) references them,
    # and the coreboot port shares this repo's SoC porting goal.
    # Board BOM confirmed from coreboot 4.11 src/mainboard/asus/kgpe-d16/
    # devicetree.cb.
    # ============================================================

    # Hardware monitor: coreboot `chip drivers/i2c/w83795` @ host I2C 0x2f.
    (
        "W83795G_W83795ADG_Datasheet.pdf",
        ["https://www.nuvoton.com/resource-files/Nuvoton_W83795G_W83795ADG_Datasheet_V1.43.pdf"],
        "Nuvoton/Winbond W83795G/ADG - Hardware Monitor (host I2C 0x2f, fans/voltages/temps)",
    ),

    # AMD SR5690 northbridge / IOMMU (RD890 family). coreboot models it as
    # southbridge/amd/sr5650. AMD's legacy www.amd.com/system/files/TechDocs/
    # links now serve an HTML portal page; the live pattern is
    # .../content/dam/amd/en/documents/archived-tech-docs/programmer-references/.
    # The Register Reference Guide (43871) is the register-level doc that
    # matches this repo's analysis style.
    (
        "AMD_SR5690_Register_Reference_Guide_43871.pdf",
        [
            "https://www.amd.com/content/dam/amd/en/documents/archived-tech-docs/programmer-references/43871.pdf",
            "https://theretroweb.com/chip/documentation/43869-64c7c40660d33123068113.pdf",
        ],
        "AMD SR5690/5670/5650 Register Reference Guide (RD890 NB/IOMMU) - HDT scan-chain node",
    ),

    # AMD SP5100 southbridge (SB700 family, embedded 8051 SMBus core).
    # coreboot models it as southbridge/amd/sb700.
    (
        "AMD_SP5100_Register_Reference_Guide_44413.pdf",
        [
            "https://www.amd.com/content/dam/amd/en/documents/archived-tech-docs/programmer-references/44413.pdf",
            "https://theretroweb.com/chip/documentation/44413-64c7c6c5a7fab785584815.pdf",
        ],
        "AMD SP5100 Register Reference Guide (SB700 southbridge, 8051 SMBus core) - HDT scan-chain node",
    ),
]

# Chips confirmed present on the KGPE-D16 (coreboot devicetree.cb / this
# directory's analysis) for which NO clean, redistributable public PDF was
# found. Listed so the gap is visible rather than silently omitted; see the
# README "Still missing" section. `main()` prints these at the end.
KNOWN_UNAVAILABLE = [
    # NOTE (2026-07-16): the W83667HG-A gap is CLOSED — the full 319pp Data
    # Book v1.2 is committed at 15h.org/W83667hg-a-datasheet-v1-2.pdf
    # (mirrored from the 15h.org ASUS KCMA-D8 page by
    # 15h.org/download_datasheets.py), so it no longer appears in this list.
    (
        "BMC Ethernet PHY (ASMB4/ASMB5 module, RMII)",
        "Raptor's device tree sets mac0 phy-mode='rmii' (external PHY needed) but "
        "the part is UNIDENTIFIED - RAPTOR-PORTING-GUIDE.md:958 lists it as an "
        "open question. RTL8201EL/RTL8211BN/RTL8201N in the analysis are the "
        "AST2050 driver's *supported* PHYs, not a board identification. Needs a "
        "board photo / ASMB schematic. Candidate (RTL8201) datasheet if confirmed:"
        " http://realtek.info/pdf/rtl8201.pdf",
        "Unidentified - open item (needs schematic/photo)",
    ),
    (
        "BMC FRU EEPROM exact part (I2C 0x50)",
        "Confirmed present (ast2050.h:213-214, RAPTOR-UBOOT-ANALYSIS.md:134) but "
        "density/vendor unread; AT24C256_Datasheet.pdf is committed as a "
        ">=24C32-class stand-in until the marking is read off the chip.",
        "Class ref committed (AT24C256); exact part unknown",
    ),
    (
        "AST2050 on-module DDR2 SDRAM (64 MB @ 0x40000000)",
        "Generic behaviour is covered by JEDEC JESD79-2; the specific SDRAM part "
        "on the ASMB4/5 module is unidentified. JEDEC standards are free but not "
        "redistributable here.",
        "JEDEC JESD79-2 (DDR2 SDRAM standard), jedec.org (registration)",
    ),
    # NOTE: the full Aspeed AST2050/AST1100 A3 Datasheet IS committed (V1.02 +
    # V1.05); it is not officially distributed by Aspeed but public copies exist.
    # It therefore does not belong in this "unavailable" list.
]


def download_from_url(url, filepath, timeout=60):
    """Try to download a single URL. Returns True on success."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "application/pdf,*/*",
    }
    req = urllib.request.Request(url, headers=headers)

    # Some manufacturer sites have broken cert chains; don't verify.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            data = response.read()

            if len(data) < 1000:
                print(f"    WARN: Very small ({len(data)} bytes), skipping")
                return False

            if not data[:5].startswith(b"%PDF"):
                print(f"    WARN: Not a PDF file (starts with {data[:20]!r}), skipping")
                return False

            with open(filepath, "wb") as f:
                f.write(data)

            print(f"    OK: {len(data):,} bytes")
            return True

    except urllib.error.HTTPError as e:
        print(f"    FAIL: HTTP {e.code} - {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"    FAIL: {e.reason}")
        return False


def download_file(urls, filepath, description, timeout=60):
    """Download a file, trying multiple URLs as fallbacks."""
    print(f"  Downloading: {description}")
    print(f"  -> {os.path.basename(filepath)}")

    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        if size > 1000:
            print(f"  SKIP: Already exists ({size:,} bytes)")
            return True

    if isinstance(urls, str):
        urls = [urls]

    for i, url in enumerate(urls):
        print(f"  Trying URL {i + 1}/{len(urls)}: {url}")
        if download_from_url(url, filepath, timeout=timeout):
            return True

    return False


def main():
    print("=" * 70)
    print("ASUS KGPE-D16 BMC Component Datasheet Downloader")
    print("=" * 70)

    succeeded = []
    failed = []

    for filename, urls, description in DATASHEETS:
        filepath = os.path.join(SCRIPT_DIR, filename)
        print()
        ok = download_file(urls, filepath, description)
        if ok:
            succeeded.append((filename, description))
        else:
            failed.append((filename, urls, description))
        # Be polite - small delay between downloads
        time.sleep(0.5)

    print()
    print("=" * 70)
    print(f"Results: {len(succeeded)} succeeded, {len(failed)} failed")
    print("=" * 70)

    if succeeded:
        print("\nSuccessfully present:")
        for filename, description in succeeded:
            filepath = os.path.join(SCRIPT_DIR, filename)
            size = os.path.getsize(filepath)
            print(f"  {filename} ({size:,} bytes)")

    if failed:
        print("\nFailed downloads (see README 'Still missing' section):")
        for filename, urls, description in failed:
            print(f"  {filename}")
            print(f"    {description}")
            if isinstance(urls, str):
                urls = [urls]
            for url in urls:
                print(f"    URL: {url}")

    print()
    print("=" * 70)
    print("Known-unavailable (present on the board, no clean public PDF):")
    print("=" * 70)
    for part, reason, pointer in KNOWN_UNAVAILABLE:
        print(f"  {part}")
        print(f"    why: {reason}")
        print(f"    ->   {pointer}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

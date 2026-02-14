#!/usr/bin/env python3
"""Download datasheets for all identified Dell C410X hardware components.

This script downloads publicly available datasheets from manufacturer websites
for all ICs identified in the Dell PowerEdge C410X BMC firmware analysis.
"""

import os
import ssl
import sys
import time
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Each entry: (filename, url, description)
DATASHEETS = [
    # === BMC SoC ===
    # Note: Aspeed datasheets are typically NDA-only. The verical.com copy
    # may be slow; Wayback Machine is a reliable fallback.
    (
        "AST2050_AST1100_Datasheet.pdf",
        [
            "https://www.verical.com/datasheet/aspeed-technology-inc-interface-misc-ast2050a3-gp-4078885.pdf",
            "https://web.archive.org/web/2024/https://www.verical.com/datasheet/aspeed-technology-inc-interface-misc-ast2050a3-gp-4078885.pdf",
        ],
        "Aspeed AST2050/AST1100 - BMC SoC (ARM926EJ-S @ 266 MHz)",
    ),

    # === Temperature Sensors ===
    (
        "ADT7462_Datasheet.pdf",
        [
            "https://www.onsemi.com/pdf/datasheet/adt7462-d.pdf",
            "https://web.archive.org/web/2024/https://www.onsemi.com/pdf/datasheet/adt7462-d.pdf",
        ],
        "ADT7462 - Flexible Temperature, Voltage Monitor & Fan Controller (ON Semi / formerly Analog Devices)",
    ),
    (
        "TMP75_Datasheet.pdf",
        ["https://www.ti.com/lit/ds/symlink/tmp75.pdf"],
        "TMP75 - Digital Temperature Sensor (Texas Instruments) - 16x per-slot sensors",
    ),
    (
        "LM75_Datasheet.pdf",
        ["https://www.ti.com/lit/ds/symlink/lm75b.pdf"],
        "LM75 - Digital Temperature Sensor (Texas Instruments) - front board sensor",
    ),

    # === Power Monitoring ===
    (
        "INA219_Datasheet.pdf",
        ["https://www.ti.com/lit/ds/symlink/ina219.pdf"],
        "INA219 - Zero-Drift Bidirectional Current/Power Monitor (Texas Instruments) - 16x per-slot monitors",
    ),

    # === I2C Multiplexers ===
    (
        "PCA9544A_Datasheet.pdf",
        [
            "https://www.nxp.com/docs/en/data-sheet/PCA9544A.pdf",
            "https://www.ti.com/lit/ds/symlink/pca9544a.pdf",
        ],
        "PCA9544A - 4-Channel I2C-bus Multiplexer with Interrupt Logic (NXP)",
    ),
    (
        "PCA9548A_Datasheet.pdf",
        [
            "https://www.nxp.com/docs/en/data-sheet/PCA9548A.pdf",
            "https://www.ti.com/lit/ds/symlink/pca9548a.pdf",
        ],
        "PCA9548A - 8-Channel I2C-bus Switch with Reset (NXP) - 2x routing to 16 TMP75 sensors",
    ),

    # === GPIO Expanders ===
    (
        "PCA9555_Datasheet.pdf",
        [
            "https://www.ti.com/lit/ds/symlink/pca9555.pdf",
            "https://www.nxp.com/docs/en/data-sheet/PCA9555.pdf",
        ],
        "PCA9555 - 16-bit I2C GPIO Expander (NXP/TI) - 5x for slot management",
    ),

    # === EEPROM ===
    (
        "AT24C256_Datasheet.pdf",
        ["https://ww1.microchip.com/downloads/en/DeviceDoc/doc0670.pdf"],
        "AT24C256 - 256Kbit I2C EEPROM (Atmel/Microchip) - FRU data storage",
    ),

    # === SPI NOR Flash (possible flash chips detected by U-Boot) ===
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
        ["https://www.winbond.com/productResource-files/DA05-0006.pdf"],
        "W25X64 - 64Mbit SPI Flash with Dual Output (Winbond)",
    ),

    # === PCIe Switches ===
    # Note: Full PLX/Broadcom datasheets are typically under NDA.
    # Product briefs are publicly available.
    (
        "PEX8696_ProductBrief.pdf",
        ["https://docs.broadcom.com/doc/12351832"],
        "PEX8696 - 96-Lane PCIe Gen2 Switch Product Brief (PLX/Broadcom)",
    ),
    (
        "PEX8647_ProductBrief.pdf",
        ["https://docs.broadcom.com/doc/12351838"],
        "PEX8647 - 48-Lane PCIe Gen2 Switch Product Brief (PLX/Broadcom)",
    ),
]


def download_from_url(url, filepath, timeout=60):
    """Try to download a single URL. Returns True on success."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "application/pdf,*/*",
    }
    req = urllib.request.Request(url, headers=headers)

    # Create an SSL context that doesn't verify certificates (some manufacturer
    # sites have broken cert chains)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            data = response.read()

            if len(data) < 1000:
                print(f"    WARN: Very small ({len(data)} bytes), skipping")
                return False

            # Check if it's actually a PDF (starts with %PDF)
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
    except Exception as e:
        print(f"    FAIL: {e}")
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
    print("Dell C410X Component Datasheet Downloader")
    print("=" * 70)
    print()

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
        print("\nSuccessfully downloaded:")
        for filename, description in succeeded:
            filepath = os.path.join(SCRIPT_DIR, filename)
            size = os.path.getsize(filepath)
            print(f"  {filename} ({size:,} bytes)")

    if failed:
        print("\nFailed downloads:")
        for filename, urls, description in failed:
            print(f"  {filename}")
            print(f"    {description}")
            if isinstance(urls, str):
                urls = [urls]
            for url in urls:
                print(f"    URL: {url}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

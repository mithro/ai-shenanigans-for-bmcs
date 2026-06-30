#!/usr/bin/env python3
"""
Analyze HPE iPDU firmware for extension bar ("stick") communication protocol strings.
Big-endian ARM926EJ-S, RAM base 0x00004000.
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

# RAM base address
RAM_BASE = 0x00004000

# Minimum string length to consider
MIN_STRING_LENGTH = 4

# Web UI noise patterns to filter out
WEB_NOISE_PATTERNS = [
    r'onclick',
    r'href=',
    r'class=',
    r'style=',
    r'display:',
    r'<[/a-zA-Z]',  # HTML tags
    r'\.css',
    r'\.js',
    r'\.html',
    r'javascript:',
    r'function\s*\(',
    r'var\s+',
    r'getElementById',
    r'innerHTML',
    r'value=',
    r'name=',
    r'type=',
    r'id=',
    r'src=',
    r'alt=',
    r'width=',
    r'height=',
    r'border=',
    r'align=',
    r'valign=',
    r'colspan=',
    r'rowspan=',
    r'cellpadding',
    r'cellspacing',
    r'&nbsp;',
    r'&lt;',
    r'&gt;',
    r'&amp;',
]

# Category search patterns (case-insensitive)
CATEGORIES = {
    'stick_bar_extension': [
        r'\bstick\b',
        r'\bbar\b',
        r'\bext\s+bar\b',
        r'\bextension\b',
    ],
    'outlet_module': [
        r'\boutlet\b',
        r'\bmodule\b',
    ],
    'firmware_update': [
        r'\bfirmware\s+update\b',
        r'\bflash\b',
        r'\bupgrade\b',
        r'\bdownload\b',
        r'\bupload\b',
    ],
    'protocol_commands': [
        r'\bcmd\b',
        r'\bcommand\b',
        r'\bpacket\b',
        r'\bframe\b',
        r'\bheader\b',
        r'\bpayload\b',
        r'\back\b',
        r'\bnak\b',
        r'\bresponse\b',
        r'\brequest\b',
        r'\bregister\b',
    ],
}


def extract_strings(firmware_data: bytes, min_length: int = MIN_STRING_LENGTH) -> List[Tuple[int, str]]:
    """Extract ASCII strings from firmware binary."""
    strings = []
    current_string = bytearray()
    start_offset = 0

    for offset, byte in enumerate(firmware_data):
        # Printable ASCII range
        if 32 <= byte <= 126:
            if not current_string:
                start_offset = offset
            current_string.append(byte)
        else:
            if len(current_string) >= min_length:
                try:
                    decoded = current_string.decode('ascii')
                    strings.append((start_offset, decoded))
                except UnicodeDecodeError:
                    pass
            current_string = bytearray()

    # Handle final string
    if len(current_string) >= min_length:
        try:
            decoded = current_string.decode('ascii')
            strings.append((start_offset, decoded))
        except UnicodeDecodeError:
            pass

    return strings


def is_web_noise(text: str) -> bool:
    """Check if string contains web UI noise."""
    for pattern in WEB_NOISE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def categorize_string(text: str) -> List[str]:
    """Determine which categories a string belongs to."""
    categories = []
    for category, patterns in CATEGORIES.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                categories.append(category)
                break  # Only add category once
    return categories


def analyze_firmware(firmware_path: Path):
    """Analyze firmware and extract protocol-related strings."""
    print(f"Analyzing firmware: {firmware_path}")
    print(f"RAM base address: 0x{RAM_BASE:08X}")
    print("=" * 80)

    # Read firmware
    firmware_data = firmware_path.read_bytes()
    print(f"Firmware size: {len(firmware_data):,} bytes")
    print()

    # Extract all strings
    print("Extracting strings...")
    all_strings = extract_strings(firmware_data)
    print(f"Found {len(all_strings):,} total strings")
    print()

    # Filter and categorize
    categorized_findings = defaultdict(list)

    for file_offset, text in all_strings:
        # Skip web noise
        if is_web_noise(text):
            continue

        # Calculate memory address
        mem_address = file_offset + RAM_BASE

        # Only include strings from firmware string tables (> 0x00690000)
        if mem_address < 0x00690000:
            continue

        # Categorize
        categories = categorize_string(text)
        if categories:
            for category in categories:
                categorized_findings[category].append((mem_address, text))

    # Print results by category
    category_names = {
        'stick_bar_extension': 'Extension Bar / Stick References',
        'outlet_module': 'Outlet / Module References',
        'firmware_update': 'Firmware Update / Flash Operations',
        'protocol_commands': 'Protocol / Command References',
    }

    for category in ['stick_bar_extension', 'outlet_module', 'firmware_update', 'protocol_commands']:
        if category not in categorized_findings:
            continue

        findings = sorted(categorized_findings[category], key=lambda x: x[0])

        print("=" * 80)
        print(f"{category_names[category]}")
        print("=" * 80)
        print(f"Found {len(findings)} strings\n")

        for mem_address, text in findings:
            # Print address and string, with proper formatting
            print(f"0x{mem_address:08X}  {repr(text)}")

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total_findings = sum(len(findings) for findings in categorized_findings.values())
    print(f"Total interesting strings found: {total_findings}")
    for category, findings in categorized_findings.items():
        print(f"  {category_names[category]}: {len(findings)}")


def main():
    firmware_path = Path("extracted/2.0.51.12_Z7550-02475_decompressed.bin")

    if not firmware_path.exists():
        print(f"ERROR: Firmware file not found: {firmware_path}")
        return 1

    analyze_firmware(firmware_path)
    return 0


if __name__ == "__main__":
    exit(main())

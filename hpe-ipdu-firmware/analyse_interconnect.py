#!/usr/bin/env python3
"""Analyse inter-PDU communication and daisy-chain protocol in HPE iPDU firmware.

This script searches the firmware for:
1. Daisy-chain / cascading topology protocol
2. PLC (Power Line Communication) modem references
3. Extension bar bus protocol
4. Redundancy management
5. Upstream/downstream detect pin usage
6. GPIO function hints
"""

import os
import struct
import re

EXTRACT_DIR = "extracted"
RAM_BASE = 0x00004000


def extract_all_strings(data, min_len=4):
    """Extract all printable strings from data."""
    strings = []
    current = b''
    start = 0
    for i, byte in enumerate(data):
        if 0x20 <= byte < 0x7F:
            if not current:
                start = i
            current += bytes([byte])
        elif byte == 0:
            if current and len(current) >= min_len:
                strings.append((start, current.decode('ascii')))
            current = b''
        else:
            if current and len(current) >= min_len:
                strings.append((start, current.decode('ascii')))
            current = b''
    return strings


def is_web_noise(s):
    """Check if a string is likely web UI noise (HTML/JS/CSS)."""
    return any(tag in s.lower() for tag in [
        '<td', '<tr', '<div', '<input', '<img', '<script', '<span',
        'onclick', 'href=', 'function(', 'document.', 'style=',
        'class=', 'var ', '//', '/*', 'text-', 'font-',
    ])


def search_plc_modem(data, strings):
    """Search for PLC (Power Line Communication) modem references."""
    print("\n  Searching for PLC modem references...")

    plc_keywords = [
        'HomePlug', 'homeplug', 'X10', 'INSTEON', 'Z-Wave',
        'powerline', 'power line', 'Power Line Communication',
        'PLC modem', 'PLC DIAG',
    ]

    found = False
    for kw in plc_keywords:
        matches = [(o + RAM_BASE, s) for o, s in strings if kw in s]
        if matches:
            found = True
            print(f"\n    '{kw}' ({len(matches)} matches):")
            for addr, s in matches[:5]:
                print(f"      0x{addr:08X}: {s[:150]}")

    if not found:
        print("    No PLC protocol references found (HomePlug, X10, INSTEON, Z-Wave).")
        print("    Despite J10 'PLC DIAG' header on PCB, firmware has no PLC support.")
        print("    J10 may be for optional PLC module or 'PLC' may mean 'Programmable Logic Controller'.")


def search_daisy_chain_protocol(data, strings):
    """Search for daisy-chain inter-PDU communication protocol."""
    print("\n  Searching for daisy-chain / inter-PDU protocol...")

    keywords = {
        'Core DC Proto': 'DC Protocol task/queue names',
        'DC Proto': 'DC Protocol references',
        'connectionType': 'Connection type variable',
        'connection type': 'Connection type string',
        'cascad': 'Cascading references',
        'Cascad': 'Cascading references',
        'daisy': 'Daisy-chain references',
        'Daisy': 'Daisy-chain references',
        'standalone': 'Standalone mode',
        'Stand Alone': 'Stand Alone mode',
    }

    for kw, desc in keywords.items():
        matches = []
        seen = set()
        for offset, s in strings:
            if kw in s and s not in seen and not is_web_noise(s):
                matches.append((offset + RAM_BASE, s))
                seen.add(s)

        if matches:
            print(f"\n    [{desc}] '{kw}' ({len(matches)} strings):")
            for addr, s in matches[:10]:
                print(f"      0x{addr:08X}: {s[:150]}")


def search_redundancy(data, strings):
    """Search for redundancy management protocol."""
    print("\n  Searching for redundancy management...")

    keywords = [
        'Redundant Communication',
        'redundan', 'Redundan',
        'paired', 'Paired', 'PAIRED',
        'PAIRED_PDU',
    ]

    for kw in keywords:
        matches = []
        seen = set()
        for offset, s in strings:
            if kw in s and s not in seen and not is_web_noise(s):
                matches.append((offset + RAM_BASE, s))
                seen.add(s)

        if matches and len(matches) <= 20:
            print(f"\n    '{kw}' ({len(matches)} strings):")
            for addr, s in matches:
                print(f"      0x{addr:08X}: {s[:150]}")
        elif matches:
            # Filter to firmware area for noisy keywords
            fw = [(a, s) for a, s in matches if a >= 0x0069_0000]
            if fw:
                print(f"\n    '{kw}' ({len(matches)} total, {len(fw)} firmware):")
                for addr, s in fw[:10]:
                    print(f"      0x{addr:08X}: {s[:150]}")


def search_detect_pins(data, strings):
    """Search for upstream/downstream detect pin usage."""
    print("\n  Searching for detect pin usage...")

    keywords = [
        'Upstream', 'upstream',
        'Downstream', 'downstream',
        'detectpin', 'Detect Pin',
        'Discovery Capable',
        'Non Monitored',
        'Monitored stick',
    ]

    for kw in keywords:
        matches = []
        seen = set()
        for offset, s in strings:
            if kw in s and s not in seen and not is_web_noise(s):
                matches.append((offset + RAM_BASE, s))
                seen.add(s)

        if matches:
            print(f"\n    '{kw}' ({len(matches)} strings):")
            for addr, s in matches[:10]:
                print(f"      0x{addr:08X}: {s[:150]}")


def search_thread_names(data, strings):
    """Search for RTOS thread/task names that reveal the software architecture."""
    print("\n  Searching for RTOS thread/task names...")

    # Thread names are typically short (< 30 chars) and found near 0x69EE..
    # Look for known thread names and their neighbours
    task_keywords = [
        'Task', 'Async', 'Proto', 'Timer', 'Thread',
        'Module', 'Handler', 'Manager',
    ]

    # Scan the known task name region
    start = 0x69ED00 - RAM_BASE
    end = start + 0x300

    pos = start
    task_strings = []
    while pos < end and pos < len(data):
        if data[pos] >= 0x20 and data[pos] < 0x7F:
            s_start = pos
            while pos < len(data) and data[pos] >= 0x20 and data[pos] < 0x7F:
                pos += 1
            s = data[s_start:pos].decode('ascii', errors='replace')
            if len(s) >= 3:
                task_strings.append((s_start + RAM_BASE, s))
        else:
            pos += 1

    if task_strings:
        print(f"\n    Task/module name region (0x{start + RAM_BASE:08X}):")
        for addr, s in task_strings:
            print(f"      0x{addr:08X}: {s}")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    decomp_file = "2.0.51.12_Z7550-02475_decompressed.bin"
    decomp_path = os.path.join(EXTRACT_DIR, decomp_file)

    if not os.path.exists(decomp_path):
        print(f"ERROR: {decomp_path} not found")
        return

    with open(decomp_path, 'rb') as f:
        data = f.read()

    print(f"  Loaded {decomp_file}: {len(data):,} bytes")
    strings = extract_all_strings(data)
    print(f"  Extracted {len(strings):,} strings")

    print(f"\n{'='*70}")
    print(f"  Inter-PDU Communication & Daisy-Chain Protocol Analysis")
    print(f"{'='*70}")

    search_plc_modem(data, strings)
    search_daisy_chain_protocol(data, strings)
    search_redundancy(data, strings)
    search_detect_pins(data, strings)
    search_thread_names(data, strings)

    print(f"\n{'='*70}")
    print(f"  Summary")
    print(f"{'='*70}")
    print("  - No PLC modem protocol found in firmware")
    print("  - Daisy-chain uses 'Core DC Proto' task with physical detect pins")
    print("  - Redundancy management between paired primary/secondary PDUs")
    print("  - Extension bars ('sticks') detected as Monitored or Non-Monitored")


if __name__ == '__main__':
    main()

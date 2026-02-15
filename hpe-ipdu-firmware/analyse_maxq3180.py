#!/usr/bin/env python3
"""Analyse MAXQ3180 SPI communication protocol in HPE iPDU firmware.

The MAXQ3180 is a 3-phase power/energy measurement AFE connected to the
NS9360 via SPI. This script searches the firmware for:
1. MAXQ3180 register addresses and SPI commands
2. Power measurement data structures
3. Calibration routines
4. SPI port configuration
5. Metering protocol details
"""

import os
import struct
import re

EXTRACT_DIR = "extracted"
RAM_BASE = 0x00004000


def find_strings_at(data, offset, count=50):
    """Extract null-terminated strings starting from offset."""
    strings = []
    pos = offset
    current = b''
    start = pos
    while pos < len(data) and len(strings) < count:
        b = data[pos]
        if 0x20 <= b < 0x7F:
            if not current:
                start = pos
            current += bytes([b])
        elif b == 0:
            if current and len(current) >= 3:
                strings.append((start + RAM_BASE, current.decode('ascii')))
            current = b''
        else:
            if current and len(current) >= 3:
                strings.append((start + RAM_BASE, current.decode('ascii')))
            current = b''
        pos += 1
    return strings


def search_maxq_strings(data):
    """Search for MAXQ3180-related strings."""
    print("\n  Searching for MAXQ3180-related strings...")

    all_results = []
    patterns = [
        rb'[Mm][Aa][Xx][Qq]',
        rb'[Mm]axim',
        rb'MAXIM',
        rb'[Mm]eter',
        rb'[Cc]alibrat',
        rb'[Ww]att',
        rb'[Vv]oltage',
        rb'[Cc]urrent',
        rb'[Pp]ower [Ff]actor',
        rb'[Ff]requency',
        rb'[Pp]hase',
        rb'[Kk][Ww][Hh]',
        rb'[Vv][Aa][Hh]',
        rb'SPI',
        rb'spi',
    ]

    # Find all printable strings
    strings = []
    current = b''
    start = 0
    for i, byte in enumerate(data):
        if 0x20 <= byte < 0x7F:
            if not current:
                start = i
            current += bytes([byte])
        elif byte == 0:
            if current and len(current) >= 6:
                strings.append((start, current.decode('ascii')))
            current = b''
        else:
            if current and len(current) >= 6:
                strings.append((start, current.decode('ascii')))
            current = b''

    for offset, s in strings:
        for pattern in patterns:
            if re.search(pattern, s.encode()):
                all_results.append((offset, s, pattern.decode()))
                break

    # Group by category
    categories = {
        'MAXQ/Maxim': [],
        'Calibration': [],
        'Power/Energy': [],
        'SPI': [],
        'Metering': [],
    }

    for offset, s, pattern in all_results:
        addr = offset + RAM_BASE
        pat_lower = pattern.lower().replace('[', '').replace(']', '')
        if 'maxq' in pat_lower or 'maxim' in pat_lower:
            categories['MAXQ/Maxim'].append((addr, s))
        elif 'calibrat' in pat_lower:
            categories['Calibration'].append((addr, s))
        elif 'spi' in pat_lower:
            categories['SPI'].append((addr, s))
        elif 'meter' in pat_lower:
            categories['Metering'].append((addr, s))
        else:
            categories['Power/Energy'].append((addr, s))

    for cat, items in categories.items():
        if not items:
            continue
        print(f"\n    [{cat}] ({len(items)} matches):")
        seen = set()
        count = 0
        for addr, s in items:
            if s not in seen:
                print(f"      0x{addr:08X}: {s[:120]}")
                seen.add(s)
                count += 1
                if count >= 40:
                    remaining = len(items) - count
                    if remaining > 0:
                        print(f"      ... and {remaining} more")
                    break


def search_maxq3180_registers(data):
    """Search for MAXQ3180 register addresses in the firmware.

    MAXQ3180 SPI register addresses are 8-bit (0x00-0xFF).
    Key registers from the MAXQ3180 datasheet:
    - 0x00: Status register
    - 0x01: Config register
    - 0x02-0x03: Voltage/current RMS registers
    - 0x04-0x05: Power registers
    - 0x10-0x1F: Calibration registers
    - 0x20-0x2F: Measurement result registers

    The SPI protocol uses:
    - Write: 0x80 | register_addr (MSB set = write)
    - Read: register_addr (MSB clear = read)
    """
    print("\n  Searching for MAXQ3180 SPI protocol patterns...")

    # Look for strings that mention specific MAXQ3180 register names
    register_names = [
        'GAIN', 'OFFSET', 'IRMS', 'VRMS', 'WATTS', 'VA', 'VAR',
        'PF', 'FREQ', 'WATT_HOUR', 'VA_HOUR', 'VAR_HOUR',
        'ICAL', 'VCAL', 'PCAL', 'THRESHOLD',
        'TEMPERATURE', 'IPEAK', 'VPEAK',
    ]

    found = []
    for name in register_names:
        pos = 0
        while True:
            pos = data.find(name.encode(), pos)
            if pos < 0:
                break
            # Check if it's part of a printable string
            context = data[max(0, pos-20):pos+len(name)+20]
            printable = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in context)
            found.append((pos + RAM_BASE, name, printable))
            pos += 1

    if found:
        print(f"    Found {len(found)} register name references:")
        seen = set()
        for addr, name, context in found:
            key = f"{name}:{context}"
            if key not in seen:
                print(f"      0x{addr:08X}: [{name}] {context}")
                seen.add(key)
    else:
        print("    No MAXQ3180 register name references found.")


def search_spi_port_config(data):
    """Search for SPI port configuration in the firmware.

    NS9360 serial ports can be configured as SPI:
    - Port A: 0x90200040 (gpio[8-11])
    - Port B: 0x90200000 (gpio[0-7])
    - Port C: 0x90300000 (gpio[40-41], gpio[20-23])
    - Port D: 0x90300040 (gpio[44-47])

    SPI mode is selected by configuring the serial port control registers.
    The serial port has a mode field that selects UART vs SPI operation.
    """
    print("\n  Searching for SPI-configured serial port registers...")

    # NS9360 serial port register offsets (from BBus, port relative)
    SPI_REGS = {
        'Ctrl A': 0x00,
        'Ctrl B': 0x04,
        'Status A': 0x08,
        'Bit Rate': 0x0C,
        'RX Buf Gap Timer': 0x10,
        'RX Char Timer': 0x14,
        'RX Match': 0x18,
        'RX Match Mask': 0x1C,
        'FIFO': 0x20,
        'Flow Control': 0x24,
        'Flow Force': 0x28,
    }

    PORTS = {
        'Port B': 0x90200000,
        'Port A': 0x90200040,
        'Port C': 0x90300000,
        'Port D': 0x90300040,
    }

    # Search for SPI-specific bit patterns in Control A register writes
    # For SPI mode, Control A[1:0] (WLS bits) and mode bits differ
    # SPI mode control: CE1 enable bit, clock polarity, clock phase
    for port_name, port_base in PORTS.items():
        refs = 0
        for reg_name, reg_off in SPI_REGS.items():
            reg_addr = port_base + reg_off
            pattern = struct.pack('>I', reg_addr)
            pos = 0
            while True:
                pos = data.find(pattern, pos)
                if pos < 0:
                    break
                refs += 1
                pos += 1
        if refs > 0:
            print(f"    {port_name} (0x{port_base:08X}): {refs} register references")


def search_metering_data_structures(data):
    """Search for power metering data structures and measurement tables."""
    print("\n  Searching for metering data structures...")

    # Look for formatted output strings that reveal data structure fields
    patterns = [
        rb'%[0-9]*\.?[0-9]*[fd].*[Vv]',     # Voltage formatting
        rb'%[0-9]*\.?[0-9]*[fd].*[Aa]',      # Current formatting
        rb'%[0-9]*\.?[0-9]*[fd].*[Ww]',      # Power formatting
        rb'%[0-9]*\.?[0-9]*[fd].*[Hh][Zz]',  # Frequency formatting
    ]

    # Find metering-related string clusters
    # The debug commands gmstats, gmstats2, mpstats, spstats suggest
    # there are formatted output routines
    metering_keywords = [
        b'gmstats', b'mpstats', b'spstats',
        b'Metering', b'metering',
        b'Measurement', b'measurement',
        b'Energy', b'energy',
        b'Power Factor', b'power factor',
    ]

    for keyword in metering_keywords:
        pos = data.find(keyword)
        if pos >= 0:
            addr = pos + RAM_BASE
            # Extract surrounding context
            strings = find_strings_at(data, pos, count=20)
            if strings:
                print(f"\n    Context around '{keyword.decode()}' (0x{addr:08X}):")
                for saddr, s in strings:
                    print(f"      0x{saddr:08X}: {s[:120]}")


def search_calibration_routines(data):
    """Search for MAXQ3180 calibration data and routines."""
    print("\n  Searching for calibration routines...")

    # The debug CLI has 'gmcal' (calibrate maxim voltage) and 'gmsave' commands
    # Look for calibration-related strings and data structures

    cal_keywords = [
        b'calibrat',
        b'Calibrat',
        b'CALIBRAT',
        b'gain',
        b'Gain',
        b'GAIN',
        b'offset',
        b'Offset',
        b'gmcal',
        b'gmsave',
    ]

    for keyword in cal_keywords:
        positions = []
        pos = 0
        while True:
            pos = data.find(keyword, pos)
            if pos < 0:
                break
            # Check this is part of a printable string (not random byte match)
            if pos > 0 and 0x20 <= data[pos-1] < 0x7F:
                pass  # Part of a longer string
            positions.append(pos)
            pos += 1

        if positions:
            unique_strings = set()
            for p in positions:
                # Extract the containing string
                start = p
                while start > 0 and 0x20 <= data[start-1] < 0x7F:
                    start -= 1
                end = p + len(keyword)
                while end < len(data) and 0x20 <= data[end] < 0x7F:
                    end += 1
                s = data[start:end].decode('ascii', errors='replace')
                if len(s) >= 6 and s not in unique_strings:
                    unique_strings.add(s)

            if unique_strings:
                print(f"\n    '{keyword.decode()}' ({len(unique_strings)} unique strings):")
                for s in sorted(unique_strings)[:20]:
                    print(f"      {s[:120]}")


def search_stick_protocol(data):
    """Search for extension bar ('stick') communication protocol.

    The iPDU can connect to extension bars. The debug CLI has 'spstats'
    (stick protocol statistics) suggesting a dedicated protocol.
    """
    print("\n  Searching for extension bar ('stick') protocol...")

    stick_keywords = [b'stick', b'Stick', b'STICK', b'extension', b'Extension',
                      b'ext bar', b'Ext Bar', b'outlet', b'Outlet']

    for keyword in stick_keywords:
        positions = []
        pos = 0
        while True:
            pos = data.find(keyword, pos)
            if pos < 0:
                break
            positions.append(pos)
            pos += 1

        if keyword in [b'stick', b'Stick', b'STICK']:
            unique = set()
            for p in positions:
                start = p
                while start > 0 and 0x20 <= data[start-1] < 0x7F:
                    start -= 1
                end = p + len(keyword)
                while end < len(data) and 0x20 <= data[end] < 0x7F:
                    end += 1
                s = data[start:end].decode('ascii', errors='replace')
                if len(s) >= 6:
                    unique.add(s)

            if unique:
                print(f"\n    '{keyword.decode()}' strings ({len(unique)}):")
                for s in sorted(unique)[:30]:
                    print(f"      {s[:120]}")


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

    print(f"\n{'='*70}")
    print(f"  MAXQ3180 SPI Communication Analysis")
    print(f"{'='*70}")

    search_maxq_strings(data)
    search_maxq3180_registers(data)
    search_spi_port_config(data)
    search_metering_data_structures(data)
    search_calibration_routines(data)
    search_stick_protocol(data)

    print(f"\n{'='*70}")
    print(f"  Summary")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()

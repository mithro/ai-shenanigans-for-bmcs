#!/usr/bin/env python3
"""Analyse TMP89FM42LUG display MCU communication protocol in HPE iPDU firmware.

The TMP89FM42LUG is a Toshiba 8-bit TLCS-870/C microcontroller used as a sub-MCU
for the front-panel display and LED management. It communicates with the NS9360
main CPU via a serial interface (likely UART).

This script searches the firmware for:
1. Display-related strings and commands
2. 7-segment display patterns
3. LED control patterns
4. Display serial protocol structures
5. Button/keypad input handling
6. Front panel communication protocol
"""

import os
import struct
import re

EXTRACT_DIR = "extracted"
RAM_BASE = 0x00004000


def find_strings_at(data, offset, count=30):
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


def extract_all_strings(data, min_len=6):
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


def search_display_strings(data):
    """Search for display-related strings in firmware."""
    print("\n  Searching for display-related strings...")

    # Categories of display-related patterns
    categories = {
        'Display/LCD': [
            rb'[Dd]isplay',
            rb'[Ll][Cc][Dd]',
            rb'[Ss]creen',
        ],
        '7-Segment': [
            rb'7.?seg',
            rb'seven.?seg',
            rb'segment',
        ],
        'LED': [
            rb'\bLED\b',
            rb'\bled\b',
            rb'[Ll]ight',
        ],
        'Button/Keypad': [
            rb'[Bb]utton',
            rb'[Kk]eypad',
            rb'[Kk]ey.?press',
            rb'[Pp]ush',
        ],
        'Front Panel': [
            rb'[Ff]ront.?[Pp]anel',
            rb'[Pp]anel',
            rb'[Bb]ezel',
        ],
        'TMP89/Toshiba': [
            rb'TMP89',
            rb'[Tt]oshiba',
            rb'TLCS',
        ],
    }

    all_strings = extract_all_strings(data)

    for cat_name, patterns in categories.items():
        matches = []
        seen = set()
        for offset, s in all_strings:
            for pattern in patterns:
                if re.search(pattern, s.encode()):
                    if s not in seen:
                        matches.append((offset + RAM_BASE, s))
                        seen.add(s)
                    break

        # Filter out pure HTML/JS/CSS matches for noisy categories
        if cat_name in ('LED', 'Button/Keypad', 'Front Panel'):
            filtered = []
            for addr, s in matches:
                # Skip obvious HTML/JS
                if any(tag in s.lower() for tag in ['<td', '<tr', '<div', '<span',
                        '<input', '<img', '<script', 'onclick', 'function(',
                        'document.', 'style=', 'class=', 'href=']):
                    continue
                filtered.append((addr, s))
            matches = filtered

        if matches:
            print(f"\n    [{cat_name}] ({len(matches)} unique strings):")
            for addr, s in matches[:40]:
                print(f"      0x{addr:08X}: {s[:120]}")
            if len(matches) > 40:
                print(f"      ... and {len(matches) - 40} more")


def search_display_commands(data):
    """Search for display-related debug CLI commands and protocol."""
    print("\n  Searching for display-related debug CLI commands...")

    # From previous analysis, the debug CLI command table is around 0x0069CD..
    # "7seg" command was found: "Detects 7 segment display"
    cli_keywords = [
        b'7seg',
        b'display',
        b'Display',
        b'led',
        b'bezel',
        b'panel',
        b'brightness',
        b'backlight',
        b'contrast',
        b'refresh',
    ]

    for keyword in cli_keywords:
        positions = []
        pos = 0
        while True:
            pos = data.find(keyword, pos)
            if pos < 0:
                break
            # Check if surrounded by null or non-printable (indicates a standalone string)
            before_ok = pos == 0 or data[pos - 1] < 0x20
            positions.append((pos, before_ok))
            pos += 1

        # Look for standalone CLI command strings (preceded by null byte)
        standalone = [(p, before_ok) for p, before_ok in positions if before_ok]
        if standalone:
            print(f"\n    '{keyword.decode()}' standalone strings ({len(standalone)}):")
            for p, _ in standalone[:10]:
                # Get the string
                end = p
                while end < len(data) and 0x20 <= data[end] < 0x7F:
                    end += 1
                s = data[p:end].decode('ascii', errors='replace')
                # Get next string (likely the description in CLI tables)
                next_start = end
                while next_start < len(data) and data[next_start] < 0x20:
                    next_start += 1
                next_end = next_start
                while next_end < len(data) and 0x20 <= data[next_end] < 0x7F:
                    next_end += 1
                desc = data[next_start:next_end].decode('ascii', errors='replace')

                addr = p + RAM_BASE
                print(f"      0x{addr:08X}: '{s}' -> '{desc}'")


def search_display_serial_protocol(data):
    """Search for display serial communication protocol details.

    The display unit (TMP89FM42LUG) communicates via serial. Look for:
    - Protocol framing bytes (STX, ETX, SOH, etc.)
    - Display command bytes
    - Display data format strings
    - Error handling strings related to display communication
    """
    print("\n  Searching for display serial protocol...")

    # Search for "Display" in context of communication/serial
    comm_patterns = [
        rb'[Dd]isplay.*[Cc]ommuni',
        rb'[Dd]isplay.*[Ss]erial',
        rb'[Dd]isplay.*[Pp]ort',
        rb'[Dd]isplay.*[Tt]imeout',
        rb'[Dd]isplay.*[Ee]rror',
        rb'[Dd]isplay.*[Ff]ail',
        rb'[Dd]isplay.*[Ss]end',
        rb'[Dd]isplay.*[Rr]ecv',
        rb'[Dd]isplay.*[Rr]ead',
        rb'[Dd]isplay.*[Ww]rite',
        rb'[Dd]isplay.*[Pp]rotocol',
        rb'[Dd]isplay.*[Bb]aud',
        rb'[Dd]isplay.*[Mm]essage',
        rb'[Dd]isplay.*[Cc]ommand',
        rb'[Dd]isplay.*[Rr]esponse',
        rb'[Dd]isplay.*[Ii]nit',
        rb'[Dd]isplay.*[Rr]eset',
        rb'[Dd]isplay.*[Ff]irmware',
        rb'[Dd]isplay.*[Vv]ersion',
    ]

    all_strings = extract_all_strings(data, min_len=8)
    found = set()

    for pattern in comm_patterns:
        for offset, s in all_strings:
            if re.search(pattern, s.encode()) and s not in found:
                addr = offset + RAM_BASE
                print(f"    0x{addr:08X}: {s[:150]}")
                found.add(s)

    if not found:
        print("    No display communication protocol strings found.")


def search_display_topology(data):
    """Search for Display Communication alarm/event strings.

    The NVRAM analysis found "Display Communication" as an alarm name,
    suggesting the firmware monitors display MCU health.
    """
    print("\n  Searching for display topology and health monitoring...")

    keywords = [
        b'Display Communication',
        b'display communication',
        b'Topology Discovery',
        b'topology discovery',
        b'Topology Disc',
    ]

    for keyword in keywords:
        pos = data.find(keyword)
        if pos >= 0:
            addr = pos + RAM_BASE
            strings = find_strings_at(data, pos, count=15)
            if strings:
                print(f"\n    Context around '{keyword.decode()}' (0x{addr:08X}):")
                for saddr, s in strings:
                    print(f"      0x{saddr:08X}: {s[:120]}")


def search_display_data_formats(data):
    """Search for format strings related to display output.

    Look for printf-style format strings that format data for display,
    such as voltage/current values shown on the front panel LCD/7-segment.
    """
    print("\n  Searching for display data format strings...")

    # The web UI format strings like "Core%dr%dVA" suggest a core/row/column
    # data model. Look for similar patterns that might be sent to the display.
    format_patterns = [
        rb'%[0-9.]*[dufx].*[AV]',  # numeric + unit
        rb'%[0-9.]*[dufx].*[Ww]',  # numeric + watts
        rb'%[0-9.]*[dufx].*[Hh][Zz]',  # numeric + hertz
    ]

    # Look for "Dialog.c" references - firmware source file for display
    dialog_keywords = [b'Dialog.c', b'dialog.c', b'DIALOG']
    for keyword in dialog_keywords:
        positions = []
        pos = 0
        while True:
            pos = data.find(keyword, pos)
            if pos < 0:
                break
            positions.append(pos)
            pos += 1

        if positions:
            print(f"\n    '{keyword.decode()}' references ({len(positions)}):")
            seen = set()
            for p in positions:
                # Extract surrounding string
                start = p
                while start > 0 and 0x20 <= data[start - 1] < 0x7F:
                    start -= 1
                end = p + len(keyword)
                while end < len(data) and 0x20 <= data[end] < 0x7F:
                    end += 1
                s = data[start:end].decode('ascii', errors='replace')
                if s not in seen:
                    addr = start + RAM_BASE
                    print(f"      0x{addr:08X}: {s[:150]}")
                    seen.add(s)


def search_uid_led(data):
    """Search for UID (Unit ID) LED control patterns.

    UID LEDs are blue indicators on each PDU/stick for physical identification.
    The firmware must send commands to the display MCU to control these.
    """
    print("\n  Searching for UID LED control patterns...")

    uid_keywords = [
        b'UID',
        b'uid',
        b'UnitID',
        b'unit_id',
        b'BlueLED',
        b'blue_led',
        b'identify',
        b'Identify',
    ]

    all_strings = extract_all_strings(data, min_len=6)

    for keyword in uid_keywords:
        matches = []
        seen = set()
        for offset, s in all_strings:
            if keyword.decode() in s and s not in seen:
                # Skip HTML/JS noise
                if any(tag in s.lower() for tag in ['<td', '<tr', '<div', '<img',
                        '<script', 'onclick', 'src=', 'style=', 'class=',
                        'name=', 'href=']):
                    continue
                matches.append((offset + RAM_BASE, s))
                seen.add(s)

        if matches:
            print(f"\n    '{keyword.decode()}' ({len(matches)} strings):")
            for addr, s in matches[:15]:
                print(f"      0x{addr:08X}: {s[:120]}")
            if len(matches) > 15:
                print(f"      ... and {len(matches) - 15} more")


def search_buzzer_beep(data):
    """Search for buzzer/beep patterns (front panel may have an audible alert)."""
    print("\n  Searching for buzzer/beep/audio alert patterns...")

    keywords = [b'buzzer', b'Buzzer', b'BUZZER', b'beep', b'Beep', b'BEEP',
                b'alarm', b'Alarm', b'alert', b'Alert', b'sound', b'Sound',
                b'tone', b'Tone', b'speaker', b'Speaker']

    all_strings = extract_all_strings(data, min_len=6)

    for keyword in keywords:
        matches = []
        seen = set()
        for offset, s in all_strings:
            # Only match as a word boundary (not substring of HTML attributes)
            kw = keyword.decode()
            if kw.lower() in s.lower():
                # Skip HTML/JS noise
                if any(tag in s.lower() for tag in ['<td', '<tr', '<div', '<input',
                        '<img', '<script', 'onclick', 'href=', 'function(',
                        'document.', 'style=', 'class=']):
                    continue
                if s not in seen:
                    matches.append((offset + RAM_BASE, s))
                    seen.add(s)

        if matches and keyword in [b'buzzer', b'Buzzer', b'BUZZER', b'beep', b'Beep',
                                    b'BEEP', b'speaker', b'Speaker']:
            print(f"\n    '{keyword.decode()}' ({len(matches)} strings):")
            for addr, s in matches[:10]:
                print(f"      0x{addr:08X}: {s[:120]}")
        elif matches and keyword in [b'alarm', b'Alarm', b'alert', b'Alert']:
            # Just count for noisy categories
            firmware_matches = [m for m in matches
                                if m[0] >= 0x0069_0000]  # skip web UI area
            if firmware_matches:
                print(f"\n    '{keyword.decode()}' firmware strings ({len(firmware_matches)}):")
                for addr, s in firmware_matches[:10]:
                    print(f"      0x{addr:08X}: {s[:120]}")


def search_additional_debug_commands(data):
    """Search for additional debug CLI commands not yet documented.

    The CLI command table appears to be at ~0x69CD.. with format:
    [command_name\0] [description\0] repeated.
    """
    print("\n  Searching for complete debug CLI command table...")

    # The known CLI region starts around 0x69CD84 - 0x4000 (RAM_BASE) = 0x65CD84
    # Let's search for the pattern of short strings followed by descriptions
    # Starting from a known command and scanning backwards/forwards

    known_offset = 0x0069CD84 - RAM_BASE  # "calibrate maxim voltage"

    # Scan backwards to find the start of the CLI table
    table_start = known_offset
    while table_start > 0:
        # Look for a pattern: null byte, then short string, then null, then description
        if data[table_start - 1] == 0:
            # Check if the preceding region is also a command entry
            look_back = table_start - 2
            while look_back > 0 and data[look_back] != 0:
                look_back -= 1
            candidate = data[look_back + 1:table_start - 1]
            if len(candidate) >= 3 and all(0x20 <= b < 0x7F for b in candidate):
                table_start = look_back + 1
            else:
                break
        else:
            break

    # Now scan forward from the start, extracting command/description pairs
    print(f"\n    CLI command table region: 0x{table_start + RAM_BASE:08X} onwards")

    pos = table_start
    commands = []
    while pos < len(data) and len(commands) < 50:
        # Extract next string
        if data[pos] < 0x20:
            pos += 1
            continue

        start = pos
        while pos < len(data) and 0x20 <= data[pos] < 0x7F:
            pos += 1
        name = data[start:pos].decode('ascii', errors='replace')

        # Skip to next string (the description)
        while pos < len(data) and data[pos] < 0x20:
            pos += 1

        desc_start = pos
        while pos < len(data) and 0x20 <= data[pos] < 0x7F:
            pos += 1
        desc = data[desc_start:pos].decode('ascii', errors='replace')

        # Heuristic: CLI commands are short (< 20 chars), descriptions are longer
        if len(name) < 25 and len(desc) >= 5:
            addr = start + RAM_BASE
            commands.append((addr, name, desc))
        elif len(name) >= 25:
            # Probably hit the end of the table
            break

    if commands:
        print(f"    Found {len(commands)} CLI command entries:")
        for addr, name, desc in commands:
            print(f"      0x{addr:08X}: {name:20s} -> {desc[:80]}")


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
    print(f"  TMP89FM42LUG Display MCU Communication Analysis")
    print(f"{'='*70}")

    search_display_strings(data)
    search_display_commands(data)
    search_display_serial_protocol(data)
    search_display_topology(data)
    search_display_data_formats(data)
    search_uid_led(data)
    search_buzzer_beep(data)
    search_additional_debug_commands(data)

    print(f"\n{'='*70}")
    print(f"  Summary")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()

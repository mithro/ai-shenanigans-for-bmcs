#!/usr/bin/env python3
"""Trace the BSP initialisation code from the reset handler.

The reset vector at 0x4000 jumps to 0xB7F64. This script traces the
init code to find where GPIO configuration values are set.

Also searches for the NET+OS BSP GPIO config data table by looking
for NABspGpioConfig structures near board identification strings.
"""

import os
import re
import struct
import subprocess
import sys
from collections import defaultdict

EXTRACT_DIR = "extracted"
BASE_ADDR = 0x00004000


def disasm_region(bin_path, file_offset, size, base_addr=BASE_ADDR):
    """Disassemble a specific region as big-endian ARM."""
    with open(bin_path, 'rb') as f:
        f.seek(file_offset)
        region = f.read(size)

    tmp = os.path.join(EXTRACT_DIR, "tmp_region.bin")
    with open(tmp, 'wb') as f:
        f.write(region)

    vma = base_addr + file_offset
    cmd = [
        "arm-linux-gnueabi-objdump", "-D",
        "-b", "binary", "-m", "arm", "-EB",
        "--adjust-vma", hex(vma),
        tmp,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    os.remove(tmp)
    return result.stdout if result.returncode == 0 else ""


def extract_bl_targets(disasm_text):
    """Extract all BL (branch-and-link) call targets from disassembly."""
    targets = []
    for line in disasm_text.split('\n'):
        m = re.match(r'\s*([0-9a-f]+):\s+[0-9a-f]+\s+bl\s+0x([0-9a-f]+)', line)
        if m:
            addr = int(m.group(1), 16)
            target = int(m.group(2), 16)
            targets.append((addr, target))
    return targets


def extract_ldr_pool_refs(disasm_text):
    """Extract all LDR Rn, [PC, #offset] references to literal pool."""
    refs = []
    for line in disasm_text.split('\n'):
        m = re.match(r'\s*([0-9a-f]+):\s+[0-9a-f]+\s+ldr\s+(\w+),\s*\[pc(?:,\s*#(\d+))?\]\s*(?:;\s*0x([0-9a-f]+))?', line, re.IGNORECASE)
        if not m:
            # Try alternate format: "@ 0xaddr"
            m = re.match(r'\s*([0-9a-f]+):\s+[0-9a-f]+\s+ldr\s+(\w+),\s*\[pc,\s*#(\d+)\]\s+@\s+0x([0-9a-f]+)', line, re.IGNORECASE)
        if m:
            addr = int(m.group(1), 16)
            reg = m.group(2)
            pool_addr = int(m.group(4), 16) if m.group(4) else None
            refs.append((addr, reg, pool_addr))
    return refs


def search_bsp_gpio_table(data, base_addr):
    """Search for the BSP GPIO config data table.

    In NET+OS, NABspGpioConfig is typically:
    struct {
        uint32_t pin_number;   // 0-72
        uint32_t direction;    // 0=input, 1=output
        uint32_t function;     // 0-3 (mux)
    };

    Or possibly a simpler format:
    struct {
        uint32_t pin_number;   // 0-72
        uint32_t config;       // 4-bit config nibble (dir/inv/func)
    };

    Search for sequences of (small_number, 0_or_1, 0_to_3) triples.
    """
    print(f"\n  Searching for BSP GPIO config table (pin, dir, func triples)...")

    best_matches = []

    for offset in range(0, len(data) - 12 * 10, 4):
        # Try to interpret as 12-byte entries (pin, dir, func)
        valid_entries = 0
        seen_pins = set()
        for i in range(min(73, (len(data) - offset) // 12)):
            pin = struct.unpack_from('>I', data, offset + i * 12)[0]
            direction = struct.unpack_from('>I', data, offset + i * 12 + 4)[0]
            func = struct.unpack_from('>I', data, offset + i * 12 + 8)[0]

            if pin <= 72 and direction <= 1 and func <= 3 and pin not in seen_pins:
                valid_entries += 1
                seen_pins.add(pin)
            else:
                break

        if valid_entries >= 10:
            best_matches.append((offset, valid_entries, 12))

        # Try 8-byte entries (pin, config_nibble)
        valid_entries = 0
        seen_pins = set()
        for i in range(min(73, (len(data) - offset) // 8)):
            pin = struct.unpack_from('>I', data, offset + i * 8)[0]
            config = struct.unpack_from('>I', data, offset + i * 8 + 4)[0]

            if pin <= 72 and config <= 0xF and pin not in seen_pins:
                valid_entries += 1
                seen_pins.add(pin)
            else:
                break

        if valid_entries >= 10:
            best_matches.append((offset, valid_entries, 8))

    # Sort by number of valid entries
    best_matches.sort(key=lambda x: x[1], reverse=True)

    for offset, count, stride in best_matches[:5]:
        addr = base_addr + offset
        print(f"\n  Candidate at 0x{addr:08X} (file offset 0x{offset:X}), "
              f"{count} entries, {stride}-byte stride:")
        for i in range(min(count, 20)):
            if stride == 12:
                pin = struct.unpack_from('>I', data, offset + i * 12)[0]
                direction = struct.unpack_from('>I', data, offset + i * 12 + 4)[0]
                func = struct.unpack_from('>I', data, offset + i * 12 + 8)[0]
                print(f"    gpio[{pin:2d}]: dir={direction} func={func}")
            else:
                pin = struct.unpack_from('>I', data, offset + i * 8)[0]
                config = struct.unpack_from('>I', data, offset + i * 8 + 4)[0]
                print(f"    gpio[{pin:2d}]: config=0x{config:X}")


def search_gpio_config_values(data, base_addr):
    """Search for 10 consecutive 32-bit values that decode as valid GPIO configs.

    Each GPIO config register is 32 bits with 8 nibbles (one per pin).
    Valid nibbles are 0x0-0xF but most should be 0x0 (mux0) or 0x3/0xB (GPIO).
    We look for groups of 10 such values stored contiguously.
    """
    print(f"\n  Searching for 10 consecutive GPIO config register values...")

    candidates = []

    for offset in range(0, len(data) - 40, 4):
        words = [struct.unpack_from('>I', data, offset + i * 4)[0] for i in range(10)]

        # Skip if any word is in an address range (likely a pointer)
        if any(0x00004000 <= w <= 0x007FFFFF for w in words):
            continue
        if any(0x90000000 <= w <= 0xFFFFFFFF for w in words):
            continue
        if all(w == 0 for w in words):
            continue

        # Count valid nibbles across all 10 registers
        # Valid means 0x0 (mux0), 0x3 (GPIO input), 0xB (GPIO output),
        # or any value 0x0-0xF
        total_nibbles = 80  # 10 registers * 8 nibbles
        mux0_count = 0
        gpio_count = 0

        for word in words:
            for j in range(8):
                nibble = (word >> (j * 4)) & 0xF
                if nibble == 0:
                    mux0_count += 1
                elif nibble in (0x3, 0xB, 0xF, 0x7):
                    gpio_count += 1

        # We expect a real GPIO config to have a mix of mux0 and GPIO pins
        # At least 30 mux0 (ethernet + serial ports = ~30 pins) and some GPIO
        if mux0_count >= 25 and gpio_count >= 5:
            candidates.append((offset, words, mux0_count, gpio_count))

    # Sort by most plausible
    candidates.sort(key=lambda x: x[2] + x[3], reverse=True)

    for offset, words, mux0, gpio in candidates[:10]:
        addr = base_addr + offset
        print(f"\n  Candidate at 0x{addr:08X} (file 0x{offset:X}): "
              f"{mux0} mux0, {gpio} GPIO pins")
        for i, word in enumerate(words):
            nibbles = [(word >> (j * 4)) & 0xF for j in range(8)]
            nibble_str = ' '.join(f'{n:X}' for n in nibbles)
            print(f"    Config #{i+1}: 0x{word:08X} = [{nibble_str}]")


def examine_brookline_area(data, base_addr):
    """Examine the data near the 'Brookline' board name strings."""
    markers = [b'Brookline', b'NS9360 Brookline Board']
    for marker in markers:
        pos = data.find(marker)
        if pos == -1:
            continue

        addr = base_addr + pos
        print(f"\n  String \"{marker.decode()}\" at 0x{addr:08X} (file 0x{pos:X})")

        # Dump 256 bytes before and after as hex + ASCII
        dump_start = max(0, pos - 256)
        dump_end = min(len(data), pos + len(marker) + 256)

        print(f"  Hex dump ({dump_end - dump_start} bytes):")
        for i in range(dump_start, dump_end, 16):
            hex_part = ' '.join(f'{data[j]:02X}' for j in range(i, min(i + 16, dump_end)))
            ascii_part = ''.join(
                chr(data[j]) if 32 <= data[j] < 127 else '.'
                for j in range(i, min(i + 16, dump_end))
            )
            marker_indicator = ""
            if i <= pos < i + 16:
                marker_indicator = " <<<"
            print(f"    {base_addr+i:08X}: {hex_part:<48s} {ascii_part}{marker_indicator}")

        # Also dump as 32-bit big-endian words
        print(f"\n  As 32-bit BE words:")
        aligned_start = dump_start & ~3
        for i in range(aligned_start, dump_end - 3, 4):
            word = struct.unpack_from('>I', data, i)[0]
            annotation = ""
            if 0x90600000 <= word <= 0x906FFFFF:
                annotation = " (BBus GPIO register)"
            elif 0x90200000 <= word <= 0x903FFFFF:
                annotation = " (BBus Serial Port)"
            elif 0x90500000 <= word <= 0x905FFFFF:
                annotation = " (BBus I2C)"
            elif 0xA0600000 <= word <= 0xA06FFFFF:
                annotation = " (Ethernet)"
            elif 0xA0900000 <= word <= 0xA09FFFFF:
                annotation = " (System Control)"
            if annotation or (pos <= i <= pos + len(marker)):
                print(f"    {base_addr+i:08X}: 0x{word:08X}{annotation}")


def trace_reset_handler(data, bin_path, base_addr):
    """Trace execution from the reset handler."""
    # Reset vector points to 0x000B7F64
    reset_target = struct.unpack_from('>I', data, 0x40 - 0)[0]  # Literal pool entry 0
    reset_offset = reset_target - base_addr

    print(f"\n  Reset handler at 0x{reset_target:08X} (file offset 0x{reset_offset:X})")

    # Disassemble 2KB from reset handler
    disasm = disasm_region(bin_path, reset_offset, 2048)
    if not disasm:
        print("  Disassembly failed")
        return

    # Show first 50 instructions
    lines = disasm.split('\n')
    print(f"\n  First 50 instructions of reset handler:")
    count = 0
    for line in lines:
        if ':' in line and '\t' in line:
            print(f"    {line.strip()}")
            count += 1
            if count >= 50:
                break

    # Extract BL (function call) targets
    bl_targets = extract_bl_targets(disasm)
    print(f"\n  Function calls from reset handler ({len(bl_targets)} BL instructions):")
    for addr, target in bl_targets[:20]:
        target_offset = target - base_addr
        # Look for strings near the target to identify the function
        nearby_str = ""
        if 0 <= target_offset < len(data) - 100:
            # Check literal pool near the function start for string references
            region = data[target_offset:target_offset + 512]
            for i in range(0, min(512, len(region) - 3), 4):
                word = struct.unpack_from('>I', region, i)[0]
                str_offset = word - base_addr
                if 0 < str_offset < len(data):
                    # Check if this points to a printable string
                    possible_str = data[str_offset:str_offset + 40]
                    if all(32 <= b < 127 or b == 0 for b in possible_str[:20]):
                        s = possible_str.split(b'\x00')[0].decode('ascii', errors='replace')
                        if len(s) >= 4:
                            nearby_str = f" (near string: \"{s[:50]}\")"
                            break

        print(f"    0x{addr:08X}: BL 0x{target:08X}{nearby_str}")

    # Trace deeper: disassemble each called function briefly
    print(f"\n  Called function previews:")
    for addr, target in bl_targets[:10]:
        target_offset = target - base_addr
        if target_offset < 0 or target_offset >= len(data):
            continue
        sub_disasm = disasm_region(bin_path, target_offset, 256)
        if sub_disasm:
            sub_bl = extract_bl_targets(sub_disasm)
            sub_lines = [l.strip() for l in sub_disasm.split('\n')
                         if ':' in l and '\t' in l][:5]
            print(f"\n    0x{target:08X}:")
            for sl in sub_lines:
                print(f"      {sl}")
            if sub_bl:
                print(f"      ... calls: {', '.join(f'0x{t:08X}' for _, t in sub_bl[:5])}")


def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))

    fw_name = "2.0.51.12_Z7550-02475"
    bin_path = os.path.join(EXTRACT_DIR, f"{fw_name}_decompressed.bin")

    with open(bin_path, 'rb') as f:
        data = f.read()

    print(f"Firmware: {bin_path} ({len(data):,} bytes)")

    # 1. Trace reset handler
    print(f"\n{'='*70}")
    print(f"  Reset Handler Trace")
    print(f"{'='*70}")
    trace_reset_handler(data, bin_path, BASE_ADDR)

    # 2. Search for BSP GPIO config data table
    print(f"\n{'='*70}")
    print(f"  BSP GPIO Config Data Table Search")
    print(f"{'='*70}")
    search_bsp_gpio_table(data, BASE_ADDR)

    # 3. Search for 10-register GPIO config values
    print(f"\n{'='*70}")
    print(f"  GPIO Config Register Value Search")
    print(f"{'='*70}")
    search_gpio_config_values(data, BASE_ADDR)

    # 4. Examine area around Brookline strings
    print(f"\n{'='*70}")
    print(f"  Brookline Board Name Area")
    print(f"{'='*70}")
    examine_brookline_area(data, BASE_ADDR)


if __name__ == '__main__':
    main()

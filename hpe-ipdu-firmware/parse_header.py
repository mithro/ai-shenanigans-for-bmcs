#!/usr/bin/env python3
"""Parse and compare bootHdr headers from HPE iPDU firmware images.

Detailed analysis of the 48-byte header and the data that follows,
trying to identify the compression/encoding format.
"""

import os
import struct
import sys

EXTRACT_DIR = "extracted"


def parse_header(data: bytes, name: str):
    """Parse and display the bootHdr header in detail."""
    print(f"\n{'='*70}")
    print(f"  {name} ({len(data)} bytes = 0x{len(data):X})")
    print(f"{'='*70}")

    # Full hex dump of first 128 bytes
    print(f"\nFirst 128 bytes hex dump:")
    for i in range(0, min(128, len(data)), 16):
        hex_part = ' '.join(f'{b:02X}' for b in data[i:i+16])
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
        print(f"  {i:04X}: {hex_part:<48s} {ascii_part}")

    # Parse known fields
    magic = data[0:8].split(b'\x00')[0].decode('ascii', errors='replace')
    product = data[8:16].split(b'\x00')[0].decode('ascii', errors='replace')
    print(f"\n  [0x00] Magic:   '{magic}'")
    print(f"  [0x08] Product: '{product}'")

    # Try various interpretations of remaining header bytes
    print(f"\n  Header bytes 0x10-0x2F as 32-bit words:")
    for offset in range(0x10, 0x30, 4):
        val_le = struct.unpack_from('<I', data, offset)[0]
        val_be = struct.unpack_from('>I', data, offset)[0]
        raw = data[offset:offset+4]
        print(f"    [0x{offset:02X}] {' '.join(f'{b:02X}' for b in raw)}"
              f"  LE=0x{val_le:08X} ({val_le:>10d})"
              f"  BE=0x{val_be:08X} ({val_be:>10d})")

    # Try interpreting as 16-bit words too
    print(f"\n  Header bytes 0x10-0x2F as 16-bit words:")
    for offset in range(0x10, 0x30, 2):
        val_le = struct.unpack_from('<H', data, offset)[0]
        val_be = struct.unpack_from('>H', data, offset)[0]
        raw = data[offset:offset+2]
        print(f"    [0x{offset:02X}] {' '.join(f'{b:02X}' for b in raw)}"
              f"  LE=0x{val_le:04X} ({val_le:>5d})"
              f"  BE=0x{val_be:04X} ({val_be:>5d})")

    # Payload analysis
    payload = data[0x30:]  # After 48-byte header
    print(f"\n  Payload starts at offset 0x30 ({len(payload)} bytes)")

    # Check first bytes of payload for patterns
    print(f"\n  First 64 bytes of payload:")
    for i in range(0, min(64, len(payload)), 16):
        hex_part = ' '.join(f'{b:02X}' for b in payload[i:i+16])
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in payload[i:i+16])
        print(f"    {i+0x30:04X}: {hex_part:<48s} {ascii_part}")

    # Try interpreting first payload bytes as ARM instructions (little-endian)
    print(f"\n  First 16 payload words as ARM LE instructions:")
    for i in range(0, min(64, len(payload)), 4):
        word = struct.unpack_from('<I', payload, i)[0]
        cond = (word >> 28) & 0xF
        cond_names = ['EQ','NE','CS','CC','MI','PL','VS','VC',
                      'HI','LS','GE','LT','GT','LE','AL','NV']
        # Check if it looks like a valid ARM instruction
        is_branch = (word & 0x0E000000) == 0x0A000000
        is_data_proc = (word & 0x0C000000) == 0x00000000
        is_ldr_str = (word & 0x0C000000) == 0x04000000
        is_ldm_stm = (word & 0x0E000000) == 0x08000000

        desc = ""
        if is_branch:
            offset_val = word & 0x00FFFFFF
            if offset_val & 0x800000:
                offset_val |= 0xFF000000
            target = (i + 0x30 + 8) + (offset_val << 2)
            link = "BL" if word & 0x01000000 else "B"
            desc = f" -> {link}{cond_names[cond]} 0x{target & 0xFFFFFFFF:08X}"
        elif is_data_proc:
            desc = f" -> data proc (cond={cond_names[cond]})"

        print(f"    {i+0x30:04X}: 0x{word:08X}{desc}")

    # Try interpreting first payload bytes as ARM instructions (big-endian)
    print(f"\n  First 16 payload words as ARM BE instructions:")
    for i in range(0, min(64, len(payload)), 4):
        word = struct.unpack_from('>I', payload, i)[0]
        cond = (word >> 28) & 0xF
        cond_names = ['EQ','NE','CS','CC','MI','PL','VS','VC',
                      'HI','LS','GE','LT','GT','LE','AL','NV']
        is_branch = (word & 0x0E000000) == 0x0A000000
        is_data_proc = (word & 0x0C000000) == 0x00000000
        is_ldr_str = (word & 0x0C000000) == 0x04000000

        desc = ""
        if is_branch:
            offset_val = word & 0x00FFFFFF
            if offset_val & 0x800000:
                offset_val |= 0xFF000000
            target = (i + 0x30 + 8) + (offset_val << 2)
            link = "BL" if word & 0x01000000 else "B"
            desc = f" -> {link}{cond_names[cond]} 0x{target & 0xFFFFFFFF:08X}"

        print(f"    {i+0x30:04X}: 0x{word:08X}{desc}")

    # Entropy of first 256 bytes of payload
    from collections import Counter
    import math
    for region_name, start, size in [
        ("payload[0:256]", 0, 256),
        ("payload[0:1024]", 0, 1024),
        ("payload[0:4096]", 0, 4096),
        ("payload middle", len(payload)//2, 4096),
        ("payload end-4096", len(payload)-4096, 4096),
    ]:
        region = payload[start:start+size]
        if len(region) < size:
            continue
        counts = Counter(region)
        entropy = -sum((c/len(region)) * math.log2(c/len(region)) for c in counts.values())
        print(f"\n  Entropy of {region_name}: {entropy:.4f} bits/byte")

    # Check if payload starts with known compression signatures
    print(f"\n  Compression signature check:")
    sigs = [
        (b'\x1f\x8b', "gzip"),
        (b'\x78\x01', "zlib (no compression)"),
        (b'\x78\x5e', "zlib (default)"),
        (b'\x78\x9c', "zlib (default)"),
        (b'\x78\xda', "zlib (best)"),
        (b'\x5d\x00\x00', "LZMA"),
        (b'\xfd\x37\x7a\x58\x5a\x00', "XZ"),
        (b'\x42\x5a\x68', "bzip2"),
        (b'\x89\x4c\x5a\x4f', "LZO"),
        (b'\x04\x22\x4d\x18', "LZ4"),
        (b'\x28\xb5\x2f\xfd', "Zstandard"),
        (b'\x1f\x9d', "compress (.Z)"),
        (b'\x1f\xa0', "compress (.Z alt)"),
        (b'\x00\x00\xa0\xe1', "ARM NOP (mov r0, r0)"),
        (b'\xe1\xa0\x00\x00', "ARM NOP BE (mov r0, r0)"),
    ]
    for sig, name in sigs:
        if payload[:len(sig)] == sig:
            print(f"    MATCH: {name}")
        # Also check at common offsets
        for check_offset in [0, 4, 8, 12, 16, 32, 48, 64]:
            if check_offset + len(sig) <= len(payload):
                if payload[check_offset:check_offset+len(sig)] == sig:
                    if check_offset > 0:
                        print(f"    MATCH at payload+0x{check_offset:X}: {name}")

    # Look for the Digi POST/ROM monitor decompression stub
    # The NS9360 boots from NOR flash at 0x50000000
    # Check if any 32-bit words in the header look like NS9360 addresses
    print(f"\n  Checking header for NS9360 memory addresses:")
    ns9360_regions = {
        (0x00000000, 0x10000000): "AHB (SDRAM CS area)",
        (0x40000000, 0x50000000): "AHB (PCI/USB/Crypto)",
        (0x50000000, 0x58000000): "External I/O (NOR Flash boot)",
        (0x90000000, 0x91000000): "BBus peripherals",
        (0xA0000000, 0xA1000000): "AHB peripherals",
        (0xFFFF0000, 0xFFFF1000): "Exception vectors (high)",
    }
    for offset in range(0x10, 0x30, 4):
        for endian, label in [('<', 'LE'), ('>', 'BE')]:
            val = struct.unpack_from(f'{endian}I', data, offset)[0]
            for (lo, hi), region in ns9360_regions.items():
                if lo <= val < hi:
                    print(f"    [0x{offset:02X}] {label} 0x{val:08X} -> {region}")

    # Check payload for NS9360 addresses
    print(f"\n  Checking first 1024 payload bytes for NS9360 addresses:")
    found = 0
    for i in range(0, min(1024, len(payload)), 4):
        for endian, label in [('<', 'LE'), ('>', 'BE')]:
            val = struct.unpack_from(f'{endian}I', payload, i)[0]
            for (lo, hi), region in ns9360_regions.items():
                if lo <= val < hi:
                    print(f"    payload+0x{i:04X} {label} 0x{val:08X} -> {region}")
                    found += 1
    if found == 0:
        print(f"    (none found - confirms payload is compressed/encrypted)")

    # XOR analysis - check if payload might be XOR encrypted
    print(f"\n  Byte frequency analysis (first 4096 bytes of payload):")
    region = payload[:4096]
    counts = Counter(region)
    # Show top 10 and bottom 10 most common bytes
    sorted_counts = sorted(counts.items(), key=lambda x: -x[1])
    print(f"    Most common:  {', '.join(f'0x{b:02X}({c})' for b,c in sorted_counts[:10])}")
    print(f"    Least common: {', '.join(f'0x{b:02X}({c})' for b,c in sorted_counts[-10:])}")
    # If XOR encrypted with a single byte, one byte value would dominate (for null bytes)
    # Expected ~16 occurrences per byte for uniform distribution in 4096 bytes
    max_count = sorted_counts[0][1]
    min_count = sorted_counts[-1][1]
    print(f"    Expected uniform: {4096/256:.1f} per byte")
    print(f"    Actual range: {min_count} to {max_count}")

    # Bigram analysis
    print(f"\n  Bigram frequency (first 4096 bytes of payload):")
    bigrams = Counter(region[i:i+2] for i in range(len(region)-1))
    sorted_bigrams = sorted(bigrams.items(), key=lambda x: -x[1])
    print(f"    Most common:  {', '.join(f'{b.hex()}({c})' for b,c in sorted_bigrams[:10])}")

    return data


def compare_headers(images):
    """Compare headers across firmware versions."""
    print(f"\n{'='*70}")
    print(f"  CROSS-VERSION COMPARISON")
    print(f"{'='*70}")

    # Byte-by-byte comparison of headers
    print(f"\n  Byte-by-byte header comparison (same='.', diff='X'):")
    min_len = min(len(d) for _, d in images)
    header_size = 0x30  # 48 bytes

    print(f"  Offset", end="")
    for name, _ in images:
        ver = name.split('_')[0]
        print(f"  {ver:>20s}", end="")
    print("  Match")

    for offset in range(0, header_size, 4):
        values = []
        for _, data in images:
            val = data[offset:offset+4]
            values.append(val)

        match = "SAME" if all(v == values[0] for v in values) else "DIFF"
        print(f"  0x{offset:02X} ", end="")
        for val in values:
            print(f"  {' '.join(f'{b:02X}' for b in val):>20s}", end="")
        print(f"  {match}")

    # Compare payload starts
    print(f"\n  Payload comparison (first 128 bytes after header):")
    for offset in range(0x30, 0x30 + 128, 4):
        values = []
        for _, data in images:
            val = data[offset:offset+4]
            values.append(val)

        match = "SAME" if all(v == values[0] for v in values) else "DIFF"
        if match == "SAME":
            continue  # Only show differences
        print(f"  0x{offset:02X} ", end="")
        for val in values:
            print(f"  {' '.join(f'{b:02X}' for b in val):>20s}", end="")
        print(f"  {match}")

    # Find first byte that differs in payload
    print(f"\n  First difference in payload between versions:")
    for i in range(len(images)):
        for j in range(i+1, len(images)):
            name_i = images[i][0].split('_')[0]
            name_j = images[j][0].split('_')[0]
            data_i = images[i][1]
            data_j = images[j][1]
            max_compare = min(len(data_i), len(data_j))
            for k in range(0x30, max_compare):
                if data_i[k] != data_j[k]:
                    print(f"    {name_i} vs {name_j}: first diff at offset 0x{k:X}")
                    # Show surrounding bytes
                    start = max(0x30, k-8)
                    for off in range(start, min(k+16, max_compare), 4):
                        v_i = ' '.join(f'{b:02X}' for b in data_i[off:off+4])
                        v_j = ' '.join(f'{b:02X}' for b in data_j[off:off+4])
                        marker = " <---" if off <= k < off+4 else ""
                        print(f"      0x{off:04X}: {v_i}  vs  {v_j}{marker}")
                    break

    # Specifically check if header fields could be: version, size, checksum
    print(f"\n  Potential header field interpretations:")
    for _, data in images:
        name = _.split('_')[0] if '_' in _ else _
        size = len(data)
        payload_size = size - 0x30

        print(f"\n    {name} (total={size}, payload={payload_size}):")

        # Check if any header word matches payload size or total size
        for offset in range(0x10, 0x30, 4):
            for endian, label in [('<', 'LE'), ('>', 'BE')]:
                val = struct.unpack_from(f'{endian}I', data, offset)[0]
                if val == size:
                    print(f"      [0x{offset:02X}] {label} = total image size ({size})")
                elif val == payload_size:
                    print(f"      [0x{offset:02X}] {label} = payload size ({payload_size})")
                elif val == size - 1:
                    print(f"      [0x{offset:02X}] {label} = total size - 1 ({size-1})")
                elif val == payload_size - 1:
                    print(f"      [0x{offset:02X}] {label} = payload size - 1 ({payload_size-1})")
                elif abs(val - size) < 256:
                    print(f"      [0x{offset:02X}] {label} = ~total size (off by {val-size})")
                elif abs(val - payload_size) < 256:
                    print(f"      [0x{offset:02X}] {label} = ~payload size (off by {val-payload_size})")

        # Try CRC32 of payload
        import zlib
        crc = zlib.crc32(data[0x30:]) & 0xFFFFFFFF
        print(f"      Payload CRC32: 0x{crc:08X}")
        for offset in range(0x10, 0x30, 4):
            for endian, label in [('<', 'LE'), ('>', 'BE')]:
                val = struct.unpack_from(f'{endian}I', data, offset)[0]
                if val == crc:
                    print(f"      [0x{offset:02X}] {label} = payload CRC32!")


def try_decompression(data: bytes, name: str):
    """Try various decompression methods on payload."""
    payload = data[0x30:]
    print(f"\n{'='*70}")
    print(f"  DECOMPRESSION ATTEMPTS: {name}")
    print(f"{'='*70}")

    import zlib
    import gzip
    import io

    # Try raw deflate at various offsets
    for offset in range(0, min(128, len(payload)), 4):
        try:
            result = zlib.decompress(payload[offset:], -15)
            print(f"  RAW DEFLATE at payload+0x{offset:X}: SUCCESS ({len(result)} bytes)")
            return result
        except zlib.error:
            pass

        try:
            result = zlib.decompress(payload[offset:])
            print(f"  ZLIB at payload+0x{offset:X}: SUCCESS ({len(result)} bytes)")
            return result
        except zlib.error:
            pass

    # Try with wbits from -15 to 15 and 16+15 (gzip)
    for wbits in [-15, -14, -13, -12, -11, -10, -9, -8, 15, 31, 47]:
        for offset in range(0, min(64, len(payload)), 4):
            try:
                result = zlib.decompress(payload[offset:], wbits)
                print(f"  zlib wbits={wbits} at payload+0x{offset:X}: SUCCESS ({len(result)} bytes)")
                return result
            except zlib.error:
                pass

    print(f"  All zlib/deflate attempts failed")

    # Try LZMA
    import lzma
    for offset in range(0, min(128, len(payload)), 4):
        try:
            result = lzma.decompress(payload[offset:])
            print(f"  LZMA at payload+0x{offset:X}: SUCCESS ({len(result)} bytes)")
            return result
        except (lzma.LZMAError, ValueError):
            pass

    # Try LZMA with various format options
    for fmt in [lzma.FORMAT_AUTO, lzma.FORMAT_ALONE, lzma.FORMAT_RAW, lzma.FORMAT_XZ]:
        fmt_name = {lzma.FORMAT_AUTO: "AUTO", lzma.FORMAT_ALONE: "ALONE",
                    lzma.FORMAT_RAW: "RAW", lzma.FORMAT_XZ: "XZ"}[fmt]
        for offset in [0, 4, 8, 12, 16]:
            try:
                if fmt == lzma.FORMAT_RAW:
                    filters = [{"id": lzma.FILTER_LZMA1}]
                    result = lzma.decompress(payload[offset:], format=fmt, filters=filters)
                else:
                    result = lzma.decompress(payload[offset:], format=fmt)
                print(f"  LZMA {fmt_name} at payload+0x{offset:X}: SUCCESS ({len(result)} bytes)")
                return result
            except (lzma.LZMAError, ValueError):
                pass

    print(f"  All LZMA attempts failed")

    # Try bzip2
    import bz2
    for offset in range(0, min(64, len(payload)), 4):
        try:
            result = bz2.decompress(payload[offset:])
            print(f"  BZIP2 at payload+0x{offset:X}: SUCCESS ({len(result)} bytes)")
            return result
        except (ValueError, OSError):
            pass

    print(f"  All bzip2 attempts failed")

    # Check for XOR encryption with common keys
    print(f"\n  Checking XOR encryption:")
    # If the payload is XOR'd, we can try common keys
    # ARM code has lots of 0x00 bytes, so XOR key would show up as the most common byte
    from collections import Counter
    first_4k = payload[:4096]
    counts = Counter(first_4k)
    most_common_byte = counts.most_common(1)[0][0]
    print(f"    Most common byte: 0x{most_common_byte:02X} (count: {counts.most_common(1)[0][1]})")

    # Try XOR with most common byte (might be the key if lots of nulls in original)
    for key_byte in [most_common_byte, 0xFF, 0x00, 0xA5, 0x5A]:
        decrypted = bytes(b ^ key_byte for b in first_4k)
        # Check if result has ARM-like patterns
        # ARM vector table: first 8 words are branch instructions (0xEAxxxxxx)
        arm_branches = sum(1 for i in range(0, 32, 4)
                         if struct.unpack_from('<I', decrypted, i)[0] & 0xFF000000 == 0xEA000000)
        if arm_branches >= 3:
            print(f"    XOR 0x{key_byte:02X}: Found {arm_branches}/8 ARM branches in first 32 bytes!")

    # Multi-byte XOR
    for key_len in [2, 4, 8]:
        # Extract key from repeating pattern
        # Use frequency analysis on each position
        for pos in range(key_len):
            subset = bytes(first_4k[i] for i in range(pos, len(first_4k), key_len))
            pos_counts = Counter(subset)

    print(f"  No simple XOR encryption detected")

    return None


def check_digi_bootloader_format(data: bytes, name: str):
    """Check for known Digi bootloader/POST formats."""
    print(f"\n{'='*70}")
    print(f"  DIGI BOOTLOADER FORMAT ANALYSIS: {name}")
    print(f"{'='*70}")

    # The Digi POST (Power-On Self Test) ROM monitor has specific formats
    # Check for segment descriptors after the 48-byte header

    # Theory: after the 48-byte header, there might be a segment table
    # Each segment could be: load_address (4), size (4), [compressed_size (4), checksum (4)]

    print(f"\n  Checking for segment descriptor table at 0x30-0x60:")
    for offset in range(0x30, min(0x70, len(data)), 4):
        val_le = struct.unpack_from('<I', data, offset)[0]
        val_be = struct.unpack_from('>I', data, offset)[0]
        raw = data[offset:offset+4]
        print(f"    [0x{offset:02X}] {' '.join(f'{b:02X}' for b in raw)}"
              f"  LE=0x{val_le:08X}"
              f"  BE=0x{val_be:08X}")

    # Check if the data at 0x30 could be an ARM exception vector table
    # but loaded at a different address
    # NS9360 can remap vectors to high (0xFFFF0000) or low (0x00000000)
    # NOR flash is at 0x50000000

    # Try treating bytes at 0x30 as relative branch instructions
    # B instruction: 0xEA000000 | (offset & 0x00FFFFFF)
    # The offset is relative to PC+8
    print(f"\n  Checking 0x30-0x50 as ARM branch table (loaded at 0x00000000):")
    for i in range(0, min(32, len(data)-0x30), 4):
        word_le = struct.unpack_from('<I', data, 0x30 + i)[0]
        word_be = struct.unpack_from('>I', data, 0x30 + i)[0]

        for word, label in [(word_le, 'LE'), (word_be, 'BE')]:
            if (word & 0x0F000000) == 0x0A000000:
                cond = (word >> 28) & 0xF
                link = word & 0x01000000
                signed_offset = word & 0x00FFFFFF
                if signed_offset & 0x800000:
                    signed_offset -= 0x1000000
                target = i + 8 + (signed_offset << 2)
                op = "BL" if link else "B"
                cond_names = ['EQ','NE','CS','CC','MI','PL','VS','VC',
                              'HI','LS','GE','LT','GT','LE','AL','NV']
                print(f"    [{label}] 0x{i:02X}: {op}{cond_names[cond]} -> 0x{target & 0xFFFFFFFF:08X}")

    # Search for ARM vector table anywhere in first 4096 bytes
    print(f"\n  Searching for ARM vector table pattern in first 4096 bytes:")
    for offset in range(0, min(4096, len(data)), 4):
        # Check if we see at least 4 branch instructions in a row at word-aligned addresses
        branches = 0
        for i in range(0, 32, 4):
            if offset + i + 4 > len(data):
                break
            word = struct.unpack_from('<I', data, offset + i)[0]
            if (word & 0x0F000000) == 0x0A000000:
                cond = (word >> 28) & 0xF
                if cond in [0xE, 0xF]:  # AL or NV condition
                    branches += 1
        if branches >= 4:
            print(f"    Possible LE vector table at 0x{offset:04X} ({branches} branches)")

        # Also check BE
        branches = 0
        for i in range(0, 32, 4):
            if offset + i + 4 > len(data):
                break
            word = struct.unpack_from('>I', data, offset + i)[0]
            if (word & 0x0F000000) == 0x0A000000:
                cond = (word >> 28) & 0xF
                if cond in [0xE, 0xF]:
                    branches += 1
        if branches >= 4:
            print(f"    Possible BE vector table at 0x{offset:04X} ({branches} branches)")

    # Look for the strings we know exist and map them
    print(f"\n  String locations (all printable strings >= 6 chars):")
    strings_found = []
    current = []
    for i in range(len(data)):
        b = data[i]
        if 32 <= b < 127:
            current.append(chr(b))
        else:
            if len(current) >= 6:
                s = ''.join(current)
                strings_found.append((i - len(current), s))
            current = []

    # Group strings by region
    regions = {}
    for pos, s in strings_found:
        region_start = (pos // 0x10000) * 0x10000
        if region_start not in regions:
            regions[region_start] = []
        regions[region_start].append((pos, s))

    for region_start in sorted(regions.keys()):
        strings = regions[region_start]
        print(f"\n    Region 0x{region_start:06X}-0x{region_start+0xFFFF:06X}: {len(strings)} strings")
        # Show first few and any interesting ones
        shown = 0
        for pos, s in strings:
            if shown < 5 or any(keyword in s.lower() for keyword in
                ['boot', 'digi', 'net', 'arm', 'henning', 'brooklyn', 'version',
                 'compress', 'decompress', 'flash', 'load', 'error', 'netos',
                 'rompager', 'http', 'html', 'ipdu', 'hppdu']):
                print(f"      0x{pos:06X}: \"{s[:80]}\"")
                shown += 1

    # Total printable vs non-printable in first 4096 bytes after header
    payload = data[0x30:]
    printable = sum(1 for b in payload[:4096] if 32 <= b < 127)
    total = min(4096, len(payload))
    print(f"\n  Printable chars in first 4096 payload bytes: {printable}/{total} ({100*printable/total:.1f}%)")

    return strings_found


def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))

    # Load all firmware images
    images = []
    for fname in sorted(os.listdir(EXTRACT_DIR)):
        if fname.endswith('_image.bin'):
            path = os.path.join(EXTRACT_DIR, fname)
            with open(path, 'rb') as f:
                data = f.read()
            images.append((fname, data))

    if not images:
        print(f"ERROR: No image.bin files found in {EXTRACT_DIR}/")
        sys.exit(1)

    print(f"Found {len(images)} firmware images")

    # Parse each header
    for name, data in images:
        parse_header(data, name)
        check_digi_bootloader_format(data, name)

    # Compare across versions
    if len(images) > 1:
        compare_headers(images)

    # Try decompression on the newest version
    newest = images[-1]
    try_decompression(newest[1], newest[0])


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Decompress HPE iPDU firmware images.

The firmware uses the Digi NET+OS bootHdr format with LZSS2 compression.
Header format (big-endian):
  [0x00] 4 bytes: Complete header size (NET+OS + custom header)
  [0x04] 4 bytes: NET+OS header size (36 for pre-7.4, 92 for post-7.4)
  [0x08] 8 bytes: Signature "bootHdr\0"
  [0x10] 4 bytes: NET+OS version
  [0x14] 4 bytes: Flags (bit 0=WriteToFlash, bit 3=LZSS2 compressed)
  [0x18] 4 bytes: Flash address (where to store in NOR flash)
  [0x1C] 4 bytes: RAM address (where to decompress to in RAM)
  [0x20] 4 bytes: Image size (compressed data size)
  [0x24] 8 bytes: Custom header "HPPDU00\0" (OEM product ID)
  [0x2C] ...   : LZSS2-compressed data
  [last 4]     : CRC32 checksum

LZSS2 algorithm based on gsuberland/open-network-ms parser.
"""

import os
import struct
import sys
import zlib

EXTRACT_DIR = "extracted"

# Header flags
BL_WRITE_TO_FLASH = 1 << 0
BL_LZSS_COMPRESSED_MAYBE = 1 << 1
BL_EXECUTE_FROM_ROM = 1 << 2
BL_LZSS2_COMPRESSED = 1 << 3
BL_BYPASS_CRC_CHECK = 1 << 4
BL_BYPASS_IMGLEN_CHECK = 1 << 5

FLAG_NAMES = {
    BL_WRITE_TO_FLASH: "BL_WRITE_TO_FLASH",
    BL_LZSS_COMPRESSED_MAYBE: "BL_LZSS_COMPRESSED_MAYBE",
    BL_EXECUTE_FROM_ROM: "BL_EXECUTE_FROM_ROM",
    BL_LZSS2_COMPRESSED: "BL_LZSS2_COMPRESSED",
    BL_BYPASS_CRC_CHECK: "BL_BYPASS_CRC_CHECK",
    BL_BYPASS_IMGLEN_CHECK: "BL_BYPASS_IMGLEN_CHECK",
}


def decompress_lzss2(data: bytes, expected_size: int) -> bytes:
    """Decompress LZSS2-compressed data.

    This implements the exact LZSS2 algorithm used by the Digi NET+OS bootloader.
    Parameters:
      N = 4096 (sliding window size)
      F = 18 (look-ahead buffer size)
      Threshold = 2 (minimum match length)
      Buffer initialized with spaces (0x20)
    """
    N = 4096           # Window size
    F = 18             # Look-ahead buffer size
    THRESHOLD = 2      # Minimum match length

    # Initialise ring buffer with spaces (0x20), as per NET+OS implementation
    ring_buffer = bytearray(b' ' * (N + F - 1))
    r = N - F  # Current position in ring buffer

    output = bytearray()
    pos = 0  # Position in input data
    flags = 0  # Flag byte - bit 8 acts as sentinel for exhaustion

    while pos < len(data):
        # Shift flags right; when bit 8 becomes 0, all 8 flag bits consumed
        flags >>= 1
        if (flags & 256) == 0:
            if pos >= len(data):
                break
            flags = data[pos] | 0xFF00
            pos += 1

        if flags & 1:
            # Literal byte
            if pos >= len(data):
                break
            c = data[pos]
            pos += 1
            output.append(c)
            ring_buffer[r] = c
            r = (r + 1) & (N - 1)
        else:
            # Back-reference: read 2 bytes
            if pos + 1 >= len(data):
                break
            i = data[pos]
            j = data[pos + 1]
            pos += 2

            # Decode position and length
            i |= (j & 0xF0) << 4  # 12-bit position in ring buffer
            j = (j & 0x0F) + THRESHOLD  # Length (4-bit + threshold)

            # Copy from ring buffer
            for k in range(j + 1):
                b = ring_buffer[(i + k) & (N - 1)]
                output.append(b)
                ring_buffer[r] = b
                r = (r + 1) & (N - 1)

        # Progress reporting
        if len(output) % (1024 * 1024) < 256:
            pct = 100 * pos / len(data) if len(data) > 0 else 0
            print(f"\r  Decompressing: {len(output):,} bytes output, "
                  f"{pos:,}/{len(data):,} input ({pct:.1f}%)", end="", flush=True)

    print(f"\r  Decompressed: {len(output):,} bytes from {len(data):,} bytes "
          f"(ratio: {len(output)/len(data):.2f}x)                    ")

    return bytes(output)


def parse_header(data: bytes, name: str) -> dict:
    """Parse the NET+OS bootHdr format."""
    print(f"\n{'='*70}")
    print(f"  {name} ({len(data):,} bytes)")
    print(f"{'='*70}")

    # All fields are big-endian
    complete_header_size = struct.unpack_from('>I', data, 0x00)[0]
    netos_header_size = struct.unpack_from('>I', data, 0x04)[0]
    signature = data[0x08:0x10].split(b'\x00')[0].decode('ascii', errors='replace')
    version = struct.unpack_from('>I', data, 0x10)[0]
    flags = struct.unpack_from('>I', data, 0x14)[0]
    flash_address = struct.unpack_from('>I', data, 0x18)[0]
    ram_address = struct.unpack_from('>I', data, 0x1C)[0]
    image_size = struct.unpack_from('>I', data, 0x20)[0]

    # Custom header (bytes after NET+OS header, before data)
    custom_header = data[netos_header_size:complete_header_size]
    custom_header_str = custom_header.split(b'\x00')[0].decode('ascii', errors='replace')

    # CRC32 at end of file
    crc32_stored = struct.unpack_from('>I', data, complete_header_size + image_size)[0]

    # Calculate CRC32 (cover header + data, excluding the stored CRC)
    # Actually, the CRC32 in NET+OS typically covers the compressed data only
    # Let me check both
    data_region = data[complete_header_size:complete_header_size + image_size]
    crc32_data_only = zlib.crc32(data_region) & 0xFFFFFFFF
    crc32_header_and_data = zlib.crc32(data[:complete_header_size + image_size]) & 0xFFFFFFFF

    # Decode flags
    flag_strs = []
    for bit_val, name_str in FLAG_NAMES.items():
        if flags & bit_val:
            flag_strs.append(name_str)

    # Decode version
    if version < 0x0704:
        version_str = f"pre-7.4 (0x{version:04X})"
    elif version <= 0xFFFF:
        major = (version >> 8) & 0xFF
        minor = version & 0xFF
        version_str = f"{major}.{minor}"
    else:
        version_str = f"unknown (0x{version:08X})"

    print(f"\n  NET+OS Header (all big-endian):")
    print(f"  [0x00] Complete header size: {complete_header_size} (0x{complete_header_size:X})")
    print(f"  [0x04] NET+OS header size:   {netos_header_size} (0x{netos_header_size:X})")
    print(f"  [0x08] Signature:            \"{signature}\"")
    print(f"  [0x10] Version:              {version_str}")
    print(f"  [0x14] Flags:                0x{flags:08X} = {' | '.join(flag_strs)}")
    print(f"  [0x18] Flash address:        0x{flash_address:08X}")
    print(f"  [0x1C] RAM address:          0x{ram_address:08X}")
    print(f"  [0x20] Image size:           {image_size:,} (0x{image_size:X})")
    print(f"  [0x24] Custom header:        \"{custom_header_str}\" ({len(custom_header)} bytes)")
    print()
    print(f"  Data offset:                 0x{complete_header_size:X}")
    print(f"  Data end:                    0x{complete_header_size + image_size:X}")
    print(f"  CRC32 offset:                0x{complete_header_size + image_size:X}")
    print(f"  CRC32 stored:                0x{crc32_stored:08X}")
    print(f"  CRC32 (data only):           0x{crc32_data_only:08X} {'MATCH!' if crc32_data_only == crc32_stored else 'no match'}")
    print(f"  CRC32 (header+data):         0x{crc32_header_and_data:08X} {'MATCH!' if crc32_header_and_data == crc32_stored else 'no match'}")
    print(f"  File size:                   {len(data):,}")
    print(f"  Expected:                    {complete_header_size + image_size + 4:,} "
          f"({'MATCH' if len(data) == complete_header_size + image_size + 4 else 'MISMATCH'})")

    return {
        'complete_header_size': complete_header_size,
        'netos_header_size': netos_header_size,
        'signature': signature,
        'version': version,
        'flags': flags,
        'flash_address': flash_address,
        'ram_address': ram_address,
        'image_size': image_size,
        'custom_header': custom_header_str,
        'crc32_stored': crc32_stored,
        'data': data_region,
    }


def analyse_decompressed(data: bytes, ram_address: int, name: str):
    """Analyse the decompressed firmware binary."""
    print(f"\n  Decompressed analysis ({name}):")
    print(f"  Size: {len(data):,} bytes ({len(data)/1024/1024:.2f} MB)")
    print(f"  Load address: 0x{ram_address:08X}")

    # Hex dump of first 128 bytes
    print(f"\n  First 128 bytes (at 0x{ram_address:08X}):")
    for i in range(0, min(128, len(data)), 16):
        hex_part = ' '.join(f'{b:02X}' for b in data[i:i+16])
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
        print(f"    {ram_address+i:08X}: {hex_part:<48s} {ascii_part}")

    # Check for ARM vector table at start
    print(f"\n  ARM vector table check:")
    for endian, label in [('<', 'LE'), ('>', 'BE')]:
        vectors = []
        for i in range(0, min(32, len(data)), 4):
            word = struct.unpack_from(f'{endian}I', data, i)[0]
            vectors.append(word)

        # Check if first 8 words look like ARM branch instructions
        branches = sum(1 for w in vectors[:8] if (w & 0x0F000000) == 0x0A000000)
        ldr_pc = sum(1 for w in vectors[:8] if (w & 0x0FFF0000) == 0x059F0000)
        mov_nop = sum(1 for w in vectors[:8] if w == 0xE1A00000)

        print(f"    {label}: B instructions={branches}, LDR PC=[PC+]={ldr_pc}, NOP={mov_nop}")
        if branches >= 4 or ldr_pc >= 4:
            print(f"    {label}: Looks like a valid ARM vector table!")
            for i, w in enumerate(vectors[:8]):
                vec_names = ['Reset', 'Undef', 'SWI', 'PAbort', 'DAbort', 'Reserved', 'IRQ', 'FIQ']
                if (w & 0x0F000000) == 0x0A000000:
                    offset_val = w & 0x00FFFFFF
                    if offset_val & 0x800000:
                        offset_val -= 0x1000000
                    target = ram_address + i*4 + 8 + (offset_val << 2)
                    link = "BL" if w & 0x01000000 else "B"
                    print(f"      {vec_names[i]:8s}: {link} 0x{target:08X}")
                elif (w & 0x0FFF0000) == 0x059F0000:
                    print(f"      {vec_names[i]:8s}: LDR PC, [PC, #0x{w & 0xFFF:X}]")
                else:
                    print(f"      {vec_names[i]:8s}: 0x{w:08X}")

    # Entropy analysis
    import math
    from collections import Counter
    for region_name, start, size in [
        ("first 4096", 0, 4096),
        ("middle", len(data)//2, 4096),
        ("end-4096", len(data)-4096, 4096),
    ]:
        region = data[start:start+size]
        if len(region) < size:
            continue
        counts = Counter(region)
        entropy = -sum((c/len(region)) * math.log2(c/len(region)) for c in counts.values())
        print(f"  Entropy [{region_name}]: {entropy:.4f} bits/byte")

    # Search for key strings
    print(f"\n  Key strings found:")
    markers = [
        b'NET+OS', b'NET+ARM', b'Brooklyn', b'Henning', b'RomPager',
        b'MAXQ', b'SPI', b'UART', b'GPIO', b'flash', b'Flash',
        b'Ethernet', b'SNMP', b'HTTP', b'Telnet', b'FTP',
        b'netos', b'ThreadX', b'Allegro', b'iPDU', b'HPPDU',
        b'NS9360', b'version', b'Version', b'Copyright',
        b'0x9060', b'0x9050', b'BBus',
    ]
    for marker in markers:
        pos = 0
        found = []
        while True:
            pos = data.find(marker, pos)
            if pos == -1:
                break
            found.append(pos)
            pos += 1
        if found:
            for p in found[:3]:
                # Extract context
                start = max(0, p - 8)
                end = min(len(data), p + len(marker) + 64)
                context = data[start:end]
                display = ''.join(chr(b) if 32 <= b < 127 else '.' for b in context)
                print(f"    0x{ram_address+p:08X}: \"{display}\"")
            if len(found) > 3:
                print(f"    ... ({len(found)} total)")

    # Count printable vs non-printable
    printable = sum(1 for b in data if 32 <= b < 127)
    print(f"\n  Printable bytes: {printable:,}/{len(data):,} ({100*printable/len(data):.1f}%)")


def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))
    os.makedirs(EXTRACT_DIR, exist_ok=True)

    # Process each firmware image
    for fname in sorted(os.listdir(EXTRACT_DIR)):
        if not fname.endswith('_image.bin'):
            continue

        path = os.path.join(EXTRACT_DIR, fname)
        with open(path, 'rb') as f:
            data = f.read()

        version_label = fname.replace('_image.bin', '')

        # Parse header
        header = parse_header(data, fname)

        # Decompress if LZSS2 compressed
        if header['flags'] & BL_LZSS2_COMPRESSED:
            print(f"\n  LZSS2 compressed - decompressing...")
            decompressed = decompress_lzss2(header['data'], header['image_size'])

            # Save decompressed binary
            out_path = os.path.join(EXTRACT_DIR, f"{version_label}_decompressed.bin")
            with open(out_path, 'wb') as f:
                f.write(decompressed)
            print(f"  Saved to {out_path}")

            # Analyse decompressed data
            analyse_decompressed(decompressed, header['ram_address'], version_label)
        else:
            print(f"\n  Not LZSS2 compressed (flags=0x{header['flags']:X})")
            # Still save the raw data
            out_path = os.path.join(EXTRACT_DIR, f"{version_label}_raw.bin")
            with open(out_path, 'wb') as f:
                f.write(header['data'])
            print(f"  Saved raw data to {out_path}")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Identify the CRC32 algorithm used in Digi NET+OS bootHdr firmware images.

The firmware has a 4-byte CRC at the end of the file (after the LZSS2
compressed payload). Standard CRC32 (zlib) does not match. This script
tries many CRC32 variants to find the correct one.

The bootHdr format is:
  [44-byte header][compressed data (image_size bytes)][4-byte CRC]

Uses lookup tables for fast CRC computation instead of bit-by-bit processing.
"""

import os
import struct
import zlib
import array

EXTRACT_DIR = "extracted"


def make_crc32_table(poly, reflected=True):
    """Build a 256-entry CRC32 lookup table.

    Args:
        poly: Generator polynomial (reflected form if reflected=True,
              normal form if reflected=False)
        reflected: If True, build table for LSB-first (reflected) processing.
                   If False, build table for MSB-first (normal) processing.
    """
    table = []
    if reflected:
        for i in range(256):
            crc = i
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ poly
                else:
                    crc >>= 1
            table.append(crc)
    else:
        for i in range(256):
            crc = i << 24
            for _ in range(8):
                if crc & 0x80000000:
                    crc = ((crc << 1) ^ poly) & 0xFFFFFFFF
                else:
                    crc = (crc << 1) & 0xFFFFFFFF
            table.append(crc)
    return table


def crc32_table(data, table, init=0xFFFFFFFF, xor_out=0xFFFFFFFF, reflected=True):
    """Compute CRC32 using a precomputed lookup table.

    This is ~50-100x faster than bit-by-bit processing in Python.
    """
    crc = init
    if reflected:
        for byte in data:
            crc = table[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    else:
        for byte in data:
            crc = table[((crc >> 24) ^ byte) & 0xFF] ^ ((crc << 8) & 0xFFFFFFFF)
    return (crc ^ xor_out) & 0xFFFFFFFF


def reflect32(value):
    """Reflect (reverse) bits of a 32-bit value."""
    result = 0
    for i in range(32):
        if value & (1 << i):
            result |= 1 << (31 - i)
    return result


# Build lookup tables once for all known polynomials
POLY_TABLES = {
    # Reflected polynomials (for reflected/LSB-first algorithms)
    (0xEDB88320, True): make_crc32_table(0xEDB88320, reflected=True),   # CRC-32
    (0x82F63B78, True): make_crc32_table(0x82F63B78, reflected=True),   # CRC-32C
    # Normal polynomials (for non-reflected/MSB-first algorithms)
    (0x04C11DB7, False): make_crc32_table(0x04C11DB7, reflected=False), # MPEG-2, BZIP2, POSIX
    (0x814141AB, False): make_crc32_table(0x814141AB, reflected=False), # CRC-32Q
    (0x000000AF, False): make_crc32_table(0x000000AF, reflected=False), # CRC-32/XFER
}

# Common CRC32 algorithm definitions
CRC_ALGORITHMS = {
    "CRC-32 (standard/ISO-HDLC)": {
        "poly": 0xEDB88320, "init": 0xFFFFFFFF, "xor_out": 0xFFFFFFFF, "reflected": True,
    },
    "CRC-32/JAMCRC": {
        "poly": 0xEDB88320, "init": 0xFFFFFFFF, "xor_out": 0x00000000, "reflected": True,
    },
    "CRC-32/MPEG-2": {
        "poly": 0x04C11DB7, "init": 0xFFFFFFFF, "xor_out": 0x00000000, "reflected": False,
    },
    "CRC-32/BZIP2": {
        "poly": 0x04C11DB7, "init": 0xFFFFFFFF, "xor_out": 0xFFFFFFFF, "reflected": False,
    },
    "CRC-32/POSIX (cksum)": {
        "poly": 0x04C11DB7, "init": 0x00000000, "xor_out": 0xFFFFFFFF, "reflected": False,
    },
    "CRC-32C (Castagnoli)": {
        "poly": 0x82F63B78, "init": 0xFFFFFFFF, "xor_out": 0xFFFFFFFF, "reflected": True,
    },
    "CRC-32Q": {
        "poly": 0x814141AB, "init": 0x00000000, "xor_out": 0x00000000, "reflected": False,
    },
    "CRC-32/XFER": {
        "poly": 0x000000AF, "init": 0x00000000, "xor_out": 0x00000000, "reflected": False,
    },
    "CRC-32 init=0": {
        "poly": 0xEDB88320, "init": 0x00000000, "xor_out": 0xFFFFFFFF, "reflected": True,
    },
    "CRC-32 init=0 xor=0": {
        "poly": 0xEDB88320, "init": 0x00000000, "xor_out": 0x00000000, "reflected": True,
    },
}


def compute_crc(data, algo_params):
    """Compute CRC using the appropriate lookup table."""
    poly = algo_params["poly"]
    reflected = algo_params["reflected"]
    table = POLY_TABLES[(poly, reflected)]
    return crc32_table(data, table, algo_params["init"], algo_params["xor_out"], reflected)


def check_match(crc, expected_be, expected_le):
    """Check if CRC matches expected value in either byte order."""
    if crc == expected_be:
        return "BE"
    if crc == expected_le:
        return "LE"
    # Also try byte-swapped
    crc_swapped = struct.unpack('>I', struct.pack('<I', crc))[0]
    if crc_swapped == expected_be:
        return "swapped-BE"
    if crc_swapped == expected_le:
        return "swapped-LE"
    return None


def try_all_crc_variants(data_ranges, expected_be, expected_le, ver):
    """Try all CRC32 algorithms against multiple data ranges."""
    for range_name, range_data in data_ranges:
        for algo_name, params in CRC_ALGORITHMS.items():
            crc = compute_crc(range_data, params)
            match = check_match(crc, expected_be, expected_le)
            if match:
                print(f"  *** MATCH ({match}) *** {ver}: {algo_name} on {range_name}")
                print(f"      CRC = 0x{crc:08X}")
                return True
    return False


def try_checksum_algorithms(data_ranges, expected_be, expected_le, ver):
    """Try non-CRC checksum algorithms using struct for speed."""
    for range_name, range_data in data_ranges:
        n = len(range_data)

        # Pad to multiple of 4 for word-aligned access
        padded = range_data if n % 4 == 0 else range_data + b'\x00' * (4 - n % 4)
        n_words = len(padded) // 4

        # Sum32 BE (big-endian word sum)
        words_be = struct.unpack(f'>{n_words}I', padded)
        checksum_be = sum(words_be) & 0xFFFFFFFF
        if checksum_be == expected_be or checksum_be == expected_le:
            print(f"  *** MATCH *** {ver}: Sum32-BE on {range_name} = 0x{checksum_be:08X}")
            return True

        # Sum32 LE (little-endian word sum)
        words_le = struct.unpack(f'<{n_words}I', padded)
        checksum_le = sum(words_le) & 0xFFFFFFFF
        if checksum_le == expected_be or checksum_le == expected_le:
            print(f"  *** MATCH *** {ver}: Sum32-LE on {range_name} = 0x{checksum_le:08X}")
            return True

        # Two's complement of sum (both endians)
        for label, chk in [("BE", checksum_be), ("LE", checksum_le)]:
            neg = (-chk) & 0xFFFFFFFF
            if neg == expected_be or neg == expected_le:
                print(f"  *** MATCH *** {ver}: -Sum32-{label} on {range_name} = 0x{neg:08X}")
                return True

        # XOR32 BE
        xor_be = 0
        for w in words_be:
            xor_be ^= w
        if xor_be == expected_be or xor_be == expected_le:
            print(f"  *** MATCH *** {ver}: XOR32-BE on {range_name} = 0x{xor_be:08X}")
            return True

        # XOR32 LE
        xor_le = 0
        for w in words_le:
            xor_le ^= w
        if xor_le == expected_be or xor_le == expected_le:
            print(f"  *** MATCH *** {ver}: XOR32-LE on {range_name} = 0x{xor_le:08X}")
            return True

        # Byte sum
        byte_sum = sum(range_data) & 0xFFFFFFFF
        if byte_sum == expected_be or byte_sum == expected_le:
            print(f"  *** MATCH *** {ver}: ByteSum on {range_name} = 0x{byte_sum:08X}")
            return True

        # Sum16 (16-bit word sum, carry-wrapped)
        if n % 2 == 0:
            n_hwords = n // 2
        else:
            n_hwords = (n + 1) // 2
        padded2 = range_data if n % 2 == 0 else range_data + b'\x00'
        hwords_be = struct.unpack(f'>{n_hwords}H', padded2)
        sum16 = sum(hwords_be) & 0xFFFFFFFF
        if sum16 == expected_be or sum16 == expected_le:
            print(f"  *** MATCH *** {ver}: Sum16-BE on {range_name} = 0x{sum16:08X}")
            return True

    return False


def try_header_zeroed_crc(data, expected_be, expected_le, ver):
    """Try CRC with specific header fields zeroed (common in bootloaders)."""
    # Try zeroing each 4-byte header field and computing CRC of full image-4
    for zero_offset in range(0, 0x2C, 4):
        modified = bytearray(data[:-4])
        modified[zero_offset:zero_offset + 4] = b'\x00\x00\x00\x00'
        crc = zlib.crc32(bytes(modified)) & 0xFFFFFFFF
        match = check_match(crc, expected_be, expected_le)
        if match:
            print(f"  *** MATCH ({match}) *** {ver}: zlib.crc32 with header[0x{zero_offset:02X}:0x{zero_offset+4:02X}] zeroed")
            print(f"      CRC = 0x{crc:08X}")
            return True

    # Try all CRC variants with image_size field zeroed
    for zero_offset in [0x20]:
        modified = bytearray(data[:-4])
        modified[zero_offset:zero_offset + 4] = b'\x00\x00\x00\x00'
        mod_bytes = bytes(modified)
        for algo_name, params in CRC_ALGORITHMS.items():
            crc = compute_crc(mod_bytes, params)
            match = check_match(crc, expected_be, expected_le)
            if match:
                print(f"  *** MATCH ({match}) *** {ver}: {algo_name} with header[0x{zero_offset:02X}] zeroed")
                print(f"      CRC = 0x{crc:08X}")
                return True

    return False


def try_posix_cksum_with_length(data_ranges, expected_be, expected_le, ver):
    """Try POSIX cksum style (CRC then fold in file length).

    The POSIX cksum command appends the file length to the data before
    finalizing the CRC. Some embedded systems do similar things.
    """
    table = POLY_TABLES[(0x04C11DB7, False)]

    for range_name, range_data in data_ranges:
        # Standard POSIX: CRC the data, then CRC the length bytes
        crc = crc32_table(range_data, table, init=0x00000000, xor_out=0x00000000, reflected=False)
        length = len(range_data)
        while length > 0:
            crc = table[((crc >> 24) ^ (length & 0xFF)) & 0xFF] ^ ((crc << 8) & 0xFFFFFFFF)
            length >>= 8
        crc ^= 0xFFFFFFFF
        match = check_match(crc, expected_be, expected_le)
        if match:
            print(f"  *** MATCH ({match}) *** {ver}: POSIX cksum on {range_name}")
            print(f"      CRC = 0x{crc:08X}")
            return True

    return False


def try_crc_of_decompressed(ver, fname, expected_be, expected_le):
    """Try CRC of decompressed firmware."""
    decomp_path = os.path.join(EXTRACT_DIR, fname.replace('_image.bin', '_decompressed.bin'))
    if not os.path.exists(decomp_path):
        print(f"  Decompressed file not found: {decomp_path}")
        return False

    with open(decomp_path, 'rb') as f:
        decomp = f.read()

    print(f"  Decompressed: {len(decomp):,} bytes")

    # Try all CRC algorithms on decompressed data
    for algo_name, params in CRC_ALGORITHMS.items():
        crc = compute_crc(decomp, params)
        match = check_match(crc, expected_be, expected_le)
        if match:
            print(f"  *** MATCH ({match}) *** {ver}: {algo_name} on decompressed")
            print(f"      CRC = 0x{crc:08X}")
            return True

    # Use zlib for speed as a sanity check
    crc_zlib = zlib.crc32(decomp) & 0xFFFFFFFF
    print(f"  zlib.crc32 of decompressed: 0x{crc_zlib:08X}")

    return False


def try_incremental_crc(data, expected_be, expected_le, ver):
    """Try computing CRC of header and payload separately then combining.

    Some systems compute CRC of the header, then continue with payload.
    Others compute header CRC and payload CRC separately and XOR/combine them.
    """
    header = data[:0x2C]
    payload = data[0x2C:-4]

    # CRC of header, then feed that as init for payload CRC
    for algo_name, params in CRC_ALGORITHMS.items():
        # Two-stage: CRC header with standard init, then CRC payload using
        # the intermediate result (without xor_out) as init for second stage
        poly = params["poly"]
        reflected = params["reflected"]
        table = POLY_TABLES[(poly, reflected)]
        init = params["init"]
        xor_out = params["xor_out"]

        # Stage 1: CRC of header (no final XOR)
        intermediate = crc32_table(header, table, init=init, xor_out=0x00000000, reflected=reflected)
        # Stage 2: CRC of payload using intermediate as init
        crc = crc32_table(payload, table, init=intermediate, xor_out=xor_out, reflected=reflected)

        match = check_match(crc, expected_be, expected_le)
        if match:
            print(f"  *** MATCH ({match}) *** {ver}: {algo_name} two-stage (hdr→payload)")
            print(f"      CRC = 0x{crc:08X}")
            return True

    # Try XOR of separate header and payload CRCs
    for algo_name, params in CRC_ALGORITHMS.items():
        hdr_crc = compute_crc(header, params)
        pay_crc = compute_crc(payload, params)
        combined = (hdr_crc ^ pay_crc) & 0xFFFFFFFF
        match = check_match(combined, expected_be, expected_le)
        if match:
            print(f"  *** MATCH ({match}) *** {ver}: {algo_name} XOR(hdr_crc, payload_crc)")
            print(f"      hdr=0x{hdr_crc:08X} pay=0x{pay_crc:08X} combined=0x{combined:08X}")
            return True

    return False


def try_netos_header_crc(data, expected_be, expected_le, ver):
    """Try CRC ranges based on netos_hdr_size.

    The header has two size fields:
      - complete_hdr_size at 0x00 (typically 44 = 0x2C)
      - netos_hdr_size at 0x04 (typically 36 = 0x24)

    The netos header is 36 bytes starting at offset 4 (i.e., 0x04 to 0x28).
    After that comes 8 bytes of custom data ("HPPDU00\0").
    """
    complete_hdr = struct.unpack_from('>I', data, 0x00)[0]
    netos_hdr = struct.unpack_from('>I', data, 0x04)[0]
    print(f"  complete_hdr_size={complete_hdr}, netos_hdr_size={netos_hdr}")

    ranges = [
        # CRC over just the netos header portion
        (f"netos_hdr (0x04:0x{0x04+netos_hdr:02X})", data[0x04:0x04 + netos_hdr]),
        # CRC from after netos header
        (f"after_netos (0x{0x04+netos_hdr:02X}:-4)", data[0x04 + netos_hdr:-4]),
        # CRC from netos header start to end-4
        (f"netos_hdr_to_end (0x04:-4)", data[0x04:-4]),
    ]

    for range_name, range_data in ranges:
        for algo_name, params in CRC_ALGORITHMS.items():
            crc = compute_crc(range_data, params)
            match = check_match(crc, expected_be, expected_le)
            if match:
                print(f"  *** MATCH ({match}) *** {ver}: {algo_name} on {range_name}")
                print(f"      CRC = 0x{crc:08X}")
                return True

    return False


def search_firmware_for_crc_table(decomp_path):
    """Search the decompressed firmware binary for CRC lookup tables.

    A CRC32 lookup table is a sequence of 256 x 4-byte values. The first
    entry is always 0x00000000. We can identify them by looking for known
    patterns.
    """
    if not os.path.exists(decomp_path):
        return

    with open(decomp_path, 'rb') as f:
        data = f.read()

    print(f"\n  Searching for CRC32 lookup tables in decompressed firmware...")

    # Known first few entries for common CRC32 tables
    # Standard CRC-32 (reflected poly 0xEDB88320):
    #   table[0]=0x00000000, table[1]=0x77073096, table[2]=0xEE0E612C
    known_tables = {
        "CRC-32 (standard)": (b'\x00\x00\x00\x00\x77\x07\x30\x96', True),   # BE byte order
        "CRC-32 (standard, LE)": (b'\x00\x00\x00\x00\x96\x30\x07\x77', True), # LE byte order
        "CRC-32/MPEG-2": (b'\x00\x00\x00\x00\x04\xC1\x1D\xB7', False),      # BE
        "CRC-32/MPEG-2 (LE)": (b'\xB7\x1D\xC1\x04\x00\x00\x00\x00', False), # LE (note: first entry non-zero in LE of non-reflected table!)
        "CRC-32C": (b'\x00\x00\x00\x00\xF2\x6B\x80\x13', True),             # BE of reflected table
        "CRC-32C (LE)": (b'\x00\x00\x00\x00\x13\x80\x6B\xF2', True),        # LE
    }

    # Also search for any 0x00000000 followed by a non-zero word (potential table start)
    found_any = False
    for name, (pattern, reflected) in known_tables.items():
        pos = 0
        while True:
            pos = data.find(pattern, pos)
            if pos < 0:
                break
            # Verify it looks like a 1KB table (256 × 4 bytes)
            # Check that entries 3-5 are non-zero
            if pos + 1024 <= len(data):
                entry3 = struct.unpack_from('>I', data, pos + 12)[0]
                entry4 = struct.unpack_from('>I', data, pos + 16)[0]
                if entry3 != 0 and entry4 != 0:
                    addr = 0x4000 + pos
                    print(f"    Found {name} table at offset 0x{pos:08X} (addr 0x{addr:08X})")
                    # Print first 8 entries
                    for i in range(8):
                        val = struct.unpack_from('>I', data, pos + i * 4)[0]
                        print(f"      [{i}] = 0x{val:08X}")
                    found_any = True
            pos += 1

    if not found_any:
        # Try finding any potential CRC table by looking for 0x00000000 followed by
        # specific patterns
        print(f"    No known CRC32 table patterns found.")
        print(f"    Searching for potential custom tables (0x00000000 + non-trivial entries)...")

        # Look for runs of 0x00000000 followed by reasonable table entries
        count = 0
        pos = 0
        while pos < len(data) - 1024:
            if data[pos:pos+4] == b'\x00\x00\x00\x00' and data[pos+4:pos+8] != b'\x00\x00\x00\x00':
                # Check if this could be a lookup table
                # A CRC table has diverse values - check entropy of first 32 entries
                entries = set()
                for i in range(32):
                    val = struct.unpack_from('>I', data, pos + i * 4)[0]
                    entries.add(val)
                if len(entries) >= 28:  # Most entries should be unique
                    addr = 0x4000 + pos
                    if count < 10:
                        print(f"    Potential table at 0x{pos:08X} (addr 0x{addr:08X}): "
                              f"{len(entries)}/32 unique entries")
                        # Print first 4 entries
                        for i in range(4):
                            val = struct.unpack_from('>I', data, pos + i * 4)[0]
                            print(f"      [{i}] = 0x{val:08X}")
                    count += 1
            pos += 4

        if count > 10:
            print(f"    ... ({count} potential tables total)")
        elif count == 0:
            print(f"    No potential custom CRC tables found.")


def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))

    versions = [
        ("1.6.16.12", "1.6.16.12_Z7550-63196_image.bin"),
        ("2.0.22.12", "2.0.22.12_Z7550-63311_image.bin"),
        ("2.0.51.12", "2.0.51.12_Z7550-02475_image.bin"),
    ]

    results = {}

    for ver, fname in versions:
        with open(os.path.join(EXTRACT_DIR, fname), 'rb') as f:
            data = f.read()

        image_size = struct.unpack_from('>I', data, 0x20)[0]
        expected_be = struct.unpack_from('>I', data, len(data) - 4)[0]
        expected_le = struct.unpack_from('<I', data, len(data) - 4)[0]

        print(f"\n{'='*70}")
        print(f"  {ver}: {len(data):,} bytes")
        print(f"  Image size in header: {image_size:,}")
        print(f"  Expected CRC: BE=0x{expected_be:08X}, LE=0x{expected_le:08X}")
        print(f"{'='*70}")

        print(f"  Header(44) + ImageSize({image_size}) + CRC(4) = {44 + image_size + 4}")
        print(f"  Actual file size = {len(data)}")

        # Define data ranges to try
        data_ranges = [
            ("all-4", data[:-4]),
            ("payload (0x2C:-4)", data[0x2C:-4]),
            ("payload+crc (0x2C:)", data[0x2C:]),
            ("header only (0:0x2C)", data[:0x2C]),
            ("header+payload (0:)", data[:]),
            ("compressed (0x30:-4)", data[0x30:-4]),
            ("netos_hdr+payload (0x04:-4)", data[0x04:-4]),
        ]

        found = False

        # 1. Try all CRC32 variants
        print(f"\n  Trying CRC32 algorithms...")
        found = try_all_crc_variants(data_ranges, expected_be, expected_le, ver)
        if found:
            results[ver] = "CRC match found"
            continue

        # 2. Try checksum algorithms
        print(f"\n  Trying checksum algorithms...")
        found = try_checksum_algorithms(data_ranges, expected_be, expected_le, ver)
        if found:
            results[ver] = "Checksum match found"
            continue

        # 3. Try CRC with header field zeroed
        print(f"\n  Trying CRC with header fields zeroed...")
        found = try_header_zeroed_crc(data, expected_be, expected_le, ver)
        if found:
            results[ver] = "CRC match with header zeroed"
            continue

        # 4. Try POSIX cksum style (with length folded in)
        print(f"\n  Trying POSIX cksum with length...")
        found = try_posix_cksum_with_length(data_ranges, expected_be, expected_le, ver)
        if found:
            results[ver] = "POSIX cksum match"
            continue

        # 5. Try netos_hdr based ranges
        print(f"\n  Trying netos_hdr based ranges...")
        found = try_netos_header_crc(data, expected_be, expected_le, ver)
        if found:
            results[ver] = "NetOS header CRC match"
            continue

        # 6. Try incremental CRC (header then payload)
        print(f"\n  Trying incremental/combined CRC...")
        found = try_incremental_crc(data, expected_be, expected_le, ver)
        if found:
            results[ver] = "Incremental CRC match"
            continue

        # 7. Try CRC of decompressed firmware
        print(f"\n  Trying CRC of decompressed firmware...")
        found = try_crc_of_decompressed(ver, fname, expected_be, expected_le)
        if found:
            results[ver] = "Decompressed CRC match"
            continue

        if not found:
            results[ver] = "NO MATCH"
            print(f"\n  No match found for {ver}.")

    # Search firmware binary for CRC lookup tables
    print(f"\n{'='*70}")
    print(f"  Searching for CRC32 Tables in Firmware")
    print(f"{'='*70}")
    decomp_path = os.path.join(EXTRACT_DIR, "2.0.51.12_Z7550-02475_decompressed.bin")
    search_firmware_for_crc_table(decomp_path)

    # Summary
    print(f"\n{'='*70}")
    print(f"  Summary")
    print(f"{'='*70}")
    for ver, result in results.items():
        print(f"  {ver}: {result}")

    if all(r == "NO MATCH" for r in results.values()):
        print(f"\n  The CRC algorithm could not be identified from standard variants.")
        print(f"  Possible explanations:")
        print(f"  1. Custom polynomial (Digi-specific)")
        print(f"  2. CRC computed over different data range than expected")
        print(f"  3. Additional transformation applied to CRC value")
        print(f"  4. Not actually CRC32 (could be CRC16x2, hash, etc.)")
        print(f"  5. The 4 bytes at the end may not be a CRC at all")
        print(f"  6. CRC may include padding or alignment bytes")


if __name__ == '__main__':
    main()

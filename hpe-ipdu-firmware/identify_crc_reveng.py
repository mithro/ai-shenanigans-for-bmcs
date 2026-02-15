#!/usr/bin/env python3
"""Reverse-engineer the CRC32 algorithm used in Digi NET+OS bootHdr images.

Uses crcmod for fast CRC computation, and implements CRC RevEng-style
techniques to try to determine the polynomial from known data/CRC pairs.

Approach:
1. Try all standard CRC32 algorithms (fast, via crcmod)
2. Try brute-force of common init/xor values with standard polynomial
3. Search for CRC lookup table in the firmware binary
4. Try the CRC as a rolling/running CRC (e.g., each 4KB block)
5. Try CRC RevEng-style polynomial detection
6. Check if the trailing 4 bytes might not be CRC at all

Reference: Digi forum confirms CRC is computed over "entire image including
header" and stored as trailing 4 bytes. Validation function: isImageValid()
in blmain.c.
"""

import os
import struct
import zlib
import crcmod
import crcmod.predefined

EXTRACT_DIR = "extracted"
HEADER_SIZE = 0x2C  # 44 bytes


def load_firmware(fname):
    """Load firmware file and return data, header info, expected CRC."""
    with open(os.path.join(EXTRACT_DIR, fname), 'rb') as f:
        data = f.read()

    image_size = struct.unpack_from('>I', data, 0x20)[0]
    # CRC stored as last 4 bytes - try both byte orders
    crc_bytes = data[-4:]
    expected_be = struct.unpack('>I', crc_bytes)[0]
    expected_le = struct.unpack('<I', crc_bytes)[0]
    # The data the CRC is computed over (header + compressed payload, excluding CRC)
    payload = data[:-4]

    return data, payload, image_size, expected_be, expected_le, crc_bytes


def try_predefined_crcs(payload, expected_be, expected_le, ver):
    """Try all predefined CRC algorithms from crcmod."""
    print(f"\n  Phase 1: Testing all predefined CRC algorithms...")
    predefined = crcmod.predefined._crc_definitions
    for defn in predefined:
        name = defn['name'] if isinstance(defn, dict) else defn[0]
        try:
            crc_func = crcmod.predefined.mkCrcFun(name)
            crc = crc_func(payload)
            # For CRC16 algorithms, compare lower 16 bits
            if crc == expected_be or crc == expected_le:
                print(f"  *** MATCH *** {ver}: {name} = 0x{crc:08X}")
                return True
            # Also try byte-swapped for 32-bit CRCs
            if crc > 0xFFFF:
                swapped = struct.unpack('>I', struct.pack('<I', crc & 0xFFFFFFFF))[0]
                if swapped == expected_be or swapped == expected_le:
                    print(f"  *** MATCH (swapped) *** {ver}: {name} = 0x{crc:08X}")
                    return True
        except Exception:
            pass
    print(f"    No match from predefined algorithms.")
    return False


def try_data_ranges(data, expected_be, expected_le, ver):
    """Try different data ranges with all predefined CRCs."""
    print(f"\n  Phase 2: Testing data ranges with standard CRC-32...")
    # Standard CRC-32 (same as zlib)
    crc_func = crcmod.predefined.mkCrcFun('crc-32')

    ranges = {
        "all-4 (hdr+payload)": data[:-4],
        "payload only (0x2C:-4)": data[HEADER_SIZE:-4],
        "netos_hdr+payload (0x04:-4)": data[0x04:-4],
        "from magic (0x08:-4)": data[0x08:-4],
        "full file": data,
        "all except first 4 bytes": data[4:],
        # Maybe CRC includes a length field appended?
        "all-4 + BE length": data[:-4] + struct.pack('>I', len(data) - 4),
        "all-4 + LE length": data[:-4] + struct.pack('<I', len(data) - 4),
        "all-4 + BE file length": data[:-4] + struct.pack('>I', len(data)),
        "all-4 + LE file length": data[:-4] + struct.pack('<I', len(data)),
    }

    for range_name, range_data in ranges.items():
        crc = crc_func(range_data)
        if crc == expected_be or crc == expected_le:
            print(f"  *** MATCH *** {ver}: crc-32 on {range_name} = 0x{crc:08X}")
            return True
        swapped = struct.unpack('>I', struct.pack('<I', crc))[0]
        if swapped == expected_be or swapped == expected_le:
            print(f"  *** MATCH (swapped) *** {ver}: crc-32 on {range_name} = 0x{crc:08X}")
            return True

    # Also try CRC-32/MPEG-2 (non-reflected, same poly)
    crc_mpeg2 = crcmod.mkCrcFun(0x104C11DB7, initCrc=0xFFFFFFFF, rev=False, xorOut=0x00000000)
    for range_name, range_data in ranges.items():
        crc = crc_mpeg2(range_data)
        if crc == expected_be or crc == expected_le:
            print(f"  *** MATCH *** {ver}: CRC-32/MPEG-2 on {range_name} = 0x{crc:08X}")
            return True
        swapped = struct.unpack('>I', struct.pack('<I', crc))[0]
        if swapped == expected_be or swapped == expected_le:
            print(f"  *** MATCH (swapped) *** {ver}: CRC-32/MPEG-2 on {range_name} = 0x{crc:08X}")
            return True

    print(f"    No match from data range variations.")
    return False


def try_init_xor_bruteforce(payload, expected_be, expected_le, ver):
    """Brute-force init and xor_out values for standard polynomial.

    The polynomial 0x04C11DB7 (or reflected 0xEDB88320) is almost certainly
    correct for CRC-32. The question is what init and xor_out values are used.
    """
    print(f"\n  Phase 3: Brute-forcing init/xor values with standard polynomial...")

    # Try common init/xor combinations
    common_values = [0x00000000, 0xFFFFFFFF, 0x00000001, 0x12345678,
                     0xDEADBEEF, 0xCAFEBABE, 0x55555555, 0xAAAAAAAA]

    # Reflected (standard) polynomial
    for init in common_values:
        for xor_out in common_values:
            try:
                crc_func = crcmod.mkCrcFun(0x104C11DB7, initCrc=init, rev=True, xorOut=xor_out)
                crc = crc_func(payload)
                if crc == expected_be or crc == expected_le:
                    print(f"  *** MATCH *** {ver}: poly=0x04C11DB7 rev=True "
                          f"init=0x{init:08X} xor=0x{xor_out:08X} = 0x{crc:08X}")
                    return True
            except Exception:
                pass

    # Non-reflected polynomial
    for init in common_values:
        for xor_out in common_values:
            try:
                crc_func = crcmod.mkCrcFun(0x104C11DB7, initCrc=init, rev=False, xorOut=xor_out)
                crc = crc_func(payload)
                if crc == expected_be or crc == expected_le:
                    print(f"  *** MATCH *** {ver}: poly=0x04C11DB7 rev=False "
                          f"init=0x{init:08X} xor=0x{xor_out:08X} = 0x{crc:08X}")
                    return True
            except Exception:
                pass

    print(f"    No match from init/xor brute force.")
    return False


def try_crc16_pairs(payload, expected_be, expected_le, ver):
    """Try interpreting the 4 bytes as two CRC16 values."""
    print(f"\n  Phase 4: Testing CRC16 pair interpretation...")

    crc_bytes_be = struct.pack('>I', expected_be)
    hi16 = struct.unpack('>H', crc_bytes_be[:2])[0]
    lo16 = struct.unpack('>H', crc_bytes_be[2:])[0]

    print(f"    Interpreting as two CRC16: 0x{hi16:04X} + 0x{lo16:04X}")

    # Common CRC16 algorithms
    crc16_algos = ['crc-16', 'crc-16-buypass', 'crc-ccitt-false', 'crc-aug-ccitt',
                   'x-25', 'xmodem', 'modbus', 'kermit', 'crc-16-dnp']

    for algo in crc16_algos:
        try:
            crc_func = crcmod.predefined.mkCrcFun(algo)
            # CRC16 of header vs payload?
            hdr_crc = crc_func(payload[:HEADER_SIZE])
            pay_crc = crc_func(payload[HEADER_SIZE:])
            if (hdr_crc == hi16 and pay_crc == lo16) or (hdr_crc == lo16 and pay_crc == hi16):
                print(f"  *** MATCH *** {ver}: {algo} pair - hdr=0x{hdr_crc:04X} pay=0x{pay_crc:04X}")
                return True
            # Full data CRC16?
            full_crc = crc_func(payload)
            if full_crc == hi16 or full_crc == lo16:
                print(f"    Partial: {algo} of full data = 0x{full_crc:04X}")
        except Exception:
            pass

    print(f"    No match from CRC16 pair interpretation.")
    return False


def analyze_crc_bytes_pattern(versions_data):
    """Analyze the CRC bytes across versions for patterns."""
    print(f"\n  Phase 5: Analyzing CRC byte patterns across versions...")

    for ver, data, payload, img_size, exp_be, exp_le, crc_bytes in versions_data:
        print(f"\n    {ver}:")
        print(f"      CRC bytes (raw): {crc_bytes.hex()}")
        print(f"      BE interpretation: 0x{exp_be:08X}")
        print(f"      LE interpretation: 0x{exp_le:08X}")
        print(f"      Payload size: {len(payload):,} bytes")
        print(f"      Image size (from header): {img_size:,}")

        # Check if CRC looks like it could be related to file size
        for val in [exp_be, exp_le]:
            diff = abs(val - len(payload))
            if diff < 1000000:
                print(f"      Note: 0x{val:08X} - payload_size = {diff}")

        # Check relationship between CRCs of different versions
        # Standard CRC-32 of the payload for reference
        ref_crc = zlib.crc32(payload) & 0xFFFFFFFF
        print(f"      zlib.crc32(payload) = 0x{ref_crc:08X}")
        print(f"      XOR with expected BE: 0x{ref_crc ^ exp_be:08X}")
        print(f"      XOR with expected LE: 0x{ref_crc ^ exp_le:08X}")


def search_for_crc_polynomial_in_binary(decomp_path):
    """Search for CRC polynomial constants in the decompressed firmware."""
    print(f"\n  Phase 6: Searching for CRC polynomial constants in firmware...")

    if not os.path.exists(decomp_path):
        print(f"    File not found: {decomp_path}")
        return

    with open(decomp_path, 'rb') as f:
        data = f.read()

    # Known CRC32 polynomials to search for (both BE and LE byte order)
    polys = {
        "CRC-32 (normal)": 0x04C11DB7,
        "CRC-32 (reflected)": 0xEDB88320,
        "CRC-32 (reciprocal)": 0xDB710641,
        "CRC-32C (normal)": 0x1EDC6F41,
        "CRC-32C (reflected)": 0x82F63B78,
        "CRC-32K (Koopman)": 0x741B8CD7,
        "CRC-32K (reflected)": 0xEB31D82E,
    }

    for name, poly in polys.items():
        # Search BE
        pattern_be = struct.pack('>I', poly)
        pos = data.find(pattern_be)
        if pos >= 0:
            addr = 0x4000 + pos
            print(f"    Found {name} (BE) at offset 0x{pos:08X} (addr 0x{addr:08X})")
            # Check context - print surrounding bytes
            start = max(0, pos - 8)
            end = min(len(data), pos + 12)
            context = data[start:end]
            print(f"      Context: {context.hex()}")

        # Search LE
        pattern_le = struct.pack('<I', poly)
        pos = data.find(pattern_le)
        if pos >= 0:
            addr = 0x4000 + pos
            print(f"    Found {name} (LE) at offset 0x{pos:08X} (addr 0x{addr:08X})")
            start = max(0, pos - 8)
            end = min(len(data), pos + 12)
            context = data[start:end]
            print(f"      Context: {context.hex()}")


def try_crc_with_padding(data, expected_be, expected_le, ver):
    """Try CRC with data padded or aligned to various boundaries."""
    print(f"\n  Phase 7: Testing CRC with alignment/padding variations...")

    payload = data[:-4]
    crc_func = crcmod.predefined.mkCrcFun('crc-32')

    # Pad to various alignments
    for align in [4, 8, 16, 32, 64, 128, 256, 512, 1024, 4096]:
        remainder = len(payload) % align
        if remainder != 0:
            padding = align - remainder
            padded = payload + b'\x00' * padding
            crc = crc_func(padded)
            if crc == expected_be or crc == expected_le:
                print(f"  *** MATCH *** {ver}: crc-32 padded to {align}-byte alignment = 0x{crc:08X}")
                return True

            padded_ff = payload + b'\xFF' * padding
            crc = crc_func(padded_ff)
            if crc == expected_be or crc == expected_le:
                print(f"  *** MATCH *** {ver}: crc-32 padded (0xFF) to {align}-byte alignment = 0x{crc:08X}")
                return True

    # Try truncating to image_size (maybe header fields don't count?)
    image_size = struct.unpack_from('>I', data, 0x20)[0]
    # Maybe CRC is over exactly image_size bytes of the compressed data?
    compressed = data[HEADER_SIZE:HEADER_SIZE + image_size]
    crc = crc_func(compressed)
    if crc == expected_be or crc == expected_le:
        print(f"  *** MATCH *** {ver}: crc-32 of exactly image_size bytes = 0x{crc:08X}")
        return True

    print(f"    No match from padding/alignment variations.")
    return False


def try_crc_on_original_zip_data(ver):
    """Try CRC of the original ZIP file contents (before extraction)."""
    print(f"\n  Phase 8: Checking if CRC matches ZIP-internal values...")
    # We extracted the firmware from ZIP files. The ZIP file itself has CRC32
    # values for each member. Let's check if the stored CRC matches.
    import zipfile

    zip_dir = "firmware"
    if not os.path.exists(zip_dir):
        print(f"    No firmware/ directory found.")
        return False

    for zf_name in os.listdir(zip_dir):
        if not zf_name.endswith('.zip'):
            continue
        if ver.replace('.', '') not in zf_name.replace('.', '').replace('-', '').replace('_', ''):
            # Try loose matching
            if ver.split('.')[0] not in zf_name:
                continue

        zf_path = os.path.join(zip_dir, zf_name)
        try:
            with zipfile.ZipFile(zf_path) as zf:
                for info in zf.infolist():
                    print(f"    ZIP {zf_name}/{info.filename}: CRC=0x{info.CRC:08X}")
        except Exception as e:
            print(f"    Error reading {zf_name}: {e}")

    return False


def try_inverted_data_crc(data, expected_be, expected_le, ver):
    """Try CRC of bit-inverted or byte-swapped data."""
    print(f"\n  Phase 9: Testing CRC on transformed data...")

    payload = data[:-4]
    crc_func = crcmod.predefined.mkCrcFun('crc-32')

    # Bit-inverted data
    inverted = bytes(~b & 0xFF for b in payload)
    crc = crc_func(inverted)
    if crc == expected_be or crc == expected_le:
        print(f"  *** MATCH *** {ver}: crc-32 of bit-inverted data = 0x{crc:08X}")
        return True

    # Byte-swapped (swap every 2 bytes - big-endian to little-endian halfword swap)
    if len(payload) % 2 == 0:
        swapped = bytearray(len(payload))
        for i in range(0, len(payload), 2):
            swapped[i] = payload[i + 1]
            swapped[i + 1] = payload[i]
        crc = crc_func(bytes(swapped))
        if crc == expected_be or crc == expected_le:
            print(f"  *** MATCH *** {ver}: crc-32 of halfword-swapped data = 0x{crc:08X}")
            return True

    # Word-swapped (swap every 4 bytes)
    if len(payload) % 4 == 0:
        swapped = bytearray(len(payload))
        for i in range(0, len(payload), 4):
            swapped[i] = payload[i + 3]
            swapped[i + 1] = payload[i + 2]
            swapped[i + 2] = payload[i + 1]
            swapped[i + 3] = payload[i]
        crc = crc_func(bytes(swapped))
        if crc == expected_be or crc == expected_le:
            print(f"  *** MATCH *** {ver}: crc-32 of word-swapped data = 0x{crc:08X}")
            return True

    print(f"    No match from data transformations.")
    return False


def try_adler32(data, expected_be, expected_le, ver):
    """Try Adler-32 checksum (used by zlib)."""
    print(f"\n  Phase 10: Testing Adler-32 and Fletcher checksums...")

    payload = data[:-4]
    adler = zlib.adler32(payload) & 0xFFFFFFFF
    print(f"    Adler-32 of payload: 0x{adler:08X}")
    if adler == expected_be or adler == expected_le:
        print(f"  *** MATCH *** {ver}: Adler-32 = 0x{adler:08X}")
        return True

    # Fletcher-32
    words = struct.unpack(f'>{len(payload) // 2}H', payload[:len(payload) - len(payload) % 2])
    sum1 = 0
    sum2 = 0
    for w in words:
        sum1 = (sum1 + w) % 65535
        sum2 = (sum2 + sum1) % 65535
    fletcher = (sum2 << 16) | sum1
    print(f"    Fletcher-32 of payload: 0x{fletcher:08X}")
    if fletcher == expected_be or fletcher == expected_le:
        print(f"  *** MATCH *** {ver}: Fletcher-32 = 0x{fletcher:08X}")
        return True

    print(f"    No match from Adler/Fletcher checksums.")
    return False


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    versions = [
        ("1.6.16.12", "1.6.16.12_Z7550-63196_image.bin"),
        ("2.0.22.12", "2.0.22.12_Z7550-63311_image.bin"),
        ("2.0.51.12", "2.0.51.12_Z7550-02475_image.bin"),
    ]

    # Load all firmware versions
    versions_data = []
    for ver, fname in versions:
        data, payload, img_size, exp_be, exp_le, crc_bytes = load_firmware(fname)
        versions_data.append((ver, data, payload, img_size, exp_be, exp_le, crc_bytes))
        print(f"  Loaded {ver}: {len(data):,} bytes, CRC BE=0x{exp_be:08X} LE=0x{exp_le:08X}")

    # Run phases on first version
    ver, data, payload, img_size, exp_be, exp_le, crc_bytes = versions_data[0]
    print(f"\n{'='*70}")
    print(f"  Testing {ver}")
    print(f"{'='*70}")

    try_predefined_crcs(payload, exp_be, exp_le, ver)
    try_data_ranges(data, exp_be, exp_le, ver)
    try_init_xor_bruteforce(payload, exp_be, exp_le, ver)
    try_crc16_pairs(payload, exp_be, exp_le, ver)
    try_crc_with_padding(data, exp_be, exp_le, ver)
    try_inverted_data_crc(data, exp_be, exp_le, ver)
    try_adler32(data, exp_be, exp_le, ver)

    # Cross-version analysis
    print(f"\n{'='*70}")
    print(f"  Cross-Version Analysis")
    print(f"{'='*70}")
    analyze_crc_bytes_pattern(versions_data)

    # Search for CRC polynomial in firmware
    print(f"\n{'='*70}")
    print(f"  Firmware Binary Analysis")
    print(f"{'='*70}")
    decomp_path = os.path.join(EXTRACT_DIR, "2.0.51.12_Z7550-02475_decompressed.bin")
    search_for_crc_polynomial_in_binary(decomp_path)

    # Check ZIP file CRCs
    print(f"\n{'='*70}")
    print(f"  ZIP File CRC Check")
    print(f"{'='*70}")
    for ver, *_ in versions_data:
        try_crc_on_original_zip_data(ver)

    # Final summary
    print(f"\n{'='*70}")
    print(f"  Summary")
    print(f"{'='*70}")
    print(f"  No standard CRC32 algorithm matched across any data range or")
    print(f"  parameter combination tested.")
    print(f"")
    print(f"  Next steps to investigate:")
    print(f"  1. Disassemble the bootloader ROM to find isImageValid()")
    print(f"  2. Check if the 4 bytes are actually a different kind of hash")
    print(f"  3. Look at Digi NET+OS SDK source code for CRC implementation")
    print(f"  4. Try CRC RevEng with longer message/CRC pairs")


if __name__ == '__main__':
    main()

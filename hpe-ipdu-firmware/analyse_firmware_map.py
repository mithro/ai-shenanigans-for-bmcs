#!/usr/bin/env python3
"""Create a high-level binary layout map of the HPE iPDU firmware.

Analyses the decompressed firmware to identify:
1. Code vs data regions (ARM instruction density)
2. String table regions
3. Web content regions (HTML, CSS, JS, images)
4. Known function locations from previous analysis
5. Binary format markers (GIF, PNG, JPEG headers)
"""

import os
import struct
from collections import Counter

EXTRACT_DIR = "extracted"
RAM_BASE = 0x00004000
BLOCK_SIZE = 4096  # Analyse in 4KB blocks


def classify_word(val):
    """Classify a 32-bit big-endian word."""
    cond = (val >> 28) & 0xF
    opclass = (val >> 24) & 0xF

    # ARM instruction: condition field is 0-E (not 0xF which is unconditional extension)
    if cond <= 0xE:
        # Data processing, branch, load/store, etc.
        return 'arm'

    return 'data'


def analyse_block(data, offset, size):
    """Analyse a block of firmware data and classify it."""
    block = data[offset:offset + size]
    if len(block) < size:
        return 'short', {}

    # Count ARM-looking instructions
    arm_count = 0
    data_count = 0
    zero_count = 0
    printable_count = 0

    for i in range(0, len(block) - 3, 4):
        val = struct.unpack_from('>I', block, i)[0]
        if val == 0:
            zero_count += 1
        elif classify_word(val) == 'arm':
            arm_count += 1
        else:
            data_count += 1

    # Count printable ASCII bytes
    for b in block:
        if 0x20 <= b < 0x7F or b in (0x0A, 0x0D, 0x09):
            printable_count += 1

    total_words = size // 4
    arm_pct = (arm_count / total_words * 100) if total_words > 0 else 0
    text_pct = (printable_count / size * 100) if size > 0 else 0
    zero_pct = (zero_count / total_words * 100) if total_words > 0 else 0

    # Check for binary content markers
    has_gif = b'GIF8' in block
    has_png = b'\x89PNG' in block
    has_jpg = b'\xff\xd8\xff' in block
    has_html = b'<html' in block or b'<HTML' in block or b'<!DOCTYPE' in block
    has_js = b'function(' in block or b'var ' in block

    if has_gif or has_png or has_jpg:
        return 'image', {'arm_pct': arm_pct, 'text_pct': text_pct}
    elif has_html:
        return 'html', {'arm_pct': arm_pct, 'text_pct': text_pct}
    elif has_js and text_pct > 60:
        return 'javascript', {'arm_pct': arm_pct, 'text_pct': text_pct}
    elif text_pct > 70:
        return 'text/strings', {'arm_pct': arm_pct, 'text_pct': text_pct}
    elif arm_pct > 60:
        return 'code', {'arm_pct': arm_pct, 'text_pct': text_pct}
    elif zero_pct > 80:
        return 'zeroes/padding', {'arm_pct': arm_pct, 'text_pct': text_pct, 'zero_pct': zero_pct}
    elif arm_pct > 30:
        return 'code+data', {'arm_pct': arm_pct, 'text_pct': text_pct}
    else:
        return 'data', {'arm_pct': arm_pct, 'text_pct': text_pct}


def find_known_landmarks(data):
    """Find known function and data landmarks from previous analysis."""
    landmarks = {}

    # Boot/init region
    landmarks[0x00004000] = "ARM reset vector table"
    landmarks[0x000B7F64] = "Reset handler (CP15 setup)"
    landmarks[0x000A817C] = "BSP system init"
    landmarks[0x000A81A8] = "BSP peripheral init"
    landmarks[0x000A86CC] = "BSP GPIO/serial init"
    landmarks[0x000A97CC] = "GPIO init cluster 1 (literal pool)"
    landmarks[0x000AA00C] = "GPIO init cluster 2 (literal pool)"

    # Serial/I2C drivers
    landmarks[0x000ACC3C] = "Port B config (literal pool)"
    landmarks[0x000B12EC] = "I2C Master Address driver"
    landmarks[0x000B20D0] = "I2C Slave Address driver"
    landmarks[0x000BAB48] = "I2C Slave Address driver 2"

    # GPIO init cluster 3-4
    landmarks[0x0029B07C] = "GPIO init cluster 3"
    landmarks[0x0029B378] = "GPIO init cluster 4"

    # Known string regions
    landmarks[0x0069C968] = "CLI command table start region"
    landmarks[0x0069EDD8] = "Firmware module names"
    landmarks[0x0069EE54] = "Display Module name string"
    landmarks[0x006A0FD4] = "I2C Bus debug string"

    # SPI error strings
    landmarks[0x00721D8C] = "SPI DMA error strings"
    landmarks[0x007305CC] = "SPI slave DMA error strings"

    # Peripheral map table
    landmarks[0x00757114] = "NS9360 peripheral address map"

    # Search for specific byte patterns
    # ThreadX signature
    pos = data.find(b'ThreadX')
    if pos >= 0:
        landmarks[pos + RAM_BASE] = "ThreadX RTOS strings"

    # RomPager signature
    pos = data.find(b'RomPager')
    if pos >= 0:
        landmarks[pos + RAM_BASE] = "RomPager web server strings"

    # OpenSSL
    pos = data.find(b'OpenSSL 0.9.7b')
    if pos >= 0:
        landmarks[pos + RAM_BASE] = "OpenSSL 0.9.7b strings"

    # YAFFS
    pos = data.find(b'yaffs')
    if pos >= 0:
        landmarks[pos + RAM_BASE] = "YAFFS filesystem strings"

    # KLone
    pos = data.find(b'klone')
    if pos >= 0:
        landmarks[pos + RAM_BASE] = "KLone web framework strings"

    # NET+OS
    pos = data.find(b'NET+OS')
    if pos >= 0:
        landmarks[pos + RAM_BASE] = "NET+OS RTOS strings"

    return landmarks


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    decomp_path = os.path.join(EXTRACT_DIR, "2.0.51.12_Z7550-02475_decompressed.bin")
    if not os.path.exists(decomp_path):
        print(f"ERROR: {decomp_path} not found")
        return

    with open(decomp_path, 'rb') as f:
        data = f.read()

    total_size = len(data)
    num_blocks = (total_size + BLOCK_SIZE - 1) // BLOCK_SIZE
    print(f"  Loaded firmware: {total_size:,} bytes ({total_size / 1024 / 1024:.1f} MB)")
    print(f"  Block size: {BLOCK_SIZE:,} bytes, {num_blocks} blocks")

    landmarks = find_known_landmarks(data)

    # Classify each block
    blocks = []
    for i in range(num_blocks):
        offset = i * BLOCK_SIZE
        mem_addr = offset + RAM_BASE
        block_type, stats = analyse_block(data, offset, BLOCK_SIZE)
        blocks.append((mem_addr, block_type, stats))

    # Merge consecutive blocks of same type into regions
    regions = []
    if blocks:
        current_type = blocks[0][1]
        region_start = blocks[0][0]
        region_blocks = 1

        for i in range(1, len(blocks)):
            if blocks[i][1] == current_type:
                region_blocks += 1
            else:
                regions.append((region_start, region_blocks * BLOCK_SIZE, current_type))
                current_type = blocks[i][1]
                region_start = blocks[i][0]
                region_blocks = 1
        regions.append((region_start, region_blocks * BLOCK_SIZE, current_type))

    print(f"\n{'='*80}")
    print(f"  Firmware Binary Layout Map")
    print(f"{'='*80}")
    print(f"  {'Start':>12s}  {'End':>12s}  {'Size':>10s}  {'Type':<20s}  Landmarks")
    print(f"  {'-'*12}  {'-'*12}  {'-'*10}  {'-'*20}  {'-'*30}")

    for start, size, rtype in regions:
        end = start + size - 1
        size_str = f"{size / 1024:.0f} KB" if size >= 1024 else f"{size} B"

        # Find landmarks in this region
        region_landmarks = []
        for addr, desc in sorted(landmarks.items()):
            if start <= addr <= end:
                region_landmarks.append(f"0x{addr:08X}: {desc}")

        landmark_str = region_landmarks[0] if region_landmarks else ""
        print(f"  0x{start:08X}  0x{end:08X}  {size_str:>10s}  {rtype:<20s}  {landmark_str}")

        for lm in region_landmarks[1:]:
            print(f"  {' ':12s}  {' ':12s}  {' ':10s}  {' ':20s}  {lm}")

    # Summary statistics
    type_sizes = Counter()
    for _, size, rtype in regions:
        type_sizes[rtype] += size

    print(f"\n{'='*80}")
    print(f"  Region Type Summary")
    print(f"{'='*80}")
    for rtype, size in type_sizes.most_common():
        pct = size / total_size * 100
        print(f"  {rtype:<20s}  {size:>10,} bytes  ({pct:5.1f}%)")
    print(f"  {'TOTAL':<20s}  {total_size:>10,} bytes  (100.0%)")


if __name__ == '__main__':
    main()

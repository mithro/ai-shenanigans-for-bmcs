#!/usr/bin/env python3
"""Disassemble the firmware payload to find decompression code.

The payload appears to start with big-endian ARM code followed by
compressed data. This script:
1. Extracts the payload
2. Disassembles it as big-endian ARM
3. Identifies where code ends and compressed data begins
4. Looks for decompression routines
"""

import os
import struct
import subprocess
import sys
import tempfile

EXTRACT_DIR = "extracted"


def find_code_end(data: bytes) -> int:
    """Find where ARM code ends and data/compressed section begins.

    Uses a sliding window entropy analysis.
    """
    import math
    from collections import Counter

    window = 256
    threshold = 7.0  # Entropy above this is likely compressed
    for offset in range(0, len(data) - window, 64):
        chunk = data[offset:offset + window]
        counts = Counter(chunk)
        entropy = -sum((c / window) * math.log2(c / window) for c in counts.values())
        if entropy > threshold:
            return offset
    return len(data)


def disassemble_be_arm(data: bytes, base_addr: int = 0, max_bytes: int = None) -> str:
    """Disassemble big-endian ARM code using objdump."""
    if max_bytes:
        data = data[:max_bytes]

    # Write raw binary
    bin_path = os.path.join(EXTRACT_DIR, "payload_be.bin")
    with open(bin_path, 'wb') as f:
        f.write(data)

    # Use objdump to disassemble as big-endian ARM
    cmd = [
        "arm-linux-gnueabi-objdump",
        "-D",
        "-b", "binary",
        "-m", "arm",
        "-EB",  # Big-endian
        "--adjust-vma", hex(base_addr),
        bin_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"objdump failed: {result.stderr}")
        return ""
    return result.stdout


def analyse_disassembly(disasm: str):
    """Analyse the disassembly for interesting patterns."""
    lines = disasm.split('\n')

    # Find function-like patterns (common prologues)
    print("\n  Function prologues (STMFD/PUSH):")
    count = 0
    for line in lines:
        if 'stmdb' in line or 'push' in line or 'stmfd' in line:
            if count < 30:
                print(f"    {line.strip()}")
            count += 1
    print(f"    ... ({count} total)")

    # Find LDR PC (jump tables / indirect branches)
    print("\n  LDR PC (indirect jumps/returns):")
    count = 0
    for line in lines:
        if 'ldr' in line and 'pc' in line.split('\t')[-1] if '\t' in line else '':
            if count < 20:
                print(f"    {line.strip()}")
            count += 1
    print(f"    ... ({count} total)")

    # Find SWI/SVC calls
    print("\n  SWI/SVC calls:")
    count = 0
    for line in lines:
        if 'svc' in line or 'swi' in line:
            if count < 20:
                print(f"    {line.strip()}")
            count += 1
    print(f"    ... ({count} total)")

    # Find references to known register addresses
    print("\n  References to BBus (0x9060xxxx GPIO config):")
    count = 0
    for line in lines:
        if '0x9060' in line or '0x90600' in line:
            if count < 20:
                print(f"    {line.strip()}")
            count += 1
    print(f"    ... ({count} total)")

    # Find string references (common pattern: ADR or LDR from literal pool)
    # Look for 'ldr' instructions with PC-relative addresses in code range
    print("\n  Key instructions (first 50 BL calls):")
    count = 0
    for line in lines:
        if '\tbl\t' in line or '\tbl ' in line:
            if count < 50:
                print(f"    {line.strip()}")
            count += 1
    print(f"    ... ({count} total BL calls)")

    # Look for decompression-related patterns
    # Typical decompressor: loop with byte reads, back-references
    print("\n  Searching for decompression patterns:")
    print("  (LDRB + CMP + branch loops)")
    # Find tight loops with LDRB
    ldrb_lines = []
    for i, line in enumerate(lines):
        if 'ldrb' in line:
            # Check nearby lines for CMP and branch
            context = lines[max(0,i-5):min(len(lines),i+10)]
            has_cmp = any('cmp' in l for l in context)
            has_branch = any(any(br in l for br in ['\tb ', '\tbne', '\tbeq', '\tbhi', '\tbls', '\tbcc', '\tbcs']) for l in context)
            if has_cmp and has_branch:
                ldrb_lines.append((i, line.strip()))

    if ldrb_lines:
        print(f"  Found {len(ldrb_lines)} LDRB+CMP+branch patterns:")
        for idx, line in ldrb_lines[:15]:
            print(f"    line {idx}: {line}")
    else:
        print("  None found")


def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))

    # Use the newest firmware
    fw_path = os.path.join(EXTRACT_DIR, "2.0.51.12_Z7550-02475_image.bin")
    with open(fw_path, 'rb') as f:
        data = f.read()

    print(f"Firmware: {fw_path} ({len(data)} bytes)")

    # The header is 48 bytes (0x30), but first check if 0x2C (44) is the header
    # [0x00] BE = 0x2C suggests header might end at 0x2C
    # But [0x20] BE = payload_size = file_size - 0x30

    # Check both possibilities
    header_end_30 = data[0x30:]
    header_end_2c = data[0x2C:]

    print(f"\nHeader size analysis:")
    print(f"  [0x00] BE = 0x{struct.unpack_from('>I', data, 0)[0]:08X} = {struct.unpack_from('>I', data, 0)[0]}")
    print(f"  [0x20] BE = 0x{struct.unpack_from('>I', data, 0x20)[0]:08X} = {struct.unpack_from('>I', data, 0x20)[0]}")
    print(f"  file_size = {len(data)}")
    print(f"  file_size - 0x2C = {len(data) - 0x2C}")
    print(f"  file_size - 0x30 = {len(data) - 0x30}")
    payload_size = struct.unpack_from('>I', data, 0x20)[0]
    print(f"  [0x20] matches file_size - 0x30: {payload_size == len(data) - 0x30}")
    print(f"  [0x20] matches file_size - 0x2C: {payload_size == len(data) - 0x2C}")

    # Use 0x2C as payload start (since [0x00] says 0x2C)
    # But verify against [0x20] which says payload_size = file_size - 0x30
    # This means:
    # - Header is 0x30 bytes (48)
    # - [0x00] = 0x2C might mean something else (maybe size of header fields excluding first 4 bytes?)

    # Actually, let me check: what if [0x00] is the offset to the actual DATA
    # (as opposed to the segment table), and the segment table is between
    # the end of the bootHdr and the data?
    # No wait, [0x00]=0x2C is before the end of the header (0x30).

    # Let's just try both payload offsets
    for payload_offset in [0x2C, 0x30]:
        payload = data[payload_offset:]

        # Find where code ends
        code_end = find_code_end(payload)
        print(f"\n{'='*70}")
        print(f"  Payload from 0x{payload_offset:02X}: code ends at ~0x{code_end:X} "
              f"(file offset 0x{payload_offset + code_end:X})")
        print(f"  Code region: {code_end} bytes")
        print(f"{'='*70}")

        if code_end < 64:
            print(f"  Code too short, likely wrong offset")
            continue

        # Disassemble first portion
        max_disasm = min(code_end + 512, 8192)  # Some extra past the boundary
        print(f"\n  Disassembling first {max_disasm} bytes as big-endian ARM:")
        disasm = disassemble_be_arm(payload, base_addr=payload_offset, max_bytes=max_disasm)

        if not disasm:
            continue

        # Save full disassembly
        disasm_path = os.path.join(EXTRACT_DIR, f"payload_0x{payload_offset:02X}_disasm.txt")
        with open(disasm_path, 'w') as f:
            f.write(disasm)
        print(f"  Saved to {disasm_path}")

        # Show first 100 lines
        lines = disasm.split('\n')
        print(f"\n  First 100 instructions:")
        count = 0
        for line in lines:
            if '\t' in line and ':' in line:
                print(f"    {line.strip()}")
                count += 1
                if count >= 100:
                    break

        # Analyse the disassembly
        analyse_disassembly(disasm)

    # Also try little-endian for comparison
    print(f"\n{'='*70}")
    print(f"  LITTLE-ENDIAN CHECK (first 32 instructions from 0x2C)")
    print(f"{'='*70}")
    payload = data[0x2C:]
    bin_path = os.path.join(EXTRACT_DIR, "payload_le.bin")
    with open(bin_path, 'wb') as f:
        f.write(payload[:256])

    cmd = [
        "arm-linux-gnueabi-objdump",
        "-D",
        "-b", "binary",
        "-m", "arm",
        "-EL",
        "--adjust-vma", "0x2c",
        bin_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        lines = result.stdout.split('\n')
        count = 0
        for line in lines:
            if '\t' in line and ':' in line:
                print(f"    {line.strip()}")
                count += 1
                if count >= 32:
                    break


if __name__ == '__main__':
    main()

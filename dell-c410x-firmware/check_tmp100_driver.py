#!/usr/bin/env python3
"""Analyze the TMP100 IOSAPI driver in fullfw to determine actual I2C address.

The TMP100 IOSAPI driver vtable is at address 0x000FCBFC in the fullfw binary.
We need to find the actual function code and look for I2C address usage.
"""

import os
import struct
import re

FULLFW = "extracted/rootfs/sbin/fullfw"


def find_elf_load_offset(data):
    """Find the offset between file offset and virtual address for the ELF."""
    # ELF header
    if data[:4] != b'\x7fELF':
        print("  Not an ELF file!")
        return None

    # Parse ELF header
    ei_class = data[4]  # 1 = 32-bit
    ei_data = data[5]   # 1 = little-endian
    e_type = struct.unpack_from('<H', data, 16)[0]
    e_machine = struct.unpack_from('<H', data, 18)[0]
    e_entry = struct.unpack_from('<I', data, 24)[0]
    e_phoff = struct.unpack_from('<I', data, 28)[0]
    e_phentsize = struct.unpack_from('<H', data, 42)[0]
    e_phnum = struct.unpack_from('<H', data, 44)[0]

    print(f"  ELF: class={ei_class} endian={ei_data} type={e_type} machine={e_machine}")
    print(f"  Entry: 0x{e_entry:08X}")
    print(f"  Program headers: {e_phnum} entries of {e_phentsize} bytes at offset {e_phoff}")

    # Parse program headers to find LOAD segments
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        p_offset = struct.unpack_from('<I', data, off + 4)[0]
        p_vaddr = struct.unpack_from('<I', data, off + 8)[0]
        p_filesz = struct.unpack_from('<I', data, off + 16)[0]
        p_memsz = struct.unpack_from('<I', data, off + 20)[0]

        type_names = {0: "NULL", 1: "LOAD", 2: "DYNAMIC", 3: "INTERP",
                      4: "NOTE", 6: "PHDR", 7: "TLS"}
        type_name = type_names.get(p_type, f"0x{p_type:X}")

        if p_type == 1:  # LOAD
            print(f"  LOAD segment: file_offset=0x{p_offset:08X} vaddr=0x{p_vaddr:08X} "
                  f"filesz=0x{p_filesz:08X} memsz=0x{p_memsz:08X}")

    # Return the first LOAD segment's offset mapping
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        if p_type == 1:  # LOAD
            p_offset = struct.unpack_from('<I', data, off + 4)[0]
            p_vaddr = struct.unpack_from('<I', data, off + 8)[0]
            return (p_vaddr, p_offset)

    return None


def vaddr_to_file_offset(vaddr, segments):
    """Convert virtual address to file offset."""
    for seg_vaddr, seg_offset, seg_filesz in segments:
        if seg_vaddr <= vaddr < seg_vaddr + seg_filesz:
            return vaddr - seg_vaddr + seg_offset
    return None


def analyze_tmp100_driver(data, segments):
    """Find and analyze the TMP100 IOSAPI driver code."""
    # The TMP100 IOSAPI driver vtable is at virtual address 0x000FCBFC
    vtable_vaddr = 0x000FCBFC
    vtable_foff = vaddr_to_file_offset(vtable_vaddr, segments)

    if vtable_foff is None:
        print(f"  Cannot map vtable address 0x{vtable_vaddr:08X} to file offset")
        return

    print(f"\n  TMP100 IOSAPI vtable at vaddr 0x{vtable_vaddr:08X}, file offset 0x{vtable_foff:08X}")

    # IOSAPI vtable typically has function pointers for init, read, write, close
    # Each is a 32-bit ARM address
    print("  Vtable entries:")
    for i in range(8):
        if vtable_foff + i * 4 + 4 <= len(data):
            func_addr = struct.unpack_from('<I', data, vtable_foff + i * 4)[0]
            print(f"    [{i}] 0x{func_addr:08X}")

    # Now look at the actual function code
    # The "read" function (typically entry [1] or [2]) is what performs the I2C transaction
    for entry_idx in range(4):
        func_vaddr = struct.unpack_from('<I', data, vtable_foff + entry_idx * 4)[0]
        func_foff = vaddr_to_file_offset(func_vaddr, segments)
        if func_foff is None:
            continue

        print(f"\n  Analyzing vtable entry [{entry_idx}] at 0x{func_vaddr:08X}:")

        # Read function code (up to 512 bytes)
        code_size = min(512, len(data) - func_foff)
        code = data[func_foff:func_foff + code_size]

        # Search for I2C address-related patterns in the ARM code
        # Look for immediate values that could be I2C addresses
        # In ARM, small immediate values are loaded via MOV or embedded in LDR
        for j in range(0, len(code) - 3, 4):
            instr = struct.unpack_from('<I', code, j)[0]

            # Check for MOV Rn, #imm (ARM encoding)
            # MOV: cond 0011101S 0000 Rd rotate8 imm8
            if (instr & 0x0FEF0000) == 0x03A00000:
                rd = (instr >> 12) & 0xF
                imm8 = instr & 0xFF
                rotate = (instr >> 8) & 0xF
                imm = (imm8 >> (rotate * 2)) | (imm8 << (32 - rotate * 2)) if rotate else imm8
                imm &= 0xFFFFFFFF
                if imm in (0x5C, 0xB8, 0x2E, 0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F,
                           0x90, 0x92, 0x94, 0x96, 0x98, 0x9A, 0x9C, 0x9E):
                    print(f"    +0x{j:03X}: MOV R{rd}, #0x{imm:02X}  (potential I2C address)")


def search_for_i2c_addresses(data, segments):
    """Search for specific I2C address patterns near TMP100 code."""
    print("\n  Searching fullfw for TMP100/LM75-related I2C addresses...")

    # The TMP100 read function likely calls PI2CMuxWriteRead() which takes the
    # device address as a parameter. Let's search for the address 0x5C, 0xB8,
    # 0x2E, or standard TMP100 addresses near the driver code area.

    # First, find where the TMP100 IOSAPI driver functions are located
    vtable_vaddr = 0x000FCBFC
    vtable_foff = vaddr_to_file_offset(vtable_vaddr, segments)
    if vtable_foff is None:
        return

    # Get function addresses from vtable
    func_addrs = []
    for i in range(4):
        addr = struct.unpack_from('<I', data, vtable_foff + i * 4)[0]
        func_addrs.append(addr)

    # Check a broader area around the TMP100 driver
    # Also check the PCA9548 driver area for mux addresses
    pca9548_vtable_vaddr = 0x000FCBFC + 0x20  # Approximate

    # Search for byte sequence 0x5C in context of I2C transactions
    # In ARM code, the address would be loaded as an immediate or from memory
    target_area_start = vaddr_to_file_offset(0x000FC000, segments)
    target_area_end = vaddr_to_file_offset(0x000FD000, segments)
    if target_area_start and target_area_end:
        area = data[target_area_start:target_area_end]
        print(f"  Scanning driver area 0x000FC000-0x000FD000 ({len(area)} bytes):")

        # Look for the byte 0x5C in this area
        pos = 0
        count_5c = 0
        while True:
            pos = area.find(b'\x5c', pos)
            if pos == -1:
                break
            # Show context
            if count_5c < 5:
                ctx_start = max(0, pos - 4)
                ctx_end = min(len(area), pos + 8)
                ctx = area[ctx_start:ctx_end]
                ctx_hex = ' '.join(f'{b:02X}' for b in ctx)
                vaddr = 0x000FC000 + pos
                print(f"    0x{vaddr:08X}: ...{ctx_hex}... (byte 0x5C at offset +{pos-ctx_start})")
            count_5c += 1
            pos += 1
        print(f"    Total occurrences of 0x5C: {count_5c}")

        # Also look for 0xB8 (which would be 0x5C as 8-bit write address)
        pos = 0
        count_b8 = 0
        while True:
            pos = area.find(b'\xb8', pos)
            if pos == -1:
                break
            count_b8 += 1
            pos += 1
        print(f"    Total occurrences of 0xB8: {count_b8}")

    # Also search for PCA9548 mux addresses
    # PCA9548 at 7-bit 0x70: 8-bit = 0xE0
    # PCA9548 at 7-bit 0x71: 8-bit = 0xE2
    print(f"\n  PCA9548 mux address search in full binary:")
    for search_byte, desc in [(0xE0, "PCA9548 @0x70 8-bit"),
                              (0xE2, "PCA9548 @0x71 8-bit"),
                              (0x70, "PCA9548 @0x70 7-bit"),
                              (0x71, "PCA9548 @0x71 7-bit")]:
        count = data.count(bytes([search_byte]))
        # Too many false positives for single-byte search, but let's check
        # in a more targeted area
        if target_area_start and target_area_end:
            area_count = area.count(bytes([search_byte]))
            print(f"    0x{search_byte:02X} ({desc}): {area_count} in driver area, {count} in full binary")


def search_for_string_refs(data):
    """Search for TMP100-related strings that might reveal the address."""
    print("\n  Searching for TMP100/temperature-related strings:")
    for pattern in [b'TMP100', b'TMP75', b'LM75', b'tmp100', b'tmp75', b'lm75',
                    b'I2CTEMP', b'i2ctemp', b'MuxWriteRead']:
        pos = data.find(pattern)
        while pos != -1:
            # Get surrounding context
            start = max(0, pos - 16)
            end = min(len(data), pos + len(pattern) + 32)
            ctx = data[start:end]
            printable = ''.join(chr(b) if 32 <= b < 127 else '.' for b in ctx)
            print(f"    '{pattern.decode()}' at 0x{pos:08X}: {printable}")
            pos = data.find(pattern, pos + 1)
            if pos != -1 and pos < data.find(pattern, pos - 1) + 100:
                continue  # Skip close duplicates
            break


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    with open(FULLFW, 'rb') as f:
        data = f.read()

    print(f"fullfw: {len(data)} bytes")

    # Parse ELF to find segment mapping
    result = find_elf_load_offset(data)
    if result is None:
        return

    # Build segment table
    e_phoff = struct.unpack_from('<I', data, 28)[0]
    e_phentsize = struct.unpack_from('<H', data, 42)[0]
    e_phnum = struct.unpack_from('<H', data, 44)[0]

    segments = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        if p_type == 1:  # LOAD
            p_offset = struct.unpack_from('<I', data, off + 4)[0]
            p_vaddr = struct.unpack_from('<I', data, off + 8)[0]
            p_filesz = struct.unpack_from('<I', data, off + 16)[0]
            segments.append((p_vaddr, p_offset, p_filesz))

    analyze_tmp100_driver(data, segments)
    search_for_i2c_addresses(data, segments)
    search_for_string_refs(data)


if __name__ == '__main__':
    main()

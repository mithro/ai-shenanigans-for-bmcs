#!/usr/bin/env python3
"""Analyse NVRAM/configuration storage format in HPE iPDU firmware.

Searches the decompressed firmware for:
1. YAFFS filesystem structures and references
2. NOR Flash sector layout and erase/write operations
3. Configuration key-value storage patterns
4. NVRAM-related function strings
5. Flash memory map and partition table
6. config.bin format clues
"""

import os
import struct
import re

EXTRACT_DIR = "extracted"
# NS9360 static memory chip selects (NOR Flash)
FLASH_CS0 = 0x40000000  # CS0 - likely first 8MB NOR
FLASH_CS1 = 0x50000000  # CS1 - likely second 8MB NOR
RAM_BASE = 0x00004000   # Decompressed firmware load address


def find_strings(data, min_length=6):
    """Find all printable ASCII strings in binary data."""
    strings = []
    current = b""
    start = 0
    for i, byte in enumerate(data):
        if 0x20 <= byte < 0x7F:
            if not current:
                start = i
            current += bytes([byte])
        else:
            if len(current) >= min_length:
                strings.append((start, current.decode('ascii')))
            current = b""
    if len(current) >= min_length:
        strings.append((start, current.decode('ascii')))
    return strings


def search_nvram_strings(data):
    """Search for NVRAM/config/flash-related strings."""
    print("\n  Searching for NVRAM/config-related strings...")

    patterns = [
        r'nvram', r'NVRAM', r'nv[_ ]ram',
        r'flash', r'Flash', r'FLASH',
        r'config', r'Config', r'CONFIG',
        r'yaffs', r'YAFFS', r'Yaffs',
        r'partition', r'Partition',
        r'erase', r'Erase',
        r'sector', r'Sector',
        r'nand', r'NAND', r'nor', r'NOR',
        r'save.*config', r'load.*config',
        r'factory.*default', r'Factory.*Default',
        r'backup', r'Backup',
        r'restore', r'Restore',
        r'persist', r'Persist',
        r'storage', r'Storage',
        r'setting', r'Setting',
    ]

    all_strings = find_strings(data, min_length=4)

    found = {}
    for offset, s in all_strings:
        for pattern in patterns:
            if re.search(pattern, s, re.IGNORECASE):
                key = pattern.lower().replace(r'.*', ' ')
                if key not in found:
                    found[key] = []
                found[key].append((offset, s))
                break

    for key in sorted(found.keys()):
        matches = found[key]
        print(f"\n    [{key}] ({len(matches)} matches):")
        # Show unique strings with their first occurrence
        seen = set()
        for offset, s in matches:
            if s not in seen:
                addr = RAM_BASE + offset
                print(f"      0x{addr:08X}: {s[:120]}")
                seen.add(s)
                if len(seen) >= 30:
                    remaining = len([m for m in matches if m[1] not in seen])
                    if remaining > 0:
                        print(f"      ... and {remaining} more unique strings")
                    break


def search_flash_addresses(data):
    """Search for NOR Flash address references (CS0: 0x4000xxxx, CS1: 0x5000xxxx)."""
    print("\n  Searching for NOR Flash address references...")

    # Look for flash address patterns in big-endian
    flash_refs = {}
    for i in range(0, len(data) - 3, 4):
        word = struct.unpack_from('>I', data, i)[0]
        # CS0: 0x40000000 - 0x40FFFFFF (first 16MB of CS0)
        if 0x40000000 <= word <= 0x40FFFFFF:
            sector = (word - 0x40000000) >> 16  # 64KB sectors
            key = f"CS0:0x{word:08X}"
            if key not in flash_refs:
                flash_refs[key] = []
            flash_refs[key].append(i)
        # CS1: 0x50000000 - 0x50FFFFFF
        elif 0x50000000 <= word <= 0x50FFFFFF:
            sector = (word - 0x50000000) >> 16
            key = f"CS1:0x{word:08X}"
            if key not in flash_refs:
                flash_refs[key] = []
            flash_refs[key].append(i)

    if not flash_refs:
        print("    No NOR Flash address references found.")
        return

    # Group by memory region
    cs0_refs = {k: v for k, v in flash_refs.items() if k.startswith("CS0")}
    cs1_refs = {k: v for k, v in flash_refs.items() if k.startswith("CS1")}

    print(f"\n    CS0 (0x4000_0000) references: {len(cs0_refs)} unique addresses")
    # Sort and show most-referenced addresses
    sorted_cs0 = sorted(cs0_refs.items(), key=lambda x: -len(x[1]))
    for addr_key, offsets in sorted_cs0[:30]:
        addr_val = int(addr_key.split(':')[1], 16)
        flash_offset = addr_val - 0x40000000
        print(f"      {addr_key} (flash+0x{flash_offset:06X}): "
              f"{len(offsets)} refs")

    print(f"\n    CS1 (0x5000_0000) references: {len(cs1_refs)} unique addresses")
    sorted_cs1 = sorted(cs1_refs.items(), key=lambda x: -len(x[1]))
    for addr_key, offsets in sorted_cs1[:30]:
        addr_val = int(addr_key.split(':')[1], 16)
        flash_offset = addr_val - 0x50000000
        print(f"      {addr_key} (flash+0x{flash_offset:06X}): "
              f"{len(offsets)} refs")

    # Try to identify flash partition boundaries
    print("\n    Potential flash partition boundaries:")
    all_addrs = set()
    for k in flash_refs:
        addr_val = int(k.split(':')[1], 16)
        all_addrs.add(addr_val)

    # Look for aligned addresses that could be partition starts
    for addr in sorted(all_addrs):
        offset = addr & 0x00FFFFFF
        # Partition boundaries are typically at 64KB or larger alignments
        if offset % 0x10000 == 0 and offset > 0:
            cs = "CS0" if addr >= 0x40000000 and addr < 0x50000000 else "CS1"
            base = 0x40000000 if cs == "CS0" else 0x50000000
            flash_off = addr - base
            refs = len(flash_refs.get(f"{cs}:0x{addr:08X}", []))
            if refs >= 2:
                print(f"      {cs} + 0x{flash_off:06X} ({flash_off // 1024}K): "
                      f"0x{addr:08X} ({refs} refs)")


def search_yaffs_structures(data):
    """Search for YAFFS filesystem structures and tags."""
    print("\n  Searching for YAFFS filesystem structures...")

    # YAFFS object header magic
    # YAFFS uses tagged data blocks. Object headers have specific patterns.
    # YAFFS1 tags: 8 bytes per page spare area
    # YAFFS2 tags: 16+ bytes per page spare area

    # Search for YAFFS-related strings
    yaffs_strings = []
    all_strings = find_strings(data, min_length=4)
    for offset, s in all_strings:
        if 'yaffs' in s.lower() or 'YAFFS' in s:
            yaffs_strings.append((offset, s))

    if yaffs_strings:
        print(f"    Found {len(yaffs_strings)} YAFFS-related strings:")
        seen = set()
        for offset, s in yaffs_strings:
            if s not in seen:
                addr = RAM_BASE + offset
                print(f"      0x{addr:08X}: {s[:120]}")
                seen.add(s)
    else:
        print("    No YAFFS strings found.")

    # Search for YAFFS mount point strings
    mount_strings = []
    for offset, s in all_strings:
        if s.startswith('/') and any(keyword in s.lower() for keyword in
                                     ['config', 'data', 'nvram', 'flash',
                                      'persist', 'var', 'etc', 'log',
                                      'mnt', 'tmp', 'yaffs']):
            mount_strings.append((offset, s))

    if mount_strings:
        print(f"\n    Potential filesystem paths ({len(mount_strings)}):")
        seen = set()
        for offset, s in mount_strings:
            if s not in seen:
                addr = RAM_BASE + offset
                print(f"      0x{addr:08X}: {s}")
                seen.add(s)


def search_config_format(data):
    """Search for configuration data format patterns."""
    print("\n  Searching for configuration data format patterns...")

    # Look for XML-like config patterns
    xml_patterns = [
        b'<?xml',
        b'<config',
        b'<Config',
        b'<setting',
        b'<Setting',
        b'<param',
        b'<value',
    ]
    for pattern in xml_patterns:
        pos = data.find(pattern)
        if pos >= 0:
            addr = RAM_BASE + pos
            # Show context
            context = data[pos:pos + 80]
            printable = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in context)
            print(f"    XML pattern '{pattern.decode()}' at 0x{addr:08X}: {printable}")

    # Look for key=value patterns (common in embedded config)
    kv_pattern = re.compile(rb'[A-Za-z][A-Za-z0-9_]+=[A-Za-z0-9./:_ ]+')
    kv_matches = list(kv_pattern.finditer(data))
    if kv_matches:
        print(f"\n    Found {len(kv_matches)} key=value patterns:")
        seen = set()
        count = 0
        for match in kv_matches:
            s = match.group().decode('ascii', errors='replace')
            if s not in seen and len(s) > 8:
                addr = RAM_BASE + match.start()
                print(f"      0x{addr:08X}: {s[:100]}")
                seen.add(s)
                count += 1
                if count >= 30:
                    break

    # Look for binary config header patterns
    # Common: magic + version + size + CRC
    print("\n    Searching for binary config headers...")
    config_magics = [
        (b'CONF', "CONF magic"),
        (b'CFG\x00', "CFG magic"),
        (b'NVRA', "NVRA magic"),
        (b'\xDE\xAD\xBE\xEF', "DEADBEEF magic"),
        (b'\xCA\xFE\xBA\xBE', "CAFEBABE magic"),
        (b'HPPD', "HPPD (HP PDU) magic"),
        (b'HENN', "HENN (Henning) magic"),
        (b'BROO', "BROO (Brookline) magic"),
    ]
    for magic, desc in config_magics:
        pos = 0
        while True:
            pos = data.find(magic, pos)
            if pos < 0:
                break
            addr = RAM_BASE + pos
            # Show context around the magic
            context = data[pos:pos + 32]
            hex_str = context.hex()
            printable = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in context)
            print(f"    {desc} at 0x{addr:08X}:")
            print(f"      Hex: {hex_str}")
            print(f"      Str: {printable}")
            pos += 1


def search_flash_operations(data):
    """Search for flash erase/write function patterns."""
    print("\n  Searching for flash operation strings...")

    all_strings = find_strings(data, min_length=6)

    # Flash operation related strings
    flash_ops = []
    for offset, s in all_strings:
        s_lower = s.lower()
        if any(keyword in s_lower for keyword in [
            'flash_erase', 'flash_write', 'flash_read', 'flash_init',
            'nor_erase', 'nor_write', 'nor_read',
            'sector_erase', 'block_erase', 'chip_erase',
            'program_flash', 'write_flash', 'erase_flash',
            'flash_program', 'flash_lock', 'flash_unlock',
            'cfi', 'jedec',
            'mx29lv640', 'macronix',
        ]):
            flash_ops.append((offset, s))

    if flash_ops:
        print(f"    Found {len(flash_ops)} flash operation strings:")
        seen = set()
        for offset, s in flash_ops:
            if s not in seen:
                addr = RAM_BASE + offset
                print(f"      0x{addr:08X}: {s[:120]}")
                seen.add(s)
    else:
        print("    No flash operation strings found.")


def search_config_save_load(data):
    """Search for config save/load/factory reset patterns."""
    print("\n  Searching for config save/load/reset patterns...")

    all_strings = find_strings(data, min_length=6)

    patterns = [
        'save', 'load', 'store', 'read', 'write',
        'factory', 'default', 'reset',
        'import', 'export',
        'download', 'upload',
        'backup', 'restore',
    ]

    config_strings = []
    for offset, s in all_strings:
        s_lower = s.lower()
        if 'config' in s_lower or 'setting' in s_lower or 'nvram' in s_lower:
            if any(p in s_lower for p in patterns):
                config_strings.append((offset, s))

    if config_strings:
        print(f"    Found {len(config_strings)} config operation strings:")
        seen = set()
        for offset, s in config_strings:
            if s not in seen:
                addr = RAM_BASE + offset
                print(f"      0x{addr:08X}: {s[:120]}")
                seen.add(s)
    else:
        print("    No config operation strings found.")


def analyse_config_bin(data):
    """Look for config.bin format information."""
    print("\n  Searching for config.bin format clues...")

    all_strings = find_strings(data, min_length=4)

    config_bin_strings = []
    for offset, s in all_strings:
        if 'config.bin' in s.lower() or 'config_bin' in s.lower():
            config_bin_strings.append((offset, s))

    if config_bin_strings:
        print(f"    Found {len(config_bin_strings)} config.bin references:")
        for offset, s in config_bin_strings:
            addr = RAM_BASE + offset
            print(f"      0x{addr:08X}: {s[:120]}")
    else:
        print("    No direct config.bin references found.")

    # Search for file format/extension references
    file_strings = []
    for offset, s in all_strings:
        if '.bin' in s.lower() or '.cfg' in s.lower() or '.dat' in s.lower():
            if any(k in s.lower() for k in ['config', 'firmware', 'image',
                                              'setting', 'backup', 'export']):
                file_strings.append((offset, s))

    if file_strings:
        print(f"\n    File format references:")
        seen = set()
        for offset, s in file_strings:
            if s not in seen:
                addr = RAM_BASE + offset
                print(f"      0x{addr:08X}: {s[:120]}")
                seen.add(s)


def search_flash_partition_table(data):
    """Search for embedded flash partition/memory map table."""
    print("\n  Searching for flash partition table...")

    # In NET+OS, the flash layout is often defined in BSP code.
    # Look for sequences of flash addresses that could define partitions.

    # Find clusters of flash addresses (CS0: 0x40xxxxxx)
    flash_addr_offsets = []
    for i in range(0, len(data) - 3, 4):
        word = struct.unpack_from('>I', data, i)[0]
        if 0x40000000 <= word <= 0x40FFFFFF:
            flash_addr_offsets.append((i, word))
        elif 0x50000000 <= word <= 0x50FFFFFF:
            flash_addr_offsets.append((i, word))

    # Look for clusters (adjacent addresses in the binary often form tables)
    if len(flash_addr_offsets) < 2:
        print("    Not enough flash address references to identify partitions.")
        return

    clusters = []
    current_cluster = [flash_addr_offsets[0]]
    for i in range(1, len(flash_addr_offsets)):
        offset, addr = flash_addr_offsets[i]
        prev_offset = flash_addr_offsets[i - 1][0]
        # Consecutive words (within 16 bytes) = likely a table
        if offset - prev_offset <= 16:
            current_cluster.append(flash_addr_offsets[i])
        else:
            if len(current_cluster) >= 3:
                clusters.append(current_cluster)
            current_cluster = [flash_addr_offsets[i]]
    if len(current_cluster) >= 3:
        clusters.append(current_cluster)

    if clusters:
        print(f"    Found {len(clusters)} potential partition tables:")
        for idx, cluster in enumerate(clusters[:10]):
            code_addr = RAM_BASE + cluster[0][0]
            print(f"\n    Table {idx + 1} at 0x{code_addr:08X} ({len(cluster)} entries):")
            for offset, addr in cluster:
                cs = "CS0" if addr < 0x50000000 else "CS1"
                base = 0x40000000 if cs == "CS0" else 0x50000000
                flash_off = addr - base
                print(f"      0x{RAM_BASE + offset:08X}: 0x{addr:08X} "
                      f"({cs}+0x{flash_off:06X}, {flash_off // 1024}K)")
    else:
        print("    No obvious partition table clusters found.")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Use v2.0.51.12 as primary analysis target (latest version)
    decomp_file = "2.0.51.12_Z7550-02475_decompressed.bin"
    decomp_path = os.path.join(EXTRACT_DIR, decomp_file)

    if not os.path.exists(decomp_path):
        print(f"ERROR: Decompressed firmware not found: {decomp_path}")
        return

    with open(decomp_path, 'rb') as f:
        data = f.read()

    print(f"  Loaded {decomp_file}: {len(data):,} bytes")

    print(f"\n{'='*70}")
    print(f"  NVRAM/Configuration Storage Analysis")
    print(f"{'='*70}")

    search_nvram_strings(data)
    search_yaffs_structures(data)
    search_flash_addresses(data)
    search_flash_partition_table(data)
    search_flash_operations(data)
    search_config_save_load(data)
    search_config_format(data)
    analyse_config_bin(data)

    print(f"\n{'='*70}")
    print(f"  Summary")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()

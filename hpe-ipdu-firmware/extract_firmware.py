#!/usr/bin/env python3
"""Extract and analyse HPE iPDU firmware image.bin files.

The firmware ZIP files contain image.bin files. This script extracts them,
identifies the structure (header, kernel, filesystem), and attempts to
extract the root filesystem.
"""

import os
import struct
import subprocess
import sys
import zipfile

BACKUP_DIR = "backup"
EXTRACT_DIR = "extracted"

# Magic bytes we're looking for
SQSH_MAGIC = b'hsqs'        # SquashFS LE
SQSH_MAGIC_BE = b'sqsh'     # SquashFS BE
CRAMFS_MAGIC = b'\x45\x3d\xcd\x28'  # CramFS
JFFS2_MAGIC = b'\x85\x19'   # JFFS2
GZIP_MAGIC = b'\x1f\x8b'    # gzip
LZMA_MAGIC = b'\x5d\x00\x00'  # LZMA
XZ_MAGIC = b'\xfd7zXZ\x00'  # XZ
UIMAGE_MAGIC = b'\x27\x05\x19\x56'  # U-Boot uImage
ZIMAGE_MAGIC = b'\x00\x00\xa0\xe1'  # ARM Linux zImage (mov r0, r0 NOP)


def find_all_magic(data: bytes, magic: bytes, name: str) -> list[int]:
    """Find all occurrences of a magic byte pattern."""
    positions = []
    offset = 0
    while True:
        pos = data.find(magic, offset)
        if pos == -1:
            break
        positions.append(pos)
        offset = pos + 1
    if positions:
        print(f"  Found {name} magic at: {', '.join(f'0x{p:08X}' for p in positions)}")
    return positions


def analyse_image(data: bytes, name: str) -> dict:
    """Analyse an image.bin firmware file."""
    print(f"\n{'='*70}")
    print(f"Analysing: {name} ({len(data)} bytes, {len(data)/1024/1024:.2f} MB)")
    print(f"{'='*70}")

    result = {
        'size': len(data),
        'squashfs': [],
        'cramfs': [],
        'jffs2': [],
        'gzip': [],
        'uimage': [],
    }

    # Print header
    print(f"\nFirst 256 bytes (header):")
    for i in range(0, min(256, len(data)), 16):
        hex_part = ' '.join(f'{b:02X}' for b in data[i:i+16])
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
        print(f"  {i:04X}: {hex_part:<48s} {ascii_part}")

    # Look for strings in the header area
    print(f"\nStrings in first 1024 bytes:")
    current = []
    for i in range(min(1024, len(data))):
        b = data[i]
        if 32 <= b < 127:
            current.append(chr(b))
        else:
            if len(current) >= 4:
                s = ''.join(current)
                print(f"  0x{i-len(current):04X}: \"{s}\"")
            current = []

    # Search for filesystem magic bytes
    print(f"\nSearching for filesystem signatures...")
    result['squashfs'] = find_all_magic(data, SQSH_MAGIC, "SquashFS-LE")
    find_all_magic(data, SQSH_MAGIC_BE, "SquashFS-BE")
    result['cramfs'] = find_all_magic(data, CRAMFS_MAGIC, "CramFS")
    result['jffs2'] = find_all_magic(data, JFFS2_MAGIC, "JFFS2")

    # Search for compression magic
    print(f"\nSearching for compressed data...")
    result['gzip'] = find_all_magic(data, GZIP_MAGIC, "gzip")
    find_all_magic(data, LZMA_MAGIC, "LZMA")
    find_all_magic(data, XZ_MAGIC, "XZ")

    # Search for boot image headers
    print(f"\nSearching for boot image headers...")
    result['uimage'] = find_all_magic(data, UIMAGE_MAGIC, "U-Boot uImage")
    find_all_magic(data, ZIMAGE_MAGIC, "ARM zImage")

    # For each SquashFS found, print header details
    for pos in result['squashfs']:
        if pos + 96 <= len(data):
            inode_count = struct.unpack_from('<I', data, pos + 4)[0]
            mod_time = struct.unpack_from('<I', data, pos + 8)[0]
            block_size = struct.unpack_from('<I', data, pos + 12)[0]
            frag_count = struct.unpack_from('<I', data, pos + 16)[0]
            # comp_type at offset 20 (squashfs 4.0+)
            comp_type = struct.unpack_from('<H', data, pos + 20)[0]
            sqfs_size = struct.unpack_from('<Q', data, pos + 40)[0]
            major = struct.unpack_from('<H', data, pos + 28)[0]
            minor = struct.unpack_from('<H', data, pos + 30)[0]
            print(f"\n  SquashFS @ 0x{pos:08X}:")
            print(f"    Version: {major}.{minor}")
            print(f"    Inodes: {inode_count}")
            print(f"    Block size: {block_size}")
            print(f"    Fragments: {frag_count}")
            print(f"    Compression: {comp_type} (1=gzip, 2=lzma, 3=lzo, 4=xz, 5=lz4, 6=zstd)")
            print(f"    Size: {sqfs_size} bytes ({sqfs_size/1024/1024:.2f} MB)")
            import datetime
            try:
                ts = datetime.datetime.fromtimestamp(mod_time)
                print(f"    Modification time: {ts.isoformat()}")
            except (OSError, ValueError):
                print(f"    Modification time: {mod_time} (raw)")

    # For each U-Boot uImage found, parse header
    for pos in result['uimage']:
        if pos + 64 <= len(data):
            magic = struct.unpack_from('>I', data, pos)[0]
            hcrc = struct.unpack_from('>I', data, pos + 4)[0]
            time = struct.unpack_from('>I', data, pos + 8)[0]
            size = struct.unpack_from('>I', data, pos + 12)[0]
            load = struct.unpack_from('>I', data, pos + 16)[0]
            entry = struct.unpack_from('>I', data, pos + 20)[0]
            dcrc = struct.unpack_from('>I', data, pos + 24)[0]
            os_type = data[pos + 28]
            arch = data[pos + 29]
            img_type = data[pos + 30]
            comp = data[pos + 31]
            img_name = data[pos + 32:pos + 64].split(b'\x00')[0].decode('ascii', errors='replace')

            os_names = {0: 'Invalid', 1: 'OpenBSD', 2: 'NetBSD', 3: 'FreeBSD',
                       4: 'BSD4.4', 5: 'Linux', 6: 'SVR4', 7: 'Esix',
                       8: 'Solaris', 9: 'Irix', 10: 'SCO', 11: 'Dell',
                       12: 'NCR', 13: 'LynxOS', 14: 'VxWorks', 15: 'pSOS',
                       16: 'QNX', 17: 'U-Boot'}
            arch_names = {0: 'Invalid', 1: 'Alpha', 2: 'ARM', 3: 'x86',
                         4: 'IA-64', 5: 'MIPS', 6: 'MIPS64', 7: 'PPC',
                         8: 'S390', 9: 'SH', 10: 'SPARC', 11: 'SPARC64',
                         12: 'M68K', 15: 'ARM64'}
            type_names = {0: 'Invalid', 1: 'Standalone', 2: 'Kernel', 3: 'RAMDisk',
                         4: 'Multi-File', 5: 'Firmware', 6: 'Script',
                         7: 'Filesystem'}
            comp_names = {0: 'none', 1: 'gzip', 2: 'bzip2', 3: 'lzma',
                         4: 'lzo', 5: 'lz4'}

            print(f"\n  U-Boot uImage @ 0x{pos:08X}:")
            print(f"    Name: \"{img_name}\"")
            print(f"    Data size: {size} bytes ({size/1024/1024:.2f} MB)")
            print(f"    Load addr: 0x{load:08X}")
            print(f"    Entry point: 0x{entry:08X}")
            print(f"    OS: {os_names.get(os_type, f'Unknown({os_type})')}")
            print(f"    Arch: {arch_names.get(arch, f'Unknown({arch})')}")
            print(f"    Type: {type_names.get(img_type, f'Unknown({img_type})')}")
            print(f"    Compression: {comp_names.get(comp, f'Unknown({comp})')}")
            import datetime
            try:
                ts = datetime.datetime.fromtimestamp(time)
                print(f"    Timestamp: {ts.isoformat()}")
            except (OSError, ValueError):
                print(f"    Timestamp: {time} (raw)")

    # Look for null-terminated strings that look like version info
    print(f"\nSearching for version strings...")
    for marker in [b'Linux version', b'Henning', b'firmware', b'iPDU',
                   b'NET+OS', b'NET+ARM', b'bootargs', b'bootcmd',
                   b'U-Boot', b'2.6.', b'2.4.', b'Digi', b'NetSilicon',
                   b'NS9360', b'image.bin']:
        pos = 0
        while True:
            pos = data.find(marker, pos)
            if pos == -1:
                break
            # Extract surrounding context
            start = max(0, pos - 16)
            end = min(len(data), pos + len(marker) + 64)
            context = data[start:end]
            # Clean for display
            display = ''.join(chr(b) if 32 <= b < 127 else '.' for b in context)
            print(f"  0x{pos:08X}: ...{display}...")
            pos += len(marker)

    return result


def extract_squashfs(data: bytes, offset: int, output_dir: str, label: str):
    """Extract a SquashFS filesystem from the data."""
    sqfs_size = struct.unpack_from('<Q', data, offset + 40)[0]
    sqfs_data = data[offset:offset + sqfs_size]

    sqfs_path = os.path.join(output_dir, f"{label}.sqfs")
    with open(sqfs_path, 'wb') as f:
        f.write(sqfs_data)
    print(f"\n  Wrote SquashFS ({sqfs_size} bytes) to {sqfs_path}")

    # Try to extract with unsquashfs
    extract_root = os.path.join(output_dir, f"{label}_rootfs")
    cmd = ["unsquashfs", "-f", "-d", extract_root, sqfs_path]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Successfully extracted to {extract_root}")
        # Count files
        file_count = sum(len(files) for _, _, files in os.walk(extract_root))
        dir_count = sum(len(dirs) for _, dirs, _ in os.walk(extract_root))
        print(f"  {file_count} files, {dir_count} directories")
    else:
        print(f"  unsquashfs failed (rc={result.returncode})")
        if result.stderr:
            print(f"  stderr: {result.stderr[:500]}")
        if result.stdout:
            print(f"  stdout: {result.stdout[:500]}")

    return extract_root


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(EXTRACT_DIR, exist_ok=True)

    # Find all zip files
    zips = sorted(f for f in os.listdir(BACKUP_DIR) if f.endswith('.zip'))
    if not zips:
        print(f"ERROR: No ZIP files found in {BACKUP_DIR}/")
        sys.exit(1)

    print(f"Found {len(zips)} firmware ZIP files:")
    for z in zips:
        print(f"  {z}")

    # Process each zip
    for zip_name in zips:
        zip_path = os.path.join(BACKUP_DIR, zip_name)

        # Extract version from filename
        # e.g., HPE_iPDU_Firmware_Update_2.0.51.12_Z7550-02475.zip
        version = zip_name.replace('.zip', '')
        for prefix in ['HPE_iPDU_Firmware_Update_', 'HPE_Intelligent_PDU_Firmware_Update_']:
            version = version.replace(prefix, '')

        print(f"\n{'#'*70}")
        print(f"Processing: {zip_name} (version label: {version})")
        print(f"{'#'*70}")

        # Extract image.bin from zip
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Find image.bin (may be in a subdirectory)
            image_names = [n for n in zf.namelist() if n.endswith('image.bin')]
            if not image_names:
                print(f"  WARNING: No image.bin found in {zip_name}")
                continue

            image_name = image_names[0]
            image_data = zf.read(image_name)
            print(f"  Extracted {image_name}: {len(image_data)} bytes")

            # Also extract README.txt if present
            readme_names = [n for n in zf.namelist() if n.endswith('README.txt')]
            if readme_names:
                readme_data = zf.read(readme_names[0])
                readme_path = os.path.join(EXTRACT_DIR, f"{version}_README.txt")
                with open(readme_path, 'wb') as f:
                    f.write(readme_data)
                print(f"  Extracted README to {readme_path}")

        # Save raw image.bin
        raw_path = os.path.join(EXTRACT_DIR, f"{version}_image.bin")
        with open(raw_path, 'wb') as f:
            f.write(image_data)

        # Analyse it
        result = analyse_image(image_data, f"{version}/image.bin")

        # Extract any SquashFS found
        for i, sqfs_offset in enumerate(result['squashfs']):
            sqfs_size = struct.unpack_from('<Q', image_data, sqfs_offset + 40)[0]
            # Verify it looks reasonable
            inode_count = struct.unpack_from('<I', image_data, sqfs_offset + 4)[0]
            if 10 < inode_count < 100000 and sqfs_size < len(image_data):
                label = f"{version}_sqfs{i}" if i > 0 else f"{version}_sqfs"
                extract_squashfs(image_data, sqfs_offset, EXTRACT_DIR, label)

    # Summary
    print(f"\n{'='*70}")
    print(f"EXTRACTION COMPLETE")
    print(f"{'='*70}")
    print(f"Extracted files are in {EXTRACT_DIR}/")

    # List what we got
    for entry in sorted(os.listdir(EXTRACT_DIR)):
        path = os.path.join(EXTRACT_DIR, entry)
        if os.path.isdir(path):
            file_count = sum(len(files) for _, _, files in os.walk(path))
            print(f"  {entry}/ ({file_count} files)")
        else:
            print(f"  {entry} ({os.path.getsize(path)} bytes)")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Extract IO table binary files from Dell C410X BMC firmware.

The firmware .pec file contains a SquashFS filesystem.
We locate the SquashFS using magic bytes, extract it,
then pull out the IO configuration tables.
"""

import os
import struct
import subprocess
import sys
import tempfile
import zipfile

FIRMWARE_ZIP = "backup/c410xbmc135.zip"
EXTRACT_DIR = "extracted"

# SquashFS magic bytes (little-endian)
SQSH_MAGIC = b'hsqs'  # SquashFS LE magic

# Files we want to extract from the rootfs
TARGET_FILES = [
    "etc/default/ipmi/evb/IO_fl.bin",
    "etc/default/ipmi/evb/IS_fl.bin",
    "etc/default/ipmi/evb/IX_fl.bin",
    "etc/default/ipmi/evb/FT_fl.bin",
    "etc/default/ipmi/evb/FunctionTable.bin",
    "etc/default/ipmi/evb/oemdef.bin",
    "etc/default/ipmi/evb/NVRAM_SDR00.dat",
    "etc/default/ipmi/evb/NVRAM_FRU00.dat",
    "etc/default/ipmi/evb/ID_devid.bin",
    "etc/default/ipmi/evb/FI_fwid.bin",
    "etc/default/ipmi/evb/bmcsetting",
]


def find_squashfs(data: bytes) -> int:
    """Find SquashFS magic in the firmware image."""
    offset = 0
    while True:
        pos = data.find(SQSH_MAGIC, offset)
        if pos == -1:
            return -1
        # Verify it looks like a real SquashFS header
        if pos + 96 <= len(data):
            # Check inode count is reasonable (offset 4, uint32 LE)
            inode_count = struct.unpack_from('<I', data, pos + 4)[0]
            if 10 < inode_count < 100000:
                print(f"  Found SquashFS at offset 0x{pos:08X} ({inode_count} inodes)")
                return pos
        offset = pos + 1
    return -1


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Step 1: Extract .pec from zip
    print(f"Extracting {FIRMWARE_ZIP}...")
    with zipfile.ZipFile(FIRMWARE_ZIP, 'r') as zf:
        names = zf.namelist()
        print(f"  Contents: {names}")
        pec_name = None
        for name in names:
            if name.lower().endswith('.pec') or 'firmimg' in name.lower() or 'bm3p' in name.lower():
                pec_name = name
                break
        if pec_name is None:
            # Just use the largest file
            sizes = [(zf.getinfo(n).file_size, n) for n in names]
            sizes.sort(reverse=True)
            pec_name = sizes[0][1]
            print(f"  Using largest file: {pec_name} ({sizes[0][0]} bytes)")

        pec_data = zf.read(pec_name)
        print(f"  Read {len(pec_data)} bytes from {pec_name}")

    # Step 2: Find SquashFS in the .pec
    print("Searching for SquashFS...")
    sqfs_offset = find_squashfs(pec_data)
    if sqfs_offset == -1:
        print("ERROR: No SquashFS found in firmware image!")
        sys.exit(1)

    # Read SquashFS size from header (offset 40 from start, uint64 LE = bytes_used)
    sqfs_size = struct.unpack_from('<Q', pec_data, sqfs_offset + 40)[0]
    print(f"  SquashFS size: {sqfs_size} bytes ({sqfs_size / 1024 / 1024:.1f} MB)")

    # Extract SquashFS blob
    sqfs_data = pec_data[sqfs_offset:sqfs_offset + sqfs_size]
    sqfs_path = os.path.join(EXTRACT_DIR, "rootfs.sqfs")
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    with open(sqfs_path, 'wb') as f:
        f.write(sqfs_data)
    print(f"  Wrote SquashFS to {sqfs_path}")

    # Step 3: Extract files from SquashFS
    print("Extracting files from SquashFS...")
    extract_root = os.path.join(EXTRACT_DIR, "rootfs")

    # Use unsquashfs to extract specific files
    for target in TARGET_FILES:
        cmd = ["unsquashfs", "-f", "-d", extract_root, sqfs_path, target]
        result = subprocess.run(cmd, capture_output=True, text=True)
        extracted_path = os.path.join(extract_root, target)
        if os.path.exists(extracted_path):
            size = os.path.getsize(extracted_path)
            print(f"  Extracted: {target} ({size} bytes)")
        else:
            print(f"  NOT FOUND: {target}")

    # Step 4: Also dump the PEC header for analysis
    print("\nPEC header (first 256 bytes):")
    for i in range(0, min(256, len(pec_data)), 16):
        hex_part = ' '.join(f'{b:02X}' for b in pec_data[i:i+16])
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in pec_data[i:i+16])
        print(f"  {i:04X}: {hex_part:<48s} {ascii_part}")

    # Step 5: Also find and dump U-Boot environment
    print("\nSearching for U-Boot environment...")
    # U-Boot env typically starts with a CRC32 followed by key=value strings
    for marker in [b'bootargs=', b'bootcmd=', b'baudrate=']:
        pos = pec_data.find(marker)
        if pos != -1:
            # Back up to find the start of the environment block
            start = max(0, pos - 256)
            print(f"  Found '{marker.decode()}' at offset 0x{pos:08X}")
            # Extract a chunk around it
            env_start = pos
            # Scan backwards to find beginning
            while env_start > start and pec_data[env_start - 1] != 0:
                env_start -= 1
            env_end = pos + 1024
            while env_end < len(pec_data) and pec_data[env_end] != 0:
                env_end += 1
            env_chunk = pec_data[env_start:env_end]
            # Parse null-terminated strings
            strings = env_chunk.split(b'\x00')
            for s in strings[:20]:
                if s:
                    try:
                        print(f"    {s.decode('ascii')}")
                    except UnicodeDecodeError:
                        pass
            break

    print("\nDone! Binary files are in extracted/rootfs/etc/default/ipmi/evb/")


if __name__ == '__main__':
    main()

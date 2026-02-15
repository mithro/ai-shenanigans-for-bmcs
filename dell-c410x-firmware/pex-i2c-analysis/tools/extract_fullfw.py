#!/usr/bin/env python3
"""Extract fullfw ARM ELF binary and kernel modules from Dell C410X BMC firmware.

The firmware archive structure:
  backup/c410xbmc135.zip
    -> C410XBMC135/fw_img/BM3P135.pec (Dell/Avocent DCSI format, ~10MB)
      -> SquashFS v3.1 at some offset (magic bytes b'hsqs')
        -> /sbin/fullfw (ARM ELF, ~1.2MB - core IPMI engine)
        -> /lib/modules/... (kernel modules including aess_i2cdrv.ko)
        -> /sbin/* (other interesting binaries)

Usage:
    uv run extract_fullfw.py
"""

import os
import shutil
import struct
import subprocess
import sys
import zipfile


# Paths relative to the repository root
FIRMWARE_ZIP_REL = os.path.join("dell-c410x-firmware", "backup", "c410xbmc135.zip")
OUTPUT_DIR_REL = os.path.join("dell-c410x-firmware", "pex-i2c-analysis", "analysis")

# SquashFS magic bytes (little-endian format)
SQSH_MAGIC = b'hsqs'

# Files and directories to extract from the SquashFS rootfs
EXTRACT_TARGETS = [
    "sbin/fullfw",
    "sbin/",
    "lib/modules/",
]


def get_repo_root():
    """Find the repository root by walking up from this script's location.

    The script is at: <repo>/dell-c410x-firmware/pex-i2c-analysis/tools/extract_fullfw.py
    So repo root is 3 levels up.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # tools/ -> pex-i2c-analysis/ -> dell-c410x-firmware/ -> repo root
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
    return repo_root


def find_squashfs(data: bytes) -> int:
    """Find the SquashFS magic bytes in the firmware image.

    Validates that the found offset looks like a real SquashFS header
    by checking the inode count is reasonable.

    Returns the offset of the SquashFS, or -1 if not found.
    """
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


def extract_pec_from_zip(zip_path: str) -> bytes:
    """Extract the .pec firmware image from the zip archive.

    Returns the raw bytes of the .pec file.
    """
    print(f"Opening firmware zip: {zip_path}")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()
        print(f"  Zip contents: {len(names)} entries")
        for name in names:
            info = zf.getinfo(name)
            if info.file_size > 0:
                print(f"    {name} ({info.file_size:,} bytes)")

        # Find the .pec file
        pec_name = None
        for name in names:
            if name.lower().endswith('.pec'):
                pec_name = name
                break

        if pec_name is None:
            # Fall back to the largest file
            sizes = [(zf.getinfo(n).file_size, n) for n in names]
            sizes.sort(reverse=True)
            pec_name = sizes[0][1]
            print(f"  WARNING: No .pec file found, using largest file: {pec_name}")

        print(f"  Reading {pec_name}...")
        pec_data = zf.read(pec_name)
        print(f"  Read {len(pec_data):,} bytes from {pec_name}")
        return pec_data


def find_and_extract_squashfs(pec_data: bytes, tmp_dir: str) -> str:
    """Locate SquashFS in the .pec data and write it to a temp file.

    Returns the path to the extracted SquashFS file.
    """
    print("Searching for SquashFS in firmware image...")
    sqfs_offset = find_squashfs(pec_data)
    if sqfs_offset == -1:
        print("ERROR: No SquashFS found in firmware image!")
        sys.exit(1)

    # Read SquashFS size from header
    # SquashFS superblock: offset 40 from start = bytes_used (uint64 LE)
    sqfs_size = struct.unpack_from('<Q', pec_data, sqfs_offset + 40)[0]
    print(f"  SquashFS size: {sqfs_size:,} bytes ({sqfs_size / 1024 / 1024:.1f} MB)")

    # Verify the size is reasonable
    if sqfs_size > len(pec_data) - sqfs_offset:
        print(f"  WARNING: SquashFS size ({sqfs_size}) exceeds available data "
              f"({len(pec_data) - sqfs_offset})")
        sqfs_size = len(pec_data) - sqfs_offset
        print(f"  Adjusted to {sqfs_size:,} bytes")

    # Write SquashFS blob to temp file
    sqfs_data = pec_data[sqfs_offset:sqfs_offset + sqfs_size]
    sqfs_path = os.path.join(tmp_dir, "rootfs.sqfs")
    with open(sqfs_path, 'wb') as f:
        f.write(sqfs_data)
    print(f"  Wrote SquashFS to {sqfs_path}")

    return sqfs_path


def unsquashfs_extract(sqfs_path: str, tmp_dir: str) -> str:
    """Extract files from the SquashFS using unsquashfs.

    Extracts the full filesystem to get all interesting files.
    Returns the path to the extracted rootfs directory.
    """
    extract_root = os.path.join(tmp_dir, "rootfs")

    print("Extracting files from SquashFS...")

    # Extract each target
    for target in EXTRACT_TARGETS:
        print(f"  Extracting: {target}")
        cmd = ["unsquashfs", "-f", "-d", extract_root, sqfs_path, target]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    unsquashfs stderr: {result.stderr.strip()}")

    return extract_root


def copy_extracted_files(extract_root: str, output_dir: str):
    """Copy extracted files to the output directory.

    Preserves directory structure under the output directory.
    """
    os.makedirs(output_dir, exist_ok=True)

    files_copied = []

    # Copy sbin/fullfw (primary target)
    fullfw_src = os.path.join(extract_root, "sbin", "fullfw")
    if os.path.exists(fullfw_src):
        fullfw_dst = os.path.join(output_dir, "fullfw")
        shutil.copy2(fullfw_src, fullfw_dst)
        size = os.path.getsize(fullfw_dst)
        print(f"  Copied: fullfw ({size:,} bytes)")
        files_copied.append(("fullfw", fullfw_dst))
    else:
        print("  ERROR: sbin/fullfw not found in SquashFS!")
        sys.exit(1)

    # Copy all sbin binaries
    sbin_src = os.path.join(extract_root, "sbin")
    sbin_dst = os.path.join(output_dir, "sbin")
    if os.path.isdir(sbin_src):
        os.makedirs(sbin_dst, exist_ok=True)
        for fname in sorted(os.listdir(sbin_src)):
            src = os.path.join(sbin_src, fname)
            if os.path.isfile(src):
                dst = os.path.join(sbin_dst, fname)
                shutil.copy2(src, dst)
                size = os.path.getsize(dst)
                print(f"  Copied: sbin/{fname} ({size:,} bytes)")
                files_copied.append((f"sbin/{fname}", dst))

    # Copy kernel modules
    modules_src = os.path.join(extract_root, "lib", "modules")
    modules_dst = os.path.join(output_dir, "lib", "modules")
    if os.path.isdir(modules_src):
        if os.path.exists(modules_dst):
            shutil.rmtree(modules_dst)
        shutil.copytree(modules_src, modules_dst)
        # List what we got
        for dirpath, dirnames, filenames in os.walk(modules_dst):
            for fname in sorted(filenames):
                fpath = os.path.join(dirpath, fname)
                rel = os.path.relpath(fpath, output_dir)
                size = os.path.getsize(fpath)
                print(f"  Copied: {rel} ({size:,} bytes)")
                files_copied.append((rel, fpath))
    else:
        print("  WARNING: lib/modules/ not found in SquashFS")

    return files_copied


def report_results(output_dir: str, files_copied: list):
    """Report file information for verification."""
    print("\n" + "=" * 70)
    print("EXTRACTION RESULTS")
    print("=" * 70)

    for rel_name, full_path in files_copied:
        if not os.path.exists(full_path):
            continue

        size = os.path.getsize(full_path)

        # Run 'file' command
        result = subprocess.run(
            ["file", full_path], capture_output=True, text=True
        )
        file_type = result.stdout.strip()

        # Run md5sum
        result = subprocess.run(
            ["md5sum", full_path], capture_output=True, text=True
        )
        md5 = result.stdout.split()[0] if result.stdout else "unknown"

        print(f"\n  {rel_name}:")
        print(f"    Size: {size:,} bytes")
        print(f"    MD5:  {md5}")
        print(f"    Type: {file_type}")

    # Special highlight for fullfw
    fullfw_path = os.path.join(output_dir, "fullfw")
    if os.path.exists(fullfw_path):
        print("\n" + "-" * 70)
        print("PRIMARY TARGET: fullfw")
        result = subprocess.run(
            ["file", fullfw_path], capture_output=True, text=True
        )
        print(f"  {result.stdout.strip()}")

        result = subprocess.run(
            ["readelf", "-h", fullfw_path], capture_output=True, text=True
        )
        if result.returncode == 0:
            print("\n  ELF Header:")
            for line in result.stdout.strip().split('\n'):
                print(f"    {line}")

    print("\n" + "=" * 70)
    print(f"All files extracted to: {output_dir}")
    print("=" * 70)


def main():
    repo_root = get_repo_root()
    print(f"Repository root: {repo_root}")

    zip_path = os.path.join(repo_root, FIRMWARE_ZIP_REL)
    output_dir = os.path.join(repo_root, OUTPUT_DIR_REL)

    # Verify the zip exists
    if not os.path.exists(zip_path):
        print(f"ERROR: Firmware zip not found at {zip_path}")
        sys.exit(1)

    # Use a project-local tmp directory (NEVER /tmp/)
    tmp_dir = os.path.join(repo_root, "dell-c410x-firmware", "pex-i2c-analysis", "tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        # Step 1: Extract .pec from zip
        pec_data = extract_pec_from_zip(zip_path)

        # Step 2: Find and extract SquashFS
        sqfs_path = find_and_extract_squashfs(pec_data, tmp_dir)

        # Step 3: Extract files from SquashFS
        extract_root = unsquashfs_extract(sqfs_path, tmp_dir)

        # Step 4: Copy to output directory
        print(f"\nCopying extracted files to {output_dir}...")
        files_copied = copy_extracted_files(extract_root, output_dir)

        # Step 5: Report results
        report_results(output_dir, files_copied)

    finally:
        # Step 6: Clean up temp directory (ALWAYS clean up!)
        print(f"\nCleaning up temp directory: {tmp_dir}")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
            print("  Temp directory removed.")


if __name__ == '__main__':
    main()

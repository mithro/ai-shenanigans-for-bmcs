#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.28",
# ]
# ///
"""Build a minimal BusyBox initramfs for the Dell C410X BMC (AST2050).

Downloads BusyBox source, cross-compiles it statically for ARM926EJ-S,
creates a cpio.gz initramfs archive, and wraps it as a legacy uImage
ramdisk for the stock U-Boot 1.2.0 bootloader.

Output files:
  - initramfs.cpio.gz   : Raw compressed cpio archive
  - uInitrd-c410x       : Legacy uImage ramdisk (for U-Boot bootm)

Usage:
    uv run build.py
    uv run build.py --busybox-version 1.37.0 --output-dir ./out
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import requests

CROSS_COMPILE = "arm-linux-gnueabi-"
BUSYBOX_MIRROR = "https://busybox.net/downloads"
SCRIPT_DIR = Path(__file__).resolve().parent


def download_busybox(version: str, build_dir: Path) -> Path:
    """Download and extract BusyBox source tarball.

    Returns the path to the extracted source directory.
    """
    tarball_name = f"busybox-{version}.tar.bz2"
    tarball_path = build_dir / tarball_name
    source_dir = build_dir / f"busybox-{version}"

    if source_dir.exists():
        print(f"[busybox] Source already exists: {source_dir}")
        return source_dir

    url = f"{BUSYBOX_MIRROR}/{tarball_name}"
    print(f"[busybox] Downloading {url}")
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()

    with open(tarball_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"[busybox] Extracting {tarball_name}")
    with tarfile.open(tarball_path, "r:bz2") as tar:
        tar.extractall(path=build_dir)

    tarball_path.unlink()
    return source_dir


def set_kconfig(config_text: str, option: str, value: bool | str) -> str:
    """Set a Kconfig option in a .config file, handling all cases robustly.

    Removes any existing setting for the option (whether set or unset),
    then appends the desired value. Works regardless of defconfig format.
    """
    # Remove existing line: either "CONFIG_X=..." or "# CONFIG_X is not set"
    config_text = re.sub(
        rf'^(CONFIG_{option}=.*|# CONFIG_{option} is not set)\n',
        '',
        config_text,
        flags=re.MULTILINE,
    )
    # Append new setting
    if value is True:
        config_text += f'CONFIG_{option}=y\n'
    elif value is False:
        config_text += f'# CONFIG_{option} is not set\n'
    else:
        config_text += f'CONFIG_{option}={value}\n'
    return config_text


def configure_busybox(source_dir: Path) -> None:
    """Configure BusyBox with defconfig + static linking + useful applets."""
    env = os.environ.copy()
    env["CROSS_COMPILE"] = CROSS_COMPILE
    env["ARCH"] = "arm"

    print("[busybox] Running defconfig")
    subprocess.run(
        ["make", "defconfig"],
        cwd=source_dir,
        env=env,
        check=True,
    )

    config_path = source_dir / ".config"
    config_text = config_path.read_text()

    # Enable static linking (required for initramfs, no shared libs)
    config_text = set_kconfig(config_text, "STATIC", True)

    # Enable useful applets for BMC hardware debugging
    for applet in [
        "FEATURE_DEVMEM", "I2CGET", "I2CSET", "I2CDUMP",
        "I2CDETECT", "I2CTRANSFER",
    ]:
        config_text = set_kconfig(config_text, applet, True)

    # Disable SHA hardware acceleration - uses x86 SHA-NI intrinsics
    # that are unavailable when cross-compiling for ARM
    config_text = set_kconfig(config_text, "SHA1_HWACCEL", False)
    config_text = set_kconfig(config_text, "SHA256_HWACCEL", False)
    config_text = set_kconfig(config_text, "SHA3_SMALL", True)

    # Disable tc (traffic control) applet - requires CBQ kernel headers
    # that were removed in recent kernel versions
    config_text = set_kconfig(config_text, "TC", False)

    config_path.write_text(config_text)

    # Run oldconfig to resolve any dependencies
    subprocess.run(
        ["make", "oldconfig"],
        cwd=source_dir,
        env=env,
        input=b"\n" * 100,  # Accept defaults for any new questions
        check=True,
    )


def build_busybox(source_dir: Path, jobs: int) -> Path:
    """Cross-compile BusyBox. Returns path to the static binary."""
    env = os.environ.copy()
    env["CROSS_COMPILE"] = CROSS_COMPILE
    env["ARCH"] = "arm"

    print(f"[busybox] Building with {jobs} parallel jobs")
    subprocess.run(
        ["make", f"-j{jobs}"],
        cwd=source_dir,
        env=env,
        check=True,
    )

    busybox_bin = source_dir / "busybox"
    if not busybox_bin.exists():
        print("[busybox] ERROR: busybox binary not found after build", file=sys.stderr)
        sys.exit(1)

    # Verify it's a static ARM binary
    file_output = subprocess.run(
        ["file", str(busybox_bin)], capture_output=True, text=True, check=True
    )
    print(f"[busybox] Binary: {file_output.stdout.strip()}")
    if "statically linked" not in file_output.stdout:
        print("[busybox] ERROR: binary is not statically linked!", file=sys.stderr)
        sys.exit(1)

    return busybox_bin


def create_initramfs(busybox_bin: Path, build_dir: Path) -> Path:
    """Create the initramfs directory tree with BusyBox installed.

    Returns the path to the initramfs root directory.
    """
    rootfs = build_dir / "rootfs"
    if rootfs.exists():
        shutil.rmtree(rootfs)

    print("[initramfs] Creating directory structure")
    for d in ["bin", "sbin", "usr/bin", "usr/sbin", "dev", "proc", "sys",
              "etc", "tmp", "run", "var/log"]:
        (rootfs / d).mkdir(parents=True, exist_ok=True)

    # Install BusyBox
    print("[initramfs] Installing BusyBox")
    dest_busybox = rootfs / "bin" / "busybox"
    shutil.copy2(busybox_bin, dest_busybox)
    dest_busybox.chmod(0o755)

    # Create symlinks for all applets
    env = os.environ.copy()
    # Run busybox --list to get applet names (using the host to list,
    # but we can also parse the binary or use a known list)
    # Since the binary is ARM, we can't run it on x86. Instead, install
    # via BusyBox's make install which creates the symlinks.
    source_dir = busybox_bin.parent
    env["CROSS_COMPILE"] = CROSS_COMPILE
    env["ARCH"] = "arm"
    env["CONFIG_PREFIX"] = str(rootfs)
    subprocess.run(
        ["make", "install"],
        cwd=source_dir,
        env=env,
        check=True,
    )

    # Copy our init script
    init_src = SCRIPT_DIR / "init"
    init_dst = rootfs / "init"
    shutil.copy2(init_src, init_dst)
    init_dst.chmod(0o755)

    # Create minimal /etc files
    (rootfs / "etc" / "hostname").write_text("c410x-bmc\n")
    (rootfs / "etc" / "passwd").write_text("root::0:0:root:/:/bin/sh\n")
    (rootfs / "etc" / "group").write_text("root:x:0:\n")

    return rootfs


def create_cpio_archive(rootfs: Path, output_dir: Path) -> Path:
    """Create a gzip-compressed cpio archive from the rootfs.

    Uses the cpio command directly for correct device node handling.
    Returns the path to the cpio.gz file.
    """
    cpio_gz = output_dir / "initramfs.cpio.gz"
    print(f"[initramfs] Creating {cpio_gz}")

    # Use find | cpio | gzip pipeline
    find = subprocess.Popen(
        ["find", ".", "-print0"],
        cwd=rootfs,
        stdout=subprocess.PIPE,
    )
    cpio = subprocess.Popen(
        ["cpio", "--null", "-o", "--format=newc"],
        cwd=rootfs,
        stdin=find.stdout,
        stdout=subprocess.PIPE,
    )
    assert find.stdout is not None
    find.stdout.close()

    gzip = subprocess.Popen(
        ["gzip", "-9"],
        stdin=cpio.stdout,
        stdout=open(cpio_gz, "wb"),
    )
    assert cpio.stdout is not None
    cpio.stdout.close()

    gzip.wait()
    cpio.wait()
    find.wait()

    if cpio.returncode != 0:
        print("[initramfs] ERROR: cpio failed", file=sys.stderr)
        sys.exit(1)

    size_kb = cpio_gz.stat().st_size / 1024
    print(f"[initramfs] Archive size: {size_kb:.0f} KB")
    return cpio_gz


def create_uimage_ramdisk(cpio_gz: Path, output_dir: Path) -> Path:
    """Wrap the cpio.gz as a legacy uImage ramdisk for U-Boot.

    The stock U-Boot 1.2.0 on the C410X only understands legacy uImage
    format. The ramdisk is loaded at 0x42600000 by tftp_boot.py.
    """
    uimage = output_dir / "uInitrd-c410x"
    print(f"[initramfs] Creating uImage ramdisk: {uimage}")

    subprocess.run(
        [
            "mkimage",
            "-A", "arm",
            "-O", "linux",
            "-T", "ramdisk",
            "-C", "gzip",
            "-n", "C410X BMC initramfs",
            "-d", str(cpio_gz),
            str(uimage),
        ],
        check=True,
    )

    # Verify
    subprocess.run(["mkimage", "-l", str(uimage)], check=True)
    return uimage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build minimal BusyBox initramfs for Dell C410X BMC",
    )
    parser.add_argument(
        "--busybox-version",
        default="1.37.0",
        help="BusyBox version to download (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for artifacts (default: script directory)",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=None,
        help="Build directory for intermediate files (default: output-dir/build)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=os.cpu_count() or 1,
        help="Parallel build jobs (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    output_dir = args.output_dir or SCRIPT_DIR
    build_dir = args.build_dir or (output_dir / "build")
    build_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Download BusyBox
    source_dir = download_busybox(args.busybox_version, build_dir)

    # Step 2: Configure
    configure_busybox(source_dir)

    # Step 3: Build
    busybox_bin = build_busybox(source_dir, args.jobs)

    # Step 4: Create initramfs
    rootfs = create_initramfs(busybox_bin, build_dir)

    # Step 5: Create cpio archive
    cpio_gz = create_cpio_archive(rootfs, output_dir)

    # Step 6: Create uImage ramdisk
    uimage = create_uimage_ramdisk(cpio_gz, output_dir)

    print("")
    print("Build complete!")
    print(f"  Initramfs: {cpio_gz}")
    print(f"  uImage:    {uimage}")


if __name__ == "__main__":
    main()

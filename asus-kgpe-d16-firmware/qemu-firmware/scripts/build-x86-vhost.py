#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Build an x86-64 "virtual host" initramfs for the USB/IP host-enumeration test
(features #2 / #3b). It boots on qemu-system-x86_64 with the HOST kernel (no x86
kernel build needed) and imports the BMC's exported USB gadget via vhci-hcd, then
verifies mass-storage data (#2) and a keyboard event (#3b).

Contents (all static, mirroring the ARM initramfs recipe):
  - static x86 busybox (CONFIG_TC disabled, as initramfs/build.py does for ARM)
  - static x86 usbip client (in-tree usbip 2.0 + libudev-zero, -all-static)
  - the host kernel's *kernel-matched* modules (vhci-hcd, usb-storage, usbhid,
    hid-generic, evdev + their dep closure), unxz'd, with a load.order
  - initramfs/vhost-x86-init as /init

Run:  uv run scripts/build-x86-vhost.py --output-dir <dir>
Produces <dir>/vhost-x86-initramfs.cpio.gz and prints the kernel to boot with
(the running host's /boot/vmlinuz-$(uname -r)).
"""
import argparse
import importlib.util
import lzma
import os
import platform
import shutil
import subprocess
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                        # qemu-firmware


def _load_build_usbip():
    """Load the sibling build-usbip.py (hyphenated) for its libudev-zero patch."""
    spec = importlib.util.spec_from_file_location(
        "build_usbip", ROOT / "initramfs" / "build-usbip.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
USBIP_SRC = (ROOT / "kernel" / "linux" / "tools" / "usb" / "usbip").resolve()
LIBUDEV_ZERO_URL = "https://github.com/illiliti/libudev-zero"
LIBUDEV_ZERO_COMMIT = "2bebebc9e0444ec53afd7f1f37aa80ff6b95f5f7"
BUSYBOX_URL = "https://busybox.net/downloads/busybox-{v}.tar.bz2"
BUSYBOX_VER = "1.37.0"
# Modules to load in the guest; their dep closure is resolved from modules.dep.
# hid-generic/evdev make the HID keyboard produce an evdev node (#3b); e1000 is the
# guest NIC (model=e1000) needed to reach the BMC's usbipd. Any that are built-in
# are skipped automatically.
TARGET_MODULES = ["e1000", "vhci-hcd", "usb-storage", "sd_mod", "usbhid",
                  "hid-generic", "evdev"]


def run(cmd, cwd=None, env=None, stdin=None):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, cwd=cwd, env=env, check=True, stdin=stdin)


def fetch(url, dest: Path):
    if dest.exists():
        return
    print("fetching", url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def build_busybox(build: Path) -> Path:
    tb = build / f"busybox-{BUSYBOX_VER}.tar.bz2"
    fetch(BUSYBOX_URL.format(v=BUSYBOX_VER), tb)
    src = build / f"busybox-{BUSYBOX_VER}"
    if not (src / "busybox").exists():
        if not src.exists():
            run(["tar", "xf", str(tb), "-C", str(build)])
        run(["make", "defconfig"], cwd=src)
        cfg = (src / ".config").read_text()
        cfg = cfg.replace("# CONFIG_STATIC is not set", "CONFIG_STATIC=y")
        # tc.c does not build against modern kernel headers (same fix as build.py).
        cfg = cfg.replace("CONFIG_TC=y", "# CONFIG_TC is not set")
        (src / ".config").write_text(cfg)
        run(["make", "oldconfig"], cwd=src, stdin=subprocess.DEVNULL)
        run(["make", f"-j{os.cpu_count()}"], cwd=src)
    return src / "busybox"


def build_usbip(build: Path) -> Path:
    """Static x86 usbip client via libudev-zero (native gcc). Returns the binary."""
    zero = build / "libudev-zero"
    if not zero.exists():
        run(["git", "clone", LIBUDEV_ZERO_URL, str(zero)])
        run(["git", "-C", str(zero), "checkout", LIBUDEV_ZERO_COMMIT])
    # Same /sys/class enumeration patch as the ARM build (needed for usbip's udc
    # enumeration; harmless for the client).
    _load_build_usbip().patch_libudev_zero_class_scan(zero)
    run(["make", "libudev.a"], cwd=zero)
    stage = build / "stage"
    (stage / "include").mkdir(parents=True, exist_ok=True)
    (stage / "lib").mkdir(parents=True, exist_ok=True)
    shutil.copy2(zero / "udev.h", stage / "include" / "libudev.h")
    shutil.copy2(zero / "libudev.a", stage / "lib" / "libudev.a")
    src = build / "usbip-src"
    if not (src / "src" / "usbip").exists():
        if src.exists():
            shutil.rmtree(src)
        shutil.copytree(USBIP_SRC, src)
        run(["./autogen.sh"], cwd=src)
        run(["./configure", f"CPPFLAGS=-I{stage}/include",
             f"LDFLAGS=-L{stage}/lib", "LIBS=-ludev",
             "--without-tcp-wrappers", "--disable-shared", "--enable-static"],
            cwd=src)
        run(["make", f"-j{os.cpu_count()}", f"LDFLAGS=-L{stage}/lib -all-static"],
            cwd=src)
    out = build / "usbip"
    run(["strip", "-o", str(out), str(src / "src" / "usbip")])
    info = subprocess.run(["file", str(out)], capture_output=True, text=True,
                          check=True).stdout
    print(info.strip())
    if "statically linked" not in info or "x86-64" not in info:
        raise SystemExit(f"FAIL: usbip not static x86-64: {info}")
    return out


def resolve_modules(krel: str):
    """Resolve the dependency closure of TARGET_MODULES from modules.dep.
    Returns (moddir, ordered list of (basename, abspath)) deps-first."""
    moddir = Path("/lib/modules") / krel
    dep_file = moddir / "modules.dep"
    if not dep_file.exists():
        raise SystemExit(f"no modules.dep at {dep_file}")
    # basename(without .ko*) -> (relpath, [dep basenames])
    table = {}

    def base(relpath):
        return Path(relpath).name.split(".ko")[0]

    for line in dep_file.read_text().splitlines():
        if ":" not in line:
            continue
        lhs, rhs = line.split(":", 1)
        deps = [base(d) for d in rhs.split()]
        table[base(lhs)] = (lhs.strip(), deps)

    ordered = []       # basenames, deps first
    seen = set()

    def visit(name):
        if name in seen:
            return
        seen.add(name)
        entry = table.get(name)
        if entry is None:
            # built-in (not a module) — nothing to load, skip silently
            return
        relpath, deps = entry
        for d in deps:
            visit(d)
        ordered.append((name, moddir / relpath))

    for t in TARGET_MODULES:
        if t not in table:
            print(f"note: {t} is built-in or absent — skipping")
        visit(t)
    return moddir, ordered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default=str(ROOT / "kernel" / "out"))
    ap.add_argument("--build-dir", default=str(HERE.parent / "initramfs" / "build" / "vhost"))
    ap.add_argument("--krelease", default=platform.release())
    args = ap.parse_args()

    build = Path(args.build_dir); build.mkdir(parents=True, exist_ok=True)
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)

    busybox = build_busybox(build)
    usbip = build_usbip(build)
    moddir, mods = resolve_modules(args.krelease)

    rootfs = build / "rootfs"
    if rootfs.exists():
        shutil.rmtree(rootfs)
    for d in ("bin", "sbin", "usr/bin", "usr/sbin", "dev", "proc", "sys",
              "tmp", "modules"):
        (rootfs / d).mkdir(parents=True, exist_ok=True)
    shutil.copy2(busybox, rootfs / "bin" / "busybox")
    os.chmod(rootfs / "bin" / "busybox", 0o755)
    shutil.copy2(usbip, rootfs / "usr/sbin" / "usbip")
    os.chmod(rootfs / "usr/sbin" / "usbip", 0o755)
    shutil.copy2(ROOT / "initramfs" / "vhost-x86-init", rootfs / "init")
    os.chmod(rootfs / "init", 0o755)

    # Bundle the modules (decompress .ko.xz -> .ko) + a load.order.
    order_lines = []
    for name, path in mods:
        data = path.read_bytes()
        if path.suffix == ".xz":
            data = lzma.decompress(data)
        ko = f"{name}.ko"
        (rootfs / "modules" / ko).write_bytes(data)
        order_lines.append(ko)
    (rootfs / "modules" / "load.order").write_text("\n".join(order_lines) + "\n")
    print(f"bundled {len(order_lines)} modules:", ", ".join(order_lines))

    # Pack cpio.gz.
    cpio = out / "vhost-x86-initramfs.cpio"
    names = subprocess.run(["find", "."], cwd=rootfs, capture_output=True,
                           text=True, check=True).stdout
    with open(cpio, "wb") as f:
        subprocess.run(["cpio", "--null", "-o", "--format=newc", "--owner=0:0"],
                       cwd=rootfs, input=names.replace("\n", "\0").encode(),
                       stdout=f, check=True)
    with open(cpio, "rb") as fi, open(str(cpio) + ".gz", "wb") as fo:
        subprocess.run(["gzip", "-9", "-c"], stdin=fi, stdout=fo, check=True)
    cpio.unlink()
    print("\nx86 vhost initramfs:", str(cpio) + ".gz")
    print("boot kernel:", f"/boot/vmlinuz-{args.krelease}")


if __name__ == "__main__":
    main()

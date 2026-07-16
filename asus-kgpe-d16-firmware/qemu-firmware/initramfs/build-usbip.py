#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Cross-compile a fully-static ARM USB/IP userspace (usbipd + usbip) for the
KGPE-D16 BMC (AST2050) initramfs.

WHY this exists (feature #2 / #3b — "connect virtual USB devices to the host"):
the BMC presents a USB *gadget* (HID keyboard + mass-storage) to a server host.
QEMU's kgpe-d16-bmc machine emulates only the BMC SoC, not the x86 host, so the
existing F6/F8 demos loop the gadget back in-guest over dummy_hcd and never reach
a real host. To prove FULL enumeration against an independent host in emulation,
the BMC guest exports its configfs gadget over USB/IP (`usbipd --device`, using the
kernel `usbip-vudc` UDC), and a second qemu-system-x86_64 "virtual host" imports it
(`usbip attach`, `vhci-hcd`). That needs the usbip userspace INSIDE the ARM
initramfs — hence this cross-build.

THE CRUX (de-risked 2026-07-16): the in-tree usbip `configure.ac` hard-requires
libudev (`AC_CHECK_LIB([udev],[udev_new])`), and `usbipd` links the whole
`libusbip` which pulls libudev across usbip_common/host_common/vhci_driver. A
static ARM build therefore needs a static ARM libudev — which glibc/eudev do not
provide cleanly for a no-dynamic-loader initramfs. Solution: **libudev-zero**
(https://github.com/illiliti/libudev-zero, ISC), a dependency-free static libudev
that reimplements exactly the sysfs-reading subset usbip uses. With it,
`--without-tcp-wrappers` and libtool `-all-static`, both binaries link fully
static (verified: `ELF 32-bit ARM ... statically linked`, no dynamic section).

The glibc `getaddrinfo`-in-static-binary warning is benign here: usbip attaches by
NUMERIC IP (the two QEMU guests talk over a fixed link, e.g. 10.9.0.1/.2), so NSS
is never dlopen'd.

The usbip source is taken from the vendored kernel submodule
(kernel/linux/tools/usb/usbip, version-locked to the BMC's 6.6.70 kernel — no
protocol skew with the in-kernel usbip-vudc/vhci-hcd drivers). It is COPIED to the
build dir before autogen so the submodule is never dirtied.

Standalone:  uv run initramfs/build-usbip.py --output-dir out
Or imported:  from build_usbip import build_usbip; usbipd, usbip = build_usbip(build)
"""
import argparse
import os
import shutil
import subprocess
from pathlib import Path

CROSS = os.environ.get("CROSS_COMPILE", "arm-linux-gnueabi-")
CC = CROSS + "gcc"
STRIP = CROSS + "strip"

# Pin libudev-zero to a known-good commit for reproducibility (master @ 2026-07-16).
LIBUDEV_ZERO_URL = "https://github.com/illiliti/libudev-zero"
LIBUDEV_ZERO_COMMIT = "2bebebc9e0444ec53afd7f1f37aa80ff6b95f5f7"

# The vendored usbip userspace (version-locked to the BMC kernel submodule).
HERE = Path(__file__).resolve().parent
USBIP_SRC = (HERE / ".." / "kernel" / "linux" / "tools" / "usb" / "usbip").resolve()


def run(cmd, cwd=None, env=None, stdin=None):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, cwd=cwd, env=env, check=True, stdin=stdin)


# libudev-zero upstream only enumerates /sys/dev/{block,char} (devnode devices), so
# it cannot see class devices without a devnode — notably the usbip 'udc' vhub
# (usbip-vudc.0), which usbipd --device must enumerate to export the bound gadget.
# This patch additionally scans /sys/class/<matched subsystem>/. Applied to the
# pinned commit (stable text); fail-loud if the expected text is absent.
_UEV_OLD = """int udev_enumerate_scan_devices(struct udev_enumerate *udev_enumerate)
{
    const char *path[] = { "/sys/dev/block", "/sys/dev/char", NULL };
    int i;

    if (!udev_enumerate) {
        return -1;
    }

    for (i = 0; path[i]; i++) {
        if (!scan_devices(udev_enumerate, path[i])) {
            return -1;
        }
    }

    return 0;
}"""
_UEV_NEW = """int udev_enumerate_scan_devices(struct udev_enumerate *udev_enumerate)
{
    const char *path[] = { "/sys/dev/block", "/sys/dev/char", NULL };
    struct udev_list_entry *m;
    char classpath[PATH_MAX];
    int i;

    if (!udev_enumerate) {
        return -1;
    }

    for (i = 0; path[i]; i++) {
        if (!scan_devices(udev_enumerate, path[i])) {
            return -1;
        }
    }

    /* Also scan /sys/class/<subsystem>/ for each matched subsystem so class
       devices WITHOUT a devnode (e.g. usbip 'udc') are enumerable. */
    for (m = udev_list_entry_get_next(&udev_enumerate->subsystem_match);
         m != NULL; m = udev_list_entry_get_next(m)) {
        snprintf(classpath, sizeof(classpath), "/sys/class/%s",
                 udev_list_entry_get_name(m));
        scan_devices(udev_enumerate, classpath);
    }

    return 0;
}"""


def patch_libudev_zero_class_scan(src: Path):
    """Make libudev-zero enumerate /sys/class/<subsystem>/ (idempotent, fail-loud)."""
    f = src / "udev_enumerate.c"
    text = f.read_text()
    if _UEV_NEW in text:
        return
    if _UEV_OLD not in text:
        raise SystemExit("libudev-zero udev_enumerate_scan_devices text changed — "
                         "update the class-scan patch in build-usbip.py")
    f.write_text(text.replace(_UEV_OLD, _UEV_NEW))


def build_libudev_zero(build: Path) -> Path:
    """Cross-build static ARM libudev.a and stage libudev.h + libudev.a; return
    the stage prefix (with include/ and lib/)."""
    src = build / "libudev-zero"
    if not src.exists():
        run(["git", "clone", LIBUDEV_ZERO_URL, str(src)])
        run(["git", "-C", str(src), "checkout", LIBUDEV_ZERO_COMMIT])
    patch_libudev_zero_class_scan(src)
    run(["make", f"CC={CC}", "libudev.a"], cwd=src)
    stage = build / "stage"
    (stage / "include").mkdir(parents=True, exist_ok=True)
    (stage / "lib").mkdir(parents=True, exist_ok=True)
    # libudev-zero's header is udev.h; usbip's configure looks for <libudev.h>.
    shutil.copy2(src / "udev.h", stage / "include" / "libudev.h")
    shutil.copy2(src / "libudev.a", stage / "lib" / "libudev.a")
    return stage


def build_usbip(build: Path):
    """Cross-build fully-static ARM usbipd + usbip. Returns (usbipd, usbip) as
    stripped Path binaries under <build>."""
    build.mkdir(parents=True, exist_ok=True)
    stage = build_libudev_zero(build)

    # Copy the vendored usbip source out of the submodule (autogen writes into the
    # tree; never dirty the submodule).
    src = build / "usbip-src"
    if src.exists():
        shutil.rmtree(src)
    shutil.copytree(USBIP_SRC, src)

    run(["./autogen.sh"], cwd=src)
    run(["./configure",
         "--host=arm-linux-gnueabi", f"CC={CC}",
         f"CPPFLAGS=-I{stage}/include",
         f"LDFLAGS=-L{stage}/lib",
         "LIBS=-ludev",
         "--without-tcp-wrappers",   # no libwrap in a static initramfs
         "--disable-shared", "--enable-static"],
        cwd=src)
    run(["make", f"-j{os.cpu_count()}", f"LDFLAGS=-L{stage}/lib -all-static"],
        cwd=src)

    outd = build / "usbip-bin"
    outd.mkdir(exist_ok=True)
    usbipd = outd / "usbipd"
    usbip = outd / "usbip"
    run([STRIP, "-o", str(usbipd), str(src / "src" / "usbipd")])
    run([STRIP, "-o", str(usbip), str(src / "src" / "usbip")])
    for b in (usbipd, usbip):
        out = subprocess.run(["file", str(b)], capture_output=True, text=True,
                             check=True).stdout
        print(out.strip())
        if "statically linked" not in out or "ARM" not in out:
            raise SystemExit(f"FAIL: {b} is not a static ARM binary: {out}")
    return usbipd, usbip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-dir", default=str(HERE / "build" / "usbip"))
    ap.add_argument("--output-dir", default=None,
                    help="optional dir to copy the stripped binaries into")
    args = ap.parse_args()
    usbipd, usbip = build_usbip(Path(args.build_dir))
    print("\nStatic ARM USB/IP userspace built:")
    run(["ls", "-la", str(usbipd), str(usbip)])
    if args.output_dir:
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for b in (usbipd, usbip):
            shutil.copy2(b, out / b.name)
        print("copied to", out)


if __name__ == "__main__":
    main()

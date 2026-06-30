#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Build a BusyBox + dropbear initramfs for the KGPE-D16 BMC (AST2050).

Produces (in --output-dir):
  - initramfs.cpio.gz       raw gzip cpio
  - uInitrd-kgpe-d16        u-boot ramdisk image
  - id_kgpe_d16_test        throwaway SSH private key for the CI ssh-login test
                            (the matching pubkey is baked into the rootfs)

Static BusyBox (shell, ip, udhcpc, ...) + static dropbear (sshd) with the test
public key in /root/.ssh/authorized_keys, so CI can SSH in over the QEMU
user-net hostfwd. stdlib only; cross-compiles with arm-linux-gnueabi-.
"""
import argparse
import os
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

CROSS = os.environ.get("CROSS_COMPILE", "arm-linux-gnueabi-")
CC = CROSS + "gcc"
BUSYBOX_URL = "https://busybox.net/downloads/busybox-{v}.tar.bz2"
DROPBEAR_URL = "https://matt.ucc.asn.au/dropbear/releases/dropbear-{v}.tar.bz2"


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


def untar(tarball: Path, into: Path) -> Path:
    with tarfile.open(tarball) as t:
        top = t.getnames()[0].split("/")[0]
        t.extractall(into)
    return into / top


def set_kconfig(text, key, val):
    """Force CONFIG_<key>=y/n in a .config blob."""
    full = f"CONFIG_{key}"
    on = f"{full}=y"
    off = f"# {full} is not set"
    want = on if val else off
    lines, seen = [], False
    for ln in text.splitlines():
        if ln.startswith(full + "=") or ln == off or ln == on:
            lines.append(want)
            seen = True
        else:
            lines.append(ln)
    if not seen:
        lines.append(want)
    return "\n".join(lines) + "\n"


def build_busybox(version, build: Path) -> Path:
    tb = build / f"busybox-{version}.tar.bz2"
    fetch(BUSYBOX_URL.format(v=version), tb)
    src = build / f"busybox-{version}"
    if not src.exists():
        untar(tb, build)
    env = {**os.environ, "ARCH": "arm", "CROSS_COMPILE": CROSS}
    run(["make", "defconfig"], cwd=src, env=env)
    cfg = (src / ".config").read_text()
    for key in ("STATIC", "IP", "UDHCPC", "FEATURE_IP_ADDRESS",
                "FEATURE_IP_LINK", "HOSTNAME", "MOUNT", "SH_IS_ASH"):
        cfg = set_kconfig(cfg, key, True)
    for key in ("TC", "SHA1_HWACCEL", "SHA256_HWACCEL"):
        cfg = set_kconfig(cfg, key, False)
    (src / ".config").write_text(cfg)
    # busybox kconfig has 'oldconfig' (not 'olddefconfig'); feed EOF so new
    # symbols take their defaults non-interactively.
    run(["make", "oldconfig"], cwd=src, env=env, stdin=subprocess.DEVNULL)
    run(["make", f"-j{os.cpu_count()}"], cwd=src, env=env)
    return src


def build_dropbear(version, build: Path) -> Path:
    tb = build / f"dropbear-{version}.tar.bz2"
    fetch(DROPBEAR_URL.format(v=version), tb)
    src = build / f"dropbear-{version}"
    if not src.exists():
        untar(tb, build)
    # Key-auth only: disable password auth so we don't need crypt() in the
    # static cross build, and keep pubkey auth (our test key is authorized).
    (src / "localoptions.h").write_text(
        "#define DROPBEAR_SVR_PASSWORD_AUTH 0\n"
        "#define DROPBEAR_SVR_PUBKEY_AUTH 1\n"
        "#define DROPBEAR_SVR_MULTIUSER 1\n"
        "/* ed25519-only: avoid slow RSA/ECDSA keygen on the emulated ARM926. */\n"
        "#define DROPBEAR_RSA 0\n"
        "#define DROPBEAR_ECDSA 0\n"
        "#define DROPBEAR_ED25519 1\n")
    run(["./configure", f"--host={CROSS.rstrip('-')}", f"CC={CC}",
         "--disable-zlib", "--disable-lastlog", "--disable-utmp",
         "--disable-wtmp", "--disable-pututline", "--disable-pututxline"],
        cwd=src)
    # Force a fully static binary — the initramfs has no dynamic loader/libc,
    # so a dynamically-linked dropbear would fail with "not found". (STATIC=1
    # alone left it dynamic, so also set LDFLAGS=-static; clean to force relink.)
    run(["make", "clean"], cwd=src)
    run(["make", f"-j{os.cpu_count()}", "PROGRAMS=dropbear dropbearkey",
         "MULTI=1", "STATIC=1", "LDFLAGS=-static"], cwd=src)
    return src / "dropbearmulti"


def gen_test_key(out: Path) -> str:
    """Generate a throwaway ed25519 keypair; return the public key text."""
    priv = out / "id_kgpe_d16_test"
    if priv.exists():
        priv.unlink()
    (out / "id_kgpe_d16_test.pub").unlink(missing_ok=True)
    run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "kgpe-d16-ci-test",
         "-f", str(priv)])
    return (out / "id_kgpe_d16_test.pub").read_text().strip()


def build_rootfs(rootfs: Path, bb_src: Path, dropbearmulti: Path, init: Path,
                 pubkey: str):
    for d in ("bin", "sbin", "usr/bin", "usr/sbin", "dev", "proc", "sys",
              "etc/dropbear", "tmp", "run", "var/log", "root/.ssh"):
        (rootfs / d).mkdir(parents=True, exist_ok=True)
    # Install BusyBox + applet symlinks via 'make install' — a host-side script
    # (busybox.mkll) that generates busybox.links and the symlink tree without
    # executing the cross-compiled ARM binary.
    run(["make", "-C", str(bb_src), f"CONFIG_PREFIX={rootfs}", "install"],
        env={**os.environ, "ARCH": "arm", "CROSS_COMPILE": CROSS})
    shutil.copy2(dropbearmulti, rootfs / "sbin/dropbearmulti")
    os.chmod(rootfs / "sbin/dropbearmulti", 0o755)
    for tool in ("dropbear", "dropbearkey"):
        (rootfs / "sbin" / tool).symlink_to("dropbearmulti")
    shutil.copy2(init, rootfs / "init")
    os.chmod(rootfs / "init", 0o755)
    (rootfs / "etc/passwd").write_text(
        "root:x:0:0:root:/root:/bin/sh\n")
    (rootfs / "etc/group").write_text("root:x:0:\n")
    (rootfs / "etc/shadow").write_text("root::0:0:99999:7:::\n")
    (rootfs / "root/.ssh/authorized_keys").write_text(pubkey + "\n")
    # dropbear refuses a home dir / .ssh / authorized_keys writable by group or
    # other. mkdir leaves /root at 0775 (umask 002), so tighten it.
    os.chmod(rootfs / "root", 0o755)
    os.chmod(rootfs / "root/.ssh", 0o700)
    os.chmod(rootfs / "root/.ssh/authorized_keys", 0o600)


def pack(rootfs: Path, out: Path):
    cpio = out / "initramfs.cpio"
    names = subprocess.run(["find", "."], cwd=rootfs, capture_output=True,
                           text=True, check=True).stdout
    with open(cpio, "wb") as f:
        # --owner=0:0 makes every file root-owned; dropbear refuses an
        # authorized_keys (or ~/.ssh, or home) not owned by the target user.
        subprocess.run(["cpio", "--null", "-o", "--format=newc", "--owner=0:0"],
                       cwd=rootfs, input=names.replace("\n", "\0").encode(),
                       stdout=f, check=True)
    with open(cpio, "rb") as fi, open(out / "initramfs.cpio.gz", "wb") as fo:
        subprocess.run(["gzip", "-9", "-c"], stdin=fi, stdout=fo, check=True)
    cpio.unlink()
    run(["mkimage", "-A", "arm", "-O", "linux", "-T", "ramdisk", "-C", "gzip",
         "-n", "KGPE-D16 BMC initramfs", "-d", str(out / "initramfs.cpio.gz"),
         str(out / "uInitrd-kgpe-d16")])


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--busybox-version", default="1.37.0")
    ap.add_argument("--dropbear-version", default="2024.86")
    ap.add_argument("--output-dir", default=str(here / "out"))
    ap.add_argument("--build-dir", default=str(here / "build"))
    args = ap.parse_args()

    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    build = Path(args.build_dir); build.mkdir(parents=True, exist_ok=True)

    busybox = build_busybox(args.busybox_version, build)
    dropbearmulti = build_dropbear(args.dropbear_version, build)
    pubkey = gen_test_key(out)

    rootfs = build / "rootfs"
    if rootfs.exists():
        shutil.rmtree(rootfs)
    build_rootfs(rootfs, busybox, dropbearmulti, here / "init", pubkey)
    pack(rootfs, out)
    print("\nInitramfs artifacts in", out)
    run(["ls", "-la", str(out)])


if __name__ == "__main__":
    main()

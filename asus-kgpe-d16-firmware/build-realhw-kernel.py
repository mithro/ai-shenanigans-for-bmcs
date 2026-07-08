#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Rebuild the modern (6.6.70) KGPE-D16 kernel for the REAL board, adding NFS root.

Reuses the kernel source tree from the d16-qemu QEMU-firmware work (already has the
AST2050 clock patch + the kgpe-d16 DTS applied) and merges:
    aspeed_g4_defconfig + kgpe-d16.config + kgpe-d16-realhw.config
Output: tmp/uImage-kgpe-d16-realhw + the DTB, ready to TFTP-boot over P2A.
"""
import os, subprocess, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                                   # culvert-g3-port worktree
WT = os.path.dirname(ROOT)                                     # .worktrees/
QF = os.path.join(WT, "d16-qemu", "asus-kgpe-d16-firmware", "qemu-firmware")
SRC = os.path.join(QF, "kernel", "linux")
FRAG_QEMU = os.path.join(QF, "kernel", "kgpe-d16.config")
FRAG_HW = os.path.join(HERE, "kernel", "kgpe-d16-realhw.config")
OUT = os.path.join(ROOT, "tmp")
ENV = {**os.environ, "ARCH": "arm", "CROSS_COMPILE": "arm-linux-gnueabi-"}


def run(cmd, **kw):
    print(f"+ {cmd if isinstance(cmd, str) else ' '.join(cmd)}", flush=True)
    subprocess.run(cmd, shell=isinstance(cmd, str), check=True, env=ENV, cwd=SRC, **kw)


def main():
    if not os.path.isdir(SRC):
        sys.exit(f"kernel source not found at {SRC} -- run the qemu-firmware build first")
    nproc = str(os.cpu_count() or 4)
    run(["make", "aspeed_g4_defconfig"])
    run(["scripts/kconfig/merge_config.sh", "-m", ".config", FRAG_QEMU, FRAG_HW])
    run(["make", "olddefconfig"])
    # confirm the NFS-root options actually made it in
    cfg = open(os.path.join(SRC, ".config")).read()
    for opt in ("CONFIG_ROOT_NFS=y", "CONFIG_IP_PNP=y", "CONFIG_NFS_FS=y"):
        if opt not in cfg:
            sys.exit(f"[!] {opt} did not survive olddefconfig -- check deps")
    print("[ok] NFS-root config present", flush=True)
    run(["make", f"-j{nproc}", "zImage", "dtbs"])
    run(["make", f"-j{nproc}", "LOADADDR=0x40008000", "uImage"])
    os.makedirs(OUT, exist_ok=True)
    shutil.copy(os.path.join(SRC, "arch/arm/boot/uImage"),
                os.path.join(OUT, "uImage-kgpe-d16-realhw"))
    shutil.copy(os.path.join(SRC, "arch/arm/boot/dts/aspeed/aspeed-bmc-asus-kgpe-d16.dtb"),
                os.path.join(OUT, "aspeed-bmc-asus-kgpe-d16-realhw.dtb"))
    print(f"[done] {OUT}/uImage-kgpe-d16-realhw", flush=True)


if __name__ == "__main__":
    main()

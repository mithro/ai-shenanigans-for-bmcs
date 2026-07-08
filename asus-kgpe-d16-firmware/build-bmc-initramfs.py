#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Rebuild the Raptor BMC initramfs to bundle the static ARM `culvert` and set
eth0 for the real-hardware BMC network (192.168.66.2), for a one-shot
TFTP-boot -> Linux shell with culvert in-hand (no spispy/JTAG).

Starts from the QEMU-verified raptor cpio.gz, uses fakeroot to preserve the static
/dev nodes (console, ttyS0/1) the 2.6.28 kernel needs (it predates devtmpfs).

  uv run build-bmc-initramfs.py \
      --base   .../raptor-out/uInitrd-raptor.cpio.gz \
      --culvert .../culvert/build-arm/culvert-arm-static \
      --out    tmp/uInitrd-culvert.cpio.gz
"""
import argparse, os, shutil, subprocess, sys, textwrap

# eth0 config for the real BMC network (eth-bmc side is 192.168.66.1 on the Pi).
NET_PATCH = textwrap.dedent("""\
    # Real BMC network (eth-bmc <-> Pi 192.168.66.1). Overrides the QEMU 10.0.2.x.
    ip addr add 192.168.66.2/24 dev eth0
    ip route add default via 192.168.66.1 2>&1 || true
""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="raw cpio.gz to start from")
    ap.add_argument("--culvert", required=True, help="static ARM culvert binary")
    ap.add_argument("--out", required=True, help="output cpio.gz")
    ap.add_argument("--work", default=None)
    args = ap.parse_args()

    work = args.work or os.path.join(os.path.dirname(os.path.abspath(args.out)), "initrd-build")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    rootfs = os.path.join(work, "rootfs")
    os.makedirs(rootfs)

    # 1. decompress + extract under fakeroot (preserves device nodes + perms)
    cpio = os.path.join(work, "base.cpio")
    with open(cpio, "wb") as f:
        subprocess.run(["gzip", "-dc", args.base], stdout=f, check=True)
    subprocess.run(f"cd {rootfs} && fakeroot cpio -idm < {cpio}", shell=True, check=True,
                   capture_output=True)

    # 2. drop in culvert
    os.makedirs(os.path.join(rootfs, "usr/bin"), exist_ok=True)
    shutil.copy(args.culvert, os.path.join(rootfs, "usr/bin/culvert"))
    os.chmod(os.path.join(rootfs, "usr/bin/culvert"), 0o755)

    # 3. patch init: swap the QEMU 10.0.2.x eth0 config for the real BMC net
    init = os.path.join(rootfs, "init")
    src = open(init).read()
    src = src.replace("ip addr add 10.0.2.15/24 dev eth0\n"
                      "ip route add default via 10.0.2.2 2>&1 || true\n", NET_PATCH)
    # announce culvert so the operator sees it's present
    src = src.replace('echo "BMC-READY"',
                      'echo "culvert: $(culvert --help >/dev/null 2>&1 && echo present)"\n'
                      'echo "BMC-READY"')
    open(init, "w").write(src)

    # 4. repack (fakeroot preserves nodes/perms), newc format, then gzip
    out_cpio = os.path.join(work, "out.cpio")
    subprocess.run(
        f"cd {rootfs} && find . | fakeroot cpio -o -H newc > {out_cpio}",
        shell=True, check=True, capture_output=True)
    with open(out_cpio, "rb") as fi, open(args.out, "wb") as fo:
        subprocess.run(["gzip", "-9"], stdin=fi, stdout=fo, check=True)

    sz = os.path.getsize(args.out)
    print(f"[*] wrote {args.out}  ({sz} bytes = {sz:#x})")
    print(f"    boot: linux-boot.py --initrd {os.path.basename(args.out)} "
          f"--cmdline-initrd {sz:#x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

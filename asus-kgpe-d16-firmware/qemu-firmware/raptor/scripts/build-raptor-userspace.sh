#!/bin/sh
# Build the C3 (Raptor 2.6.28) initramfs: BusyBox + dropbear static against
# MUSL, repacked with static /dev nodes.
#
# Why musl: the C2 userspace is static modern glibc (--enable-kernel=3.2) and
# refuses to run on the 2.6.28 kernel (kernel-version gate + missing pre-3.2
# syscall fallbacks -> silent "Attempted to kill init!"). musl has no version
# gate and conservative syscalls, so the *identical* BusyBox/dropbear sources
# build and run on the old kernel. The reusable initramfs/build.py already takes
# CROSS_COMPILE, so we just point it at a musl cross toolchain and then repack
# with mkinitramfs-raptor.py (build.py's cpio has no device nodes; 2.6.28 has no
# devtmpfs to create them).
#
# Output: $OUT/uInitrd-raptor  (+ the throwaway SSH test key from build.py)
set -e

here=$(cd "$(dirname "$0")" && pwd)
qf="$here/../.."                       # qemu-firmware/
: "${TOOLS:=$qf/raptor/tools}"
: "${OUT:=$qf/raptor/out}"
: "${MUSL_URL:=https://musl.cc/arm-linux-musleabi-cross.tgz}"
mkdir -p "$TOOLS" "$OUT"

# 1. musl cross toolchain (soft-float EABI, matches the ARM926EJ-S target).
musl_bin="$TOOLS/arm-linux-musleabi-cross/bin"
if [ ! -x "$musl_bin/arm-linux-musleabi-gcc" ]; then
    echo "fetching musl toolchain: $MUSL_URL"
    # musl.cc is frequently flaky (intermittent connection resets / 5xx), which
    # was intermittently failing C3 with wget exit 4 (network failure). Retry
    # hard and show each attempt (drop -q so the diagnostics stay visible per the
    # repo's fail-loud convention); wget still errors out loudly if it ultimately
    # can't fetch, rather than silently continuing with no toolchain.
    wget -nv --tries=8 --waitretry=15 --timeout=45 --retry-connrefused \
        -O "$TOOLS/musl.tgz" "$MUSL_URL"
    tar xzf "$TOOLS/musl.tgz" -C "$TOOLS"
    rm -f "$TOOLS/musl.tgz"
fi
export PATH="$musl_bin:$PATH"

# 2. Build the rootfs (BusyBox + dropbear + test key) with the musl toolchain.
CROSS_COMPILE=arm-linux-musleabi- uv run "$qf/initramfs/build.py" \
    --output-dir "$OUT" --build-dir "$qf/initramfs/build"

# 3. Repack that rootfs into a uInitrd WITH static /dev nodes (console/null/
#    urandom/ptmx/ttyS0-1) so the pre-devtmpfs 2.6.28 kernel gives PID 1 stdio.
uv run "$here/mkinitramfs-raptor.py" \
    --rootfs "$qf/initramfs/build/rootfs" \
    --init "$qf/initramfs/init" \
    --out "$OUT/uInitrd-raptor"
echo "RAPTOR_USERSPACE_BUILD_DONE: $OUT/uInitrd-raptor"
ls -la "$OUT/uInitrd-raptor"

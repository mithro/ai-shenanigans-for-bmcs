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
# Fallback mirror: the musl.cc apex is periodically unreachable from GitHub-hosted
# runners (plain IPv4 "Connection timed out" persisting for hours -- C3 failure
# signature 2026-07-21). more.musl.cc is a separately-hosted mirror that serves a
# toolchain with the SAME internal layout (arm-linux-musleabi-cross/bin/... --
# verified 2026-07-22; a different gcc build, harmless for a static BusyBox/dropbear
# that the C3 boot then validates end-to-end) and stays up when the apex flakes.
: "${MUSL_URL_FALLBACK:=https://more.musl.cc/10/x86_64-linux-musl/arm-linux-musleabi-cross.tgz}"
mkdir -p "$TOOLS" "$OUT"

# 1. musl cross toolchain (soft-float EABI, matches the ARM926EJ-S target).
musl_bin="$TOOLS/arm-linux-musleabi-cross/bin"
if [ ! -x "$musl_bin/arm-linux-musleabi-gcc" ]; then
    # Try the primary (musl.cc) then the fallback mirror (more.musl.cc), stopping
    # at the first that downloads. Force IPv4 (-4): GitHub-hosted runners carry an
    # IPv6 address but no working IPv6 *route*, so resolving an AAAA record and
    # connecting over IPv6 fails hard with "Network is unreachable" (wget exit 4)
    # -- the 2026-07-18 C3 failure signature. Retry hard and show each attempt (no
    # -q, per fail-loud). The `if wget` wrapper consumes wget's non-zero exit so
    # `set -e` doesn't abort before we can try the next mirror.
    fetched=""
    for url in "$MUSL_URL" "$MUSL_URL_FALLBACK"; do
        echo "fetching musl toolchain: $url"
        if wget -4 -nv --tries=8 --waitretry=15 --timeout=45 --retry-connrefused \
                -O "$TOOLS/musl.tgz" "$url"; then
            fetched="$url"
            break
        fi
        echo "musl toolchain fetch failed from $url; trying next mirror" >&2
    done
    [ -n "$fetched" ] || { echo "ERROR: all musl toolchain mirrors failed" >&2; exit 1; }
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

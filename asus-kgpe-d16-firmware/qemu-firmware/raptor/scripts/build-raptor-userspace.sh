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
# musl cross-toolchain sources, tried in order -- one "url topdir prefix" per line
# (MUSL_SOURCES overridable). The ARM926EJ-S is ARMv5TE soft-float, so every source
# is a soft-float EABI (non-hf) musl gcc:
#   * musl.cc apex + more.musl.cc mirror -- but the whole musl.cc family is
#     periodically unreachable from GitHub-hosted runners (IPv4 "Connection timed
#     out" for hours; BOTH timed out on CI run 29862701322, 2026-07-22).
#   * cross-tools/musl-cross github release -- served from
#     release-assets.githubusercontent.com, which runners ALWAYS reach, so this is
#     the reliable fallback. Verified 2026-07-22: __ARM_ARCH 5 + __SOFTFP__ (runs
#     on the ARM926EJ-S); its prefix (arm-unknown-linux-musleabi-) and dir differ
#     from musl.cc's, hence the per-source topdir + prefix columns below.
: "${MUSL_SOURCES:=$(cat <<'SRCS'
https://musl.cc/arm-linux-musleabi-cross.tgz arm-linux-musleabi-cross arm-linux-musleabi-
https://more.musl.cc/10/x86_64-linux-musl/arm-linux-musleabi-cross.tgz arm-linux-musleabi-cross arm-linux-musleabi-
https://github.com/cross-tools/musl-cross/releases/download/20260515/arm-unknown-linux-musleabi.tar.xz arm-unknown-linux-musleabi arm-unknown-linux-musleabi-
SRCS
)}"
mkdir -p "$TOOLS" "$OUT"

# 1. Fetch a musl cross toolchain from the first working source (or reuse an
#    already-extracted one). CROSS_COMPILE is set from whichever source wins, so
#    the differing prefixes (arm-linux-musleabi- vs arm-unknown-linux-musleabi-)
#    are handled transparently. Force IPv4 (-4): GitHub-hosted runners carry an
#    IPv6 address but no working IPv6 *route*, so an AAAA connect fails hard with
#    "Network is unreachable" (wget exit 4). Retry hard, show each attempt (no -q,
#    per fail-loud); the `wget && tar` wrapper consumes the non-zero exit so
#    `set -e` doesn't abort before the next source is tried. `tar xf` auto-detects
#    gzip/xz. Fed by heredoc (not a pipe) so the loop runs in THIS shell and the
#    winning musl_bin/CROSS_COMPILE survive.
musl_bin=""
CROSS_COMPILE=""
while read -r url topdir prefix; do
    [ -n "$url" ] || continue
    tc_bin="$TOOLS/$topdir/bin"
    if [ ! -x "$tc_bin/${prefix}gcc" ]; then
        echo "fetching musl toolchain: $url"
        if wget -4 -nv --tries=8 --waitretry=15 --timeout=45 --retry-connrefused \
                -O "$TOOLS/musl.tar" "$url" && tar xf "$TOOLS/musl.tar" -C "$TOOLS"; then
            rm -f "$TOOLS/musl.tar"
        else
            rm -f "$TOOLS/musl.tar"
            echo "musl toolchain fetch/extract failed from $url; trying next source" >&2
            continue
        fi
    fi
    if [ -x "$tc_bin/${prefix}gcc" ]; then
        musl_bin="$tc_bin"
        CROSS_COMPILE="$prefix"
        break
    fi
    echo "fetched $url but ${prefix}gcc missing after extract; trying next source" >&2
done <<END
$MUSL_SOURCES
END
[ -n "$CROSS_COMPILE" ] || { echo "ERROR: all musl toolchain sources failed" >&2; exit 1; }
export PATH="$musl_bin:$PATH"
export CROSS_COMPILE
echo "using musl toolchain: ${CROSS_COMPILE}gcc  ($musl_bin)"

# 2. Build the rootfs (BusyBox + dropbear + test key) with the musl toolchain.
#    CROSS_COMPILE was exported above from the source that won.
uv run "$qf/initramfs/build.py" \
    --output-dir "$OUT" --build-dir "$qf/initramfs/build"

# 3. Repack that rootfs into a uInitrd WITH static /dev nodes (console/null/
#    urandom/ptmx/ttyS0-1) so the pre-devtmpfs 2.6.28 kernel gives PID 1 stdio.
uv run "$here/mkinitramfs-raptor.py" \
    --rootfs "$qf/initramfs/build/rootfs" \
    --init "$qf/initramfs/init" \
    --out "$OUT/uInitrd-raptor"
echo "RAPTOR_USERSPACE_BUILD_DONE: $OUT/uInitrd-raptor"
ls -la "$OUT/uInitrd-raptor"

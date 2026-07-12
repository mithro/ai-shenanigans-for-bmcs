# Cross-building a static ARM `culvert` for the AST2050 BMC

For the in-band step (running culvert *on* the BMC under Linux), culvert must be a
**statically-linked ARM binary** — the Raptor initramfs is musl-based, so a
glibc-dynamic build won't run, but a fully static binary has no libc dependency.

Toolchain: Debian `arm-linux-gnueabi-` (soft-float — correct for the FPU-less
ARM926EJ-S). Cross file: `arm-linux-gnueabi-cross.ini` (this dir).

```sh
cd asus-kgpe-d16-firmware/culvert          # the vendored mithro/culvert submodule
meson setup build-arm \
    --cross-file ../culvert-arm/arm-linux-gnueabi-cross.ini \
    --default-library static \
    -Ddtc:tools=false -Ddtc:tests=false -Ddtc:static-build=true
ninja -C build-arm src/culvert
arm-linux-gnueabi-strip build-arm/src/culvert -o build-arm/culvert-arm-static
```

Why each dtc option (culvert bundles dtc as a subproject for libfdt):
- `-Ddtc:tests=false` — dtc's test binaries would need to *run* (an exe_wrapper /
  qemu-arm we don't have) during the cross build.
- `-Ddtc:tools=false` — skip the dtc CLI tools (not needed; the `dtc` *program* used
  to compile the embedded `.dts` is found natively on PATH).
- `-Ddtc:static-build=true` — makes `libfdt` link its **static** lib (`both_libraries`
  otherwise links the `.so`, which breaks a `-static` final link).

The cross file also sets `ld = 'arm-linux-gnueabi-ld'` so the devicetree-blob→object
step (`ld -r -b binary g3.dtb`) emits an **ARM** object, not a native x86 one.

Result: `build-arm/culvert-arm-static` — ELF 32-bit ARM EABI5, statically linked.

## ⚠️ glibc-static does NOT run on the 2.6.28 kernel — use musl

The Debian `arm-linux-gnueabi-` toolchain's glibc is built with a **minimum kernel
of 3.2.0** (`file` shows `for GNU/Linux 3.2.0`). The Raptor BMC kernel is **2.6.28**,
so *any* glibc-static binary — even a hello-world — **segfaults** at startup
(hardware-verified: `rc=139`). Build against **musl** instead (no kernel floor):

- Toolchain: `.worktrees/d16-qemu/tmp/arm-linux-musleabi-cross` (the Raptor userspace
  toolchain), cross file `arm-linux-musleabi-cross.ini.example`.
- musl lacks `argp.h` (a glibc extension culvert's `cmd.h` uses), so build
  **argp-standalone** with the same musl toolchain and add its include + `libargp.a`
  to `c_args`/`c_link_args` (see the `.example` cross file).

```sh
# 1. argp-standalone (meson), musl:
meson setup argp/build-musl --cross-file arm-linux-musleabi-cross.ini --default-library static && ninja -C argp/build-musl
# 2. culvert, musl (add -I<argp> to c_args, -L<argp/build> -largp to c_link_args):
meson setup build-musl --cross-file arm-linux-musleabi-cross.ini --default-library static \
    -Ddtc:tools=false -Ddtc:tests=false -Ddtc:static-build=true
ninja -C build-musl src/culvert
arm-linux-musleabi-strip build-musl/src/culvert -o build-musl/culvert-musl-static   # ~229 KB
```

## ✅ In-band result (hardware-verified 2026-07-08)

TFTP'd `culvert-musl-static` into the running BMC Linux (`tftp -g -r culvert
192.168.66.1`) and ran it **on the AST2050**, no spispy/JTAG:

```
~ # ./culvert probe via devmem          -> ilpc: Disabled   EXIT=0
~ # ./culvert devmem read 0x1e6e207c    -> 0x1e6e207c: 0x00000202   EXIT=0   (SCU7C = AST2050 ID)
```

So culvert's **devmem bridge is hardware-verified in-band** — it opens `/dev/mem`
(`mknod /dev/mem c 1 1` on the static-node initramfs), identifies the SoC, selects
the `g3` devicetree, binds the SoC drivers, and reads registers correctly. `sfc`
flash-dump has no data to return on this bench — the SMC flash window `0x14000000`
reads `0` even in-band (no readable boot flash; the board is in its dead-firmware
state), which is a rig limitation, not a culvert gap.

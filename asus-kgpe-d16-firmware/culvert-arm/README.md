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
TFTP it into the running BMC Linux and run `culvert ... devmem` in-band.

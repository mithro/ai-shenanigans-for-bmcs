# Result — Redfish OpenBMC over NFS on the faithful AST2050, at 64 MB

**2026-07-10: PASS.** The stripped Redfish-only OpenBMC image
(`../obmc-phosphor-image-ast2050-redfish.bb`) boots over NFS on the faithful
`-M kgpe-d16-bmc` QEMU machine at the AST2050's real **64 MB** DDR2 and answers
the Redfish API.

`redfish-64mb-boot.log` is the full serial + harness transcript (has systemd ANSI
colour codes). Key evidence:

```
CPU: ARM926EJ-S [41069265] revision 5 (ARMv5TEJ)          # faithful G3 core
Zone ranges: Normal [mem 0x0000000040000000-0x0000000043ffffff]   # exactly 64 MB
VFS: Mounted root (nfs filesystem) ...                     # NFS root over FTGMAC100
systemd[1]: ... Reached target Basic System
Started bmcweb server                                      # the Redfish daemon
... login:                                                # full boot, no OOM

[redfish] HTTP 200 from /redfish/v1:
{ "@odata.id": "/redfish/v1", "RedfishVersion": "1.17.0", "Name": "Root Service" }

PHASE 6b RESULT: PASS — real OpenBMC Redfish over NFS on the faithful AST2050 machine
```

- **0** out-of-memory / oom-kill events across the whole boot — it genuinely fits 64 MB.
- Boot kernel: our modern AST2050 kernel (6.6.70) with `mem=64M` pinning the RAM to
  the faithful size; rootfs: the ARMv5TE (`Tag_CPU_arch: v5TE`) phosphor/bmcweb image
  served over NFSv3.

Reproduce:
```sh
# after building obmc-phosphor-image-ast2050-redfish for quanta-q71l (see ../README.md):
../qemu-firmware/scripts/stage-openbmc-nfsroot.sh <image>.squashfs-xz /export/openbmc-kgpe-d16
../qemu-firmware/scripts/openbmc-nfsroot-test.py \
    --qemu ../qemu-firmware/qemu/build/qemu-system-arm \
    --kernel zImage-kgpe-d16 --dtb aspeed-bmc-asus-kgpe-d16.dtb \
    --nfsroot 10.0.2.2:/export/openbmc-kgpe-d16 --mem 64
```

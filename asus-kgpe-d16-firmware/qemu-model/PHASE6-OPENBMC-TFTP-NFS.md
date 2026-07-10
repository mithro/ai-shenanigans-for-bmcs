# Phase 6 — OpenBMC booting via TFTP + NFS on the faithful AST2050 machine

The program's headline goal: a modern OpenBMC system that **TFTP-loads its kernel and
mounts its root filesystem over NFS**, inside the faithful `-M kgpe-d16-bmc` QEMU —
mirroring how the fpgas.online RPis are served. This runs on the *modern-kernel* path,
which already boots to SSH and tolerates the faithful SCU (the legacy-boot oracle stays
green independently).

## Boot chain

```
U-Boot ──tftp──► zImage + aspeed-bmc-asus-kgpe-d16.dtb   (QEMU slirp built-in TFTP)
   │
   └─ bootm ──► Linux (FTGMAC100 up) ── ip=dhcp (slirp 10.0.2.15) ──►
        root=/dev/nfs nfsroot=10.0.2.2:/export/rootfs,vers=3,tcp ──►
        NFS mount over the FTGMAC100 ──► OpenBMC userspace (systemd/bmcweb/Redfish)
```

`-kernel` (direct) also works for the kernel stage; the U-Boot `tftp` stage is what makes
it a true netboot. slirp's gateway `10.0.2.2` proxies to the host, where the NFS server
runs.

## Pieces

1. **Kernel** — `kernel/kgpe-d16.config` + **`kernel/kgpe-d16-nfsroot.config`** (added):
   `IP_PNP{,_DHCP}`, `NFS_FS`, `NFS_V3`, `ROOT_NFS`, `SUNRPC`, `LOCKD`. Build merges both
   fragments onto `aspeed_g4_defconfig`. *(config is committed; kernel rebuild is a CI step.)*
2. **TFTP** — QEMU slirp: `-netdev user,id=n,tftp=<dir>,bootfile=zImage,...`. The kernel +
   DTB are served from `<dir>`; U-Boot `tftp`s them. No external TFTP server needed.
3. **NFS server** — the guest reaches the host NFS server at **10.0.2.2** through slirp
   (guest→gateway = host). Requires a host NFS server (`nfs-kernel-server`, or a userspace
   `unfsd`). **The dev sandbox has no NFS tooling**, so this is a **CI job** (ubuntu-latest
   has apt): install the server, export `/export/rootfs` (localhost, insecure, no_root_squash),
   boot QEMU, assert the guest reaches a login/shell + a service check. Same shape as the
   existing C1–C4 boot jobs in `d16-qemu-stack.yml`.
4. **Rootfs** — two stages:
   - **6a (transport proof):** a BusyBox rootfs (reuse the `initramfs/` contents as an NFS
     export) → prove the machine TFTP-boots the kernel and NFS-mounts root to a shell. This
     validates the netboot/NFS transport on the *faithful* machine with the FTGMAC100 model.
   - **6b (OpenBMC):** a modern OpenBMC rootfs. Modern OpenBMC ran in QEMU on `romulus`
     (AST2500, PR #22); an **AST2050 (`kgpe-d16`) Yocto machine layer** is needed to build an
     image for this board — a large, separate effort. Interim: serve the OpenBMC *romulus*
     userspace (glibc/armv?) or a phosphor-subset over NFS to exercise bmcweb/Redfish on the
     faithful kernel, then converge on a native AST2050 image.

## Status / next steps

- [x] NFS-root kernel config fragment (`kgpe-d16-nfsroot.config`).
- [ ] TFTP boot: verify U-Boot `tftp` of the kernel via slirp `tftp=` (local, feasible).
- [ ] NFS rootfs export from the BusyBox initramfs contents.
- [ ] CI job `boot-nfsroot` in `d16-qemu-stack.yml`: apt-install NFS server → export → boot
      → assert shell over NFS. (**6a milestone.**)
- [ ] OpenBMC rootfs over NFS (**6b** — needs the AST2050 Yocto machine or a served subset).

## Why this is oracle-safe

Phase 6 rides the *modern-kernel* path (a new boot job); it does not change the legacy
C1–C4 boots. The FTGMAC100 register/DMA path is already register-faithful and proven
(eth0 comes up 100M/full in C2), so netboot uses the existing NIC model.

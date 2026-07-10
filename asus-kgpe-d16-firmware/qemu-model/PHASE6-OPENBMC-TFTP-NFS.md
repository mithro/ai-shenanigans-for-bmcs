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

- [x] NFS-root kernel config fragment (`kgpe-d16-nfsroot.config`) — now also enables
      `DEVTMPFS_MOUNT` (no initramfs to mknod `/dev/console` before init over NFS).
- [x] Kernel build merges the fragment (`scripts/build-kernel.sh`), so the single kernel
      artifact carries NFS/IP_PNP (dormant for the C2/C3 initramfs boots).
- [x] NFS rootfs export: `initramfs/build.py` emits `nfs-rootfs.tar` (root-owned tree),
      uploaded with the initramfs artifact. Verified locally (ownership/symlinks/modes).
- [x] NFS-boot harness `scripts/nfsboot-test.py`: boots `-M kgpe-d16-bmc` with
      `root=/dev/nfs ip=dhcp nfsroot=10.0.2.2:/export/...,vers=3,tcp,nolock init=/init`;
      PASS = kernel "Mounted root (nfs filesystem" **and** userspace "BMC-READY", with an
      optional SSH-over-NFS check.
- [x] CI job **`boot-nfsroot` (C5)** in `d16-qemu-stack.yml`: apt-installs
      `nfs-kernel-server`, extracts the tar to `/export/kgpe-d16-rootfs`, exports it
      `*(rw,no_root_squash,insecure)` (insecure: slirp SNATs the guest to a 127.0.0.1
      high port), starts rpcbind+nfsd, then runs the harness. (**6a milestone — validated
      in CI since the dev sandbox has no NFS tooling and external NFS servers can't be built.**)
- [ ] OpenBMC rootfs over NFS (**6b** — needs the AST2050 Yocto machine or a served subset;
      note ARMv5 (ARM926) vs the AST2500 `romulus` OpenBMC's ARMv6, so romulus binaries
      can't be reused directly — a native `kgpe-d16` machine layer is required).

## Why 6a is the meaningful milestone

6a proves the **exact transport** OpenBMC will use — the faithful AST2050 QEMU pulls its
kernel over the network and mounts `/` over NFSv3, running real userspace (BusyBox+dropbear,
SSH-reachable) entirely from the NFS export, over the register-faithful FTGMAC100. 6b then
only swaps the *contents* of that export for an OpenBMC image; the machine/kernel/transport
are already proven identical to how the hardware netboots.

## Why this is oracle-safe

Phase 6 rides the *modern-kernel* path (a new boot job); it does not change the legacy
C1–C4 boots. The FTGMAC100 register/DMA path is already register-faithful and proven
(eth0 comes up 100M/full in C2), so netboot uses the existing NIC model.

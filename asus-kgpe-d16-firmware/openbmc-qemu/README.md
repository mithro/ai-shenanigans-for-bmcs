# Modern OpenBMC + Redfish in QEMU (Track A)

Per @mithro's "both — QEMU build + NIC in parallel": develop the modern OpenBMC +
**Redfish** stack in QEMU (full observability, testable) in parallel with the real-HW
NIC deep-dive. The phosphor/bmcweb userspace is SoC-agnostic, so the same image is the
basis for running on the real AST2050 (over the NFS root) once the NIC lands.

## Build (multi-hour Yocto build)
```sh
git clone https://github.com/openbmc/openbmc.git ~/openbmc
cd ~/openbmc
. setup romulus            # or palmetto (ast2400, ARM926 -- closest SoC to the AST2050)
bitbake obmc-phosphor-image
# image -> build/romulus/tmp/deploy/images/romulus/obmc-phosphor-image-romulus.static.mtd
```
Host deps needed: `chrpath diffstat gawk lz4 zstd file` (+ the usual gcc/python3/git).
Machine choice: **romulus** (ast2500) has the fullest QEMU + Redfish support;
**palmetto** (ast2400, ARM926EJ-S) is the closest SoC to the AST2050 (G3). Both share
the same phosphor/bmcweb userspace.

## Run + reach Redfish
```sh
asus-kgpe-d16-firmware/openbmc-qemu/run-openbmc-qemu.sh
# Redfish:  curl -k https://localhost:2443/redfish/v1
# login:    curl -k -u root:0penBmc https://localhost:2443/redfish/v1/Systems
# SSH:      ssh -p 2222 root@localhost   (pw 0penBmc)
```

## Path to the real AST2050
1. Prove OpenBMC + Redfish run + answer in QEMU (this dir).
2. Build/adapt an **ast2400-class kgpe-d16 machine** (device tree = our
   `dts/aspeed-bmc-asus-kgpe-d16-realhw.dts` + the AST2050 clock patch) so the image
   targets the real board.
3. Serve the OpenBMC rootfs over **NFS root** (Pi `/srv/nfs/bmc`) with our modern
   AST2050 kernel — needs the eth0 RMII-TX fix first (see `../MODERN-KERNEL-STATUS.md`,
   `../NIC-MAC-REGISTER-COMPARISON.md`).

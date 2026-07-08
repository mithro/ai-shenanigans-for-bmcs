# Booting Linux on the AST2050 BMC via TFTP (over P2A, no spispy/JTAG)

Continues the P2A boot chain (`P2A-DRAM-BOOT-SEQUENCE.md` → `RAPTOR-UBOOT-BUILD.md`):
once U-Boot is live at the `boot#` prompt, it TFTP-loads a kernel + initramfs from
the Pi and boots Linux — the environment in which culvert's remaining in-band pieces
(`devmem`, `sfc` dump, `console`) can finally be exercised.

## The network path (BMC ↔ Pi) — WORKS

The AST2050's on-chip NIC (`aspeednic#0` in U-Boot, MAC `1e:b9:ba:50:cc:b9`) is wired
to the Pi through a USB-Ethernet adapter that udev names **`eth-bmc`** (MAC
`00:e0:4c:68:00:fc`; `/etc/systemd/network/10-eth-bmc.link`). This is a **separate**
link from `eth-host` (the x86 PXE network, `192.168.77.0/24`).

Pi side (run on `asus-bmc`):
```sh
sudo ip addr add 192.168.66.1/24 dev eth-bmc
sudo ip link set eth-bmc up
# TFTP-only dnsmasq bound to eth-bmc (port=0 => no DNS; no dhcp-range => no DHCP,
# so it won't clash with the host-PXE dnsmasq on eth-host):
sudo dnsmasq --port=0 --enable-tftp --tftp-root=/srv/tftp-bmc \
     --interface=eth-bmc --bind-interfaces --tftp-no-blocksize \
     --pid-file=/run/dnsmasq-bmctftp.pid --log-facility=/var/log/dnsmasq-bmctftp.log
```
U-Boot side (static IP; the aspeednic driver works):
```
setenv ipaddr 192.168.66.2
setenv serverip 192.168.66.1
ping 192.168.66.1          # -> "host 192.168.66.1 is alive"   ✅
```

## TFTP into DRAM — WORKS

```
tftp 0x41000000 uImage-raptor      # 1.77 MB @ ~566 KiB/s  ✅
tftp 0x42000000 uInitrd-kgpe-d16   # ~955 KB
```
Kernel + initrd staged in `/srv/tftp-bmc/` on the Pi. Both are from the QEMU-verified
Raptor stack (`.worktrees/d16-qemu/tmp/raptor-out/`): `uImage-raptor` = Raptor AST2050
**Linux 2.6.28** (uncompressed uImage, load/entry `0x40008000`); `uInitrd-kgpe-d16` =
a busybox initramfs (`/init` → serial shell; has `devmem`, `tftp`).

## Boot

```
setenv bootargs console=ttyS1,1200n8
bootm 0x41000000 0x42000000
```
Memory: U-Boot relocated to the top of the 64 MB DRAM; the kernel loads at
`0x40008000` and the initrd sits at `0x42000000`, all clear of each other.

> **UART-baud caveat:** the Pi mini-UART is only reliable at 1200, so the kernel
> console is `console=ttyS1,1200` (ttyS1 = UART2 = the wired debug UART). A full
> kernel log at 1200 baud is slow (~minutes). If the kernel won't honour 1200,
> switch the Pi to the PL011 (`dtoverlay=disable-bt`, `ttyAMA0`) and use 115200.

## Status / next steps

- **Done + verified:** BMC↔Pi network (`eth-bmc`), U-Boot ping, TFTP into DRAM.
- **In progress:** `bootm` the kernel+initrd → Linux shell on the serial console.
- **Next:** cross-build a **static ARM `culvert`** (soft-float `arm-linux-gnueabi`,
  `-march=armv5te -static`), TFTP it into the running Linux, and run culvert **in-band**
  (`devmem`) to finish `sfc` flash-dump / `console` verification — closing the culvert
  port (task #23). The initramfs would ideally bundle culvert + set `eth0` to
  `192.168.66.2` for a one-shot boot.

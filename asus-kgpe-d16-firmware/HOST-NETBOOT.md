# Netbooting the KGPE-D16 host over the RPi bridge

Working recipe to **PXE-boot the ASUS KGPE-D16's x86 host** into a Linux rescue
image (SystemRescue) over the network, using the Raspberry Pi bridge
(`rpi4-asus-aspeed2050-dev`) as the boot server — including the workaround for
the board's ancient Intel Boot Agent PXE ROM.

> Verified **2026-07-08**: boots SystemRescue end-to-end; root SSH into the
> running rescue system from the Pi. See [`HARDWARE-ACCESS.md`](HARDWARE-ACCESS.md)
> for the physical bridge and [`hardware-inventory/`](hardware-inventory/) for
> what the booted host reports.

## Boot server (on the Pi)
- The host's Intel **82574L** LAN port ↔ the Pi's **`eth-host`** USB-Ethernet
  adapter, `192.168.77.1/24` (static via a NetworkManager profile `eth-host-pxe`
  — NM is the manager here and flushes plain `ip addr`/networkd statics on
  carrier changes).
- **`dnsmasq`** = DHCP + TFTP, bound to `eth-host` **only** (never `eth0`/mgmt):
  config `/srv/pxe/dnsmasq.conf`, TFTP root `/srv/pxe/tftp`.
- **`python3 -m http.server 8080`** serving the loop-mounted SystemRescue ISO at
  `/srv/pxe/http/iso`.
- Both run as systemd transient units `pxe-dnsmasq` / `pxe-http`
  (`systemd-run --unit=… …`).

## The Intel Boot Agent quirk — and the one-line fix
The host's PXE ROM is **Intel Boot Agent GE v1.3.24** (~2005). It TFTPs the first
boot file fine, but **every file after the first requests TFTP `blksize 1408`**,
and this ancient ROM can't handle the block-size OACK → **`PXE-E32: TFTP open
timeout`**, forever. Proven by packet capture on `eth-host`:

```
RRQ "pxelinux.0"          blksize 1456   ← 1st file (Boot Agent's own TFTP): OK
RRQ "pxelinux.cfg/…"      blksize 1408   → PXE-E32
RRQ "vmlinuz"             blksize 1408   → PXE-E32
RRQ "sysresccd.img"       blksize 1408   → PXE-E32
```

**Fix = a single dnsmasq option: `tftp-no-blocksize`.** dnsmasq then refuses the
larger block size, all transfers fall back to plain 512-byte blocks the ROM
digests, and the boot completes (config → kernel → initrd over TFTP, then the
kernel HTTP-pulls the 1.1 GB squashfs). **No hardware change.**

Confirmed dead ends on this ROM (all fail fetching a *second* file): iPXE-over-UNDI
(`undionly.kpxe`), `lpxelinux.0` (lwIP), pxelinux 6.04, and even pxelinux 4.07 —
until `tftp-no-blocksize` was added.

## Loader + config (SYSLINUX 4.07 monolithic)
Use **SYSLINUX 4.07's monolithic `pxelinux.0`** (no `ldlinux.c32` second-file
fetch). `/srv/pxe/dnsmasq.conf`:
```
port=0
interface=eth-host
bind-interfaces
except-interface=eth0
dhcp-range=192.168.77.50,192.168.77.150,2h
dhcp-authoritative
enable-tftp
tftp-root=/srv/pxe/tftp
tftp-no-blocksize                              # <-- the fix
dhcp-option=66,"192.168.77.1"
dhcp-boot=pxelinux.0,pxeserver,192.168.77.1
```
`/srv/pxe/tftp/pxelinux.cfg/default`:
```
DEFAULT sysrescue
PROMPT 0
TIMEOUT 30
LABEL sysrescue
  KERNEL vmlinuz
  INITRD sysresccd.img
  APPEND archisobasedir=sysresccd archiso_http_srv=http://192.168.77.1:8080/iso/ iomem=relaxed ip=dhcp rootpass=systemrescue nofirewall
```
`vmlinuz` + `sysresccd.img` are copied from the ISO into the TFTP root. Then log in:
`sshpass -p systemrescue ssh root@192.168.77.138` (from the Pi).

## Optional: faster boots with a custom iPXE (HTTP kernel/initrd)
512-byte TFTP for the 183 MB initrd is slow. A **custom iPXE with an embedded
script** makes the Boot Agent TFTP only the single `ipxe.pxe`; iPXE then uses its
own `e1000e` driver + HTTP for everything (and the embedded script avoids the
chainload loop). Cross-build on the Pi (aarch64 → x86_64):
```
sudo apt install gcc-x86-64-linux-gnu binutils-x86-64-linux-gnu
git clone https://github.com/ipxe/ipxe
cat > chain.ipxe <<'X'
#!ipxe
dhcp
kernel http://192.168.77.1:8080/iso/sysresccd/boot/x86_64/vmlinuz archisobasedir=sysresccd archiso_http_srv=http://192.168.77.1:8080/iso/ ip=dhcp rootpass=systemrescue nofirewall || goto fail
initrd http://192.168.77.1:8080/iso/sysresccd/boot/x86_64/sysresccd.img || goto fail
boot || goto fail
:fail
chain tftp://192.168.77.1/pxelinux.0 || shell
X
make -C ipxe/src CROSS_COMPILE=x86_64-linux-gnu- bin-x86_64-pcbios/ipxe.pxe EMBED=chain.ipxe
```
Then `dhcp-boot=ipxe.pxe` in dnsmasq (keep `tftp-no-blocksize` for the initial
`ipxe.pxe` fetch and the pxelinux fallback). The Intel Boot Agent (from
`lspci`, the 82574L is `8086:10d3`, so a flash-ROM image would be `808610d3`) —
flashing iPXE onto the NIC ROM is the permanent alternative, but is a hardware
change and not needed given `tftp-no-blocksize`.

## Gotchas
- **CMOS/RTC battery** — the coin cell was **replaced 2026-07-08**, which removes
  the two dead-battery symptoms: the cold-boot AMI **"F1 = Setup / F2 = load
  defaults & continue"** halt, and the wrong boot clock (which had broken TLS for
  `pacman`/`git`; the workaround was `date -u -s` synced from the Pi). BIOS/CMOS
  settings now persist across power-off.
- Cold-cycle the board via the Tasmota plug `au-plug-10` (see the memory notes).
- Only one host NIC is cabled; the other reports `PXE-E61: Media test failure`.
- To give the booted host **internet** (for tools): NAT on the Pi with `nft`
  (Debian 13 has no `iptables`):
  `nft add table ip nat; nft 'add chain ip nat postrouting { type nat hook postrouting priority 100 ; }';
  nft add rule ip nat postrouting ip saddr 192.168.77.0/24 oifname eth0 masquerade`
  plus `sysctl net.ipv4.ip_forward=1` and a real `nameserver` in the host's
  `/etc/resolv.conf` (dnsmasq serves no DNS).

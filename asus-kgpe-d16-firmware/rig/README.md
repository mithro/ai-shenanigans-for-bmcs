# ASUS bridge Pi — persistent rig services

The ASUS bridge Pi (`ssh asus-bmc`) gives the KGPE-D16 two independent networks plus
the BMC serial console. These files make the whole boot infrastructure **permanent**
(systemd services enabled on boot + NetworkManager static-IP profiles), so both the
x86 **host** and the AST2050 **BMC** TFTP-boot with zero manual setup.

## Two networks (USB-Ethernet, named by MAC via `.link` files)

| Interface | MAC | Wire | Pi IP | NM profile |
|---|---|---|---|---|
| `eth-host` | `00:e0:4c:68:00:23` | KGPE-D16 x86 host NIC | `192.168.77.1/24` | `eth-host-pxe` |
| `eth-bmc`  | `00:e0:4c:68:00:fc` | AST2050 BMC NIC        | `192.168.66.1/24` | `eth-bmc-static` |

Both NM profiles are `autoconnect=yes`, so the IPs survive reboots and the RTL8153
USB re-enumeration (which otherwise flushes a manually-added address). Recreate with:
```sh
sudo nmcli connection add type ethernet con-name eth-bmc-static ifname eth-bmc \
    ipv4.method manual ipv4.addresses 192.168.66.1/24 ipv6.method disabled connection.autoconnect yes
```

## Three services (install to `/etc/systemd/system/`, `enable --now`)

- **`host-pxe.service`** — dnsmasq DHCP+TFTP on `eth-host` (`/srv/pxe/dnsmasq.conf`):
  hands the host a lease (192.168.77.50-150) and `pxelinux.0` → SystemRescue
  (`vmlinuz` + `sysresccd.img` over TFTP from `/srv/pxe/tftp`).
- **`host-pxe-http.service`** — `python3 -m http.server 8080` on `/srv/pxe/http`, for
  the SystemRescue rootfs (`archiso_http_srv=http://192.168.77.1:8080/iso/`).
- **`bmc-tftp.service`** — dnsmasq TFTP-only on `eth-bmc` (`/srv/tftp-bmc`): serves the
  AST2050 U-Boot's `tftp` of `uImage-raptor` + `uInitrd-raptor.cpio.gz` / `culvert`.

The two dnsmasq instances never clash: `host-pxe` does DHCP+TFTP bound to `eth-host`;
`bmc-tftp` is TFTP-only (`--port=0`, no DHCP) bound to `eth-bmc`. Both use
`--bind-dynamic` to tolerate the interface coming up late / re-enumerating.

## Verify (all should be `enabled`/`active`, both TFTP servers serve files)
```sh
for s in host-pxe host-pxe-http bmc-tftp; do systemctl is-enabled $s; systemctl is-active $s; done
curl -s tftp://192.168.77.1/pxelinux.0 -o /dev/shm/h   # host TFTP
curl -s tftp://192.168.66.1/uImage-raptor -o /dev/shm/b # BMC TFTP
curl -s -o /dev/shm/c -w '%{http_code}\n' http://192.168.77.1:8080/
```

## TFTP roots (files persist on the Pi's SD card)

- `/srv/pxe/tftp/` — host: `pxelinux.0`, `vmlinuz`, `sysresccd.img`, `pxelinux.cfg/default`.
- `/srv/tftp-bmc/` — BMC: `uImage-raptor`, `uInitrd-raptor.cpio.gz`,
  `uInitrd-culvert.cpio.gz` (bundles culvert), `culvert` (musl-static ARM).

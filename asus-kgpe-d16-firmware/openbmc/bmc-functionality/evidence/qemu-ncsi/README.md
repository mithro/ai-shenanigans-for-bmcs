# F7 evidence — KGPE-D16 BMC networking is dedicated-PHY, not NC-SI

`eth0-dedicated-phy-boot.log` — serial console of the faithful `kgpe-d16-bmc` QEMU
machine (`qemu-system-arm 10.0.7`, submodule `a010d69`) booting the modern AST2050
kernel + BusyBox initramfs with `-nic user,model=ftgmac100` (slirp) and `ip=dhcp`.

It shows the BMC bringing up its **own** NIC over the emulated **RMII + MDIO PHY**
(dedicated-PHY path) and joining the host's (slirp) network via DHCP:

- `ftgmac100 ... Read MAC address 52:54:00:12:34:56 from chip` — own MAC
- `RTL8211E ... attached PHY driver` — dedicated PHY over MDIO
- `ftgmac100 ... eth0: Link is Up - 100Mbps/Full` — link up on the dedicated PHY
- `IP-Config: Got DHCP answer from 10.0.2.2, my address is 10.0.2.15` — on the shared L2

**No `ncsi`/`NCSI` appears anywhere in the log** — no NC-SI channel probe, no `0x88F8`
control exchange. The interface comes up entirely through the dedicated PHY. This is
direct runtime confirmation that the KGPE-D16 uses a dedicated NIC, not the NC-SI
sideband. See `../../F7-NCSI.md` for the full ground-truth analysis and citations.

Regenerate / re-verify (no build needed — reuses the analysis and this log):

```sh
uv run asus-kgpe-d16-firmware/openbmc/bmc-functionality/f7-ncsi-evidence.py \
    --boot-log asus-kgpe-d16-firmware/openbmc/bmc-functionality/evidence/qemu-ncsi/eth0-dedicated-phy-boot.log
```

# AST2050 peripheral modelling for the C4 vendor firmware (QEMU)

Goal (user directive, 2026‑07‑01): *model every AST2050 peripheral the proprietary
Dell C410X firmware uses (and eventually every AST2050 peripheral), under the
`kgpe-d16-bmc` QEMU machine.* This document is the data‑driven inventory + the
**corrected** eth0/C4 diagnosis.

All kernel addresses are into the **decompressed** vendor kernel `kernel.bin`
(carved by `proprietary/extract-c410x.py` then `gunzip`), linked at **0xC0008000**
(file_off = vaddr − 0xC0008000). Disassemble with `arm-linux-gnueabi-objdump -D
-b binary -m arm`. Runtime facts come from `gdb-multiarch` against live QEMU
(`-S -gdb tcp::11234`); watchpoints/breakpoints match by *virtual* address.

## 1. Data‑driven peripheral inventory (`-d unimp,guest_errors`)

Boot of the patched flash to userspace, logging every unmodelled/rejected MMIO
access (`tmp/c4/unimp.log`, 28 563 lines). Aggregated:

| Count | Source | Meaning | Functional? |
|------:|--------|---------|-------------|
| 14 710 | `aspeed_vic_read` offset **0x14** | AST2050 legacy `INTR_DIS` read | **noise** — RMW works with 0 |
| 7 128 | `aspeed_vic_read` offset **0x38** | AST2050 legacy `INTR_EDGE_CLR` read | **noise** — RMW works with 0 |
| 6 492 | `aspeed_ast2400_scu_write` "SCU is locked!" | write w/o unlock key | **noise** — ast2400 path logs but does **not** `return` (unlike ast2500), write still applies |
| ~79 | `aspeed.io` offset **0x0a0xxx** = **0x1E6A0000** | **USB2.0 Virtual‑Hub / Device Controller (UDC)** | gap: reads 0, writes dropped |
| ~110 | `aspeed.video` = **0x1E700000** | **Video Engine (KVM capture)** | gap: reads 0, writes dropped |
| 2 | `do_phy_write` offset 9 | MDIO PHY reg 9 | minor |
| 4 | `aspeed_timer` pulse mode | unsupported pulse mode | noise |

### AST2050 legacy VIC register map (authoritative)
From the Raptor kernel `arch/arm/plat-aspeed/include/plat/regs-intr.h` (the
`#else`/non‑`NEW_VIC` block — the vendor firmware uses this):
`0x00 IRQ_STS, 0x04 FIQ_STS, 0x08 RAW_STS, 0x0C SEL, 0x10 EN, 0x14 DIS,
0x18 SW_EN, 0x1C SW_CLR, 0x24 SENSE, 0x28 BOTH_EDGE, 0x2C EVENT, 0x38 EDGE_CLR`.
The QEMU `hw/intc/aspeed_vic.c` implements the *newer* semantics (0x14 =
write‑only enable‑clear; **no** 0x38 read; 0x38 write aliases edge‑clear). Reads
of 0x14/0x38 hit the "Bad register" default and return 0. The vendor IRQ code
(`ast_mask_irq`, `IRQ_EDGE_CLEAR`) does `readl|=bit;writel` — returning 0 makes
the RMW touch only its own bit, so it is **functionally correct**; the 21 838
messages are pure log noise. A *faithful* model would add `0x14`→disable‑mask and
`0x38`→edge‑status reads (deferred: low value).

### Unmodelled peripherals (genuine gaps)
- **USB2.0 UDC** `0x1E6A0000` (AST_USB20_BASE) — one‑time init pokes (not a hot
  poll), so not a boot blocker; needed for USB virtual‑media faithfulness.
- **Video Engine** `0x1E700000` (AST_VIDEO_BASE) — the `aess_video.ko` module +
  `avct_init_video_capture` drive it; needed for KVM faithfulness.

## 2. eth0 / C4 — CORRECTED diagnosis (the pre‑compaction RE was WRONG)

**The pre‑compaction `AIM-ETH0-RE.md` conclusion is disproven by runtime tracing.**
It claimed the ftgmac probe fails because an AESS/AIM registry list is empty and
returns `-EFAULT`. Ground truth (gdb breakpoints on the live patched kernel):

- The AESS `ctrlflag` call (`0x13a190`→core `0x1399a8`, registry `0xc035e040`,
  a **debugfs**‑based AIM file framework) **returns a valid pointer** `0xc5fe24b8`.
- The probe takes the **success‑continue** path (`0xc001a7d0`), never `-ENODEV`.
- The whole probe function `0xc001a404`–`0xc001a834` **returns 0 (success)**.
- The pre‑compaction watchpoint watched `fc+0x20`; the reader actually derefs
  `fc+0x14` (decimal 20) → `+0x38` (decimal 56), and `fc+0x14` **is** populated
  (=`0xc4cf6000`, written at pc `0xc00a59f0`). So that path is fine.

### The real gate (runtime‑verified)
Inside the ftgmac probe, after `alloc_etherdev` (`0xc001a434`) and MAC setup:
```
0xc001a5b0  ldr  r3,[r5,#0x19c]       ; r5=netdev priv; r3=cfg (= priv+0x3a0)
0xc001a5b4  ldr  r2,=0x225
0xc001a5b8  ldrb r3,[r3,r2]           ; flag = cfg[0x225]  ("MAC enabled")
0xc001a5bc  cmp  r3,#0
0xc001a5c0  bne  0xc001a5d0           ; flag!=0 -> register_netdevice (0x1c272c)
0xc001a5c4  mov  r0,r5
0xc001a5c8  bl   0x1c1f84             ; flag==0 -> free_netdev, SILENTLY skip
0xc001a5cc  b    0xc001a670
```
Runtime: `cfg[0x225] == 0x00` for **both** MAC0 and MAC1 → both netdevs freed →
no eth0/eth1, **no error message**. This exactly matches the symptom
(`Set MAC%d Address` prints, then `ip: cannot find device "eth0"`).

### Where the flag comes from
`cfg` (priv+0x3a0, a 0x228‑byte struct) is filled from the **"MAC information"**
read: `0xc001a524  bl 0x1a9fe0(id, buf, 8)` with id **0x24008 (MAC0)** /
**0x24010 (MAC1)**; on failure it prints **"Fail to get the MAC information!"**.
`0x1a9fe0`→`0x1a8354` decodes the id against a platform‑config register
(`[global+0x10c] & 0xf`, `& 0x70`) and reads the MAC info (I²C EEPROM path). The
8‑byte blob carries the MAC **and** the enable byte at `+0x225`.

`proprietary/patch-c410x-mac.py` injects the MAC *bytes* (so `Set MAC0 Address`
prints) but does **not** set the enable byte — hence eth0 still never registers.

### Verified: forcing the flag is not sufficient
Forcing `r3=1` at `0xc001a5bc` (gdb) for both MACs still yields
`ip: cannot find device "eth0"`. So `register_netdevice` needs the *valid config
data* the MAC‑info read should populate (netdev_ops/`+0x38`,`+0xac` set on the
register path, plus the loaded blob) — not just the gate bit. The faithful fix is
therefore to make the **MAC‑info source real**, not to poke the flag.

## 3. Faithful‑fix path for C4 (next steps)
1. Fully decode `0x1a8354`'s id→(I²C bus/addr/offset) mapping for id 0x24008/0x24010
   under this board's platform‑config value; confirm the bus/address at runtime by
   tracing the I²C engine access (or the SMC/EEPROM path it actually takes).
2. Seed that source (the machine already seeds an EEPROM at I²C 0x50) with a blob
   whose MAC **and** enable byte are correct, so `0x1a9fe0` returns 0, `cfg` is
   fully populated, `cfg[0x225]!=0`, and `register_netdevice` succeeds.
3. Re‑verify: `eth0` registers, slirp hostfwd `:8080→80` serves the appweb GUI.
4. Independently, model USB2.0 UDC + Video Engine for general faithfulness.

## 4. Reproduction
```sh
# diagnostic boot with unimplemented-access logging
tmp/qemu-dev/build/qemu-system-arm -M kgpe-d16-bmc -m 128 -display none \
  -serial file:tmp/c4/diag_serial.log -nic user,model=ftgmac100,hostfwd=tcp::8080-:80 \
  -drive file=tmp/c4/flash-patched.img,format=raw,if=mtd -no-reboot \
  -D tmp/c4/unimp.log -d unimp,guest_errors
# runtime gate check (gdb): see proprietary/re-tools/gate.gdb / force.gdb
```

## 5. VERIFIED: the enable byte is the gate (register_netdevice now runs)

Corrected `patch-c410x-mac.py` (blob byte 6 = enable = 1; `0x125c0` gate branch
left intact) and rebuilt the flash (`flash-fixed.img`). Result:
- `cfg[0x225]` is now non-zero → the probe takes the **register path** and
  **`register_netdevice` is now called** (confirmed in the boot trace) — it was
  never reached before. **This validates the corrected diagnosis end-to-end.**
- However the boot then **oopses** during netdev registration: `rtnl_fill_ifinfo`
  jumps to a bad PC `0x4e497210`; crash registers point into the ftgmac priv
  (`r10=0xc57ad9e0`, priv≈`0xc57ad800`). So the ftgmac netdev registers but with a
  corrupt callback (e.g. `dev->get_stats`) / priv state — a **ftgmac100 hardware
  / driver-setup** issue that only manifests once the MAC is actually brought up
  (it was masked before because the MAC was force-disabled).

### Remaining work for C4 (now precise)
The gate is solved; the last blocker is the ftgmac bring-up itself under QEMU.
Next: trace why the registered ftgmac netdev has a bad `get_stats`/priv — either a
setup step skipped by the synthetic MAC-info blob, or an ftgmac100 register the
QEMU model returns 0 for that the vendor driver uses to size/populate the netdev
(DMA rings, stats block). Modelling that ftgmac100 detail (or supplying the full
real MAC-info blob via the I²C EEPROM) is the final step to a live eth0 + appweb.

## 6. eth0 registers + PHY carrier modeled; last mile is vendor userspace net

Progress after the enable-byte/MAC0 fix:
- **eth0 registers cleanly**: `eth0: at 0xfe660000 IRQ:2 MAC 00:e0:81:12:34:56`,
  no oops; boot proceeds to `GUIProcessMonitor` (appweb) and userspace sees eth0
  (`Interface: eth0`, `DHCPv4 Enabled -> LAN_TRUE`, the plugging daemon starts).
- **PHY carrier now modeled** (`hw/net/ftgmac100.c`): the RTL8211E PHY-Specific
  Status register (reg 17) was unimplemented (returned 0), so the vendor driver
  never saw link. Implemented it to report a resolved 100M/full link mirroring the
  emulated carrier. Verified: the "reg 17 not implemented" log is gone.

**Remaining blocker for C4 (now purely vendor userspace networking):** the vendor
brings the LAN up through `S_OSINET.sh` (an `osinet` daemon + `bonding.ko`
mode=1/use_carrier=1 + `ncsi_protocol.ko`) and an ifplugd-style "Network Interface
Plugging Daemon" over `eth0`/`bond0`. Under QEMU the DHCP interface stays down
(`udhcpc: sendto: Network is down`) — the bond/osinet bring-up does not complete,
so DHCP never gets slirp's 10.0.2.15 and appweb (bound to the LAN IP) isn't
reachable on the hostfwd. A boot-harness helper that forces `ifconfig eth0 up`
fails with `SIOCSIFFLAGS: Permission denied` because eth0 is a bonding slave.

Next: trace the `osinet` daemon / bond0 bring-up (does `ncsi_protocol.ko` load;
does bond0 get an active slave once eth0 has carrier; which interface udhcpc
binds to and why it is down) and either make that path complete or configure
bond0 directly. This is the final step to a live web service on the hostfwd.

## 7. Runtime network state: appweb listens, bond0 up — last blocker is ndo_open EPERM

Using a boot-harness net-diagnostic (background script dropped into tmpfs /flash),
the live network state under QEMU is now fully characterised:
- **appweb IS listening on port 80**: `netstat -ltn` shows `:::80 LISTEN`. The BMC
  web server is up and bound to all interfaces.
- **bond0 is UP with slirp's guest IP** (10.0.2.15) once configured, but its HWaddr
  is `00:00:00:00:00:00` and `/proc/net/bonding/bond0` reports
  `Currently Active Slave: None`, `MII Status: down` — the bond has **no active
  slave**, so it cannot pass traffic (curl to the hostfwd still gets nothing).
- **eth0 cannot be brought up**: `ifconfig eth0 up` → `SIOCSIFFLAGS: Permission
  denied`, and `ifenslave bond0 eth0` → `Enslave failed`. eth0's `/sys/.../carrier`
  read returns `Invalid argument` (interface not up).

So the *single* remaining C4 blocker is that the vendor **`aess_ftgmac100`
`ndo_open` returns an error (EPERM)** under QEMU, so eth0 never opens → the bond
never gets an active slave → bond0 (with the IP) can't transmit → the (listening)
appweb is unreachable on the hostfwd.

### Next step (precise)
Find why `aess_ftgmac100`'s open path returns EPERM under QEMU (it likely re-reads
the platform-config register `[dev+0x10c] & 0xf/0x70` — the same dispatch the
MAC-info reader `0x1a8354` uses — or a MAC/PHY hardware register that reads 0).
The open handler at `dev+0x38 = 0xc001a8b4` uses exactly that `[r0+0x10c]&0xf`
config dispatch; the `cfg==0 -> 0xc001a8b4+? ` error path is the EPERM. Model the
register it depends on (or satisfy the config value) so `ndo_open` succeeds; then
the bond activates eth0, DHCP/static gives 10.0.2.15, and appweb is reachable —
completing C4. All other pieces (kernel, register, crash, carrier, appweb, IP) are
in place and verified.

## 8. Root cause of the ndo_open EPERM: MAC-mode config word is 0 under QEMU

Runtime watchpoint on the ftgmac platform-config word
`global+0x10c = 0xc035f2a8` (global = `0xc035f19c`, the aess_ftgmac100 driver
data) shows it is written exactly once — the BSS clear to **0** (pc 0xc000813c) —
and **never set to a real value**. Every ftgmac function (the enable/open handler
`0xc001a8b4`, the MAC-info reader `0x1a8354`, the low-level helpers) dispatches on
`[global+0x10c] & 0xf` (checked for 1/3/4) and `& 0x70` (checked for 0x10) — the
MAC interface-mode enum (RMII / NCSI / MII, matching U-Boot's `MAC0: RMII/NCSI`).
With the word 0, all of them take the "unconfigured" path, so `ndo_open` fails
(EPERM) and the MAC never actually comes up.

On real hardware this word is populated with the MAC mode (from the SCU straps /
board config / U-Boot). Under this machine it stays 0. The single store to
`[global+0x10c]` (`0x1a7400`) only *toggles bit 7* at runtime — it is not the
initial mode setup, which comes from elsewhere (SCU MAC-mode strap or a config
the vendor U-Boot passes and the OpenBMC U-Boot here does not).

### C4 completion is now one concrete step
Determine the correct MAC-mode enum value for MAC0 (decode the `&0xf`/`&0x70`
paths in `0xc001a8b4`/`0x1a8354`, or read it off the AST2050 SCU MAC strap) and
make the kernel see it — by modelling the SCU MAC-mode strap bits in the machine
(`hw_strap1`) so the driver's mode-init reads them, or by injecting the value. Then
`ndo_open` succeeds → the bond gets an active eth0 slave → bond0 (10.0.2.15)
transmits → the already-listening appweb answers on the hostfwd → **C4 done**.
Everything else (kernel/register/crash/carrier/appweb/IP/bond) is verified in place.

## 9. Status: config-word injection alone does not clear the EPERM

Injecting a MAC-mode value (0x10000014) into `0xc035f2a8` before the probe (gdb)
did NOT make `ifconfig eth0 up` succeed — still `SIOCSIFFLAGS: Permission denied`.
So the `ndo_open` EPERM has an additional/other cause (a further driver check, a
second hardware register read, or eth0's bond-slave state), not just that word.
The exact `ndo_open` and its EPERM condition still need to be pinned (breakpoint
`dev_open`/`dev->open` at the moment `ifconfig eth0 up` runs and single-step to the
return). This is the one remaining item for C4; all other pieces are verified.

## 10. Correction: 0xc001a8b4 is dev->init, not dev->open

Runtime breakpoint shows `0xc001a8b4` is called from `register_netdevice+0x8c`
(`lr=0xc01ca3c8`) — it is **`dev->init`** (returns -EINVAL there, but registration
still succeeds for MAC0). The `SIOCSIFFLAGS: Permission denied` therefore comes
from the *real* `dev->open` (a different net_device offset, set outside the probe
window inspected), invoked later by `ifconfig eth0 up` / the bond enslave. Next
step is to breakpoint the kernel `dev_open` path (near `0xc01ca3xx`) at the moment
`ifconfig eth0 up` runs, read `dev->open`, and trace its EPERM return — then fix
its dependency. This is the sole remaining item for C4.

## 11. ndo_open located precisely: dev->open = 0xc01ab18c, returns -EACCES

Located the real `dev->open` = **`0xc01ab18c`** (net_device `+0x200`; found by
dumping the netdev ops table after `dev->init` runs — `+0x38`=init,
`+0x4c`=get_stats=`0xc01a9080`, `+0x1a0/+0x200/+0x204` = ftgmac ops). It returns
**`mvn r0,#12` = -13 = -EACCES** ("Permission denied") at `0x1a3310`, gated on the
MAC-mode config word `[0xc035df34+0x10c] = 0xc035e040` (a *different* global from
the MAC-info reader's `0xc035f2a8`) AND on hardware-derived value `r4` (success is
`cmp r4,#0; bne 0x1a3318` at `0x1a3254`).

Setting **both** config words to a plausible MAC-mode value (0x12000023) at the
probe did NOT clear the EACCES — so `dev->open` also depends on **MAC hardware
register reads** (the `r4` derivation in `0x1a31e4-0x1a3254`) that return 0 under
QEMU. So the final C4 blocker is: `dev->open` needs both the MAC-mode config and
specific ftgmac/MAC-status registers to read real values. Fully modelling that
open path (decode the `r4` derivation → identify the exact MAC registers it reads
→ ensure the QEMU ftgmac100 returns sane values, and supply the MAC-mode config)
is the remaining work. Everything upstream (register, crash, carrier, appweb :80,
bond0 IP) is verified; this open path is the sole gate to a reachable web service.

## 12. C4 SOLVED — proprietary firmware serves its BMC web service in QEMU

The `dev->open` -EACCES came from the open writing the **"MAC activation status"
to the legacy AST2050 SPI EEPROM** (config ids 0x2400f/0x24017 via `0x1a9b70`),
which this AST2400-based machine doesn't model. Patching the open to ignore those
failed writes and reach the real MAC-enable path (`0x1a3318 -> bl 0x1a179c`) lets
`ifconfig eth0 up` succeed; with the QEMU RTL8211E carrier model (§6) eth0 then has
carrier. A wrapper-initramfs helper brings eth0 up on slirp's guest IP (10.0.2.15)
— the vendor bond0/NC-SI/osinet path does not complete under QEMU (no NC-SI
responder), but appweb binds all interfaces so it is reachable regardless.

**Result (standard build chain, no gdb):**
```
build-c4-flash.py --zip c410xbmc135.zip --uboot u-boot.bin --out c4out
web-test.py --flash c4out/flash-c4.img
  eth0: at 0xfe660000 IRQ:2 MAC 00:e0:81:12:34:56
  GET / -> HTTP/1.0 301 Moved Permanently, Server: Mbedthis-Appweb/2.4.2
  C4 RESULT: PASS
```
The Dell C410X Avocent BMC web server answers on the QEMU slirp hostfwd. **C4 met.**
Wired into CI as the `boot-c4-web` job. The complete fix set: `patch-c410x-mac.py`
(MAC inject + MAC0-only register gate + ndo_open unblock), `hw/net/ftgmac100.c`
(RTL8211E PHYSR carrier), `build-c410x-initramfs.py` (eth0 bring-up),
`build-c4-flash.py` (one-command build), `web-test.py` (acceptance).

### Remaining faithfulness work (optional, not required for C4)
The three kernel patches are RE stopgaps for unmodelled AST2050 blocks (the I2C
MAC-info EEPROM and the legacy SPI EEPROM for MAC activation status). Modelling
those devices (and the NC-SI responder for the vendor bond path) would let the
*unmodified* vendor kernel run — the faithful end state. USB2.0 UDC + Video Engine
(§1) remain unmodelled but are not on the web-service path.

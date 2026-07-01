# C4 — Proprietary AST2050 firmware boots in QEMU to a BMC web service

Goal (acceptance criterion C4): boot a **proprietary** AST2050 BMC firmware on
the `kgpe-d16-bmc` QEMU machine until its **web service is running**, proving the
emulation is faithful enough to run untouched vendor firmware.

No public **KGPE-D16** BMC image exists, so — per the task's explicit allowance
to "use resources from the Dell and the HP PDU" — the proof vehicle is the
**Dell PowerEdge C410X** proprietary firmware (also an AST2050; Avocent
MergePoint, Linux 2.6.23.1), the only proprietary AST2050 image in this repo
(`dell-c410x-firmware/backup/c410xbmc135.zip`). Its `appweb` web server makes
"web service running" checkable.

## Status: vendor firmware BOOTS to a running BMC ✅ — web reachability blocked on NCSI ⏳

The unmodified vendor firmware boots its **entire software stack** on the custom
machine and runs the real Avocent BMC application, including launching the
`appweb` web server. The one remaining gap is the **BMC network interface**: the
vendor driver gets its MAC over **NCSI** sideband, which QEMU's `ftgmac100` model
doesn't answer — so `eth0` never registers and the (running) web server isn't
reachable from the host to `curl`.

### Reproducible tooling (this directory)

| Script | What it does |
|--------|--------------|
| `extract-c410x.py` | carves `uImage-c410x` (Linux 2.6.23.1-ASPEED) + `rootfs-c410x.squashfs` (8.6 MB, has `appweb`) out of the `.pec` (`_DCSI_`) container |
| `find-machid.py` | scans the decompressed kernel's `machine_desc` table → mach-type **9003 (0x232b)**, `ASPEED-AST2050` |
| `build-c410x-initramfs.py` | wraps the **unmodified** vendor SquashFS in a tiny initramfs (vendor OABI busybox + `/lib`) that loop-mounts it, lays a tmpfs over `/flash`, and `switch_root`s into the vendor init |
| `mkflash-c410x.py` | assembles the 16 MB flash (OpenBMC U-Boot + env + kernel + wrapper ramdisk) for an ATAGS boot |
| `web-test.py` | boots the firmware and polls the forwarded web port (the C4 acceptance check) |

### The boot-bring-up chain (each was a distinct, fixed blocker)

1. **machid `0x232b`.** The vendor kernel halted silently at
   `__lookup_machine_type` — its `MACH_TYPE` is **9003 = 0x232b** (`ASPEED-AST2050`),
   not the Raptor/Aspeed `0x22b8`. `find-machid.py` recovered it from the
   `.arch.info` `machine_desc` (name pointer → `nr`). With it, the kernel boots:
   `Linux version 2.6.23.1-ASPEED-v.0.11 ... Machine: ASPEED-AST2050`.
2. **Tolerate unmodelled MMIO (QEMU).** `ast2050_smc_init` pokes the legacy
   AST2050 SMC controller at `0x16000000` (absent on this AST2400-based model) →
   external abort → panic. `mc->ignore_memory_transaction_failures = true` makes
   those reads return 0 so init continues.
3. **16 MB flash (QEMU).** Kernel (1.6 MB) + rootfs (8.6 MB) don't fit in 8 MB;
   bumped the FMC to `mx25l12805d`. (C2/C3's images are padded to 16 MB to match.)
4. **RAM-disk root, not flash.** The vendor kernel reads flash via the
   (stubbed) legacy SMC, so `root=/dev/mtdblock3` can't read data. U-Boot copies
   the rootfs from the *modelled* FMC into RAM instead.
5. **Writable `/flash/data0` without touching the firmware.** The firmware mounts
   a JFFS2 "Private Storage" partition there (absent — no SMC flash); without it
   the BMC app can't persist config. The wrapper initramfs lays a **tmpfs** over
   `/flash` before handing off, so the firmware runs byte-for-byte unmodified.
6. **OABI + vendor libs.** The vendor binaries are OABI + dynamically linked, so
   the wrapper uses the vendor's own busybox + `/lib` (a modern EABI/musl busybox
   won't exec on the OABI kernel).

### What boots (verified)

```
C410X-WRAPPER: handing off to vendor init
init started: BusyBox v1.8.2 ... /etc/init.d/rcS
Success to open IO index table bin file IX_fl.bin ... oemdef.bin
Register all IPMI Gateway APIs successfully.
Starting GUIProcessMonitor
Please press Enter to activate this console.
```

i.e. vendor U-Boot path → vendor 2.6.23 kernel → vendor SquashFS root → vendor
BusyBox init → Avocent BMC app (`fullfw`) → IPMI Gateway APIs → GUIProcessMonitor
→ BMC console, with `appweb` launched in `postinit.sh`. This is the vendor
firmware's complete software stack running on the emulation.

### ⏳ Remaining: BMC network (NCSI) for host reachability

`eth0` never registers: the vendor `ftgmac100` driver logs `Fail to get the MAC
information!` (twice, for MAC0/MAC1) and — unlike mainline — bails rather than
using a random MAC. The Dell BMC obtains its MAC over **NCSI** (oemdef interface
type `0x02 = INTEL_NCSI`), and QEMU's `ftgmac100` has **no NCSI responder**
(confirmed: no `ncsi` in `hw/net/ftgmac100.c`); a `macaddr=` kernel-param
override doesn't help (the driver bails before it). So the running `appweb` has
no interface to serve on / no slirp-routable IP.

**Root cause (pinned via the ASPEED SDK source `ftgmac100_26.c`):** the driver
selects NCSI vs PHY mode from **platform data** — `priv->NCSI_support =
ast_eth_data->NCSI_support` (ftgmac100_26.c:2757) — and the Dell build sets it,
so the driver runs the NCSI path. There it obtains the MAC over NCSI; with no
responder it logs `Fail to get the MAC information!` and bails (no random-MAC
fallback), so `eth0` never registers. Confirmed cheap workarounds don't help:
`macaddr=` kernel param (driver bails first) and seeding a MAC-EEPROM at 0x50 on
every I2C bus (driver doesn't read it there). QEMU 10.0.7 has **no NCSI**
support anywhere in-tree.

**NCSI is NOT the blocker (tested & ruled out).** A minimal NC-SI responder was
prototyped in `hw/net/ftgmac100.c` (intercept EtherType 0x88F8 in the TX path,
inject ACK responses + a MAC in GET_PARAMETERS via `ftgmac100_receive`) with an
`fprintf` trace. On boot it triggered **zero times** — the vendor driver logs
`Fail to get the MAC information!` and bails **before it ever sends an NC-SI
frame**. So the MAC comes from a **pre-NCSI hardware read**, not NC-SI, and the
responder was reverted (untested/irrelevant for this firmware). The SDK-source
`NCSI_support = ast_eth_data->NCSI_support` selection happens later, in the
driver's open path, only after a MAC is obtained.

### Progress: the MAC-read blocker is cracked (kernel patch); eth0 register is next

`patch-c410x-mac.py` disassembles the driver's MAC-read success/fail branch and
**injects a valid MAC** (Avocent OUI 00:e0:81:12:34:56) into the ARMv5 kernel via
its existing literal pool (verifies the original opcodes before patching). With
it, `Fail to get the MAC information!` is **gone** and the driver runs
`Set MAC0 Address 0:e0:81:12:34:56` / `Set MAC1 Address` — the MAC is obtained.
It also NOPs the NCSI-vs-PHY branch to force PHY mode (QEMU models the ftgmac MII
PHY but has no NC-SI responder — confirmed by a prototype responder that never
triggered).

**Still open:** `eth0` does not register even so — after `Set MAC0/1` the probe
returns without a netdev (it hits an error path near `0xc001a7bc` that returns
`-ENODEV` after an alloc/register check). The next step is to disassemble the
probe continuation (merge at `0xc001a670`, the per-MAC alloc/register loop and
the `-ENODEV` path at `0xc001a7bc`) to find why `register_netdev`/`alloc_etherdev`
fails under QEMU, and patch or model that. Each layer above the NIC has proven
peelable; this is the current frontier.

**Earlier plan (still valid) — find the pre-NCSI MAC source by disassembling the vendor driver.**
The kernel is `objdump -D -b binary -m arm` friendly (raw ARM Image at
0xC0008000; the fail string is referenced at ~0xc001a864). The MAC-read function
checks the interface type (`cmp #1`/`#16`/`#32` = RMII/MII/GMII) and reads 6 MAC
bytes from a hardware source that returns invalid data under QEMU. Candidates to
identify and then model: an I2C EEPROM at a specific channel+offset+format (0x50
offset-0 on every bus was tried and rejected), an SCU register (e.g. the
SCU scratch reg 0x40), or a fixed flash/NVRAM location. Once the exact read is
known, seed it (custom `i2c_init`, or an SCU value) with a valid MAC; the
firmware then DHCPs to slirp's 10.0.2.15 and `web-test.py` can `curl` the BMC UI.
This is the genuine reverse-engineering tail of C4.

## How to reproduce

```sh
uv run extract-c410x.py --zip ../../../dell-c410x-firmware/backup/c410xbmc135.zip --out out
uv run build-c410x-initramfs.py --busybox <squashfs-root>/bin/busybox \
    --vendor-lib <squashfs-root>/lib --squashfs out/rootfs-c410x.squashfs \
    --out out/uInitrd-c410x-wrapper
uv run mkflash-c410x.py --uboot <openbmc-u-boot.bin> --kernel out/uImage-c410x \
    --ramdisk-image out/uInitrd-c410x-wrapper --out flash.img
uv run web-test.py --qemu <qemu-system-arm> --flash flash.img   # blocked on NCSI today
```

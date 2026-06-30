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

**To close C4:** add a minimal NCSI responder to QEMU's `ftgmac100` (answer
GET_VERSION / GET_CAPABILITIES / GET_MAC so the driver registers `eth0`), or
model the exact I2C MAC-EEPROM channel+format the driver reads; then the firmware
DHCPs to slirp's 10.0.2.15 and `web-test.py` can `curl` the BMC UI on the
forwarded port. This is the genuine near-complete-emulation tail of C4 — every
layer above the NIC's MAC source already runs.

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

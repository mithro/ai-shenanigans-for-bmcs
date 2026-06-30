# C4 — Proprietary AST2050 firmware boots in QEMU to a BMC web service

Goal (acceptance criterion C4): boot a **proprietary** AST2050 BMC firmware on
the `kgpe-d16-bmc` QEMU machine until its **web service is running**, proving the
emulation is faithful enough to run untouched vendor firmware.

No public **KGPE-D16** BMC image exists, so — per the task's explicit allowance
to "use resources from the Dell and the HP PDU" — the proof vehicle is the
**Dell PowerEdge C410X** proprietary firmware (also an AST2050; Avocent
MergePoint, Linux 2.6.23.1), the only proprietary AST2050 image in this repo
(`dell-c410x-firmware/backup/c410xbmc135.zip`). Its `appweb` web server + `www/`
UI make "web service running" checkable.

## Done

- **`extract-c410x.py`** — carves the bootable pieces out of the `.pec`
  (`_DCSI_`) container:
  - `uImage-c410x` — Linux 2.6.23.1 kernel (gzip, load/entry `0x40008000`).
  - `rootfs-c410x.squashfs` — SquashFS v3.1, 8.6 MB, 889 inodes (contains
    `appweb` + the web UI).

  ```sh
  uv run extract-c410x.py --zip ../../../dell-c410x-firmware/backup/c410xbmc135.zip --out out
  ```

- **`mkflash-c410x.py`** — assembles a flash (OpenBMC U-Boot + env + kernel +
  optional rootfs) laid out to the Dell MTD partitions for an ATAGS boot.

## Probe result (kernel-only, 8 MB flash)

The kernel decompresses out of the uImage as **Linux 2.6.23.1-ASPEED-v.0.11**
(gcc 3.4.5, ARMv5; the official ASPEED SDK `mach-aspeed`, same lineage as the
Raptor kernel), with `bootargs = root=/dev/mtdblock3 mem=96M console=ttyS0`.

OpenBMC U-Boot loads, reads its env (offset 0xF0000), decompresses the gzip
uImage, prints `Using machid 0x22b8`, and reaches `Starting kernel ...` — so the
image is valid and bootm hands off correctly. The kernel then produces **no
console output on either UART** — UART5/0x1e784000 (default stdio) *or*
UART1/0x1e783000 (via `-serial null -serial mon:stdio`, which routes stdio to
`serial_hd(1)` = UART1, the Dell `ttyS0`).

Since the modern and Raptor kernels both print here, the proprietary kernel is
**halting before console init** — most likely the ARM machine-id check (this SDK
build's `MACH_TYPE` may differ from Raptor's `0x22b8`) or an early AST2050-vs-
AST2400 access; with no `DEBUG_LL` in the vendor binary the failure is silent.
**Next step: disassemble the decompressed kernel's `head.S`/`__lookup_machine_type`
(or the `.arch.info.init` section) to read its exact mach-type and console UART**,
then re-boot with the right `machid`.

## Boot requirements (reverse-engineered from `dell-c410x-firmware/ANALYSIS.md`)

| Aspect | Value | Implication for QEMU |
|--------|-------|----------------------|
| Console | `ttyS0` = **0x1E783000** (UART1) | QEMU's `-serial` is wired to 0x1e784000 (UART5); the Dell console lands on a UART QEMU doesn't show — wire `-serial` to 0x1e783000 (or remap the machine's default UART) |
| Root | `root=/dev/mtdblock3` | SquashFS must sit in flash as the **4th MTD partition** (uboot/env/kernel/rootfs), not a ramdisk |
| Memory | `mem=96M` | pass in bootargs |
| Flash | uboot@0, env@0x20000, kernel@0x100000, rootfs@0x300000 | kernel(1.6M)+rootfs(8.6M) needs a **≥16 MB** flash — the machine's `mx25l6405d` (8 MB) is too small; bump the `kgpe-d16-bmc` FMC to a 16/32 MB chip |
| Machine id | (Avocent mach-type, TBD) | ATAGS boot via OpenBMC U-Boot needs the right `machid`; the proprietary kernel has no `DEBUG_LL`, so discover it from the kernel binary or the original U-Boot env |

## Remaining work (the hard, emulation-completeness criterion)

1. **Bigger flash** — change the `kgpe-d16-bmc` FMC model to ≥16 MB and lay the
   flash out as uboot/env/kernel/rootfs so `root=/dev/mtdblock3` resolves.
2. **Console** — wire QEMU's stdio serial to 0x1E783000 (the proprietary kernel
   uses its compiled-in `console=ttyS0`; a first probe with `console=ttyS1` in
   ATAGS stayed silent — the kernel either ignores the ATAGS console or halts at
   the machine-id check, which can't be seen without DEBUG_LL).
3. **Machine id** — recover the Avocent kernel's `MACH_TYPE` (from the kernel
   image or the firmware's U-Boot env) for the ATAGS hand-off.
4. **Survive device probes** — the firmware probes its full I2C tree (16×INA219,
   ADT7462, 16×TMP75, PCA9555/9548/9544, EEPROM — see the C410X DTS) and GPIOs;
   QEMU must model or tolerate enough of these that init reaches `appweb`. This
   is the genuine risk and the bulk of the work.
5. **Verify** — `curl` the forwarded web port and assert the BMC UI responds.

This is the highest-effort criterion (near-complete AST2050 peripheral
emulation). The firmware is extracted and the boot path is fully scoped; the
remaining steps are mechanical-but-large plus an open emulation-coverage risk.

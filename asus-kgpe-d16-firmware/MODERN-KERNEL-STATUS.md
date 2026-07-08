# Modern Linux (6.6.70) on the real KGPE-D16 AST2050 — status

Part of the full-OpenBMC bring-up (`docs/plans/2026-07-08-openbmc-ast2050-full-buildout.md`).
Everything here is over **P2A + TFTP**, no spispy/JTAG.

## ✅ DONE — a modern kernel boots on the real AST2050

**Linux 6.6.70 boots end-to-end on the real hardware** (the linchpin — the AST2050
is not in mainline; earliest is the AST2400/G4). Evidence (full dmesg captured):

```
## Booting kernel from Legacy Image ... Linux-6.6.70-dirty
## Flattened Device Tree blob at 43000000 ... Booting using the fdt blob
[    0.000000] OF: fdt: Machine model: ASUS KGPE-D16 BMC
[    0.000000] Normal   [mem 0x40000000-0x43ffffff]         # 64 MB
[    0.051138] ASPEED Unknown rev A0 (00000202)             # AST2050 recognised
[    0.340557] 1e784000.serial: ttyS4 ... 16550A  console [ttyS4] enabled
[    0.673611] ftgmac100 1e660000.ethernet: Read MAC address ...
[    3.586434] NFS: Registering the id_resolver key type    # NFS-root kernel
```

### What it took (all committed)
- **`aspeed-bmc-asus-kgpe-d16.dts` (QEMU, 6.6.70) → real-HW variant** (`dts/`): memory
  128→**64 MB**; dropped the `fixed-link` (QEMU-ism) so the ftgmac100 auto-scans MDIO.
- **U-Boot `CONFIG_OF_LIBFDT`** enabled → 3-arg `bootm K [R] D` passes the FDT.
- **SCU0C reset in `ddr2-init`** — a modern kernel gates "unused" clocks incl.
  **UARTCLK** (SCU0C[15]); the SCU survives the P2A watchdog reset, so the next
  U-Boot came up with a dead console until we restore SCU0C's default.
- **`clk_ignore_unused`** on the cmdline so the running kernel keeps the console clock.
- **`linux-boot.py`**: `--dtb` (3-arg bootm), `--no-initrd` (`bootm K - D` for NFS),
  `--tftp-gap` (8 s @115200 — the 20 s default silently truncated the capture).
- **Kernel rebuilt for real HW** (`kernel/kgpe-d16-realhw.config` +
  `build-realhw-kernel.py`): NFS root (`IP_PNP`+`ROOT_NFS`+`NFS_FS`+
  `NETWORK_FILESYSTEMS`), `netconsole` off.

## 🔶 BLOCKER — eth0 (ftgmac100, RMII) doesn't pass traffic on the modern kernel

NFS root (and all networking: OpenBMC/Redfish) is blocked on this. **U-Boot's driver
works** (it TFTP-loads the kernel over the same NIC), but the modern kernel's
ftgmac100 doesn't. Precisely characterised via **P2A register reads** while the
kernel runs:

- The **RMII PHY link negotiates fine**: a **Realtek RTL8201CP** at MDIO 0x20 is
  found; `MACCR=0x00080500` = `FAST_MODE`(100M)+`FULLDUP` → `adjust_link` saw the
  link **up at 100M/full**. So the SCU pinmux + RMII refclk (set by U-Boot) work.
- **But the MAC never stays enabled for traffic**: `MACCR` bits 0-3 (`TXDMA_EN`,
  `RXDMA_EN`, `TXMAC_EN`, `RXMAC_EN`) are **0**, and re-reads show `MACCR` flipping
  `0x00080500 → 0x00000000` — the driver is **resetting the MAC in a loop**.
- Result: the BMC transmits **0 packets** (confirmed by `tcpdump` on the Pi) → the
  NFS mount / IP-config never complete and the boot stalls.
- The driver warns **`Unsupported PHY mode rmii !`** — the aspeed ftgmac100 path
  (`ftgmac100.c`) only fully supports **RGMII** (+ NC-SI, + AST2500/2600 RMII via an
  `rmii_rclk` gate that the AST2400/2050 lacks). Real-PHY **RMII on AST2400/2050** is
  the gap. The Raptor 2.6.28 `ftgmac100_26.c` supported it (porting-guide Change 10).

### PINPOINTED (2026-07-09): the boot "hang" is `ip_auto_config` waiting on eth0's carrier
`initcall_debug` + `ignore_loglevel` (over `earlycon`) shows the **last initcall is
`ip_auto_config`** — it never returns. That's the kernel's `ip=` handler: it opens
eth0 and waits up to `CONF_CARRIER_TIMEOUT` (120 s) for the link. The console goes
silent because the wait is silent (not because the kernel/console died — a *no-root*
boot skips `ip_auto_config` and reaches `prepare_namespace`/panic fine). So the single
root cause is: **eth0's RMII carrier never comes up under the modern kernel** (U-Boot's
driver links fine; the kernel's ftgmac100 reset leaves the RMII link down). Everything
else (DDR2, console, load, DMA) is ruled out. Tooling to get here: `verify=y` +
`tmp/boot_retry.py` (reliable clean boots), `tmp/mac_regs.py` (P2A reg reads),
`initcall_debug ignore_loglevel`.

**RULED OUT the PHY (2026-07-09): `fixed-link` also fails.** Booted with a `fixed-link`
DTB (Generic PHY, immediate carrier, kernel never touches the RTL8201CP): the BMC
*still* sends **0 packets** (Pi tcpdump) and NFS never mounts. So it is **not** the PHY
reset / RMII-clock-direction — it is the **MAC-side RMII TX** in the modern ftgmac100
driver that is broken on the AST2050. U-Boot's ftgmac100 TXes fine (tftp works); the
kernel's does not. Localised to the MAC/RMII clocking in `ftgmac100.c`. Leading
candidate now: `ftgmac100_setup_clk` sets MACCLK to 100 MHz (or the missing RMII
`RCLK`/refclk gate the driver only handles for AST2500/2600) — U-Boot's AST2050 path
only de-asserts the MAC reset (SCU04[11]) and leaves the MAC clock at its default. Fix
to try: for the AST2050, skip/adjust the `setup_clk` rate and/or supply the RMII
refclk, matching U-Boot. Needs a driver patch + rebuild, or a shell to compare MAC
regs live.

(Superseded PHY hypothesis: the RTL8201CP RMII reference-clock direction —
In RMII the PHY can be strapped/registered to *output* the 50 MHz refclk (page-7 reg
`RMSR`); U-Boot sets it, but the kernel's `genphy_soft_reset` on open may revert it →
the MAC loses its RMII clock → no link. Fix candidates: a Realtek PHY fixup / DT PHY
node config for the RMII clock. — superseded, since fixed-link bypasses the PHY and
still fails.)

### Next steps for the NIC (the real-HW driver-porting work)
1. Read `ftgmac100_adjust_link` + the reset path (`ftgmac100_reset_task` /
   `ftgmac100_init_hw`/`start_hw`) — find why the link-change reset loops on the
   RMII path and doesn't leave TX/RX enabled. Likely fixes: mark the AST2050 MAC so
   the RMII branch configures clocking like AST2400 without the flap; or port the
   Raptor RMII setup; or add the AST2050 RMII refclk handling.
2. Cross-check **SCU48 (MAC clock delay)** and the `ftgmac100_setup_clk` 100 MHz
   `clk_set_rate` against what the AST2050 clock driver actually programs.
3. Iterate: patch `ftgmac100.c`, rebuild (`build-realhw-kernel.py`), boot NFS root,
   confirm packets on the Pi `tcpdump` + a completed mount.

Once eth0 passes traffic, the NFS root (server + export + busybox rootfs +
`inittab`/`rcS` are all staged on the Pi) mounts and Phase A2 completes, unblocking
A3 (driver audit) and Phase C (OpenBMC).

## ⚠️ Boot reliability (found while debugging the NIC — affects everything)

The modern-kernel boot on real HW is **flaky**: the *same* `uImage-kgpe-d16-realhw`
booted with a full dmesg on some attempts and **no console output at all** on others
(and stalls at varying points in between). This inconsistency — not the NIC — is what
made the eth0 symptoms so hard to pin down (the "console dies at ~4 s" is really the
kernel keeping going while the console stops, and some boots the kernel is corrupt
from the start). The likely cause is the **3.45 MB kernel being corrupted during the
tftp-into-DDR2 + reset-boot load** (DDR2 storage errors and/or an occasionally
imperfect reset-boot). The smaller 2.98 MB QEMU kernel booted reliably in the A1
tests; the larger real-HW kernel does not.

**Mitigation added:** `linux-boot.py` now `setenv verify y`, so U-Boot's `bootm`
CRC-checks the loaded uImage. On a **clean (CRC-OK) boot the console stays alive past
4 s** (`clk: Not disabling unused clocks` + the panic on a no-root boot are seen) —
so the earlier "console dies at 4 s" boots were **corrupted loads**, not a driver bug.

**DDR2 storage is NOT the cause** — a direct P2A test (`tmp/ddr2_test_host.py`, run via
`tmp/run_ddr2_test.py`) wrote a 16 MB deterministic pattern and read it back with **0
byte errors** (0.0000%). So the flakiness is not DRAM corruption. The remaining
inconsistency (some clean boots reach `prepare_namespace`, others stop a few ms
earlier) points to the **reset-boot mechanism / a kernel-init timing sensitivity** for
the larger real-HW kernel, not memory. **Next:** (a) make `linux-boot.py` retry until
`bootm` reports a clean CRC *and* the kernel reaches a known marker; (b) then, on a
confirmed-clean boot, resume the eth0 debug (a clean boot with `ftgmac100.dyndbg=+p`
should finally show whether eth0 links + the reset reason, or an `AHB bus error`).

## Boot recipe (today)
```sh
# modern kernel, NFS root (blocked on eth0):
uv run asus-kgpe-d16-firmware/linux-boot.py \
  --kernel uImage-kgpe-d16-realhw --dtb aspeed-bmc-asus-kgpe-d16-realhw.dtb --no-initrd \
  --bootargs "console=ttyS4,115200n8 clk_ignore_unused root=/dev/nfs \
    nfsroot=192.168.66.1:/srv/nfs/bmc,vers=3,tcp \
    ip=192.168.66.2:192.168.66.1:192.168.66.1:255.255.255.0:kgpe-d16:eth0:off rw"
```
Read MAC/SCU state live via P2A with `tmp/mac_regs.py`.

# Full modern-OpenBMC bring-up on the KGPE-D16 AST2050 — master plan

**Date:** 2026-07-08
**Goal (from @mithro):** finish the BMC setup on the real board — full U-Boot; a
**modern** Linux kernel (not the Raptor 2.6.28) with drivers for every peripheral
OpenBMC uses; full host control (virtual keyboard, serial-over-LAN, power on/off,
sensors); a working **OpenBMC Redfish API** for remote control; virtual-COM + VGA
capture; all **culvert** features; a modern, up-to-date **OpenBMC** running.
Development filesystem via **NFS root** (like the RPis in fpgas.online).

## Where we are (foundation — DONE, see the other docs)

All over **P2A + TFTP**, no spispy/JTAG:
- **U-Boot** boots interactively on the real AST2050 (`P2A-DRAM-BOOT-SEQUENCE.md`,
  `RAPTOR-UBOOT-BUILD.md`) — `boot#` prompt, 115200 on the PL011.
- **Linux** TFTP-boots to a shell (`LINUX-TFTP-BOOT.md`) — but the **Raptor 2.6.28**
  kernel + a tiny static-node initramfs. This is the piece to replace.
- **culvert** runs in-band; `devmem` bridge verified (`CULVERT-G3-HARDWARE-RESULTS.md`).
- **Permanent rig** (`rig/`): PXE for the host + TFTP for the BMC, reboot-proven.

## Hard constraints (what makes this non-trivial)

- **AST2050 (G3) is not in mainline Linux** (earliest is AST2400/G4). A modern kernel
  needs G3 support: device tree, the AST2050 clock/DDR differences, and confirming
  each aspeed driver binds on G3. *Partly done:* the C2/QEMU track already builds a
  modern kernel + `aspeed-bmc-asus-kgpe-d16.dtb` (`qemu-firmware/kernel/`), so the DT
  + config exist and boot under QEMU — real-HW boot + driver coverage is the work.
- **64 MB DRAM, ~48 MB usable** (8 MB VRAM). Modern OpenBMC is large → **NFS root** for
  the rootfs (kernel + a small initramfs to mount NFS); keep RAM for buffers.
- **Boot is P2A-only** → every kernel/U-Boot test needs the x86 host up (culvert runs
  on it). The host is a dependency and is currently network-down (recover first).
- **No writable boot flash on this bench** → nothing is persisted on the BMC; every
  boot is re-loaded over P2A. That's fine for development (NFS holds the state).

## Milestones (each independently verifiable; ⬜ todo, 🔶 partial, ✅ done)

### Phase A — Modern kernel on the real hardware
- **A0 ✅ Recover the x86 host** — PXE-boots SystemRescue 6.18.34 unattended (fixed the
  ISO loop-mount + NAT persistence); culvert rebuilt; P2A verified.
- **A1 ✅ Modern Linux 6.6.70 boots on the real AST2050** over P2A/TFTP. FDT U-Boot
  (`CONFIG_OF_LIBFDT`) 3-arg `bootm K I dtb` passes the DT (`Machine model: ASUS
  KGPE-D16 BMC`); 64 MB sizing; **ASPEED rev 0x202** recognized; **ftgmac100 + I2C +
  8250 console** all bind; console stays alive to userspace with **`clk_ignore_unused`**
  (the AST2050 clock driver gates UARTCLK otherwise, and that gating survives the
  SCU-preserving reset → also reset SCU0C in `ddr2-init`). Boots cleanly to the VFS
  root-mount (panics only for lack of a rootfs — expected → A2). tftp-gap fixed (8 s).
- **A2 🔶 NFS root.** NFS server + export + busybox rootfs + `inittab`/`rcS` ready on
  the Pi (`/srv/nfs/bmc`). Kernel rebuilt with NFS root (`kgpe-d16-realhw.config`:
  `IP_PNP`+`ROOT_NFS`+`NFS_FS`+`NETWORK_FILESYSTEMS`) → `uImage-kgpe-d16-realhw`.
  `linux-boot.py --no-initrd` boots `bootm K - D`. **Real-HW NIC issues found:**
  (1) DT `fixed-link` was a QEMU-ism → removed it (real DTS), now the ftgmac100
  auto-scans MDIO and finds the real **RTL8201CP** PHY at 0x20; (2) the kernel then
  hangs right after `netconsole: network logging started` — netconsole's netpoll
  stalls waiting for eth0's carrier (the QEMU fixed-link had an instant carrier) →
  **disabled `CONFIG_NETCONSOLE`** (rebuilding). tcpdump on the Pi saw **0 packets**
  from the BMC (consistent with the boot hanging before IP-config). **Root-caused
  (see `MODERN-KERNEL-STATUS.md`):** eth0's **RMII link negotiates** (RTL8201CP @0x20,
  MACCR shows 100M/full via `adjust_link`) but the driver **resets the MAC in a loop**
  (MACCR flaps `0x80500`↔`0`), so TX/RX enables never stick → 0 packets. The aspeed
  ftgmac100 warns `Unsupported PHY mode rmii` — real-PHY **RMII on AST2400/2050** is a
  driver gap (Raptor's `ftgmac100_26.c` had it; porting-guide Change 10). **This NIC
  driver fix is the current critical path** — it blocks NFS root + all OpenBMC
  networking. All infra staged: NFS server/export/rootfs on the Pi, `linux-boot.py`,
  `build-realhw-kernel.py`, `tmp/mac_regs.py` (live P2A register reads).
- **A3 ⬜ Peripheral driver coverage.** Every OpenBMC-used block binds on G3: I2C,
  GPIO, PWM/tach (fans), ADC (voltages), MAC/ftgmac, watchdog, LPC (KCS/BT/SNOOP for
  IPMI + host), eSPI/SuperIO, SPI/SMC, RTC, video/2D (for KVM), UART/VUART. Audit the
  DTB vs `dmesg`/`/sys` bind status; add/fix nodes + drivers per gap.

### Phase B — Full U-Boot
- **B1 ⬜ Env + boot flow.** Persist the environment (NFS or a saved image over P2A),
  DHCP/tftp/nfs boot scripts, a clean `bootcmd` that fetches kernel+dtb and NFS-boots.
- **B2 ⬜ U-Boot feature audit** (i2c, gpio, mmc-if-any, `bootm`/`booti`, mtd/sf,
  net) — enable what OpenBMC's flashing/recovery expects.

### Phase C — Modern OpenBMC userspace
- **C1 ⬜ Choose + build OpenBMC** for the AST2050. Options: (a) Yocto
  `openbmc` with a new `ast2050`/`kgpe-d16` machine (heavy; the "modern up-to-date"
  target); (b) bootstrap the phosphor stack onto a Debian NFS root for faster
  iteration, then converge to Yocto. Decide + document.
- **C2 ⬜ Boot OpenBMC to systemd + D-Bus** on the NFS root; `phosphor-*` services up.
- **C3 ⬜ bmcweb + Redfish** answering on the BMC's NIC (`/redfish/v1`), auth working.

### Phase D — Host control
- **D1 ⬜ Power/reset control** — GPIO → host power/reset button (KGPE-D16 GPIO map is
  RE'd; `dell-c410x-firmware/io-tables/gpio-pin-mapping.md` + the D16 DT). Redfish
  `ResetType`.
- **D2 ⬜ Sensors** — hwmon: CPU/board temps (I2C LM75/ADT7462-class), fan tach + PWM,
  voltage rails (ADC). Surface in Redfish `/Thermal` `/Power`.
- **D3 ⬜ Serial-over-LAN** — host COM ↔ AST2050 VUART/UART ↔ `obmc-console` ↔
  SSH/Redfish. (`/dev/serial-com1` is the host COM1 on the Pi today; on the BMC it's
  the VUART.)
- **D4 ⬜ Virtual keyboard/mouse** — USB-HID gadget (AST2050 USB2.0 device) → host.
- **D5 ⬜ VGA capture / KVM** — AST2050 video/2D engine → `obmc-ikvm` (VNC) + Redfish
  KVM. (Distinct from the external Magewell grab of the host VGA.)
- **D6 ⬜ Virtual COM port** — expose the captured host COM as a virtual port + over
  Redfish/SOL.

### Phase E — culvert full coverage
- **E1 ⬜ Exercise every culvert function in-band** (probe ✅, devmem ✅; sfc, console,
  otp, coprocessor, trace, read/write, reset — where the hardware supports it) and
  document pass/expected-absent per function. Fold real-HW fixes back to
  `mithro/culvert@ast2050-support`.

### Phase F — Integration
- **F1 ⬜ End-to-end Redfish control** of power/sensors/SOL/KVM from a remote client.
- **F2 ⬜ "Modern up-to-date OpenBMC"** — track a current OpenBMC release; CI build.

## Execution notes

- **Commit small + often; push after each milestone.** Each phase gets a status
  section here (updated as we go) + its own doc where it grows large.
- **NFS root** is the dev vehicle (state survives the P2A re-loads). A small initramfs
  mounts NFS; the heavy rootfs lives on the Pi.
- **Hardware test loop:** host up (A0) → `ddr2-init-p2a.py` → `p2a-image-boot.py`
  U-Boot → tftp kernel+dtb+initrd → NFS-boot. The `linux-boot.py` orchestrator
  generalises to this.

## Debug session findings (2026-07-08, NIC/boot) — see MODERN-KERNEL-STATUS.md

Extensive real-HW debugging of "eth0 doesn't work" narrowed it to a deeper issue:
- **Boot reliability:** the P2A/reset-boot load of the 3.45 MB kernel is occasionally
  bad. `verify=y` (bootm CRC) + a `boot_retry` wrapper (retry until clean CRC + kernel
  start) give reliable boots. **DDR2 is NOT the cause** (16 MB P2A pattern test = 0
  errors).
- **The real blocker is a kernel HANG at ~4.05 s**, not eth0 or the console: with
  `earlycon keep_bootcon` BOTH consoles (direct-MMIO earlycon + 8250) stop at the same
  instant → the kernel is hung, not the UART. It hangs *after* the driver initcalls
  (last seen: `dns_resolver registered`) and *before* `prepare_namespace`, so eth0 is
  never even opened on these boots. (A *no-root* boot reached `prepare_namespace`
  +panic at 4.18 s, so the hang point is somewhat variable.) Using `initcall_debug` to
  name the exact hanging initcall — that's the current front.

## Two-track plan (2026-07-09, @mithro: "both — QEMU build + NIC in parallel")

- **Track A — OpenBMC in QEMU (Phase C, running).** `git clone openbmc` →
  `. setup romulus` → `bitbake obmc-phosphor-image` (build log `/home/tim/openbmc-build.log`,
  ~6531 tasks, multi-hour). Goal: a modern OpenBMC + **Redfish/bmcweb** running in the
  QEMU `romulus-bmc` machine (full observability), then adapt the userspace toward the
  real AST2050 (SoC-agnostic phosphor/bmcweb runs over the NFS root once the NIC lands).
  romulus (ast2500) chosen for best QEMU+Redfish support; real-HW target is an
  ast2400-class kgpe-d16 machine + our modern AST2050 kernel.
- **Track B — real-HW NIC (deep-dive).** Register comparison done (SCU identical → not
  clock/pinmux; DMA-coherency config is correct). Remaining: inspect the live TX ring at
  `TXR_BADR` over P2A (descriptor OWN/pointer), or bisect vs Raptor `ftgmac100_26`
  (checked: DBLAC/ITC differ but U-Boot TXes with the modern DBLAC, so not those).

## Status log

- 2026-07-08: plan created. Foundation (U-Boot/Linux/culvert-devmem/rig) done.
  Starting **Phase A0** (recover host) → **A1** (modern kernel on real HW).
- 2026-07-08: **A1 prep done.** Modern kernel = **Linux 6.6.70** uImage-kgpe-d16 (DTB
  kernel, `aspeed-bmc-asus-kgpe-d16.dts` on `aspeed-g4.dtsi` + `aspeed,ast2050-scu`
  clock override). Fixes for real HW: DTB memory **128→64 MB** (recompiled
  `...-64mb.dtb`); U-Boot **`CONFIG_OF_LIBFDT` enabled** (was off) so 3-arg
  `bootm K I dtb` passes the FDT; `linux-boot.py --dtb` mode added. Console is
  **ttyS4** (uart5 = 0x1e784000 = UART2). Kernel .config already has the OpenBMC
  driver set: FTGMAC100, I2C/GPIO/SGPIO, **SENSORS_ASPEED** (fan/PWM), **ASPEED_ADC**,
  **KCS+BT IPMI-BMC**, LPC_CTRL+SNOOP, UART_ROUTING, P2A_CTRL, SPI_SMC. **Gaps for
  later:** `ASPEED_VIDEO` (KVM/VGA, D5) and an explicit VUART/`8250_aspeed_vuart`
  (SOL, D3) not yet enabled. Also fixed the rig: the host PXE HTTP rootfs
  (SystemRescue ISO) is now a **persistent fstab loop-mount** (was the missing piece).

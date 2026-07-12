# NIC crack — exact next-session steps (verified tooling)

The NIC blocker is **fully diagnosed**: `ftgmac100_open` (ndo_open) hard-hangs inside
`reset_and_config_mac` on the AST2050 → eth0 never comes up → NFS root + all real-HW
OpenBMC blocked. See `../NIC-MAC-REGISTER-COMPARISON.md` for the full bisection.

## 0. Power-cycle the rig first (REQUIRED)
On 2026-07-09 the P2A reset-boot went **severely flaky** (4/4+ `boot_retry` attempts fail
with `started=False`) after many boot/kill cycles — the AST2050/DDR2/SCU state is degraded.
Every boot experiment is blocked until the board is power-cycled. Toggle the Tasmota plug
`au-plug-10` OFF→ON (AC-restore + PXE are turnkey now, so the host auto-boots SystemRescue
and P2A comes back). Verify P2A: `uv run tmp/p2a_read.py read 0x1e6e207c` → `0x00000202`.

## 1. Boot the modern kernel so it hangs in ndo_open, then READ THE LOG BUFFER over P2A
The console dies ~4–7s (8250 UART), so use `__log_buf` instead (verified working this session):
```sh
# fix3 kernel = markers in ftgmac100_open + reset bisect (in the d16-qemu ftgmac100.c)
uv run tmp/boot_retry.py 4 -- --kernel uImage-kgpe-d16-fix3 --dtb kgpe-flclk.dtb --no-initrd \
  --bootargs "earlycon console=ttyS4,115200n8 clk_ignore_unused root=/dev/nfs \
    nfsroot=192.168.66.1:/srv/nfs/bmc,vers=3,tcp \
    ip=192.168.66.2:192.168.66.1:192.168.66.1:255.255.255.0:kgpe-d16:eth0:off rw" --watch 45
# after a clean boot (kernel now hung in ndo_open), dump the full dmesg from DRAM:
uv run tmp/read_logbuf.py 15     # reads __log_buf @ phys 0x40cffa2c (64KB) via culvert; strings|grep
```
`__log_buf` phys = virt `0x80cffa2c` − `0x40000000` (kernel PAGE_OFFSET 0x80000000, DRAM 0x40000000).
The last `AST2050-OPEN: stepN` / `reset_mac` line in the buffer = the exact hang point.
If messages exist **after** `reset_mac skipped` → it's the console (fix the 8250);
if it truly stops there → it's a real hang in the reset/usleep/MAC-write path.

## 2. Prime suspects for the fix (in order)
1. **RMII RCLK** — the driver does `devm_clk_get_optional("RCLK")` = NULL on the G3 DT; the
   AST2050 RMII MAC reset may need the 50 MHz RCLK. Add it to the DT / SCU and enable
   before `reset_and_config_mac`.
2. **A MAC clock/reset gate** re-touched between probe (works) and open (hangs) — read
   SCU0C/SCU04 over P2A at hang-time vs probe-time.
3. **ioremap memory-type / AHB write** — Linux's Device-memory write to MACCR stalls while
   U-Boot's flat-mapped write works; try a `dsb`/dummy-read, or match Raptor's sequence
   (`ftgmac100_26.c` sets PHY/clocks *before* touching MACCR and never polls SW_RST).

## 3. Once eth0 is up
`root=/dev/nfs` boots the OpenBMC rootfs (extract the romulus `.static.mtd`, or build a
kgpe-d16 machine) → real-HW Redfish + host control. Also unblocks culvert task E (in-band
`ip link set eth0 up` under ftrace, and the full feature exercise).

## Artifacts (staged on the Pi `/srv/tftp-bmc/`, built in `tmp/`)
- `uImage-kgpe-d16-fix3` — markers + skip-reset bisect kernel.
- `kgpe-flclk.dtb` — fixed-link + `clock-frequency=24000000` on UART2.
- `uImage-kgpe-d16-realhw-shell` — built-in-initramfs shell kernel (boot with `rdinit=/bin/sh`
  + NO `ip=` for interactive debug; 4.1 MB so flakier to load — power-cycle first).
- Tooling: `run_mac_block.py`, `run_tx_ring.py`, `run_poll_ring.py`, `read_logbuf.py`.

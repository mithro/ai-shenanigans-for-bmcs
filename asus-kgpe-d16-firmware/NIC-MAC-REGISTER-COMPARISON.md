# NIC: U-Boot (working) vs Linux (broken) MAC/SCU register comparison

The modern-kernel ftgmac100 doesn't TX on the AST2050 (0 packets on the wire) while
U-Boot's driver TXes fine over the same MAC. To isolate the difference, both states
were dumped over **P2A** (`tmp/mac_block_host.py` via `tmp/run_mac_block.py`):
- **U-Boot working**: booted U-Boot over P2A, did a `tftp` (aspeednic inits the MAC +
  TXes 3.4 MB successfully), then dumped the registers.
- **Linux**: booted the modern kernel (NFS-root), which opens eth0, then dumped.

## The decisive finding: the SCU is IDENTICAL

| SCU reg | U-Boot | Linux | |
|---|---|---|---|
| SCU04 reset-ctl (MAC1 rst=bit11) | `0x000ff658` | `0x000ff658` | same (MAC1 reset de-asserted) |
| SCU08 clk-sel | `0x61800070` | `0x61800070` | same |
| SCU0C clk-stop | `0x000c3e89` | `0x000c3e89` | same |
| **SCU48 MAC-clock-delay** | `0x00000000` | `0x00000000` | same |
| SCU70 hw-strap | `0x00819582` | `0x00819582` | same |
| **SCU74 pinmux** (RMII mode) | `0x4204d000` | `0x4204d000` | same |
| SCU80/88/90 pinmux | `0x0` | `0x0` | same |

→ **The RMII pinmux, clock select, MAC-clock-delay and reset are byte-for-byte the
same.** This *rules out the entire clock/pinmux/SCU class* as the cause (and confirms
the `setup_clk` MACCLK patch was a dead end — the clock is identical anyway).

## MAC block

| off | reg | U-Boot (working, post-tftp+halt) | Linux (varies) |
|---|---|---|---|
| 0x08 | MAC_MADR | `0x0000960e` | set to the same MAC (read from chip) |
| 0x0c | MAC_LADR | `0xceb95d8d` | same |
| 0x20 | TXR_BADR | `0x43fe9760` | set (Linux briefly showed `0x43fe9760`) |
| 0x24 | RXR_BADR | `0x43feb5a0` | set |
| 0x50 | MACCR | `0x00080500` (FAST+CRC_APD+FULLDUP) | seen `0x0008050f` (…+TXDMA/RXDMA/TXMAC/RXMAC EN) and `0x0` |
| 0x3c | DMAFIFOS | `0x0c000003` | `0x08001003` / `0x0c000000` |

Linux **does** reach a fully-enabled MAC (`MACCR=0x8050f`, TX/RX + DMA on, descriptors
set) — yet still **0 packets on the wire**. So with the *same SCU* and an equivalently
configured MAC, U-Boot TXes and Linux does not.

## Conclusion → where the fix must be

Since the SCU and the MAC control/enable/descriptor-base registers match U-Boot's
working state, the remaining suspects are **not** register config:
1. **DMA coherency (ARM926, VIVT cache, no HW DMA coherency).** If the kernel's
   `dma_alloc_coherent` TX descriptors/buffers aren't truly non-cacheable on the
   AST2050, the MAC reads stale descriptor data → nothing clocks out. (Mainline handles
   this for AST2400/ARM926, so check the AST2050 memory/cache/`dma-ranges` setup.)
2. **TX descriptor *content*** (OWN bit, buffer pointer/len) — read the ring at
   `TXR_BADR` over P2A during a TX attempt and compare with a valid U-Boot TX descriptor.
3. **RMII 50 MHz refclk physical path** — least likely given the identical SCU, but the
   refclk source (SoC-output vs external vs PHY-output) should be confirmed.

Captured dumps: `tmp/mac-uboot-working.txt`, `tmp/mac-linux-broken.txt`,
`tmp/mac-linux-fixedlink.txt`. Re-dump with `uv run tmp/run_mac_block.py`.

## 2026-07-09 update — TX descriptor ring probe + a capture-timing gotcha

Added `tmp/tx_ring_host.py` / `tmp/run_tx_ring.py` to dump the ftgmac100 TX descriptor
ring over P2A (decodes txdes0 OWN bit + txdes3 buffer address). **Key gotcha discovered:**
`TXR_BADR` reads `0x43fe9760` in *every* capture because that is **U-Boot's** ring, and
the captures kept landing during U-Boot's `tftp` phase (U-Boot uses a tiny 1-descriptor
ring with EDOTR set at txdes[0], OWN=SW). The `MACCR=0x8050f` "fully enabled" reading was
also U-Boot mid-tftp, **not** Linux. So the earlier "Linux reaches a fully-enabled MAC"
claim is unconfirmed — we have **not** yet cleanly captured Linux's own ring.

To get Linux's real state you must capture **after** the boot fully completes (Linux ~40s
in, sitting in the `ip_auto_config` carrier wait) — not during the U-Boot tftp.

### 2026-07-09 later — REFINED root cause: the MAC is UNCONFIGURED, not mis-TXing

The "flaky boots" turned out to be the **short `--watch` window** cutting off before
"Booting Linux": with `--watch 100` the kernel booted clean (exit 0). Capturing Linux's
*real* state (`run_mac_block.py`) after that boot gave **MACCR=0, MAC_MADR=0, TXR_BADR=0,
IER=0** — the MAC is **completely unconfigured**. So the earlier "MAC enabled but not
TXing" was wrong (that was U-Boot's tftp state); the truth is **`ftgmac100_open`/adjust_link
never configures the MAC**. The DTS uses the real RMII PHY (RTL8201CP @ MDIO 0x20,
`phy-mode="rmii"`, no fixed-link), and the driver logs `Unsupported PHY mode rmii !`. Chain:
`ndo_open` → `phy_start` → the PHY **never reports link-up** → `adjust_link(link=up)` is
never called → MACCR stays 0 → eth0 has no carrier → `ip_auto_config` waits 120s → fails →
0 packets. The console dies at ~4.05s (dns_resolver) so the ndo_open/PHY messages aren't
visible; `read_logbuf.py` only recovers the first ~7 lines (modern 6.6 kernel uses the
printk **ringbuffer/prb**, not the old flat `__log_buf`, so the reader needs a prb parser).

**Test done — fixed-link ALSO leaves the MAC unconfigured.** Built `tmp/kgpe-fixedlink.dtb`
(adds `fixed-link { speed=100; full-duplex; }` to bypass PHY negotiation). After a clean
fixed-link boot, `run_mac_block.py` still shows MACCR=0 / TXR_BADR=0. So it is **not**
purely PHY negotiation.

**Definitive poll** (`rig/nic-diag/run_poll_ring.py`, sample in `sample-ring-poll.txt`):
polling TXR_BADR/MACCR/MADR straight through a boot shows U-Boot's live state
(`TXR_BADR=0x43fe9760 MACCR=0x80500 MADR=0x960e`) during tftp, then at bootm everything
drops to **0 and stays 0 for ~74s** — `TXR_BADR` never becomes a Linux ring address. So
**Linux's `ftgmac100` never configures the MAC / never sets up its TX ring**: eth0 is
never brought up. The blocker is `ndo_open`/`ftgmac100_init_hw`/`adjust_link` bailing out
early — NOT TX-DMA, NOT the clock/pinmux/SCU, NOT the descriptor content.

**To find the exact bail-out** you need the kernel messages from `ndo_open`. The console
does NOT actually die at 4s — it's just quiet; adding `initcall_debug` (keeps printing)
carries it to ~7s. That revealed the smoking gun.

### 2026-07-09 FINAL — ndo_open HANGS; MAC control-block WRITES stall the AHB

Booting `kgpe-flclk.dtb` (fixed-link + `clock-frequency=24000000` on the UART) with
`earlycon initcall_debug ignore_loglevel ftgmac100.dyndbg=+pmf` + step markers added to
`ftgmac100_open` showed:
```
[7.038] calling ip_auto_config
[7.042] AST2050-OPEN: step1 alloc_rings
[7.046] AST2050-OPEN: step2 reset_and_config_mac   <-- then HANG (no step3)
```
So **`ftgmac100_open` hangs inside `ftgmac100_reset_and_config_mac`** and never returns —
this is a hard hang, not a carrier wait. `ip_auto_config` never completes; the MAC is
left at U-Boot's config (`MACCR=0x80500`), eth0 never comes up, 0 Linux packets.

Bisecting `ftgmac100_reset_mac` (patches applied live in the d16-qemu kernel tree):
- Skipping the SW_RST **poll** (keeping the writes): still hangs at step2 → not the poll.
- Skipping the SW_RST **write** (keeping the first `iowrite32(maccr)`): still hangs at
  step2 → the first `iowrite32(MACCR)` itself stalls.
- Skipping the **entire** `reset_mac` (no writes, just a marker): prints "reset_mac
  skipped" then hangs before step3 → the NEXT MAC write (in `init_hw`/`init_all`) stalls.

**Conclusion: any WRITE to the MAC control block hangs the CPU during `ndo_open`, while
READs worked at probe (5.9s).** Root cause is a clock/reset/AHB-state that differs between
probe-time and open-time in the post-P2A-reset-boot Linux context (candidates: a MAC clock
gate the clk framework re-gates despite `clk_ignore_unused`; the RMII RCLK the driver
skips for "AST2400"; or an AHB-arbitration interaction with the live P2A bridge). U-Boot's
writes work because it sets the MAC clocks its own way before writing.

**Next (bounded):** add a marker to `ftgmac100_init_hw` to confirm the write-stall there;
read SCU0C/SCU04/the MAC clock-gate over P2A *at the moment of the hang* (compare vs probe
time); try enabling the RMII RCLK; or bisect the MAC clock setup against Raptor's
`ftgmac100_26` init (which sets up PHY/clocks before touching MACCR). The diagnostic
scaffolding (open-step markers + reset bisect) is live in the d16-qemu `ftgmac100.c`.

### 2026-07-09 refinement — the hang survives skipping ALL reset register writes
Booting the skip-entire-`reset_mac` kernel with **minimal** console (no initcall_debug) put
ndo_open at 4.1s and still stopped at exactly `reset_mac skipped (G3)` — and eth0 stayed
down (MACCR=0x80500, ping fails, only U-Boot tftp packets on the wire). Since that build
does **zero** MAC register writes in the reset path, the freeze point is now the
`usleep_range()` between the two reset calls (or the console dying at that instant). Two
important consequences: (a) the "MAC-write-stall" is not the whole story — the hang
persists with no writes; (b) console-blocking is **not** it either (minimal console, still
dead). **This is no longer productively debuggable blind.** The reliable next move is an
**interactive shell**: boot the modern kernel with a bundled initramfs + `rdinit=/bin/sh`
+ **no `ip=`** (so `ip_auto_config` never auto-opens eth0 and can't hang the boot). From a
shell you can `dmesg`, then `ip link set eth0 up` under `strace`/ftrace and watch exactly
where `ndo_open` blocks, and read the printk ringbuffer directly. That same shell also
unblocks the culvert in-band feature exercise (project task E). The console reaches the
shell fine (it's quiet, not dead) with `console=ttyS4` + the `clock-frequency=24000000`
UART pin (`kgpe-flclk.dtb`).

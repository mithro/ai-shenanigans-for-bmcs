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
in, sitting in the `ip_auto_config` carrier wait) — not during the U-Boot tftp. On
2026-07-09 this was blocked by **boot flakiness**: 4 consecutive `boot_retry` attempts
failed, including a *new* mode where the full 3.4 MB kernel + DTB load cleanly (bytes
transferred OK) yet bootm never prints "Booting Linux" (`started=False`). That points to
a degraded U-Boot/reset-boot state after many boot+kill cycles (or a `linux-boot.py`
bootm-timing issue), independent of the NIC. **Next session, on a fresh rig:** get one
clean fixed-link boot, then `run_mac_block.py` + `run_tx_ring.py` to see Linux's ring —
if txdes[0] shows OWN=MAC persistently, the MAC isn't consuming (refclk/PHY-timing); if
OWN=SW with no buffer, the driver never queued (higher layer / DMA).

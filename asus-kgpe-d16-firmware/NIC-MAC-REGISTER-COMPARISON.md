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
